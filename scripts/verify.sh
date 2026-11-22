#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

container="${CONTAINER_NAME:-chiv-x64}"
docker inspect "$container" >/dev/null 2>&1 || {
  printf 'Container %s does not exist. Start it with ./scripts/start.sh\n' "$container" >&2
  exit 1
}

docker inspect --format 'state={{.State.Status}} running={{.State.Running}} restarts={{.RestartCount}} exit={{.State.ExitCode}}' "$container"

if ! docker inspect --format '{{.State.Running}}' "$container" | grep -qx true; then
  printf '\nContainer is not running. Recent logs:\n' >&2
  docker compose logs --tail=80 >&2
  exit 1
fi

printf '\nServer process:\n'
docker exec "$container" sh -lc 'ps -eo pid,args | grep -E "[C]hivalry2-Win64-Shipping.exe|[U]nchainedLauncher.CLI server" || true'

printf '\nExpected UDP listeners (host view):\n'
if command -v ss >/dev/null 2>&1; then
  ss -lunp | grep -E ':(7777|3075|7071)([[:space:]]|$)' || true
else
  printf 'ss not installed; check UDP ports 7777, 3075, and 7071 from the host.\n'
fi

printf '\nRecent container logs:\n'
docker compose logs --tail=40
printf '\nNote: a running container/listener alone does not prove browser registration or external gameplay.\n'
