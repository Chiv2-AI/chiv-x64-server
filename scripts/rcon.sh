#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "$#" -eq 0 ]]; then
  printf 'Usage: %s <RCON command>\nExample: %s servertravel tdm_darkforest\n' "$0" "$0" >&2
  exit 2
fi

command="$*"
if [[ "$command" == *$'\n'* || "$command" == *$'\r'* ]]; then
  printf 'ERROR: RCON accepts one command per invocation; newlines are not allowed.\n' >&2
  exit 2
fi

docker compose exec --no-TTY chiv-x64 python3 - "$command" <<'PY'
import os
import socket
import sys

command = sys.argv[1]
if not command.strip():
    print("ERROR: RCON command is empty.", file=sys.stderr)
    sys.exit(2)

try:
    port = int(os.environ.get("RCON_PORT", "9001"))
    with socket.create_connection(("127.0.0.1", port), timeout=5) as rcon:
        rcon.settimeout(2)
        rcon.sendall(command.encode("utf-8") + b"\n")
        try:
            response = rcon.recv(4096)
        except socket.timeout:
            response = b""
except (OSError, ValueError) as exc:
    print(f"RCON send failed ({type(exc).__name__}).", file=sys.stderr)
    sys.exit(1)

print(f"Command transmitted to loopback RCON; reply bytes={len(response)} (reply content hidden).")
if not response:
    print("No reply was received; this does not establish whether the game accepted the command.")
PY
