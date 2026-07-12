#!/usr/bin/env python3
"""
E2E Scenario Integration Tests (L3-2)
======================================
End-to-end scenarios that verify the full CADE pipeline works
for real CAA development tasks. Each test creates a workspace,
runs a user request through the Kernel, and checks generated output.

These catch gaps that unit/module tests miss — when all pieces
work individually but the chain breaks in practice.
"""

import shutil, sys, tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from kernel import Kernel, KernelMode

total = passed = 0

def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


def make_workspace():
    """Create a minimal CAA workspace structure for testing."""
    ws = Path(tempfile.mkdtemp(prefix="cade_e2e_"))
    fw = ws / "TestFW.edu"
    fw.mkdir(parents=True)
    (fw / "IdentityCard.h").write_text("// IdentityCard\n", encoding="utf-8")
    mod = fw / "TestModule.m"
    mod.mkdir()
    (mod / "src").mkdir()
    (mod / "LocalInterfaces").mkdir()
    (mod / "PublicInterfaces").mkdir()
    (mod / "CNext" / "resources" / "msgcatalog").mkdir(parents=True)
    (mod / "CNext" / "code" / "dictionary").mkdir(parents=True)
    (mod / "Imakefile.mk").write_text(
        "SOURCES =\n"
        "LINK_WITH =\n"
        "BUILT_OBJECT_TYPE = SHARED_LIBRARY\n",
        encoding="utf-8",
    )
    return ws


print("=" * 60)
print("  E2E Scenario Integration Tests (L3-2)")
print("=" * 60)

# ═══════════════════════════════════════════════════════════════
# SCENARIO 1: Create a simple command
# ═══════════════════════════════════════════════════════════════
print("\n[SCENARIO 1] Create command 'MyCmd' in TestModule.m")
ws = make_workspace()
k = Kernel(workspace_root=str(ws))
r = k.execute(KernelMode.DEVELOP, "create command MyCmd in TestModule.m TestFW.edu")

ck("status is pending or ok", r["status"] in ("pending", "ok"), f"status={r['status']}")
ck("has message", "message" in r)

# Verify plan was built (full file gen requires real CAA workspace)
ck("plan built (preview present or status pending)",
   "preview" in r or r.get("status") == "pending",
   f"keys={list(r.keys())}")

shutil.rmtree(ws, ignore_errors=True)

# ═══════════════════════════════════════════════════════════════
# SCENARIO 2: BOM export with Decomposer enhancement
# ═══════════════════════════════════════════════════════════════
print("\n[SCENARIO 2] BOM export CSV right-click → Decomposer enhances")
ws = make_workspace()
k = Kernel(workspace_root=str(ws))
r = k.execute(KernelMode.DEVELOP,
              "create command ExportBOM in TestModule.m TestFW.edu")

ck("develop returns result", r["status"] in ("pending", "ok"))

# Manually trigger decomposer enhance
from requirements import RequirementsClarifier, RequirementsDecomposer, ClarificationResult
clarifier = RequirementsClarifier()
cr = clarifier.analyze("BOM export to CSV with right-click trigger")
decomposer = RequirementsDecomposer()
extras = decomposer.enhance(cr)

ck("detects product domain", cr.domain == "product")
ck("has playbooks", len(extras["playbooks"]) > 0, str(extras["playbooks"]))
ck("has capabilities", len(extras["capabilities"]) > 0, str(extras["capabilities"]))
ck("csv triggers document_export",
   "cap.document_export" in extras["capabilities"])

# Apply extras to generated module
mod = ws / "TestFW.edu" / "TestModule.m"
if mod.exists():
    plan = {"intent": {"name": "ExportBOM", "module": "TestModule.m", "framework": "TestFW.edu"}}
    applied = k._apply_extras(plan, extras)
    ck("extras applied successfully", isinstance(applied, dict))

    cpp_file = mod / "src" / "ExportBOM.cpp"
    if cpp_file.exists():
        content = cpp_file.read_text(encoding="utf-8", errors="replace")
        ck("knowledge refs in cpp", "CADE Playbooks" in content or
           "CADE Capabilities" in content)

shutil.rmtree(ws, ignore_errors=True)

# ═══════════════════════════════════════════════════════════════
# SCENARIO 3: Knowledge query via analyze()
# ═══════════════════════════════════════════════════════════════
print("\n[SCENARIO 3] Knowledge query for CAA concepts")
k = Kernel(workspace_root=".")

# UI query
r = k.execute(KernelMode.ANALYZE, "how to create a dialog with list in CAA")
data = r.get("data") or r.get("detail") or r
ck("UI knowledge returns ok", r["status"] == "ok")
ck("UI knowledge mentions ui", "ui" in str(r).lower() or "dialog" in str(r).lower())

# Part query
r = k.execute(KernelMode.ANALYZE, "how to create a fillet feature on a part")
ck("Part knowledge returns ok", r["status"] == "ok")
ck("Part knowledge mentions part", "part" in str(r).lower() or "fillet" in str(r).lower())

# Unknown should still work
r = k.execute(KernelMode.ANALYZE, "what is the meaning of life")
ck("Unknown query does not crash", r["status"] in ("ok", "error"))

# ═══════════════════════════════════════════════════════════════
# SCENARIO 4: Repair loop on empty workspace
# ═══════════════════════════════════════════════════════════════
print("\n[SCENARIO 4] Repair loop handles gracefully")
k = Kernel(workspace_root=".")
r = k.execute(KernelMode.REPAIR, "fix dictionary issues")
ck("repair returns result", r["status"] in ("no_issues", "fixed", "not_applicable"),
   f"status={r['status']}")

# ═══════════════════════════════════════════════════════════════
# SCENARIO 5: Vague intent → clarification → generation
# ═══════════════════════════════════════════════════════════════
print("\n[SCENARIO 5] Vague intent → clarification")
ws = make_workspace()
k = Kernel(workspace_root=str(ws))

r = k.execute(KernelMode.DEVELOP, "I want to make an assembly statistics tool")
ck("vague intent -> needs_clarification", r["status"] == "needs_clarification",
   f"status={r['status']}")
ck("has clarification questions",
   "questions" in str(r).lower() or "unresolved" in str(r).lower(),
   "present" if "questions" in str(r).lower() else "missing")

shutil.rmtree(ws, ignore_errors=True)

# ═══════════════════════════════════════════════════════════════
# SCENARIO 6: Version info via develop
# ═══════════════════════════════════════════════════════════════
print("\n[SCENARIO 6] Version and build routing")
k = Kernel(workspace_root=".")
r = k.execute(KernelMode.DEVELOP, "version")
ck("version returns result", r["status"] == "ok")
ck("version is 3.0.0", "3.0.0" in str(r))

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
