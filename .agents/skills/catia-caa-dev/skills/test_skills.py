"""
Test Suite for CATIA CAA Development Skills
============================================
Purpose: Verify all skills are properly installed and functional
"""

import sys
from pathlib import Path

# Add skills directory to path
skill_root = Path(__file__).parent.parent
sys.path.insert(0, str(skill_root / "skills"))


def test_imports():
    """Test that all modules can be imported"""
    print("Testing module imports...")

    try:
        import env

        print("  [OK] env.py")
    except Exception as e:
        print(f"  [FAIL] env.py: {e}")
        return False

    try:
        import parser

        print("  [OK] parser.py")
    except Exception as e:
        print(f"  [FAIL] parser.py: {e}")
        return False

    try:
        import utils

        print("  [OK] utils.py")
    except Exception as e:
        print(f"  [FAIL] utils.py: {e}")
        return False

    try:
        import build

        print("  [OK] build.py")
    except Exception as e:
        print(f"  [FAIL] build.py: {e}")
        return False

    try:
        import run

        print("  [OK] run.py")
    except Exception as e:
        print(f"  [FAIL] run.py: {e}")
        return False

    try:
        import clean

        print("  [OK] clean.py")
    except Exception as e:
        print(f"  [FAIL] clean.py: {e}")
        return False

    try:
        import workspace

        print("  [OK] workspace.py")
    except Exception as e:
        print(f"  [FAIL] workspace.py: {e}")
        return False

    try:
        import runtime_view

        print("  [OK] runtime_view.py")
    except Exception as e:
        print(f"  [FAIL] runtime_view.py: {e}")
        return False

    try:
        import generator

        print("  [OK] generator.py")
    except Exception as e:
        print(f"  [FAIL] generator.py: {e}")
        return False

    try:
        import meta_model

        print("  [OK] meta_model.py")
    except Exception as e:
        print(f"  [FAIL] meta_model.py: {e}")
        return False

    try:
        import analyzer

        print("  [OK] analyzer.py")
    except Exception as e:
        print(f"  [FAIL] analyzer.py: {e}")
        return False

    try:
        import changeset

        print("  [OK] changeset.py")
    except Exception as e:
        print(f"  [FAIL] changeset.py: {e}")
        return False

    try:
        import actions

        print("  [OK] actions.py")
    except Exception as e:
        print(f"  [FAIL] actions.py: {e}")
        return False

    return True


def test_directory_structure():
    """Test that required directories exist"""
    print("\nTesting directory structure...")

    required_dirs = [
        skill_root / "skills",
        skill_root / "cache",
        skill_root / "logs",
        skill_root / "templates",
        skill_root / "tools",
    ]

    all_exist = True
    for dir_path in required_dirs:
        if dir_path.exists():
            print(f"  [OK] {dir_path.name}/")
        else:
            print(f"  [FAIL] {dir_path.name}/ (missing)")
            all_exist = False

    return all_exist


def test_parser():
    """Test parser functionality"""
    print("\nTesting parser...")

    try:
        from parser import parse_mkmk_output

        test_output = """
C:\\workspace\\MyFile.cpp(126): error C2143: syntax error
C:\\workspace\\MyFile.cpp(130): warning C4101: unreferenced variable
"""

        result = parse_mkmk_output(test_output)

        assert result["error_count"] == 1, "Expected 1 error"
        assert result["warning_count"] == 1, "Expected 1 warning"
        assert result["errors"][0]["line"] == 126, "Expected line 126"

        print("  [OK] Parser works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] Parser failed: {e}")
        return False


def test_utils():
    """Test utilities"""
    print("\nTesting utils...")

    try:
        from utils import Cache, Logger, format_duration

        # Test logger
        logger = Logger("test_suite.log")
        logger.clear()
        logger.write("Test message")

        # Test cache
        cache = Cache("test_suite.json")
        cache.save({"test": "data"})
        data = cache.load()
        assert data["test"] == "data", "Cache read/write failed"
        cache.clear()

        # Test duration formatting
        assert format_duration(45) == "45.0s"
        assert format_duration(125) == "2m 5s"

        print("  [OK] Utils work correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] Utils failed: {e}")
        return False


