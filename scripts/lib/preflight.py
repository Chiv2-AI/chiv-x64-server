#!/usr/bin/env python3
"""Read-only host/input preflight for the native x86_64 EGS profile."""

from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any

try:
    from .config import ConfigError, resolve, validate_inputs
except ImportError:  # Direct script execution from scripts/check-config.sh.
    from config import ConfigError, resolve, validate_inputs


class Finding:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passes: list[str] = []
        self.exit_code = 2

    def error(self, message: str, exit_code: int = 2) -> None:
        self.errors.append(message)
        self.exit_code = max(self.exit_code, exit_code)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def passed(self, message: str) -> None:
        self.passes.append(message)


def parse_user_id(value: str) -> tuple[int, int] | None:
    pieces = value.split(":", 1)
    if len(pieces) != 2:
        return None
    try:
        return int(pieces[0]), int(pieces[1])
    except ValueError:
        return None


def _mode_access(path_stat: os.stat_result, uid: int, gid: int) -> int:
    if uid == 0:
        return 0b111
    if uid == path_stat.st_uid:
        return (path_stat.st_mode >> 6) & 0b111
    if gid == path_stat.st_gid:
        return (path_stat.st_mode >> 3) & 0b111
    return path_stat.st_mode & 0b111


def _has_access_acl(path: Path) -> bool:
    if not hasattr(os, "getxattr"):
        return False
    try:
        os.getxattr(path, "system.posix_acl_access", follow_symlinks=False)
        return True
    except OSError:
        return False


def container_access(path: Path, uid: int, gid: int, required: int) -> bool | None:
    """Check mode-bit access for the container identity; ACLs are unknown."""
    try:
        target_stat = path.stat()
    except OSError:
        return False

    if _has_access_acl(path):
        return None
    if _mode_access(target_stat, uid, gid) & required != required:
        return False

    # Every existing ancestor must be traversable by the container user.
    for parent in path.parents:
        try:
            parent_stat = parent.stat()
        except OSError:
            return False
        if _has_access_acl(parent):
            return None
        if _mode_access(parent_stat, uid, gid) & 0b001 == 0:
            return False
    return True


def check_ipv6_address(advertised: str, ip_json: str) -> tuple[str, str]:
    try:
        address = ipaddress.ip_address(advertised)
    except ValueError:
        return "error", "SERVER_ADVERTISE_IP must be a valid IPv6 address."
    if address.version != 6 or not address.is_global:
        return "error", "SERVER_ADVERTISE_IP must be a global IPv6 address."
    try:
        interfaces = json.loads(ip_json)
    except (json.JSONDecodeError, TypeError):
        return "error", "Could not read structured IPv6 address data from iproute2."

    for interface in interfaces if isinstance(interfaces, list) else []:
        if not isinstance(interface, dict):
            continue
        for entry in interface.get("addr_info") or []:
            if not isinstance(entry, dict) or entry.get("family") != "inet6":
                continue
            try:
                candidate = ipaddress.ip_address(str(entry.get("local", "")))
            except ValueError:
                continue
            if candidate != address:
                continue
            flags = set(entry.get("flags") or [])
            if entry.get("scope") != "global" or not candidate.is_global:
                return "error", "Advertised IPv6 is assigned but not global-scope."
            if flags.intersection({"tentative", "deprecated", "temporary", "dadfailed"}):
                return "error", (
                    "Advertised IPv6 is temporary, tentative, deprecated, or failed "
                    "duplicate-address detection; choose a stable preferred address."
                )
            preferred = entry.get("preferred_life_time")
            if preferred == 0 or preferred == "0":
                return "error", "Advertised IPv6 is no longer preferred."
            return "pass", "Advertised IPv6 is locally assigned and preferred."
    return "error", "SERVER_ADVERTISE_IP is not assigned to a local interface."


def parse_ss_listeners(output: str) -> list[dict[str, Any]]:
    listeners = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 5 or fields[0] not in {"tcp", "tcp6", "udp", "udp6"}:
            continue
        protocol = "tcp" if fields[0].startswith("tcp") else "udp"
        try:
            port = int(fields[4].rsplit(":", 1)[1])
        except (IndexError, ValueError):
            continue
        pids = {int(value) for value in re.findall(r"\bpid=(\d+)", line)}
        listeners.append({"protocol": protocol, "port": port, "pids": pids})
    return listeners


