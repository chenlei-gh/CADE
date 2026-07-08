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

import json
import os
import sys
from pathlib import Path
from typing import List, Optional

SKILL_ROOT = Path(__file__).resolve().parent.parent

# Import CATIA detector
try:
    from .catia_detector import CATIAInstallation, detect_catia_installations
except ImportError:
    from catia_detector import CATIAInstallation, detect_catia_installations


def detect_catia_installations_interactive(
    verbose: bool = True,
) -> List[CATIAInstallation]:
    """
    Detect all CATIA installations and return them.
    Uses the new dynamic CATIA detector (no hardcoded paths).

    Args:
        verbose: Print progress messages

    Returns:
        List of CATIAInstallation objects, sorted by version (newest first)
    """
    installations = detect_catia_installations(verbose=verbose)
    return installations


def select_catia_installation(
    installations: List[CATIAInstallation], auto_select: bool = False
) -> Optional[CATIAInstallation]:
    """
    Let user select from detected CATIA installations.

    Args:
        installations: List of detected installations
        auto_select: If True and only one installation found, select it automatically

    Returns:
        Selected CATIAInstallation or None if cancelled
    """
    if not installations:
        return None

    if len(installations) == 1 and auto_select:
        return installations[0]

    # Display options
    print("\n📋 Detected CATIA installations:")
    for i, inst in enumerate(installations, 1):
        code_bin = inst.get_code_bin_path()
        print(f"  [{i}] {inst.version} - {inst.root_path}")
        if code_bin:
            print(f"      (Code/Bin: {code_bin})")

    # User selection
    while True:
        try:
            choice = input(
                f"\nSelect CATIA version [1-{len(installations)}] (default: 1): "
            ).strip()
            if not choice:
                choice = "1"

            idx = int(choice) - 1
            if 0 <= idx < len(installations):
                return installations[idx]
            else:
                print(
                    f"❌ Invalid choice. Please enter a number between 1 and {len(installations)}."
                )
        except ValueError:
            print("❌ Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            return None


def detect_catia_root() -> Optional[Path]:
    """
    Auto-detect CATIA installation path (legacy function for compatibility).
    Now uses the new dynamic detector.

    Search order:
    1. Environment variable CATIA_ROOT
    2. Dynamic detection across all drives
    """
    # Check environment variable first
    if "CATIA_ROOT" in os.environ:
        p = Path(os.environ["CATIA_ROOT"])
        if validate_catia_root(p):
            return p

    # Use new detector
    installations = detect_catia_installations(verbose=False)
    if installations:
        # Return the newest version (first in sorted list)
        return installations[0].root_path

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
    catia_version: Optional[str] = None,
    interactive: bool = True,
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
        catia_version: Specific CATIA version to use (e.g., "B30")
        interactive: Allow user to select from multiple installations
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
        # Detect all installations
        installations = detect_catia_installations_interactive(verbose=interactive)

        if not installations:
            return {
                "status": "error",
                "message": "CATIA installation not found. Please install CATIA or specify catia_root manually.",
            }

        # Filter by version if specified
        if catia_version:
            installations = [
                inst for inst in installations if inst.version == catia_version
            ]
            if not installations:
                return {
                    "status": "error",
                    "message": f"CATIA version {catia_version} not found.",
                }

        # Select installation
        if interactive:
            selected = select_catia_installation(
                installations, auto_select=(len(installations) == 1)
            )
            if selected is None:
                return {"status": "error", "message": "No CATIA version selected."}
        else:
            selected = installations[0]  # Use newest

        catia_root = selected.root_path
        catia_version = selected.version
    else:
        catia_root = Path(catia_root).resolve()

        if not validate_catia_root(catia_root):
            return {"status": "error", "message": f"Invalid CATIA root: {catia_root}"}

        # Extract version from path if not provided
        if not catia_version:
            import re

            match = re.search(r"[BR]\d{2,3}", catia_root.name)
            catia_version = match.group(0) if match else "Unknown"

    # Find CNEXT.exe
    cnext_exe = find_cnext_exe(catia_root)
    if cnext_exe is None:
        return {"status": "error", "message": f"CNEXT.exe not found in {catia_root}"}

    # Get code/bin path for AddPrereqComponent
    code_bin_path = None
    for arch in ["intel_a", "win_b64", "win64", "amd64_win64"]:
        candidate = catia_root / arch / "code" / "bin"
        if candidate.exists():
            code_bin_path = candidate
            break

    # Prepare configuration
    config = {
        "workspace": str(workspace),
        "catia_root": str(catia_root),
        "catia_version": catia_version,
        "cnext_exe": str(cnext_exe),
        "code_bin_path": str(code_bin_path) if code_bin_path else None,
        "copy_prereq": copy_prereq,
    }

    if copy_prereq and target_dir:
        config["target_dir"] = str(target_dir)

    # Write configuration files
    try:
        write_workspace_config(workspace, config)

        return {
            "status": "ok",
            "message": f"Workspace environment configured with CATIA {catia_version}",
            "config": config,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to write configuration: {e}"}


def write_workspace_config(workspace: Path, config: dict) -> None:
    """
    Write workspace configuration files.

    Creates:
    1. .cade_workspace.json - CADE-specific config
    2. setup_env.bat - Environment variables setup (Windows)
    """
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
            f.write(f'set "CATIA_VERSION={config.get("catia_version", "Unknown")}"\n')
            f.write(f'set "CNEXT_EXE={config["cnext_exe"]}"\n')
            f.write(f'set "WORKSPACE={config["workspace"]}"\n')
            if config.get("code_bin_path"):
                f.write(f'set "CATIA_CODE_BIN={config["code_bin_path"]}"\n')
            f.write(
                f"echo Workspace environment configured for CATIA {config.get('catia_version', 'Unknown')}.\n"
            )


def get_workspace_config(workspace: Path) -> Optional[dict]:
    """Read workspace configuration."""
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
        installations = detect_catia_installations_interactive(verbose=True)
        if installations:
            print(f"\n✅ Found {len(installations)} CATIA installation(s)")
            for inst in installations:
                print(f"\n{inst.version}:")
                print(f"  Path: {inst.root_path}")
                print(f"  Release: {inst.release}")
                cnext = find_cnext_exe(inst.root_path)
                if cnext:
                    print(f"  CNEXT.exe: {cnext}")
                code_bin = inst.get_code_bin_path()
                if code_bin:
                    print(f"  Code/Bin: {code_bin}")
        else:
            print("❌ No CATIA installations detected")
        return

    # Configure workspace
    print(f"Configuring workspace: {workspace}")

    result = setup_workspace_environment(
        workspace=workspace,
        catia_root=args.catia_root,
        interactive=True,
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
