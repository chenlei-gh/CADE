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
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from env import CAAEnvironment
from parser import parse_mkmk_output
from utils import Cache, Logger, format_duration, output_json


# ─── Health & Verification ──────────────────────────────────────

def validate_workspace(workspace_path: Path) -> dict:
    """Validate a CAA workspace before building. Returns issues list."""
    issues = []
    warnings = []
    fws = [p for p in workspace_path.iterdir() if p.is_dir() and p.name.endswith(".edu")]

    if not fws:
        issues.append("No .edu framework found — not a CAA workspace")
        return {"can_build": False, "issues": issues, "warnings": warnings}

    for fw in fws:
        ic = fw / "IdentityCard"
        if not (ic.exists() and any(ic.iterdir())):
            issues.append(f"{fw.name}: missing IdentityCard")
        imake = fw / "Imakefile.mk"
        if not imake.exists():
            issues.append(f"{fw.name}: missing Imakefile.mk")
        mods = [m for m in fw.iterdir() if m.is_dir() and m.name.endswith(".m")]
        if not mods:
            issues.append(f"{fw.name}: no modules (.m) found")
        for mod in mods:
            if not (mod / "Imakefile.mk").exists():
                issues.append(f"{mod.name}: missing Imakefile.mk")

    can_build = not any("missing IdentityCard" in i or "no modules" in i for i in issues)
    return {"can_build": can_build, "issues": issues, "warnings": warnings}


def verify_build(
    workspace_path: Path,
    expected_modules: Optional[List[str]] = None,
    build_start_time: Optional[datetime] = None,
    touched_modules: Optional[List[str]] = None,
) -> dict:
    """Post-build verification: check that fresh, plausible DLLs were produced.

    Args:
        workspace_path: Workspace root
        expected_modules: Optional list of module names (e.g. ['TTModule']) to verify.
                          If provided, each is checked individually.
        build_start_time: Start of the current build. Used as the staleness
                          cutoff only for modules that this build actually
                          touched (see touched_modules). Modules that mkmk
                          skipped via incremental build are not expected to
                          have a fresher DLL, so they are not held to this
                          cutoff -- otherwise every untouched module in a
                          multi-tool workspace would be falsely flagged as
                          stale on every build.
        touched_modules: Optional list of module names whose sources were
                          actually compiled/linked in this invocation (as
                          seen in the mkmk output, e.g. via 'compilation' /
                          'link1st' steps). If omitted, all modules are
                          treated as touched (legacy behavior, single-tool
                          workspaces).
    """
    arch = "win_b64"
    try:
        from env import CAAEnvironment
        env = CAAEnvironment(); env.load_config()
        arch = env.get_architecture() or "win_b64"
    except Exception:
        pass

    bin_dir = workspace_path / arch / "code" / "bin"
    dlls = list(bin_dir.glob("*.dll")) if bin_dir.exists() else []
    issues = []

    if not dlls:
        issues.append(f"No DLLs found in {bin_dir}")

    touched_lower = {m.lower() for m in touched_modules} if touched_modules is not None else None

    def _dll_module_name(dll_name: str) -> str:
        return dll_name[:-4] if dll_name.lower().endswith(".dll") else dll_name

    def _check_staleness(dll) -> Optional[str]:
        if not build_start_time:
            return None
        if touched_lower is not None and _dll_module_name(dll.name).lower() not in touched_lower:
            # This build's mkmk run did not recompile/relink this module
            # (incremental build skipped it because its sources were
            # unchanged). Its DLL predating this build's start time is
            # therefore expected, not a failure.
            return None
        if dll.stat().st_mtime < build_start_time.timestamp():
            return f"{dll.name}: stale DLL (older than current build start)"
        return None

    # Check target module DLLs (P1-006)
    if expected_modules:
        dll_by_name = {d.name.lower(): d for d in dlls}
        for mod_name in expected_modules:
            expected_dll = f"{mod_name.lower()}.dll"
            dll = dll_by_name.get(expected_dll)
            if dll is None:
                issues.append(f"Expected DLL not found: {expected_dll}")
                continue
            size = dll.stat().st_size
            if size < 1024:
                issues.append(f"{dll.name}: suspicious size ({size} bytes)")
            stale_issue = _check_staleness(dll)
            if stale_issue:
                issues.append(stale_issue)
    else:
        for dll in dlls:
            size = dll.stat().st_size
            if size < 1024:
                issues.append(f"{dll.name}: suspicious size ({size} bytes)")
            stale_issue = _check_staleness(dll)
            if stale_issue:
                issues.append(stale_issue)

    return {
        "dll_count": len(dlls),
        "dlls": [{"name": d.name, "size": d.stat().st_size} for d in dlls],
        "issues": issues,
        "ok": len(issues) == 0,
    }


