#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ "$(uname -m)" == "x86_64" ]] || fail "This deployment expects an x86_64 host (found $(uname -m))."
command -v docker >/dev/null || fail "Docker is not installed or not on PATH."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required (docker compose)."

if ! docker info >/dev/null 2>&1; then
  fail "Docker is unavailable to this user. Check that the daemon is running and that your account has permission; do not solve this by running the server as root."
fi

if [[ ! -f .env ]]; then
  printf 'No .env found. Start with:\n  cp .env.example .env\nThen edit .env with the real host paths and advertised address.\n'
else
  printf 'Found .env. Run ./scripts/check-config.sh after filling it in.\n'
fi

printf '\nHost preflight passed. This script makes no system changes.\n'
printf 'Review the README firewall section and run any sudo-required commands yourself.\n'
