# Configuration and setup-helper contract

## Effective configuration

`scripts/lib/config.py` is the shared read-only resolver. It requires Docker
Compose v2.23.0 or newer and Python 3.10 or newer. It asks Compose for its
canonical JSON model using
`docker compose config --format json`. Compose, not this project, interprets
`.env`, shell overrides, quoting, interpolation, and path bases. The resolver
does not source `.env`, evaluate shell text, or implement dotenv parsing.

Consumers may use the default JSON output or the limited `--udp-ports` and
`--check-inputs` views. JSON contains only this allowlist for service
`chiv-x64`:

- Identity: service, image, container name, and user.
- Host paths: `CHIV_GAME`, `CLI_DIR`, `PROTON_DIR`,
  `COMPAT_CLIENT_DIR`, `LEGENDARY_CONFIG`, `CHIV_PREFIX`, and
  `CHIV_LOCALAPPDATA`, mapped from the canonical bind-mount sources.
- Runtime settings: game/ping/query/RCON ports, display, advertised address,
  server name, browser backend, and saved-directory suffix.

No full Compose model, environment map, command, Compose stderr, or credential
value is returned. Errors use a safe generic message because Compose failure
output may include interpolated values.
The four server ports must be valid TCP/UDP port numbers and must be distinct,
as required by the CLI server options.

Exit codes for the resolver and setup helper:

| Code | Meaning |
|---:|---|
| 0 | Resolution/check succeeded; `--help` also exits 0 |
| 2 | Invalid/missing user configuration or input |
| 3 | Required Compose/runtime capability unavailable |
| 4 | Local file write/read failure |
| 130 | User cancelled (SIGINT) |

`check-config.sh` requires an existing `.env`, then delegates to the shared
resolver and read-only preflight. It verifies input types/content markers,
`pfx/system.reg`, mode-bit access as the configured numeric container UID/GID,
the locally assigned preferred global IPv6 address, configured socket
collisions, the current service's existing listeners, and its Xvfb process.
Game-file identity and exact compatibility-client contents are explicitly
reported as unverified until the artifact follow-up (`chiv-4f7.9`) resolves
those inputs. (The plugin is no longer a local input: the pinned public release
is resolved and downloaded from the launcher's official registry.)
ACL permissions, missing optional AppData mount sources, inaccessible socket
ownership, and other unprovable states are reported as unknown with a manual
check rather than a pass. It does not print private host paths, create missing
directories, or change permissions. It exits 2 for missing/invalid
configuration and 3 when Compose or required host tools are missing.

## `setup.sh` CLI

The setup assistant implements this contract:

- Interactive mode is the default. `--non-interactive` requires all required
  values as flags; never prompt in this mode.
- `--help` prints usage without reading or changing `.env`.
- Never overwrite an existing `.env`. If it exists, stop with code 2 and ask
  the operator to back it up/remove it deliberately before retrying.
- `--check-only` validates proposed answers and Compose resolution without
  writing `.env`.
- Cancellation and every validation/dependency failure leave `.env` untouched.
- Required options: `--server-advertise-ip`, `--chiv-game`, `--cli-dir`,
  `--proton-dir`, `--compat-client-dir`, and `--legendary-config`.
- Optional settings/options: `--server-name`, `--saved-dir-suffix`,
  `--server-browser-backend`,
  `--game-port`, `--ping-port`, `--query-port`, `--rcon-port`,
  `--display-num`, `--container-name`, `--image-name`, `--chiv-prefix`, and
  `--chiv-localappdata`. Unspecified optional values retain Compose defaults.

The resolver never creates `.env`; only `setup.sh` writes it, after validation.
