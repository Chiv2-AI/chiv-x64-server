# chiv-x64-server

Reusable **native x86_64** Docker setup for the Chivalry 2 dedicated server,
launched through GE-Proton and `UnchainedLauncher.CLI`. It runs without CPU
emulation.

The reference deployment uses **Epic Games Store (EGS)** files and
Heroic/Legendary authentication. The repository contains scaffolding only: no
game files, Proton build, launcher bundle, plugin registry, or credentials.
Steam is not the tested login path for this deployment. In particular,
`--steam-path` in the CLI command refers to its Proton compatibility-client
input; it does not mean that an interactive Steam login is needed.

## 1. Prerequisites

- An x86_64 Linux host with enough free disk space for the game, Proton, prefix,
  and persistent state. The deployed host was Ubuntu-based; other distributions
  may need package-name or firewall-command adjustments.
- Docker Engine and Docker Compose v2, usable by the account that will run the
  server. The server container runs as UID/GID `1000:1000` by default.
- A host address to advertise. **IPv6-specific:** the supplied Compose profile
  is configured for IPv6 and requires the host's current stable global IPv6
  address, not a temporary/privacy address.
- EGS game files, an initialized GE-Proton installation and compatibility
  client, a Linux `UnchainedLauncher.CLI` bundle, and a local plugin registry.
- A fresh Epic/Legendary authentication on the host. Do not copy credentials
  from another machine or put credentials, tokens, or private config in this
  repository.

### Step 1: verify the host

On Ubuntu, install Docker Engine and the Compose v2 plugin using the current
Ubuntu/Docker package instructions, then enable the daemon. Grant the intended
operator account Docker access only if you accept that Docker access is
effectively root-level. Do not run the game container as root to avoid
permission setup.

Run the read-only host preflight:

```bash
./scripts/prepare-host.sh
```

This checks architecture, Docker, Compose, and Docker access. It does not
install packages, create accounts, alter firewall settings, or use `sudo`.

## 2. Prepare the host directories and inputs

### Step 2: prepare directories and permissions

The example layout uses `/srv/chiv-x64-server`. The Compose service runs as UID/GID
`1000:1000`; verify the intended operator account matches, or deliberately
adjust the Compose `user` setting and ownership together:

```bash
id
sudo mkdir -p /srv/chiv-x64-server/{game,cli,proton,legendary-config}
sudo chown -R 1000:1000 /srv/chiv-x64-server
chmod 700 /srv/chiv-x64-server/legendary-config
```

If you do not have permission to create a directory under `/srv`, clone the
repository and keep its private `state/` under a directory owned by your
operator account instead; do not use `sudo` to run the repository or container.

Do not run the Docker service as root to work around permissions. Keep
authentication and Proton-prefix data private. Prefix and AppData state
defaults to `./state` in this checkout. Do not serve that directory over Samba
or commit it. If using `/srv` for state, create separate prefix and AppData
directories and assign them to UID/GID `1000:1000`.

### Step 3: stage and verify the EGS game

The reference deployment reused an existing EGS installation, transferred it
to a dedicated game directory, imported it into Heroic/Legendary, and repaired about
1.06 GiB of missing files rather than redownloading the full game. The source
was a development install, so the transfer was based on an audited/filtered
file set. Do not blindly copy Windows credentials, registry state, UE4SS or
research artifacts as part of a game transfer. Import/verify the destination
with the EGS toolchain and record any repair/download that occurs.

For a transfer, first produce/review a file manifest for the source install;
exclude credentials, registry state, and local development artifacts. Then
copy the reviewed files to the configured `CHIV_GAME` directory using a resumable tool such as
`rsync`, preserving the source until verification completes. The exact manifest
is source-install-specific, so this repo intentionally does not ship a blanket
copy command that could import private or irrelevant files.

In Heroic/Legendary, import the copied install at the configured `CHIV_GAME`, run
verification/repair, and wait for it to finish. Continue only after the
platform tool reports the install valid; record any files it had to download.

### Step 4: authenticate Epic and initialize Proton

Install/open Heroic on the host and use its interactive Epic login flow for the
intended account. Confirm the account is authenticated in Heroic; do not copy
browser cookies, Windows credentials, or another machine's auth state.

In Heroic, select/install the intended GE-Proton release and use the CLI
branch's supported Proton compatibility client. Launch the imported game once
through that runner so Heroic creates the compatibility prefix. The reference
layout used:

- Game: `/srv/chiv-x64-server/game`
- GE-Proton: `/srv/chiv-x64-server/proton/GE-Proton11-11-x86_64`
- Proton compatibility client: `/srv/chiv-x64-server/proton/compat-client`
- Prefix: `/srv/chiv-x64-server/prefix`
- Legendary config: the operator's private Legendary configuration directory

