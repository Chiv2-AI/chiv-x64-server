# Fresh setup

This guide describes acquisition paths; it does **not** claim a fresh install
or end-to-end launch has been validated. The selected CLI source and plugin
release are documented in [development evidence](development.md); the
`--steam-path` compatibility-client contents/provenance and actual integration
validation remain open. Do not substitute arbitrary binaries or releases.

## Host prerequisites

- Native Linux x86_64, Docker Engine, and Docker Compose v2.23.0+.
- Python 3.10+, `iproute2` (`ip` and `ss`), and Docker access for the operator.
- A stable, preferred global IPv6 address on the host. The supplied profile is
  IPv6-enabled; IPv4-only use needs a separately reviewed and validated profile.
- Legitimate EGS entitlement and enough disk space for game, Proton, prefix,
  and writable state.

Docker access is effectively root-level. Keep the checkout operator-owned and
do not run the game container as root. The helper scripts do not install
packages, configure firewall rules, create state directories, or use `sudo`.

## Choose how to acquire game files

### Heroic GUI route

1. Install Heroic from its [official Linux guide](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/wiki/Linux-Quick-Start-Guide).
2. Sign into Epic interactively with the account entitled to the game.
3. Install Chivalry 2 outside this repository and run Heroic's verify/repair.
4. Locate Heroic's actual Legendary configuration directory; package formats
   (including Flatpak) use different locations. Set `LEGENDARY_CONFIG` to that
   private directory. Never copy browser cookies or credentials from another
   machine.

### Legendary headless route

The pinned `legendary-gl` version is 0.21.1. Install it in an isolated Python
environment and use your own interactive account authentication. The exact
application name must come from your account; do not guess it:

```sh
legendary auth
legendary list
legendary install "<exact Chivalry 2 app name from legendary list>" --base-path /path/to/install
legendary verify "<exact Chivalry 2 app name from legendary list>"
legendary list-installed --show-dirs
```

The credential directory is private host state, not an input to this helper.
No login or download is initiated by this repository.

## Proton prefix and CLI/plugin inputs

Use Heroic to install/select the GE-Proton version required by the compatible
CLI. Configure the game's compat-data directory to the future `CHIV_PREFIX`,
launch the imported/installed game once through that runner, and verify
`CHIV_PREFIX/pfx/system.reg` exists. Do not use an unrelated Windows prefix.

`CLI_DIR` must contain `UnchainedLauncher.CLI`; `COMPAT_CLIENT_DIR` must contain
the files that CLI build expects (it is not a Steam account); and
`LOCAL_REGISTRY` must contain the CLI-compatible plugin registry and DLL
referenced by Compose (currently `Chiv2-Community/UnchainedPlugin:v1.0.1`).
See [the compatibility record](development.md) for provenance and the
remaining compatibility-client gap. These inputs are not built,
authenticated, or downloaded by the setup helper.

## Configure, review, and start

From the repository root:

```bash
./scripts/setup.sh
./scripts/prepare-host.sh
./scripts/check-config.sh
```

`setup.sh` writes only `.env`, with mode 0600, after Compose validation. It
never accepts credentials or copies auth/prefix state. Review
[configuration](configuration.md) and [networking](networking.md) before
starting. Starting the service uses `--register` and **can publish a listing**:

```bash
./scripts/start.sh
```

Do not start until you deliberately accept registration and have reviewed the
advertised address, backend, and firewall. Then use `./scripts/verify.sh` for
local observations and perform external checks separately.
