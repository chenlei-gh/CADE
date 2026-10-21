"""
CATIA CAA Run Skill
===================
Purpose: Start CATIA Runtime View (CNEXT)
Usage: python run.py [options]
Output: JSON with runtime status
"""

import argparse
import glob
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# See build.py for why this is required: a bare `from env import ...` only
# works if skills/ happens to already be on sys.path (true for `python
# run.py` or via cade.py's own insert; not true for a direct python-binding
# import from an arbitrary cwd, e.g. capabilities.yaml python: run.start_catia_runtime).
sys.path.insert(0, str(Path(__file__).parent))

from env import CAAEnvironment
from utils import Cache, Logger, output_json

# Startup detection polling interval (seconds). The sleep and the elapsed-time
# accounting MUST use the same constant: they previously disagreed (0.5s sleep
# vs 0.2s accounting), so an actual 5s wait was logged as "2.0s".
POLL_INTERVAL = 0.5
POLL_MAX_ATTEMPTS = 30

# Grace period after taskkill before re-checking whether a PID really died.
PROCESS_EXIT_SETTLE = 0.5

# Age beyond which an unreferenced cade_run_*.bat is treated as an orphan.
# NOTE: this is NOT a "still launching?" window — the batch blocks on
# `call mkrun` for the whole CATIA session, so a live file can be hours old
# (observed >20 min). Safety comes from the in-use check, not this threshold;
# the age test only avoids paying for a WMIC query on freshly written files.
STALE_BAT_AGE_SECONDS = 3600


def _clean_cnext_sessions():
    """Remove CNEXT session files that trigger 'hot restart unavailable' prompt."""
    appdata = os.environ.get("LOCALAPPDATA", "")
    if not appdata:
        return
    temp_dir = Path(appdata) / "DassaultSystemes" / "CATTemp"
    if not temp_dir.exists():
        return
    # All files that trigger hot-restart or recovery prompts
    patterns = ["SessionInfoFile_*", "AbendTrace_*", "CNext*.roll", "error.log"]
    for pattern in patterns:
        for f in glob.glob(str(temp_dir / pattern)):
            try:
                os.remove(f)
            except OSError:
                pass


