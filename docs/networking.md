# Networking and registration

The supplied Compose profile uses host networking and is IPv6-enabled. It
requires a stable, preferred global IPv6 address assigned locally; enter the
raw address in `SERVER_ADVERTISE_IP`. The preflight checks local assignment,
not Internet reachability. IPv4-only or dual-stack support is not claimed.

| Port | Protocol | Purpose |
|---:|---|---|
| `GAME_PORT` (default 7777) | UDP | Gameplay |
| `PING_PORT` (default 3075) | UDP | Browser ping/beacon |
| `QUERY_PORT` (default 7071) | UDP | A2S query |
| `RCON_PORT` (default 9001) | TCP | Administration; keep loopback-only |

The IPv6 relay binds the advertised IPv6 address for ping/query and forwards
to local IPv4 sockets; it does not relay gameplay. Allow only the ports needed
in the host/router policy. Preserve ICMPv6, neighbor discovery, and
path-MTU behavior. This repository does not configure a firewall or router.
Review existing policy before making any host changes.

The Compose command includes `--register`. Starting it may publish a listing
through `SERVER_BROWSER_BACKEND`; inspect the backend and address before
running `./scripts/start.sh`. A local “HB Success” log is not proof that a
public listing exists.

`./scripts/verify.sh` reports local sockets only. Test A2S, browser ping, and
gameplay independently from an IPv6-capable external client. No external
probe, backend lookup, or public listing check is performed by this repository.
