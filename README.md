# Chivalry 2 x64 EGS server

This repository runs the Chivalry 2 dedicated server on **native Linux x86_64**
using Epic Games Store (EGS) game files, GE-Proton, and
`UnchainedLauncher.CLI`. It does not emulate x64 on ARM.

The repository supplies Compose/runtime scaffolding, not the game, CLI,
compatibility client, Proton files, or credentials. The pinned UnchainedPlugin
release is fetched from the launcher's official registry, not supplied here. The
plugin load and server-registration path is verified on a reference x64
deployment, but a reproducible from-scratch install (compatibility-client
provenance and a CLI build) is **not yet complete**; review [the supported-input
and acquisition evidence](docs/development.md) before choosing a setup path. You
need legitimate access to the EGS game.

## Supported configuration

| Host/runtime | Game/platform | Network profile | Status |
|---|---|---|---|
| Linux x86_64, Docker Engine, Compose v2.23+ | EGS + GE-Proton + Unchained CLI | IPv6-enabled; stable global IPv6 required | Repository profile; complete clean install not validated |

IPv4-only, Steam-login, ARM64, and dual-stack operation are not supported by
the supplied profile.

## Choose a setup path

- **Fresh install:** use [docs/setup.md](docs/setup.md). It separates Heroic
  (GUI) and Legendary (headless CLI) acquisition and identifies the remaining
  compatibility-client and integration validation. Do not proceed as if the
  full chain were proven.
- **Existing compatible inputs:** use [docs/existing-install.md](docs/existing-install.md)
  to reuse read-only game/tool inputs with isolated writable state.

## Setup sequence

1. Review prerequisites and evidence in [setup](docs/setup.md).
2. Clone this repository into a directory owned by your operator account. Docker
   access is effectively root-level; do not run the service as root.
3. Configure an operator-owned `.env` with `./scripts/setup.sh`, or copy
   `.env.example` and edit it manually. Keep authentication files outside Git.
4. Review [networking and registration](docs/networking.md), including the
   stable global IPv6 and exposed ports.
5. Run `./scripts/prepare-host.sh` and `./scripts/check-config.sh`. These are
   read-only checks; missing artifacts are not downloaded or created.
6. Only when you are ready to publish/run the server, explicitly start it:

   ```bash
   ./scripts/start.sh
   ```

   **Warning:** the Compose command uses `--register` and can publish a server
   listing. Review the backend and advertised address first.
7. Check local evidence with `./scripts/verify.sh`; perform external IPv6,
   browser, and gameplay checks separately. The helper does not do them.

## Common commands

Run from the repository root:

| Command | Purpose |
|---|---|
| `./scripts/setup.sh --help` | Show configuration-helper options |
| `./scripts/setup.sh` | Guided configuration only; does not launch or download |
| `./scripts/prepare-host.sh` | Read-only host checks |
| `./scripts/check-config.sh` | Read-only configuration/input preflight |
| `./scripts/start.sh` | Build/start; may publicly register the server |
| `./scripts/verify.sh` | Local readiness snapshot; no external probes |
| `./scripts/rcon.sh <command> [args...]` | Send one RCON command; RCON remains loopback-only |
| `./scripts/stop.sh` | Stop the Compose service without deleting state |

See [configuration](docs/configuration.md),
[operations](docs/operations.md), and
[troubleshooting](docs/troubleshooting.md) for details. For code/test work, see
[development evidence](docs/development.md) and the repository-local `AGENTS.md`.

Optional, for development: [running the UE4SS live bridge on this server](docs/ue4ss-live-bridge.md)
(execute Python in the live game from the host; modifies the game dir and the
service).
