import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

import scripts.lib.config as config_module
from scripts.lib.config import ConfigError, resolve, validate_inputs
from scripts.lib.config import _version_tuple
from scripts.lib.setup import REQUIRED as SETUP_REQUIRED, render_env


def rendered_config(
    game="/srv/game",
    ports=None,
):
    ports = ports or {
        "GAME_PORT": "7777",
        "PING_PORT": "3075",
        "QUERY_PORT": "7071",
        "RCON_PORT": "9001",
    }
    volumes = [
        (game, "/game"),
        ("/srv/cli", "/opt/cli"),
        ("/srv/proton", "/proton/GE-Proton11-11-x86_64"),
        ("/srv/compat", "/proton-compat-client"),
        ("/srv/legendary", "/opt/legendary"),
        ("/srv/prefix", "/proton-prefix"),
        ("/srv/appdata", "/proton-prefix/pfx/drive_c/users/steamuser/AppData/Local/Chivalry 2"),
    ]
    environment = {
        **ports,
        "DISPLAY": ":101",
        "SERVER_ADVERTISE_IP": "2001:db8::42",
        "SERVER_NAME": "fixture server",
        "SERVER_BROWSER_BACKEND": "https://example.invalid",
        "SAVED_DIR_SUFFIX": "FixtureSuffix",
        "AUTH_TOKEN": "secret-env-canary",
    }
    return {
        "services": {
            "chiv-x64": {
                "image": "fixture-image:local",
                "container_name": "fixture-container",
                "user": "1000:1000",
                "environment": environment,
                "volumes": [
                    {"type": "bind", "source": source, "target": target}
                    for source, target in volumes
                ],
                # A canary here must never appear in resolver output.
                "command": "fixture-secret-canary",
            }
        }
    }


class FakeCompose:
    def __init__(self, document=None, version="v2.30.0", config_error=None):
        self.document = document or rendered_config()
        self.version = version
        self.config_error = config_error
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        if command[2:] == ["version", "--short"]:
            return subprocess.CompletedProcess(
                command, 0, self.version + "\n", ""
            )
        if self.config_error is not None:
            return subprocess.CompletedProcess(
                command, 1, "secret-canary stdout", self.config_error
            )
        return subprocess.CompletedProcess(
            command, 0, json.dumps(self.document), ""
        )


class ConfigResolverTests(unittest.TestCase):
    def test_only_allowlisted_compose_values_are_returned(self):
        fake = FakeCompose()
        config = resolve(Path.cwd(), runner=fake)

        self.assertEqual(config["ports"], {
            "game": 7777,
            "ping": 3075,
            "query": 7071,
            "rcon": 9001,
        })
        self.assertEqual(config["paths"]["CHIV_GAME"], "/srv/game")
        self.assertEqual(config["saved_dir_suffix"], "FixtureSuffix")
        self.assertNotIn("command", json.dumps(config))
        self.assertNotIn("fixture-secret-canary", json.dumps(config))
        self.assertNotIn("secret-env-canary", json.dumps(config))
        self.assertEqual(fake.calls[1][-3:], ["config", "--format", "json"])

    def test_compose_rendered_overrides_and_special_path_characters_are_preserved(self):
        special_path = "/tmp/chiv install/#folder/$dollar"
        fake = FakeCompose(document=rendered_config(
            game=special_path,
            ports={
                "GAME_PORT": "18001",
                "PING_PORT": "18002",
                "QUERY_PORT": "18003",
                "RCON_PORT": "18004",
            },
        ))
        config = resolve(Path.cwd(), runner=fake)

        self.assertEqual(config["paths"]["CHIV_GAME"], special_path)
        self.assertEqual(config["ports"]["game"], 18001)
        self.assertEqual(config["ports"]["query"], 18003)

    def test_compose_error_output_is_suppressed(self):
        fake = FakeCompose(config_error="secret-canary error")
        with self.assertRaises(ConfigError) as raised:
            resolve(Path.cwd(), runner=fake)
        self.assertNotIn("secret-canary", str(raised.exception))

        stdout = StringIO()
        stderr = StringIO()
        with patch.object(
            config_module, "resolve",
            side_effect=lambda root: resolve(root, runner=fake),
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = config_module.main([])
        self.assertEqual(code, 2)
        self.assertNotIn("secret-canary", stdout.getvalue() + stderr.getvalue())

    def test_old_compose_version_fails_with_actionable_message(self):
        fake = FakeCompose(version="v2.22.0")
        with self.assertRaisesRegex(ConfigError, "v2.23.0 or newer"):
            resolve(Path.cwd(), runner=fake)
        self.assertEqual(len(fake.calls), 1)

    def test_missing_mount_and_invalid_port_fail_clearly(self):
        document = rendered_config()
        document["services"]["chiv-x64"]["volumes"] = []
        with self.assertRaisesRegex(ConfigError, "CHIV_GAME mount"):
            resolve(Path.cwd(), runner=FakeCompose(document=document))

        document = rendered_config()
        document["services"]["chiv-x64"]["environment"]["GAME_PORT"] = "not-a-port"
        with self.assertRaisesRegex(ConfigError, "GAME_PORT"):
            resolve(Path.cwd(), runner=FakeCompose(document=document))

        document = rendered_config()
        document["services"]["chiv-x64"]["environment"]["RCON_PORT"] = "7777"
        with self.assertRaisesRegex(ConfigError, "ports must differ"):
            resolve(Path.cwd(), runner=FakeCompose(document=document))

    def test_required_input_checks_do_not_echo_private_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "paths": {
                    "CHIV_GAME": str(root / "missing private path"),
                    "CLI_DIR": str(root),
                    "PROTON_DIR": str(root),
                    "COMPAT_CLIENT_DIR": str(root),
                    "LEGENDARY_CONFIG": str(root),
                }
            }
            with self.assertRaises(ConfigError) as raised:
                validate_inputs(config)
        self.assertNotIn(tmp, str(raised.exception))


