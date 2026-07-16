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
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from env import CAAEnvironment
from utils import Cache, Logger, output_json


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


def check_process_running(process_name: str) -> list:
    """
    Check if a process is running using Windows native commands

    Args:
        process_name: Process name (e.g., "CNEXT.exe")

    Returns:
        List of dictionaries with process information
    """
    running_processes = []

    try:
        # Use pipe approach (more reliable than /FI on Chinese Windows)
        result = subprocess.run(
            ["cmd", "/c", f"tasklist | findstr {process_name}"],
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


def start_catia_runtime(
    workspace_path: str = None,
    env_name: str = None,
    wait_for_exit: bool = False,
    timeout: int = 300,
) -> dict:
    """
    Start CATIA Runtime View (CNEXT)

    Args:
        workspace_path: Path to workspace with Runtime View (optional)
        env_name: CATIA environment name (e.g., 'CATIA.P3.V5-6R2018.B28')
        wait_for_exit: Wait for CATIA to exit before returning
        timeout: Timeout in seconds for startup detection

    Returns:
        Dictionary with runtime status
    """

    logger = Logger("runtime.log")
    cache = Cache("runtime.json")

    # Clear previous logs
    logger.clear()

    start_time = datetime.now()
    logger.write("Starting CATIA Runtime View")

    if workspace_path:
        ws = Path(workspace_path)
        if not ws.exists():
            error_msg = f"Workspace path does not exist: {workspace_path}"
            logger.write(error_msg, "ERROR")
            return {"status": "error", "message": error_msg}
        logger.write(f"Workspace: {workspace_path}")

    # Initialize environment
    caa_env = CAAEnvironment()

    # CATSTART handles its own environment via -direnv and -env.
    # We must NOT override standard CATIA env vars - only inject Runtime View paths.
    # Start with clean system environment
    env_vars = os.environ.copy()

    # Only add Runtime View paths if workspace is provided
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

    # Get CATSTART path (use CATSTART with proper parameters)
    catstart_path = caa_env.get_catstart_path()
    if not catstart_path or not catstart_path.exists():
        error_msg = f"CATSTART.exe not found"
        logger.write(error_msg, "ERROR")
        return {"status": "error", "message": error_msg}

    executable_path = catstart_path
    logger.write(f"Using CATSTART: {catstart_path}")

    # Build command with proper parameters.
    # When workspace is provided, use mkrun (standard CAA dev workflow)
    # instead of CATSTART, because mkrun properly initializes Runtime View paths.
    if workspace_path:
        import tempfile
        catia_path = Path(caa_env.config.get("CATIA_INSTALL", ""))
        arch = caa_env.get_architecture() or "win_b64"
        tck_init = catia_path / arch / "code" / "command" / "tck_init.bat"
        tck_profile = catia_path / arch / "TCK" / "command" / "tck_profile.bat"
        mkinit = catia_path / arch / "code" / "command" / "mkinit.bat"
        code_bin = catia_path / arch / "code" / "bin"
        code_command = catia_path / arch / "code" / "command"

        batfile = Path(tempfile.mktemp(suffix=".bat", prefix="cade_run_"))
        batfile.write_text(
            "@echo off\r\n"
            f'call "{tck_init}" > NUL 2>&1\r\n'
            f'call "{tck_profile}" > NUL 2>&1\r\n'
            f'call "{mkinit}" > NUL 2>&1\r\n'
            f"set PATH={code_bin};{code_command};%PATH%\r\n"
            # Add workspace graphic path so CNEXT finds icons
            f"set CATGraphicPath={workspace_path}\\{arch}\\resources\\graphic;%CATGraphicPath%\r\n"
            f'cd /d "{workspace_path}"\r\n'
            f"call mkrun\r\n",
            encoding="ascii",
        )
        cmd_args = ["cmd", "/c", f"start /min cmd /c {batfile}"]
        logger.write(f"Using mkrun (workspace): {workspace_path}")
    else:
        # No workspace — use CATSTART for a plain CATIA launch
        if not env_name:
            env_name = caa_env.get_default_env()
        env_dir = caa_env.get_catenv_dir()
        cmd_args = [
            str(catstart_path),
            "-run", "CNEXT.exe",
            "-env", env_name,
            "-direnv", env_dir,
            "-nowindow",
        ]
        logger.write(f"Using CATSTART: {catstart_path}")
        logger.write(f"Environment: {env_name}")

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
            for i in range(30):
                time.sleep(0.5)
                running = check_process_running("CNEXT.exe")
                if running:
                    logger.write(f"CNEXT detected after {(i + 1) * 0.2:.1f}s")
                    runtime_result = {
                        "status": "started",
                        "message": "CATIA started successfully",
                        "pid": running[0]["pid"],
                        "timestamp": start_time.isoformat(),
                    }
                    break

            if runtime_result is None:
                logger.write("CNEXT still initializing (continuing in background)")
                runtime_result = {
                    "status": "launching",
                    "message": "CATIA launch initiated (still initializing)",
                    "timestamp": start_time.isoformat(),
                }

        # Save to cache
        cache.save(runtime_result)

        return runtime_result

    except subprocess.TimeoutExpired:
        error_msg = f"CATIA startup timeout after {timeout} seconds"
        logger.write(error_msg, "ERROR")
        return {"status": "timeout", "message": error_msg, "timeout_seconds": timeout}

    except Exception as e:
        error_msg = f"Runtime exception: {str(e)}"
        logger.write(error_msg, "ERROR")
        return {"status": "error", "message": error_msg, "exception": str(e)}


def stop_catia(force: bool = False) -> dict:
    """
    Stop all running CATIA processes.

    Tries graceful shutdown first (taskkill without /F),
    falls back to force if timeout.

    Args:
        force: Skip graceful, force-kill immediately

    Returns:
        Dictionary with stop result
    """
    running = check_process_running("CNEXT.exe")
    if not running:
        return {"status": "not_running", "message": "CATIA is not running"}

    pids = [p["pid"] for p in running]
    stopped = []
    failed = []

    for pid in pids:
        try:
            if not force:
                # Graceful shutdown first
                result = subprocess.run(
                    ["taskkill", "/PID", str(pid)],
                    capture_output=True,
                    timeout=15,
                )
                time.sleep(5)  # CNEXT needs time to flush state files
                # Check if still running
                still_running = check_process_running("CNEXT.exe")
                if any(p["pid"] == pid for p in still_running):
                    # Force kill
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        capture_output=True,
                        timeout=10,
                    )
            else:
                # Force kill immediately
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                    timeout=10,
                )
            stopped.append(pid)
        except Exception:
            # Last resort: force kill
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                    timeout=10,
                )
                stopped.append(pid)
            except Exception:
                failed.append(pid)

    method = "force" if force else "graceful+force"
    return {
        "status": "stopped" if not failed else "partial",
        "message": f"Stopped {len(stopped)} process(es) [{method}]",
        "stopped": stopped,
        "failed": failed,
    }


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


