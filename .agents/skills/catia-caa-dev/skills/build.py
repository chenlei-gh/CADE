"""
CATIA CAA Build Skill
=====================
Purpose: Compile CAA workspace using mkmk with full Build Time environment.
Usage: python build.py [workspace_path] [options]
Output: JSON with compilation result

Build Time calling chain (replicates VS Build Time Prompt):
  cmd.exe
    → mkinit.bat  (full Mkmk environment: detects VS, Windows Kit, etc.)
    → mkmkM.exe   (actual compilation)
"""

import argparse
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from env import CAAEnvironment
from parser import parse_mkmk_output
from utils import Cache, Logger, format_duration, output_json


def build_workspace(
    workspace_path: Path, options: str = "-u", timeout: int = 600
) -> dict:
    """
    Build CAA workspace using mkmk with full Build Time environment.

    The Build Time environment must be initialized inside cmd.exe (via mkinit.bat),
    so we execute the entire build chain through cmd /c and capture output to a temp file.
    """
    logger = Logger("build.log")
    cache = Cache("build.json")
    logger.clear()

    start_time = datetime.now()
    logger.write(f"Starting build: {workspace_path}")
    logger.write(f"Options: {options}")

    # --- Validate environment ---
    caa_env = CAAEnvironment()
    if not caa_env.load_config():
        return error_result("Failed to load CAA configuration")

    if not workspace_path.exists():
        return error_result(f"Workspace path does not exist: {workspace_path}")

    # --- Get Build Time command ---
    try:
        cmd, cmd_display = caa_env.build_time_command(str(workspace_path), options)
        logger.write(f"Command: {cmd_display}")
    except FileNotFoundError as e:
        return error_result(str(e))

    # --- Execute mkmk via cmd.exe ---
    # Write output to temp file because subprocess may not capture cmd.exe child output
    # Use system temp directory to avoid polluting workspace
    import tempfile

    tmpfile = Path(tempfile.mktemp(suffix=".tmp", prefix="mkmk_output_"))
    batfile = Path(tempfile.mktemp(suffix=".bat", prefix="mkmk_run_"))

    try:
        # Create batch file — split & chain into separate lines for proper %PATH% expansion
        steps = cmd_display.split(" & ")
        bat_lines = ["@echo off"]
        for i, step in enumerate(steps):
            if i == len(steps) - 1:
                bat_lines.append(f'{step} > "{tmpfile}" 2>&1')
            else:
                bat_lines.append(step)
        bat_lines.append(f'echo EXIT_CODE=%ERRORLEVEL% >> "{tmpfile}"')
        bat_content = "\r\n".join(bat_lines) + "\r\n"
        batfile.write_text(bat_content, encoding="ascii")

        logger.write("Executing build...")
        result = subprocess.run(
            ["cmd", "/c", str(batfile)],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )

        # Read output from temp file
        try:
            output = tmpfile.read_text(encoding="utf-8", errors="replace")
        except Exception:
            output = result.stdout + "\n" + result.stderr

        # Log full output
        logger.write("=" * 60)
        logger.write("Build Output:")
        logger.write("=" * 60)
        for line in output.split("\n"):
            if line.strip():
                logger.write(line)

        # Parse errors/warnings
        parsed = parse_mkmk_output(output)

        # Extract exit code from output
        exit_code = result.returncode
        for line in output.split("\n"):
            if line.startswith("EXIT_CODE="):
                try:
                    exit_code = int(line.split("=")[1].strip())
                except ValueError:
                    pass

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        if exit_code != 0 or parsed["error_count"] > 0:
            status = "failed"
            message = f"Build failed with {parsed['error_count']} error(s)"
        else:
            status = "success"
            message = "Build successful"

        build_result = {
            "status": status,
            "message": message,
            "error_count": parsed["error_count"],
            "warning_count": parsed["warning_count"],
            "errors": parsed["errors"],
            "warnings": parsed["warnings"],
            "duration": format_duration(duration),
            "duration_seconds": duration,
            "workspace": str(workspace_path),
            "options": options,
            "timestamp": start_time.isoformat(),
            "return_code": exit_code,
        }

        cache.save(build_result)
        logger.write(
            f"Status: {status} | Errors: {parsed['error_count']} | Duration: {format_duration(duration)}"
        )
        return build_result

    except subprocess.TimeoutExpired:
        return error_result(f"Build timeout after {timeout} seconds", timeout=timeout)
    except Exception as e:
        return error_result(f"Build exception: {e}", exception=str(e))
    finally:
        # Clean up temp files
        if tmpfile.exists():
            tmpfile.unlink()
        if batfile.exists():
            batfile.unlink()


