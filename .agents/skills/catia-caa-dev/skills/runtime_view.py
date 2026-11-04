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

    # Execute command with the same Build Time chain as build.py.
    # mkCreateRuntimeView loads every framework IdentityCard. mkinit alone
    # does not register the TCK or the prerequisite workspace, so every
    # framework fails with "Unable to load component". The chain must be
    # tck_init -> tck_profile <TCK id> -> mkinit -> mkGetPreq -p -> command.
    # Declared before the try so the finally below can clean up on every exit
    # path — including the early return for a missing mkinit.bat, which fires
    # before these are assigned.
    tmpfile = None
    batfile = None
    try:
        catia_install = caa_env.config.get("CATIA_INSTALL", "")
        code_command = Path(catia_install) / architecture / "code" / "command"
        code_bin = Path(catia_install) / architecture / "code" / "bin"
        mkinit_bat = code_command / "mkinit.bat"
        tck_init_bat = code_command / "tck_init.bat"
        tck_profile_bat = (
            Path(catia_install) / architecture / "TCK" / "command" / "tck_profile.bat"
        )

        if not mkinit_bat.exists():
            error_msg = f"mkinit.bat not found: {mkinit_bat}"
            logger.write(error_msg, "ERROR")
            return {"status": "error", "message": error_msg, "created": False}

        # Create a temporary batch file to run mkCreateRuntimeView with proper environment
        tmpfile = workspace_path / ".mkcreate_output.tmp"
        batfile = workspace_path / ".mkcreate_run.bat"

        # Same order as CAAEnvironment.build_time_command(). tck_profile's
        # first argument must be the TCK id (V5_6R2018_B28), never a path.
        steps = []
        if tck_init_bat.exists():
            steps.append(f'call "{tck_init_bat}" >nul 2>&1')
        tck_id = caa_env.resolve_tck_id()
        if tck_profile_bat.exists() and tck_id:
            steps.append(f'call "{tck_profile_bat}" {tck_id} >nul 2>&1')
        steps.append(f'call "{mkinit_bat}" >nul 2>&1')
        steps.append(f"set PATH={code_bin};{code_command};%PATH%")
        steps.append(f'cd /d "{workspace_path}"')
        if catia_install:
            steps.append(f'call mkGetPreq -p "{catia_install};" >nul 2>&1')
        if mk_cmd:
            steps.append(f'"{mk_cmd}"')
        else:
            steps.append("mkmk -rtv")
        cmd_str = " && ".join(steps)

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

    finally:
        # Runs on every exit path, so the workspace-local .mkcreate_* files are
        # gone once this function returns or raises — success, timeout, or
        # exception alike. Previously the cleanup sat inside the try body, so
        # both except branches returned straight past it and left the files
        # behind in the user's workspace. Cleanup failures are swallowed so
        # they can never mask the real return value or exception.
        for temp_path in (tmpfile, batfile):
            if temp_path is None:
                continue
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass


def check_runtime_view_l0(workspace_path: Path, architecture: str = None) -> dict:
    """Check L0: Physical Runtime View directory presence."""
    if architecture is None:
        try:
            architecture = CAAEnvironment().get_architecture() or "win_b64"
        except Exception:
            architecture = "win_b64"

    target_dir = Path(workspace_path) / architecture
    exists = target_dir.is_dir()
    return {
        "level": "L0",
        "status": "PASS" if exists else "FAIL",
        "check": "runtime_view_directory_present",
        "evidence": {
            "target_path": str(target_dir),
            "architecture": architecture,
            "exists": exists,
            "scope": "physical_directory_check",
        },
    }


def _verify_pe_file(path: Path, expected_arch: str = None) -> bool:
    """Verify that path is a valid Windows PE file with complete COFF and Optional headers.

    Checks:
    1. DOS header magic (MZ) and minimum file size
    2. e_lfanew pointer validity within file boundaries
    3. PE signature (PE\\0\\0)
    4. COFF File Header (20 bytes): NumberOfSections > 0, SizeOfOptionalHeader >= 2
    5. Machine architecture matching (win_b64 -> 0x8664 AMD64, intel_a -> 0x014c i386)
    6. Optional Header magic (0x020B PE32+ for 64-bit, 0x010B PE32 for 32-bit)
    """
    try:
        import struct

        file_size = path.stat().st_size
        # Minimum size: DOS Header (64 bytes) + PE Sig (4 bytes) + COFF Header (20 bytes) + Optional Magic (2 bytes) = 90 bytes
        if file_size < 90:
            return False

        with open(path, "rb") as f:
            header = f.read(64)
            if len(header) < 64 or header[:2] != b"MZ":
                return False

            pe_offset = struct.unpack_from("<I", header, 0x3C)[0]
            # Must leave room for PE sig (4) + COFF (20) + Optional Magic (2)
            if pe_offset <= 0 or pe_offset > file_size - 26:
                return False

            f.seek(pe_offset)
            pe_sig = f.read(4)
            if pe_sig != b"PE\x00\x00":
                return False

            coff_bytes = f.read(20)
            if len(coff_bytes) < 20:
                return False

            machine, num_sections, _, _, _, size_opt_hdr, _ = struct.unpack("<HHIIIHH", coff_bytes)
            if num_sections <= 0 or size_opt_hdr < 2:
                return False

            opt_magic_bytes = f.read(2)
            if len(opt_magic_bytes) < 2:
                return False
            opt_magic = struct.unpack("<H", opt_magic_bytes)[0]

            # Validate architecture consistency
            norm_arch = (expected_arch or "").lower()
            if norm_arch == "win_b64":
                if machine != 0x8664 or opt_magic != 0x020B:
                    return False
            elif norm_arch == "intel_a":
                if machine != 0x014C or opt_magic != 0x010B:
                    return False
            else:
                # General check: must be either AMD64 (PE32+) or i386 (PE32)
                if machine == 0x8664 and opt_magic != 0x020B:
                    return False
                elif machine == 0x014C and opt_magic != 0x010B:
                    return False
                elif machine not in (0x8664, 0x014C):
                    return False

            return True
    except Exception:
        return False