def classify_port_conflicts(
    ports: dict[str, int],
    listeners: list[dict[str, Any]],
    own_pids: set[int] | None,
) -> list[tuple[str, str]]:
    expected = {
        ("udp", ports[name]): f"{name} UDP port {ports[name]}"
        for name in ("game", "ping", "query")
    }
    expected[("tcp", ports["rcon"])] = f"RCON TCP port {ports['rcon']}"
    findings = []
    for listener in listeners:
        label = expected.get((listener["protocol"], listener["port"]))
        if label is None:
            continue
        pids = listener["pids"]
        if own_pids is not None and pids and pids.intersection(own_pids):
            findings.append(("pass", f"{label} is held by this Compose service."))
        elif own_pids is None or not pids:
            findings.append((
                "unknown",
                f"Could not identify the owner of a listener on {label}; inspect it manually.",
            ))
        else:
            findings.append((
                "error",
                f"{label} is already held by another process; resolve the conflict before start.",
            ))
    return findings


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=8, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def parse_container_processes(
    output: str, display: str,
) -> tuple[set[int], set[int]]:
    pids: set[int] = set()
    xvfb_pids: set[int] = set()
    for line in output.splitlines()[1:]:
        fields = line.strip().split(None, 1)
        try:
            pid = int(fields[0])
        except (IndexError, ValueError):
            continue
        pids.add(pid)
        if len(fields) == 2:
            argv = fields[1].split()
            executable = Path(argv[0]).name if argv else ""
            if (executable == "Xvfb" and len(argv) > 1
                    and argv[1] == display):
                xvfb_pids.add(pid)
    return pids, xvfb_pids


def own_container_processes(
    root: Path, display: str,
) -> tuple[set[int], set[int]] | None:
    result = _run(["docker", "compose", "ps", "--all", "--quiet", "chiv-x64"], cwd=root)
    if result is None or result.returncode != 0:
        return None
    pids: set[int] = set()
    xvfb_pids: set[int] = set()
    running = False
    for container_id in result.stdout.split():
        inspected = _run(
            ["docker", "inspect", "--format", "{{.State.Running}} {{.State.Pid}}",
             container_id]
        )
        if inspected is None or inspected.returncode != 0:
            return None
        fields = inspected.stdout.split()
        if len(fields) != 2 or fields[0] != "true":
            continue
        running = True
        top = _run(["docker", "top", container_id, "-eo", "pid,args"])
        if top is None or top.returncode != 0:
            return None
        container_pids, container_xvfb_pids = parse_container_processes(
            top.stdout, display
        )
        pids.update(container_pids)
        xvfb_pids.update(container_xvfb_pids)
    if running and not pids:
        return None
    return pids, xvfb_pids


