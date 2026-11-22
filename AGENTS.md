# Repository agent notes

- Scope: native Linux x86_64 + EGS + GE-Proton + Unchained CLI only. Do not
  claim IPv4, ARM64, fresh-install, or artifact compatibility without evidence.
- Keep work in this repository. The Beads tracker lives at
  `/home/rmary/projects/unchained/chiv_arm64`; use `bd` there for durable task
  status and run `bd prime` when resuming tracker work.
- Never authenticate, download game data, query public backends, start/stop/
  recreate live services, or test external gameplay without explicit approval.
  `scripts/start.sh` may publicly register the server.
- Do not expose raw logs, process argv, resolved Compose environments,
  credentials, tokens, or authentication output. Keep RCON loopback-only.
- Do not add sudo/firewall automation, credential or prefix copying, or
  destructive cleanup. Game/tool mounts remain read-only.
- Run offline regression tests with
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`.
  Compose-dependent tests may skip if Docker Compose is unavailable.
- Report validation limits explicitly. Do not commit, push, or sync without
  authorization.
