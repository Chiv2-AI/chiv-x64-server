import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.lib.config import ConfigError, validate_inputs
from scripts.lib.preflight import (
    Finding,
    _check_content,
    check_ipv6_address,
    classify_port_conflicts,
    container_access,
    parse_container_processes,
    parse_ss_listeners,
    parse_user_id,
)


class PreflightTests(unittest.TestCase):
    def test_numeric_container_identity(self):
        self.assertEqual(parse_user_id("1000:1000"), (1000, 1000))
        self.assertEqual(parse_user_id("1001:2001"), (1001, 2001))
        self.assertIsNone(parse_user_id("root:root"))

    def test_container_access_uses_target_uid_gid_not_host_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private"
            path.mkdir(mode=0o700)
            path.chmod(0o700)
            self.assertFalse(container_access(path, 99001, 99001, 0b101))
            self.assertTrue(
                container_access(path, path.stat().st_uid, path.stat().st_gid, 0b101)
            )

    def test_missing_cli_file_and_wrong_input_type_fail_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("game", "cli", "proton", "compat", "legendary"):
                (root / name).mkdir()
            config = {
                "paths": {
                    "CHIV_GAME": str(root / "game"),
                    "CLI_DIR": str(root / "cli"),
                    "PROTON_DIR": str(root / "proton"),
                    "COMPAT_CLIENT_DIR": str(root / "compat"),
                    "LEGENDARY_CONFIG": str(root / "legendary"),
                }
            }
            with self.assertRaisesRegex(ConfigError, "UnchainedLauncher.CLI"):
                validate_inputs(config)
            (root / "CLI").write_text("not a directory")
            config["paths"]["CHIV_GAME"] = str(root / "CLI")
            with self.assertRaisesRegex(ConfigError, "CHIV_GAME"):
                validate_inputs(config)

    def test_uninitialized_prefix_is_a_hard_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {}
            for variable, name in (
                ("CHIV_GAME", "game"),
                ("CLI_DIR", "cli"),
                ("PROTON_DIR", "proton"),
                ("COMPAT_CLIENT_DIR", "compat"),
                ("LEGENDARY_CONFIG", "legendary"),
                ("CHIV_PREFIX", "prefix"),
                ("CHIV_LOCALAPPDATA", "appdata"),
            ):
                directory = root / name
                directory.mkdir()
                (directory / "fixture").write_text("fixture")
                paths[variable] = str(directory)
            cli = root / "cli" / "UnchainedLauncher.CLI"
            cli.write_text("fixture")
            cli.chmod(0o755)
            proton = root / "proton" / "proton"
            proton.write_text("fixture")
            proton.chmod(0o755)
            config = {
                "paths": paths,
                "user": f"{os.getuid()}:{os.getgid()}",
            }
            finding = Finding()
            _check_content(config, finding)
            self.assertTrue(any("pfx/system.reg" in error for error in finding.errors))

    def test_advertised_ipv6_must_be_assigned_and_preferred_global(self):
        good = json.dumps([{
            "ifname": "eth0",
            "addr_info": [{
                "family": "inet6",
                "local": "2606:4700::1111",
                "scope": "global",
                "flags": [],
                "preferred_life_time": "forever",
            }],
        }])
        self.assertEqual(check_ipv6_address("2606:4700::1111", good)[0], "pass")
        self.assertEqual(check_ipv6_address("2606:4700::2222", good)[0], "error")
        self.assertEqual(
            check_ipv6_address(
                "2606:4700::1111",
                good.replace('"flags": []', '"flags": ["temporary"]'),
            )[0],
            "error",
        )
        self.assertEqual(
            check_ipv6_address(
                "2606:4700::1111",
                good.replace('"flags": []', '"flags": ["deprecated"]'),
            )[0],
            "error",
        )
        self.assertEqual(
            check_ipv6_address(
                "2606:4700::1111",
                good.replace('"flags": []', '"flags": ["tentative"]'),
            )[0],
            "error",
        )
        self.assertEqual(
            check_ipv6_address(
                "2001:db8::1",
                json.dumps([{
                    "addr_info": [{
                        "family": "inet6",
                        "local": "2001:db8::1",
                        "scope": "global",
                    }]
                }]),
            )[0],
            "error",
        )

    def test_listener_parser_and_owned_vs_foreign_port_classification(self):
        ss_output = "\n".join([
            'udp UNCONN 0 0 0.0.0.0:17777 0.0.0.0:* users:(("game",pid=12,fd=4))',
            'tcp LISTEN 0 128 [::]:19001 [::]:* users:(("rcon",pid=99,fd=5))',
            'tcp LISTEN 0 128 127.0.0.1:22000 0.0.0.0:* users:(("other",pid=77,fd=8))',
        ])
        listeners = parse_ss_listeners(ss_output)
        self.assertEqual(len(listeners), 3)
        ports = {"game": 17777, "ping": 17778, "query": 17779, "rcon": 19001}
        findings = classify_port_conflicts(ports, listeners, {12})
        self.assertEqual(findings[0][0], "pass")
        self.assertEqual(findings[1][0], "error")
        self.assertIn("RCON TCP port 19001", findings[1][1])

    def test_listener_owner_unknown_is_not_reported_as_free_or_conflicting(self):
        listeners = parse_ss_listeners(
            'udp UNCONN 0 0 [::]:17777 [::]:* users:(("game",pid=12,fd=4))'
        )
        findings = classify_port_conflicts(
            {"game": 17777, "ping": 17778, "query": 17779, "rcon": 19001},
            listeners,
            None,
        )
        self.assertEqual(findings[0][0], "unknown")

    def test_container_process_parser_matches_only_configured_xvfb(self):
        processes, xvfb = parse_container_processes(
            "\n".join([
                "PID COMMAND",
                "10 /usr/bin/Xvfb :99 -screen 0 1280x1024x24",
                "11 /opt/bin/Xvfb :100 -screen 0 1280x1024x24",
                "12 /bin/bash -c Xvfb :99",
                "13 /opt/cli/UnchainedLauncher.CLI server",
            ]),
            ":99",
        )
        self.assertEqual(processes, {10, 11, 12, 13})
        self.assertEqual(xvfb, {10})


if __name__ == "__main__":
    unittest.main()