def sync_runtime_view(workspace_path: Path, arch: str = "win_b64") -> dict:
    """Sync CNext resources to Runtime View after build for CNEXT visibility."""
    import shutil
    rv = workspace_path / arch
    synced = []
    errors = []
    for fw_dir in workspace_path.iterdir():
        if not fw_dir.is_dir() or not fw_dir.name.endswith(".edu"):
            continue
        cnext = fw_dir / "CNext"
        if not cnext.exists():
            continue
        # Dictionary
        dict_src = cnext / "code" / "dictionary"
        if dict_src.exists():
            dict_dst = rv / "code" / "dictionary"
            dict_dst.mkdir(parents=True, exist_ok=True)
            for f in dict_src.glob("*.dico"):
                shutil.copy2(f, dict_dst / f.name)
                synced.append(f"dictionary/{f.name}")
        # NLS + CATRsc (recursively, to sync localized subdirectories like
        # Simplified_Chinese/ that CATIA's NLS loader searches per language).
        msg_src = cnext / "resources" / "msgcatalog"
        if msg_src.exists():
            msg_dst = rv / "resources" / "msgcatalog"
            msg_dst.mkdir(parents=True, exist_ok=True)
            for f in msg_src.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(msg_src)
                    dst = msg_dst / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dst)
                    synced.append(f"msgcatalog/{rel.as_posix()}")
        # Icons
        icon_src = cnext / "resources" / "graphic" / "icons"
        if icon_src.exists():
            icon_dst = rv / "resources" / "graphic" / "icons"
            icon_dst.mkdir(parents=True, exist_ok=True)
            for f in icon_src.rglob("*.bmp"):
                rel = f.relative_to(icon_src)
                dst = icon_dst / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
                synced.append(f"icons/{rel.as_posix()}")
    return {"synced": synced, "errors": errors, "ok": len(errors) == 0}


def diagnose_environment() -> dict:
    """Diagnose CAA build environment health."""
    from env import CAAEnvironment
    env = CAAEnvironment()
    result = {"ok": True, "checks": [], "issues": []}

    if not env.load_config():
        result["ok"] = False
        result["issues"].append("CAA configuration not loaded")
        return result

    catia = Path(env.config.get("CATIA_INSTALL", ""))
    arch = env.get_architecture() or "win_b64"

    checks = [
        ("CATIA installation", catia.exists()),
        ("tck_init.bat", (catia / arch / "code" / "command" / "tck_init.bat").exists()),
        ("tck_profile.bat", (catia / arch / "TCK" / "command" / "tck_profile.bat").exists()),
        ("mkinit.bat", (catia / arch / "code" / "command" / "mkinit.bat").exists()),
        ("mkmk.bat", (catia / arch / "code" / "command" / "mkmk.bat").exists()),
        ("mkmkM.exe", (catia / arch / "code" / "bin" / "mkmkM.exe").exists()),
        ("CNEXT.exe", (catia / arch / "code" / "bin" / "CNEXT.exe").exists()),
        ("CATSTART.exe", (catia / arch / "code" / "bin" / "CATSTART.exe").exists()),
    ]

    for name, ok in checks:
        result["checks"].append({"name": name, "ok": ok})
        if not ok:
            result["ok"] = False
            result["issues"].append(f"Missing: {name}")

    return result


