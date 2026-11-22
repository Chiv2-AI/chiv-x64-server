# Configuration

Configure `.env` from the checkout root with `./scripts/setup.sh`, or copy
`.env.example` and edit it. Setup writes only `.env`, mode 0600; it will not
overwrite an existing file or symlink. `--check-only` validates without
writing. See `./scripts/setup.sh --help` for exact options.

## Variables

| Variable | Required/default | Meaning |
|---|---|---|
| `SERVER_ADVERTISE_IP` | Required | Stable, preferred global IPv6 address, raw (no brackets) |
| `CHIV_GAME` | Required | Verified EGS game root |
| `CLI_DIR` | Required | Directory containing `UnchainedLauncher.CLI` |
| `LOCAL_REGISTRY` | Required | Local plugin registry directory |
| `PROTON_DIR` | Required | GE-Proton directory containing `proton` |
| `COMPAT_CLIENT_DIR` | Required | CLI-specific Proton compatibility-client files |
| `LEGENDARY_CONFIG` | Required | Private host Legendary/EGS config directory; credentials stay here |
| `SERVER_NAME` | `x64 EGS CLI server` | Display name |
| `SAVED_DIR_SUFFIX` | `UnchainedX64` | Saved/AppData subdirectory suffix |
| `SERVER_BROWSER_BACKEND` | Compose default | Registration/query backend; review before start |
| `GAME_PORT` | `7777/UDP` | Gameplay |
| `PING_PORT` | `3075/UDP` | Browser ping/beacon |
| `QUERY_PORT` | `7071/UDP` | A2S query |
| `RCON_PORT` | `9001/TCP` | RCON; loopback-only |
| `DISPLAY_NUM` | `99` | X display |
| `CHIV_PREFIX` | `./state/prefix` | Writable, private Proton prefix |
| `CHIV_LOCALAPPDATA` | `./state/appdata` | Writable, private AppData/log root |
| `CONTAINER_NAME` | `chiv-x64` | Optional Docker identity |
| `IMAGE_NAME` | `chiv-x64-native:local` | Optional Docker image tag |

The four ports must be unique and within 1–65535. On host-networked Docker,
container/image names do not reserve ports. Check for conflicts before launch.

## Paths and permissions

The Compose service runs as UID/GID `1000:1000`. Inputs must be readable by
that identity; prefix/AppData must also be writable. Preflight inspects mode
bits and reports ACL/unknown cases rather than changing permissions. Do not
solve access problems by running as root or making private data world-readable.

Local credentials, `.env`, game files, Proton, prefix, AppData, CLI bundles,
registries, and logs must never be committed or shared. Git ignore is not a
security boundary.

## Helper exit statuses

`check-config.sh`: 0 passed, 2 invalid/missing configuration or inputs, 3
required host tools/Compose unavailable. `verify.sh`: 0 local readiness
evidence complete, 1 service stopped, 2 missing/incomplete/unknown evidence,
3 Compose/runtime unavailable. Neither helper tests public visibility.
