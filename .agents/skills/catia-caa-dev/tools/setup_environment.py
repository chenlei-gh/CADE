#!/usr/bin/env python3
"""
CADE Workspace Environment Manager
===================================
Automatically configure workspace environment (CATIA paths and settings).

This replaces the manual CATIA GUI operation with automatic detection and configuration.

Note: This configures workspace ENVIRONMENT (CATIA paths), not framework PREREQUISITES
(AddPrereqComponent dependencies). For prerequisites management, use tools/prerequisites_manager.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

SKILL_ROOT = Path(__file__).resolve().parent.parent


def detect_catia_root() -> Optional[Path]:
    """
    Auto-detect CATIA installation path.

    Search order:
    1. Environment variable CATIA_ROOT
    2. Registry (Windows)
    3. Common installation paths
    """
    # Check environment variable
    if "CATIA_ROOT" in os.environ:
        p = Path(os.environ["CATIA_ROOT"])
        if validate_catia_root(p):
            return p

    # Check common paths
    common_paths = [
        r"C:\Program Files\Dassault Systemes\B28",
        r"C:\Program Files\Dassault Systemes\B29",
        r"C:\Program Files\Dassault Systemes\B30",
        r"C:\Program Files (x86)\Dassault Systemes\B28",
        r"D:\CATIA\B28",
        r"D:\CATIA\B29",
        r"E:\CATIA\B28",
    ]

    for path_str in common_paths:
        p = Path(path_str)
        if validate_catia_root(p):
            return p

    # Try registry (Windows only)
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Dassault Systemes\CATIA"
            )
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    try:
                        install_dir, _ = winreg.QueryValueEx(subkey, "InstallDir")
                        p = Path(install_dir)
                        if validate_catia_root(p):
                            return p
                    except:
                        pass
                    i += 1
                except OSError:
                    break
        except:
            pass

    return None


def validate_catia_root(path: Path) -> bool:
    """Validate if path is a valid CATIA installation root."""
    if not path.exists():
        return False

    # Check for key directories/files
    markers = [
        "CAADoc/Doc",  # CAA documentation
        "win_b64/code/bin/CNEXT.exe",  # CATIA executable
        "intel_a/code/bin/CNEXT.exe",  # Alternative architecture
    ]

    return any((path / marker).exists() for marker in markers)


def find_cnext_exe(catia_root: Path) -> Optional[Path]:
    """Find CNEXT.exe in CATIA installation."""
    candidates = [
        catia_root / "win_b64/code/bin/CNEXT.exe",
        catia_root / "intel_a/code/bin/CNEXT.exe",
    ]

    for exe in candidates:
        if exe.exists():
            return exe
    return None


def setup_workspace_environment(
    workspace: Path,
    catia_root: Optional[Path] = None,
    copy_prereq: bool = False,
    target_dir: Optional[Path] = None,
) -> dict:
    """
    Configure workspace environment (CATIA paths and settings).

    This is the programmatic equivalent of:
    CATIA > Tools > Workspace Explorer > Right-click workspace > Manage prerequisites

    Args:
        workspace: Workspace root directory
        catia_root: CATIA installation path (auto-detected if None)
        copy_prereq: Copy prerequisite files locally
        target_dir: Target directory for copied prerequisites

    Returns:
        {"status": "ok"|"error", "message": str, "config": {...}}
    """
    workspace = Path(workspace).resolve()

    if not workspace.exists():
        return {"status": "error", "message": f"Workspace not found: {workspace}"}

    # Auto-detect CATIA if not provided
    if catia_root is None:
        catia_root = detect_catia_root()
        if catia_root is None:
            return {
                "status": "error",
                "message": "CATIA installation not found. Please specify catia_root manually.",
            }

    catia_root = Path(catia_root).resolve()

    if not validate_catia_root(catia_root):
        return {"status": "error", "message": f"Invalid CATIA root: {catia_root}"}

    # Find CNEXT.exe
    cnext_exe = find_cnext_exe(catia_root)
    if cnext_exe is None:
        return {"status": "error", "message": f"CNEXT.exe not found in {catia_root}"}

    # Prepare configuration
    config = {
        "workspace": str(workspace),
        "catia_root": str(catia_root),
        "cnext_exe": str(cnext_exe),
        "copy_prereq": copy_prereq,
    }

    if copy_prereq and target_dir:
        config["target_dir"] = str(target_dir)

    # Write configuration files
    try:
        write_workspace_config(workspace, config)

        return {
            "status": "ok",
            "message": f"Workspace environment configured successfully",
            "config": config,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to write configuration: {e}"}


def write_workspace_config(workspace: Path, config: dict) -> None:
    """
    Write workspace configuration files.

    Creates:
    1. .cade_workspace.json - CADE-specific config
    2. Environment variables setup (optional)
    """
    import json

    # Write CADE config
    config_file = workspace / ".cade_workspace.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    # Write environment setup script (Windows)
    if sys.platform == "win32":
        env_script = workspace / "setup_env.bat"
        with open(env_script, "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write(f'set "CATIA_ROOT={config["catia_root"]}"\n')
            f.write(f'set "CNEXT_EXE={config["cnext_exe"]}"\n')
            f.write(f'set "WORKSPACE={config["workspace"]}"\n')
            f.write(f"echo Workspace environment configured.\n")


def get_workspace_config(workspace: Path) -> Optional[dict]:
    """Read workspace configuration."""
    import json

    config_file = workspace / ".cade_workspace.json"
    if not config_file.exists():
        return None

    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── CLI ────────────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CADE Workspace Environment Manager")
    parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Workspace directory (default: current directory)",
    )
    parser.add_argument(
        "--catia-root", help="CATIA installation path (auto-detected if not specified)"
    )
    parser.add_argument(
        "--copy-prereq", action="store_true", help="Copy prerequisite files locally"
    )
    parser.add_argument(
        "--target-dir", help="Target directory for copied prerequisites"
    )
    parser.add_argument(
        "--show", action="store_true", help="Show current configuration"
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Only detect CATIA installation (don't configure)",
    )

    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()

    # Show current config
    if args.show:
        config = get_workspace_config(workspace)
        if config:
            print("Current workspace configuration:")
            import json

            print(json.dumps(config, indent=2))
        else:
            print("No configuration found.")
        return

    # Detect only
    if args.detect:
        catia_root = detect_catia_root()
        if catia_root:
            print(f"✅ CATIA detected: {catia_root}")
            cnext = find_cnext_exe(catia_root)
            if cnext:
                print(f"✅ CNEXT.exe: {cnext}")
        else:
            print("❌ CATIA not detected")
        return

    # Configure workspace
    print(f"Configuring workspace: {workspace}")

    result = setup_workspace_prerequisites(
        workspace=workspace,
        catia_root=args.catia_root,
        copy_prereq=args.copy_prereq,
        target_dir=args.target_dir,
    )

    if result["status"] == "ok":
        print(f"✅ {result['message']}")
        print("\nConfiguration:")
        import json

        print(json.dumps(result["config"], indent=2))
        print(f"\nConfiguration saved to: {workspace}/.cade_workspace.json")
    else:
        print(f"❌ {result['message']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
