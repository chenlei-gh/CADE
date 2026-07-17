#!/usr/bin/env python3
"""
CADE Real-World UI Test — Complete Scenario
=============================================
Full pipeline: workspace → develop → analyze → repair → multi-intent
Tests all 3 Kernel modes with CatalogIndex, aliases, decomposer, verifier.
"""

import shutil
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from changeset import ChangeSet
from kernel import Kernel, KernelMode

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" +
          (f" — {detail}" if detail else ""))


def make_workspace(base: Path) -> Path:
    """Create a complete CAA workspace structure."""
    ws = base
    fw = ws / "TestUI.edu"
    (fw / "IdentityCard").mkdir(parents=True)
    (fw / "IdentityCard" / "IdentityCard.h").write_text(
        '#pragma once\n#include "CATBaseUnknown.h"\n', encoding="utf-8")
    (fw / "Imakefile.mk").write_text(
        'SOURCES =\nLINK_WITH = System ObjectModelerBase\n', encoding="utf-8")
    (fw / "CNext" / "code" / "dictionary").mkdir(parents=True)
    (fw / "CNext" / "resources" / "msgcatalog").mkdir(parents=True)
    (fw / "CNext" / "resources" / "graphic" / "icons" / "normal").mkdir(parents=True)
    (fw / "CNext" / "code" / "dictionary" / "TestUI.dico").write_text(
        'TestUI CNext\n', encoding="utf-8")
    (ws / "win_b64" / "code" / "dictionary").mkdir(parents=True)

    mod = fw / "TestModule.m"
    for sub in ["src", "LocalInterfaces", "PublicInterfaces",
                "CNext/code/dictionary", "CNext/resources/msgcatalog"]:
        (mod / sub).mkdir(parents=True)
    (mod / "Imakefile.mk").write_text(
        "SOURCES =\nLINK_WITH = System\n"
        "BUILT_OBJECT_TYPE = SHARED_LIBRARY\n", encoding="utf-8")
    return ws


print("=" * 65)
print("  CADE v3.2.1 — Real-World UI Scenario Test")
print("=" * 65)

# ═══════════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════════
ws = Path(tempfile.mkdtemp(prefix="cade_test_"))
ws = make_workspace(ws)
k = Kernel(workspace_root=str(ws))

print(f"\n[Workspace] {ws}")
print(f"   Framework: TestUI.edu/TestModule.m")

# ═══════════════════════════════════════════════════════════════
# SECTION 1: ANALYZE — Knowledge Queries (CatalogIndex)
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("  SECTION 1: ANALYZE — Knowledge Queries")
print("=" * 65)

tests = {
    "中文单字": [("对话框", 5), ("装配", 3), ("倒角", 2), ("工程图", 3)],
    "中文短语": [("如何创建对话框", 5), ("装配统计工具怎么做", 3)],
    "英文查询": [("how to create a dialog", 5), ("what is CATIProduct", 1)],
    "复合别名": [("选择", 3), ("颜色", 1), ("标注", 3), ("约束", 3)],
}

for group, cases in tests.items():
    print(f"\n  [{group}]")
    for q, min_refs in cases:
        r = k.execute(KernelMode.ANALYZE, q)
        refs = len(r.get("references", []))
        check(f"{q}", refs >= min_refs, f"{refs} refs (need >={min_refs})")

# ═══════════════════════════════════════════════════════════════
# SECTION 2: ANALYZE — Workspace
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("  SECTION 2: ANALYZE — Workspace & Diagnostics")
print("=" * 65)

r = k.execute(KernelMode.ANALYZE, "analyze workspace")
check("analyze workspace → ok", r["status"] == "ok")

r = k.execute(KernelMode.ANALYZE, "diagnose workspace")
check("diagnose → ok", r["status"] in ("ok", "pending"))

# ═══════════════════════════════════════════════════════════════
# SECTION 3: DEVELOP — Single Intents
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("  SECTION 3: DEVELOP — Single Intents")
print("=" * 65)

r = k.execute(KernelMode.DEVELOP, "create command SettingsCmd in TestModule.m TestUI.edu")
check("first command → pending", r["status"] == "pending", r.get("message", "")[:60])
first_cs = ChangeSet.from_dict(r.get("changeset", {}))
first_apply = first_cs.apply(dry_run=False, workspace_root=ws)
check("first command changeset → applied", first_apply["status"] == "applied",
      "; ".join(first_apply.get("errors", []))[:100])
check("SettingsCmd header exists",
      (ws / "TestUI.edu" / "TestModule.m" / "LocalInterfaces" / "SettingsCmd.h").exists())
check("SettingsCmd source exists",
      (ws / "TestUI.edu" / "TestModule.m" / "src" / "SettingsCmd.cpp").exists())

