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
    steps_cf, conn_cf, parse_cf = explorer.extract_chain_from_cpp(cpp_cross_fn, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Cross-function isolation rejected as disconnected", conn_cf == "disconnected")
    check(
        "Cross-function steps do not falsely connect",
        len({s.function_scope for s in steps_cf}) <= 1 and not any(s.target_name == "CATIPrtContainer" for s in steps_cf),
        f"steps={len(steps_cf)} parse={parse_cf}",
    )

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
    steps_eb, conn_eb, _parse_eb = explorer.extract_chain_from_cpp(cpp_error_branch, start_type="CATIProduct", target_type="CATIArrSegment")
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
    steps_un, conn_un, _parse_un = explorer.extract_chain_from_cpp(cpp_unlinked, start_type="CATIProduct", target_type="CATIArrSegment")
    check("Unlinked dataflow within same function detected as disconnected", conn_un == "disconnected")

    # 7d: All steps in error branch must NEVER fall back and recover
    cpp_all_error = tmp_dir / "all_error_branch.cpp"
    cpp_all_error.write_text(
        """
        void CAAMyClass::FailAll() {
            HRESULT hr = E_FAIL;
            if (FAILED(hr)) {
                CATIProduct *piProduct = NULL;
                CATIPrtContainer *piCont = NULL;
                piProduct->GetChildren();
                piCont->GetPart();
            }
        }
        """,
        encoding="utf-8"
    )
    steps_ae, conn_ae, _parse_ae = explorer.extract_chain_from_cpp(cpp_all_error, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("All steps in error branch cleanly rejected without fallback", conn_ae == "disconnected")
    check("Error branch fallback loophole sealed (step count is 0)", len(steps_ae) == 0)

    # 7e: Target only appearing in method argument string without QI transition
    cpp_arg_only = tmp_dir / "target_in_arg_string_only.cpp"
    cpp_arg_only.write_text(
        """
        void CAAMyClass::QueryByName() {
            CATIProduct *piProduct = NULL;
            CATBaseUnknown *pObj = NULL;
            pObj = piProduct->FindObject("CATIPrtContainer");
            pObj->Release();
        }
        """,
        encoding="utf-8"
    )
    steps_ao, conn_ao, _parse_ao = explorer.extract_chain_from_cpp(cpp_arg_only, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Target appearing only in argument string is NOT falsely connected", conn_ao == "disconnected")

    # 7f: Cross-function same-name variable isolation
    cpp_same_var = tmp_dir / "same_var_diff_func.cpp"
    cpp_same_var.write_text(
        """
        void CAAMyClass::MethodAlpha() {
            CATIProduct *piSharedVar = NULL;
            piSharedVar->GetChildren();
        }
        void CAAMyClass::MethodBeta() {
            CATIPrtContainer *piSharedVar = NULL;
            piSharedVar->GetPart();
        }
        """,
        encoding="utf-8"
    )
    steps_sv, conn_sv, _parse_sv = explorer.extract_chain_from_cpp(cpp_same_var, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Same-named local variable across functions isolated by function scope", conn_sv == "disconnected")

    # 7h: same name AND same type in two functions must not connect
    cpp_same_type = tmp_dir / "same_type_same_name.cpp"
    cpp_same_type.write_text(
        """
        void CAAMyClass::Produces() {
            CATIProduct *piSharedVar = NULL;
            piSharedVar->GetChildren();
        }
        void CAAMyClass::Consumes() {
            CATIProduct *piSharedVar = NULL;
            CATIPrtContainer *piCont = NULL;
            piSharedVar->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
        }
        """,
        encoding="utf-8",
    )
    steps_st, conn_st, _parse_st = explorer.extract_chain_from_cpp(
        cpp_same_type, start_type="CATIProduct", target_type="CATIPrtContainer"
    )
    check("Same-type same-name locals across functions stay disconnected", conn_st == "disconnected")
    check(
        "Cross-function same-type chain is not a single-scope connected walk",
        not (conn_st == "connected" and len({s.function_scope for s in steps_st}) > 1),
    )

    # 7i: reassignment kills the previous definition
    cpp_redef = tmp_dir / "reassign.cpp"
    cpp_redef.write_text(
        """
        void CAAMyClass::Reset() {
            CATIProduct *piProduct = NULL;
            piProduct->GetChildren();
            piProduct = NULL;
            CATIPrtContainer *piCont = NULL;
            piProduct->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
        }
        """,
        encoding="utf-8",
    )
    _steps_rd, conn_rd, _parse_rd = explorer.extract_chain_from_cpp(
        cpp_redef, start_type="CATIProduct", target_type="CATIPrtContainer"
    )
    check("Reassignment invalidates the previous reachable definition", conn_rd == "disconnected")

    # 7j: unrelated function calling the same interface is not the start flow
    cpp_other = tmp_dir / "other_function_same_iface.cpp"
    cpp_other.write_text(
        """
        void CAAMyClass::StartOnly() {
            CATIProduct *piMine = NULL;
            piMine->GetChildren();
        }
        void CAAMyClass::OtherProduct() {
            CATIProduct *piOther = NULL;
            CATIPrtContainer *piCont = NULL;
            piOther->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
        }
        """,
        encoding="utf-8",
    )
    _steps_ot, conn_ot, _parse_ot = explorer.extract_chain_from_cpp(
        cpp_other, start_type="CATIProduct", target_type="CATIPrtContainer"
    )
    check("Unrelated function using the same interface is not connected", conn_ot == "disconnected")

    # 7k: target exists only in an unrelated function
    cpp_tgt_elsewhere = tmp_dir / "target_elsewhere.cpp"
    cpp_tgt_elsewhere.write_text(
        """
        void CAAMyClass::StartOnly() {
            CATIProduct *piMine = NULL;
            piMine->GetChildren();
        }
        void CAAMyClass::TargetOnly() {
            CATIPrtContainer *piCont = NULL;
            piCont->GetPart();
        }
        """,
        encoding="utf-8",
    )
    _steps_te, conn_te, _parse_te = explorer.extract_chain_from_cpp(
        cpp_tgt_elsewhere, start_type="CATIProduct", target_type="CATIPrtContainer"
    )
    check("Target only in an unrelated function is disconnected", conn_te == "disconnected")

    # 7l: comment markers inside a string must not eat the real call
    cpp_str = tmp_dir / "string_comment.cpp"
    cpp_str.write_text(
        """
        void CAAMyClass::KeepCall() {
            CATIProduct *piProduct = NULL;
            CATUnicodeString label = "not a // comment";
            CATIPrtContainer *piCont = NULL;
            piProduct->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
        }
        """,
        encoding="utf-8",
    )
    steps_sc, conn_sc, parse_sc = explorer.extract_chain_from_cpp(
        cpp_str, start_type="CATIProduct", target_type="CATIPrtContainer"
    )
    check("String-literal comment marker does not drop the real QI", conn_sc == "connected" and parse_sc == "ok")
    check("String-literal case still records the QI step", any(s.kind == "query_interface" for s in steps_sc))

    # 7m: template/goto/define is an unsupported subset and cannot be a chain
    cpp_bad = tmp_dir / "unsupported.cpp"
    cpp_bad.write_text(
        """
        #define QI QueryInterface
        void CAAMyClass::MacroHidden() {
            CATIProduct *piProduct = NULL;
            CATIPrtContainer *piCont = NULL;
            piProduct->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
        }
        """,
        encoding="utf-8",
    )
    _steps_bad, conn_bad, parse_bad = explorer.extract_chain_from_cpp(
        cpp_bad, start_type="CATIProduct", target_type="CATIPrtContainer"
    )
    check("Unsupported preprocessor syntax is not a connected chain", conn_bad != "connected")
    check("Unsupported syntax is labeled unsupported_syntax", parse_bad == "unsupported_syntax")

    # 7n: type substring must not count as the target type
    cpp_sub = tmp_dir / "type_substring.cpp"
    cpp_sub.write_text(
        """
        void CAAMyClass::Substring() {
            CATIProduct *piProduct = NULL;
            CATIProductExtra *piExtra = NULL;
            piProduct->QueryInterface(IID_CATIProductExtra, (void**)&piExtra);
        }
        """,
        encoding="utf-8",
    )
    _steps_sub, conn_sub, _parse_sub = explorer.extract_chain_from_cpp(
        cpp_sub, start_type="CATIProduct", target_type="CATIProductEx"
    )
    check("Type substring is not an exact target hit", conn_sub != "connected")

    # 7o: same-function QI still connects
    cpp_ok = tmp_dir / "same_function_qi.cpp"
    cpp_ok.write_text(
        """
        void CAAMyClass::Convert() {
            CATIProduct *piProduct = NULL;
            CATIPrtContainer *piCont = NULL;
            piProduct->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
            piCont->GetPart();
        }
        """,
        encoding="utf-8",
    )
    steps_ok, conn_ok, parse_ok = explorer.extract_chain_from_cpp(
        cpp_ok, start_type="CATIProduct", target_type="CATIPrtContainer"
    )
    check("Same-function QI remains connected", conn_ok == "connected" and parse_ok == "ok")
    check("Same-function QI chain includes the target interface", any(s.target_name == "CATIPrtContainer" for s in steps_ok))

    # 7p: output argument without '&' remains a def inside the same function
    cpp_out = tmp_dir / "bare_out_param.cpp"
    cpp_out.write_text(
        """
        void CAAMyClass::BareOut() {
            CATIProduct *piProduct = NULL;
            CATIContainer *pContainer = NULL;
            piProduct->GetSpecContainer(pContainer);
            CATIPrtContainer *piCont = NULL;
            pContainer->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
        }
        """,
        encoding="utf-8",
    )
    steps_out, conn_out, _parse_out = explorer.extract_chain_from_cpp(
        cpp_out, start_type="CATIProduct", target_type="CATIPrtContainer"
    )
    check("Bare CAT* out-parameter still connects inside one function", conn_out == "connected")
    check("Bare out-parameter chain reaches the QI target", any(s.target_name == "CATIPrtContainer" for s in steps_out))

    # 7g: Method disambiguation check with ownership_status
    step_amb = ChainStep(
        line=10, kind="method_call", caller_var="pUnknown", caller_type="", target_name="Release"
    )
    explorer.verify_steps([step_amb])
    check("Ambiguous method with multiple owners flags owner_ambiguity", step_amb.owner_ambiguity is True)
    check("Ambiguous method has ownership_status=='ambiguous'", step_amb.ownership_status == "ambiguous")
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
        check("Candidate document distinguishes HeaderMap modules from LINK_WITH", "not verified LINK_WITH" in content)

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

# 9b: Uncovered action query invokes chain explorer with objective tone.
# Direction must be explicit. Identifier order is not a start/target guess.
k_res = k.execute(KernelMode.ANALYZE, "如何在CAA中从CATIProduct到CATIEhiBundleSegment并配置线束")
check("Kernel analyze returned ok for uncovered domain", k_res.get("status") == "ok")
k_data = k_res.get("data", {})
# CATIEhiBundleSegment is an unconnected official fragment, so Kernel must accurately label it as fragment
check("Kernel correctly labels unconnected evidence as official_usecase_fragment", k_data.get("evidence_level") == "official_usecase_fragment")
check("Kernel data sets connected=False and fragment_only=True", k_data.get("connected") is False and k_data.get("fragment_only") is True)
check("Kernel provides disconnected_warning for fragments", "disconnected_warning" in k_data)
check("Kernel tone explicitly states static-checked / not compiler-verified", "compiler_verified" in k_data and k_data["compiler_verified"] is False)
check("Kernel included isolated candidate note", "isolated_candidate_note" in k_data)

# 9c: A connected source walk is still not a promoted chain when the index
# only matched its root path. Metadata consistency is unverified.
k_res_chain = k.execute(KernelMode.ANALYZE, "如何在CAA中从CATIDftDrawing获取CATIDftSheet")
check("Kernel analyze returned ok for connected chain query", k_res_chain.get("status") == "ok")
k_chain_data = k_res_chain.get("data", {})
check(
    "Kernel does not promote a root-matched unverified index to official_usecase_chain",
    k_chain_data.get("evidence_level") == "official_usecase_fragment",
)
check(
    "Kernel keeps unverified-index evidence as a fragment",
    k_chain_data.get("connected") is False and k_chain_data.get("fragment_only") is True,
)
check(
    "Kernel names the unverified index as the reject reason",
    "index_consistency" in (k_chain_data.get("contract_reject_reason") or ""),
)
check("Kernel chain payload has source hash", bool((k_chain_data.get("candidate") or {}).get("source_sha256")))
check(
    "Kernel chain payload marks link_libraries as non-authoritative",
    k_chain_data.get("link_libraries_authority") == "header_map_module_not_link_with",
)

# 9d: a lying connected label without the evidence contract must not be promoted
promoted, reason = Kernel._chain_contract_ok({
    "connectivity_status": "connected",
    "evidence_tier": "candidate_fragment",
    "parse_status": "ok",
    "source_sha256": "abc",
    "steps": [{"function_scope": "A", "ownership_status": "verified", "in_error_branch": False}],
})
check("Kernel refuses connected label that disagrees with evidence_tier", promoted is False and "evidence_tier" in reason)

promoted_scope, reason_scope = Kernel._chain_contract_ok({
    "connectivity_status": "connected",
    "evidence_tier": "grounded_candidate_chain",
    "parse_status": "ok",
    "source_sha256": "abc",
    "index_consistency": "consistent",
    "start_type": "CATIProduct",
    "target_type": "CATIPrtContainer",
    "steps": [
        {
            "function_scope": "FuncA",
            "ownership_status": "verified",
            "in_error_branch": False,
            "caller_type": "CATIProduct",
            "caller_def": ["FuncA", 1, "pVar", 1],
            "result_def": ["FuncA", 1, "pMid", 2],
            "result_type": "CATIContainer",
        },
        {
            "function_scope": "FuncB",
            "ownership_status": "verified",
            "in_error_branch": False,
            "caller_type": "CATIContainer",
            "caller_def": ["FuncB", 2, "pMid", 3],
            "kind": "query_interface",
            "result_type": "CATIPrtContainer",
            "target": "CATIPrtContainer",
        },
    ],
})
check(
    "Kernel refuses a claimed chain that spans two functions",
    promoted_scope is False and "scope" in reason_scope,
)

# 9e: QI header miss is not collapsed into ownership verified
qi_miss = ChainStep(
    line=1, kind="query_interface", caller_var="p", caller_type="CATIProduct",
    target_name="CATIDoesNotExistHeader",
)
explorer.verify_steps([qi_miss])
check("QI convention is recorded separately", qi_miss.qi_convention == "IUnknown")
check("QI header miss is not ownership verified", qi_miss.ownership_status != "verified")
check("QI header miss is explicit", qi_miss.header_index_status == "miss")

print("=" * 70)
print("10. 14-Item Convergence Checklist Verification")
print("=" * 70)

with tempfile.TemporaryDirectory() as tmp_dir_10_str:
    t10_dir = Path(tmp_dir_10_str)

    # Item 1: Cross-function splice. Neither function is a complete start->target walk.
    # A wrong implementation that shares variable names across functions would connect.
    cpp_1 = t10_dir / "item1_cross_func.cpp"
    cpp_1.write_text("""
    void CAAMyClass::FuncA() {
        CATIProduct *pVar = NULL;
        CATIContainer *pMid = NULL;
        pVar->GetSpecContainer(pMid);
    }
    void CAAMyClass::FuncB() {
        CATIContainer *pMid = NULL;
        CATIPrtContainer *pCont = NULL;
        pMid->QueryInterface(IID_CATIPrtContainer, (void**)&pCont);
    }
    """, encoding="utf-8")
    steps_1, conn_1, parse_1 = explorer.extract_chain_from_cpp(cpp_1, start_type="CATIProduct", target_type="CATIPrtContainer")
    scopes_1 = {s.function_scope for s in steps_1}
    check("Item 1: Cross-function splice is not a connected chain", conn_1 != "connected" and parse_1 == "ok")
    check("Item 1: Returned steps do not span both functions as one chain", len(scopes_1) <= 1)

    # Item 2: Lexical Scope Shadowing within same function
    cpp_2 = t10_dir / "item2_shadowing.cpp"
    cpp_2.write_text("""
    void CAAMyClass::ShadowTest() {
        CATIProduct *piProduct = NULL;
        {
            CATIOther *piProduct = NULL;
            piProduct->UnrelatedCall();
        }
        CATIPrtContainer *piCont = NULL;
        piProduct->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
    }
    """, encoding="utf-8")
    steps_2, conn_2, parse_2 = explorer.extract_chain_from_cpp(cpp_2, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Item 2: Lexical scope restores outer definition and connects", conn_2 == "connected" and parse_2 == "ok")
    check("Item 2: Inner shadowed step not linked as CATIProduct", not any(s.caller_type == "CATIProduct" and s.target_name == "UnrelatedCall" for s in steps_2))

    # Item 3: Order strictly enforced: Declaration -> Call -> Reassignment (NULL) -> Call
    cpp_3 = t10_dir / "item3_order_reassign.cpp"
    cpp_3.write_text("""
    void CAAMyClass::OrderReassign() {
        CATIProduct *piProduct = NULL;
        piProduct->GetChildren();
        piProduct = NULL;
        CATIPrtContainer *piCont = NULL;
        piProduct->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
    }
    """, encoding="utf-8")
    _s3, conn_3, _p3 = explorer.extract_chain_from_cpp(cpp_3, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Item 3: Reassignment to NULL invalidates reachability before QI", conn_3 != "connected")

    # Item 4: Target variable declared only after all calls cannot validate preceding calls
    cpp_4 = t10_dir / "item4_late_decl.cpp"
    cpp_4.write_text("""
    void CAAMyClass::LateDeclaration() {
        CATIProduct *piProduct = NULL;
        piProduct->GetChildren();
        piProduct->Update();
        CATIPrtContainer *piLateTarget = NULL;
    }
    """, encoding="utf-8")
    _s4, conn_4, _p4 = explorer.extract_chain_from_cpp(cpp_4, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Item 4: Target declared late without producing call remains disconnected", conn_4 != "connected")

    # Item 5: Input vs Output param: Ordinary method passing without '&' cannot infer output from CAT*
    cpp_5 = t10_dir / "item5_in_param.cpp"
    cpp_5.write_text("""
    void CAAMyClass::InParamCheck() {
        CATIProduct *piProduct = NULL;
        CATIPrtContainer *piCont = NULL;
        piProduct->InspectContainer(piCont);
        piCont->GetPart();
    }
    """, encoding="utf-8")
    steps_5, conn_5, _p5 = explorer.extract_chain_from_cpp(cpp_5, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Item 5: Unwhitelisted bare parameter does not fabricate result_def", conn_5 != "connected")
    check("Item 5: InspectContainer has no result_def assigned", not any(s.target_name == "InspectContainer" and s.result_def is not None for s in steps_5))

    # Item 6: QueryInterface caller_def, result_def and target arrival
    cpp_6 = t10_dir / "item6_qi_defs.cpp"
    cpp_6.write_text("""
    void CAAMyClass::QiDefs() {
        CATIProduct *piProduct = NULL;
        CATIPrtContainer *piCont = NULL;
        piProduct->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
    }
    """, encoding="utf-8")
    steps_6, conn_6, parse_6 = explorer.extract_chain_from_cpp(cpp_6, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Item 6: QI produces connected chain", conn_6 == "connected" and parse_6 == "ok")
    qi_step = next((s for s in steps_6 if s.kind == "query_interface"), None)
    check("Item 6: QI step exposes caller_def", qi_step is not None and qi_step.caller_def is not None)
    check("Item 6: QI step exposes result_def for target", qi_step is not None and qi_step.result_def is not None)
    check("Item 6: QI step to_dict contains caller_def and result_def", qi_step is not None and "caller_def" in qi_step.to_dict() and "result_def" in qi_step.to_dict())

    # Item 7: Function parameters as start type: CATIProduct_var
    cpp_7 = t10_dir / "item7_param_var.cpp"
    cpp_7.write_text("""
    HRESULT CAAMyClass::ProcessProduct(CATIProduct_var ispProduct) {
        CATIPrtContainer *piCont = NULL;
        ispProduct->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
        return S_OK;
    }
    """, encoding="utf-8")
    steps_7, conn_7, parse_7 = explorer.extract_chain_from_cpp(cpp_7, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Item 7: CATIProduct_var function parameter recognized as start type", conn_7 == "connected" and parse_7 == "ok")
    check("Item 7: Parameter start reaches target", any(s.target_name == "CATIPrtContainer" for s in steps_7))

    # Function boundary must reset after the closing brace, before the next function.
    cpp_fn = t10_dir / "function_boundary.cpp"
    cpp_fn.write_text("""
    void CAAMyClass::First() {
        CATIProduct *piProduct = NULL;
        piProduct->GetChildren();
    }
    CATIPrtContainer *gCont = NULL;
    void CAAMyClass::Second() {
        CATIProduct *piOther = NULL;
        gCont->GetPart();
    }
    """, encoding="utf-8")
    steps_fn, conn_fn, parse_fn = explorer.extract_chain_from_cpp(cpp_fn, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Item 4b: Function exit does not leak the old function into later calls", conn_fn != "connected" and parse_fn == "ok")
    check("Item 4b: Later call is not attributed to the closed function", not any(s.function_scope.endswith("First") and s.target_name == "GetPart" for s in steps_fn))

    cpp_qi_if = t10_dir / "unbraced_qi.cpp"
    cpp_qi_if.write_text("""
    void CAAMyClass::GuardedQi() {
        CATIProduct *pProduct = NULL;
        CATIPrtContainer *pContainer = NULL;
        if (pProduct)
            pProduct->QueryInterface(IID_CATIPrtContainer, (void**)&pContainer);
    }
    """, encoding="utf-8")
    steps_qi_if, conn_qi_if, parse_qi_if = explorer.extract_chain_from_cpp(cpp_qi_if, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("QI unbraced branch is not a connected chain", conn_qi_if != "connected" and parse_qi_if == "ok")
    check("QI unbraced branch is not promoted into the candidate walk", not any(s.kind == "query_interface" and not s.in_error_branch for s in steps_qi_if))

    cpp_sig = t10_dir / "out_signature.cpp"
    cpp_sig.write_text("""
    void CAAMyClass::Signature() {
        CATIProduct *piProduct = NULL;
        CATIOther *pOther = NULL;
        CATIContainer *pContainer = NULL;
        piProduct->GetSpecContainer(pOther, pContainer);
        CATIPrtContainer *piCont = NULL;
        pContainer->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
    }
    """, encoding="utf-8")
    steps_sig, conn_sig, _parse_sig = explorer.extract_chain_from_cpp(cpp_sig, start_type="CATIProduct", target_type="CATIPrtContainer")
    spec_step = next((s for s in steps_sig if s.target_name == "GetSpecContainer"), None)
    # Official signature is GetSpecContainer(outContainer). A leading CAT* input is not
    # the out slot, and the scanner must not invent a second-argument output contract.
    check("Out-signature does not treat the first CAT* token as output", spec_step is not None and spec_step.result_var != "pOther")
    check("Unproven second argument is not an indexed out parameter", spec_step is not None and spec_step.result_var != "pContainer" and conn_sig != "connected")

    # Item 8: Unsupported syntax must downgrade, not just templates.
    cpp_8 = t10_dir / "item8_template.cpp"
    cpp_8.write_text("""
    template <class T>
    void CAAMyClass::TemplateFunction(T* p) {
        CATIProduct *piProduct = NULL;
        CATIPrtContainer *piCont = NULL;
        piProduct->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
    }
    """, encoding="utf-8")
    _s8, conn_8, parse_8 = explorer.extract_chain_from_cpp(cpp_8, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Item 8: Template syntax triggers parse_status unsupported_syntax", parse_8 == "unsupported_syntax")
    check("Item 8: Template syntax downgrades connectivity to disconnected", conn_8 != "connected")

    cpp_raw = t10_dir / "item8_raw.cpp"
    cpp_raw.write_text(
        'void CAAMyClass::Raw() {\n'
        '    const char *note = R"(if (FAILED(rc)) { })";\n'
        '    CATIProduct *piProduct = NULL;\n'
        '    CATIPrtContainer *piCont = NULL;\n'
        '    piProduct->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);\n'
        '}\n',
        encoding="utf-8",
    )
    _s_raw, conn_raw, parse_raw = explorer.extract_chain_from_cpp(cpp_raw, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Item 8: Raw string is unsupported_syntax", parse_raw == "unsupported_syntax" and conn_raw != "connected")

    cpp_brace_lit = t10_dir / "item8_brace_literal.cpp"
    cpp_brace_lit.write_text("""
    void CAAMyClass::LiteralBrace() {
        CATIProduct *piProduct = NULL;
        const char *blob = "} void Fake() {";
        CATIPrtContainer *piCont = NULL;
        piProduct->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
    }
    """, encoding="utf-8")
    steps_lit, conn_lit, parse_lit = explorer.extract_chain_from_cpp(cpp_brace_lit, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Item 8: Brace inside a string does not split the function", conn_lit == "connected" and parse_lit == "ok")
    check("Item 8: String-brace chain stays in the real function", steps_lit and all("LiteralBrace" in s.function_scope for s in steps_lit))

    cpp_while = t10_dir / "item8_unbraced_while.cpp"
    cpp_while.write_text("""
    void CAAMyClass::UnbracedWhile() {
        CATIProduct *piProduct = NULL;
        CATIPrtContainer *piCont = NULL;
        while (piProduct)
            piProduct->QueryInterface(IID_CATIPrtContainer, (void**)&piCont);
    }
    """, encoding="utf-8")
    _s_while, conn_while, parse_while = explorer.extract_chain_from_cpp(cpp_while, start_type="CATIProduct", target_type="CATIPrtContainer")
    check("Item 8: Unbraced while body is not a connected chain", conn_while != "connected" and parse_while == "ok")

    # Item 9: Kernel refuses promotion when scope, parse_status or def-use evidence missing
    p_bad_parse, r_bad_parse = Kernel._chain_contract_ok({
        "connectivity_status": "connected",
        "evidence_tier": "grounded_candidate_chain",
        "parse_status": "unsupported_syntax",
        "source_sha256": "abc1234",
        "index_consistency": "consistent",
        "start_type": "CATIProduct",
        "target_type": "CATIPrtContainer",
        "steps": [{"function_scope": "Func", "ownership_status": "verified", "in_error_branch": False, "caller_type": "CATIProduct", "caller_def": ["Func", 1, "p", 1], "result_def": ["Func", 1, "c", 2], "kind": "query_interface", "result_type": "CATIPrtContainer"}],
    })
    check("Item 9: Kernel rejects candidate with parse_status != ok", p_bad_parse is False and "parse_status" in r_bad_parse)

    p_missing_parse, r_missing_parse = Kernel._chain_contract_ok({
        "connectivity_status": "connected",
        "evidence_tier": "grounded_candidate_chain",
        "source_sha256": "abc1234",
        "index_consistency": "consistent",
        "start_type": "CATIProduct",
        "target_type": "CATIPrtContainer",
        "steps": [{"function_scope": "Func", "caller_type": "CATIProduct", "caller_def": ["Func", 1, "p", 1], "result_def": ["Func", 1, "c", 2], "kind": "query_interface", "result_type": "CATIPrtContainer"}],
    })
    check("Item 9: Kernel rejects missing parse_status", p_missing_parse is False and "parse_status" in r_missing_parse)

    p_unknown_idx, r_unknown_idx = Kernel._chain_contract_ok({
        "connectivity_status": "connected",
        "evidence_tier": "grounded_candidate_chain",
        "parse_status": "ok",
        "source_sha256": "abc1234",
        "index_consistency": "unknown",
        "start_type": "CATIProduct",
        "target_type": "CATIPrtContainer",
        "steps": [{"function_scope": "Func", "caller_type": "CATIProduct", "caller_def": ["Func", 1, "p", 1], "result_def": ["Func", 1, "c", 2], "kind": "query_interface", "result_type": "CATIPrtContainer"}],
    })
    check("Item 9: Kernel rejects unknown index_consistency", p_unknown_idx is False and "index_consistency" in r_unknown_idx)

    p_bad_def, r_bad_def = Kernel._chain_contract_ok({
        "connectivity_status": "connected",
        "evidence_tier": "grounded_candidate_chain",
        "parse_status": "ok",
        "source_sha256": "abc1234",
        "index_consistency": "consistent",
        "start_type": "CATIProduct",
        "target_type": "CATIPrtContainer",
        "steps": [
            {"function_scope": "Func", "ownership_status": "verified", "in_error_branch": False, "caller_type": "CATIProduct", "caller_def": ["Func", 1, "p", 1], "result_def": ["Func", 1, "res1", 2], "result_type": "CATIContainer"},
            {"function_scope": "Func", "ownership_status": "verified", "in_error_branch": False, "caller_type": "CATIContainer", "caller_def": ["Func", 1, "unrelated_var", 99], "result_def": ["Func", 1, "res2", 3], "kind": "query_interface", "result_type": "CATIPrtContainer"},
        ],
    })
    check("Item 9: Kernel rejects candidate with broken Def-Use chain", p_bad_def is False and "not produced" in r_bad_def)

    p_missing_caller, r_missing_caller = Kernel._chain_contract_ok({
        "connectivity_status": "connected",
        "evidence_tier": "grounded_candidate_chain",
        "parse_status": "ok",
        "source_sha256": "abc1234",
        "index_consistency": "consistent",
        "start_type": "CATIProduct",
        "target_type": "CATIPrtContainer",
        "steps": [
            {"function_scope": "Func", "caller_type": "CATIProduct", "caller_def": ["Func", 1, "p", 1], "result_def": ["Func", 1, "res", 2], "result_type": "CATIContainer"},
            {"function_scope": "Func", "caller_type": "CATIContainer", "kind": "query_interface", "result_type": "CATIPrtContainer"},
        ],
    })
    check("Item 9: Kernel rejects a later step with no caller_def", p_missing_caller is False and "caller_def" in r_missing_caller)

    p_wrong_start, r_wrong_start = Kernel._chain_contract_ok({
        "connectivity_status": "connected",
        "evidence_tier": "grounded_candidate_chain",
        "parse_status": "ok",
        "source_sha256": "abc1234",
        "index_consistency": "consistent",
        "start_type": "CATIProduct",
        "target_type": "CATIPrtContainer",
        "steps": [
            {"function_scope": "Func", "caller_type": "CATIOther", "caller_def": ["Func", 1, "p", 1], "result_def": ["Func", 1, "c", 2], "kind": "query_interface", "result_type": "CATIPrtContainer"},
        ],
    })
    check("Item 9: Kernel rejects a first caller that is not start_type", p_wrong_start is False and "start_type" in r_wrong_start)

    p_unverified_idx, r_unverified_idx = Kernel._chain_contract_ok({
        "connectivity_status": "connected",
        "evidence_tier": "grounded_candidate_chain",
        "parse_status": "ok",
        "source_sha256": "abc1234",
        "index_consistency": "root_matched_metadata_unverified",
        "start_type": "CATIProduct",
        "target_type": "CATIPrtContainer",
        "steps": [
            {"function_scope": "Func", "caller_type": "CATIProduct", "caller_def": ["Func", 1, "p", 1], "result_def": ["Func", 1, "c", 2], "kind": "query_interface", "result_type": "CATIPrtContainer"},
        ],
    })
    check(
        "Item 9: Kernel rejects root-matched but metadata-unverified index",
        p_unverified_idx is False and "index_consistency" in r_unverified_idx,
    )

    p_scope_key, r_scope_key = Kernel._chain_contract_ok({
        "connectivity_status": "connected",
        "evidence_tier": "grounded_candidate_chain",
        "parse_status": "ok",
        "source_sha256": "abc1234",
        "index_consistency": "consistent",
        "start_type": "CATIProduct",
        "target_type": "CATIPrtContainer",
        "steps": [
            {"function_scope": "FuncA", "caller_type": "CATIProduct", "caller_def": ["FuncB", 1, "p", 1], "result_def": ["FuncA", 1, "c", 2], "kind": "query_interface", "result_type": "CATIPrtContainer"},
        ],
    })
    check(
        "Item 9: Kernel rejects a definition key from another function",
        p_scope_key is False and "function_scope" in r_scope_key,
    )

    p_no_result_def, r_no_result_def = Kernel._chain_contract_ok({
        "connectivity_status": "connected",
        "evidence_tier": "grounded_candidate_chain",
        "parse_status": "ok",
        "source_sha256": "abc1234",
        "index_consistency": "consistent",
        "start_type": "CATIProduct",
        "target_type": "CATIPrtContainer",
        "steps": [
            {"function_scope": "Func", "caller_type": "CATIProduct", "caller_def": ["Func", 1, "p", 1], "kind": "query_interface", "result_type": "CATIPrtContainer"},
        ],
    })
    check(
        "Item 9: Kernel rejects a target type label with no result_def",
        p_no_result_def is False and "not produced" in r_no_result_def,
    )

    # Item 10: Kernel candidate prioritization goes through the real selector.
    cand_frag = {
        "usecase": "CAAUsecaseFragment",
        "connectivity_status": "disconnected",
        "evidence_tier": "candidate_fragment",
        "parse_status": "ok",
        "source_sha256": "sha_frag",
        "index_consistency": "root_matched_metadata_unverified",
        "start_type": "CATIProduct",
        "target_type": "CATIPrtContainer",
        "steps": [{"function_scope": "Func", "ownership_status": "verified", "in_error_branch": False}],
    }
    cand_conn = {
        "usecase": "CAAUsecaseConnected",
        "connectivity_status": "connected",
        "evidence_tier": "grounded_candidate_chain",
        "parse_status": "ok",
        "source_sha256": "sha_conn",
        "index_consistency": "consistent",
        "start_type": "CATIProduct",
        "target_type": "CATIPrtContainer",
        "steps": [
            {"function_scope": "Func", "ownership_status": "verified", "in_error_branch": False, "caller_type": "CATIProduct", "caller_def": ["Func", 1, "p", 1], "result_def": ["Func", 1, "c", 2], "kind": "query_interface", "result_type": "CATIPrtContainer", "target": "CATIPrtContainer"}
        ],
    }

    class _FakeRetrieval:
        def explore_chain(self, start="", target="", query="", max_candidates=3):
            return {"status": "ok", "candidates": [cand_frag, cand_conn]}

    k_sel = Kernel()
    k_sel._retrieval_facade = _FakeRetrieval()
    k_sel._retrieval_attempted = True
    selected = k_sel._try_chain_exploration("如何从CATIProduct到CATIPrtContainer")
    check("Item 10: Kernel selector promotes candidate 2", selected is not None and selected["data"]["evidence_level"] == "official_usecase_chain")
    check("Item 10: Kernel selector did not keep the fragment", selected["data"]["candidate"]["usecase"] == "CAAUsecaseConnected")

    refused_dir = k_sel._try_chain_exploration("请比较CATIProduct和CATIPrtContainer")
    check("Item 10: Ambiguous identifier order is not a direction", refused_dir is None)

    # Item 11: Target filename substring is NOT an exact target match
    cands_fn = explorer.find_candidate_usecases(start="CATIProduct", target="Drawing")
    filtered_fn = [
        uc for uc in cands_fn
        if "Drawing" in uc.get("interfaces", [])
        or "Drawing" in uc.get("symbols", [])
        or "Drawing" in uc.get("methods", [])
    ]
    check("Item 11: Exact symbol filter drops filename-only substring hits", filtered_fn == [])

    # Item 12: Index consistency honestly declared
    if res_a.get("candidates"):
        check("Item 12: Index consistency states root_matched_metadata_unverified", res_a["candidates"][0].get("index_consistency") == "root_matched_metadata_unverified")

    # Item 13: Official positive examples: Assembly (CAAMmrGetPartFromProduct.cpp) & Drafting
    part_cpp = Path(r"C:\Program Files\Dassault Systemes\B28\CAADoc\CAAMechanicalModeler.edu\CAAMmrUtilities.m\src\CAAMmrGetPartFromProduct.cpp")
    if part_cpp.exists():
        s_part, conn_part, parse_part = explorer.extract_chain_from_cpp(part_cpp, "CATIProduct", "CATIPrtContainer")
        check("Item 13: Assembly official use case recovered connected", conn_part == "connected" and parse_part == "ok" and len(s_part) == 6)
    else:
        check("Item 13: Assembly official use case recovered connected", res_a.get("status") == "ok" and len(res_a.get("candidates", [])) > 0)
    check("Item 13: Drafting blind test recovered connected", res_blind.get("status") == "ok" and res_blind["candidates"][0]["connectivity_status"] == "connected")

    # Item 14: Cross-reference and zero workspace pollution
    check("Item 14: Official catalog unpolluted", "CATIEhiBundleSegment" not in cat_content)

print("=" * 70)
print(f"RESULTS: {passed}/{total} checks passed.")
print("=" * 70)

if passed < total:
    sys.exit(1)
