from datetime import datetime, timezone
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import scripts.lib.verify as verify
from scripts.lib.verify import (
    bounded_read,
    current_run_markers,
    appdata_marker_observations,
    _listeners,
    parse_timestamp,
)


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.started = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)

    def test_current_and_stale_startup_markers_are_separated_with_timezone(self):
        current, untimed, malformed = current_run_markers(
            "\n".join([
                "2026-11-22T11:59:59Z State Up",
                "2026-11-22T12:59:00+01:00 State Up",
                "2026-11-22T12:02:03.000Z HB Success",
            ]),
            self.started,
        )
        self.assertNotIn("State Up", current)
        self.assertEqual(current["registration heartbeat"], self.started.replace(minute=2, second=3))
        self.assertEqual((untimed, malformed), (0, 0))

    def test_timezone_free_malformed_and_missing_timestamps_are_unknown(self):
        current, untimed, malformed = current_run_markers(
            "2026-11-22 12:01:00 State Up\n"
            "2026-99-99T12:01:00Z HB Success\n"
            "RCON Listening",
            self.started,
        )
        self.assertEqual(current, {})
        self.assertEqual(untimed, 1)
        self.assertEqual(malformed, 2)

    def test_bounded_read_keeps_tail_and_discards_partial_first_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "log"
            path.write_bytes(b"old\n123456789\nlast marker\n")
            contents, state = bounded_read(path, limit=16)
            self.assertEqual(state, "bounded")
            self.assertEqual(contents, "last marker\n")

    def test_read_failure_is_reported_without_content(self):
        with tempfile.TemporaryDirectory() as directory:
            contents, state = bounded_read(Path(directory) / "missing")
            self.assertIsNone(contents)
            self.assertEqual(state, "unreadable")

    def test_appdata_log_reads_current_markers_and_ignores_copied_history(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = Path(directory) / "Saved_custom" / "Logs"
            logs.mkdir(parents=True)
            (logs / "unchained.log.1").write_text(
                "2026-11-22T11:00:00Z State Up\n"
            )
            (logs / "unchained.log").write_text(
                "2026-11-22T12:03:00Z RCON Listening\n"
                "2026-11-22T12:04:00Z HB Success\n"
            )
            markers, ambiguous, state = appdata_marker_observations(
                Path(directory), "custom", self.started
            )
            self.assertNotIn("State Up", markers)
            self.assertIn("RCON listening", markers)
            self.assertIn("registration heartbeat", markers)
            self.assertFalse(ambiguous)
            self.assertEqual(state, "read")

    def test_listener_protocols_are_scoped_to_expected_configured_ports(self):
        output = "\n".join([
            "udp UNCONN 0 0 0.0.0.0:17777 0.0.0.0:*",
            "tcp LISTEN 0 128 0.0.0.0:19001 0.0.0.0:*",
            "tcp LISTEN 0 128 0.0.0.0:13075 0.0.0.0:*",
        ])
        with patch("scripts.lib.verify.run") as runner:
            runner.return_value = type("Result", (), {
                "returncode": 0, "stdout": output,
            })()
            result = _listeners({
                "game": 17777, "ping": 13075, "query": 17071, "rcon": 19001,
            })
        self.assertEqual(result, {
            "game": True, "ping": False, "query": False, "rcon": True,
        })

    def test_naive_timestamp_is_not_assumed_local_or_utc(self):
        self.assertIsNone(parse_timestamp("2026-11-22T12:00:00"))
        self.assertEqual(
            parse_timestamp("2026-11-22T12:00:00-05:00"),
            datetime(2026, 11, 22, 17, 0, tzinfo=timezone.utc),
        )

    def test_main_distinguishes_stopped_and_incomplete_game_process(self):
        config = {
            "ports": {"game": 17777, "ping": 13075, "query": 17071, "rcon": 19001},
            "paths": {"CHIV_LOCALAPPDATA": "/missing"},
            "saved_dir_suffix": "custom",
        }
        started = self.started
        output = io.StringIO()
        with (
            patch.object(verify, "resolve", return_value=config),
            patch.object(verify.shutil, "which", return_value="/usr/bin/docker"),
            patch.object(verify, "_safe_container_id", return_value="container-id"),
            patch.object(verify, "_inspect", return_value={
                "running": False, "status": "exited", "restarts": 1,
                "started_at": started,
            }),
            contextlib.redirect_stdout(output),
        ):
            code = verify.main()
        self.assertEqual(code, 1)
        self.assertIn("Container stopped", output.getvalue())
        self.assertIn("External/browser visibility was not tested", output.getvalue())

        output = io.StringIO()
        with (
            patch.object(verify, "resolve", return_value=config),
            patch.object(verify.shutil, "which", return_value="/usr/bin/docker"),
            patch.object(verify, "_safe_container_id", return_value="secret-container-id"),
            patch.object(verify, "_inspect", return_value={
                "running": True, "status": "running", "restarts": 0,
                "started_at": started,
            }),
            patch.object(verify, "_container_processes", return_value=(set(), {"bash"})),
            patch.object(verify, "_listeners", return_value={
                "game": True, "ping": True, "query": True, "rcon": True,
            }),
            patch.object(verify, "_docker_log_markers", return_value=({}, False)),
            patch.object(verify, "appdata_marker_observations", return_value=({}, False, "not found")),
            contextlib.redirect_stdout(output),
        ):
            code = verify.main()
        self.assertEqual(code, 2)
        self.assertIn("Game binary process present: no", output.getvalue())
        self.assertNotIn("secret-container-id", output.getvalue())
        self.assertNotIn("not tested: yes", output.getvalue())

    def test_missing_service_is_unknown_and_not_crash_claim(self):
        config = {
            "ports": {"game": 1, "ping": 2, "query": 3, "rcon": 4},
            "paths": {}, "saved_dir_suffix": "test",
        }
        output = io.StringIO()
        with (
            patch.object(verify, "resolve", return_value=config),
            patch.object(verify.shutil, "which", return_value="/usr/bin/docker"),
            patch.object(verify, "_safe_container_id", return_value=""),
            contextlib.redirect_stdout(output),
        ):
            code = verify.main()
        self.assertEqual(code, 2)
        self.assertIn("no container exists", output.getvalue())
        self.assertIn("unknown", output.getvalue())

    def test_compose_lookup_selects_only_the_named_service(self):
        with patch("scripts.lib.verify.run") as runner:
            runner.return_value = type("Result", (), {
                "returncode": 0,
                "stdout": "selected-service-id\n",
            })()
            result = verify._safe_container_id(Path("/fixture"))
        self.assertEqual(result, "selected-service-id")
        self.assertEqual(
            runner.call_args.args[0],
            ["docker", "compose", "ps", "--all", "--quiet", "chiv-x64"],
        )

    def test_log_parser_does_not_return_raw_secret_canary(self):
        completed = type("Result", (), {
            "returncode": 0,
            "stdout": "2026-11-22T12:01:00Z HB Success auth-token-canary\n",
            "stderr": "",
        })()
        with patch("scripts.lib.verify.run", return_value=completed):
            markers, ambiguous = verify._docker_log_markers("fixture-id", self.started)
        self.assertIn("registration heartbeat", markers)
        self.assertFalse(ambiguous)
        self.assertNotIn("auth-token-canary", repr(markers))


if __name__ == "__main__":
    unittest.main()
