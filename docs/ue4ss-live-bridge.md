# Optional: UE4SS live bridge on this server

An **optional** development add-on: load UE4SS and the PythonScripting live
bridge inside the running dedicated server so you can execute Python in the live
game from the host (inspect actors, drive the world). It is **not** needed for
normal operation, and it modifies the game directory and the Compose service.

UE4SS runs **alongside** the server's UnchainedPlugin — coexistence was
observed on the reference deployment. This optional path is documentation only:
the repository does not bundle UE4SS/PythonScripting or alter/start a server.

> The reasoning behind each step (why `ProcessEvent`, how the Wine path maps,
> the proxy override, the read-only-mount limitation) is game-agnostic and
> documented in the base repo: `ue4ss-python/docs/HEADLESS.md` (and `LIVE.md`).

## What you supply

Nothing here ships UE4SS. Build/obtain from `ue4ss-python` (and the proxy
builder), subject to RE-UE4SS licensing and the separate distribution gate:

- the UE4SS proxy `dwmapi.dll`, `UE4SS.dll`, and a `UE4SS-settings.ini`;
- the `PythonScripting` mod payload (`ue4ss-python/dist/PythonScripting`:
  embedded CPython, `python_scripts/`, `dlls/`).

## Manual, opt-in setup

Let `WIN64` be `<game>/TBL/Binaries/Win64` on the host.

1. Stop the service and make a separate writable game copy if the normal
   read-only game mount must remain protected. Back up the existing
   `UE4SS-settings.ini`, mod directory, and Compose configuration. Do not
   modify a live/loaded UE4SS installation or replace a loaded DLL.
2. **UE4SS core** → install the matching `dwmapi.dll`, `UE4SS.dll`, and
   `UE4SS-settings.ini` into `WIN64/`, following the base repository's
   compatibility and licensing instructions.
3. **PythonScripting** → install the matching payload in
   `WIN64/Mods/PythonScripting/` and enable it in `mods.txt`. Prefer the
   stable managed bootstrap instead of editing a generated `main.py`. Let
   `MOD` be the host path to that installed mod directory:

   ```sh
   python tools/managed.py --mod-dir "$MOD" --dry-run install
   python tools/managed.py --mod-dir "$MOD" install
   python tools/managed.py --mod-dir "$MOD" --dry-run live-enable --transport file \
     --inbox 'Z:\game\TBL\Binaries\Win64\Mods\PythonScripting\live\inbox' \
     --outbox 'Z:\game\TBL\Binaries\Win64\Mods\PythonScripting\live\outbox' \
     --heartbeat 'Z:\game\TBL\Binaries\Win64\Mods\PythonScripting\live\alive'
   python tools/managed.py --mod-dir "$MOD" live-enable --transport file \
     --inbox 'Z:\game\TBL\Binaries\Win64\Mods\PythonScripting\live\inbox' \
     --outbox 'Z:\game\TBL\Binaries\Win64\Mods\PythonScripting\live\outbox' \
     --heartbeat 'Z:\game\TBL\Binaries\Win64\Mods\PythonScripting\live\alive'
   ```

   Run these tools from the base `ue4ss-python` checkout. Review the dry-run
   before applying it. The component paths are Windows/Wine paths visible to
   the game; create the corresponding `live/inbox` and `live/outbox`
   directories in the host-mounted game tree. The host CLI must use the actual
   host path for that same directory. The commands update local files only;
   keep the install and token/configuration state local.
4. **Game-thread progress** → do not set
   `DefaultExecuteInGameThreadMethod` as a Python executor control: that is a
   UE4SS Lua setting. Python uses the engine-tick callback when available;
   `PYUE_EXECUTOR=processevent` explicitly forces the ProcessEvent fallback,
   otherwise it is selected automatically only when the tick callback is
   unavailable. The fallback treats the first ProcessEvent callback thread as
   the presumed game thread, which is a heuristic, not a dedicated-server
   guarantee. See `ue4ss-python/docs/HEADLESS.md`.
5. **Session transport/path** → for file IPC, configure both the game and host
   client to see the same session directory. The Wine path corresponding to
   the default host mount (`CHIV_GAME` → `/game`, Wine `z: -> /`) is:

   ```
   Z:\game\TBL\Binaries\Win64\Mods\PythonScripting\live
   ```

   Resolve and configure the actual session directory for the installed bridge;
   do not hand-edit generated bridge source. File IPC requires a writable
   shared directory. For TCP, the game listener is loopback-only inside its
   network namespace; host access needs an explicit host-network route or SSH
   tunnel and a separately provisioned private token.
6. **Compose** → only after reviewing the security and isolation impact, make
   the game mount writable for UE4SS logs/state and configure the Wine proxy
   override when required by the installed proxy:

   ```yaml
   environment:
     WINEDLLOVERRIDES: "dwmapi=n,b"
   ```

   The example Compose service intentionally remains unchanged and read-only.
   Any edited service must be explicitly reviewed and recreated by its
   operator; this guide does not authorize or perform that action.

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
- This is not an approved server deployment or validation. The earlier
  reference-server report observed bridge heartbeat/status/execute, but did not
  establish that a Lua executor setting caused Python game-thread progress.
- A dedicated server has no local player. The optional workbench
  `chivalry2_ai` payload's managed overlay wraps the player chat/UI adapter; its
  `!ai` own-chat path is therefore not a headless server interface. Do not
  enable it as a server component without a server-specific command/event
  adapter and a separately configured AI host. Neither is supplied here. The
  live bridge remains the applicable headless interface once game-thread
  progress is verified on the target server.