def _check_content(config: dict[str, Any], finding: Finding) -> None:
    paths = {key: Path(value).expanduser() for key, value in config["paths"].items()}
    for variable in ("CHIV_GAME", "LOCAL_REGISTRY", "COMPAT_CLIENT_DIR"):
        path = paths[variable]
        try:
            next(path.iterdir())
        except (OSError, StopIteration):
            finding.error(f"{variable} must be a readable, non-empty directory.")
        else:
            next_step = {
                "CHIV_GAME": "run Heroic/Legendary verification before relying on this install",
                "LOCAL_REGISTRY": "confirm its selected DLL metadata and CLI compatibility (chiv-4f7.9)",
                "COMPAT_CLIENT_DIR": "confirm its CLI-specific files and provenance (chiv-4f7.9)",
            }[variable]
            finding.warning(
                f"{variable} is non-empty, but release-specific contents are not "
                f"validated; {next_step}."
            )

    prefix = paths["CHIV_PREFIX"]
    system_reg = prefix / "pfx" / "system.reg"
    if not prefix.is_dir():
        finding.error("CHIV_PREFIX must be an initialized prefix directory.")
    elif not system_reg.is_file():
        finding.error("CHIV_PREFIX is missing pfx/system.reg; initialize it with Heroic first.")
    else:
        finding.passed("Proton prefix contains pfx/system.reg.")

    identity = parse_user_id(config["user"])
    if identity is None:
        finding.warning(
            "Container user is not numeric; UID/GID access could not be checked."
        )
        return
    uid, gid = identity
    if system_reg.is_file():
        prefix_file_access = container_access(system_reg, uid, gid, 0b100)
        if prefix_file_access is False:
            finding.error(
                f"CHIV_PREFIX/pfx/system.reg is not readable by UID:GID {uid}:{gid}."
            )
        elif prefix_file_access is None:
            finding.warning("Proton prefix ACL read access is unknown.")

    for variable in (
        "CHIV_GAME", "CLI_DIR", "LOCAL_REGISTRY", "PROTON_DIR",
        "COMPAT_CLIENT_DIR", "LEGENDARY_CONFIG",
    ):
        access = container_access(paths[variable], uid, gid, 0b101)
        if access is False:
            finding.error(
                f"{variable} is not readable/traversable by container UID:GID "
                f"{uid}:{gid}; adjust reviewed host permissions."
            )
        elif access is None:
            finding.warning(
                f"{variable} has ACL-based permissions; verify access as container "
                f"UID:GID {uid}:{gid}."
            )

    for variable, file_path in (
        ("CLI_DIR", paths["CLI_DIR"] / "UnchainedLauncher.CLI"),
        ("PROTON_DIR", paths["PROTON_DIR"] / "proton"),
    ):
        try:
            file_mode = file_path.stat().st_mode
        except OSError:
            continue
        access = container_access(file_path, uid, gid, 0b101)
        if not stat.S_ISREG(file_mode) or not file_mode & 0o111:
            finding.error(f"{variable} executable must be a regular executable file.")
        elif access is False:
            finding.error(f"{variable} executable is inaccessible to UID:GID {uid}:{gid}.")
        elif access is None:
            finding.warning(f"{variable} executable ACL access is unknown.")

    auth_access = tree_container_access(paths["LEGENDARY_CONFIG"], uid, gid)
    if auth_access is False:
        finding.error(
            f"LEGENDARY_CONFIG contains unreadable files for UID:GID {uid}:{gid}; "
            "keep it private while granting the container read access."
        )
    elif auth_access is None:
        finding.warning(
            "LEGENDARY_CONFIG ACL or large-tree permissions could not be fully "
            f"verified for UID:GID {uid}:{gid}."
        )

    registry_access = tree_container_access(paths["LOCAL_REGISTRY"], uid, gid)
    if registry_access is False:
        finding.error(
            f"LOCAL_REGISTRY contains unreadable files for UID:GID {uid}:{gid}."
        )
    elif registry_access is None:
        finding.warning(
            f"LOCAL_REGISTRY ACL access could not be fully verified for UID:GID {uid}:{gid}."
        )

    for variable in ("CHIV_PREFIX", "CHIV_LOCALAPPDATA"):
        path = paths[variable]
        if path.exists():
            access = container_access(path, uid, gid, 0b111)
            if access is False:
                finding.error(
                    f"{variable} is not writable/traversable by UID:GID {uid}:{gid}."
                )
            elif access is None:
                finding.warning(
                    f"{variable} ACL write access is unknown for UID:GID {uid}:{gid}."
                )
        else:
            ancestor = path
            while not ancestor.exists() and ancestor != ancestor.parent:
                ancestor = ancestor.parent
            access = container_access(ancestor, uid, gid, 0b111)
            if access is False:
                finding.error(
                    f"{variable} is missing and its existing parent is not writable "
                    f"by UID:GID {uid}:{gid}; create/review it manually."
                )
            else:
                finding.warning(
                    f"{variable} does not exist; it was not created. Compose bind-mount "
                    "creation and container access need operator verification."
                )


def tree_container_access(root: Path, uid: int, gid: int,
                          limit: int = 10000) -> bool | None:
    """Inspect permissions, not contents, for a bounded directory tree."""
    pending = [root]
    inspected = 0
    unknown = False
    while pending:
        directory = pending.pop()
        access = container_access(directory, uid, gid, 0b101)
        if access is False:
            return False
        if access is None:
            unknown = True
        try:
            entries = list(os.scandir(directory))
        except OSError:
            return False
        for entry in entries:
            inspected += 1
            if inspected > limit:
                return None
            path = Path(entry.path)
            if entry.is_symlink():
                unknown = True
                continue
            if entry.is_dir(follow_symlinks=False):
                pending.append(path)
            else:
                access = container_access(path, uid, gid, 0b100)
                if access is False:
                    return False
                if access is None:
                    unknown = True
    return None if unknown else True