def _verify_dico_syntax(path: Path, target_module: str = None) -> dict:
    """Validate CAA .dico file syntax and verify explicit target module linkage.

    Rules:
    - Every non-empty, non-comment line must contain at least 3 whitespace-separated tokens
      (interface, implementation/class, and shared library).
    - If target_module is provided, at least one entry must explicitly bind to that module's
      runtime library (e.g. libTargetModule or TargetModule).
    """
    entries_count = 0
    syntax_errors = 0
    mentions_target = False
    norm_mod = (target_module[:-2] if target_module.endswith(".m") else target_module).lower() if target_module else None

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line_idx, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 3:
                    entries_count += 1
                    if norm_mod:
                        # Third column and beyond specify the shared library/module
                        for p in parts[2:]:
                            p_clean = p.lower()
                            if norm_mod == p_clean or f"lib{norm_mod}" == p_clean or norm_mod in p_clean:
                                mentions_target = True
                                break
                else:
                    syntax_errors += 1
    except Exception:
        return {
            "valid_syntax": False,
            "entry_count": 0,
            "syntax_errors": 1,
            "mentions_target_module": False if target_module else None,
        }

    return {
        "valid_syntax": (entries_count > 0 and syntax_errors == 0),
        "entry_count": entries_count,
        "syntax_errors": syntax_errors,
        "mentions_target_module": mentions_target if target_module else None,
    }


def check_runtime_view_l1(
    workspace_path: Path, architecture: str = None, target_module: str = None
) -> dict:
    """Check L1: Runtime View asset integrity (DLLs, DICO, CATNls)."""
    l0 = check_runtime_view_l0(workspace_path, architecture)
    if l0["status"] != "PASS":
        return {
            "level": "L1",
            "status": "NOT_RUN",
            "check": "runtime_asset_integrity",
            "evidence": {
                "reason": "l0_directory_not_present",
                "target_module": target_module,
            },
        }

    arch_dir = Path(l0["evidence"]["target_path"])
    bin_dir = arch_dir / "code" / "bin"
    dico_dir = arch_dir / "code" / "dictionary"
    msg_dir = arch_dir / "resources" / "msgcatalog"

    # Scan DLLs & verify PE format with architecture matching
    dll_files = []
    pe_valid_dlls = []
    if bin_dir.is_dir():
        dll_files = [f for f in bin_dir.glob("*.dll") if f.is_file() and f.stat().st_size > 0]
        pe_valid_dlls = [f for f in dll_files if _verify_pe_file(f, expected_arch=architecture)]

    # Scan DICOs & verify syntax
    dico_files = []
    dico_reports = []
    if dico_dir.is_dir():
        dico_files = [f for f in dico_dir.glob("*.dico") if f.is_file() and f.stat().st_size > 0]
        for df in dico_files:
            rep = _verify_dico_syntax(df, target_module=target_module)
            dico_reports.append({"file": df.name, **rep})

    # Scan MsgCatalogs
    nls_files = []
    if msg_dir.is_dir():
        nls_files = [f for f in msg_dir.glob("*.CATNls") if f.is_file() and f.stat().st_size > 0]

    # Target module check if requested
    target_dll_found = False
    target_dll_valid_pe = False
    target_dico_bound = False
    if target_module:
        norm_mod = target_module[:-2] if target_module.endswith(".m") else target_module
        expected_dll_name = f"{norm_mod}.dll".lower()
        for f in dll_files:
            if f.name.lower() == expected_dll_name:
                target_dll_found = True
                target_dll_valid_pe = _verify_pe_file(f, expected_arch=architecture)
                break
        # Strong binding: at least one valid DICO must explicitly mention the target module
        target_dico_bound = any(r.get("valid_syntax") and r.get("mentions_target_module") for r in dico_reports)

    # General syntax validity of DICOs
    any_valid_dico = any(r["valid_syntax"] for r in dico_reports)

    # Evaluation
    # R-03 fix: If target_module is specified, it MUST have a valid PE DLL AND be declared in a valid DICO.
    # An unrelated DICO alone cannot satisfy L1 for target_module.
    if target_module:
        passed = target_dll_found and target_dll_valid_pe and target_dico_bound
    else:
        passed = len(pe_valid_dlls) > 0 and any_valid_dico

    return {
        "level": "L1",
        "status": "PASS" if passed else "FAIL",
        "check": "runtime_asset_integrity",
        "evidence": {
            "target_module": target_module,
            "target_dll_found": target_dll_found if target_module else None,
            "target_dll_valid_pe": target_dll_valid_pe if target_module else None,
            "target_dico_bound": target_dico_bound if target_module else None,
            "dll_count": len(dll_files),
            "pe_valid_dll_count": len(pe_valid_dlls),
            "dico_count": len(dico_files),
            "dico_reports": dico_reports,
            "nls_count": len(nls_files),
            "bin_dir_exists": bin_dir.is_dir(),
            "dico_dir_exists": dico_dir.is_dir(),
            "assets": {
                "dll": {
                    "count": len(dll_files),
                    "valid_pe_count": len(pe_valid_dlls),
                    "target_found": target_dll_found if target_module else None,
                    "target_valid_pe": target_dll_valid_pe if target_module else None,
                },
                "dico": {
                    "count": len(dico_files),
                    "valid_syntax": any_valid_dico,
                    "reports": dico_reports,
                },
                "nls": {
                    "count": len(nls_files),
                    "present": len(nls_files) > 0,
                },
            },
            "scope": "asset_filesystem_integrity_check",
        },
    }