def compose_is_supported():
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "compose", "version", "--short"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    version = _version_tuple(result.stdout) if result.returncode == 0 else None
    return version is not None and version >= (2, 23, 0)


@unittest.skipUnless(compose_is_supported(), "Docker Compose v2.23+ is unavailable")
class ComposeIntegrationTests(unittest.TestCase):
    def _compose_fixture(self, root: Path, game_path: str) -> None:
        for name in ("cli", "proton", "compat", "legendary",
                     "prefix", "appdata", "state/prefix", "state/appdata"):
            (root / name).mkdir(parents=True, exist_ok=True)
        game = Path(game_path)
        game.mkdir(parents=True, exist_ok=True)
        env_lines = [
            "CHIV_GAME='%s'" % game_path,
            "CLI_DIR=%s" % (root / "cli"),
            "PROTON_DIR=%s" % (root / "proton"),
            "COMPAT_CLIENT_DIR=%s" % (root / "compat"),
            "LEGENDARY_CONFIG=%s" % (root / "legendary"),
            "SERVER_ADVERTISE_IP=2001:db8::42",
            "GAME_PORT=17001",
            "PING_PORT=17002",
            "QUERY_PORT=17003",
            "RCON_PORT=17004",
        ]
        (root / ".env").write_text("\n".join(env_lines) + "\n")
        (root / "docker-compose.yml").write_text(
            """services:
  chiv-x64:
    image: "${IMAGE_NAME:-fixture:local}"
    container_name: "${CONTAINER_NAME:-fixture}"
    user: "1000:1000"
    environment:
      DISPLAY: ":${DISPLAY_NUM:-99}"
      SERVER_ADVERTISE_IP: "${SERVER_ADVERTISE_IP:?required}"
      SERVER_NAME: "${SERVER_NAME:-fixture}"
      SERVER_BROWSER_BACKEND: "${SERVER_BROWSER_BACKEND:-https://example.invalid}"
      SAVED_DIR_SUFFIX: "${SAVED_DIR_SUFFIX:-UnchainedX64}"
      GAME_PORT: "${GAME_PORT:-7777}"
      PING_PORT: "${PING_PORT:-3075}"
      QUERY_PORT: "${QUERY_PORT:-7071}"
      RCON_PORT: "${RCON_PORT:-9001}"
    volumes:
      - type: bind
        source: "${CHIV_GAME:?required}"
        target: /game
      - type: bind
        source: "${CLI_DIR:?required}"
        target: /opt/cli
      - type: bind
        source: "${PROTON_DIR:?required}"
        target: /proton/GE-Proton11-11-x86_64
      - type: bind
        source: "${COMPAT_CLIENT_DIR:?required}"
        target: /proton-compat-client
      - type: bind
        source: "${LEGENDARY_CONFIG:?required}"
        target: /opt/legendary
      - type: bind
        source: "${CHIV_PREFIX:-./state/prefix}"
        target: /proton-prefix
      - type: bind
        source: "${CHIV_LOCALAPPDATA:-./state/appdata}"
        target: /proton-prefix/pfx/drive_c/users/steamuser/AppData/Local/Chivalry 2
"""
        )

    def test_compose_interpolation_quoting_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # A literal "$" in a path is not supported (Compose interpolation);
            # exercise the special chars the system does round-trip.
            game_path = str(root / "game dir" / "#data" / "literal")
            self._compose_fixture(root, game_path)
            env = os.environ.copy()
            for key in (
                "CHIV_GAME", "CLI_DIR", "PROTON_DIR",
                "COMPAT_CLIENT_DIR", "LEGENDARY_CONFIG", "CHIV_PREFIX",
                "CHIV_LOCALAPPDATA", "SERVER_ADVERTISE_IP", "GAME_PORT",
                "PING_PORT", "QUERY_PORT", "RCON_PORT", "DISPLAY_NUM",
                "SERVER_NAME", "SERVER_BROWSER_BACKEND", "SAVED_DIR_SUFFIX",
                "IMAGE_NAME", "CONTAINER_NAME", "COMPOSE_FILE",
                "COMPOSE_PROJECT_NAME",
            ):
                env.pop(key, None)
            env["GAME_PORT"] = "18001"  # shell environment beats project .env
            original = subprocess.run

            def runner(command, **kwargs):
                return original(command, env=env, **kwargs)

            config = resolve(root, runner=runner)
            self.assertEqual(config["paths"]["CHIV_GAME"], game_path)
            self.assertEqual(config["ports"]["game"], 18001)
            self.assertEqual(config["ports"]["ping"], 17002)
            self.assertEqual(
                config["paths"]["CHIV_PREFIX"], str(root / "state" / "prefix")
            )
            self.assertEqual(config["display"], ":99")

    def test_generated_env_file_round_trips_literal_compose_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._compose_fixture(root, str(root / "original-game"))
            # "$" and embedded quotes are excluded on purpose: env-file
            # interpolation/quoting does not round-trip them. Spaces and "#" do.
            special_game = str(root / "game dir/#hash value")
            values = {
                "SERVER_ADVERTISE_IP": "2606:4700::1111",
                "CHIV_GAME": special_game,
                "CLI_DIR": str(root / "cli"),
                "PROTON_DIR": str(root / "proton"),
                "COMPAT_CLIENT_DIR": str(root / "compat"),
                "LEGENDARY_CONFIG": str(root / "legendary"),
                "GAME_PORT": "18005",
                "PING_PORT": "18006",
                "QUERY_PORT": "18007",
                "RCON_PORT": "18008",
                "SERVER_NAME": "Literal name # hash",
            }
            self.assertEqual(set(values).intersection(SETUP_REQUIRED), set(SETUP_REQUIRED))
            env_file = root / ".generated-env"
            env_file.write_text(render_env(values))
            env_file.chmod(0o600)
            env = os.environ.copy()
            for key in (
                "CHIV_GAME", "CLI_DIR", "PROTON_DIR",
                "COMPAT_CLIENT_DIR", "LEGENDARY_CONFIG", "CHIV_PREFIX",
                "CHIV_LOCALAPPDATA", "SERVER_ADVERTISE_IP", "GAME_PORT",
                "PING_PORT", "QUERY_PORT", "RCON_PORT", "DISPLAY_NUM",
                "SERVER_NAME", "SERVER_BROWSER_BACKEND", "SAVED_DIR_SUFFIX",
                "IMAGE_NAME", "CONTAINER_NAME", "COMPOSE_FILE",
                "COMPOSE_PROJECT_NAME",
            ):
                env.pop(key, None)
            env["GAME_PORT"] = "19999"  # generated answers must be isolated from the caller
            original = subprocess.run

            def runner(command, **kwargs):
                kwargs.setdefault("env", env)
                return original(command, **kwargs)

            config = resolve(root, runner=runner, env_file=env_file)
            self.assertEqual(config["paths"]["CHIV_GAME"], special_game)
            self.assertEqual(config["server_name"], values["SERVER_NAME"])
            self.assertEqual(config["ports"]["game"], 18005)

    def test_missing_required_variable_is_reported_without_compose_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._compose_fixture(root, str(root / "game"))
            env_path = root / ".env"
            env_path.write_text(
                "\n".join(
                    line for line in env_path.read_text().splitlines()
                    if not line.startswith("SERVER_ADVERTISE_IP=")
                ) + "\n"
            )
            original = subprocess.run

            def runner(command, **kwargs):
                env = os.environ.copy()
                for key in (
                    "SERVER_ADVERTISE_IP", "CHIV_GAME", "CLI_DIR",
                    "PROTON_DIR", "COMPAT_CLIENT_DIR",
                    "LEGENDARY_CONFIG",
                ):
                    env.pop(key, None)
                return original(command, env=env, **kwargs)

            with self.assertRaises(ConfigError) as raised:
                resolve(root, runner=runner)
            self.assertNotIn("secret", str(raised.exception).lower())

    def test_invalid_compose_file_error_is_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "compose.yaml").write_text("services: [invalid\n")
            original = subprocess.run

            def runner(command, **kwargs):
                env = os.environ.copy()
                env.pop("SERVER_ADVERTISE_IP", None)
                return original(command, env=env, **kwargs)

            with self.assertRaises(ConfigError) as raised:
                resolve(root, runner=runner)
            self.assertNotIn("services:", str(raised.exception))
            self.assertNotIn("invalid", str(raised.exception).lower())


if __name__ == "__main__":
    unittest.main()
