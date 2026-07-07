"""
CATIA CAA Workspace Check Skill
================================
Purpose: Validate CAA workspace structure and configuration
Usage: python workspace.py [workspace_path]
Output: JSON with validation results
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from env import CAAEnvironment
from utils import Cache, Logger, output_json, validate_framework_structure


def check_workspace(workspace_path: Path) -> dict:
    """
    Check CAA workspace structure and configuration

    Args:
        workspace_path: Path to workspace directory

    Returns:
        Dictionary with workspace status
    """
    logger = Logger("workspace.log")
    cache = Cache("workspace.json")

    # Clear previous logs
    logger.clear()

    start_time = datetime.now()
    logger.write(f"Checking workspace: {workspace_path}")

    errors = []
    warnings = []
    frameworks_info = []

    # Validate workspace path
    if not workspace_path.exists():
        error_msg = f"Workspace path does not exist: {workspace_path}"
        logger.write(error_msg, "ERROR")
        return {
            "status": "error",
            "message": error_msg,
            "workspace": "invalid",
            "errors": [error_msg],
        }

    # Check CAA environment
    caa_env = CAAEnvironment()
    if not caa_env.initialize():
        warnings.append("CAA environment not properly configured")
        logger.write("CAA environment check failed", "WARNING")
    else:
        logger.write("CAA environment OK")

    # Find all frameworks (*.edu directories or directories with IdentityCard)
    frameworks = []

    # Pattern 1: *.edu directories
    for fw_dir in workspace_path.glob("*.edu"):
        if fw_dir.is_dir():
            frameworks.append(fw_dir)

    # Pattern 2: Directories with IdentityCard subdirectory
    for item in workspace_path.iterdir():
        if item.is_dir() and (item / "IdentityCard").exists():
            if item not in frameworks:
                frameworks.append(item)

    logger.write(f"Found {len(frameworks)} framework(s)")

    # Validate each framework
    for fw_path in frameworks:
        logger.write(f"Checking framework: {fw_path.name}")

        validation = validate_framework_structure(fw_path)

        fw_info = {
            "name": fw_path.name,
            "path": str(fw_path.relative_to(workspace_path)),
            "valid": validation["valid"],
            "missing_required": validation["missing_required"],
            "missing_optional": validation["missing_optional"],
        }

        # Count modules
        modules = []
        if (fw_path / "src").exists():
            for item in (fw_path / "src").iterdir():
                if item.is_dir():
                    modules.append(item.name)

        fw_info["module_count"] = len(modules)
        fw_info["modules"] = modules

        # Check for dictionary
        dico_path = fw_path / "CNext" / "code" / "dictionary"
        fw_info["has_dictionary"] = dico_path.exists()
        if dico_path.exists():
            dico_files = list(dico_path.glob("*.dico"))
            fw_info["dictionary_files"] = [f.name for f in dico_files]

        # Check for Imakefile.mk
        imakefile = fw_path / "Imakefile.mk"
        fw_info["has_imakefile"] = imakefile.exists()

        # Record errors
        if not validation["valid"]:
            for missing in validation["missing_required"]:
                error_msg = f"{fw_path.name}: Missing required {missing}"
                errors.append(error_msg)
                logger.write(error_msg, "ERROR")

        # Record warnings
        for missing in validation["missing_optional"]:
            warning_msg = f"{fw_path.name}: Missing optional {missing}"
            warnings.append(warning_msg)
            logger.write(warning_msg, "WARNING")

        frameworks_info.append(fw_info)

    # Check for Runtime View
    runtime_dirs = list(workspace_path.glob("**/win_b64")) + list(
        workspace_path.glob("**/intel_a")
    )
    has_runtime = len(runtime_dirs) > 0

    if has_runtime:
        logger.write(
            f"Runtime View found: {[str(d.relative_to(workspace_path)) for d in runtime_dirs]}"
        )
    else:
        warnings.append("No Runtime View found (win_b64 or intel_a)")
        logger.write("No Runtime View found", "WARNING")

    # Check for Visual Studio solution files
    vs_solutions = list(workspace_path.glob("*.sln"))
    has_vs_solution = len(vs_solutions) > 0

    if has_vs_solution:
        logger.write(f"Visual Studio solutions: {[s.name for s in vs_solutions]}")
    else:
        logger.write("No Visual Studio solution found", "INFO")

    # Determine overall status
    if errors:
        status = "invalid"
        message = f"Workspace has {len(errors)} error(s)"
    elif warnings:
        status = "warning"
        message = f"Workspace OK with {len(warnings)} warning(s)"
    else:
        status = "ok"
        message = "Workspace structure is valid"

    # Build result
    workspace_result = {
        "status": status,
        "message": message,
        "workspace": status,
        "workspace_path": str(workspace_path),
        "frameworks": len(frameworks),
        "framework_details": frameworks_info,
        "runtime": has_runtime,
        "runtime_dirs": [str(d.relative_to(workspace_path)) for d in runtime_dirs],
        "vs_solution": has_vs_solution,
        "vs_solution_files": [s.name for s in vs_solutions],
        "env_config": has_env_config,
        "errors": errors,
        "warnings": warnings,
        "timestamp": start_time.isoformat(),
    }

    # Save to cache
    cache.save(workspace_result)

    logger.write("=" * 60)
    logger.write(f"Status: {status}")
    logger.write(f"Frameworks: {len(frameworks)}")
    logger.write(f"Errors: {len(errors)}")
    logger.write(f"Warnings: {len(warnings)}")

    return workspace_result


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Check CATIA CAA workspace structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python workspace.py                  # Check current directory
  python workspace.py D:\\workspace     # Check specific workspace
        """,
    )

    parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Path to workspace directory (default: current directory)",
    )

    args = parser.parse_args()

    # Resolve workspace path
    workspace_path = Path(args.workspace).resolve()

    # Execute check
    result = check_workspace(workspace_path)

    # Output JSON
    exit_code = 0 if result["status"] in ["ok", "warning"] else 1
    output_json(result, exit_code=exit_code)


if __name__ == "__main__":
    main()
