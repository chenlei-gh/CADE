#!/usr/bin/env python3
"""
E2E Integration Tests (L3)
============================
Merged from test_e2e_workflow.py + test_e2e_scenarios.py.

Tests the complete CADE pipeline at two levels:
  Part A — Kernel 3-mode scenarios (develop/analyze/repair)
  Part B — Low-level actions.py compatibility
"""

import shutil, sys, tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from kernel import Kernel, KernelMode
from requirements import RequirementsClarifier, RequirementsDecomposer, ClarificationResult

total = passed = 0
def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


def make_workspace():
    ws = Path(tempfile.mkdtemp(prefix="cade_e2e_"))
    fw = ws / "TestFW.edu"
    fw.mkdir(parents=True)
    (fw / "IdentityCard.h").write_text("// IdentityCard\n", encoding="utf-8")
    mod = fw / "TestModule.m"
    mod.mkdir()
    (mod / "src").mkdir()
    (mod / "LocalInterfaces").mkdir()
    (mod / "PublicInterfaces").mkdir()
    (mod / "CNext/resources/msgcatalog").mkdir(parents=True)
    (mod / "CNext/code/dictionary").mkdir(parents=True)
    (mod / "Imakefile.mk").write_text(
        "SOURCES =\nLINK_WITH =\nBUILT_OBJECT_TYPE = SHARED_LIBRARY\n",
        encoding="utf-8",
    )
    return ws


print("=" * 60)
print("  E2E Integration Tests (L3)")
print("=" * 60)

# ═══════════════════════════════════════════════════════════════
# PART A: Kernel 3-mode scenarios
# ═══════════════════════════════════════════════════════════════
print("\n--- PART A: Kernel 3-Mode Scenarios ---")

print("\n[A1] Create command via Kernel")
ws = make_workspace()
k = Kernel(workspace_root=str(ws))
r = k.execute(KernelMode.DEVELOP, "create command MyCmd in TestModule.m TestFW.edu")
ck("returns pending", r["status"] == "pending", r["status"])
ck("has preview", "preview" in r or "extras_applied" in r)
shutil.rmtree(ws, ignore_errors=True)

print("\n[A2] BOM export → Decomposer enhancement")
ws = make_workspace()
k = Kernel(workspace_root=str(ws))
r = k.execute(KernelMode.DEVELOP, "create command ExportBOM in TestModule.m TestFW.edu")
clarifier = RequirementsClarifier()
cr = clarifier.analyze("BOM export to CSV with right-click trigger")
decomposer = RequirementsDecomposer()
extras = decomposer.enhance(cr)
ck("domain=product", cr.domain == "product")
ck("has playbooks", len(extras["playbooks"]) > 0)
ck("has capabilities", len(extras["capabilities"]) > 0)
mod = ws / "TestFW.edu" / "TestModule.m"
if mod.exists():
    applied = k._apply_extras({"intent": {"name": "ExportBOM", "module": "TestModule.m", "framework": "TestFW.edu"}}, extras)
    ck("extras applied", isinstance(applied, dict))
shutil.rmtree(ws, ignore_errors=True)

print("\n[A3] Knowledge queries")
k = Kernel(workspace_root=".")
for label, query, expected_keyword in [
    ("ui", "how to create a dialog with list", "ui"),
    ("part", "how to create a fillet feature", "part"),
    ("product", "how to export BOM from assembly", "product"),
    ("undo", "how does CATIA undo redo work", "ok"),
]:
    r = k.execute(KernelMode.ANALYZE, query)
    ck(f"knowledge {label} → ok", r["status"] == "ok", r["status"])

print("\n[A4] Repair loop handles empty workspace")
r = k.execute(KernelMode.REPAIR, "fix dictionary issues")
ck("repair → no_issues", r["status"] == "no_issues", r["status"])

print("\n[A5] Vague intent → clarification")
r = k.execute(KernelMode.DEVELOP, "I want to make an assembly statistics tool")
ck("needs_clarification", r["status"] == "needs_clarification", r["status"])

print("\n[A6] Version and build routing")
r = k.execute(KernelMode.DEVELOP, "version")
ck("version → ok", r["status"] == "ok")

# ═══════════════════════════════════════════════════════════════
# PART B: Low-level actions.py compatibility
# ═══════════════════════════════════════════════════════════════
print("\n--- PART B: Actions Layer ---")

ws = make_workspace()
from actions import ActionContext, analyze_workspace, create_command, delete_command, list_modules, list_commands
ctx = ActionContext(str(ws))

print("\n[B1] Workspace analysis")
r = analyze_workspace(ctx)
ck("analyze → ok", r["status"] == "ok")

print("\n[B2] List modules")
r = list_modules(ctx)
ck("list_modules → ok", r["status"] == "ok")

print("\n[B3] List commands")
r = list_commands(ctx)
ck("list_commands → ok", r["status"] == "ok")

print("\n[B4] Preview create command")
r = create_command(ctx, name="E2ETest", module="TestModule.m", framework="TestFW.edu")
ck("create → pending", r["status"] == "pending", r.get("status", "?"))
if r.get("preview"):
    ck("preview has will_create", len(r["preview"].get("will_create", [])) > 0)

print("\n[B5] Preview delete command")
r = delete_command(ctx, name="E2ETest", module="TestModule.m", framework="TestFW.edu")
# May return error if command wasn't actually created (preview mode)
ck("delete no crash", r is not None, f"status={r.get('status', '?')}")

shutil.rmtree(ws, ignore_errors=True)

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
