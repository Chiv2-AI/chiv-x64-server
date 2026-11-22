# Operations

## Lifecycle

From the repository root:

```bash
./scripts/start.sh
./scripts/verify.sh
./scripts/stop.sh
```

**Starting may publicly register the server** because Compose passes
`--register`. `stop.sh` stops the service without deleting its persistent
state. Avoid `docker compose down -v` or deleting `state/` unless you have
reviewed the consequences and intentionally want to remove data.

## Readiness and logs

`verify.sh` shows selected container state, restart count, game process,
configured sockets, and current-run timestamped markers. It reads bounded
container/AppData log tails, never prints raw lines or process arguments, and
cannot prove external reachability or gameplay. AppData logs may include
copied prior-run history; timestamps without an explicit timezone remain
unknown.

Raw logs can contain private registration/authentication information. Inspect
them locally and redact before sharing. Never paste `.env`, Legendary config,
tokens, device codes, or authentication output into support requests.

## RCON

RCON is loopback-only. Do not expose its TCP port to the public Internet.
`./scripts/rcon.sh <command> [args...]` sends a command; map travel affects
players, so check before changing maps. Avoid bot commands while a real player
may be connected. A missing reply does not necessarily mean the command failed.

## Updates and backups

Game files and tools are read-only container mounts. Update/repair them on the
host with the appropriate trusted platform tool, with the server safely
stopped. Validate CLI/plugin compatibility before replacing artifacts.

Backups must protect `.env`, Legendary credentials, prefix, AppData, and any
server state as private data. This guide does not prescribe a tested backup,
restore, or destructive update procedure; confirm paths and retention before
acting.
