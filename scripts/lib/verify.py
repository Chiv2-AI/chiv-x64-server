#!/usr/bin/env python3
"""Read-only, current-run scoped local readiness observations."""

from __future__ import annotations

from datetime import datetime, timezone
import glob
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

try:
    from .config import ConfigError, resolve
except ImportError:
    from config import ConfigError, resolve

MAX_LOG_BYTES = 2 * 1024 * 1024
MARKERS = {
    "State Up": re.compile(r"\bState Up\b", re.IGNORECASE),
    "RCON listening": re.compile(r"\bRCON Listening\b", re.IGNORECASE),
    "plugin initialized": re.compile(r"Unchained Sleuth initialized", re.IGNORECASE),
    "registration heartbeat": re.compile(r"\bHB Success\b", re.IGNORECASE),
}
ISO_TIMESTAMP = re.compile(
    r"^\s*(\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)?)"
)


def run(command: list[str], *, timeout: int = 8) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def parse_timestamp(value: str) -> datetime | None:
    normalized = value.strip().replace(" ", "T", 1)
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def current_run_markers(
    text: str, started_at: datetime
) -> tuple[dict[str, datetime], int, int]:
    """Return latest marker time, plus untimed and malformed matching-line counts."""
    latest: dict[str, datetime] = {}
    untimed = 0
    malformed = 0
    for line in text.splitlines():
        matches = [name for name, pattern in MARKERS.items() if pattern.search(line)]
        if not matches:
            continue
        match = ISO_TIMESTAMP.match(line)
        if not match:
            untimed += 1
            continue
        timestamp = parse_timestamp(match.group(1))
        if timestamp is None:
            malformed += 1
            continue
        if timestamp >= started_at:
            for name in matches:
                latest[name] = max(timestamp, latest.get(name, timestamp))
    return latest, untimed, malformed


def bounded_read(path: Path, limit: int = MAX_LOG_BYTES) -> tuple[str | None, str]:
    try:
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - limit))
            data = stream.read(limit)
        if size > limit:
            # The first fragment can begin mid-line; discard it.
            data = data.split(b"\n", 1)[-1]
        return data.decode("utf-8", errors="replace"), "bounded"
    except OSError:
        return None, "unreadable"


def appdata_marker_observations(
    appdata: Path, suffix: str, started_at: datetime
) -> tuple[dict[str, datetime], bool, str]:
    log_dir = appdata / f"Saved_{suffix}" / "Logs"
    candidates = []
    for name in ("unchained.log", "kismet.log"):
        candidates.extend(glob.glob(str(log_dir / (name + "*"))))
    if not candidates:
        return {}, False, "not found"
    if len(candidates) > 20:
        def modified(path: str) -> float:
            try:
                return os.path.getmtime(path)
            except OSError:
                return 0

        candidates = sorted(
            candidates, key=modified, reverse=True
        )[:20]
        truncated = True
    else:
        truncated = False
    latest: dict[str, datetime] = {}
    had_unknown = truncated
    for candidate in candidates:
        contents, state = bounded_read(Path(candidate))
        if contents is None:
            had_unknown = True
            continue
        markers, untimed, malformed = current_run_markers(contents, started_at)
        had_unknown |= bool(untimed or malformed)
        for name, timestamp in markers.items():
            latest[name] = max(timestamp, latest.get(name, timestamp))
    return latest, had_unknown, "read" if not had_unknown else "partial/ambiguous"


def _safe_container_id(root: Path) -> str | None:
    result = run(
        ["docker", "compose", "ps", "--all", "--quiet", "chiv-x64"],
        timeout=8,
    )
    if result is None or result.returncode != 0:
        return None
    ids = result.stdout.split()
    return ids[0] if ids else ""


def _inspect(container_id: str) -> dict[str, Any] | None:
    result = run([
        "docker", "inspect", "--format",
        "{{json .State}} {{.RestartCount}}",
        container_id,
    ])
    if result is None or result.returncode != 0:
        return None
    # Docker's Go template emits a JSON state object and a numeric restart count.
    raw = result.stdout.strip()
    try:
        state_text, restarts_text = raw.rsplit(" ", 1)
        state = json.loads(state_text)
        started = parse_timestamp(str(state.get("StartedAt", "")))
        if started is None:
            return None
        return {
            "running": bool(state.get("Running")),
            "status": str(state.get("Status", "unknown")),
            "restarts": int(restarts_text),
            "started_at": started,
        }
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _container_processes(container_id: str) -> tuple[set[int], set[str]] | None:
    result = run(["docker", "exec", container_id, "ps", "-eo", "pid,comm"])
    if result is None or result.returncode != 0:
        return None
    pids: set[int] = set()
    names: set[str] = set()
    for line in result.stdout.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 2:
            continue
        try:
            pid = int(fields[0])
        except ValueError:
            continue
        pids.add(pid)
        names.add(Path(fields[1]).name)
    return pids, names


