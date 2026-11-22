#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

container_id="$(docker compose ps --all --quiet | head -n 1)"
if [[ -z "$container_id" ]]; then
  printf 'No container exists in this Compose project. Start it with ./scripts/start.sh\n' >&2
  exit 1
fi
container="$(docker inspect --format '{{.Name}}' "$container_id" | sed 's#^/##')"

docker inspect --format 'state={{.State.Status}} running={{.State.Running}} restarts={{.RestartCount}} exit={{.State.ExitCode}}' "$container_id"

if ! docker inspect --format '{{.State.Running}}' "$container_id" | grep -qx true; then
  printf '\nContainer %s is not running. Review its logs locally, redacting any authentication material before sharing.\n' "$container" >&2
  exit 1
fi

printf '\nServer process:\n'
docker exec "$container_id" sh -lc 'ps -eo pid,args | grep -E "[C]hivalry2-Win64-Shipping.exe|[U]nchainedLauncher.CLI server" || true'

printf '\nExpected UDP listeners (host view):\n'
if command -v ss >/dev/null 2>&1; then
  ss -lunp | grep -E ':(7777|3075|7071)([[:space:]]|$)' || true
else
  printf 'ss not installed; check UDP ports 7777, 3075, and 7071 from the host.\n'
fi

printf '\nRecent readiness markers (raw log lines are not displayed):\n'
python3 - "$container_id" <<'PY'
import subprocess
import sys

result = subprocess.run(
    ["docker", "logs", "--tail=200", sys.argv[1]],
    capture_output=True,
    text=True,
    check=False,
)
logs = result.stdout + result.stderr
markers = {
    "State Up": "State Up",
    "RCON listening": "RCON Listening",
    "plugin initialized": "Unchained Sleuth initialized",
    "registration heartbeat": "HB Success",
}
for label, marker in markers.items():
    print(f"{label}: {'yes' if marker in logs else 'not seen'}")
PY
printf '\nNote: a running container/listener alone does not prove browser registration or external gameplay.\n'
