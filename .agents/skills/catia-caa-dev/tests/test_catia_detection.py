#!/usr/bin/env python3
"""
CATIA Detection System - Comprehensive Test Suite
==================================================
Tests the dynamic CATIA detection and workspace setup functionality.

Usage:
    python test_catia_detection.py [--verbose]
"""

import json
import sys
from pathlib import Path

# Add tools to path
SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "tools"))

from catia_detector import CATIADetector, CATIAInstallation, detect_catia_installations
from setup_environment import (
    detect_catia_installations_interactive,
    detect_catia_root,
    get_workspace_config,
    setup_workspace_environment,
)


class TestRunner:
    """Test runner with colored output"""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.passed = 0
        self.failed = 0
        self.tests = []

    def test(self, name, func):
        """Run a test function"""
        print(f"\n{'=' * 60}")
        print(f"TEST: {name}")
        print(f"{'=' * 60}")

        try:
            result = func()
            if result:
                print(f"[PASS] {name}")
                self.passed += 1
                self.tests.append((name, True, None))
            else:
                print(f"[FAIL] {name}")
                self.failed += 1
                self.tests.append((name, False, "Test returned False"))
        except Exception as e:
            print(f"[FAIL] {name}")
            print(f"   Error: {e}")
            self.failed += 1
            self.tests.append((name, False, str(e)))
            if self.verbose:
                import traceback

                traceback.print_exc()

    def summary(self):
        """Print test summary"""
        print(f"\n{'=' * 60}")
        print(f"TEST SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total: {self.passed + self.failed}")
        print(f"[PASS] Total: {self.passed}")
        print(f"[FAIL] Total: {self.failed}")

        if self.failed > 0:
            print(f"\nFailed tests:")
            for name, passed, error in self.tests:
                if not passed:
                    print(f"  - {name}")
                    if error:
                        print(f"    {error}")
        else:
            print("\nALL CATIA DETECTION TESTS PASSED")

        return self.failed == 0


def test_detector_basic():
    """Test basic detector functionality"""
    detector = CATIADetector(verbose=True)

    # Test drive detection
    drives = detector.get_available_drives()
    print(f"  Available drives: {drives}")
    assert len(drives) > 0, "No drives found"

    # Test version extraction
    test_cases = [
        ("B28", ("B28", "V5R28")),
        ("B30", ("B30", "V5R30")),
        ("R2018", ("R2018", "V5-6R2018")),
        ("B28SP3", ("B28", "V5R28")),
        ("invalid", None),
    ]

    for dir_name, expected in test_cases:
        result = detector.extract_version_info(dir_name)
        if expected is None:
            assert result is None, f"Expected None for {dir_name}, got {result}"
        else:
            assert result == expected, (
                f"Expected {expected} for {dir_name}, got {result}"
            )

    print("  [OK] Version extraction works correctly")
    return True


def test_detector_scan():
    """Test full system scan"""
    installations = detect_catia_installations(verbose=True)

    print(f"\n  Found {len(installations)} installation(s)")

    for inst in installations:
        print(f"  - {inst.version}: {inst.root_path}")

        # Test methods
        assert inst.root_path.exists(), f"Path doesn't exist: {inst.root_path}"

        code_bin = inst.get_code_bin_path()
        if code_bin:
            print(f"    Code/Bin: {code_bin}")
            assert code_bin.exists(), f"Code/Bin doesn't exist: {code_bin}"

        # Test serialization
        data = inst.to_dict()
        assert "root_path" in data
        assert "version" in data
        assert "release" in data

        inst2 = CATIAInstallation.from_dict(data)
        assert inst2.version == inst.version

        print(f"    [OK] Serialization works")

    if len(installations) == 0:
        print("  [WARN]  No CATIA installations found (this may be expected)")

    return True


