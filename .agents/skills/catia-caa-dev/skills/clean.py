"""
CATIA CAA Clean Skill
=====================
Purpose: Clean build artifacts (Objects directories)
Usage: python clean.py [workspace_path]
Output: JSON with clean result
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from utils import Cache, Logger, format_duration, output_json


def clean_workspace(workspace_path: Path, dry_run: bool = False) -> dict:
    """
    Clean CAA workspace build artifacts

    Args:
        workspace_path: Path to workspace or framework directory
        dry_run: If True, only report what would be deleted

    Returns:
        Dictionary with clean results
    """
    logger = Logger("clean.log")
    cache = Cache("clean.json")

    # Clear previous logs
    logger.clear()

    start_time = datetime.now()
    logger.write(f"Starting clean: {workspace_path}")
    logger.write(f"Dry run: {dry_run}")

    # Validate workspace path
    if not workspace_path.exists():
        error_msg = f"Workspace path does not exist: {workspace_path}"
        logger.write(error_msg, "ERROR")
        return {"status": "error", "message": error_msg, "cleaned": False}

    # Find all Objects directories
    objects_dirs = []
    deleted_dirs = []
    failed_dirs = []
    total_size = 0

    # Search for Objects directories (common patterns)
    patterns = ["**/Objects", "**/objects", "**/OBJ"]

    for pattern in patterns:
        for obj_dir in workspace_path.glob(pattern):
            if obj_dir.is_dir():
                # Calculate size
                try:
                    dir_size = sum(
                        f.stat().st_size for f in obj_dir.rglob("*") if f.is_file()
                    )
                    total_size += dir_size
                    objects_dirs.append(
                        {
                            "path": str(obj_dir.relative_to(workspace_path)),
                            "size_bytes": dir_size,
                            "size_mb": round(dir_size / (1024 * 1024), 2),
                        }
                    )
                except Exception as e:
                    logger.write(
                        f"Error calculating size for {obj_dir}: {e}", "WARNING"
                    )

    logger.write(f"Found {len(objects_dirs)} Objects directories")
    logger.write(f"Total size: {total_size / (1024 * 1024):.2f} MB")

    # Delete directories (if not dry run)
    if not dry_run and objects_dirs:
        for obj_info in objects_dirs:
            obj_path = workspace_path / obj_info["path"]
            try:
                logger.write(f"Deleting: {obj_path}")
                shutil.rmtree(obj_path)
                deleted_dirs.append(obj_info["path"])
            except Exception as e:
                logger.write(f"Failed to delete {obj_path}: {e}", "ERROR")
                failed_dirs.append({"path": obj_info["path"], "error": str(e)})

    # Calculate duration
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Build result
    clean_result = {
        "status": "success" if not failed_dirs else "partial",
        "message": f"Cleaned {len(deleted_dirs)} directories"
        if not dry_run
        else f"Would clean {len(objects_dirs)} directories",
        "cleaned": len(deleted_dirs) > 0 if not dry_run else False,
        "dry_run": dry_run,
        "objects_found": len(objects_dirs),
        "objects_deleted": len(deleted_dirs),
        "objects_failed": len(failed_dirs),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "directories": objects_dirs,
        "failed": failed_dirs,
        "duration": format_duration(duration),
        "workspace": str(workspace_path),
        "timestamp": start_time.isoformat(),
    }

    # Save to cache
    cache.save(clean_result)

    logger.write("=" * 60)
    logger.write(f"Status: {clean_result['status']}")
    logger.write(f"Objects found: {len(objects_dirs)}")
    logger.write(f"Objects deleted: {len(deleted_dirs)}")
    logger.write(f"Total size: {clean_result['total_size_mb']} MB")
    logger.write(f"Duration: {format_duration(duration)}")

    return clean_result


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Clean CATIA CAA build artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python clean.py                      # Clean current directory
  python clean.py D:\\workspace         # Clean specific workspace
  python clean.py --dry-run            # Preview what would be deleted
  python clean.py . --dry-run          # Preview current directory
        """,
    )

    parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Path to workspace directory (default: current directory)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be deleted without actually deleting",
    )

    args = parser.parse_args()

    # Resolve workspace path
    workspace_path = Path(args.workspace).resolve()

    # Execute clean
    result = clean_workspace(workspace_path, dry_run=args.dry_run)

    # Output JSON
    output_json(result, exit_code=0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