def error_result(message: str, **kwargs) -> dict:
    return {
        "status": "error",
        "message": message,
        "error_count": 0,
        "warning_count": 0,
        "errors": [],
        **kwargs,
    }


# ─── Named Build Functions (AI-Friendly) ──────────────────────────


def incremental_build(workspace_path: Path, timeout: int = 600) -> dict:
    """Incremental build (mkmk -u) — most common"""
    return build_workspace(workspace_path, "-u", timeout)


def full_build(workspace_path: Path, timeout: int = 1200) -> dict:
    """Full rebuild (mkmk -a)"""
    return build_workspace(workspace_path, "-a", timeout)


def clean_build(workspace_path: Path, timeout: int = 1200) -> dict:
    """Clean then build (mkmk -c)"""
    return build_workspace(workspace_path, "-c", timeout)


def debug_build(workspace_path: Path, timeout: int = 600) -> dict:
    """Debug mode build (mkmk -g)"""
    return build_workspace(workspace_path, "-g", timeout)


def dry_run_build(workspace_path: Path, timeout: int = 60) -> dict:
    """Dry run — show what would be built (mkmk -n)"""
    return build_workspace(workspace_path, "-n", timeout)


def create_runtime_view(workspace_path: Path) -> dict:
    """Create/update Runtime View (mkCreateRuntimeView) + copy dictionaries"""
    result = _exec_build_cmd("mkCreateRuntimeView", workspace_path)
    # mkCreateRuntimeView may skip dictionary copy — ensure it manually
    _copy_dictionaries_to_runtime(workspace_path)
    return result


def _copy_dictionaries_to_runtime(workspace_path: Path):
    """Copy all framework dictionaries to Runtime View's code/dictionary/"""
    import shutil
    rv_dict = workspace_path / "win_b64" / "code" / "dictionary"
    for dico in workspace_path.rglob("CNext/code/dictionary/*.dico"):
        if dico.is_file():
            rv_dict.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dico, rv_dict / dico.name)


def multi_create_runtime_view(workspace_path: Path) -> dict:
    """Multi Runtime View (mkMultiCreateRuntimeView)"""
    return _exec_build_cmd("mkMultiCreateRuntimeView", workspace_path)


# ─── Workspace ────────────────────────────────────────────────────


def workspace_info(workspace_path: Path) -> dict:
    """Show workspace info (mkwhereami + mkreadcpd)"""
    return _exec_build_cmd("mkwhereami & mkreadcpd", workspace_path)


def workspace_where(workspace_path: Path) -> dict:
    """Show current workspace location (mkwhereami)"""
    return _exec_build_cmd("mkwhereami", workspace_path)


def workspace_config(workspace_path: Path) -> dict:
    """Read workspace config (mkreadcpd)"""
    return _exec_build_cmd("mkreadcpd", workspace_path)


def workspace_build_config(workspace_path: Path) -> dict:
    """Read build configuration (mkreadbldcfg)"""
    return _exec_build_cmd("mkreadbldcfg", workspace_path)