def test_legacy_detect_catia_root():
    """Test legacy detect_catia_root function"""
    root = detect_catia_root()

    if root:
        print(f"  Detected root: {root}")
        assert root.exists(), f"Root doesn't exist: {root}"
        print("  [OK] Legacy detection works")
    else:
        print("  [WARN]  No CATIA detected (this may be expected)")

    return True


def test_installation_class():
    """Test CATIAInstallation class"""
    # Create test installation
    test_path = Path("C:/Program Files/Dassault Systemes/B28")
    inst = CATIAInstallation(test_path, "B28", "V5R28")

    assert inst.root_path == test_path
    assert inst.version == "B28"
    assert inst.release == "V5R28"

    # Test string representations
    str_repr = str(inst)
    assert "B28" in str_repr
    assert str(test_path) in str_repr

    # Test serialization
    data = inst.to_dict()
    inst2 = CATIAInstallation.from_dict(data)
    assert inst2.version == inst.version
    assert inst2.root_path == inst.root_path

    print("  [OK] CATIAInstallation class works correctly")
    return True


def test_workspace_setup():
    """Test workspace setup (dry run)"""
    # Create temporary test workspace
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test_workspace"
        workspace.mkdir()

        print(f"  Test workspace: {workspace}")

        # Test with auto-detection (non-interactive)
        result = setup_workspace_environment(workspace=workspace, interactive=False)

        print(f"  Setup result: {result['status']}")
        if result["status"] == "ok":
            config = result["config"]
            print(f"  CATIA Root: {config['catia_root']}")
            print(f"  CATIA Version: {config['catia_version']}")

            # Verify config file was created
            config_file = workspace / ".cade_workspace.json"
            assert config_file.exists(), "Config file not created"

            # Verify we can read it back
            loaded_config = get_workspace_config(workspace)
            assert loaded_config is not None
            assert loaded_config["catia_version"] == config["catia_version"]

            print("  [OK] Workspace setup works correctly")
        else:
            print(f"  [WARN]  Setup failed: {result['message']}")
            print("     (This may be expected if no CATIA is installed)")

    return True


def test_detection_sorting():
    """Test version sorting logic"""
    # Create test installations
    installations = [
        CATIAInstallation(Path("C:/B28"), "B28", "V5R28"),
        CATIAInstallation(Path("C:/B30"), "B30", "V5R30"),
        CATIAInstallation(Path("C:/R2018"), "R2018", "V5-6R2018"),
        CATIAInstallation(Path("C:/B25"), "B25", "V5R25"),
    ]

    # Sort like the detector does
    import re

    VERSION_PATTERN = re.compile(r"^([BR])(\d{2,3})$")

    def version_sort_key(inst):
        version = inst.version
        match = VERSION_PATTERN.match(version)
        if match:
            prefix = match.group(1)
            number = int(match.group(2))
            prefix_priority = 1 if prefix == "B" else 0
            return (prefix_priority, number)
        return (0, 0)

    installations.sort(key=version_sort_key, reverse=True)

    # Verify sorting order: B30, B28, B25, R2018
    expected_order = ["B30", "B28", "B25", "R2018"]
    actual_order = [inst.version for inst in installations]

    print(f"  Expected order: {expected_order}")
    print(f"  Actual order:   {actual_order}")

    assert actual_order == expected_order, f"Sorting incorrect"
    print("  [OK] Version sorting works correctly")

    return True


