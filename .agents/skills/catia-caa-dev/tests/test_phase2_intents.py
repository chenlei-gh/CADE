#!/usr/bin/env python3
"""Phase 2 Intent Layer tests with strict failure accounting."""

import shutil
import sys
import tempfile
import traceback
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

WORKSPACE = Path(tempfile.mkdtemp(prefix="cade_test_intents_"))
total = 0
passed = 0
failures = []


def check(label, ok, detail=""):
    global total, passed
    total += 1
    if ok:
        passed += 1
    else:
        failures.append(label)
    trailer = f" — {detail}" if detail else ""
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{trailer}")


def run_case(label, fn):
    try:
        fn()
    except Exception as exc:
        check(label, False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()


def make_workspace(root):
    fw = root / "TestFramework.edu"
    module = fw / "TestModule.m"
    for directory in [
        fw / "IdentityCard",
        fw / "CNext" / "code" / "dictionary",
        fw / "CNext" / "resources" / "msgcatalog",
        module / "src",
        module / "LocalInterfaces",
        module / "PublicInterfaces",
        module / "resources",
        root / "win_b64" / "code" / "dictionary",
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    (fw / "IdentityCard" / "IdentityCard.h").write_text(
        '#pragma once\n#include "CATBaseUnknown.h"\n', encoding="utf-8"
    )
    (fw / "Imakefile.mk").write_text("MODULES += TestModule\n", encoding="utf-8")
    (fw / "CNext" / "code" / "dictionary" / "TestFramework.dico").write_text(
        "TestFramework CNext\n", encoding="utf-8"
    )
    (module / "Imakefile.mk").write_text(
        "SOURCES =\nLINK_WITH = System\nBUILT_OBJECT_TYPE = SHARED_LIBRARY\n",
        encoding="utf-8",
    )


print("=" * 80)
print("Phase 2 Intent Layer Tests")
print("=" * 80)

try:
    make_workspace(WORKSPACE)

    from actions import ActionContext
    from changeset import ChangeSet
    from intents import create_executable_command, create_ui_dialog, expose_service
    from intents.helpers import generate_tooltip, merge_changeset

    ctx = ActionContext(WORKSPACE)
    check("public intent imports", True)

    def test_simple_command():
        result = create_executable_command(
            ctx,
            name="CalculateVolume",
            module="TestModule.m",
            framework="TestFramework",
        )
        check("simple command returns pending", result.get("status") == "pending", result.get("message", ""))
        check("simple command has changes", result.get("changeset", {}).get("total_changes", 0) > 0)
        created = result.get("changeset", {}).get("created", {})
        nls = "\n".join(value for path, value in created.items() if path.endswith("TestFramework.CATNls"))
        check("generated command uses public tooltip", "Calculate Volume" in nls, nls[:80])

    run_case("simple executable command", test_simple_command)

    def test_command_with_dialog():
        result = create_executable_command(
            ctx,
            name="DialogCmd",
            module="TestModule.m",
            framework="TestFramework",
            with_dialog=True,
        )
        check("command with dialog returns pending", result.get("status") == "pending", result.get("message", ""))
        check("default dialog name", result.get("components", {}).get("dialog") == "DialogCmdDlg")
        created = result.get("changeset", {}).get("created", {})
        check("dialog header included", any(path.endswith("DialogCmdDlg.h") for path in created))
        check("dialog source included", any(path.endswith("DialogCmdDlg.cpp") for path in created))

    run_case("command with dialog", test_command_with_dialog)

    def test_service():
        result = expose_service(
            ctx,
            component_name="TestComponent",
            module="TestModule.m",
            framework="TestFramework",
            methods=[{"name": "GetData", "params": [], "return": "HRESULT"}],
        )
        check("expose service returns pending", result.get("status") == "pending", result.get("message", ""))
        check("service interface is reported", result.get("service", {}).get("interface") == "ITestComponent")
        check("service changeset is non-empty", result.get("changeset", {}).get("total_changes", 0) > 0)

    run_case("expose service", test_service)

    def test_ui_dialog():
        result = create_ui_dialog(
            ctx,
            name="TestIntentDlg",
            module="TestModule.m",
            framework="TestFramework",
            controls=[{"type": "Editor", "name": "ValueEditor"}],
        )
        check("UI dialog returns pending", result.get("status") == "pending", result.get("message", ""))
        check("UI dialog metadata", result.get("dialog", {}).get("controls") == ["ValueEditor"])

    run_case("create UI dialog", test_ui_dialog)

    def test_validation():
        result = create_executable_command(
            ctx,
            name="BadCmd",
            module="MissingModule.m",
            framework="TestFramework",
        )
        check("missing module is rejected", result.get("status") == "error", result.get("message", ""))
        check("missing module gives alternatives", "available_modules" in result)

    run_case("parameter validation", test_validation)

    for name, expected in [
        ("CalculateVolume", "Calculate Volume"),
        ("SaveData", "Save Data"),
        ("MyCommand", "My Command"),
    ]:
        actual = generate_tooltip(name)
        check(f"generate_tooltip({name})", actual == expected, actual)

    def test_merge_helper():
        target = ChangeSet(action="target", description="target")
        source = ChangeSet(action="source", description="source")
        target.add_create(WORKSPACE / "one.txt", "one")
        source.add_create(WORKSPACE / "two.txt", "two")
        source.add_modify(WORKSPACE / "existing.txt", "new")
        merge_changeset(target, source)
        check("public merge helper keeps created files", len(target.created) == 2)
        check("public merge helper keeps modified files", len(target.modified) == 1)

    run_case("public changeset merge helper", test_merge_helper)
finally:
    shutil.rmtree(WORKSPACE, ignore_errors=True)

print("\n" + "=" * 80)
print(f"RESULTS: {passed}/{total}")
print("=" * 80)
if failures:
    print("Failures:")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)

print("\nIntent Layer implementation verified!")
sys.exit(0)
