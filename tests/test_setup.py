import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import scripts.lib.setup as setup


REQUIRED_FLAGS = [
    "--server-advertise-ip", "2606:4700::1111",
    "--chiv-game", "./game",
    "--cli-dir", "./cli",
    "--proton-dir", "./proton/GE-Proton11-11-x86_64",
    "--compat-client-dir", "./proton/compat-client",
    "--legendary-config", "./legendary-config",
]


class FakeResolver:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def __call__(self, root, *, env_file=None):
        self.calls.append((root, env_file))
        self.assert_secure_temp_file(root, env_file)
        if self.error:
            raise self.error
        return {}

    @staticmethod
    def assert_secure_temp_file(root, path):
        assert path is not None and path.parent == root
        assert path.exists()
        assert path.stat().st_mode & 0o777 == 0o600


class SetupTests(unittest.TestCase):
    def test_help_works_from_outside_checkout_without_writing_files(self):
        checkout = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                ["bash", str(checkout / "scripts/setup.sh"), "--help"],
                cwd=tmp,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("--non-interactive", result.stdout)
            self.assertFalse((Path(tmp) / ".env").exists())

    def test_noninteractive_success_writes_custom_values_private_and_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = FakeResolver()
            code = setup.run_setup(
                [
                    "--non-interactive",
                    *REQUIRED_FLAGS,
                    "--server-name", 'Test "server"',
                    "--game-port", "18001",
                    "--ping-port", "18002",
                    "--query-port", "18003",
                    "--rcon-port", "18004",
                    "--container-name", "chiv-x64-test",
                    "--image-name", "chiv-x64-test:local",
                ],
                root=root,
                prompt=lambda _: self.fail("non-interactive setup prompted"),
                resolver=resolver,
            )
            self.assertEqual(code, 0)
            env = root / ".env"
            self.assertTrue(env.is_file())
            self.assertEqual(env.stat().st_mode & 0o777, 0o600)
            contents = env.read_text()
            self.assertIn('SERVER_NAME=\'Test "server"\'', contents)
            self.assertIn("GAME_PORT='18001'", contents)
            self.assertIn("CONTAINER_NAME='chiv-x64-test'", contents)
            self.assertNotIn("TOKEN", contents)
            self.assertEqual(len(resolver.calls), 1)
            self.assertFalse(any(path.name.startswith(".setup-env-")
                                 for path in root.iterdir()))

    def test_interactive_defaults_and_check_only_do_not_write_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            answers = iter([
                "2606:4700::1111",
                "",  # checkout-local example path
                "./cli",
                "./proton/GE-Proton11-11-x86_64",
                "./proton/compat-client",
                "./legendary-config",
                *("" for _ in setup.OPTIONAL),
            ])
            resolver = FakeResolver()
            result = setup.run_setup(
                ["--check-only"],
                root=root,
                prompt=lambda _: next(answers),
                resolver=resolver,
            )
            self.assertEqual(result, 0)
            self.assertFalse((root / ".env").exists())
            self.assertEqual(len(resolver.calls), 1)
            self.assertFalse(any(path.name.startswith(".setup-env-")
                                 for path in root.iterdir()))

    def test_noninteractive_missing_fields_fails_without_prompt_or_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = setup.run_setup(
                ["--non-interactive"],
                root=root,
                prompt=lambda _: self.fail("non-interactive setup prompted"),
                resolver=FakeResolver(),
            )
            self.assertEqual(result, 2)
            self.assertFalse((root / ".env").exists())

    def test_existing_regular_file_and_symlink_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = root / ".env"
            env.write_text("KEEP=regular\n")
            self.assertEqual(
                setup.run_setup(["--check-only"], root=root, resolver=FakeResolver()),
                2,
            )
            self.assertEqual(env.read_text(), "KEEP=regular\n")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.write_text("KEEP=target\n")
            (root / ".env").symlink_to(target)
            self.assertEqual(
                setup.run_setup(["--check-only"], root=root, resolver=FakeResolver()),
                2,
            )
            self.assertEqual(target.read_text(), "KEEP=target\n")

    def test_eof_invalid_input_and_compose_error_leave_no_partial_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                setup.run_setup(
                    [], root=root, prompt=lambda _: (_ for _ in ()).throw(EOFError()),
                    resolver=FakeResolver(),
                ),
                130,
            )
            self.assertFalse((root / ".env").exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = FakeResolver()
            bad_flags = list(REQUIRED_FLAGS)
            bad_flags[1] = "not-an-ip"
            self.assertEqual(
                setup.run_setup(
                    ["--non-interactive", *bad_flags],
                    root=root,
                    resolver=resolver,
                ),
                2,
            )
            self.assertEqual(resolver.calls, [])
            self.assertFalse((root / ".env").exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = FakeResolver(error=setup.ConfigError("safe config error"))
            self.assertEqual(
                setup.run_setup(
                    ["--non-interactive", *REQUIRED_FLAGS],
                    root=root,
                    resolver=resolver,
                ),
                2,
            )
            self.assertFalse((root / ".env").exists())

    def test_concurrent_destination_creation_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_open = os.open
            env = root / ".env"

            def create_race(path, flags, mode=0o777):
                if Path(path) == env and not env.exists():
                    env.write_text("RACE=preserve\n")
                return real_open(path, flags, mode)

            with patch.object(setup.os, "open", side_effect=create_race):
                result = setup.run_setup(
                    ["--non-interactive", *REQUIRED_FLAGS],
                    root=root,
                    resolver=FakeResolver(),
                )
            self.assertEqual(result, 2)
            self.assertEqual(env.read_text(), "RACE=preserve\n")

    def test_single_quote_and_control_characters_are_explicitly_rejected(self):
        values = {key: "value" for key in setup.REQUIRED}
        values["SERVER_ADVERTISE_IP"] = "2606:4700::1111"
        values["CHIV_GAME"] = "./game's"
        with self.assertRaisesRegex(ValueError, "single quote"):
            setup.validate_values(values)
        values["CHIV_GAME"] = "./game\nsecond-line"
        with self.assertRaisesRegex(ValueError, "control characters"):
            setup.validate_values(values)


if __name__ == "__main__":
    unittest.main()
