#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ "$(uname -m)" == "x86_64" ]] || fail "This deployment expects an x86_64 host (found $(uname -m))."
command -v docker >/dev/null || fail "Docker is not installed or not on PATH."
command -v python3 >/dev/null || fail "Python 3 is required for read-only configuration checks."
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || fail "Python 3.10 or newer is required."
command -v ip >/dev/null || fail 'iproute2 `ip` is required for the local IPv6 check.'
command -v ss >/dev/null || fail 'iproute2 `ss` is required for the read-only listener check.'
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required (docker compose)."
python3 - <<'PY' || fail "Docker Compose v2.23.0 or newer is required."
import subprocess
import sys
sys.path.insert(0, "scripts/lib")
from config import MIN_COMPOSE, _version_tuple
try:
    result = subprocess.run(
        ["docker", "compose", "version", "--short"],
        capture_output=True, text=True, check=False, timeout=5,
    )
except (OSError, subprocess.TimeoutExpired):
    raise SystemExit(1)
version = _version_tuple(result.stdout) if result.returncode == 0 else None
if version is None or version < MIN_COMPOSE:
    raise SystemExit(1)
PY

if ! docker info >/dev/null 2>&1; then
  fail "Docker is unavailable to this user. Check that the daemon is running and that your account has permission; do not solve this by running the server as root."
fi

if [[ ! -f .env ]]; then
  printf 'No .env found. Start with:\n  cp .env.example .env\nThen edit .env with the real host paths and advertised address.\n'
else
  printf 'Found .env. Running read-only input, permissions, IPv6, and listener checks.\n'
  "$ROOT/scripts/check-config.sh"
fi

printf '\nHost preflight passed. This script makes no system changes.\n'
printf 'Review the README firewall section and run any sudo-required commands yourself.\n'