def _check_process_running_win32(process_name: str):
    """Fast Windows-native process enumeration via Toolhelp32Snapshot (sub-10ms)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        TH32CS_SNAPPROCESS = 0x00000002
        h_snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if h_snap == -1:
            return None

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_char * 260),
            ]

        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        target = process_name.lower()
        found = []
        success = kernel32.Process32First(h_snap, ctypes.byref(pe))
        while success:
            exe_name = pe.szExeFile.decode("latin1", errors="replace")
            if exe_name.lower() == target:
                found.append({"pid": int(pe.th32ProcessID), "name": exe_name})
            success = kernel32.Process32Next(h_snap, ctypes.byref(pe))
        kernel32.CloseHandle(h_snap)
        return found
    except Exception:
        return None


def check_process_running(process_name: str) -> list:
    """
    Check if a process is running using Windows native commands (P2-009 fix).

    Args:
        process_name: Process name (e.g., "CNEXT.exe") — validated for safety.

    Returns:
        List of dictionaries with process information
    """
    # Validate process_name: only allow alphanumeric + .exe (P2-009 fix)
    # Allow empty/missing to return empty list (graceful degradation)
    import re
    if not process_name or not process_name.strip():
        return []
    if not re.match(r'^[a-zA-Z0-9_.\-]+\.exe$', process_name):
        return []  # Invalid name → no matches found

    # Fast path: sub-10ms native snapshot on Windows (avoids 250ms+ tasklist subprocess)
    native_res = _check_process_running_win32(process_name)
    if native_res is not None:
        return native_res

    running_processes = []

    try:
        # Fallback to tasklist with /FI filter
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )

        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                if process_name.lower() in line.lower():
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            running_processes.append(
                                {"pid": int(parts[1]), "name": parts[0]}
                            )
                        except (ValueError, IndexError):
                            pass
    except Exception:
        pass

    return running_processes


def _pid_running(pid: int) -> bool:
    """Return True if a CNEXT.exe process with this exact PID is still alive.

    Scoped to the PID rather than the process name: stop_catia loops over
    several PIDs, and a name-only lookup cannot tell whether the specific
    process it just killed actually exited or a sibling is still running.
    """
    return any(p["pid"] == pid for p in check_process_running("CNEXT.exe"))


def _wait_pid_exit(pid: int, attempts: int = 6) -> bool:
    """Wait for a PID to disappear, returning True once it is confirmed gone.

    A force-killed process is not necessarily absent from tasklist on the very
    next query, so a single check would report a false failure for a process
    that is in fact shutting down. Polls with a bounded budget and reports the
    truth if the process is genuinely still alive after it expires.
    """
    for attempt in range(attempts):
        if not _pid_running(pid):
            return True
        if attempt < attempts - 1:
            time.sleep(PROCESS_EXIT_SETTLE)
    return not _pid_running(pid)


def _live_cmd_commandlines() -> str | None:
    """Return the concatenated command lines of all live cmd.exe processes.

    None means the query failed, i.e. in-use state is unknown and callers must
    not delete anything. Querying once and scanning the blob keeps orphan
    reclamation O(1) in subprocess calls instead of one WMIC spawn per file.
    """
    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='cmd.exe'", "get", "CommandLine"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        if result.returncode != 0:
            return None
        return (result.stdout or "").lower()
    except Exception:
        return None


def _reclaim_stale_run_bats(logger=None) -> int:
    """Delete aged, unreferenced cade_run_*.bat files left by killed hosts.

    Self-deletion in the batch body covers the normal and stop_catia paths;
    this only reclaims files whose host cmd.exe was killed before the script
    could finish. A file must clear BOTH the age threshold AND the absence of
    any live cmd.exe reference. The in-use check is what actually protects an
    in-flight launch (a batch parked on `call mkrun` stays alive for the whole
    CATIA session and can far exceed the age threshold); the age test merely
    skips freshly written files before spending a WMIC query on them.
    Bails out entirely when the process query fails (never delete on doubt),
    and swallows per-file errors so reclamation cannot break a launch.

    Residual race: a cmd.exe that picks up a candidate between the WMIC query
    and the unlink would have its file removed underneath it. Not closed, and
    accepted for a once-per-launch safety net.
    """
    candidates = [
        path
        for path in glob.glob(str(Path(tempfile.gettempdir()) / "cade_run_*.bat"))
        if time.time() - os.path.getmtime(path) >= STALE_BAT_AGE_SECONDS
    ]
    if not candidates:
        return 0

    live_cmdlines = _live_cmd_commandlines()
    if live_cmdlines is None:
        return 0

    reclaimed = 0
    for path in candidates:
        try:
            if Path(path).name.lower() in live_cmdlines:
                continue
            os.unlink(path)
            reclaimed += 1
        except OSError:
            pass
    if reclaimed and logger:
        logger.write(f"Reclaimed {reclaimed} stale cade_run_*.bat file(s)")
    return reclaimed


def _runtime_view_state(caa_env, workspace_path):
    """Return (mounted, warning). mounted is True only when <ws>/<arch> exists."""
    if not workspace_path:
        return False, None
    caa_env.load_config()
    arch = caa_env.get_architecture() or "win_b64"
    runtime_view = Path(workspace_path) / arch
    if runtime_view.exists():
        return True, None
    return False, (
        f"Runtime View directory not found: {runtime_view} — "
        "CATDLLPath/CATDictionaryPath/CATMsgCatalogPath will NOT include "
        "this workspace's DLLs. Run build.py first to generate the Runtime View."
    )


def _mkrun_payload_error(cnext_args):
    """Return an error message if cnext_args cannot survive `mkrun -c`.

    mkrun does not parse the -c value with CRT rules: it splits it on plain
    spaces before re-launching CNEXT. All three spellings of a path with a
    space were tried on B28 and all truncate at the first space
    (``Cannot open library C:\\temp\\space``): bare, nested quotes, and
    backslash-escaped quotes. That is an mkrun limitation, not something the
    caller can escape, so refuse instead of writing a launcher that is
    guaranteed to fail silently.
    """
    spaced = [a for a in (cnext_args or []) if " " in str(a)]
    if not spaced:
        return None
    return (
        "mkrun cannot pass an argument containing a space: "
        + ", ".join('"%s"' % str(a) for a in spaced)
        + ". mkrun splits the -c payload on spaces before relaunching CNEXT, "
        "so quoting and escaping are both lost and the path is truncated at "
        "the first space. Move the macro/parameter file to a path without "
        "spaces, or run without a workspace so CATSTART is used instead."
    )


def _mkrun_cmd(caa_env, workspace_path, cnext_args=None, detach=True):
    """Build the mkrun launcher used by every workspace launch.

    CATSTART cannot mount a workspace Runtime View. mkrun, after tck_init /
    tck_profile / mkinit, is the CAA development entry. cnext_args (for
    example -macro / -batch) are handed to CNEXT through `mkrun -c` and
    therefore reach it with the Runtime View paths already set.

    detach=True (interactive start) returns as soon as the window is up, so
    CATIA outlives the Python process. detach=False (macro/batch) runs the
    batch in the foreground so the exit code and timeout belong to CNEXT,
    not to `start`. Returns (cmd_args, batfile).

    Raises ValueError when cnext_args cannot be expressed through `mkrun -c`
    (see _mkrun_payload_error).
    """
    caa_env.load_config()
    catia_path = Path(caa_env.config.get("CATIA_INSTALL", ""))
    arch = caa_env.get_architecture() or "win_b64"
    tck_init = catia_path / arch / "code" / "command" / "tck_init.bat"
    tck_profile = catia_path / arch / "TCK" / "command" / "tck_profile.bat"
    mkinit = catia_path / arch / "code" / "command" / "mkinit.bat"
    code_bin = catia_path / arch / "code" / "bin"
    code_command = catia_path / arch / "code" / "command"
    rv = f"{workspace_path}\\{arch}"
    tck_id = caa_env.resolve_tck_id()
    tck_profile_line = (
        f'call "{tck_profile}" {tck_id} > NUL 2>&1\r\n'
        if tck_profile.exists() and tck_id
        else ""
    )
    # -macro / -batch are CNEXT switches, not mkrun switches. mkrun parses its
    # own argv and aborts on anything it does not know, so appending them after
    # `mkrun` yields "illegal option" and CNEXT never starts. The command to
    # launch is passed through -c, so they have to be spelled
    #   mkrun -c "CNEXT <switches>"
    # mkrun splits that payload on plain spaces, so an argument containing one
    # cannot be expressed at all — fail loudly rather than emit a broken script.
    if cnext_args:
        payload_error = _mkrun_payload_error(cnext_args)
        if payload_error:
            raise ValueError(payload_error)
        parts = [str(arg).replace('"', "") for arg in cnext_args]
        mkrun_tail = 'call mkrun -c "CNEXT ' + " ".join(parts) + '"'
    else:
        mkrun_tail = "call mkrun"
    bat_content = (
        "@echo off\r\n"
        f'call "{tck_init}" > NUL 2>&1\r\n'
        f"{tck_profile_line}"
        f'call "{mkinit}" > NUL 2>&1\r\n'
        f"set PATH={code_bin};{code_command};%PATH%\r\n"
        f"set CATDLLPath={rv}\\code\\bin;%CATDLLPath%\r\n"
        f"set CATDictionaryPath={rv}\\code\\dictionary;%CATDictionaryPath%\r\n"
        f"set CATMsgCatalogPath={rv}\\resources\\msgcatalog;%CATMsgCatalogPath%\r\n"
        f"set CATReffilesPath={rv}\\reffiles;%CATReffilesPath%\r\n"
        f"set CATGraphicPath={rv}\\resources\\graphic;%CATGraphicPath%\r\n"
        f'cd /d "{workspace_path}"\r\n'
        f"{mkrun_tail}\r\n"
        # Self-delete once the script is done. The interpreter exits long
        # before a detached batch does, so a finally-block unlink races the
        # file handle. `(goto)` aborts the interpreter and releases it.
        '(goto) 2>nul & del "%~f0"\r\n'
    )
    # newline="" prevents text-mode \n -> \r\n translation from doubling the
    # \r\n already embedded in bat_content.
    with tempfile.NamedTemporaryFile(
        suffix=".bat", prefix="cade_run_", delete=False,
        mode="w", encoding="ascii", newline="",
    ) as f:
        f.write(bat_content)
        batfile = f.name
    # List form, not a pre-joined string: a TEMP path with spaces must stay
    # one argument, and quoting it inside `start` makes `start` treat it as
    # the window title. See start_catia_runtime.
    if detach:
        return ["cmd", "/c", "start", "/min", "cmd", "/c", batfile], batfile
    return ["cmd", "/c", batfile], batfile


def _catstart_cmd(caa_env, env_name, extra_args):
    """Bare CATSTART launcher. Does not mount any workspace Runtime View."""
    catstart = caa_env.get_catstart_path()
    if not catstart or not catstart.exists():
        return None, None, {"status": "error", "message": "CATSTART.exe not found"}
    if not env_name:
        env_name = caa_env.get_default_env()
    env_dir = caa_env.get_catenv_dir()
    cmd = [
        str(catstart),
        "-run", "CNEXT.exe",
        "-env", env_name,
        "-direnv", env_dir,
    ]
    cmd.extend(extra_args)
    return cmd, os.environ.copy(), None


def start_catia_runtime(
    workspace_path: str = None,
    env_name: str = None,
    wait_for_exit: bool = False,
    timeout: int = 300,
    entrypoint: str = "python_cli",
    orchestrated_by_kernel: bool = False,
) -> dict:
    """
    Start CATIA Runtime View (CNEXT)

    Args:
        workspace_path: Path to workspace with Runtime View (optional)
        env_name: CATIA environment name (e.g., 'CATIA.P3.V5-6R2018.B28')
        wait_for_exit: Wait for CATIA to exit before returning
        timeout: Timeout in seconds for startup detection
        entrypoint: Invocation source ("python_cli" | "cade_cli" | "kernel")
        orchestrated_by_kernel: True iff invoked and controlled by Kernel

    Returns:
        Dictionary with runtime status
    """

    logger = Logger("runtime.log")
    cache = Cache("runtime.json")

    from utils import verify_kernel_orchestration
    verified_kernel, verified_ep, audit_warning = verify_kernel_orchestration(
        orchestrated_by_kernel=orchestrated_by_kernel,
        entrypoint=entrypoint,
    )
    orchestrated_by_kernel = verified_kernel
    entrypoint = verified_ep

    # Clear previous logs
    logger.clear()

    start_time = datetime.now()
    logger.write("Starting CATIA Runtime View")
    logger.write(f"Entrypoint: {entrypoint} | Orchestrated by Kernel: {orchestrated_by_kernel}")
    if audit_warning:
        logger.write(f"TELEMETRY_AUDIT: {audit_warning}")

    if workspace_path:
        ws = Path(workspace_path)
        if not ws.exists():
            error_msg = f"Workspace path does not exist: {workspace_path}"
            logger.write(error_msg, "ERROR")
            err_res = {
                "status": "error",
                "message": error_msg,
                "entrypoint": entrypoint,
                "orchestrated_by_kernel": orchestrated_by_kernel,
                "operation": "start_runtime",
                "stage": "runtime_start",
            }
            if audit_warning:
                err_res["telemetry_audit_warning"] = audit_warning
            return err_res
        logger.write(f"Workspace: {workspace_path}")

    # Initialize environment
    caa_env = CAAEnvironment()

    # CATSTART handles its own environment via -direnv and -env.
    # We must NOT override standard CATIA env vars - only inject Runtime View paths.
    # Start with clean system environment
    env_vars = os.environ.copy()

    # Only add Runtime View paths if workspace is provided
    runtime_view_mounted = False
    if workspace_path:
        caa_env.load_config()
        arch = caa_env.get_architecture()
        runtime_view = Path(workspace_path) / arch

        if runtime_view.exists():
                runtime_bin = runtime_view / "code" / "bin"
                existing = env_vars.get("CATDLLPath", "")
                env_vars["CATDLLPath"] = str(runtime_bin) + (os.pathsep + existing if existing else "")
                logger.write(f"CATDLLPath += {runtime_bin}")
                print(f"Using Runtime View: {runtime_view}", file=sys.stderr)
                runtime_view_mounted = True
        else:
            warn = (
                f"Runtime View directory not found: {runtime_view} — "
                f"CATDLLPath/CATDictionaryPath/... will NOT include this "
                f"workspace's DLLs even though mkrun is used. Run build.py "
                f"first to generate the Runtime View."
            )
            logger.write(warn, "WARNING")
            print(f"[WARNING] {warn}", file=sys.stderr)

    # Workspace -> mkrun (CAA dev entry, Runtime View mounted).
    # No workspace -> CATSTART. That is a bare session: status can still be
    # "started" while no custom CAA DLL is loaded. Do not treat that as the
    # prescribed entry for verifying workspace tools.
    if workspace_path:
        # Reclaim orphaned bats before creating ours so the new file is not
        # a candidate (it is also too young to qualify).
        _reclaim_stale_run_bats(logger)
        cmd_args, _batfile = _mkrun_cmd(caa_env, workspace_path)
        logger.write(f"Using mkrun (workspace): {workspace_path}")
    else:
        cmd_args, _launch_env, bare_err = _catstart_cmd(
            caa_env, env_name, ["-nowindow"]
        )
        if bare_err:
            logger.write(bare_err["message"], "ERROR")
            return bare_err
        logger.write(f"Using CATSTART: {cmd_args[0]}")
        logger.write(f"Environment: {cmd_args[4]}")
        warning_msg = (
            "No workspace provided — starting a BARE CATIA session. "
            "Runtime View (CATDLLPath/CATDictionaryPath/CATMsgCatalogPath) is "
            "NOT mounted, so custom CAA DLLs will NOT be loaded. "
            "If you need a workspace's CAA tools available, restart with: "
            "python run.py <workspace_path>"
        )
        logger.write(warning_msg, "WARNING")
        print(f"[WARNING] {warning_msg}", file=sys.stderr)

    # Check if CATIA is already running
    running_catia = check_process_running("CNEXT.exe")
    if running_catia:
        logger.write("CATIA is already running — stopping gracefully first")
        stop_catia(force=False)
        time.sleep(2)
        # Clean session files to prevent "热启动不可用" prompt
        _clean_cnext_sessions()

    # Start CATIA
    try:
        cmd_line = " ".join(f'"{a}"' if " " in a else a for a in cmd_args)
        logger.write(f"Launching: {cmd_line}")

        if wait_for_exit:
            # Start and wait for completion
            result = subprocess.run(
                cmd_args,
                env=env_vars,
                timeout=timeout,
                capture_output=True,
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.write(f"CATIA exited with code: {result.returncode}")
            logger.write(f"Duration: {duration:.1f}s")

            runtime_result = {
                "status": "exited",
                "message": f"CATIA exited with code {result.returncode}",
                "exit_code": result.returncode,
                "duration_seconds": duration,
                "timestamp": start_time.isoformat(),
                "runtime_view_mounted": runtime_view_mounted,
                "entrypoint": entrypoint,
                "orchestrated_by_kernel": orchestrated_by_kernel,
                "operation": "start_runtime",
                "stage": "runtime_start",
            }
        else:
            # Use Popen with CREATE_NO_WINDOW to suppress cmd popup.
            # DETACHED_PROCESS ensures CATIA survives Python exit.
            import subprocess as sp

            sp.Popen(
                cmd_args,
                env=env_vars,
                creationflags=sp.DETACHED_PROCESS,
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
            )

            # Quick poll (shorter intervals, return early if found)
            logger.write("Waiting for CNEXT...")
            runtime_result = None
            for i in range(POLL_MAX_ATTEMPTS):
                time.sleep(POLL_INTERVAL)
                running = check_process_running("CNEXT.exe")
                if running:
                    logger.write(
                        f"CNEXT detected after {(i + 1) * POLL_INTERVAL:.1f}s"
                    )
                    runtime_result = {
                        "status": "started",
                        "message": "CATIA started successfully",
                        "pid": running[0]["pid"],
                        "timestamp": start_time.isoformat(),
                        "runtime_view_mounted": runtime_view_mounted,
                        "entrypoint": entrypoint,
                        "orchestrated_by_kernel": orchestrated_by_kernel,
                        "operation": "start_runtime",
                        "stage": "runtime_start",
                    }
                    break

            if runtime_result is None:
                logger.write("CNEXT still initializing (continuing in background)")
                runtime_result = {
                    "status": "launching",
                    "message": "CATIA launch initiated (still initializing)",
                    "timestamp": start_time.isoformat(),
                    "runtime_view_mounted": runtime_view_mounted,
                    "entrypoint": entrypoint,
                    "orchestrated_by_kernel": orchestrated_by_kernel,
                    "operation": "start_runtime",
                    "stage": "runtime_start",
                }

        # P5.3 Envelope attachment (branch-driven, preserving raw fields)
        raw_snapshot = dict(runtime_result)
        cur_status = runtime_result.get("status")
        if cur_status == "exited":
            runtime_result["execution"] = {
                "status": "completed",
                "action_result": "exited",
                "raw": raw_snapshot,
            }
            runtime_result["verification"] = {
                "status": "not_run",
                "check": "none",
                "evidence": {
                    "reason": "launcher_exit_code_does_not_prove_cnext_lifecycle"
                },
            }
        elif cur_status == "started":
            runtime_result["execution"] = {
                "status": "completed",
                "action_result": "started",
                "raw": raw_snapshot,
            }
            runtime_result["verification"] = {
                "status": "observed",
                "check": "cnext_process_scan",
                "evidence": {
                    "target_image": "CNEXT.exe",
                    "observed_process": "CNEXT.exe",
                    "pid": runtime_result.get("pid"),
                    "match_found": True,
                    "instance_scope": "global_image_name_snapshot_only",
                },
            }
        elif cur_status == "launching":
            runtime_result["execution"] = {
                "status": "completed",
                "action_result": "launching",
                "raw": raw_snapshot,
            }
            runtime_result["verification"] = {
                "status": "not_run",
                "check": "catia_start_pending",
                "evidence": {
                    "reason": "launch_initiated_polling_window_expired",
                    "v1_classification": "not_specified_in_v1",
                },
            }
        else:
            runtime_result["execution"] = {
                "status": "completed",
                "action_result": cur_status,
                "raw": raw_snapshot,
            }
            runtime_result["verification"] = {
                "status": "not_run",
                "check": "none",
                "evidence": {"reason": f"unhandled_status_{cur_status}"},
            }

        if audit_warning:
            runtime_result["telemetry_audit_warning"] = audit_warning

        # Save to cache
        cache.save(runtime_result)

        return runtime_result

    except subprocess.TimeoutExpired:
        error_msg = f"CATIA startup timeout after {timeout} seconds"
        logger.write(error_msg, "ERROR")
        res = {
            "status": "timeout",
            "message": error_msg,
            "timeout_seconds": timeout,
            "entrypoint": entrypoint,
            "orchestrated_by_kernel": orchestrated_by_kernel,
            "operation": "start_runtime",
            "stage": "runtime_start",
        }
        if audit_warning:
            res["telemetry_audit_warning"] = audit_warning
        raw_snapshot = dict(res)
        res["execution"] = {
            "status": "timeout",
            "action_result": "timeout",
            "raw": raw_snapshot,
        }
        res["verification"] = {
            "status": "not_run",
            "check": "none",
            "evidence": {"reason": "startup_timeout"},
        }
        return res

    except Exception as e:
        error_msg = f"Runtime exception: {str(e)}"
        logger.write(error_msg, "ERROR")
        res = {
            "status": "error",
            "message": error_msg,
            "exception": str(e),
            "entrypoint": entrypoint,
            "orchestrated_by_kernel": orchestrated_by_kernel,
            "operation": "start_runtime",
            "stage": "runtime_start",
        }
        if audit_warning:
            res["telemetry_audit_warning"] = audit_warning
        raw_snapshot = dict(res)
        res["execution"] = {
            "status": "error",
            "action_result": "error",
            "raw": raw_snapshot,
        }
        res["verification"] = {
            "status": "not_run",
            "check": "none",
            "evidence": {"reason": "startup_exception"},
        }
        return res


def stop_catia(
    force: bool = False,
    entrypoint: str = "python_cli",
    orchestrated_by_kernel: bool = False,
) -> dict:
    """
    Stop all running CATIA processes.

    Tries graceful shutdown first (taskkill without /F),
    falls back to force if timeout.

    Args:
        force: Skip graceful, force-kill immediately
        entrypoint: Invocation source ("python_cli" | "cade_cli" | "kernel")
        orchestrated_by_kernel: True iff invoked and controlled by Kernel

    Returns:
        Dictionary with stop result
    """
    from utils import verify_kernel_orchestration
    verified_kernel, verified_ep, audit_warning = verify_kernel_orchestration(
        orchestrated_by_kernel=orchestrated_by_kernel,
        entrypoint=entrypoint,
    )
    orchestrated_by_kernel = verified_kernel
    entrypoint = verified_ep

    running = check_process_running("CNEXT.exe")
    if not running:
        not_running_res = {
            "status": "not_running",
            "message": "CATIA is not running",
            "entrypoint": entrypoint,
            "orchestrated_by_kernel": orchestrated_by_kernel,
            "operation": "stop_runtime",
            "stage": "runtime_stop",
        }
        if audit_warning:
            not_running_res["telemetry_audit_warning"] = audit_warning
        not_running_res["execution"] = {
            "status": "completed",
            "action_result": "not_running",
            "raw": dict(not_running_res),
        }
        not_running_res["verification"] = {
            "status": "observed",
            "check": "cnext_process_scan",
            "evidence": {
                "target_image": "CNEXT.exe",
                "match_found": False,
                "instance_scope": "single_query_snapshot_only",
            },
        }
        return not_running_res

    pids = [p["pid"] for p in running]
    stopped = []
    failed = []

    for pid in pids:
        try:
            if not force:
                # Graceful shutdown first
                subprocess.run(
                    ["taskkill", "/PID", str(pid)],
                    capture_output=True,
                    timeout=15,
                )
                time.sleep(5)  # CNEXT needs time to flush state files
                # Check if still running
                if _pid_running(pid):
                    # Force kill
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        capture_output=True,
                        timeout=10,
                    )
                    time.sleep(PROCESS_EXIT_SETTLE)
            else:
                # Force kill immediately
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                    timeout=10,
                )
                time.sleep(PROCESS_EXIT_SETTLE)
        except Exception:
            # Last resort: force kill
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                    timeout=10,
                )
                time.sleep(PROCESS_EXIT_SETTLE)
            except Exception:
                pass

        # taskkill reports failure through its exit code and never raises, so
        # a bare `stopped.append(pid)` used to claim success for processes
        # that were still alive. Confirm against the live process list instead.
        if _wait_pid_exit(pid):
            stopped.append(pid)
        else:
            failed.append(pid)

    method = "force" if force else "graceful+force"
    if failed and not stopped:
        status = "failed"
    elif failed:
        status = "partial"
    else:
        status = "stopped"
    message = f"Stopped {len(stopped)} process(es) [{method}]"
    if failed:
        message += f" — {len(failed)} still running (pid={failed})"
    res = {
        "status": status,
        "message": message,
        "stopped": stopped,
        "failed": failed,
        "entrypoint": entrypoint,
        "orchestrated_by_kernel": orchestrated_by_kernel,
        "operation": "stop_runtime",
        "stage": "runtime_stop",
    }
    if audit_warning:
        res["telemetry_audit_warning"] = audit_warning
    raw_snapshot = dict(res)
    res["execution"] = {
        "status": "completed",
        "action_result": status,
        "raw": raw_snapshot,
    }
    res["verification"] = {
        "status": "observed",
        "check": "cnext_process_scan",
        "evidence": {
            "target_image": "CNEXT.exe",
            "stopped_pids": stopped,
            "failed_pids": failed,
            "instance_scope": "post_stop_process_scan",
        },
    }
    return res


def check_catia_running() -> dict:
    """
    Check if CATIA is currently running

    Returns:
        Dictionary with status information
    """
    running_processes = check_process_running("CNEXT.exe")

    if running_processes:
        return {
            "status": "running",
            "message": f"Found {len(running_processes)} CATIA process(es)",
            "processes": running_processes,
        }
    else:
        return {"status": "not_running", "message": "CATIA is not running"}


# ─── Named Run Functions (AI-Friendly) ────────────────────────────


def run_catia_macro(
    macro_path: str,
    env_name: str = None,
    timeout: int = 300,
    workspace_path: str = None,
) -> dict:
    """
    Run a CATScript macro in CATIA (CNEXT -macro).

    A workspace uses the same mkrun launcher as start_catia_runtime, so
    CATDLLPath/CATDictionaryPath/CATMsgCatalogPath come from the Runtime
    View. CATSTART is only the no-workspace fallback and does not load
    custom CAA DLLs.

    Args:
        macro_path: Path to .CATScript file
        env_name: CATIA environment name (bare CATSTART fallback only)
        timeout: Timeout in seconds
        workspace_path: Workspace whose Runtime View must be visible

    Returns:
        Dictionary with execution result
    """
    mp = Path(macro_path)
    if not mp.exists():
        return {"status": "error", "message": f"Macro file not found: {macro_path}"}

    caa_env = CAAEnvironment()
    mounted, missing = _runtime_view_state(caa_env, workspace_path)
    if missing:
        print(f"[WARNING] {missing}", file=sys.stderr)

    try:
        if workspace_path:
            macro_args = ["-macro", str(mp)]
            payload_error = _mkrun_payload_error(macro_args)
            if payload_error:
                return {"status": "error", "message": payload_error,
                        "macro": str(macro_path), "launcher": "mkrun"}
            cmd_args, _bat = _mkrun_cmd(
                caa_env, workspace_path, macro_args, detach=False
            )
            launch_env = None
        else:
            cmd_args, launch_env, bare_err = _catstart_cmd(
                caa_env, env_name, ["-nowindow", "-macro", str(mp)]
            )
            if bare_err:
                return bare_err
            print(
                "[WARNING] No workspace provided — macro runs in a BARE "
                "CATIA session. Custom CAA DLLs will NOT be loaded.",
                file=sys.stderr,
            )

        result = subprocess.run(
            cmd_args,
            capture_output=True,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=launch_env,
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "message": f"Macro execution completed (exit {result.returncode})",
            "macro": str(macro_path),
            "exit_code": result.returncode,
            "runtime_view_mounted": mounted,
            "launcher": "mkrun" if workspace_path else "CATSTART",
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "message": f"Macro timed out after {timeout}s"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def run_catia_batch(
    batch_script: str = None,
    env_name: str = None,
    timeout: int = 600,
    workspace_path: str = None,
) -> dict:
    """
    Run CATIA in batch mode (CNEXT -batch).

    Same launcher split as run_catia_macro: workspace -> mkrun with the
    Runtime View mounted; no workspace -> bare CATSTART, no custom DLLs.

    Args:
        batch_script: Optional batch script path
        env_name: CATIA environment name (bare CATSTART fallback only)
        timeout: Timeout in seconds
        workspace_path: Workspace whose Runtime View must be visible

    Returns:
        Dictionary with execution result
    """
    caa_env = CAAEnvironment()
    mounted, missing = _runtime_view_state(caa_env, workspace_path)
    if missing:
        print(f"[WARNING] {missing}", file=sys.stderr)

    extra = ["-batch"]
    if batch_script:
        extra.extend(["-macro", batch_script])

    try:
        if workspace_path:
            payload_error = _mkrun_payload_error(extra)
            if payload_error:
                return {"status": "error", "message": payload_error,
                        "launcher": "mkrun"}
            cmd_args, _bat = _mkrun_cmd(
                caa_env, workspace_path, extra, detach=False
            )
            launch_env = None
        else:
            cmd_args, launch_env, bare_err = _catstart_cmd(
                caa_env, env_name, extra
            )
            if bare_err:
                return bare_err
            print(
                "[WARNING] No workspace provided — batch runs in a BARE "
                "CATIA session. Custom CAA DLLs will NOT be loaded.",
                file=sys.stderr,
            )

        result = subprocess.run(
            cmd_args,
            capture_output=True,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=launch_env,
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "message": f"Batch execution completed (exit {result.returncode})",
            "exit_code": result.returncode,
            "runtime_view_mounted": mounted,
            "launcher": "mkrun" if workspace_path else "CATSTART",
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "message": f"Batch timed out after {timeout}s"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def run_catia_with_env(
    env_name: str, workspace_path: str = None, timeout: int = 60
) -> dict:
    """Start CATIA with a specific environment (CNEXT -env)"""
    return start_catia_runtime(
        workspace_path=workspace_path, env_name=env_name, timeout=timeout
    )


def _pe_exports(dll_path: Path):
    """Return the export names of a PE DLL, or _pe_exports on failure.

    Pure stdlib (struct only) — the project ships no dependencies and the
    task is a read-only header walk, so a ctypes/PyWin32 binding would add
    risk without adding information.
    """
    try:
        data = Path(dll_path).read_bytes()
        if len(data) < 0x40 or data[:2] != b"MZ":
            return None
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
        if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            return None
        coff = e_lfanew + 4
        n_sections = struct.unpack_from("<H", data, coff + 2)[0]
        opt_size = struct.unpack_from("<H", data, coff + 16)[0]
        opt = coff + 20
        magic = struct.unpack_from("<H", data, opt)[0]
        if magic == 0x20B:      # PE32+
            dd_off = opt + 112
        elif magic == 0x10B:    # PE32
            dd_off = opt + 96
        else:
            return None
        export_rva, export_size = struct.unpack_from("<II", data, dd_off)
        if not export_rva or not export_size:
            return []
        sec_off = opt + opt_size
        sections = []
        for i in range(n_sections):
            base = sec_off + i * 40
            vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, base + 8)
            sections.append((vaddr, max(vsize, rsize), raddr))

        def rva_to_off(rva):
            for vaddr, span, raddr in sections:
                if vaddr <= rva < vaddr + span:
                    return raddr + (rva - vaddr)
            return None

        hdr = rva_to_off(export_rva)
        if hdr is None or hdr + 40 > len(data):
            return None
        n_names = struct.unpack_from("<I", data, hdr + 24)[0]
        names_rva = struct.unpack_from("<I", data, hdr + 32)[0]
        names_off = rva_to_off(names_rva)
        if names_off is None:
            return None
        out = []
        for i in range(min(n_names, 4096)):
            str_rva = struct.unpack_from("<I", data, names_off + i * 4)[0]
            s_off = rva_to_off(str_rva)
            if s_off is None:
                continue
            end = data.find(b"\0", s_off)
            if end < 0:
                continue
            out.append(data[s_off:end].decode("ascii", "replace"))
        return out
    except (OSError, struct.error, ValueError):
        return None


def _batch_search_dirs(caa_env, workspace_path):
    """Directories CATBatch scans for a batch descriptor, highest priority first.

    CATBatch resolves a parameter file's `batch_name` against every
    `batchdesc/` directory reachable from BATCH_PATH (string evidence in
    CATBatchUtils.dll), falling back to the CATIA install's own resources.
    The Runtime View must come first so a workspace descriptor shadows an
    official one of the same name.
    """
    dirs = []
    arch = caa_env.get_architecture() or "win_b64"
    if workspace_path:
        rv = Path(workspace_path) / arch / "resources" / "batchdesc"
        dirs.append(rv)
    catia_path = Path(caa_env.config.get("CATIA_INSTALL", "") or "")
    if str(catia_path) not in ("", "."):
        dirs.append(catia_path / arch / "resources" / "batchdesc")
    return dirs


def _read_batch_param(param_file: Path):
    """Extract batch_name + declared input files from a CATBatch parameter XML."""
    import xml.etree.ElementTree as ET

    info = {"batch_name": None, "inputs": [], "outputs": []}
    try:
        root = ET.parse(str(param_file)).getroot()
    except (ET.ParseError, OSError) as e:
        return info, f"parameter file is not well-formed XML: {e}"
    info["batch_name"] = root.get("batch_name")
    for tag, key in (("inputParameters", "inputs"), ("outputParameters", "outputs")):
        for section in root.findall(tag):
            for node in section:
                path = node.get("filePath") or node.get("folderPath")
                if path:
                    info[key].append(path)
    return info, None


def run_caa_batch(
    param_file: str,
    workspace_path: str = None,
    timeout: int = 900,
    dry_run: bool = False,
) -> dict:
    """Run a compiled CAA batch through CATBatch.exe (descriptor-driven).

    This is NOT the same mechanism as run_catia_batch: that one runs a
    *script* through `CNEXT -batch -macro` and needs a CATMain entry point.
    CATBatch loads a *library* and calls its `batchmain` export, resolving
    the library from a descriptor named by the parameter file's batch_name.

    Preflight is the point of this function. CATBatch's own failure mode is
    an AFWIN modal dialog plus a non-zero exit code with no stdout, so every
    check that can be done statically is done before the process starts:
    descriptor found, referenced DLL present, DLL exports `batchmain`, and
    declared input files exist.
    """
    caa_env = CAAEnvironment()
    caa_env.load_config()

    pf = Path(param_file)
    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        return ok

    if not add("parameter_file_exists", pf.is_file(), str(pf)):
        return {"status": "error", "message": f"Parameter file not found: {pf}",
                "checks": checks}

    info, parse_err = _read_batch_param(pf)
    if not add("parameter_file_parses", parse_err is None, parse_err or str(pf)):
        return {"status": "error", "message": parse_err, "checks": checks}

    batch_name = info.get("batch_name")
    if not add("batch_name_present", bool(batch_name),
               f"batch_name={batch_name!r}"):
        return {"status": "error",
                "message": "parameter file has no batch_name attribute",
                "checks": checks}

    # Descriptor resolution — the exact place the BatchSample collision happened:
    # a wrong batch_name silently matched an official descriptor and reported
    # "Entry point <batchmain> not found" for a DLL the author never wrote.
    search_dirs = _batch_search_dirs(caa_env, workspace_path)
    descriptor = None
    searched = []
    for d in search_dirs:
        candidate = d / f"{batch_name}.xml"
        searched.append(str(candidate))
        if candidate.is_file():
            descriptor = candidate
            break
    if not add("descriptor_found", descriptor is not None,
               f"batch_name={batch_name!r} searched={searched}"):
        return {"status": "error",
                "message": (f"No batch descriptor named '{batch_name}.xml'. "
                            f"CATBatch would fall back to an official "
                            f"descriptor of the same name and report a "
                            f"misleading 'batchmain not found'."),
                "checks": checks, "searched": searched}

    import xml.etree.ElementTree as ET
    try:
        descriptor_root = ET.parse(str(descriptor)).getroot()
    except (ET.ParseError, OSError) as e:
        add("descriptor_parses", False, f"{descriptor}: {e}")
        return {"status": "error", "message": f"Descriptor is not well-formed XML: {e}",
                "checks": checks}
    add("descriptor_parses", True, str(descriptor))

    commandline = (descriptor_root.get("commandline") or "").strip()
    tokens = commandline.split()
    library = tokens[1] if len(tokens) >= 2 else None
    if not add("descriptor_has_commandline", bool(library),
               f"commandline={commandline!r}"):
        return {"status": "error",
                "message": "descriptor commandline must be 'CATBatch <Library>'",
                "checks": checks}

    # Locate the library on CATDLLPath (Runtime View first, then the install).
    arch = caa_env.get_architecture() or "win_b64"
    dll_dirs = []
    if workspace_path:
        dll_dirs.append(Path(workspace_path) / arch / "code" / "bin")
    catia_path = Path(caa_env.config.get("CATIA_INSTALL", "") or "")
    if str(catia_path) not in ("", "."):
        dll_dirs.append(catia_path / arch / "code" / "bin")
    dll_path = None
    for d in dll_dirs:
        candidate = d / f"{library}.dll"
        if candidate.is_file():
            dll_path = candidate
            break
    if not add("library_found", dll_path is not None,
               f"{library}.dll searched={[str(d) for d in dll_dirs]}"):
        return {"status": "error",
                "message": (f"Descriptor '{batch_name}' points at "
                            f"'{library}.dll', which is not on CATDLLPath. "
                            f"Build the module first."),
                "checks": checks}

    exports = _pe_exports(dll_path)
    if exports is None:
        add("exports_batchmain", None, "could not parse PE export table")
    else:
        if not add("exports_batchmain", "batchmain" in exports,
                   f"{dll_path.name} exports={sorted(exports)}"):
            return {"status": "error",
                    "message": (f"{dll_path.name} does not export 'batchmain'. "
                                f"A CATBatch library is entered through "
                                f"batchmain, not CATMain."),
                    "checks": checks}

    missing_inputs = [p for p in info["inputs"] if not Path(p).exists()]
    add("input_files_exist", not missing_inputs,
        f"missing={missing_inputs}" if missing_inputs else f"{len(info['inputs'])} ok")

    result = {
        "status": "dry_run" if dry_run else "pending",
        "param_file": str(pf),
        "batch_name": batch_name,
        "descriptor": str(descriptor),
        "library": library,
        "dll": str(dll_path) if dll_path else None,
        "checks": checks,
        "preflight_ok": all(c["ok"] is not False for c in checks),
    }

    if missing_inputs or result["preflight_ok"] is False or dry_run:
        if dry_run:
            result["status"] = "dry_run"
            result["message"] = "Preflight completed; CATBatch not started."
        else:
            result["status"] = "error"
            result["message"] = "Preflight failed; CATBatch not started."
        return result

    catbatch = catia_path / arch / "code" / "bin" / "CATBatch.exe"
    if not catbatch.is_file():
        result["status"] = "error"
        result["message"] = f"CATBatch.exe not found: {catbatch}"
        return result

    # CATIA writes its run log to %TEMP%/<32-hex>/. Snapshot the directory set
    # so the log for THIS run can be identified instead of guessing by mtime.
    temp_root = Path(tempfile.gettempdir())
    before = {p.name for p in temp_root.iterdir() if p.is_dir()} if temp_root.is_dir() else set()

    launch_env = caa_env.initialize(workspace_path=workspace_path) or os.environ.copy()
    if workspace_path:
        rv = Path(workspace_path) / arch
        launch_env["BATCH_PATH"] = str(rv)

    try:
        proc = subprocess.run(
            [str(catbatch), str(pf)],
            capture_output=True, timeout=timeout, text=True,
            encoding="utf-8", errors="replace", env=launch_env,
            cwd=str(workspace_path) if workspace_path else None,
        )
    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
        result["message"] = f"CATBatch timed out after {timeout}s"
        return result
    except OSError as e:
        result["status"] = "error"
        result["message"] = f"Failed to launch CATBatch: {e}"
        return result

    after = {p.name for p in temp_root.iterdir() if p.is_dir()} if temp_root.is_dir() else set()
    log_dirs = sorted(after - before)
    result["exit_code"] = proc.returncode
    result["log_dirs"] = [str(temp_root / d) for d in log_dirs]
    result["stdout"] = (proc.stdout or "").strip()[-2000:]
    result["stderr"] = (proc.stderr or "").strip()[-2000:]

    # The new-dir diff above only works when CATBatch writes under %TEMP%. It
    # usually writes to C:\temp instead, which is a DIFFERENT directory than
    # tempfile.gettempdir() on a machine with TMP=/tmp, so the diff comes back
    # empty. CATBatch always names the real location, as "located in <path>" —
    # on stderr when it dies before batchmain, on stdout once a batch runs — so
    # search both and keep the diff as a last resort.
    located = re.search(r"located in <(.+?)>",
                        result["stderr"] + "\n" + result["stdout"])
    if located:
        reported = located.group(1).replace("\\\\", "\\").strip()
        if reported and reported.lower() != "(null)":
            result["log_dirs"] = [reported]

    result["status"] = "success" if proc.returncode == 0 else "failed"
    if proc.returncode != 0 and not result["stdout"] and not result["stderr"]:
        result["message"] = (
            f"CATBatch exited {proc.returncode} with no console output. "
            f"This is the AFWIN signature — read the log under "
            f"{result['log_dirs'] or '%TEMP%/<uuid>/'} for the real cause."
        )
    else:
        result["message"] = f"CATBatch completed (exit {proc.returncode})"
    return result


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Start CATIA Runtime View",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
Examples:
  python run.py D:\workspace                 # Mount Runtime View via mkrun (required)
  python run.py D:\workspace --wait          # Mount, start, and wait for exit
  python run.py --env CATIA.P3.V5-6R2018.B28 D:\workspace
  python run.py --check                      # Check if running (does not start)
  python run.py --stop                       # Stop CATIA (does not start)
  python run.py --dev D:\workspace           # Build + mount Runtime View + start

workspace is a positional argument, not --workspace. Omitting it falls back to
bare CATSTART.exe: CATIA starts, but custom CAA DLLs are not loaded.
Check runtime_view_mounted. status=started does not mean the workspace is mounted.
Do not launch CATSTART.exe or CNEXT.exe from the CATIA install directory.
        """,
    )

    parser.add_argument(
        "workspace",
        nargs="?",
        default=None,
        help="Workspace path. Required to mount Runtime View; omit only for a bare session",
    )

    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help="CATIA environment name (e.g., CATIA.P3.V5-6R2018.B28)",
    )

    parser.add_argument(
        "--wait", action="store_true", help="Wait for CATIA to exit before returning"
    )

    parser.add_argument(
        "--check", action="store_true", help="Check if CATIA is running (do not start)"
    )

    parser.add_argument(
        "--stop", action="store_true", help="Stop all running CATIA processes"
    )

    parser.add_argument(
        "--dev", action="store_true", help="Build then run (shortcut for build+run cycle)"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Startup timeout in seconds (default: 300)",
    )

    args = parser.parse_args()

    # Check mode
    if args.check:
        result = check_catia_running()
        output_json(result, exit_code=0)
        return

    # Stop mode
    if args.stop:
        result = stop_catia(entrypoint="python_cli", orchestrated_by_kernel=False)
        output_json(
            result, exit_code=0 if result["status"] in ["stopped", "not_running"] else 1
        )
        return

    # Dev mode: build then run
    if args.dev and args.workspace:
        from build import build_workspace
        from pathlib import Path as _Path
        print("Building...", file=sys.stderr)
        build_result = build_workspace(
            _Path(args.workspace),
            entrypoint="python_cli",
            orchestrated_by_kernel=False,
        )
        if build_result.get("status") != "success":
            output_json(build_result, exit_code=1)
            return
        print("Build OK, launching...", file=sys.stderr)

    # Start CATIA
    result = start_catia_runtime(
        workspace_path=args.workspace,
        env_name=args.env,
        wait_for_exit=args.wait,
        timeout=args.timeout,
        entrypoint="python_cli",
        orchestrated_by_kernel=False,
    )

    # Output JSON
    exit_code = 0 if result["status"] in ["started", "exited", "already_running"] else 1
    output_json(result, exit_code=exit_code)


# Alias for backward compatibility
start_catia = start_catia_runtime


if __name__ == "__main__":
    main()