def _listeners(ports: dict[str, int]) -> dict[str, bool | None]:
    result = run(["ss", "-H", "-lntup"])
    if result is None or result.returncode != 0:
        return {name: None for name in ports}
    found: set[tuple[str, int]] = set()
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        protocol = fields[0].lower()
        match = re.search(r":(\d+)$", fields[4])
        if protocol in ("tcp", "udp") and match:
            found.add((protocol, int(match.group(1))))
    expected = {
        "game": "udp",
        "ping": "udp",
        "query": "udp",
        "rcon": "tcp",
    }
    return {
        name: (expected[name], port) in found
        for name, port in ports.items()
        if name in expected
    }


def _docker_log_markers(
    container_id: str, started_at: datetime
) -> tuple[dict[str, datetime], bool]:
    result = run([
        "docker", "logs", "--timestamps", "--since",
        started_at.isoformat(), "--tail", "10000", container_id,
    ], timeout=12)
    if result is None or result.returncode != 0:
        return {}, True
    latest, untimed, malformed = current_run_markers(
        result.stdout + "\n" + result.stderr, started_at
    )
    return latest, bool(untimed or malformed)


def _timestamp_label(value: datetime | None) -> str:
    return value.astimezone(timezone.utc).isoformat() if value else "not observed"


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    try:
        config = resolve(root)
    except ConfigError as exc:
        print(f"Configuration unavailable: {exc}", file=sys.stderr)
        return exc.exit_code

    if not shutil.which("docker"):
        print("Docker unavailable; local readiness is unknown.")
        return 2
    container_id = _safe_container_id(root)
    if container_id is None:
        print("Could not query Compose service chiv-x64; local readiness is unknown.")
        return 2
    if not container_id:
        print("Compose service chiv-x64: no container exists (not started).")
        print("Local readiness: unknown. External/browser visibility was not tested.")
        return 2

    inspected = _inspect(container_id)
    if inspected is None:
        print("Compose service chiv-x64 exists, but Docker state is unavailable.")
        print("Local readiness: unknown. External/browser visibility was not tested.")
        return 2

    print(
        f"Compose service chiv-x64: {inspected['status']}; "
        f"running={'yes' if inspected['running'] else 'no'}; "
        f"restarts={inspected['restarts']}; "
        f"started={_timestamp_label(inspected['started_at'])}"
    )
    if not inspected["running"]:
        print("Container stopped; local readiness: no.")
        print("External/browser visibility was not tested.")
        return 1

    processes = _container_processes(container_id)
    if processes is None:
        game_process = "unknown"
    else:
        _, names = processes
        game_process = "yes" if "Chivalry2-Win64-Shipping.exe" in names else "no"
    print(f"Game binary process present: {game_process}.")

    port_state = _listeners(config["ports"])
    for name in ("game", "ping", "query", "rcon"):
        state = port_state.get(name)
        label = "unknown" if state is None else ("listening" if state else "not listening")
        protocol = "TCP" if name == "rcon" else "UDP"
        print(f"{name.upper()} {protocol} configured port {config['ports'][name]}: {label}.")

    logs, ambiguous_logs = _docker_log_markers(container_id, inspected["started_at"])
    appdata, appdata_ambiguous, appdata_state = appdata_marker_observations(
        Path(config["paths"]["CHIV_LOCALAPPDATA"]).expanduser(),
        config["saved_dir_suffix"],
        inspected["started_at"],
    )
    all_markers = dict(logs)
    for marker, timestamp in appdata.items():
        all_markers[marker] = max(timestamp, all_markers.get(marker, timestamp))
    for marker in MARKERS:
        print(f"Current-run {marker}: {_timestamp_label(all_markers.get(marker))}.")
    heartbeat = all_markers.get("registration heartbeat")
    if heartbeat is not None:
        age = max(0, int((datetime.now(timezone.utc) - heartbeat).total_seconds()))
        print(f"Latest registration heartbeat age: {age}s (local observation only).")
    else:
        print("Latest registration heartbeat age: unknown/not observed.")
    print(f"Configured AppData logs: {appdata_state}.")
    if ambiguous_logs or appdata_ambiguous:
        print("Some log marker timestamps were missing or ambiguous; absence is not proof of failure.")

    sockets_ok = len(port_state) == len(config["ports"]) and all(
        value is True for value in port_state.values()
    )
    local_ready = (
        game_process == "yes"
        and sockets_ok
        and all(marker in all_markers for marker in ("State Up", "RCON listening"))
    )
    if local_ready:
        print("Local readiness: ready (process, configured sockets, and current-run startup markers observed).")
        code = 0
    else:
        print("Local readiness: incomplete/unknown; inspect the missing observations locally.")
        code = 2
    print("Registration heartbeat is a local log observation, not proof of public listing.")
    print("External reachability, browser visibility, and gameplay were not tested.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