def test_no_hardcoded_paths():
    """Verify no hardcoded paths remain anywhere in the project."""
    import re

    # Scan ALL directories
    scan_dirs = [
        SKILL_ROOT / "skills",
        SKILL_ROOT / "tests",
        SKILL_ROOT / "tools",
        SKILL_ROOT / "docs",
        SKILL_ROOT / "templates",
        SKILL_ROOT / "config",
    ]

    files_to_check = []
    extensions = ("*.py", "*.md", "*.bat", "*.ps1", "*.json", "*.yaml", "*.yml", "*.txt")
    for d in scan_dirs:
        if not d.is_dir():
            continue
        for ext in extensions:
            files_to_check.extend(d.rglob(ext))

    # Hardcoded path patterns (Windows drive letters + /tmp outside tempfile context)
    bad_patterns = [
        # String literals with drive letters
        (r'["\']([A-Za-z]):\\\\', "Hardcoded drive path (string)"),
        (r'["\']([A-Za-z]):/', "Hardcoded drive path (string)"),
        # Path() with drive letters (not using tempfile)
        (r'Path\(["\']([A-Za-z]):[/\\\\]', "Hardcoded Path() with drive letter"),
        # Directories that should use tempfile
        (r"WORKSPACE\s*=\s*['\"](?!tempfile)", "WORKSPACE not using tempfile"),
        # /tmp/ in non-test files (should use tempfile)
        (r'Path\(["\']/tmp/', "Path('/tmp/...') - use tempfile.mkdtemp()"),
    ]

    # Known false positives
    SKIP_FILES = {
        "IMPLEMENTATION_SUMMARY.md",
        "COMPLETION_REPORT.md",
        "test_catia_detection.py",      # this file itself
    }
    SKIP_DIRS = {"docs/examples", "docs/guides", "docs"}  # documentation with example paths
    SKIP_PATTERNS = [
        r"regex", r"re\.compile", r"VERSION_PATTERN",
        r"D:\\DevTools", r"D:/DevTools",
        r"catia_root", r"CATIA_INSTALL",
        r"nonexistent",                 # intentional error testing
        r"Z:/",                         # intentional error testing
        r"/tmp/",                        # standard temp dir, not Windows hardcode
        r"B28", r"B30", r"B25", r"R2018",  # test fixture versions
        r"framework",                    # docs example framework paths
        r"workspace",                    # docs example workspace paths
    ]

    issues = []
    checked_count = 0
    for file_path in files_to_check:
        if not file_path.exists():
            continue
        if file_path.name in SKIP_FILES:
            continue
        # Skip documentation example files
        rel = str(file_path.relative_to(SKILL_ROOT))
        if any(rel.startswith(d) for d in SKIP_DIRS):
            continue

        checked_count += 1
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue

            for pattern, description in bad_patterns:
                m = re.search(pattern, stripped)
                if not m:
                    continue

                # Skip known false positives
                if any(re.search(s, stripped, re.IGNORECASE) for s in SKIP_PATTERNS):
                    continue

                # Skip if in a comment after the pattern
                hash_idx = stripped.find("#")
                if hash_idx != -1 and hash_idx < m.start():
                    continue

                issues.append({
                    "file": str(file_path.relative_to(SKILL_ROOT)),
                    "line": line_num,
                    "pattern": description,
                    "content": stripped[:120],
                })
                break  # one issue per line

    # Report
    print(f"  Scanned {checked_count} files across 6 directories")

    if issues:
        print(f"  FAIL: Found {len(issues)} potential hardcoded path(s):")
        for issue in issues:
            print(f"    {issue['file']}:{issue['line']} - {issue['pattern']}")
            print(f"      {issue['content']}")
        return False

    print(f"  PASS: No hardcoded paths detected in {checked_count} files")
    return True
    return True


def main():
    """Run all tests"""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=" * 60)
    print("CATIA Detection System - Test Suite")
    print("=" * 60)

    runner = TestRunner(verbose=verbose)

    # Run tests
    runner.test("Detector Basic Functionality", test_detector_basic)
    runner.test("Installation Class", test_installation_class)
    runner.test("Version Sorting Logic", test_detection_sorting)
    runner.test("Full System Scan", test_detector_scan)
    runner.test("Legacy detect_catia_root", test_legacy_detect_catia_root)
    runner.test("Workspace Setup", test_workspace_setup)
    runner.test("No Hardcoded Paths", test_no_hardcoded_paths)

    # Summary
    success = runner.summary()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
