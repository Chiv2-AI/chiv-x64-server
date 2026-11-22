#!/usr/bin/env python3
"""Generate a private .env file without provisioning or launching the server."""

from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Callable

try:
    from .config import ConfigError, resolve
except ImportError:  # Direct script execution from scripts/setup.sh.
    from config import ConfigError, resolve


REQUIRED = (
    "SERVER_ADVERTISE_IP",
    "CHIV_GAME",
    "CLI_DIR",
    "LOCAL_REGISTRY",
    "PROTON_DIR",
    "COMPAT_CLIENT_DIR",
    "LEGENDARY_CONFIG",
)
OPTIONAL = (
    "SERVER_NAME",
    "SAVED_DIR_SUFFIX",
    "SERVER_BROWSER_BACKEND",
    "GAME_PORT",
    "PING_PORT",
    "QUERY_PORT",
    "RCON_PORT",
    "DISPLAY_NUM",
    "CONTAINER_NAME",
    "IMAGE_NAME",
    "CHIV_PREFIX",
    "CHIV_LOCALAPPDATA",
)
DEFAULTS = {
    "CHIV_GAME": "./game",
    "CLI_DIR": "./cli",
    "LOCAL_REGISTRY": "./cli/local-registry3",
    "PROTON_DIR": "./proton/GE-Proton11-11-x86_64",
    "COMPAT_CLIENT_DIR": "./proton/compat-client",
    "LEGENDARY_CONFIG": "./legendary-config",
}
COMPOSE_DEFAULTS = {
    "SERVER_NAME": "x64 EGS CLI server",
    "SAVED_DIR_SUFFIX": "UnchainedX64",
    "SERVER_BROWSER_BACKEND": "https://servers.polehammer.net",
    "GAME_PORT": "7777",
    "PING_PORT": "3075",
    "QUERY_PORT": "7071",
    "RCON_PORT": "9001",
    "DISPLAY_NUM": "99",
    "CHIV_PREFIX": "./state/prefix",
    "CHIV_LOCALAPPDATA": "./state/appdata",
}
ARGUMENTS = {
    "server_advertise_ip": "SERVER_ADVERTISE_IP",
    "chiv_game": "CHIV_GAME",
    "cli_dir": "CLI_DIR",
    "local_registry": "LOCAL_REGISTRY",
    "proton_dir": "PROTON_DIR",
    "compat_client_dir": "COMPAT_CLIENT_DIR",
    "legendary_config": "LEGENDARY_CONFIG",
    "server_name": "SERVER_NAME",
    "saved_dir_suffix": "SAVED_DIR_SUFFIX",
    "server_browser_backend": "SERVER_BROWSER_BACKEND",
    "game_port": "GAME_PORT",
    "ping_port": "PING_PORT",
    "query_port": "QUERY_PORT",
    "rcon_port": "RCON_PORT",
    "display_num": "DISPLAY_NUM",
    "container_name": "CONTAINER_NAME",
    "image_name": "IMAGE_NAME",
    "chiv_prefix": "CHIV_PREFIX",
    "chiv_localappdata": "CHIV_LOCALAPPDATA",
}


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Guided configuration only. This does not authenticate, download, "
            "build, or start the server."
        )
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="never prompt; require every required setting as an option",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="validate answers with Compose without writing .env",
    )
    for option, variable in ARGUMENTS.items():
        parser.add_argument(
            "--" + option.replace("_", "-"),
            dest=option,
            metavar=variable,
            help=f"value for {variable}",
        )
    return parser


def _ask(prompt: Callable[[str], str], variable: str, default: str | None) -> str:
    suffix = f" [{default}]" if default else ""
    value = prompt(f"{variable}{suffix}: ")
    if value == "" and default is not None:
        return default
    return value


def gather_values(
    args: argparse.Namespace,
    prompt: Callable[[str], str],
) -> dict[str, str]:
    values: dict[str, str] = {}
    for variable in REQUIRED:
        argument = next(name for name, key in ARGUMENTS.items() if key == variable)
        value = getattr(args, argument)
        if value is None and not args.non_interactive:
            value = _ask(prompt, variable, DEFAULTS.get(variable))
        if value is not None:
            values[variable] = value

    for variable in OPTIONAL:
        argument = next(name for name, key in ARGUMENTS.items() if key == variable)
        value = getattr(args, argument)
        if value is None and not args.non_interactive:
            value = _ask(prompt, variable, None)
        if value is not None and value != "":
            values[variable] = value
    return values