def check_runtime_view(workspace_path: Path, target_module: str = None) -> dict:
    """
    Check Runtime View with layered evidence (L0 and L1).

    Args:
        workspace_path: Path to workspace directory
        target_module: Optional target module to verify in L1

    Returns:
        Dictionary with runtime view status and verification levels
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

    try:
        configured_arch = CAAEnvironment().get_architecture() or "win_b64"
    except Exception:
        configured_arch = "win_b64"

    l0_res = check_runtime_view_l0(workspace_path, configured_arch)
    l1_res = check_runtime_view_l1(workspace_path, configured_arch, target_module=target_module)

    levels = {
        "L0": l0_res,
        "L1": l1_res,
        "L2": {"level": "L2", "status": "NOT_RUN", "check": "target_process_identity", "evidence": {"reason": "static_probe_only"}},
        "L3": {"level": "L3", "status": "NOT_RUN", "check": "module_loaded_exact_path", "evidence": {"reason": "static_probe_only"}},
        "L4": {"level": "L4", "status": "NOT_RUN", "check": "addin_runtime_registration", "evidence": {"reason": "static_probe_only"}},
        "L5": {"level": "L5", "status": "NOT_RUN", "check": "functional_verification", "evidence": {"reason": "static_probe_only"}},
    }

    highest = "L1" if l1_res["status"] == "PASS" else ("L0" if l0_res["status"] == "PASS" else "NONE")

    if runtime_dirs:
        res = {
            "status": "found",
            "message": f"Found {len(runtime_dirs)} Runtime View(s)",
            "runtime_views": runtime_dirs,
            "runtime_view_present": True,
            "runtime_view_mounted": True,  # legacy alias
            "runtime_verification": {
                "highest_verified_level": highest,
                "levels": levels,
            },
        }
        raw_snapshot = dict(res)
        if len(runtime_dirs) == 1:
            target_arch = runtime_dirs[0]["architecture"]
            target_path = runtime_dirs[0]["path"]
            arch_matched = (target_arch == configured_arch)
        else:
            target_arch = [d["architecture"] for d in runtime_dirs]
            target_path = [d["path"] for d in runtime_dirs]
            arch_matched = any(d["architecture"] == configured_arch for d in runtime_dirs)

        res["execution"] = {
            "status": "completed",
            "action_result": "found",
            "raw": raw_snapshot,
        }
        res["verification"] = {
            "status": "passed",
            "check": "runtime_candidate_path_exists",
            "evidence": {
                "target_architecture": target_arch,
                "target_path": target_path,
                "configured_architecture": configured_arch,
                "architecture_matched": arch_matched,
                "exists": True,
                "instance_scope": "path_existence_predicate_only",
                "levels": levels,
            },
        }
        return res
    else:
        res = {
            "status": "not_found",
            "message": "No Runtime View found",
            "runtime_views": [],
            "runtime_view_present": False,
            "runtime_view_mounted": False,  # legacy alias
            "runtime_verification": {
                "highest_verified_level": "NONE",
                "levels": levels,
            },
        }
        raw_snapshot = dict(res)
        res["execution"] = {
            "status": "completed",
            "action_result": "not_found",
            "raw": raw_snapshot,
        }
        res["verification"] = {
            "status": "not_run",
            "check": "none",
            "evidence": {
                "reason": "no_candidate_path_exists",
                "configured_architecture": configured_arch,
                "architecture_matched": False,
                "exists": False,
                "levels": levels,
            },
        }
        return res


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