def _check_display(config: dict[str, Any], own_xvfb_pids: set[int] | None,
                   finding: Finding) -> None:
    match = re.fullmatch(r":(\d+)", config["display"])
    if not match:
        finding.error("DISPLAY must use the configured numeric :N format.")
        return
    display = match.group(1)
    if own_xvfb_pids is None:
        finding.warning(
            f"Could not inspect Xvfb ownership for display :{display}; verify the "
            "current container process list manually."
        )
    elif own_xvfb_pids:
        finding.passed(f"X display :{display} is owned by this Compose service.")
    else:
        finding.passed(
            f"No Xvfb process for display :{display} exists in this Compose service."
        )


def _check_container_name(config: dict[str, Any], root: Path,
                          finding: Finding) -> None:
    name = config["container_name"]
    result = _run(
        ["docker", "ps", "--all", "--quiet", "--filter",
         f"name=^/{re.escape(name)}$"]
    )
    if result is None or result.returncode != 0:
        finding.warning(
            "Could not check whether CONTAINER_NAME is already in use; inspect "
            "Docker container names manually."
        )
        return
    ids = result.stdout.split()
    if not ids:
        finding.passed("Configured container name is not currently in use.")
        return
    for container_id in ids:
        inspected = _run(
            ["docker", "inspect", "--format", "{{json .Config.Labels}}", container_id]
        )
        if inspected is None or inspected.returncode != 0:
            finding.warning(
                "Could not identify an existing container using CONTAINER_NAME."
            )
            return
        try:
            labels = json.loads(inspected.stdout)
        except json.JSONDecodeError:
            labels = None
        working_dir = (
            labels.get("com.docker.compose.project.working_dir")
            if isinstance(labels, dict) else None
        )
        is_this_service = (
            isinstance(labels, dict)
            and labels.get("com.docker.compose.service") == "chiv-x64"
            and isinstance(working_dir, str)
            and Path(working_dir).resolve() == root.resolve()
        )
        if is_this_service:
            finding.passed("Configured container name belongs to this Compose service.")
        else:
            finding.error(
                "CONTAINER_NAME is already used by another container; choose a "
                "unique name or resolve it manually."
            )


def run_preflight(root: Path) -> tuple[Finding, dict[str, Any] | None]:
    finding = Finding()
    try:
        config = resolve(root)
        validate_inputs(config)
    except ConfigError as exc:
        finding.error(str(exc), exit_code=exc.exit_code)
        return finding, None

    try:
        _check_content(config, finding)
    except (OSError, KeyError, TypeError):
        finding.error("Could not inspect one or more configured input paths.")

    advertised = config["advertise_ip"]
    if not shutil.which("ip"):
        finding.error(
            "iproute2 `ip` is required to verify the assigned IPv6 address.",
            exit_code=3,
        )
    else:
        result = _run(["ip", "-j", "-6", "address", "show"])
        if result is None or result.returncode != 0:
            finding.error("Could not read local IPv6 interface addresses with iproute2.")
        else:
            status, message = check_ipv6_address(advertised, result.stdout)
            getattr(finding, status)(message)

    if not shutil.which("ss"):
        finding.error(
            "iproute2 `ss` is required to check configured port conflicts.",
            exit_code=3,
        )
    else:
        result = _run(["ss", "-H", "-lntup"])
        if result is None or result.returncode != 0:
            finding.warning("Could not inspect host listening sockets; check ports manually.")
        else:
            own_processes = own_container_processes(root, config["display"])
            own_pids = own_processes[0] if own_processes is not None else None
            own_xvfb_pids = own_processes[1] if own_processes is not None else None
            for status, message in classify_port_conflicts(
                config["ports"], parse_ss_listeners(result.stdout), own_pids
            ):
                getattr(finding, status)(message)
            _check_display(config, own_xvfb_pids, finding)

    if config["container_name"] and not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]*", config["container_name"]
    ):
        finding.error("CONTAINER_NAME contains characters unsupported by Docker.")
    else:
        _check_container_name(config, root, finding)
    if config["image"] and any(character.isspace() for character in config["image"]):
        finding.error("IMAGE_NAME must not contain whitespace.")

    return finding, config


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    finding, config = run_preflight(root)
    for message in finding.passes:
        print(f"PASS: {message}")
    for message in finding.warnings:
        print(f"UNKNOWN: {message}")
    for message in finding.errors:
        print(f"ERROR: {message}", file=sys.stderr)
    if config is not None and not finding.errors:
        print(
            f"Read-only preflight completed for {config['service']} "
            f"({len(finding.warnings)} unknown check(s))."
        )
    return finding.exit_code if finding.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
