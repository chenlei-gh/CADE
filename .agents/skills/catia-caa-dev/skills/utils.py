"""
CATIA CAA Development Utilities
================================
Purpose: Common utilities for all skills
"""

import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class Logger:
    """Simple logger for skills (P2-007 fix: optional workspace-scoped logging)"""

    def __init__(self, log_file: str, workspace_root: Path = None):
        """
        Initialize logger

        Args:
            log_file: Path to log file (in logs/ directory)
            workspace_root: If provided, isolates logs per workspace
        """
        self.skill_root = Path(__file__).parent.parent
        if workspace_root:
            ws_hash = hashlib.md5(str(workspace_root.resolve()).encode()).hexdigest()[:8]
            self.log_path = self.skill_root / "logs" / ws_hash / log_file
        else:
            self.log_path = self.skill_root / "logs" / log_file
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = str(self.log_path) + ".lock"

    def _acquire_lock(self) -> bool:
        """Simple file-based lock to prevent concurrent writes (P2-007 fix)."""
        try:
            # Use O_CREAT | O_EXCL for atomic lock creation
            fd = os.open(self._lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except (OSError, FileExistsError):
            return False

    def _release_lock(self):
        try:
            os.unlink(self._lock_file)
        except OSError:
            pass

    def write(self, message: str, level: str = "INFO"):
        """Write log entry with file locking (P2-007 fix)"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"

        # Retry with lock
        waited = 0
        while not self._acquire_lock():
            import time
            time.sleep(0.01)
            waited += 0.01
            if waited > 2.0:  # Timeout after 2s
                break

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        finally:
            self._release_lock()

    def clear(self):
        """Clear log file"""
        if self.log_path.exists():
            self.log_path.unlink()


class Cache:
    """Simple cache manager for skills (P2-007 fix: optional workspace isolation)"""

    def __init__(self, cache_file: str, workspace_root: Path = None):
        """
        Initialize cache

        Args:
            cache_file: Cache filename (in cache/ directory)
            workspace_root: If provided, isolates cache per workspace
        """
        self.skill_root = Path(__file__).parent.parent
        if workspace_root:
            ws_hash = hashlib.md5(str(workspace_root.resolve()).encode()).hexdigest()[:8]
            self.cache_path = self.skill_root / "cache" / ws_hash / cache_file
        else:
            self.cache_path = self.skill_root / "cache" / cache_file
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = str(self.cache_path) + ".lock"

    def _acquire_lock(self) -> bool:
        """File lock for cache writes (P2-007 fix)."""
        try:
            fd = os.open(self._lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except (OSError, FileExistsError):
            return False

    def _release_lock(self):
        try:
            os.unlink(self._lock_file)
        except OSError:
            pass

    def save(self, data: Dict[str, Any]):
        """Save data to cache with atomic write (P2-007 fix)"""
        # Write to temp file, then rename (atomic on same filesystem)
        tmp = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.cache_path)
        except Exception:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            raise

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
        "IdentityCard.xml": framework_path / "IdentityCard" / "IdentityCard.xml",
        "Imakefile.mk": framework_path / "Imakefile.mk",
    }
    # Accept .h as fallback
    if not required["IdentityCard.xml"].exists():
        required["IdentityCard.xml"] = framework_path / "IdentityCard" / "IdentityCard.h"

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


def render_template(content: str, replacements: Optional[Dict[str, str]] = None) -> str:
    """
    Unified template rendering — single source of truth.

    Applies replacements in three passes to support multiple placeholder styles:
      1. {{Key}} — mustache/double-brace (full-line placeholders)
      2. <Key> — angle-bracket (inline placeholders)
      3. Key   — plain text (variable/identifier substitution)

    Keys are sorted by length (longest first) to prevent substring corruption.
    e.g., CommandClassName is replaced before ClassName.

    Used by both changeset.py (add_create_file) and generator.py (_replace/_render).

    Args:
        content: Template content with placeholders
        replacements: Dict mapping placeholder keys to replacement values

    Returns:
        Rendered content with all placeholders resolved
    """
    if not replacements:
        return content

    # Sort by key length descending: longer keys first to avoid substring corruption
    # e.g., CommandClassName must be replaced before ClassName
    sorted_keys = sorted(replacements.keys(), key=len, reverse=True)

    # Pass 1: {{Key}} — mustache/double-brace
    for k in sorted_keys:
        content = content.replace("{{" + k + "}}", replacements[k])

    # Pass 2: <Key> — angle-bracket
    for k in sorted_keys:
        content = content.replace(f"<{k}>", replacements[k])

    # Pass 3: Key — plain text (most aggressive, applied last)
    for k in sorted_keys:
        content = content.replace(k, replacements[k])

    return content


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
    print("\u2713 Duration formatting works")

    # Test render_template
    tmpl = "class <LongName> : public <Name> { /* {{LongName}} */ };"
    result = render_template(tmpl, {"LongName": "MyCmd", "Name": "Cmd"})
    assert "MyCmd" in result and "Cmd" in result
    assert "class MyCmd" in result
    assert "public Cmd" in result
    print("✓ render_template works")

    print("\n\u2713 All utilities working correctly")