def workspace_module_info(workspace_path: Path, module: str = None) -> dict:
    """Read module info (mkreadms)"""
    cmd = f"mkreadms {module}" if module else "mkreadms"
    return _exec_build_cmd(cmd, workspace_path)


# ─── Framework ────────────────────────────────────────────────────


def update_framework(workspace_path: Path) -> dict:
    """Update Framework (MkUpToDateAFramework)"""
    return _exec_build_cmd("MkUpToDateAFrameworkM", workspace_path)


def copy_framework(workspace_path: Path, args: str = "") -> dict:
    """Copy Framework (MkCopyFw)"""
    return _exec_build_cmd(f"MkCopyFw {args}".strip(), workspace_path)


def remove_framework(workspace_path: Path, fw_name: str = "") -> dict:
    """Remove Framework (MkRemoveAFramework or mkRmFw)"""
    cmd = f"MkRemoveAFrameworkM {fw_name}" if fw_name else "mkRmFw"
    return _exec_build_cmd(cmd, workspace_path)


# ─── Dependency & Prerequisite ────────────────────────────────────


def dependency_analysis(workspace_path: Path) -> dict:
    """Run dependency analysis (mkmkdepend)"""
    return _exec_build_cmd("mkmkdepend", workspace_path)


def impact_analysis(workspace_path: Path) -> dict:
    """Run impact analysis (mkmkimpact)"""
    return _exec_build_cmd("mkmkimpact", workspace_path)


def get_prerequisite(workspace_path: Path, target: str = "") -> dict:
    """View prerequisite (mkGetPreq)"""
    cmd = f"mkGetPreq {target}" if target else "mkGetPreq"
    return _exec_build_cmd(cmd, workspace_path)


def setup_prerequisite_path(workspace_path: Path, catia_install: str = None) -> dict:
    """
    Set up prerequisite workspace path (mkGetPreq -p).
    Links the CAA workspace to the CATIA installation so mkmk can
    find system frameworks (BSFBuildtimeData, System, etc.).
    
    Equivalent to: mkGetPreq -p "C:/Program Files/Dassault Systemes/B28;"
    """
    if not catia_install:
        from env import CAAEnvironment
        env = CAAEnvironment()
        env.load_config()
        catia_install = env.config.get("CATIA_INSTALL", "")
    if not catia_install:
        return error_result("CATIA installation path not configured")
    cmd = f'mkGetPreq -p "{catia_install};"'
    return _exec_build_cmd(cmd, workspace_path)


def print_prerequisite(workspace_path: Path, target: str = "") -> dict:
    """Print prerequisite tree (mkPrintPreq)"""
    cmd = f"mkPrintPreq {target}" if target else "mkPrintPreq"
    return _exec_build_cmd(cmd, workspace_path)


# ─── IdentityCard ─────────────────────────────────────────────────


def create_identity_card(workspace_path: Path, fw_name: str = "") -> dict:
    """Create IdentityCard (mkCreateIC)"""
    cmd = f"mkCreateIC {fw_name}" if fw_name else "mkCreateIC"
    return _exec_build_cmd(cmd, workspace_path)


# ─── Documentation ────────────────────────────────────────────────


def generate_cpp_doc(workspace_path: Path) -> dict:
    """Generate C++ documentation (mkmancpp)"""
    return _exec_build_cmd("mkmancpp", workspace_path)


def generate_idl_doc(workspace_path: Path) -> dict:
    """Generate IDL documentation (mkmanidl)"""
    return _exec_build_cmd("mkmanidl", workspace_path)


def extract_methods(workspace_path: Path) -> dict:
    """Extract method prototypes (mkGetMethodsProto)"""
    return _exec_build_cmd("mkGetMethodsProto", workspace_path)


# ─── Export ───────────────────────────────────────────────────────


def export_symbols(workspace_path: Path, dll: str = "") -> dict:
    """Export DLL symbols (mkexportsymbols)"""
    cmd = f"mkexportsymbols {dll}" if dll else "mkexportsymbols"
    return _exec_build_cmd(cmd, workspace_path)


