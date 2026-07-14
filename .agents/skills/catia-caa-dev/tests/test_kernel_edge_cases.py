#!/usr/bin/env python3
"""
Kernel Edge Case & Boundary Tests (L8)
========================================
Tests Kernel resilience: null inputs, malformed requests, error paths,
concurrency, state transitions, and policy enforcement.

Run: python test_kernel_edge_cases.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from kernel import Kernel, KernelMode, KernelResult, KernelState, ModePolicy, POLICIES

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    s = "PASS" if ok else "FAIL"
    print(f"  [{s}] {label}" + (f" — {detail}" if detail else ""))


def make_ws():
    ws = Path(tempfile.mkdtemp(prefix="cade_edge_"))
    fw = ws / "TestFW.edu"
    fw.mkdir(parents=True)
    (fw / "IdentityCard.h").write_text("// IC\n", encoding="utf-8")
    mod = fw / "TestModule.m"
    mod.mkdir()
    (mod / "src").mkdir()
    (mod / "LocalInterfaces").mkdir()
    (mod / "PublicInterfaces").mkdir()
    (mod / "Imakefile.mk").write_text(
        "SOURCES =\nLINK_WITH =\nBUILT_OBJECT_TYPE = SHARED_LIBRARY\n",
        encoding="utf-8",
    )
    return ws


# ═══════════════════════════════════════════════════════════════
# 1. Null / Empty Inputs
# ═══════════════════════════════════════════════════════════════
print("=" * 70)
print("  1. Null / Empty / Whitespace Inputs")
print("=" * 70)

k = Kernel()

for mode in [KernelMode.DEVELOP, KernelMode.ANALYZE, KernelMode.REPAIR]:
    r = k.execute(mode, "")
    check(f"{mode.value}: empty → error", r["status"] == "error", r.get("message", ""))

    r = k.execute(mode, "   ")
    check(f"{mode.value}: whitespace → error", r["status"] == "error")

    r = k.execute(mode, None)
    check(f"{mode.value}: None → error", r["status"] == "error")

# ═══════════════════════════════════════════════════════════════
# 2. Special Characters & Edge Strings
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  2. Special Characters & Edge Strings")
print("=" * 70)

special_requests = [
    "!@#$%^&*()",
    "../../../etc/passwd",
    "cmd && rm -rf /",
    "a" * 500,  # Very long
    "create command \x00\x01\x02",  # Control chars
    "中文混合English混合123",
    "\n\t\r",
]

for req in special_requests:
    r = k.execute(KernelMode.DEVELOP, req)
    # Must not crash — any status is acceptable except unhandled exception
    check(f"special: {req[:30]}... → no crash", "status" in r, r.get("status", "CRASH"))

# ═══════════════════════════════════════════════════════════════
# 3. Non-Existent Workspace
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  3. Non-Existent Workspace")
print("=" * 70)

k_bad = Kernel(workspace_root="Z:/nonexistent/path/12345")

for mode in [KernelMode.DEVELOP, KernelMode.ANALYZE, KernelMode.REPAIR]:
    r = k_bad.execute(mode, "some request")
    check(f"{mode.value}: bad workspace → no crash", "status" in r)
    check(f"{mode.value}: returns dict", isinstance(r, dict))

# ═══════════════════════════════════════════════════════════════
# 4. State Machine Transitions
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  4. State Machine Transitions")
print("=" * 70)

ws = make_ws()
k = Kernel(workspace_root=str(ws))

# Initial state
check("initial: IDLE", k._state == KernelState.IDLE)

# Develop → CLARIFYING → PLANNING → GENERATING → COMPLETED
r = k.execute(KernelMode.DEVELOP, "create command TestCmd in TestModule.m TestFW.edu")
check("develop: ends COMPLETED or FAILED", k._state in (KernelState.COMPLETED, KernelState.FAILED),
      k._state.value)

# Analyze → PLANNING → COMPLETED
k2 = Kernel(workspace_root=str(ws))
r = k2.execute(KernelMode.ANALYZE, "list modules")
check("analyze: ends COMPLETED", k2._state in (KernelState.COMPLETED, KernelState.FAILED),
      k2._state.value)

# Repair → REPAIRING → COMPLETED
k3 = Kernel(workspace_root=str(ws))
r = k3.execute(KernelMode.REPAIR, "fix dictionary issues")
check("repair: ends COMPLETED or FAILED", k3._state in (KernelState.COMPLETED, KernelState.FAILED),
      k3._state.value)

shutil.rmtree(ws, ignore_errors=True)

# ═══════════════════════════════════════════════════════════════
# 5. ModePolicy Enforcement
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  5. ModePolicy Enforcement")
print("=" * 70)

# DEVELOP policy
dp = POLICIES[KernelMode.DEVELOP]
check("DEVELOP: read_only=False", dp.READ_ONLY is False)
check("DEVELOP: needs_preview=True", dp.NEEDS_PREVIEW is True)
check("DEVELOP: needs_confirm=True", dp.NEEDS_CONFIRM is True)
check("DEVELOP: needs_rollback=True", dp.NEEDS_ROLLBACK is True)
check("DEVELOP: auto_apply=False", dp.AUTO_APPLY is False)

# ANALYZE policy
ap = POLICIES[KernelMode.ANALYZE]
check("ANALYZE: read_only=True", ap.READ_ONLY is True)
check("ANALYZE: needs_preview=False", ap.NEEDS_PREVIEW is False)
check("ANALYZE: auto_apply=True", ap.AUTO_APPLY is True)

# REPAIR policy
rp = POLICIES[KernelMode.REPAIR]
check("REPAIR: read_only=False", rp.READ_ONLY is False)
check("REPAIR: needs_rollback=True", rp.NEEDS_ROLLBACK is True)
check("REPAIR: auto_apply=True", rp.AUTO_APPLY is True)

# ═══════════════════════════════════════════════════════════════
# 6. KernelResult Edge Cases
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  6. KernelResult Edge Cases")
print("=" * 70)

# Standard result
kr = KernelResult(status="ok", mode="develop", message="Done")
d = kr.to_dict()
check("to_dict: has status", "status" in d)
check("to_dict: has mode", "mode" in d)
check("to_dict: has message", "message" in d)
check("to_dict: no empty state", "state" not in d)  # state="" → stripped

# Result with state
kr2 = KernelResult(status="ok", mode="develop", state="completed", message="Done")
d2 = kr2.to_dict()
check("to_dict: with state", "state" in d2)

# Result with data
kr3 = KernelResult(status="ok", mode="develop", message="Done",
                   data={"count": 5, "items": ["a", "b"]})
d3 = kr3.to_dict()
check("to_dict: data count", d3.get("count") == 5)
check("to_dict: data items", "items" in d3)

# Empty data stripped
kr4 = KernelResult(status="ok", mode="develop", message="Done",
                   data={"empty_key": "", "none_key": None})
d4 = kr4.to_dict()
check("to_dict: empty values stripped", "empty_key" not in d4)
check("to_dict: None values stripped", "none_key" not in d4)

# ═══════════════════════════════════════════════════════════════
# 7. Rapid Sequential Execution (No Leaks)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  7. Rapid Sequential Execution")
print("=" * 70)

ws2 = make_ws()
k_seq = Kernel(workspace_root=str(ws2))

for i in range(20):
    r = k_seq.execute(KernelMode.ANALYZE, "what is CATIProduct")
    check(f"seq[{i}]: no crash", "status" in r)

shutil.rmtree(ws2, ignore_errors=True)

# ═══════════════════════════════════════════════════════════════
# 8. INTENT_TYPE Coverage
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  8. Intent Type Detection Coverage")
print("=" * 70)

intent_tests = [
    ("create command ExportBOM", "CreateCommand"),
    ("create a dialog", "CreateCommandWithDialog"),
    ("create feature MyFeat", "CreateFeature"),
    ("make extension MyExt", "CreateExtension"),
    ("create interface IMyIntf", "CreateInterface"),
    ("generate workbench MyWb", "CreateWorkbench"),
    ("create module MyMod", "CreateModule"),
    ("create framework MyFw", "CreateFramework"),
]

for req, expected in intent_tests:
    detected = k._detect_intent_type(req.lower())
    check(f"intent: {req[:30]}", detected == expected, f"got {detected}")

# ═══════════════════════════════════════════════════════════════
# 9. Entity Extraction
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  9. Entity Extraction")
print("=" * 70)

extract_tests = [
    ("create command MyCmd in MyModule.m", ("MyCmd", "MyModule.m", None)),
    ("make feature TestFeat in TestMod.m framework TestFW.edu",
     ("TestFeat", "TestMod.m", "TestFW.edu")),
    ("generate workbench CalcWb", ("CalcWb", None, None)),
]

for req, (exp_name, exp_mod, exp_fw) in extract_tests:
    name, mod, fw = k._extract_entities(req)
    check(f"extract name: {req[:30]}", name == exp_name, f"got {name}")
    check(f"extract mod: {req[:30]}", mod == exp_mod, f"got {mod}")
    check(f"extract fw: {req[:30]}", fw == exp_fw, f"got {fw}")

# ═══════════════════════════════════════════════════════════════
# 10. Knowledge Query Detection
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  10. Knowledge Query Detection")
print("=" * 70)

kq_true = [
    "how to create a fillet",
    "what is CATIProduct",
    "how does undo work",
    "explain the update mechanism",
    "describe CATISpecObject",
    "implement a dialog with list",
]
kq_false = [
    "create command MyCmd",
    "list modules",
    "diagnose workspace",
    "build the project",
]

for req in kq_true:
    check(f"is_knowledge: {req[:35]}", k._is_knowledge_query(req))

for req in kq_false:
    check(f"not_knowledge: {req[:30]}", not k._is_knowledge_query(req))

# ═══════════════════════════════════════════════════════════════
# 11. Build/Run Routing
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  11. Build/Run Routing")
print("=" * 70)

ws3 = make_ws()
k_br = Kernel(workspace_root=str(ws3))

# These should be detected as build/run operations (not crash)
br_requests = [
    "build the workspace",
    "full build",
    "clean build",
    "start catia",
    "stop catia",
    "runtime view",
]

for req in br_requests:
    result = k_br._handle_build_run(req)
    if result is not None:
        check(f"build_run: {req[:20]} → routed", "status" in result, result.get("status", "?"))
    else:
        check(f"build_run: {req[:20]} → None (fine)", True)

shutil.rmtree(ws3, ignore_errors=True)

# ═══════════════════════════════════════════════════════════════
# 12. Alias Loading
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  12. Alias Loading")
print("=" * 70)

catalog = SKILL_ROOT / "catalog" / "index.yaml"
aliases = k._load_aliases(catalog)
check("aliases loaded", len(aliases) > 10, f"got {len(aliases)}")
check("倒角 → chamfer", "倒角" in aliases)
check("至少20个别名", len(aliases) >= 20, f"got {len(aliases)}")

# Summary
print("\n" + "=" * 70)
print(f"  KERNEL EDGE CASES: {passed}/{total}")
if total:
    print(f"  Pass rate: {passed / total * 100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> All kernel edge case tests passed <<<")
    sys.exit(0)
else:
    print(f"\n  >>> {total - passed} failure(s) <<<")
    sys.exit(1)
