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

# DEVELOP mode auto-applies (backup+rollback safety, same as REPAIR) —
# see kernel.Kernel._execute_develop_plan()/_apply_changeset_dict(). The
# ChangeSet is generated AND written to disk in a single kernel.execute()
# call; there is no separate manual-apply step for callers to perform.
r = k.execute(KernelMode.DEVELOP, "create command SettingsCmd in TestModule.m TestUI.edu")
check("first command → ok (auto-applied)", r["status"] == "ok", r.get("message", "")[:60])
check("first command apply_result → applied",
      r.get("apply_result", {}).get("status") == "applied",
      "; ".join(r.get("apply_result", {}).get("errors", []))[:100])
check("SettingsCmd header exists",
      (ws / "TestUI.edu" / "TestModule.m" / "LocalInterfaces" / "SettingsCmd.h").exists())
check("SettingsCmd source exists",
      (ws / "TestUI.edu" / "TestModule.m" / "src" / "SettingsCmd.cpp").exists())

k = Kernel(workspace_root=str(ws))
r = k.execute(KernelMode.DEVELOP, "create command ExportCmd in TestModule.m TestUI.edu")
check("second command → ok (auto-applied)", r["status"] == "ok", r.get("message", "")[:60])
# The changeset dict is still attached to the result (pre-apply snapshot,
# not re-appliable) so we can inspect what it *would have* created without
# touching the filesystem again.
second_cs_dict = r.get("changeset", {})
addin_h = ws / "TestUI.edu" / "TestModule.m" / "LocalInterfaces" / "TestModuleAddin.h"
addin_cpp = ws / "TestUI.edu" / "TestModule.m" / "src" / "TestModuleAddin.cpp"
dico = ws / "TestUI.edu" / "CNext" / "code" / "dictionary" / "TestUI.dico"
shared_paths = {str(addin_h), str(addin_cpp), str(dico)}
recreated = shared_paths & set(second_cs_dict.get("created", {}))
check("second command does not recreate shared Addin/dico", not recreated,
      str(sorted(recreated)))
check("second command apply_result → applied",
      r.get("apply_result", {}).get("status") == "applied",
      "; ".join(r.get("apply_result", {}).get("errors", []))[:100])
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
# SECTION 3.5: DEVELOP — Preview Mode
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("  SECTION 3.5: DEVELOP — Preview Mode (generate but don't apply)")
print("=" * 65)

# Preview mode: ChangeSet generated but NOT applied to disk
preview_ws = Path(tempfile.mkdtemp(prefix="cade_preview_test_"))
preview_ws = make_workspace(preview_ws)
k_preview = Kernel(workspace_root=str(preview_ws))

r = k_preview.execute(KernelMode.DEVELOP, "create command PreviewCmd in TestModule.m TestUI.edu", preview=True)
check("preview → status='preview'", r["status"] == "preview", r.get("status", ""))
check("preview → preview_mode=True", r.get("preview_mode") == True)
check("preview → has changeset", bool(r.get("changeset")), "changeset key present")
check("preview → no files written",
      not (preview_ws / "TestUI.edu" / "TestModule.m" / "src" / "PreviewCmd.cpp").exists())
check("preview → no header written",
      not (preview_ws / "TestUI.edu" / "TestModule.m" / "LocalInterfaces" / "PreviewCmd.h").exists())

# Now apply the same request without preview — files should be created
r2 = k_preview.execute(KernelMode.DEVELOP, "create command PreviewCmd in TestModule.m TestUI.edu")
check("apply → status='ok'", r2["status"] == "ok", r2.get("status", ""))
check("apply → source file exists",
      (preview_ws / "TestUI.edu" / "TestModule.m" / "src" / "PreviewCmd.cpp").exists())
check("apply → header file exists",
      (preview_ws / "TestUI.edu" / "TestModule.m" / "LocalInterfaces" / "PreviewCmd.h").exists())

shutil.rmtree(preview_ws, ignore_errors=True)

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
# SECTION 8: API Registry — Knowledge-driven Whitelist
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("  SECTION 8: API Registry (whitelist)")
print("=" * 65)

from api_registry import get_registry
from verifier import CodeVerifier

registry = get_registry(SKILL)
stats = registry.stats()
check("registry loaded", stats["apis"] > 200, f"{stats['apis']} apis")
check("capability APIs indexed", stats["sources"]["capability"] >= 50,
      f"{stats['sources']['capability']} from capabilities")

# Verified real APIs (from capabilities/*.md, checked against CAADoc)
for api in ["CATCSO", "CATIProduct", "CATIGSMFactory", "CATPathElement"]:
    check(f"known API: {api}", registry.is_known_api(api))

# Fabricated APIs — documented in knowledge base as NOT existing
for fake in ["CATIUpdate", "CATIMechanicalUpdate", "CATISelectionSetFactory"]:
    check(f"fabricated API rejected: {fake}", not registry.is_known_api(fake))

# Noise anchors from framework auto-extraction must be filtered
check("noise anchor filtered", not registry.is_known_api("CATI2DCamera_22103"))

# Verifier integration: fabricated include flagged, real one passes
v = CodeVerifier()
issues = v.verify_file("src/WlTestCmd.cpp", '''
#include "WlTestCmd.h"
#include "CATStateCommand.h"
#include "CATIUpdate.h"
CATCreateClass(WlTestCmd);
''')
unknown = [i for i in issues if "Unknown CAA header" in i.message]
check("fabricated include flagged", len(unknown) == 1,
      f"{len(unknown)} flagged")