def build_workspace(
    workspace_path: Path, options: str = "-u -a", timeout: int = 600
) -> dict:
    """
    Build CAA workspace using mkmk with full Build Time environment.

    The Build Time environment must be initialized inside cmd.exe (via mkinit.bat),
    so we execute the entire build chain through cmd /c and capture output to a temp file.
    """
    logger = Logger("build.log", workspace_root=workspace_path)
    cache = Cache("build.json", workspace_root=workspace_path)
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

    # --- Pre-build health check ---
    health = validate_workspace(workspace_path)
    if health["issues"]:
        logger.write(f"Workspace issues: {health['issues']}")
        if not health.get("can_build", True):
            return error_result(f"Workspace validation failed: {'; '.join(health['issues'])}")

    # --- Auto-configure workspace prerequisites (links to CATIA installation) ---
    # Only run if workspace looks like a real CAA workspace (has .edu directory)
    has_framework = any(
        p.is_dir() and p.name.endswith(".edu")
        for p in workspace_path.iterdir()
    )
    if has_framework:
        # Cache check: skip if already configured (mkGetPreq is idempotent but slow)
        cache_data = cache.load()
        last_prereq = cache_data.get("prereq_workspace", "")
        if last_prereq != str(workspace_path):
            prereq_result = setup_prerequisite_path(workspace_path)
            if prereq_result.get("status") == "success":
                cache_data["prereq_workspace"] = str(workspace_path)
                cache.save(cache_data)
                logger.write("Prerequisites configured")
            else:
                # P2-004 fix: Don't silently continue — report and abort
                prereq_err = prereq_result.get("message", "Unknown prereq error")
                logger.write(f"Prerequisite setup failed: {prereq_err}")
                return error_result(
                    f"Prerequisite setup failed: {prereq_err}",
                    prereq=prereq_result,
                )
        else:
            logger.write("Prerequisites already configured (cached)")

    # --- Get Build Time command ---
    try:
        cmd, cmd_display = caa_env.build_time_command(str(workspace_path), options)
        logger.write(f"Command: {cmd_display}")
    except FileNotFoundError as e:
        return error_result(str(e))

    # --- Execute mkmk via cmd.exe ---
    # build_time_command now writes a complete .bat to caa_env._build_bat
    # with proper error handling, fallback, and output capture.
    try:
        logger.write("Executing build...")
        # CREATE_NO_WINDOW = 0x08000000 suppresses cmd popup
        result = subprocess.run(
            cmd,  # ["cmd", "/c", "path/to/generated.bat"] from build_time_command
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )

        # Combine stdout + stderr for parsing
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

        # Auto-diagnose fix suggestions
        from parser import diagnose_errors
        suggestions = diagnose_errors(parsed)

        # Extract exit code
        exit_code = result.returncode
        for line in output.split("\n"):
            if line.startswith("EXIT_CODE="):
                try:
                    exit_code = int(line.split("=")[1].strip())
                except ValueError:
                    pass

        # Enhanced exit code detection: also check for #ERR# in output
        if exit_code == 0 and "#ERR#" in output:
            exit_code = -1  # mkmk sometimes returns 0 even with errors

        # Detect TCK/license errors and provide actionable guidance
        tck_guidance = None
        if "at least, one framework" in output or "at least one framework" in output:
            tck_guidance = (
                "mkmk cannot find workspace frameworks. This typically occurs when "
                "the TCK environment is not properly initialized. "
                "Workaround: Use Visual Studio + RADE plugin for compilation "
                "(see TROUBLESHOOTING_FLOWCHART.md > mkmk Issues > License error)."
            )
        elif "RADE" in output and ("license" in output.lower() or "licensing" in output.lower()):
            tck_guidance = (
                "RADE license not available for CLI compilation. "
                "This is expected without a registered TCK. "
                "Workaround: Use Visual Studio manual compilation "
                "(see SKILL.md Method 3 or FAQ.md Q8)."
            )

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
            "suggestions": suggestions if status == "failed" else [],
            "duration": format_duration(duration),
            "duration_seconds": duration,
            "workspace": str(workspace_path),
            "options": options,
            "timestamp": start_time.isoformat(),
            "return_code": exit_code,
            "output": output,  # Raw mkmk output for repair loop to parse
        }
        if tck_guidance:
            build_result["tck_guidance"] = tck_guidance

        # Preserve prerequisite state in the final cache entry. The completed
        # build result is cached only after post-build verification has had a
        # chance to change its status.
        build_result["prereq_workspace"] = str(workspace_path)

        # Post-build verification (P1-005 fix)
        # Discover expected module names from frameworks
        expected_mods = []
        for fw_dir in workspace_path.iterdir():
            if fw_dir.is_dir() and fw_dir.name.endswith(".edu"):
                for mod_dir in fw_dir.iterdir():
                    if mod_dir.is_dir() and mod_dir.name.endswith(".m"):
                        expected_mods.append(mod_dir.name.replace(".m", ""))

        # Determine which modules mkmk actually compiled/linked this run
        # (via '# make:  <Framework>.edu\<Module>.m...' lines). mkmk is
        # incremental: modules whose sources are unchanged are skipped and
        # legitimately keep an older DLL timestamp, so they must not be
        # held to the build_start_time staleness cutoff below. An empty
        # result here is meaningful (nothing needed rebuilding this run,
        # e.g. a no-op re-run) and must NOT be treated as "unknown" --
        # otherwise every already-up-to-date DLL in the workspace gets
        # falsely flagged as stale.
        touched_mods = sorted(set(re.findall(r"#\s*make:\s*\S+?\.edu[\\/](\S+?)\.m\b", output)))
        # Only fall back to "check everything" (None) if the output doesn't
        # even contain a compilation/link section, which means we truly
        # can't tell what mkmk did (unexpected output format).
        has_build_steps = "step: compilation" in output or "step: link1st" in output
        touched_for_verify = touched_mods if has_build_steps else None

        verify = verify_build(
            workspace_path,
            expected_modules=expected_mods if expected_mods else None,
            build_start_time=start_time,
            touched_modules=touched_for_verify,
        )
        build_result["verification"] = verify
        if verify["issues"]:
            if status == "success" and not verify["ok"]:
                build_result["status"] = "failed_verification"
                build_result["message"] = f"Build compiled but verification failed: {'; '.join(verify['issues'])}"
            logger.write(f"Post-build: {verify['issues']}")
        # Sync framework resources to Runtime View for CNEXT visibility (P2-005 fix: all frameworks)
        try:
            sync = sync_runtime_view(workspace_path)
            if sync["synced"]:
                logger.write(f"Runtime View synced: {len(sync['synced'])} files")
        except Exception:
            pass
        cache.save(build_result)
        logger.write(
            f"Status: {build_result['status']} | Errors: {parsed['error_count']} | Duration: {format_duration(duration)}"
        )
        return build_result

    except subprocess.TimeoutExpired:
        return error_result(f"Build timeout after {timeout} seconds", timeout=timeout)
    except Exception as e:
        return error_result(f"Build exception: {e}", exception=str(e))
    finally:
        # Clean up temp .bat generated by build_time_command
        try:
            build_bat = getattr(caa_env, "_build_bat", None)
            if build_bat and build_bat.exists():
                build_bat.unlink()
        except Exception:
            pass


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


