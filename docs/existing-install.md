# Reusing an existing installation

Reuse is appropriate only when the game, CLI, Proton build, compatibility
client, and registry are mutually compatible. Their exact compatibility is
not established by checking that directories are non-empty; see
[development evidence](development.md).

## Reuse read-only inputs

The Compose service mounts game, CLI, registry, Proton, compatibility client,
and Legendary config as host paths. Game/tool inputs are read-only inside the
container. Set their paths in `.env` rather than copying large files. Verify
the game with Heroic/Legendary on the host before relying on it. If an update
is needed, stop the game safely first and update it host-side; do not make the
container mounts writable.

Never reuse an active writable Proton prefix across containers. Point
`CHIV_PREFIX` and `CHIV_LOCALAPPDATA` to new, isolated paths for this server;
the Compose defaults are `./state/prefix` and `./state/appdata`. Keep state
private and Git-ignored. This repository does not copy, initialize, or create
those paths.

For shared Docker hosts, choose unique `CONTAINER_NAME` and `IMAGE_NAME`.
Host networking means names do not isolate ports: check the configured ports
before starting. Do not stop another service just to free them.

Run `./scripts/check-config.sh` after configuring `.env`. It checks structural
and permission prerequisites but cannot prove artifact compatibility or
game-file integrity.
