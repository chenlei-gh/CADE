"""
CATIA CAA Development Utilities
================================
Purpose: Common utilities for all skills
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class Logger:
    """Simple logger for skills"""

    def __init__(self, log_file: str):
        """
        Initialize logger

        Args:
            log_file: Path to log file (in logs/ directory)
        """
        self.skill_root = Path(__file__).parent.parent
        self.log_path = self.skill_root / "logs" / log_file
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str, level: str = "INFO"):
        """Write log entry"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)

    def clear(self):
        """Clear log file"""
        if self.log_path.exists():
            self.log_path.unlink()


class Cache:
    """Simple cache manager for skills"""

    def __init__(self, cache_file: str):
        """
        Initialize cache

        Args:
            cache_file: Cache filename (in cache/ directory)
        """
        self.skill_root = Path(__file__).parent.parent
        self.cache_path = self.skill_root / "cache" / cache_file
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, data: Dict[str, Any]):
        """
        Save data to cache (overwrites)

        Args:
            data: Dictionary to save as JSON
        """
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self) -> Dict[str, Any]:
        """
        Load data from cache

        Returns:
            Dictionary or empty dict if not found
        """
        if not self.cache_path.exists():
            return {}

        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def clear(self):
        """Clear cache file"""
        if self.cache_path.exists():
            self.cache_path.unlink()


def output_json(data: Dict[str, Any], exit_code: int = 0):
    """
    Output JSON to stdout and exit

    Args:
        data: Dictionary to output
        exit_code: Exit code (0=success, 1=error)
    """
    print(json.dumps(data, indent=2, ensure_ascii=False))
    sys.exit(exit_code)


def output_error(message: str, details: Dict[str, Any] = None):
    """
    Output error in JSON format and exit

    Args:
        message: Error message
        details: Additional error details
    """
    error_data = {"status": "error", "message": message}
    if details:
        error_data.update(details)

    output_json(error_data, exit_code=1)


def output_success(message: str, data: Dict[str, Any] = None):
    """
    Output success in JSON format and exit

    Args:
        message: Success message
        data: Additional data
    """
    success_data = {"status": "success", "message": message}
    if data:
        success_data.update(data)

    output_json(success_data, exit_code=0)


def find_workspace_root(start_path: Path = None) -> Path:
    """
    Find CAA workspace root by looking for typical markers

    Args:
        start_path: Starting directory (defaults to cwd)

    Returns:
        Path to workspace root or current directory
    """
    current = start_path or Path.cwd()

    # Look for workspace markers
    markers = ["CNext", "IdentityCard", ".workspace"]

    # Search up to 5 levels
    for _ in range(5):
        for marker in markers:
            if (current / marker).exists():
                return current

        parent = current.parent
        if parent == current:  # Reached root
            break
        current = parent

    # Return original if not found
    return start_path or Path.cwd()


def validate_framework_structure(framework_path: Path) -> Dict[str, Any]:
    """
    Validate basic framework structure

    Args:
        framework_path: Path to framework directory

    Returns:
        Dictionary with validation results
    """
    required = {
        "IdentityCard": framework_path / "IdentityCard",
        "IdentityCard.h": framework_path / "IdentityCard" / "IdentityCard.h",
        "Imakefile.mk": framework_path / "Imakefile.mk",
    }

    optional = {
        "PublicInterfaces": framework_path / "PublicInterfaces",
        "LocalInterfaces": framework_path / "LocalInterfaces",
        "src": framework_path / "src",
        "CNext": framework_path / "CNext",
    }

    missing_required = []
    missing_optional = []

    for name, path in required.items():
        if not path.exists():
            missing_required.append(name)

    for name, path in optional.items():
        if not path.exists():
            missing_optional.append(name)

    return {
        "valid": len(missing_required) == 0,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "framework_path": str(framework_path),
    }


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "2m 35s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = int(seconds // 60)
    secs = int(seconds % 60)

    if minutes < 60:
        return f"{minutes}m {secs}s"

    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m {secs}s"


if __name__ == "__main__":
    # Test utilities
    print("Testing utilities...")

    # Test logger
    logger = Logger("test.log")
    logger.clear()
    logger.write("Test message")
    print("✓ Logger works")

    # Test cache
    cache = Cache("test.json")
    cache.save({"test": "data"})
    data = cache.load()
    assert data["test"] == "data"
    cache.clear()
    print("✓ Cache works")

    # Test duration formatting
    assert format_duration(45.5) == "45.5s"
    assert format_duration(125) == "2m 5s"
    print("✓ Duration formatting works")

    print("\n✓ All utilities working correctly")
