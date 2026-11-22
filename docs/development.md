# Acquisition and compatibility evidence

## Offline regression checks

From the repository root, run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

This suite uses local fixtures and does not need game files, credentials, a
Docker daemon, or network access. A few optional Compose semantic tests run only
when Docker Compose v2.23+ is installed; they invoke `docker compose config`
against temporary fixtures and do not start containers. Skips are reported
explicitly.

This page records the evidence behind the host inputs required by the x86_64
EGS Compose profile. It is a research record, not a claim that a clean install
or complete server launch has been tested. **No game download, login, bundle
build, or server launch was performed for this research.**

## Onboarding validation boundary

Reviewed from the repository checkout with no inherited `.env`, credentials, or
game installation. `setup.sh --help` was smoke-tested from outside the checkout;
the offline test suite uses temporary fixture directories and dummy values.

| Evidence level | Result |
|---|---|
| Static/source review of Compose, helper contracts, paths, warnings, and docs | Verified; links and documented defaults reviewed |
| Automated offline fixtures | 37 tests passed |
| Compose semantic config validation | **NOT RUN**; Docker Compose v2.23+ unavailable (4 optional tests skipped) |
| Real fresh game acquisition / authentication / prefix initialization | **NOT RUN** |
| CLI source + selected plugin release | Source/release identities selected and documented below; actual build/registry integration **NOT RUN** |
| Proton compatibility-client input | **BLOCKED / NOT ESTABLISHED**; `--steam-path` contents/source still need real-world setup follow-up |
| Local game process/readiness | **NOT RUN** |
| Backend registration / public listing | **NOT RUN** |
| External IPv6 reachability / gameplay | **NOT RUN** |

The fixture suite proves only the modeled behavior. It is not Compose validation,
artifact compatibility evidence, or a fresh-install trial. A clean installation
requires explicit authorization for the host, resources/ports/state, downloads,
authentication, lifecycle actions, and registration policy. No such live
validation is claimed here.

## Supported-input matrix

