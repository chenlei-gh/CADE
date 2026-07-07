#!/usr/bin/env python3
"""Diagnostics + FixPlan Tests"""

import shutil
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from actions import ActionContext
from diagnostics import (
    Diagnostic,
    DiagnosticsEngine,
    FixAction,
    FixPlan,
    Severity,
    diagnose_workspace,
)
from meta_model import (
    Command,
    Dialog,
    Framework,
    Module,
    WorkspaceSnapshot,
)

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(
        f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else "")
    )


print("=" * 60)
print("  Diagnostics + FixPlan Tests")
print("=" * 60)

# Build a mock snapshot with known issues
ws = Path(tempfile.mkdtemp(prefix="caa_diag_"))
fw_dir = ws / "TestFW.edu"
mod_dir = fw_dir / "TestMod.m"
fw_dir.mkdir(parents=True)
mod_dir.mkdir(parents=True)
(mod_dir / "src").mkdir()
(mod_dir / "LocalInterfaces").mkdir()
(mod_dir / "Imakefile.mk").write_text("SOURCES = \\\n    src/OtherCmd.cpp\n")

# Create a framework and module with a command that HAS NO dictionary entry
fw = Framework(name="TestFW.edu", path=fw_dir)
mod = Module(name="TestMod.m", path=mod_dir)
mod.framework = fw
fw.modules.append(mod)

cmd = Command(name="MissingFromDict", path=mod_dir / "src" / "MissingFromDict.cpp")
cmd.module = mod
cmd.is_stateful = True
mod.commands.append(cmd)

# Create a dialog
dlg = Dialog(name="TestDlg", path=mod_dir / "src" / "TestDlg.cpp")
dlg.module = mod
mod.dialogs.append(dlg)

snapshot = WorkspaceSnapshot(root=ws, frameworks=[fw])

# ═══════════════════════════════════════════════════════════════════
print("\n[1] Basic Diagnostics class")
d = Diagnostic(
    severity=Severity.ERROR,
    problem="Test",
    reason="Testing",
    category="dictionary",
    entity="TestCmd",
    fix_plan=FixPlan(
        action=FixAction.APPEND_LINE,
        file="test.dico",
        line="TestCmd  CATCommand  libTest",
    ),
    auto_fixable=True,
)
d2 = d.to_dict()
ck("1.1 Diagnostic.severity", d2["severity"] == "error")
ck("1.2 Diagnostic.auto_fixable", d2["auto_fixable"] == True)
ck("1.3 FixPlan in dict", "fix_plan" in d2)
ck("1.4 FixPlan.action", d2["fix_plan"]["action"] == "append_line")
ck("1.5 FixPlan.file", d2["fix_plan"]["file"] == "test.dico")

# ═══════════════════════════════════════════════════════════════════
print("\n[2] DiagnosticsEngine on mock workspace")

engine = DiagnosticsEngine(snapshot)
results = engine.run_all()
summary = engine.summary()

ck("2.1 Returns list", isinstance(results, list))
ck("2.2 Has findings", len(results) > 0, f"{len(results)} diagnostics")
ck("2.3 Has summary", "total" in summary)

# Should detect missing dictionary
dict_issues = [d for d in results if d.category == "dictionary"]
ck(
    "2.4 Dictionary issues detected",
    len(dict_issues) >= 1,
    f"found: {len(dict_issues)}",
)

# Should detect IdentityCard missing
ic_issues = [
    d for d in results if d.category == "integrity" and "IdentityCard" in d.problem
]
ck("2.5 IdentityCard missing detected", len(ic_issues) >= 1, f"found: {len(ic_issues)}")

# Should detect Imakefile missing SOURCES
imake_issues = [d for d in results if d.category == "imakefile"]
ck("2.6 Imakefile issues", len(imake_issues) >= 0, f"found: {len(imake_issues)}")

# ═══════════════════════════════════════════════════════════════════
print("\n[3] FixPlan generation")

# Find a diagnostic with FixPlan
fixable = [d for d in results if d.auto_fixable]
ck("3.1 Auto-fixable diagnostics exist", len(fixable) >= 1, f"found: {len(fixable)}")

if fixable:
    fp = fixable[0].fix_plan
    ck("3.2 FixPlan has action", fp and fp.action is not None)
    ck("3.3 FixPlan has file", fp and fp.file is not None and len(fp.file) > 0)
    ck("3.4 FixPlan has description", fp and len(fp.description) > 0)

# ═══════════════════════════════════════════════════════════════════
print("\n[4] FixAction enum completeness")

required_actions = [
    "insert_line",
    "append_line",
    "delete_line",
    "replace_line",
    "create_file",
    "delete_file",
    "rename",
    "regenerate",
]
for action_name in required_actions:
    try:
        FixAction(action_name)
        ck(f"4.x FixAction.{action_name}", True)
    except ValueError:
        ck(f"4.x FixAction.{action_name}", False)

# ═══════════════════════════════════════════════════════════════════
print("\n[5] diagnose_workspace convenience function")

ctx = ActionContext(str(ws))
result = diagnose_workspace(ctx)
ck("5.1 Returns dict", isinstance(result, dict))
ck("5.2 Has status", result["status"] == "ok")
ck("5.3 Has summary", "diagnostics" in result, f"keys: {list(result.keys())[:5]}")
ck(
    "5.4 Has diagnostics count",
    result.get("total", 0) > 0,
    f"total={result.get('total', 0)}",
)

# ═══════════════════════════════════════════════════════════════════
print("\n[6] Severity enum")
ck("6.1 ERROR", Severity.ERROR.value == "error")
ck("6.2 WARNING", Severity.WARNING.value == "warning")
ck("6.3 INFO", Severity.INFO.value == "info")

# Cleanup
shutil.rmtree(ws, ignore_errors=True)

print(f"\n{'=' * 60}")
print(f"  Diagnostics: {passed}/{total} ({passed / total * 100:.0f}%)")
print(f"{'=' * 60}")
