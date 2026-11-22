#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  printf 'ERROR: Python 3.10 or newer is required for setup.\n' >&2
  exit 3
}

exec python3 "$ROOT/scripts/lib/setup.py" "$@"