check("flag is CATIUpdate.h", any("CATIUpdate" in i.message for i in unknown))
check("suggestion offered", any("Did you mean" in i.message for i in unknown))

# Local + whitelisted includes must NOT be flagged
v2 = CodeVerifier()
issues2 = v2.verify_file("src/WlLocalCmd.cpp", '''
#include "WlLocalCmd.h"
#include "CATStateCommand.h"
#include "CATCSO.h"
CATCreateClass(WlLocalCmd);
''')
bad = [i for i in issues2 if "Unknown CAA header" in i.message]
check("local + whitelisted includes pass", len(bad) == 0, f"{len(bad)} flagged")

# Kernel develop → knowledge_refs traceability
r = k.execute(KernelMode.DEVELOP, "create command RefsCmd in TestModule.m TestUI.edu", preview=True)
check("develop attaches knowledge_refs", "knowledge_refs" in r,
      f"keys: {sorted(r.keys())[:8]}")

# ═══════════════════════════════════════════════════════════════
# SECTION 9: UI Failure Patterns — static lint via repair pipeline
# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("  SECTION 9: UI Failure Patterns (ui_lint)")
print("=" * 65)

from ui_lint import UILinter
linter = UILinter()

# Rule 1: NULL-parent dialog → invisible (fp_dialog_null_parent)
f1 = linter.lint_source("BadDlgCmd.cpp", '''
CATStatusChangeRC BadDlgCmd::Activate(CATCommand *c, CATNotification *n) {
    _pDlg = new MyDlg(NULL);
    _pDlg->Build();
    _pDlg->SetVisibility(CATDlgShow);
    return CATStatusChangeRCCompleted;
}
''')
check("null-parent dialog flagged", any(f.rule == "ui_dialog_null_parent" for f in f1))

# Rule 2: Cancel() without SetVisibility(CATDlgHide) → close button dead
f2 = linter.lint_source("BadCloseCmd.cpp", '''
CATStatusChangeRC BadCloseCmd::Activate(CATCommand *c, CATNotification *n) {
    _pDlg = new MyDlg(pMain);
    _pDlg->SetVisibility(CATDlgShow);
    return CATStatusChangeRCCompleted;
}
CATStatusChangeRC BadCloseCmd::Desactivate(CATCommand *c, CATNotification *n) {
    if (_pDlg) { _pDlg->SetVisibility(CATDlgHide); }
    return CATStatusChangeRCCompleted;
}
CATStatusChangeRC BadCloseCmd::Cancel(CATCommand *c, CATNotification *n) {
    return CATStatusChangeRCAborted;
}
''')
check("empty Cancel() flagged", any(f.rule == "ui_dialog_cancel_empty" for f in f2))

# Rule 3: repeated SetAccessChild on same toolbar → only last button works
f3 = linter.lint_source("BadAddin.cpp", '''
CATCmdContainer* BadAddin::CreateToolbars() {
    NewAccess(CATCmdContainer, pTlb, MyTlb);
    NewAccess(CATCmdStarter, pC1, FirstCmd);
    SetAccessChild(pTlb, pC1);
    NewAccess(CATCmdStarter, pC2, SecondCmd);
    SetAccessChild(pTlb, pC2);
    return pTlb;
}
''')
check("SetAccessChild overwrite flagged",
      any(f.rule == "ui_toolbar_access_chain" for f in f3))

# Clean code → no findings
clean = f1 + f2 + f3  # sanity: findings exist on bad code
f_clean = linter.lint_source("GoodAddin.cpp", '''
CATCmdContainer* GoodAddin::CreateToolbars() {
    NewAccess(CATCmdContainer, pTlb, MyTlb);
    NewAccess(CATCmdStarter, pC1, FirstCmd);
    SetAccessChild(pTlb, pC1);
    NewAccess(CATCmdStarter, pC2, SecondCmd);
    SetAccessNext(pC1, pC2);
    return pTlb;
}
''')
check("clean code passes", len(f_clean) == 0)

# End-to-end: repair pipeline surfaces ui_pattern diagnostics on a
# workspace containing bad code (validates _diagnose_static actually
# scans the disk — it previously built an empty snapshot and no-op'd)
bad_ws = Path(tempfile.mkdtemp(prefix="cade_uilint_ws_"))
bad_ws = make_workspace(bad_ws)
(bad_ws / "TestUI.edu" / "TestModule.m" / "src" / "BadCmd.cpp").write_text('''
#include "BadCmd.h"
CATCreateClass(BadCmd);
CATStatusChangeRC BadCmd::Activate(CATCommand *c, CATNotification *n) {
    _pDlg = new MyDlg(NULL);
    _pDlg->SetVisibility(CATDlgShow);
    return CATStatusChangeRCCompleted;
}
''', encoding="utf-8")
k_bad = Kernel(workspace_root=str(bad_ws))
r = k_bad.execute(KernelMode.REPAIR, "fix issues preview")
diags = r.get("diagnostics", [])
ui_diags = [d for d in diags if d.get("category") == "ui_pattern"]
check("repair surfaces ui_pattern diagnostics", len(ui_diags) >= 1,
      f"{len(ui_diags)} ui_pattern of {len(diags)} total")
shutil.rmtree(bad_ws, ignore_errors=True)

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
