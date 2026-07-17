"""
CATIA CAA Runtime View Skill
=============================
Purpose: Create and manage CATIA Runtime View
Usage: python runtime_view.py [workspace_path] [options]
Output: JSON with runtime view status
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from env import CAAEnvironment
from utils import Cache, Logger, format_duration, output_json


def create_runtime_view(
    workspace_path: Path, overwrite: bool = False, architecture: str = None
) -> dict:
    """
    Create CATIA Runtime View using mkCreateRuntimeView

    Args:
        workspace_path: Path to workspace directory
        overwrite: If True, recreate existing runtime view
        architecture: Target architecture (auto-detect if None)

    Returns:
        Dictionary with runtime view creation result
    """
    logger = Logger("runtime_view.log")
    cache = Cache("runtime_view.json")

    # Clear previous logs
    logger.clear()

    # Initialize environment (once, used for arch detection + runtime view creation)
    caa_env = CAAEnvironment()

    # Auto-detect architecture if not specified
    if architecture is None:
        architecture = caa_env.get_architecture()

    start_time = datetime.now()
    logger.write(f"Creating Runtime View: {workspace_path}")
    logger.write(f"Architecture: {architecture}")
    logger.write(f"Overwrite: {overwrite}")

    env_vars = caa_env.initialize()

    if not env_vars:
        error_msg = "Failed to initialize CAA environment"
        logger.write(error_msg, "ERROR")
        return {"status": "error", "message": error_msg, "created": False}

    # Validate workspace path
    if not workspace_path.exists():
        error_msg = f"Workspace path does not exist: {workspace_path}"
        logger.write(error_msg, "ERROR")
        return {"status": "error", "message": error_msg, "created": False}

    # Check if runtime view already exists
    runtime_path = workspace_path / architecture
    if runtime_path.exists():
        if not overwrite:
            logger.write(f"Runtime View already exists: {runtime_path}", "WARNING")
            return {
                "status": "exists",
                "message": f"Runtime View already exists at {architecture}",
                "created": False,
                "runtime": architecture,
                "runtime_path": str(runtime_path),
            }
        else:
            logger.write(f"Removing existing Runtime View: {runtime_path}")
            try:
                import shutil

                shutil.rmtree(runtime_path)
                logger.write("Existing Runtime View removed")
            except Exception as e:
                error_msg = f"Failed to remove existing Runtime View: {e}"
                logger.write(error_msg, "ERROR")
                return {"status": "error", "message": error_msg, "created": False}

    # Find mkCreateRuntimeView command
    catia_path = Path(caa_env.config.get("CATIA_INSTALL", ""))

    # Try to locate mkCreateRuntimeView
    mk_cmd_paths = [
        catia_path / architecture / "code" / "command" / "mkCreateRuntimeView.bat",
        catia_path
        / "CAADoc"
        / "CNext"
        / "code"
        / "command"
        / "mkCreateRuntimeView.bat",
    ]

    mk_cmd = None
    for path in mk_cmd_paths:
        if path.exists():
            mk_cmd = path
            break

    if not mk_cmd:
        # Fallback: Try to use mkmk with -rtv option
        logger.write("mkCreateRuntimeView not found, attempting mkmk -rtv", "WARNING")

        mkmk_path = caa_env.get_mkmk_path()
        if not mkmk_path:
            error_msg = "Neither mkCreateRuntimeView nor mkmk found"
            logger.write(error_msg, "ERROR")
            return {"status": "error", "message": error_msg, "created": False}

        # Use mkmk to create runtime view
        cmd = [str(mkmk_path), "-rtv"]
        logger.write(f"Using mkmk: {' '.join(cmd)}")
    else:
        # Use mkCreateRuntimeView
        cmd = [str(mk_cmd)]
        logger.write(f"Using mkCreateRuntimeView: {mk_cmd}")

    # Execute command with Build Time environment
    # mkCreateRuntimeView is a Build Time tool that requires mkinit.bat initialization
    try:
        # Use Build Time environment initialization
        catia_install = caa_env.config.get("CATIA_INSTALL", "")
        mkinit_bat = (
            Path(catia_install) / architecture / "code" / "command" / "mkinit.bat"
        )

        if not mkinit_bat.exists():
            error_msg = f"mkinit.bat not found: {mkinit_bat}"
            logger.write(error_msg, "ERROR")
            return {"status": "error", "message": error_msg, "created": False}

        # Create a temporary batch file to run mkCreateRuntimeView with proper environment
        tmpfile = workspace_path / ".mkcreate_output.tmp"
        batfile = workspace_path / ".mkcreate_run.bat"

        # Build command string
        if mk_cmd:
            cmd_str = f'call "{mkinit_bat}" >nul 2>&1 && cd /d "{workspace_path}" && "{mk_cmd}"'
        else:
            cmd_str = f'call "{mkinit_bat}" >nul 2>&1 && cd /d "{workspace_path}" && mkmk -rtv'

        logger.write(f"Command: {cmd_str}")

        # Write batch file. newline="" prevents write_text's default
        # \n -> \r\n translation from doubling the \r\n already embedded in
        # bat_content, which produces malformed \r\r\n line endings that can
        # corrupt the CATIA TCK/mkmk batch chain (see env.py build_time_command).
        bat_content = f'@echo off\r\n{cmd_str} > "{tmpfile}" 2>&1\r\necho EXIT_CODE=%ERRORLEVEL% >> "{tmpfile}"\r\n'
        batfile.write_text(bat_content, encoding="ascii", newline="")

        result = subprocess.run(
            ["cmd", "/c", str(batfile)],
            capture_output=True,
            text=True,
            timeout=300,
            encoding="utf-8",
            errors="replace",
        )

        # Read output from temp file
        try:
            output = tmpfile.read_text(encoding="utf-8", errors="replace")
        except Exception:
            output = result.stdout + "\n" + result.stderr
        logger.write("=" * 60)
        logger.write("Command Output:")
        logger.write("=" * 60)
        for line in output.split("\n"):
            if line.strip():
                logger.write(line)

        # Extract exit code from output
        exit_code = result.returncode
        for line in output.split("\n"):
            if line.startswith("EXIT_CODE="):
                try:
                    exit_code = int(line.split("=")[1].strip())
                except ValueError:
                    pass

        # Calculate duration
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Check if runtime view was created
        runtime_created = runtime_path.exists()

        if result.returncode == 0 and runtime_created:
            status = "success"
            message = f"Runtime View created successfully at {architecture}"
            logger.write(message)
        elif runtime_created:
            status = "warning"
            message = f"Runtime View created but command returned code {exit_code}"
            logger.write(message, "WARNING")
        else:
            status = "failed"
            message = f"Failed to create Runtime View (code {exit_code})"
            logger.write(message, "ERROR")

        # Build result
        runtime_result = {
            "status": status,
            "message": message,
            "created": runtime_created,
            "runtime": architecture if runtime_created else None,
            "runtime_path": str(runtime_path) if runtime_created else None,
            "return_code": exit_code,
            "duration": format_duration(duration),
            "workspace": str(workspace_path),
            "timestamp": start_time.isoformat(),
        }

        # Clean up temp files
        try:
            if tmpfile.exists():
                tmpfile.unlink()
            if batfile.exists():
                batfile.unlink()
        except Exception:
            pass

        # Save to cache
        cache.save(runtime_result)

        logger.write("=" * 60)
        logger.write(f"Status: {status}")
        logger.write(f"Created: {runtime_created}")
        logger.write(f"Duration: {format_duration(duration)}")

        return runtime_result

    except subprocess.TimeoutExpired:
        error_msg = "Runtime View creation timeout after 300 seconds"
        logger.write(error_msg, "ERROR")
        return {"status": "timeout", "message": error_msg, "created": False}

    except Exception as e:
        error_msg = f"Runtime View creation exception: {str(e)}"
        logger.write(error_msg, "ERROR")
        return {
            "status": "error",
            "message": error_msg,
            "exception": str(e),
            "created": False,
        }


def check_runtime_view(workspace_path: Path) -> dict:
    """
    Check if Runtime View exists

    Args:
        workspace_path: Path to workspace directory

    Returns:
        Dictionary with runtime view status
    """
    logger = Logger("runtime_view.log")

    runtime_dirs = []

    # Check for common runtime view directories
    for arch in ["win_b64", "intel_a"]:
        runtime_path = workspace_path / arch
        if runtime_path.exists():
            runtime_dirs.append(
                {"architecture": arch, "path": str(runtime_path), "exists": True}
            )

    if runtime_dirs:
        return {
            "status": "found",
            "message": f"Found {len(runtime_dirs)} Runtime View(s)",
            "runtime_views": runtime_dirs,
        }
    else:
        return {
            "status": "not_found",
            "message": "No Runtime View found",
            "runtime_views": [],
        }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Create or check CATIA Runtime View",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python runtime_view.py                     # Check current directory
  python runtime_view.py --create            # Create runtime view
  python runtime_view.py --create --overwrite # Recreate runtime view
  python runtime_view.py D:\\workspace --create # Create in specific workspace
        """,
    )

    parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Path to workspace directory (default: current directory)",
    )

    parser.add_argument("--create", action="store_true", help="Create Runtime View")

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing Runtime View (requires --create)",
    )

    parser.add_argument(
        "--architecture",
        default=None,
        choices=["win_b64", "intel_a"],
        help="Target architecture (auto-detect if not specified)",
    )

    args = parser.parse_args()

    # Resolve workspace path
    workspace_path = Path(args.workspace).resolve()

    # Execute command
    if args.create:
        result = create_runtime_view(
            workspace_path, overwrite=args.overwrite, architecture=args.architecture
        )
    else:
        result = check_runtime_view(workspace_path)

    # Output JSON
    exit_code = 0 if result["status"] in ["success", "found", "exists"] else 1
    output_json(result, exit_code=exit_code)


if __name__ == "__main__":
    main()
