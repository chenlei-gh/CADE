#!/usr/bin/env python3
"""
Test CAA Call Chain Explorer & Self-Bootstrapping Engine
========================================================
Verifies the end-to-end evidence discovery, source slice extraction,
attribution verification, Jev review, clean rejection, and candidate
isolation.

Run:
    python tests/test_chain_explorer.py
"""

import os
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from retrieval import get_retrieval
from chain_explorer import ChainExplorer
from kernel import Kernel, KernelMode

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    s = "PASS" if ok else "FAIL"
    print(f"  [{s}] {label}" + (f" - {detail}" if detail else ""))


print("=" * 70)
print("1. Facade & Environment Health")
print("=" * 70)

r = get_retrieval(SKILL_ROOT)
check("Retrieval facade exposes chain_explorer", hasattr(r, "chain_explorer") and r.chain_explorer is not None)

health = r.health()
ce_health = health.get("chain_explorer", {})
check("ChainExplorer health is OK", ce_health.get("ok") is True, f"caadoc_root={ce_health.get('caadoc_root')}")

explorer = r.chain_explorer
caadoc_root = explorer.caadoc_root
check("CAADoc root accessible on disk", caadoc_root is not None and caadoc_root.exists(), str(caadoc_root))


print("=" * 70)
print("2. Scenario A: Assembly Tree -> Part Container (CATIProduct -> CATIPrtContainer)")
print("=" * 70)

res_a = explorer.explore(start="CATIProduct", target="CATIPrtContainer")
check("Scenario A status is ok", res_a.get("status") == "ok")
check("Scenario A returned candidate use cases", len(res_a.get("candidates", [])) > 0)

if res_a.get("candidates"):
    cand_a = res_a["candidates"][0]
    check("Scenario A has step count > 0", cand_a.get("step_count", 0) > 0, f"steps={cand_a.get('step_count')}")
    check("Scenario A has required headers", len(cand_a.get("headers_required", [])) > 0)
    check("Scenario A has required frameworks", len(cand_a.get("frameworks_required", [])) > 0)
    # Check that at least one step involves QI or method call to target
    steps_a = cand_a.get("steps", [])
    has_target = any(
        "CATIPrtContainer" in (s.get("target") or "")
        or "CATIPrtContainer" in (s.get("result_type") or "")
        or "CATIPrtContainer" in (s.get("caller_type") or "")
        for s in steps_a
    )
    check("Scenario A call chain reaches CATIPrtContainer", has_target)


print("=" * 70)
print("3. Scenario B: Geometry & Topological Fillet (CATIPrtContainer -> CATDynFillet)")
print("=" * 70)

res_b = explorer.explore(start="CATIPrtContainer", target="CATDynFillet")
check("Scenario B status is ok", res_b.get("status") == "ok")
check("Scenario B returned candidates", len(res_b.get("candidates", [])) > 0)

if res_b.get("candidates"):
    cand_b = res_b["candidates"][0]
    steps_b = cand_b.get("steps", [])
    has_fillet = any("CATDynFillet" in (s.get("caller_type") or "") or "CATDynFillet" in (s.get("target") or "") for s in steps_b)
    check("Scenario B calling sequence contains CATDynFillet operations", has_fillet)
    check("Scenario B frameworks include TopologicalOperators", any("TopologicalOperators" in fw for fw in cand_b.get("frameworks_required", [])))


print("=" * 70)
print("4. Scenario C: Uncovered Domain: Electrical Harness (CATIProduct -> CATIEhiBundleSegment)")
print("=" * 70)

res_c = explorer.explore(start="CATIProduct", target="CATIEhiBundleSegment")
check("Scenario C status is ok", res_c.get("status") == "ok")
check("Scenario C returned candidates", len(res_c.get("candidates", [])) > 0)

if res_c.get("candidates"):
    cand_c = res_c["candidates"][0]
    steps_c = cand_c.get("steps", [])
    has_ehi = any(
        "CATIEhiBundleSegment" in (s.get("target") or "")
        or "CATIEhiBundleSegment" in (s.get("result_type") or "")
        or "CATIEhiBundleSegment" in (s.get("caller_type") or "")
        for s in steps_c
    )
    check("Scenario C calling sequence contains CATIEhiBundleSegment", has_ehi)
    check("Scenario C frameworks include ElecHarnessItf", any("ElecHarnessItf" in fw for fw in cand_c.get("frameworks_required", [])))


print("=" * 70)
print("5. Blind Test: Drafting Generalization (CATIDftDrawing -> CATIDftSheet)")
print("=" * 70)

res_blind = explorer.explore(start="CATIDftDrawing", target="CATIDftSheet")
check("Blind test status is ok", res_blind.get("status") == "ok")
check("Blind test returned candidates", len(res_blind.get("candidates", [])) > 0)

if res_blind.get("candidates"):
    cand_blind = res_blind["candidates"][0]
    steps_blind = cand_blind.get("steps", [])
    has_sheet = any("CATIDftSheet" in (s.get("target") or "") or "CATIDftSheet" in (s.get("result_type") or "") for s in steps_blind)
    check("Blind test recovered CATIDftSheet connection", has_sheet)


print("=" * 70)
print("6. Negative Control: Clean Rejection Without Hallucination")
print("=" * 70)

res_neg = explorer.explore(start="CATIProduct", target="CATIFakeNonExistentItf")
check("Negative control status is insufficient_evidence", res_neg.get("status") == "insufficient_evidence")
check("Negative control returned 0 candidates", len(res_neg.get("candidates", [])) == 0)
check("Negative control provides missing_evidence reason", len(res_neg.get("missing_evidence", [])) > 0)


print("=" * 70)
print("7. Controlled Crystallization & Knowledge Isolation")
print("=" * 70)

if res_c.get("candidates"):
    cand_to_crystallize = res_c["candidates"][0]
    exp_dir = SKILL_ROOT / "knowledge" / "experimental"
    c_res = explorer.crystallize(cand_to_crystallize, output_dir=exp_dir)

    check("Crystallize status is ok", c_res.get("status") == "ok")
    doc_path = Path(c_res.get("file", ""))
    check("Candidate markdown file created", doc_path.exists())

    content = doc_path.read_text(encoding="utf-8")
    check("Candidate header contains SECURITY NOTICE", "SECURITY NOTICE" in content)
    check("Candidate document states isolated from catalog", "isolated from official knowledge" in content)
    check("Candidate document contains Promotion Gate checklist", "Promotion Gate" in content)

    # Verify official catalog/index.yaml was NOT modified or contaminated
    cat_yaml = SKILL_ROOT / "catalog" / "index.yaml"
    cat_content = cat_yaml.read_text(encoding="utf-8")
    check("Official catalog/index.yaml is UNPOLLUTED by candidate", "CATIEhiBundleSegment" not in cat_content)


print("=" * 70)
print("8. End-to-End Kernel ANALYZE Integration")
print("=" * 70)

k = Kernel()
k_res = k.execute(KernelMode.ANALYZE, "如何在CAA中获取CATIEhiBundleSegment并配置线束")
check("Kernel analyze returned ok", k_res.get("status") == "ok")
k_data = k_res.get("data", {})
check("Kernel surfaced official_usecase_chain", k_data.get("evidence_level") == "official_usecase_chain")
check("Kernel included isolated candidate note", "isolated_candidate_note" in k_data)

print("=" * 70)
print(f"RESULTS: {passed}/{total} checks passed.")
print("=" * 70)

if passed < total:
    sys.exit(1)
