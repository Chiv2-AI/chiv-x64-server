#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  printf 'ERROR: Missing .env. Copy .env.example to .env and configure it.\n' >&2
  exit 2
fi

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  printf 'ERROR: Python 3.10 or newer is required for read-only preflight.\n' >&2
  exit 3
}

exec python3 "$ROOT/scripts/lib/preflight.py"
