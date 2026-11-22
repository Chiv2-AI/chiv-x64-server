# Optional: UE4SS live bridge on this server

An **optional** development add-on: load UE4SS and the PythonScripting live
bridge inside the running dedicated server so you can execute Python in the live
game from the host (inspect actors, drive the world). It is **not** needed for
normal operation, and it modifies the game directory and the Compose service.

UE4SS runs **alongside** the server's UnchainedPlugin — the two coexist.

> The reasoning behind each step (why `ProcessEvent`, how the Wine path maps,
> the proxy override, the read-only-mount limitation) is game-agnostic and
> documented in the base repo: `ue4ss-python/docs/HEADLESS.md` (and `LIVE.md`).

## What you supply

Nothing here ships UE4SS. Build/obtain from `ue4ss-python` (and the proxy
builder), subject to RE-UE4SS licensing:

- the UE4SS proxy `dwmapi.dll`, `UE4SS.dll`, and a `UE4SS-settings.ini`;
- the `PythonScripting` mod payload (`ue4ss-python/dist/PythonScripting`:
  embedded CPython, `python_scripts/`, `dlls/`).

## Steps

Let `WIN64` be `<game>/TBL/Binaries/Win64` on the host.

1. **UE4SS core** → copy `dwmapi.dll`, `UE4SS.dll`, `UE4SS-settings.ini` into
   `WIN64/`.
2. **PythonScripting mod** → copy the payload to `WIN64/Mods/PythonScripting/`;
   ensure `WIN64/Mods/mods.txt` contains `PythonScripting : 1` and the mod has
   an `enabled.txt`.
3. **ProcessEvent drain** (required on a headless server) → in
   `WIN64/UE4SS-settings.ini`, under `[General]`, add:

   ```ini
   DefaultExecuteInGameThreadMethod = ProcessEvent
   ```

   Without this the bridge freezes before a match starts (the default
   `EngineTick` pump stalls at `WaitingToStart` with no players). See
   `ue4ss-python/docs/HEADLESS.md`.
4. **Bridge session path** → the bridge's
   `Mods/PythonScripting/python_scripts/main.py` hardcodes its session dir.
   Rewrite its `INBOX`/`OUTBOX`/`HEARTBEAT` to the **Wine** path the game sees.
   With this repo's default mount (`CHIV_GAME` → `/game`, and Wine `z: -> /`)
   that is:

   ```
   Z:\game\TBL\Binaries\Win64\Mods\PythonScripting\live
   ```

   Create `live/inbox` and `live/outbox` under that folder on the host.
5. **Compose** → UE4SS must load its proxy and write into the game dir, so for
   this service:
   - change the game mount from `:ro` to `:rw`;
   - add to `environment:`  `WINEDLLOVERRIDES: "dwmapi=n,b"`.

   Then recreate: `docker compose up -d --force-recreate`.

## Verify

- `WIN64/UE4SS.log` shows UE4SS init and
  `PythonScripting: … main.py …` followed by `[Python] live bridge ready`.
- The heartbeat advances — watch `…/PythonScripting/live/alive`.
- From the host (using the base repo's client):

  ```sh
  export PYUE_LIVE_DIR=<host game>/TBL/Binaries/Win64/Mods/PythonScripting/live
  python3 ue4ss-python/tools/live.py --session-dir "$PYUE_LIVE_DIR" status
  python3 ue4ss-python/tools/live.py --session-dir "$PYUE_LIVE_DIR" \
      exec "len(ue4ss.find_all_of('Actor'))"
  ```

  A healthy run reports `the bridge is alive` and returns results from the live
  world.

## Caveats

- `:rw` on the game mount gives up the read-only safety of the default profile.
- If several services mount the **same** `CHIV_GAME`, enabling UE4SS in that
  directory affects all of them; use a separate game copy if you want isolation.
- Keep backups of anything you overwrite (`UE4SS-settings.ini`, the service's
  compose file).
- The in-game `!ai` chat overlay is a separate feature and is not covered here.
