#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ -f .env ]] || fail "Missing .env. Copy .env.example to .env and configure it."

# Let Compose validate required substitutions without printing its fully
# interpolated configuration (which may contain private paths).
docker compose config -q || fail "Compose configuration is invalid. Check required .env values."

python3 - <<'PY'
from pathlib import Path
import os
import re
import shlex
import sys

env_file = Path(".env")
values = {}
for raw in env_file.read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    match = re.match(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
    if not match:
        continue
    key, value = match.groups()
    value = value.strip()
    if value.startswith(("'", '"')):
        try:
            parts = shlex.split(value, comments=True)
        except ValueError as exc:
            print(f"ERROR: invalid quoting for {key} in .env: {exc}", file=sys.stderr)
            sys.exit(1)
        value = parts[0] if parts else ""
    else:
        value = value.split("#", 1)[0].strip()
    values[key] = value

required = ("SERVER_ADVERTISE_IP", "CHIV_GAME", "CLI_DIR", "LOCAL_REGISTRY",
            "PROTON_DIR", "COMPAT_CLIENT_DIR", "LEGENDARY_CONFIG")
missing = [key for key in required if not values.get(key, "").strip()]
if missing:
    print("ERROR: Set these .env values: " + ", ".join(missing), file=sys.stderr)
    sys.exit(1)

for key in ("CHIV_GAME", "CLI_DIR", "LOCAL_REGISTRY", "PROTON_DIR",
            "COMPAT_CLIENT_DIR", "LEGENDARY_CONFIG"):
    path = Path(os.path.expanduser(values[key]))
    if not path.is_dir():
        print(f"ERROR: {key} directory does not exist: {path}", file=sys.stderr)
        sys.exit(1)

cli = Path(os.path.expanduser(values["CLI_DIR"])) / "UnchainedLauncher.CLI"
if not cli.is_file():
    print(f"ERROR: CLI executable not found: {cli}", file=sys.stderr)
    sys.exit(1)

proton = Path(os.path.expanduser(values["PROTON_DIR"])) / "proton"
if not proton.is_file():
    print(f"ERROR: Proton executable not found: {proton}", file=sys.stderr)
    sys.exit(1)

print("Configuration and required input paths look valid.")
print("Secret values and full Compose configuration were not printed.")
PY
