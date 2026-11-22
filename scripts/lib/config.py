#!/usr/bin/env python3
"""Resolve the safe, allowlisted effective configuration through Docker Compose."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

MIN_COMPOSE = (2, 23, 0)
SERVICE_NAME = "chiv-x64"

MOUNT_TARGETS = {
    "/game": "CHIV_GAME",
    "/opt/cli": "CLI_DIR",
    "/proton/GE-Proton11-11-x86_64": "PROTON_DIR",
    "/proton-compat-client": "COMPAT_CLIENT_DIR",
    "/opt/legendary": "LEGENDARY_CONFIG",
    "/proton-prefix": "CHIV_PREFIX",
    "/proton-prefix/pfx/drive_c/users/steamuser/AppData/Local/Chivalry 2":
        "CHIV_LOCALAPPDATA",
}
PORT_ENVIRONMENT = {
    "GAME_PORT": "game",
    "PING_PORT": "ping",
    "QUERY_PORT": "query",
    "RCON_PORT": "rcon",
}
INTERPOLATION_ENVIRONMENT_KEYS = {
    "IMAGE_NAME",
    "CONTAINER_NAME",
    "SERVER_NAME",
    "SAVED_DIR_SUFFIX",
    "SERVER_ADVERTISE_IP",
    "SERVER_BROWSER_BACKEND",
    "GAME_PORT",
    "PING_PORT",
    "QUERY_PORT",
    "RCON_PORT",
    "DISPLAY_NUM",
    "CHIV_GAME",
    "CLI_DIR",
    "PROTON_DIR",
    "COMPAT_CLIENT_DIR",
    "LEGENDARY_CONFIG",
    "CHIV_PREFIX",
    "CHIV_LOCALAPPDATA",
}


class ConfigError(Exception):
    """A safe-to-display configuration failure."""

    exit_code = 2


class ComposeUnavailable(ConfigError):
    """Compose is missing or lacks the required machine-readable interface."""

    exit_code = 3

def _run_compose(args: list[str], *, root: Path,
                 runner=subprocess.run,
                 environment: dict[str, str] | None = None
                 ) -> subprocess.CompletedProcess[str]:
    try:
        options: dict[str, Any] = {
            "cwd": root,
            "text": True,
            "capture_output": True,
            "check": False,
        }
        if environment is not None:
            options["env"] = environment
        return runner(["docker", "compose", *args], **options)
    except OSError:
        raise ComposeUnavailable(
            "Docker Compose is unavailable. Install Docker Compose v2.23.0 or newer "
            "and ensure `docker` is on PATH."
        ) from None


def _version_tuple(output: str) -> tuple[int, int, int] | None:
    match = re.search(r"\bv?(\d+)\.(\d+)\.(\d+)\b", output)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _compose_document(root: Path, runner=subprocess.run,
                      env_file: Path | None = None) -> dict[str, Any]:
    version = _run_compose(["version", "--short"], root=root, runner=runner)
    parsed_version = _version_tuple(version.stdout) if version.returncode == 0 else None
    if parsed_version is None or parsed_version < MIN_COMPOSE:
        raise ComposeUnavailable(
            "Docker Compose v2.23.0 or newer is required for machine-readable "
            "configuration. Upgrade Compose, then retry."
        )

    command = ["--project-directory", str(root)]
    environment = None
    if env_file is not None:
        command += ["--env-file", str(env_file), "--file", str(root / "docker-compose.yml")]
        environment = os.environ.copy()
        for key in INTERPOLATION_ENVIRONMENT_KEYS:
            environment.pop(key, None)
    rendered = _run_compose(
        [*command, "config", "--format", "json"],
        root=root,
        runner=runner,
        environment=environment,
    )
    if rendered.returncode != 0:
        raise ConfigError(
            "Compose could not resolve this project. Check .env syntax, required "
            "settings, and the Compose file; detailed output is suppressed to "
            "protect interpolated values."
        )
    try:
        document = json.loads(rendered.stdout)
    except (json.JSONDecodeError, TypeError):
        raise ComposeUnavailable(
            "Compose returned invalid machine-readable configuration. Verify "
            "Docker Compose v2.23.0 or newer."
        ) from None
    if not isinstance(document, dict):
        raise ConfigError("Compose returned an unsupported configuration format.")
    return document


def _mount_sources(service: dict[str, Any]) -> dict[str, str]:
    volumes = service.get("volumes")
    if not isinstance(volumes, list):
        raise ConfigError("Compose service is missing its expected bind mounts.")

    by_target: dict[str, str] = {}
    for volume in volumes:
        if not isinstance(volume, dict):
            continue
        target = volume.get("target")
        source = volume.get("source")
        if isinstance(target, str) and isinstance(source, str):
            by_target[target] = source

    result: dict[str, str] = {}
    for target, variable in MOUNT_TARGETS.items():
        # CHIV_LOCALAPPDATA is a nested mount beneath CHIV_PREFIX and must be
        # selected by its exact target.
        source = by_target.get(target)
        if source is None:
            raise ConfigError(
                f"Compose service is missing the configured {variable} mount."
            )
        result[variable] = source
    return result


def _ports(environment: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for variable, name in PORT_ENVIRONMENT.items():
        raw = environment.get(variable)
        try:
            port = int(raw)
        except (TypeError, ValueError):
            raise ConfigError(
                f"Compose service has an invalid {variable} value."
            ) from None
        if not 1 <= port <= 65535:
            raise ConfigError(f"Compose service has an invalid {variable} value.")
        result[name] = port
    if len(set(result.values())) != len(result):
        raise ConfigError("Compose service game, ping, query, and RCON ports must differ.")
    return result


def resolve(root: Path, runner=subprocess.run,
            env_file: Path | None = None) -> dict[str, Any]:
    """Return only the documented, non-secret service settings."""
    document = _compose_document(
        root.resolve(),
        runner=runner,
        env_file=env_file.resolve() if env_file is not None else None,
    )
    services = document.get("services")
    service = services.get(SERVICE_NAME) if isinstance(services, dict) else None
    if not isinstance(service, dict):
        raise ConfigError(f"Compose service {SERVICE_NAME} is missing.")

    environment = service.get("environment")
    if not isinstance(environment, dict):
        raise ConfigError("Compose service environment is missing or unsupported.")

    def required_string(source: dict[str, Any], key: str) -> str:
        value = source.get(key)
        if not isinstance(value, str) or not value:
            raise ConfigError(f"Compose service is missing {key}.")
        return value

    return {
        "service": SERVICE_NAME,
        "image": required_string(service, "image"),
        "container_name": required_string(service, "container_name"),
        "user": required_string(service, "user"),
        "paths": _mount_sources(service),
        "ports": _ports(environment),
        "display": required_string(environment, "DISPLAY"),
        "advertise_ip": required_string(environment, "SERVER_ADVERTISE_IP"),
        "server_name": required_string(environment, "SERVER_NAME"),
        "server_browser_backend": required_string(
            environment, "SERVER_BROWSER_BACKEND"
        ),
        "saved_dir_suffix": required_string(environment, "SAVED_DIR_SUFFIX"),
    }


def validate_inputs(config: dict[str, Any]) -> None:
    required_paths = (
        "CHIV_GAME",
        "CLI_DIR",
        "PROTON_DIR",
        "COMPAT_CLIENT_DIR",
        "LEGENDARY_CONFIG",
    )
    for variable in required_paths:
        path = Path(config["paths"][variable]).expanduser()
        if not path.is_dir():
            raise ConfigError(
                f"{variable} must point to an existing directory. "
                "Check the path in .env."
            )

    cli = Path(config["paths"]["CLI_DIR"]).expanduser() / "UnchainedLauncher.CLI"
    if not cli.is_file():
        raise ConfigError("UnchainedLauncher.CLI was not found in CLI_DIR.")

    proton = Path(config["paths"]["PROTON_DIR"]).expanduser() / "proton"
    if not proton.is_file():
        raise ConfigError("The Proton executable was not found in PROTON_DIR.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve the allowlisted effective chiv-x64 Compose settings."
    )
    parser.add_argument(
        "--check-inputs",
        action="store_true",
        help="validate required host inputs and print only a safe summary",
    )
    parser.add_argument(
        "--udp-ports",
        action="store_true",
        help="print the configured game, ping, and query UDP ports",
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]

    try:
        config = resolve(root)
        if args.check_inputs:
            validate_inputs(config)
            print("Configuration and required input paths look valid.")
            print("Full Compose output and secret values were not printed.")
        elif args.udp_ports:
            print(",".join(
                str(config["ports"][name]) for name in ("game", "ping", "query")
            ))
        else:
            print(json.dumps(config, sort_keys=True))
        return 0
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