Before the first launch, configure Heroic's compatibility-data/prefix location
for this game to `/srv/chiv-x64-server/prefix`. Confirm that the initialized
prefix contains `/srv/chiv-x64-server/prefix/pfx/system.reg`.

Locate the Legendary configuration created by Heroic on your host. Set
`LEGENDARY_CONFIG` to that actual directory, or copy its contents to the
private `/srv/chiv-x64-server/legendary-config` directory
and point the variable there. Do not leave it empty or copy it into this Git
checkout. Preserve private permissions/ownership and ensure UID 1000 can read
it. Never paste login output, device codes, tokens, or credential files into
issue notes, logs, or Git.

**No VNC or Steam login is part of the verified EGS instructions here.** If a
different x64 Steam deployment is desired, document and validate it as a
separate workflow instead of treating it as a prerequisite for this one.

### Step 5: install the CLI bundle and plugin registry

Place the Linux `UnchainedLauncher.CLI` bundle in the directory configured by
`CLI_DIR`; it must contain the `UnchainedLauncher.CLI` executable. The deployed
bundle was built from the `server-cli` branch and included its native Proton
helper. Obtain a trusted Linux bundle built from
[UnchainedLauncher `server-cli`](https://github.com/Chiv2-Community/UnchainedLauncher/tree/server-cli);
this repository does not build or publish that bundle. Confirm
`UnchainedLauncher.CLI server --help` runs before continuing. Use a CLI build
compatible with the current game registry format.

The compatibility-client directory passed as `COMPAT_CLIENT_DIR` must contain
the client files expected by that CLI build. It is not a Steam account or
interactive login. Obtain it from the same trusted CLI/Proton deployment inputs
and confirm UID 1000 can read it; this repository does not bootstrap or
authenticate Steam.

Provide the plugin registry directory at `LOCAL_REGISTRY`, containing the
plugin release referenced by `--dll` in `docker-compose.yml`. The validated deployment used a
locally published `UnchainedPlugin` build compatible with the CLI and IPv6
registration behavior. Keep the registry read-only in the container.

## 3. Configure the deployment

### Step 6: set and validate `.env`

From this repository:

```bash
cp .env.example .env
```

Edit `.env` and set the host's paths and advertised address. The example values
assume the layout above. Required values:

| Variable | Meaning |
|---|---|
| `SERVER_ADVERTISE_IP` | Stable host address advertised by the server; raw IPv6, without brackets |
| `CHIV_GAME` | Verified EGS game directory |
| `CLI_DIR` | Directory containing `UnchainedLauncher.CLI` |
| `LOCAL_REGISTRY` | Local plugin registry directory |
| `PROTON_DIR` | GE-Proton directory containing `proton` |
| `COMPAT_CLIENT_DIR` | Proton compatibility-client directory passed as `--steam-path` |
| `LEGENDARY_CONFIG` | Private directory containing the host's Legendary/EGS configuration |
| `CONTAINER_NAME` | Optional unique Docker container name when sharing a Docker host |
| `IMAGE_NAME` | Optional unique Docker image tag when sharing a Docker host |

Optional server name, ports, display, prefix, AppData, image, and container
name overrides are listed in `.env.example`. When sharing a Docker host with
another deployment, set unique `CONTAINER_NAME` and `IMAGE_NAME` values.
Writable prefix and AppData paths must be exclusive to this deployment; never
share an active Proton prefix between containers. Game, Proton, CLI, and
compatibility-client inputs may be reused only when compatible; prefer
read-only mounts or isolated copies where the application might write.
Do not put passwords or tokens in `.env`; the Legendary
configuration path is a path to private credentials, not a place to paste
credentials themselves.

### Reusing files from another installation

Existing game files are mounted read-only by this Compose profile, and the CLI,
Proton, compatibility client, and local registry mounts are also read-only.
You may point those variables at compatible existing paths instead of copying
large inputs. Keep the Legendary config, Proton prefix, and AppData separate:
copy the auth config into a private, Git-ignored directory if needed, and give
this Compose project its own writable prefix and AppData paths. Never mount the
same active prefix writable into two containers.

For a separate checkout that reuses existing inputs, set `CHIV_GAME`, `CLI_DIR`,
`LOCAL_REGISTRY`, `PROTON_DIR`, and `COMPAT_CLIENT_DIR` in its private `.env` to
the compatible existing paths. Copy writable state into this checkout only
once, into new, empty, Git-ignored directories:

```bash
install -d -m 700 state/prefix state/appdata legendary-config
cp -a /path/to/existing/prefix/. state/prefix/
cp -a /path/to/existing/appdata/. state/appdata/
cp -a /path/to/existing/legendary-config/. legendary-config/
chmod 700 state/prefix state/appdata legendary-config
```

Set `CHIV_PREFIX=./state/prefix`, `CHIV_LOCALAPPDATA=./state/appdata`, and
`LEGENDARY_CONFIG=./legendary-config` in `.env`. Confirm the source directories
are the ones intended before copying; never copy into an existing state
directory or expose the resulting auth copy. Set distinct `CONTAINER_NAME` and
`IMAGE_NAME` values. The game/tool inputs remain mounted read-only. Check host
ports before launch; host networking prevents running another instance on those
same ports at the same time.

Host networking means container/image names do not isolate network ports.
Before starting, inspect existing containers and host listeners. Do not start
this service while another service is listening on the configured game, ping,
or query ports. This setup is not designed to run a second instance alongside
another server on the default ports; do not stop or recreate an existing
service just to free them.

Validate before launch:

```bash
./scripts/check-config.sh
```

This checks Compose interpolation and required input directories without
printing the fully rendered Compose configuration or secret values.

## 4. Firewall and network

### Step 7: review firewall and address configuration

The committed Compose configuration is the tested **IPv6-enabled** profile.
The IPv6 items below are only required when using IPv6; the standard IPv4 game
port requirements still apply. This is not an automatic dual-stack toggle: for
an IPv4-only host, do not put an IPv4 address in `SERVER_ADVERTISE_IP` and run
the files unchanged. The IPv6 relay binds an IPv6 socket, and the CLI/Unreal
arguments explicitly enable IPv6. An IPv4-only deployment needs a separate
Compose configuration that disables the relay and removes the IPv6-specific
CLI/Unreal flags, then must be validated independently.

Compose uses **host networking**, so the service binds directly on the host;
Docker port publishing is not used. Allow only the ports you intend to expose:

| Port | Protocol | Purpose |
|---:|---|---|
| 7777 | UDP | Gameplay |
| 3075 | UDP | Server-browser ping/beacon |
| 7071 | UDP | A2S query |
| 9001 | TCP | RCON; keep loopback-only or restrict to a trusted VPN/LAN |

Keep SSH administrative access LAN/VPN-only. A reference UFW policy uses
default-deny incoming, allows LAN SSH/Samba, and exposes UDP 7777, 3075,
and 7071. Review the host's existing policy and replace the example LAN range
before applying any commands. For UFW, confirm IPv6 filtering is enabled
(`IPV6=yes` in `/etc/default/ufw`) and preserve essential
ICMPv6/NDP/path-MTU traffic. Firewall changes require operator review and
`sudo`; none of the scripts in this repository applies them.

Example policy (adapt the LAN CIDR first; this does not open RCON):

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.0.0/24 to any port 22 proto tcp
sudo ufw allow from 192.168.0.0/24 to any port 445 proto tcp
sudo ufw allow 7777/udp
sudo ufw allow 3075/udp
sudo ufw allow 7071/udp
sudo ufw status verbose
```

Enable UFW only after confirming SSH access and the existing policy; otherwise
you may lock yourself out. Do not forward TCP 9001/RCON from the router.

**IPv6-specific settings:** the CLI receives `--use-ipv6` after its argument
separator and Unreal receives the IPv6 INI settings and `-MULTIHOME` address.
The included relay binds the advertised IPv6 address on UDP 3075/7071 and
forwards those ping/query packets to local IPv4 sockets; it does not relay
gameplay. The stable global IPv6 must match `SERVER_ADVERTISE_IP`. Do not run a
second relay on those ports. IPv6 also requires IPv6 firewall filtering and
working ICMPv6/NDP/path-MTU traffic; the IPv4 firewall rules alone are not
sufficient.

| Setup item | IPv4-only | IPv6-enabled Compose (as supplied) |
|---|---|---|
| Stable global IPv6 address | Not needed | **Required**; set raw address in `SERVER_ADVERTISE_IP` |
| `--use-ipv6` and Unreal IPv6 INI / `-MULTIHOME` args | Not needed | **Required** |
| `ipv6-udp-relay.py` for 3075/7071 | Not needed | **Required** for IPv6 ping/query listeners |
| IPv6 firewall and ICMPv6/NDP path | Not needed | **Required** |
| UDP 7777/3075/7071 game/browser ports | Required as used | Required as used; allow IPv6 too |

## 5. Start and stop

### Step 8: build and launch

Start in the foreground:

```bash
./scripts/start.sh
```

The script validates configuration and runs `docker compose up --build`.
Use `Ctrl-C` for the configured SIGINT clean stop. To stop a detached or
otherwise running Compose service without removing its container or state:

```bash
./scripts/stop.sh
```

The equivalent direct commands are `docker compose up --build` and
`docker compose stop`. Avoid `docker compose down -v` or deleting `state/`
unless you deliberately intend to remove persistent data.

### RCON administration

RCON listens on loopback only and should not be exposed through a router or
public firewall rule. From this repository directory, send one command with:

```bash
./scripts/rcon.sh servertravel tdm_darkforest
```

RCON may return no reply even when the game executes a command; the helper hides
reply contents and reports only the byte count. Verify any important change
through the server's status/logs. Map travel affects connected players, so
check the server is safe to change first. Avoid bot commands while a real
player may be connected.

## 6. Verify readiness

### Step 9: check local and external readiness

Run:

```bash
./scripts/verify.sh
```

The helper reports container state/restarts, matching server processes,
host-visible UDP listeners, and recent logs. A running container or open socket
alone does not prove that the server is ready. Confirm all of the following:

- Container remains running without a growing restart count.
- Logs show the server reached `State Up`, plugin/RCON startup, and successful
  browser-backend registration.
- UDP 7777, 3075, and 7071 are bound as intended.
- A2S query and browser ping work from another machine; test gameplay
  separately from A2S.
- Public IPv6 tests are made from an IPv6-capable external client, not only the
  host or LAN.

The helper reports only selected readiness-marker presence, not raw log lines.
Review logs privately if further diagnosis is needed and redact authentication
data before sharing them.

### Log locations

The game/plugin file logs are written under the host path configured by
`CHIV_LOCALAPPDATA`, normally:

```text
Saved_UnchainedX64/Logs/unchained.log
Saved_UnchainedX64/Logs/kismet.log
```

For the default state path, these are under
`./state/appdata/Saved_UnchainedX64/Logs/`. If `CHIV_LOCALAPPDATA` points
elsewhere, look beneath that configured host directory. When reusing or copying
AppData from another installation, existing log files are copied too; they may
contain earlier runs.

The container's stdout/stderr is separate and can be viewed with
`docker compose logs` from the repository directory. Treat raw game/container
logs as private and inspect them before sharing; server registration details
may appear there.

Useful manual checks:

```bash
docker inspect -f 'state={{.State.Status}} restarts={{.RestartCount}}' chiv-x64
ss -lunp | grep -E ':(7777|3075|7071)'
docker exec chiv-x64 ps -eo args
```

## 7. Troubleshooting

- **Compose rejects configuration or a mount:** rerun `./scripts/check-config.sh`;
  check `.env` values and that every host path exists and is accessible to
  UID/GID `1000:1000`.
- **Container repeatedly exits:** inspect `docker compose logs --tail=200`.
  Check the CLI build against the current plugin-registry JSON schema before
  changing launch flags. A registry serialization/schema mismatch can prevent
  startup; distinguish such fatal errors from non-fatal XKB warnings.
- **Authentication or launch arguments fail:** check the private Legendary
  configuration and initialized Proton prefix on the host. Do not copy a
  Windows prefix/credential store as a shortcut.
- **Server is up but browser ping is red:** check the current advertised
  address, UDP 3075 firewall path, relay process, and external IPv6 reachability.
  These relay/address checks are IPv6-specific; for IPv4-only, verify the
  direct IPv4 listener and do not run the IPv6-configured Compose unchanged.
- **A2S works but gameplay does not:** test UDP 7777 independently; the relay
  does not carry gameplay.
- **Listed address is an internal proxy address:** investigate the browser
  backend/reverse-proxy source-IP forwarding. Do not change the game host's
  bind address based only on an internal proxy address in the listing.

## Optional: LAN Samba shares

The reference deployment exposed only the game and AppData directories over
authenticated, LAN-restricted Samba shares. Do not share the Proton prefix,
Proton binaries, Legendary/Heroic configuration, CLI bundle, logs, or the
repository's `.env`. Configure and validate Samba on the host separately;
these Compose scripts do not manage Samba or its credentials.

## Repository contents and security

- `Dockerfile`, `docker-compose.yml`: runtime image and service definition.
- `ipv6-udp-relay.py`: small IPv6-to-local-IPv4 UDP relay for ping/query.
- `scripts/prepare-host.sh`: read-only host prerequisite check.
- `scripts/check-config.sh`: required config/path preflight.
- `scripts/start.sh`, `scripts/stop.sh`: Compose lifecycle helpers.
- `scripts/rcon.sh`: send a single command through the container's loopback RCON.
- `scripts/verify.sh`: container/process/socket/log snapshot.

Never commit `.env`, Legendary/Heroic credentials, game files, Proton, the
prefix, AppData, launcher bundles, local registries, or logs. `.gitignore`
excludes the expected local data paths; review it before adding new inputs.

## References

- Project checklist: `docs/IPv6 server setup checklist.md` in the source
  repository.
- Beads epic `chiv-8si.9` and its completed setup tasks record the reference
  EGS deployment steps and outcomes.
