"""
CATIA Installation Detector

Dynamically scans all available drives and paths to find CATIA installations.
Eliminates hardcoded paths and versions.

Author: CADE Team
Date: 2026-07-08
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CATIAInstallation:
    """Represents a detected CATIA installation"""

    def __init__(self, root_path: Path, version: str, release: str):
        self.root_path = root_path
        self.version = version  # e.g., "B28", "R2018"
        self.release = release  # e.g., "V5-6R2018", "V5R28"

    def __str__(self) -> str:
        return f"{self.root_path} ({self.version})"

    def __repr__(self) -> str:
        return f"CATIAInstallation(root={self.root_path}, version={self.version})"

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for JSON serialization"""
        return {
            "root_path": str(self.root_path),
            "version": self.version,
            "release": self.release,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "CATIAInstallation":
        """Create from dictionary"""
        return cls(
            root_path=Path(data["root_path"]),
            version=data["version"],
            release=data["release"],
        )

    def get_code_bin_path(self) -> Optional[Path]:
        """Get the intel_a/code/bin path for AddPrereqComponent"""
        code_bin = self.root_path / "intel_a" / "code" / "bin"
        if code_bin.exists():
            return code_bin

        # Try alternative architectures
        for arch in ["win_b64", "win64", "amd64_win64"]:
            code_bin = self.root_path / arch / "code" / "bin"
            if code_bin.exists():
                return code_bin

        return None


class CATIADetector:
    """Detects CATIA installations across all drives and paths"""

    # Common base paths to search (relative to drive root)
    SEARCH_PATTERNS = [
        r"Program Files\Dassault Systemes",
        r"Program Files (x86)\Dassault Systemes",
        r"CATIA",
        r"DS\CATIA",
        r"Dassault Systemes",
        r"CAA\CATIA",
    ]

    # Version patterns to match (B20-B99, R20-R99, R2018-R2099)
    VERSION_PATTERN = re.compile(r"^([BR](\d{2,4}))(?:[^\d]|$)")

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._log_buffer = []

    def _log(self, message: str):
        """Internal logging"""
        if self.verbose:
            print(f"  {message}")
        self._log_buffer.append(message)

    def get_available_drives(self) -> List[str]:
        """Get all available drive letters (C-Z)"""
        drives = []
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                drives.append(drive_path)
        return drives

    def validate_catia_root(self, path: Path) -> bool:
        """
        Validate if a path is a valid CATIA root directory.
        Checks for presence of CNext directory structure.
        """
        if not path.exists() or not path.is_dir():
            return False

        # Check for characteristic CATIA directories
        indicators = [
            path / "CNext",
            path / "intel_a",
            path / "win_b64",
            path / "code",
        ]

        # At least one indicator must exist
        return any(indicator.exists() for indicator in indicators)

    def extract_version_info(self, dir_name: str) -> Optional[Tuple[str, str]]:
        """
        Extract version and release info from directory name.
        Returns (version, release) or None if not a valid version.

        Examples:
            "B28" -> ("B28", "V5R28")
            "R2018" -> ("R2018", "V5-6R2018")
            "B30SP3" -> ("B30", "V5R30")
        """
        match = self.VERSION_PATTERN.match(dir_name)
        if match:
            version = match.group(1)  # Full version string (B28, R2018, etc.)
            prefix = version[0]  # B or R
            number = version[1:]  # 28, 2018, etc.

            if prefix == "B":
                release = f"V5R{number}"
            else:  # R
                release = f"V5-6R{number}"

            return (version, release)

        return None

    def scan_directory(self, base_path: Path) -> List[CATIAInstallation]:
        """Scan a base directory for CATIA installations"""
        installations = []

        if not base_path.exists() or not base_path.is_dir():
            return installations

        try:
            for entry in base_path.iterdir():
                if not entry.is_dir():
                    continue

                # Check if directory name matches version pattern
                version_info = self.extract_version_info(entry.name)
                if not version_info:
                    continue

                version, release = version_info

                # Validate it's actually a CATIA installation
                if self.validate_catia_root(entry):
                    installation = CATIAInstallation(entry, version, release)
                    installations.append(installation)
                    self._log(f"Found: {installation}")

        except PermissionError:
            self._log(f"Permission denied: {base_path}")
        except Exception as e:
            self._log(f"Error scanning {base_path}: {e}")

        return installations

    def scan_all(self) -> List[CATIAInstallation]:
        """
        Scan all drives and common paths for CATIA installations.
        Returns sorted list (newest version first).
        """
        if self.verbose:
            print("[SCAN] Scanning for CATIA installations...")

        all_installations = []
        drives = self.get_available_drives()

        self._log(f"Scanning drives: {', '.join(drives)}")

        for drive in drives:
            for pattern in self.SEARCH_PATTERNS:
                search_path = Path(drive) / pattern
                installations = self.scan_directory(search_path)
                all_installations.extend(installations)

        # Sort by version (B30 > B28, R2020 > R2018)
        def version_sort_key(inst: CATIAInstallation) -> Tuple[int, int]:
            """Sort key: (prefix_priority, version_number)"""
            version = inst.version
            match = self.VERSION_PATTERN.match(version)
            if match:
                full_version = match.group(1)  # e.g., "B28", "R2018"
                prefix = full_version[0]  # B or R
                number = int(full_version[1:])  # 28, 2018, etc.
                # B versions have higher priority than R versions
                prefix_priority = 1 if prefix == "B" else 0
                return (prefix_priority, number)
            return (0, 0)

        all_installations.sort(key=version_sort_key, reverse=True)

        if self.verbose:
            if all_installations:
                print(f"[OK] Found {len(all_installations)} CATIA installation(s)")
            else:
                print("[FAIL] No CATIA installations found")

        return all_installations

    def get_logs(self) -> List[str]:
        """Get all logged messages"""
        return self._log_buffer


def detect_catia_installations(verbose: bool = False) -> List[CATIAInstallation]:
    """
    Convenience function to detect all CATIA installations.

    Args:
        verbose: Print progress messages

    Returns:
        List of CATIAInstallation objects, sorted by version (newest first)
    """
    detector = CATIADetector(verbose=verbose)
    return detector.scan_all()


if __name__ == "__main__":
    # Test the detector
    print("CATIA Installation Detector - Test Mode\n")
    installations = detect_catia_installations(verbose=True)

    if installations:
        print("\n[LIST] Detected Installations:")
        for i, inst in enumerate(installations, 1):
            code_bin = inst.get_code_bin_path()
            print(f"\n[{i}] {inst.version}")
            print(f"    Path: {inst.root_path}")
            print(f"    Release: {inst.release}")
            print(f"    Code/Bin: {code_bin if code_bin else 'Not found'}")
    else:
        print("\n[WARN]  No CATIA installations detected")
        print("    Please install CATIA or check installation paths")