| Input | Source and version evidence | Expected input/check | Status and constraints |
|---|---|---|---|
| Chivalry 2 EGS game files | Epic entitlement; acquire with Heroic or `legendary-gl` 0.21.1 (the version pinned in `Dockerfile`) | Install root passed as `CHIV_GAME`; contains the game executable and content, readable by container UID 1000 | Documented path; acquisition/repair not executed. Account must own/access the EGS product. Do not redistribute game files. |
| EGS authentication | Heroic interactive Epic login, or Legendary `auth`; upstream: [Legendary CLI](https://github.com/derrod/legendary) | Private Legendary config directory mounted at `/opt/legendary`; never commit or print its contents | Documented. Operator must use an account with access to the game and authenticate on the host, not through this repo or container. |
| GE-Proton | Heroic's selected Proton-GE build; Compose currently names `GE-Proton11-11-x86_64` | `PROTON_DIR/GE-Proton11-11-x86_64/proton` must exist and be executable/readable | Existing deployment path is a compatibility expectation, not proof this precise archive remains available. Obtain from the project's official release/distribution channels and follow its license; redistribution rights are not established here. |
| Proton compatibility client | `server-cli` Linux workflow consumes a separate `--steam-path` input | `COMPAT_CLIENT_DIR` mounted at `/proton-compat-client`; must contain the client files expected by the CLI, readable by UID 1000 | **Remaining blocker:** no confirmed contents, version, acquisition path, or license/redistribution status. It is not Steam login data. The real-world setup agent must identify and validate this input before claiming a working chain. |
| Proton prefix | Created by launching the installed EGS game once with the selected Heroic runner and configured compat-data location | `CHIV_PREFIX/pfx/system.reg`; prefix is writable, private, owned/accessibly mapped to UID 1000 | Documented initialization procedure, not executed. Compose mounts this as `/proton-prefix`. Do not copy a Windows prefix or credentials. |
| Unchained server CLI | [`server-cli` branch CLI README](https://github.com/Chiv2-Community/UnchainedLauncher/tree/server-cli/UnchainedLauncher.CLI); build instructions require .NET 10 SDK; Linux publish additionally needs Rust and `uvx`/`cargo-xwin` | Linux publish output in `CLI_DIR`, including executable `UnchainedLauncher.CLI` and bundled helper; `server --help` must run | Selected source: current observed branch tip `7007d68dae663ec8be65125a72028bb33c3d26b6` (moving branch; pin this revision for the next setup). Build is not performed here. Review upstream license; TBL input must come from an entitled game installation. |
| Plugin registry and plugin DLL | [UnchainedPlugin v1.0.1 release](https://github.com/Chiv2-Community/UnchainedPlugin/releases/tag/v1.0.1), release commit `2382eee09f11f19b6794e88d73b1e9c10a873945`; [registry metadata](https://github.com/Chiv2-Community/C2ModRegistry/blob/main/dll_db/packages/Chiv2-Community/UnchainedPlugin.json) | Compose selects `Chiv2-Community/UnchainedPlugin:v1.0.1`; local registry must provide that release's DLL and metadata | Selected per operator direction. Registry metadata identifies the DLL SHA-256 as `85cf655d7af84ea9d933c06d05efdb11743ab1d5a93aefeff1e0de474ced469d`. Release history includes IPv6 server support (v1.0.0) and v1.0.1 server-integration updates. The local registry bundle and CLI compatibility are not exercised here; real-world setup must verify them. Review license/redistribution rights before distributing the artifact. |

The repo image separately installs `legendary-gl==0.21.1` for the CLI's
container-side EGS argument handling; it does not acquire game files or replace
host-side Heroic/Legendary authentication.

## Game acquisition: two documented paths

### Fresh download (proposed; not executed)

1. Install Heroic from its [official Linux installation instructions](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/wiki/Linux-Quick-Start-Guide)
   or install the pinned Legendary version in an isolated Python environment.
   Heroic is a GUI and uses Legendary for Epic games; headless Legendary is a
   separate CLI and does not provide Heroic's GUI workflow.
2. Sign in interactively using the operator's own Epic account and confirm the
   account has access to Chivalry 2. Do not automate login or share authentication
   state.
3. In Heroic, locate Chivalry 2 in the library, choose an install directory
   outside this repository, and install. For Legendary, first authenticate and
   list available games; use the **exact app name shown by that account**:

   ```sh
   legendary auth
   legendary list
   legendary install "<exact Chivalry 2 app name from legendary list>" \
     --base-path /srv/chiv-x64-server
   legendary verify "<exact Chivalry 2 app name from legendary list>"
   legendary list-installed --show-dirs
   ```

   The name is intentionally not supplied here: Epic app identifiers vary and
   must not be guessed. `legendary list --json` is also available for inspection.
4. Verify/repair with Legendary's `verify` command (or `install --repair`), or
   Heroic's game-page verification action. Point `CHIV_GAME` at the listed,
   verified install root only after
   the tool completes successfully.

Legendary 0.21.1 source confirms its config directory resolution:
`LEGENDARY_CONFIG_PATH`, then `$XDG_CONFIG_HOME/legendary`, then
`~/.config/legendary`. Heroic may use its own application-data location and
bundled Legendary; use the actual config that Heroic maintains, not an assumed
path. Native Linux installs generally use the user's XDG config locations.
Flatpak data is sandboxed under the Flatpak app data area (commonly
`~/.var/app/com.heroicgameslauncher.hgl`); grant the Flatpak filesystem access
to the chosen game/proton directories and locate its real Legendary config from
Heroic settings/files rather than substituting the native path. These paths vary
with package and user configuration.

### Import an existing legitimate install (proposed; not executed)

Use Heroic's import-existing-game action and select the install root, or use
`legendary import "<exact app name from legendary list>" /path/to/game` with
Legendary 0.21.1. Then run the platform's verify/repair operation and wait for
completion. This is preferable to blindly copying an installation: if a transfer
is necessary, review a source-specific manifest and exclude credentials,
registry state, and development artifacts. Keep the source until destination
verification passes.

## Proton and prefix initialization

Use Heroic to select/install the intended GE-Proton release. Configure the
game's compatibility-data/prefix directory to the path that will become
`CHIV_PREFIX`, then launch the imported/installed game once through that runner.
Confirm `CHIV_PREFIX/pfx/system.reg` exists. Do not proceed with an empty prefix.
Keep it private and writable by the server's UID/GID `1000:1000`; do not share an
active writable prefix with another server process.

The CLI README documents Linux overrides `--proton-path`,
`--compat-data-path`, `--steam-path`, and `--proton-helper`; its compat-data
path must contain `pfx`. In this repo, the compatibility client is mounted at
`/proton-compat-client` and passed as `--steam-path`. This is a runtime input
name, not a requirement to log in to Steam. The correct compat-client contents
and a reproducible public acquisition source remain unverified.

## CLI and registry acquisition

The `server-cli` branch currently points to commit
[`7007d68dae663ec8be65125a72028bb33c3d26b6`](https://github.com/Chiv2-Community/UnchainedLauncher/commit/7007d68dae663ec8be65125a72028bb33c3d26b6)
(observed 2026-11-22). Use that immutable revision for the next build rather
than relying on a future branch tip. Its CLI README gives a source-build
procedure: from that launcher source checkout, install .NET 10 SDK, Rust, and
`uvx` / `cargo-xwin`, then run:

```sh
dotnet publish UnchainedLauncher.CLI -c Release -r linux-x64 -o out-cli
```

This branch's README states that a game installation containing `TBL` is
required. Verify the published executable with `UnchainedLauncher.CLI server
--help`. The source procedure is documented but was not built here. Review the
source repository's license before redistribution.

The CLI README supports local registry specifications (`local:/path`) and
versioned DLL selection. Compose now references the public `v1.0.1` release
through the local registry. Its release history records IPv6 support and later
server-registration changes. This selection is not a substitute for verifying
the downloaded/local registry contents and running a compatible CLI against
the IPv6 registration configuration.

### Handoff for the real-world setup agent

Use the documented `server-cli` source revision and the v1.0.1 plugin selection.
Identify the correct `--steam-path` compatibility-client artifact and its
source/license, build the CLI, assemble the expected local-registry layout, and
verify the release DLL hash against the registry metadata. Then perform the
authorized local integration checks. Do not treat the branch or release choice
alone as proof that the complete runtime combination works. Any launch must
account for `--register` and the possibility of public listing.

## Wrapper decision and validation boundary

No `download-game.sh` is proposed. Heroic and Legendary already document install,
import, and verification flows; a wrapper would duplicate authentication and
app-name selection and add risk without removing a demonstrated recurring error.
Use their supported commands directly.

Evidence reviewed on 2026-11-22:

- Legendary 0.21.1 source (`legendary/lfs/lgndry.py`) confirms config path
  precedence. CLI docs: <https://github.com/derrod/legendary>.
- Heroic Linux guide and project wiki describe Epic login, Linux packaging, and
  game setup: <https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/wiki/Linux-Quick-Start-Guide>.
- UnchainedLauncher `server-cli` branch CLI README documents build, launch,
  Proton, EGS, and registry behavior:
  <https://github.com/Chiv2-Community/UnchainedLauncher/blob/server-cli/UnchainedLauncher.CLI/README.md>.
  The branch revision observed was
  <https://github.com/Chiv2-Community/UnchainedLauncher/commit/7007d68dae663ec8be65125a72028bb33c3d26b6>;
  it is a moving branch, not a release guarantee.
- Public plugin registry package metadata:
  <https://github.com/Chiv2-Community/C2ModRegistry/blob/main/dll_db/packages/Chiv2-Community/UnchainedPlugin.json>.
- UnchainedPlugin v1.0.1 release notes and tag/commit:
  <https://github.com/Chiv2-Community/UnchainedPlugin/releases/tag/v1.0.1>.
- The public registry metadata gives the release asset hash; no DLL was
  downloaded or independently hashed during this repository update.

No authentication, game downloads, bundle builds, server launches, external
backend queries, or live registration tests were performed. The selected CLI
source revision and plugin release are documented, but no local CLI/registry
bundle was assembled. The `--steam-path` compatibility-client source/content
remains the explicit external blocker and handoff action for the next
real-world setup agent. A clean install and full integration remain unverified.