# ─── Utility ──────────────────────────────────────────────────────


def mkmk_version(workspace_path: Path = None) -> dict:
    """Show mkmk version (mkmkversion)"""
    return _exec_build_cmd("mkmkversion", workspace_path or Path("."))


def run_executable(workspace_path: Path, target: str = "") -> dict:
    """Run executable in build environment (mkrun)"""
    cmd = f"mkrun {target}" if target else "mkrun"
    return _exec_build_cmd(cmd, workspace_path)


def register_vs(workspace_path: Path) -> dict:
    """Register VS integration (mkManageDevenvReg)"""
    return _exec_build_cmd("mkManageDevenvReg", workspace_path)


def build_with_threads(
    workspace_path: Path, threads: int = 8, timeout: int = 1200
) -> dict:
    """Multi-threaded build (mkmk -j N)"""
    return build_workspace(workspace_path, f"-j {threads}", timeout)


def _exec_build_cmd(command: str, workspace_path: Path, timeout: int = 300) -> dict:
    """Execute a generic Build Time command"""
    import subprocess
    import tempfile
    from datetime import datetime

    logger = Logger("build.log")
    start_time = datetime.now()
    logger.write(f"Running: {command}")

    caa_env = CAAEnvironment()
    if not caa_env.load_config():
        return error_result("Failed to load CAA configuration")

    try:
        cmd, cmd_display = caa_env.run_command(command, str(workspace_path))
        logger.write(f"Command: {cmd_display}")
    except FileNotFoundError as e:
        return error_result(str(e))

    tmpfile = Path(tempfile.mktemp(suffix=".tmp", prefix="mkmk_cmd_"))
    batfile = Path(tempfile.mktemp(suffix=".bat", prefix="mkmk_cmd_"))

    try:
        bat_content = f'@echo off\r\n{cmd_display} > "{tmpfile}" 2>&1\r\necho EXIT_CODE=%ERRORLEVEL% >> "{tmpfile}"\r\n'
        batfile.write_text(bat_content, encoding="ascii")

        result = subprocess.run(
            ["cmd", "/c", str(batfile)],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )

        try:
            output = tmpfile.read_text(encoding="utf-8", errors="replace")
        except Exception:
            output = result.stdout + "\n" + result.stderr

        logger.write(output[:2000])

        exit_code = result.returncode
        for line in output.split("\n"):
            if line.startswith("EXIT_CODE="):
                try:
                    exit_code = int(line.split("=")[1].strip())
                except ValueError:
                    pass

        duration = (datetime.now() - start_time).total_seconds()

        return {
            "status": "success" if exit_code == 0 else "failed",
            "message": f"Command completed with exit code {exit_code}",
            "command": command,
            "exit_code": exit_code,
            "duration_seconds": duration,
            "output_tail": output[-500:] if len(output) > 500 else output,
        }
    except subprocess.TimeoutExpired:
        return error_result(f"Command timed out after {timeout}s")
    except Exception as e:
        return error_result(f"Command exception: {e}")
    finally:
        if tmpfile.exists():
            tmpfile.unlink()
        if batfile.exists():
            batfile.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Build CATIA CAA workspace",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  python build.py\n  python build.py D:\\workspace\\MyFw.edu\n  python build.py . -g\n  python build.py --timeout 1200",
    )
    parser.add_argument(
        "workspace", nargs="?", default=".", help="Workspace path (default: current)"
    )
    parser.add_argument(
        "options", nargs="?", default="-u", help="mkmk options (default: -u)"
    )
    parser.add_argument(
        "--timeout", type=int, default=600, help="Timeout in seconds (default: 600)"
    )
    args = parser.parse_args()

    result = build_workspace(Path(args.workspace).resolve(), args.options, args.timeout)
    output_json(result, exit_code=0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
