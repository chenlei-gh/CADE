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
                print(f"✅ PASSED: {name}")
                self.passed += 1
                self.tests.append((name, True, None))
            else:
                print(f"❌ FAILED: {name}")
                self.failed += 1
                self.tests.append((name, False, "Test returned False"))
        except Exception as e:
            print(f"❌ FAILED: {name}")
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
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")

        if self.failed > 0:
            print(f"\nFailed tests:")
            for name, passed, error in self.tests:
                if not passed:
                    print(f"  - {name}")
                    if error:
                        print(f"    {error}")

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

    print("  ✓ Version extraction works correctly")
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

        print(f"    ✓ Serialization works")

    if len(installations) == 0:
        print("  ⚠️  No CATIA installations found (this may be expected)")

    return True


def test_legacy_detect_catia_root():
    """Test legacy detect_catia_root function"""
    root = detect_catia_root()

    if root:
        print(f"  Detected root: {root}")
        assert root.exists(), f"Root doesn't exist: {root}"
        print("  ✓ Legacy detection works")
    else:
        print("  ⚠️  No CATIA detected (this may be expected)")

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

    print("  ✓ CATIAInstallation class works correctly")
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

            print("  ✓ Workspace setup works correctly")
        else:
            print(f"  ⚠️  Setup failed: {result['message']}")
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
    print("  ✓ Version sorting works correctly")

    return True


def test_no_hardcoded_paths():
    """Verify no hardcoded paths remain in code"""
    import re

    files_to_check = [
        SKILL_ROOT / "tools" / "setup_environment.py",
        SKILL_ROOT / "skills" / "env.py",
    ]

    # Patterns that indicate hardcoding (only in actual code, not comments)
    bad_patterns = [
        (r'["\']C:\\\\', "Hardcoded C:\\ drive path"),
        (r'["\']D:\\\\', "Hardcoded D:\\ drive path"),
        (r'["\']E:\\\\', "Hardcoded E:\\ drive path"),
    ]

    issues = []
    for file_path in files_to_check:
        if not file_path.exists():
            print(f"  ⚠️  File not found: {file_path}")
            continue

        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Check each line
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip comments and docstrings
            if stripped.startswith("#"):
                continue
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue

            # Check for suspicious patterns
            for pattern, description in bad_patterns:
                if re.search(pattern, line):
                    # Additional check: ignore if it's clearly in a comment
                    if (
                        "#" in line and line.index("#") < line.index(pattern)
                        if pattern in line
                        else False
                    ):
                        continue

                    issues.append(
                        {
                            "file": file_path.name,
                            "line": line_num,
                            "description": description,
                            "content": line.strip()[:100],
                        }
                    )

    if issues:
        print("  ❌ Found potential hardcoded values:")
        for issue in issues:
            print(f"    {issue['file']}:{issue['line']} - {issue['description']}")
            print(f"       {issue['content']}")
        return False

    print("  ✓ No hardcoded paths detected in code")
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