k = Kernel(workspace_root=str(ws))
r = k.execute(KernelMode.DEVELOP, "create command ExportCmd in TestModule.m TestUI.edu")
check("second command → pending", r["status"] == "pending", r.get("message", "")[:60])
second_cs = ChangeSet.from_dict(r.get("changeset", {}))
addin_h = ws / "TestUI.edu" / "TestModule.m" / "LocalInterfaces" / "TestModuleAddin.h"
addin_cpp = ws / "TestUI.edu" / "TestModule.m" / "src" / "TestModuleAddin.cpp"
dico = ws / "TestUI.edu" / "CNext" / "code" / "dictionary" / "TestUI.dico"
shared_paths = {str(addin_h), str(addin_cpp), str(dico)}
recreated = shared_paths & set(second_cs.created)
check("second command does not recreate shared Addin/dico", not recreated,
      str(sorted(recreated)))
second_apply = second_cs.apply(dry_run=False, workspace_root=ws)
check("second command changeset → applied", second_apply["status"] == "applied",
      "; ".join(second_apply.get("errors", []))[:100])
check("ExportCmd header exists",
      (ws / "TestUI.edu" / "TestModule.m" / "LocalInterfaces" / "ExportCmd.h").exists())
check("ExportCmd source exists",
      (ws / "TestUI.edu" / "TestModule.m" / "src" / "ExportCmd.cpp").exists())
if dico.exists():
    dico_text = dico.read_text(encoding="utf-8", errors="replace")
    check("dico has one Addin registration", dico_text.count("TestModuleAddin") == 1,
          f"count={dico_text.count('TestModuleAddin')}")
else:
    check("dico has one Addin registration", False, "dico missing")

# ═══════════════════════════════════════════════════════════════
# SECTION 4: DEVELOP — Multi-Intent
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("  SECTION 4: DEVELOP — Multi-Intent Decomposition")
print("=" * 65)

r = k.execute(KernelMode.DEVELOP, "做装配统计工具，包含导出BOM和自动着色")
results = r.get("results", [])
check("multi-intent detected", len(results) >= 2, f"{len(results)} sub-intents")
for i, sub in enumerate(results[:3]):
    si = sub.get("sub_intent", {})
    check(f"  sub[{i}] has goal", bool(si.get("goal", "")),
          si.get("goal", "")[:40])

# ═══════════════════════════════════════════════════════════════
# SECTION 5: REPAIR
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("  SECTION 5: REPAIR")
print("=" * 65)

for req in ["fix dictionary issues", "fix broken references", "fix Imakefile"]:
    r = k.execute(KernelMode.REPAIR, req)
    check(f"repair: {req} → no crash", r["status"] in ("no_issues", "fixed", "pending"))

# ═══════════════════════════════════════════════════════════════
# SECTION 6: Edge Cases
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("  SECTION 6: Edge Cases")
print("=" * 65)

r = k.execute(KernelMode.DEVELOP, "")
check("develop empty → error", r["status"] == "error")

r = k.execute(KernelMode.ANALYZE, "")
check("analyze empty → error", r["status"] == "error")

r = k.execute(KernelMode.REPAIR, "")
check("repair empty → error", r["status"] == "error")

r = k.execute(KernelMode.ANALYZE, "!@#$%^&*()")
check("analyze special chars → no crash", r["status"] != "error")

k_bad = Kernel(workspace_root="Z:/nonexistent")
r = k_bad.execute(KernelMode.DEVELOP, "create command Test in TestModule.m TestFW.edu")
check("bad workspace → no crash", r["status"] in ("ok", "error", "pending"))

# ═══════════════════════════════════════════════════════════════
# SECTION 7: CatalogIndex Direct Tests
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("  SECTION 7: CatalogIndex Direct")
print("=" * 65)

from catalog import CatalogIndex
catalog = CatalogIndex.load(SKILL)

check("entries loaded", len(catalog.entries) > 50, f"{len(catalog.entries)} entries")
check("aliases loaded", len(catalog.aliases) >= 29, f"{len(catalog.aliases)} aliases")

# Search tests
for q, min_r in [("对话框", 3), ("assembly", 3), ("surface", 2), ("constraint", 2)]:
    results = catalog.search(q)
    check(f"catalog.search({q})", len(results) >= min_r, f"{len(results)} results")

# Alias match
for q, expect in [("对话框", True), ("装配体", True), ("xyz123", False)]:
    check(f"has_alias({q})", catalog.has_alias_match(q) == expect)

# ═══════════════════════════════════════════════════════════════
# CLEANUP & SUMMARY
# ═══════════════════════════════════════════════════════════════
shutil.rmtree(ws, ignore_errors=True)

print(f"\n{'='*65}")
print(f"  RESULTS: {passed}/{total} ({passed*100//max(total,1)}%)")
print("=" * 65)

if passed == total:
    print("\n  >>> ALL REAL-WORLD UI TESTS PASSED <<<")
    sys.exit(0)
else:
    print(f"\n  >>> {total - passed} FAILURE(S) <<<")
    sys.exit(1)
