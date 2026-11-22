# chiv-x64-server

Reusable **x86_64** Docker setup for a headless **Chivalry 2 dedicated server**,
run through **GE-Proton** and the **UnchainedLauncher.CLI**. It is the native-x64
counterpart to the Orin/ARM server setup.

This repo ships **only the scaffolding** — the Dockerfile, the compose file, an
IPv6→IPv4 UDP relay, and docs. It contains **no game files, no Proton build, no
launcher binary, and no credentials**; you supply those locally and point the
compose at them via `.env`.

## What you supply (not in this repo)

| Thing | `.env` key | Notes |
|---|---|---|
| Chivalry 2 install | `CHIV_GAME` | e.g. downloaded with `legendary` (EGS) |
| GE-Proton build | `PROTON_DIR` | the compose expects `GE-Proton11-11-x86_64`; change the path in `docker-compose.yml` for another version |
| Proton compat client | `COMPAT_CLIENT_DIR` | the `--steam-path` compat client |
| UnchainedLauncher.CLI | `CLI_DIR` | from Chiv2-Community; holds `UnchainedLauncher.CLI` |
| Plugin registry | `LOCAL_REGISTRY` | local registry that provides `UnchainedPlugin` |
| Legendary/EGS config | `LEGENDARY_CONFIG` | **holds Epic credentials — never commit** |

## Quick start

```bash
cp .env.example .env
# edit .env: set SERVER_ADVERTISE_IP and the paths above
docker compose build
docker compose up          # host networking; Ctrl-C sends SIGINT (clean stop)
```

The container runs an `Xvfb` display, starts the IPv6 UDP relay for the ping and
query ports, then launches `UnchainedLauncher.CLI server` against `/game` with
`UnchainedPlugin`.

## How it works

- **Host networking**: the game uses UDP `7777` (game), `3075` (ping), `7071`
  (query), and RCON on `9001` (keep RCON loopback-only in your firewall).
- **IPv6**: `ipv6-udp-relay.py` relays the IPv6 ping/query listeners to the local
  IPv4 sockets so the server is reachable over both. The launcher is started with
  `--use-ipv6` and `-MULTIHOME=$SERVER_ADVERTISE_IP`. Set `SERVER_ADVERTISE_IP`
  to the host's **stable** global IPv6 (not a temporary/privacy address).
- **State**: Proton's prefix and the game's LocalAppData live under `./state`
  (git-ignored) by default; override with `CHIV_PREFIX` / `CHIV_LOCALAPPDATA`.

## Mount layout (host → container)

| Host (`.env`) | Container |
|---|---|
| `CHIV_GAME` | `/game` |
| `CLI_DIR` | `/opt/cli` (ro) |
| `LOCAL_REGISTRY` | `/opt/local-registry3` (ro) |
| `PROTON_DIR` | `/proton/GE-Proton11-11-x86_64` (ro) |
| `COMPAT_CLIENT_DIR` | `/proton-compat-client` (ro) |
| `LEGENDARY_CONFIG` | `/opt/legendary` |
| `CHIV_PREFIX` | `/proton-prefix` |
| `CHIV_LOCALAPPDATA` | `…/AppData/Local/Chivalry 2` |
| `./ipv6-udp-relay.py` | `/opt/ipv6-udp-relay.py` (ro) |

## Firewall / IPv6 checklist

Default-deny incoming; LAN-only SSH; public UDP `7777/3075/7071`; RCON loopback
only. Confirm the host has a stable global IPv6 and that it survives restarts.

## Security

Never commit `.env`, the legendary config, the game files, Proton, or the
launcher. The `.gitignore` already excludes these; keep it that way.

## UE4SS / scripting (optional)

This base runs the Unchained server stack only. To add UE4SS + the
PythonScripting mod (for the live bridge / in-game scripting) on top, see the
`chivalry2-workbench` docs; note a dedicated server has no local player, so the
own-player `!ai` chat path does not apply — the live bridge does.
