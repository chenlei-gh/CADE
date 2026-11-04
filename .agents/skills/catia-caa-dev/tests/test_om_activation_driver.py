#!/usr/bin/env python3
"""
Test P0-2: Object Modeler Activation & Evidence Driver Unit Tests
=================================================================
Validates:
1. Preflight system dictionary conflict detection and search-order rules.
2. Official Dassault CAAMmrMeasureSet use case and model asset inspection.
3. Layered L0~L5 evidence evaluation matrix:
   - L0 runtime structure
   - L1 PE DLL and DICO syntax
   - L2 target process identity
   - L3 exact module path matching
   - L4 OM dictionary resolution + constructor probe activation
   - L5 independent visual verification reservation
"""

import os
import sys
import tempfile
import pathlib

TESTS_DIR = pathlib.Path(__file__).parent
SKILL_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))
sys.path.insert(0, str(SKILL_ROOT / "tools"))

from verify_om_activation import OMActivationDriver

total = passed = 0


def ck(label: str, ok: bool, detail: str = ""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    status = "PASS" if ok else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)


print("=" * 70)
print("  Test P0-2: Object Modeler Activation Driver & Layered Evidence")
print("=" * 70)

driver = OMActivationDriver()

# ── 1. Line B: Official Use Case Inspection ─────────────────────────
print("\n[1] Official Use Case & Model Asset Inspection")
uc = driver.inspect_official_usecase()
ck("Line B: CAAMechanicalModeler.edu exists in B28", uc["edu_directory_exists"])
ck("Line B: CAAMmrMultiMeasureAndMeasureSet.CATPart exists", uc["catpart_model_exists"])
ck("Line B: Official CAAEMmrMeasureSetVisu.cpp exists", uc["official_cpp_source_exists"])
ck("Line B: Late type verified as CAAMmrMeasureSet", uc["late_type_confirmed"] == "CAAMmrMeasureSet")
ck("Line B: Interface verified as CATI3DGeoVisu", uc["interface_confirmed"] == "CATI3DGeoVisu")

# ── 2. Line C: Dictionary Conflict Analysis ─────────────────────────
print("\n[2] System Dictionary Conflict & Precedence Analysis")
dc = driver.check_system_dictionary_conflict()
ck("Line C: Scanned at least 500 B28 system dictionaries", dc["scanned_system_dictionaries"] >= 500, f"scanned={dc['scanned_system_dictionaries']}")
ck("Line C: Stock B28 has 0 conflict registrations for CAAMmrMeasureSet CATI3DGeoVisu",
   dc["exact_interface_conflicts"] == 0, f"conflicts={dc['exact_interface_conflicts']}")
ck("Line C: Isolated mapping is exclusive in clean B28", dc["exclusive_mapping"] is True)

# Test artificial conflict detection logic
with tempfile.TemporaryDirectory() as td_fake:
    fake_b28 = pathlib.Path(td_fake)
    fake_dico_dir = fake_b28 / "win_b64" / "code" / "dictionary"
    fake_dico_dir.mkdir(parents=True)
    fake_dico = fake_dico_dir / "ExistingSystem.dico"
    fake_dico.write_text("CAAMmrMeasureSet CATI3DGeoVisu libSystemConflict\n", encoding="latin-1")

    driver_conflict = OMActivationDriver(b28_root=str(fake_b28))
    dc_fake = driver_conflict.check_system_dictionary_conflict()
    ck("Line C: Driver detects simulated system dictionary conflict", dc_fake["has_system_conflict"] is True)
    ck("Line C: Conflict details record exact line and library",
       len(dc_fake["conflict_entries"]) == 1 and dc_fake["conflict_entries"][0]["library"] == "libSystemConflict")

# ── 3. Line D: Layered Evidence Evaluation Matrix (L0 ~ L5) ─────────
print("\n[3] Layered Evidence Evaluation Matrix (L0 ~ L5)")