def run_catia_macro(macro_path: str, env_name: str = None, timeout: int = 300) -> dict:
    """
    Run a CATScript macro in CATIA (CNEXT -macro)

    Args:
        macro_path: Path to .CATScript file
        env_name: CATIA environment name
        timeout: Timeout in seconds

    Returns:
        Dictionary with execution result
    """
    # Validate macro file exists
    mp = Path(macro_path)
    if not mp.exists():
        return {"status": "error", "message": f"Macro file not found: {macro_path}"}

    caa_env = CAAEnvironment()
    if not env_name:
        env_name = caa_env.get_default_env()
    env_dir = caa_env.get_catenv_dir()

    catstart = caa_env.get_catstart_path()
    if not catstart or not catstart.exists():
        return {"status": "error", "message": "CATSTART.exe not found"}

    cmd_args = [
        str(catstart),
        "-run",
        "CNEXT.exe",
        "-env",
        env_name,
        "-direnv",
        env_dir,
        "-nowindow",
        "-macro",
        str(macro_path),
    ]

    try:
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "message": f"Macro execution completed (exit {result.returncode})",
            "macro": str(macro_path),
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "message": f"Macro timed out after {timeout}s"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def run_catia_batch(
    batch_script: str = None, env_name: str = None, timeout: int = 600
) -> dict:
    """
    Run CATIA in batch mode (CNEXT -batch)

    Args:
        batch_script: Optional batch script path
        env_name: CATIA environment name
        timeout: Timeout in seconds

    Returns:
        Dictionary with execution result
    """
    caa_env = CAAEnvironment()
    if not env_name:
        env_name = caa_env.get_default_env()
    env_dir = caa_env.get_catenv_dir()

    catstart = caa_env.get_catstart_path()
    if not catstart or not catstart.exists():
        return {"status": "error", "message": "CATSTART.exe not found"}

    cmd_args = [
        str(catstart),
        "-run",
        "CNEXT.exe",
        "-env",
        env_name,
        "-direnv",
        env_dir,
        "-batch",
    ]
    if batch_script:
        cmd_args.extend(["-macro", batch_script])

    try:
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "message": f"Batch execution completed (exit {result.returncode})",
            "exit_code": result.returncode,
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


def run_catia_with_runtime(workspace_path: str, timeout: int = 60) -> dict:
    """Start CATIA with Runtime View from workspace (CNEXT -direnv)"""
    return start_catia_runtime(workspace_path=workspace_path, timeout=timeout)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Start CATIA Runtime View",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
Examples:
  python run.py                              # Start CATIA (default environment)
  python run.py D:\workspace                 # Start with Runtime View
  python run.py --env CATIA.P3.V5-6R2018.B28 # Specify environment
  python run.py --wait                       # Start and wait for exit
  python run.py --check                      # Check if running
  python run.py --dev D:\workspace           # Build + Run in one command
        """,
    )

    parser.add_argument(
        "workspace",
        nargs="?",
        default=None,
        help="Workspace path with Runtime View (optional)",
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
        result = stop_catia()
        output_json(
            result, exit_code=0 if result["status"] in ["stopped", "not_running"] else 1
        )
        return

    # Dev mode: build then run
    if args.dev and args.workspace:
        from build import build_workspace
        from pathlib import Path as _Path
        print("Building...", file=sys.stderr)
        build_result = build_workspace(_Path(args.workspace))
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
    )

    # Output JSON
    exit_code = 0 if result["status"] in ["started", "exited", "already_running"] else 1
    output_json(result, exit_code=exit_code)


# Alias for backward compatibility
start_catia = start_catia_runtime


if __name__ == "__main__":
    main()