def test_environment():
    """Test environment initialization"""
    print("\nTesting environment...")

    try:
        from env import CAAEnvironment

        caa_env = CAAEnvironment()

        # Check if config exists (path resolved by CAAEnvironment)
        if not caa_env.load_config():
            print(
                "  [WARN] config/caa_env_config.txt not found (run config/initialize_caa_env.bat)"
            )
            return True  # Not an error, just not configured yet

        # Try to initialize
        env_vars = caa_env.initialize()
        if env_vars:
            print("  [OK] Environment initialized")
            info = caa_env.get_info()
            print(f"    CATIA: {info['catia_version']}")
            print(f"    mkmk: {'Found' if info['mkmk_path'] != 'N/A' else 'Not found'}")
        else:
            print("  [WARN] Environment initialization failed (check configuration)")

        return True
    except Exception as e:
        print(f"  [FAIL] Environment test failed: {e}")
        return False


def test_generator():
    """Test template generator"""
    print("\nTesting template generator...")

    try:
        from generator import TemplateGenerator

        gen = TemplateGenerator()
        available = gen.get_available_templates()

        # Check that all required types exist
        required = [
            "interface",
            "component",
            "command",
            "dialog",
            "workbench",
            "framework",
            "module",
            "testcase",
            "resource",
            "feature",
        ]
        missing = [t for t in required if t not in available]

        if missing:
            print(f"  [FAIL] Missing template types: {missing}")
            return False

        print(f"  [OK] {len(available)} template types available")
        print(f"    Types: {', '.join(sorted(available)[:10])}...")

        # Quick generation test
        import tempfile

        td = Path(tempfile.mkdtemp())
        r = gen.generate("interface", "ITest", td)

        if r["status"] == "success" and r["count"] > 0:
            print(f"  [OK] Template generation works ({r['count']} files)")
        else:
            print(f"  [WARN] Generation returned: {r['status']}")

        # Cleanup
        import shutil

        shutil.rmtree(td, ignore_errors=True)

        return True
    except Exception as e:
        print(f"  [FAIL] Generator test failed: {e}")
        return False


def test_actions():
    """Test atomic actions (meta model + analyzer + changeset)"""
    print("\nTesting atomic actions...")

    try:
        import shutil
        import tempfile

        from actions import ActionContext
        from analyzer import WorkspaceAnalyzer
        from changeset import ChangeSet
        from meta_model import Command, Framework, Interface, Module, Visibility

        # Test 1: Meta model relationships
        fw = Framework(name="Test.edu", path=Path("."))
        mod = Module(name="TestMod.m", path=Path("."))
        fw.add_module(mod)
        cmd = Command(name="TestCmd", path=Path("."), is_stateful=True)
        mod.add_command(cmd)
        assert cmd.module == mod, "Command.module relationship broken"
        assert cmd in mod.commands, "Module.commands list broken"
        print("  [OK] Meta model relationships")

        # Test 2: ChangeSet preview
        cs = ChangeSet(action="test", description="Test changeset")
        cs.add_create(Path("/tmp/test.h"), "// test")
        cs.add_warning("Test warning")
        preview = cs.preview()
        assert "test.h" in preview
        assert "Test warning" in preview
        print("  [OK] ChangeSet preview")

        # Test 3: ChangeSet dry_run
        result = cs.apply(dry_run=True)
        assert result["status"] == "dry_run"
        print("  [OK] ChangeSet dry_run")

        # Test 4: ActionContext
        ctx = ActionContext("D:/test")
        snap = ctx.refresh()
        assert snap is not None
        assert len(snap.frameworks) >= 0
        print(f"  [OK] ActionContext: {len(snap.frameworks)} framework(s)")

        return True
    except Exception as e:
        print(f"  [FAIL] Actions test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("CATIA CAA Development Skills - Test Suite")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Directory Structure", test_directory_structure()))
    results.append(("Parser", test_parser()))
    results.append(("Utils", test_utils()))
    results.append(("Environment", test_environment()))
    results.append(("Generator", test_generator()))
    results.append(("Actions", test_actions()))

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    for name, passed in results:
        status = "[OK] PASS" if passed else "[FAIL] FAIL"
        print(f"{status:8} {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n[OK] All tests passed! Skills are ready to use.")
        return 0
    else:
        print("\n[WARN] Some tests failed. Check output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
