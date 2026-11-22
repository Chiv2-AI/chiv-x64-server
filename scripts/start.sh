#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

"$ROOT/scripts/check-config.sh"
printf 'Starting in the foreground. Press Ctrl-C for a clean SIGINT shutdown.\n'
exec docker compose up --build