def validate_values(values: dict[str, str]) -> None:
    missing = [key for key in REQUIRED if not values.get(key, "").strip()]
    if missing:
        raise ValueError("Missing required settings: " + ", ".join(missing))

    for key, value in values.items():
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError(f"{key} must not contain control characters.")
        if "\\" in value:
            raise ValueError(
                f"{key} contains a backslash; use a Linux path without backslashes."
            )
        if "'" in value:
            raise ValueError(
                f"{key} contains a single quote, which this helper does not accept. "
                "Use a path/name without single quotes."
            )

    try:
        address = ipaddress.ip_address(values["SERVER_ADVERTISE_IP"])
    except ValueError:
        raise ValueError("SERVER_ADVERTISE_IP must be a literal global IPv6 address.") from None
    if address.version != 6 or not address.is_global:
        raise ValueError("SERVER_ADVERTISE_IP must be a literal global IPv6 address.")

    ports = {}
    for key, default in (
        ("GAME_PORT", "7777"),
        ("PING_PORT", "3075"),
        ("QUERY_PORT", "7071"),
        ("RCON_PORT", "9001"),
    ):
        raw = values.get(key, default)
        if not re.fullmatch(r"\d+", raw):
            raise ValueError(f"{key} must be an integer from 1 to 65535.")
        port = int(raw)
        if not 1 <= port <= 65535:
            raise ValueError(f"{key} must be an integer from 1 to 65535.")
        ports[key] = port
    if len(set(ports.values())) != len(ports):
        raise ValueError("GAME_PORT, PING_PORT, QUERY_PORT, and RCON_PORT must differ.")

    if "DISPLAY_NUM" in values:
        if not re.fullmatch(r"\d{1,5}", values["DISPLAY_NUM"]):
            raise ValueError("DISPLAY_NUM must be an integer from 0 to 65535.")
        if int(values["DISPLAY_NUM"]) > 65535:
            raise ValueError("DISPLAY_NUM must be an integer from 0 to 65535.")
    if "CONTAINER_NAME" in values and not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]*", values["CONTAINER_NAME"]
    ):
        raise ValueError("CONTAINER_NAME contains characters unsupported by Docker.")
    if "IMAGE_NAME" in values and any(char.isspace() for char in values["IMAGE_NAME"]):
        raise ValueError("IMAGE_NAME must not contain whitespace.")


def render_env(values: dict[str, str]) -> str:
    return "".join(f"{key}='{values[key]}'\n" for key in (*REQUIRED, *OPTIONAL)
                   if key in values)


def _validate_with_compose(root: Path, content: str, resolver=resolve) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=".setup-env-", dir=root)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        stream = os.fdopen(fd, "w", encoding="utf-8", newline="\n")
        fd = -1
        with stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        resolver(root, env_file=temporary_path)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _write_new_env(path: Path, content: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    created = os.fstat(fd)
    try:
        os.fchmod(fd, 0o600)
        data = content.encode("utf-8")
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
    except BaseException:
        os.close(fd)
        try:
            current = path.lstat()
            if current.st_dev == created.st_dev and current.st_ino == created.st_ino:
                path.unlink()
        except OSError:
            pass
        raise
    else:
        os.close(fd)


def run_setup(
    argv: list[str] | None = None,
    *,
    root: Path | None = None,
    prompt: Callable[[str], str] = input,
    resolver=resolve,
) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    project_root = (root or Path(__file__).resolve().parents[2]).resolve()
    destination = project_root / ".env"

    if os.path.lexists(destination):
        print(
            "ERROR: .env already exists (including a symlink). Back it up or "
            "remove it deliberately before running setup again.",
            file=sys.stderr,
        )
        return 2

    if args.non_interactive:
        missing_args = [
            ARGUMENTS[key]
            for key in ARGUMENTS
            if ARGUMENTS[key] in REQUIRED
            and getattr(args, key) is None
        ]
        if missing_args:
            print(
                "ERROR: --non-interactive requires: "
                + ", ".join("--" + key.lower().replace("_", "-") for key in missing_args),
                file=sys.stderr,
            )
            return 2

    try:
        if not args.non_interactive:
            print(
                "Configure paths and server settings for files you already "
                "acquired. See README.md and docs/development.md for EGS, "
                "Proton, prefix, and CLI prerequisites."
            )
            print(
                "No login, download, directory creation, or credential copying "
                "is performed; LEGENDARY_CONFIG is a private directory path."
            )
        values = gather_values(args, prompt)
        validate_values(values)
        content = render_env(values)
        _validate_with_compose(project_root, content, resolver=resolver)
        if args.check_only:
            print("Configuration answers passed Compose validation; no .env was written.")
            return 0
        _write_new_env(destination, content)
    except (EOFError, KeyboardInterrupt):
        print("Cancelled; no .env was written.", file=sys.stderr)
        return 130
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    except FileExistsError:
        print(
            "ERROR: .env was created concurrently; it was not overwritten.",
            file=sys.stderr,
        )
        return 2
    except OSError:
        print("ERROR: Could not safely write or validate the configuration.", file=sys.stderr)
        return 4

    print("Created .env with mode 0600. Credentials were not requested or copied.")
    print("Next: review the setup guide and run ./scripts/check-config.sh.")
    print(
        "Warning: ./scripts/start.sh can publicly register the server; review "
        "registration settings before starting."
    )
    return 0


def main() -> int:
    try:
        return run_setup()
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2


if __name__ == "__main__":
    raise SystemExit(main())