# NOTE: mkmk's usage line is:
#   mkmk [-W WSPath] [-a|-lFW FWlist|framework [framework]|module [module]]
#        [[-g|-ge]|-w|-dev] [-u] ...
# '-a' (or an explicit framework/module name) is a MANDATORY target
# selector, not optional. Flags like '-u' (reset persistent options) and
# '-g' (debug mode) are modifiers only — passing them alone, without a
# target selector, makes mkmk print the misleading
# "must be executed in a workspace containing, at least, one framework"
# error (it's actually a missing-target error, not a real "no framework"
# problem). All whole-workspace build helpers below must therefore always
# include '-a'. Also note mkmk 5.28's documented 'mkmk -help' usage line has
# no '-n' (dry-run) or '-c' (clean) option; '-n' is rejected outright as an
# illegal option ('illegal option -- n'). '-c' is silently accepted (no
# error) but does not appear in the documented option list, so its actual
# effect is unverified/undocumented — clean_build() below therefore relies
# on '-u' (reset persistent compile options) for a full rebuild instead of
# depending on '-c'. dry_run_build() uses '-a -nobuild' (parse/graph update only,
# no actual compilation) to achieve the same effect.


def incremental_build(workspace_path: Path, timeout: int = 600) -> dict:
    """Incremental build (mkmk -u -a) — most common"""
    return build_workspace(workspace_path, "-u -a", timeout)


