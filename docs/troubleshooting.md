# Troubleshooting

Use the read-only checks first. Neither helper changes host state.

| Symptom | Check | Next action |
|---|---|---|
| Compose config fails | `./scripts/check-config.sh` | Check required values and path types in `.env`; resolver output suppresses interpolated details |
| Input permission unknown/fails | Review the reported variable and UID/GID `1000:1000` | Check parent-directory traversal and ACLs locally; do not use blanket `chmod` |
| No preferred global IPv6 | `ip -6 addr` locally; compare to configured address | Select the stable assigned address, not a temporary/privacy address |
| Port conflict/not listening | `./scripts/verify.sh` and `ss -lntup` | Identify the owning service; do not stop another service without approval |
| Container stopped/restarting | `./scripts/verify.sh` | Inspect logs privately and check CLI/plugin compatibility; redact before sharing |
| Game process absent | `./scripts/verify.sh` | Confirm launch reached the game binary; missing process is not by itself proof of a crash |
| Old/copied markers or timestamp unknown | Check configured AppData log files locally | Untimed/malformed lines are not treated as current-run success |
| Browser ping fails | Check advertised IPv6, UDP ping port, relay, firewall and ICMPv6 path | Test externally from an IPv6-capable client; helper does not query public services |
| A2S works, gameplay fails | Test configured game UDP port independently | The IPv6 relay carries ping/query only, not gameplay |
| Auth/prefix startup fails | Check private host Legendary config and initialized prefix | Confirm `pfx/system.reg`; do not copy another user's credentials or Windows prefix |

Do not post raw logs, `ps ... args`, resolved Compose configuration, tokens,
credential files, or device codes. Local readiness and external visibility
are separate questions.
