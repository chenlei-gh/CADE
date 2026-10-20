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
from chain_explorer import ChainExplorer, ChainStep
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
print("7. Adversarial Negative Controls (Def-Use, Cross-Function & Error Blocks)")
print("=" * 70)

import tempfile

with tempfile.TemporaryDirectory() as tmp_dir_str:
    tmp_dir = Path(tmp_dir_str)

    # 7a: Cross-function isolation counter-example
    cpp_cross_fn = tmp_dir / "cross_function_isolated.cpp"
    cpp_cross_fn.write_text(
        """
        void CAAMyClass::FunctionA() {
            CATIProduct *piProduct = NULL;
            piProduct->GetChildren();
        }
        void CAAMyClass::FunctionB() {
            CATIPrtContainer *piContainer = NULL;
            piContainer->GetPart();
        }
        """,
        encoding="utf-8"
    )
    steps_cf, conn_cf = explorer.extract_chain_from_cpp(cpp_cross_fn, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Cross-function isolation rejected as disconnected", conn_cf == "disconnected")
    check("Cross-function steps do not falsely connect", len(steps_cf) == 0)

    # 7b: Error handling branch isolation
    cpp_error_branch = tmp_dir / "error_branch.cpp"
    cpp_error_branch.write_text(
        """
        void CAAMyClass::Execute() {
            CATIProduct *piProduct = NULL;
            HRESULT rc = S_OK;
            if (FAILED(rc)) {
                CATIArrSegment *piErrSeg = NULL;
                piErrSeg->Release();
                return;
            }
            piProduct->GetChildren();
        }
        """,
        encoding="utf-8"
    )
    steps_eb, conn_eb = explorer.extract_chain_from_cpp(cpp_error_branch, start_type="CATIProduct", target_type="CATIArrSegment")
    check("Target in FAILED(rc) error block is not promoted to valid chain", conn_eb == "disconnected")

    # 7c: Dataflow disconnect within same function
    cpp_unlinked = tmp_dir / "unlinked_dataflow.cpp"
    cpp_unlinked.write_text(
        """
        void CAAMyClass::Execute() {
            CATIProduct *piProduct = NULL;
            piProduct->GetChildren();
            CATIArrSegment *piOther = NULL;
            piOther->GetDiameter();
        }
        """,
        encoding="utf-8"
    )
    steps_un, conn_un = explorer.extract_chain_from_cpp(cpp_unlinked, start_type="CATIProduct", target_type="CATIArrSegment")
    check("Unlinked dataflow within same function detected as disconnected", conn_un == "disconnected")

    # 7d: Method disambiguation check
    step_amb = ChainStep(
        line=10, kind="method_call", caller_var="pUnknown", caller_type="", target_name="Release"
    )
    explorer.verify_steps([step_amb])
    check("Ambiguous method with multiple owners flags owner_ambiguity", step_amb.owner_ambiguity is True)
    check("Ambiguous method has candidate owners", len(step_amb.candidate_owners) > 1)


print("=" * 70)
print("8. Controlled Crystallization (Zero Workspace Pollution & Overwrite Defense)")
print("=" * 70)

with tempfile.TemporaryDirectory() as tmp_exp_dir_str:
    exp_dir = Path(tmp_exp_dir_str)
    if res_c.get("candidates"):
        cand_to_crystallize = res_c["candidates"][0]

        # First write
        c_res1 = explorer.crystallize(cand_to_crystallize, output_dir=exp_dir, overwrite=False)
        check("Crystallize status is ok", c_res1.get("status") == "ok")
        doc_path1 = Path(c_res1.get("file", ""))
        check("Candidate markdown file created in temp dir", doc_path1.exists())

        # Second write with overwrite=False: must generate _v2
        c_res2 = explorer.crystallize(cand_to_crystallize, output_dir=exp_dir, overwrite=False)
        doc_path2 = Path(c_res2.get("file", ""))
        check("Overwrite defense creates _v2 candidate file", "_v2" in doc_path2.name and doc_path2.exists())

        content = doc_path1.read_text(encoding="utf-8")
        check("Candidate header contains SECURITY NOTICE", "SECURITY NOTICE" in content)
        check("Candidate document states isolated from catalog", "isolated from official knowledge" in content)
        check("Candidate document contains Promotion Gate checklist", "Promotion Gate" in content)
        check("Candidate document distinguishes Frameworks vs Link Modules", "Recommended Link Modules" in content)

    # Verify official catalog/index.yaml was NOT modified or contaminated
    cat_yaml = SKILL_ROOT / "catalog" / "index.yaml"
    cat_content = cat_yaml.read_text(encoding="utf-8")
    check("Official catalog/index.yaml is UNPOLLUTED by candidate", "CATIEhiBundleSegment" not in cat_content)


print("=" * 70)
print("9. End-to-End Kernel ANALYZE Integration & Precedence")
print("=" * 70)

k = Kernel()

# 9a: Curated catalog hit takes precedence over chain exploration
k_cat = k.execute(KernelMode.ANALYZE, "如何在CAA中创建特征")
check("Curated catalog knowledge takes precedence", k_cat.get("status") == "ok")
check("Curated hit returns references", "references" in k_cat.get("data", {}))

# 9b: Uncovered action query invokes chain explorer with objective tone
k_res = k.execute(KernelMode.ANALYZE, "如何在CAA中获取CATIEhiBundleSegment并配置线束")
check("Kernel analyze returned ok for uncovered domain", k_res.get("status") == "ok")
k_data = k_res.get("data", {})
check("Kernel surfaced official_usecase_chain", k_data.get("evidence_level") == "official_usecase_chain")
check("Kernel tone explicitly states static-checked / not compiler-verified", "compiler_verified" in k_data and k_data["compiler_verified"] is False)
check("Kernel included isolated candidate note", "isolated_candidate_note" in k_data)

print("=" * 70)
print(f"RESULTS: {passed}/{total} checks passed.")
print("=" * 70)

if passed < total:
    sys.exit(1)