def full_build(workspace_path: Path, timeout: int = 1200) -> dict:
    """Full rebuild (mkmk -a)"""
    return build_workspace(workspace_path, "-a", timeout)


def clean_build(workspace_path: Path, timeout: int = 1200) -> dict:
    """Clean then build (mkmk -a -u) — '-u' resets persistent compile options"""
    return build_workspace(workspace_path, "-a -u", timeout)


def debug_build(workspace_path: Path, timeout: int = 600) -> dict:
    """Debug mode build (mkmk -a -g)"""
    return build_workspace(workspace_path, "-a -g", timeout)


def dry_run_build(workspace_path: Path, timeout: int = 60) -> dict:
    """Dry run — update mkmk data/graph without compiling (mkmk -a -nobuild).
    mkmk has no '-n' flag; '-nobuild' is the real equivalent."""
    return build_workspace(workspace_path, "-a -nobuild", timeout)


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
    result = _exec_build_cmd(cmd, workspace_path)
    # Exit code 5 means already configured — non-fatal
    if result.get("status") == "failed" and result.get("exit_code") == 5:
        result["status"] = "success"
        result["message"] = "Prerequisite already configured"
        result["exit_code"] = 0
    return result


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
    """Multi-threaded build (mkmk -a -j N) — '-a' is the mandatory target selector"""
    return build_workspace(workspace_path, f"-a -j {threads}", timeout)


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

    # Use NamedTemporaryFile for atomic temp file creation (P2-008 fix)
    tmpf = tempfile.NamedTemporaryFile(suffix=".tmp", prefix="mkmk_cmd_", delete=False)
    batf = tempfile.NamedTemporaryFile(suffix=".bat", prefix="mkmk_cmd_", delete=False)
    tmpfile = Path(tmpf.name); batfile = Path(batf.name)
    tmpf.close(); batf.close()  # Close handles — we'll read/write manually

    try:
        bat_content = f'@echo off\r\n{cmd_display} > "{tmpfile}" 2>&1\r\necho EXIT_CODE=%ERRORLEVEL% >> "{tmpfile}"\r\n'
        # newline="" prevents Path.write_text's default \n -> \r\n translation
        # from doubling the \r\n already embedded in bat_content, which
        # produces malformed \r\r\n line endings (see env.py build_time_command
        # for the full explanation of the corruption this caused).
        with open(batfile, "w", encoding="ascii", newline="") as bf:
            bf.write(bat_content)

        result = subprocess.run(
            ["cmd", "/c", str(batfile)],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            creationflags=0x08000000 if sys.platform == "win32" else 0,
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
        "options", nargs="?", default="-u -a", help="mkmk options (default: -u -a)"
    )
    parser.add_argument(
        "--timeout", type=int, default=600, help="Timeout in seconds (default: 600)"
    )
    # mkmk options are positional values that begin with '-'. parse_known_args
    # keeps the documented `build.py <workspace> -a` form usable without
    # requiring callers to know argparse's `--` escape convention.
    args, unknown = parser.parse_known_args()
    if unknown:
        if args.options != "-u -a" or len(unknown) != 1:
            parser.error("unrecognized arguments: " + " ".join(unknown))
        args.options = unknown[0]

    result = build_workspace(Path(args.workspace).resolve(), args.options, args.timeout)
    output_json(result, exit_code=0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
