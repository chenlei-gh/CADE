# CATIA UI Debug Tools

Diagnostic scripts for inspecting/driving a running CATIA (CNEXT) process
from outside — useful when a generated command's toolbar button doesn't
appear, doesn't respond to clicks, or a dialog won't open/close.

These were built and used to diagnose three real CADE code-generation bugs
(see the "对话框命令生命周期" / dialog-command-lifecycle notes in
`../../SKILL.md`'s production-readiness section): a NULL-parent dialog bug,
a `SetAccessChild` toolbar-overwrite bug, and a `Cancel()`-vs-`Desactivate()`
dialog-close bug.

## Why these exist

- **UI Automation and Win32 `TB_BUTTONCOUNT` do NOT work on CATIA's custom
  toolbar widgets.** Only brute-force `EnumChildWindows` + title-text
  matching reliably inspects CATIA toolbar/window contents from outside
  the process (`cade_findbtn.ps1`, `cade_enumwin.ps1`).
- Piping PowerShell script stdout directly through Git-Bash pipes is
  unreliable (UTF-16 / truncation issues) — redirect to a file with
  `Out-File -Encoding utf8` first if chaining these in a shell script.

## Scripts

| Script | Purpose |
|---|---|
| `cade_quit.vbs` | Clean COM shutdown (`app.Quit`) of a running CATIA. **Always prefer this over `taskkill /F`**, which corrupts `DialogPosition.CATSettings` and can trigger a blocking "Warm Start" recovery modal on next launch. |
| `cade_attach.vbs` | Attaches to a running CATIA via COM (`GetObject(, "CATIA.Application")`), opens a Part document, and dispatches a command by id (`app.StartCommand`) — useful for testing a command's `Activate`/`BuildGraph` path without clicking the UI. |
| `cade_enumwin.ps1` | Lists all top-level windows owned by a target PID plus child windows that look like dialogs (class `#32770` or title containing `CADEDlg`). |
| `cade_findbtn.ps1` | Brute-force search for toolbar/command windows by title-text match (edit the `-match` pattern for your command class names). |
| `cade_dismiss.ps1` | Finds the first visible native `#32770` dialog owned by a process and sends `ENTER` (e.g. to dismiss a blocking modal). |
| `cade_probeclick.ps1` | Simulates a real left mouse click at absolute screen coordinates (`SetCursorPos` + `mouse_event`) — needed because CATIA's toolbar buttons ignore `BM_CLICK`/`WM_LBUTTONDOWN` sent via `SendMessage`. |
| `cade_resize.ps1` | Repositions/resizes a named toolbar window to a fixed on-screen location — useful for recovering a toolbar pushed off-screen by a corrupted settings file. |
| `cade_shot.ps1` | Saves a PNG screenshot of a process's main window via `PrintWindow` (works even if occluded), plus lists any visible `CATDlgFloatingFrame` windows. |
| `cade_tbquery.ps1` | Reference-only: standard `TB_BUTTONCOUNT` query — does **not** work reliably on CATIA toolbars, kept for completeness/comparison. |
| `cade_uia.ps1` | Reference-only: UI Automation descendant enumeration — also does **not** reliably see CATIA's custom toolbar button controls, kept for completeness/comparison. |
| `cade_do_undo.ps1` / `cade_do_redo.ps1` | Reliably drives CATIA's Ctrl+Z/Ctrl+Y (Undo/Redo) on a given main-window hwnd: restores+maximizes the window, sets foreground, clicks inside the 3D view client area to guarantee real keyboard focus, then sends the key via `System.Windows.Forms.SendKeys`. **Must run window-restore + click + SendKeys in one single PowerShell process invocation** — splitting these steps across separate `terminal` tool calls loses OS foreground focus back to the calling shell/editor window in between, and the Ctrl+Z/Ctrl+Y appears to silently do nothing (or gets buffered and fires on some later, unrelated call). Usage: `powershell -ExecutionPolicy Bypass -File cade_do_undo.ps1 <mainHwnd>`. |
| `cade_do_undo_multi.ps1` | Same as `cade_do_undo.ps1` but sends Ctrl+Z N times in a loop (`<mainHwnd> <count>`) — useful when other Automation calls (e.g. `Selection.Add`/`Clear` in a colour-check script) were run in between and pushed extra entries onto CATIA's undo stack that need to be skipped past. |
| `cade_escape_and_undo.ps1` / `cade_escape_and_redo.ps1` | ESC-then-Ctrl+Z/Ctrl+Y combo on a given hwnd: first cancels any pending inline rename/edit in the tree, then performs the undo/redo. Useful when a previous automation step may have left the tree in inline-edit mode. |
| `cade_click_on_hwnd.ps1` | Brings a window to the foreground and simulates a left mouse click at coordinates relative to the window's top-left corner (`<hwnd> <relX> <relY>`). |
| `cade_restore_and_shot.ps1` | Restores a window if minimized, brings it to the foreground, then saves a `PrintWindow` screenshot to the given PNG path (`<hwnd> <outPng>`). |
| `cade_crop.ps1` | Crops a region from a source PNG (`<srcPng> <x> <y> <w> <h> <outPng>`) — useful for comparing a specific UI area across runs. |

## Usage notes

- Get the CATIA process PID from `cade run`'s JSON output (`pid` field) or
  `tasklist | grep -i CNEXT`.
- Run `.ps1` scripts with `powershell -File <script> <args...>` from a
  terminal (Git-Bash `sh` can invoke `powershell` directly).
- Run `.vbs` scripts with `cscript //nologo <script>`.
- CNEXT typically takes ~55-65s to fully load after `cade run` — wait
  before attaching/querying.