with tempfile.TemporaryDirectory() as td_rt:
    rt_ws = pathlib.Path(td_rt)
    bin_dir = rt_ws / "win_b64" / "code" / "bin"
    dico_dir = rt_ws / "win_b64" / "code" / "dictionary"
    bin_dir.mkdir(parents=True)
    dico_dir.mkdir(parents=True)

    # 3.1 Initial state: valid structure (L0 PASS), missing binary (L1 FAIL)
    ev_init = driver.evaluate_layered_evidence(rt_ws)
    ck("L0: directory structure valid is PASS", ev_init["L0"]["status"] == "PASS")
    ck("L1: missing DLL is FAIL", ev_init["L1"]["status"] == "FAIL")
    ck("L2: unprobed PID is NOT_RUN", ev_init["L2"]["status"] == "NOT_RUN")
    ck("L3: unprobed modules is NOT_RUN", ev_init["L3"]["status"] == "NOT_RUN")
    ck("L4: unprobed OM trigger is UNKNOWN", ev_init["L4"]["status"] == "UNKNOWN")
    ck("L5: geometric visual verification is NOT_RUN", ev_init["L5"]["status"] == "NOT_RUN")
    ck("L5: evidence notes pending geometric implementation",
       ev_init["L5"]["evidence"]["status"] == "PENDING_GEOMETRIC_IMPL")

    # 3.2 L2: Target Process Identity
    ev_l2 = driver.evaluate_layered_evidence(rt_ws, cnext_pid=12345)
    ck("L2: valid cnext_pid is PASS", ev_l2["L2"]["status"] == "PASS" and ev_l2["L2"]["evidence"]["cnext_pid"] == 12345)

    # 3.3 L3: Exact Module Path Matching
    fake_dll_path = str(bin_dir / "AcceptanceMod.dll")
    ev_l3_miss = driver.evaluate_layered_evidence(rt_ws, loaded_modules=["C:\\Windows\\System32\\kernel32.dll"])
    ck("L3: missing target DLL in loaded modules is FAIL", ev_l3_miss["L3"]["status"] == "FAIL")

    ev_l3_hit = driver.evaluate_layered_evidence(rt_ws, loaded_modules=[fake_dll_path, "C:\\Windows\\System32\\kernel32.dll"])
    ck("L3: exact target DLL in loaded modules is PASS", ev_l3_hit["L3"]["status"] == "PASS")
    ck("L3: exact path confirmed", ev_l3_hit["L3"]["evidence"]["exact_match_pass"] is True)

    # 3.4 L4: Object Modeler Resolution & Extension Activation Probe
    probe_log = rt_ws / "probe.log"
    # Case A: QueryInterface succeeded (0x0) but probe was NOT hit
    ev_l4_no_probe = driver.evaluate_layered_evidence(rt_ws, query_interface_hr=0, probe_log_file=probe_log)
    ck("L4: QueryInterface S_OK without probe hit remains UNKNOWN (cannot prove our extension was activated)",
       ev_l4_no_probe["L4"]["status"] == "UNKNOWN")

    # Case B: QueryInterface failed (E_NOINTERFACE = 0x80004002)
    ev_l4_fail = driver.evaluate_layered_evidence(rt_ws, query_interface_hr=0x80004002, probe_log_file=probe_log)
    ck("L4: QueryInterface failure is FAIL", ev_l4_fail["L4"]["status"] == "FAIL")

    # Case C: QueryInterface succeeded AND constructor probe confirmed hit
    probe_log.write_text("INSTANTIATED: MyVisuExtension for CAAMmrMeasureSet\n", encoding="utf-8")
    ev_l4_pass = driver.evaluate_layered_evidence(rt_ws, query_interface_hr=0, probe_log_file=probe_log)
    ck("L4: QueryInterface S_OK WITH constructor probe hit is PASS", ev_l4_pass["L4"]["status"] == "PASS")
    ck("L4: evidence confirms active extension",
       ev_l4_pass["L4"]["evidence"]["active_extension"] == "MyVisuExtension")

print("\n" + "=" * 70)
print(f"  Result: {passed}/{total} tests passed ({'ALL PASS' if passed == total else 'SOME FAILED'})")
print("=" * 70)

if passed != total:
    sys.exit(1)
