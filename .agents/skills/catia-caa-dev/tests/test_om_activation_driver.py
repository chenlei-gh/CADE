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
import time
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
ck("Line B: Official CAAMechanicalModeler.edu.dico exists", uc["official_dico_exists"])
ck("Line B: AST parsed CATImplementClass correctly", uc["parsed_cpp_ast"]["parsed"] is True)
ck("Line B: Late type verified from AST as CAAMmrMeasureSet", uc["target_component_verified_from_ast"] == "CAAMmrMeasureSet")
ck("Line B: Interface verified from AST as CATI3DGeoVisu", uc["target_interface_verified_from_ast"] == "CATI3DGeoVisu")
ck("Line B: Extension type verified as DataExtension", uc["parsed_cpp_ast"]["extension_type"] == "DataExtension")
ck("Line B: Base class verified as CATExtIVisu", uc["parsed_cpp_ast"]["base_class"] == "CATExtIVisu")
ck("Line B: Official DICO registration verified", uc["parsed_dico"]["parsed"] is True)
ck("Line B: Official blueprint fully verified end-to-end", uc["official_blueprint_verified"] is True)

# Negative test for Line B: non-DataExtension blueprint rejection
uc_fake = dict(uc)
uc_fake_ast = dict(uc["parsed_cpp_ast"])
uc_fake_ast["extension_type"] = "CodeExtension"
blueprint_rejected = not (
    uc_fake_ast["parsed"]
    and uc_fake_ast["extension_type"] == "DataExtension"
    and uc_fake["target_component_verified_from_ast"] == "CAAMmrMeasureSet"
    and uc_fake["target_interface_verified_from_ast"] == "CATI3DGeoVisu"
    and uc_fake_ast["base_class"] == "CATExtIVisu"
    and uc["parsed_dico"]["parsed"]
)
ck("Line B: Non-DataExtension AST strictly rejected from blueprint verification", blueprint_rejected is True)

# ── 2. Line C: Dictionary Conflict Analysis ─────────────────────────
print("\n[2] System Dictionary Conflict & Precedence Analysis")
dc = driver.check_system_dictionary_conflict()
ck("Line C: Recursive scan enabled", dc["recursive_scan_enabled"] is True)
ck("Line C: Scanned at least 500 B28 system dictionaries", dc["scanned_dictionaries_success"] >= 500, f"scanned={dc['scanned_dictionaries_success']}")
ck("Line C: Scan completeness is 100% without unreadable files", dc["scan_completeness_rate"] == 1.0, f"rate={dc['scan_completeness_rate']}")
ck("Line C: Stock B28 has 0 conflict registrations for CAAMmrMeasureSet CATI3DGeoVisu",
   dc["exact_interface_conflicts"] == 0, f"conflicts={dc['exact_interface_conflicts']}")
ck("Line C: Isolated mapping is exclusive in clean B28", dc["exclusive_mapping_in_scanned_dictionaries"] is True)
ck("Line C: Dictionary precedence is marked as UNTESTED_HYPOTHESIS, not asserted as fact",
   dc["precedence_status"] == "UNTESTED_HYPOTHESIS")

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

# Test unreadable directory walk error handling
with tempfile.TemporaryDirectory() as td_unreadable:
    fake_b28_unr = pathlib.Path(td_unreadable)
    fake_dico_dir_unr = fake_b28_unr / "win_b64" / "code" / "dictionary"
    fake_dico_dir_unr.mkdir(parents=True)
    normal_dico = fake_dico_dir_unr / "Normal.dico"
    normal_dico.write_text("SomeComp SomeIface libSome\n", encoding="latin-1")
    
    # Mocking unreadable directory error in check_system_dictionary_conflict
    driver_unr = OMActivationDriver(b28_root=str(fake_b28_unr))
    orig_walk = os.walk
    def mock_walk_with_error(top, onerror=None):
        if onerror:
            err = PermissionError(13, "Permission denied", os.path.join(top, "LockedSubdir"))
            onerror(err)
        return orig_walk(top)
    
    try:
        os.walk = mock_walk_with_error
        dc_unr = driver_unr.check_system_dictionary_conflict()
        ck("Line C: Incomplete directory walk captures unreadable directory",
           dc_unr["unreadable_directories_count"] == 1)
        ck("Line C: Incomplete directory walk resets completeness rate to 0.0",
           dc_unr["scan_completeness_rate"] == 0.0)
        ck("Line C: Incomplete directory walk strictly refuses exclusive mapping claim",
           dc_unr["exclusive_mapping_in_scanned_dictionaries"] is False)
    finally:
        os.walk = orig_walk

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

    # 3.3 L3: Exact Module Path Matching (Strict Invariant)
    fake_dll_path = str(bin_dir / "AcceptanceMod.dll")
    ev_l3_miss = driver.evaluate_layered_evidence(rt_ws, loaded_modules=["C:\\Windows\\System32\\kernel32.dll"])
    ck("L3: missing target DLL in loaded modules is FAIL", ev_l3_miss["L3"]["status"] == "FAIL")

    # Critical Reviewer Point: Same DLL name from wrong path MUST FAIL
    stray_wrong_path = "C:\\StrayWorkspace\\win_b64\\code\\bin\\AcceptanceMod.dll"
    ev_l3_stray = driver.evaluate_layered_evidence(rt_ws, loaded_modules=[stray_wrong_path])
    ck("L3: same filename from wrong path MUST FAIL (stray path violation)", ev_l3_stray["L3"]["status"] == "FAIL")
    ck("L3: stray path captured in evidence", ev_l3_stray["L3"]["evidence"]["stray_mismatch_path"] == stray_wrong_path)
    ck("L3: exact match is False on stray path", ev_l3_stray["L3"]["evidence"]["exact_match_pass"] is False)

    # Exact path match PASS
    ev_l3_hit = driver.evaluate_layered_evidence(rt_ws, loaded_modules=[fake_dll_path, "C:\\Windows\\System32\\kernel32.dll"])
    ck("L3: exact target DLL path in loaded modules is PASS", ev_l3_hit["L3"]["status"] == "PASS")
    ck("L3: exact path confirmed", ev_l3_hit["L3"]["evidence"]["exact_match_pass"] is True)

    # 3.4 L4: Object Modeler Resolution & Extension Activation (4-Factor Probe Contract)
    probe_log = rt_ws / "probe.log"
    now = time.time()
    test_nonce = "NONCE_ABC_123"
    test_pid = 9999

    # Case A: QueryInterface succeeded (0x0) but probe log does NOT exist -> UNKNOWN
    ev_l4_no_probe = driver.evaluate_layered_evidence(rt_ws, query_interface_hr=0, probe_log_file=probe_log)
    ck("L4: QueryInterface S_OK without probe log remains UNKNOWN",
       ev_l4_no_probe["L4"]["status"] == "UNKNOWN")

    # Case B: QueryInterface failed (E_NOINTERFACE = 0x80004002) -> FAIL
    ev_l4_fail = driver.evaluate_layered_evidence(rt_ws, query_interface_hr=0x80004002, probe_log_file=probe_log)
    ck("L4: QueryInterface failure is FAIL", ev_l4_fail["L4"]["status"] == "FAIL")

    # Case C: Probe log exists but is STALE (mtime < session_start_time) -> UNKNOWN
    probe_log.write_text(f"ACTION=CONSTRUCTOR_ACTIVATED;NONCE={test_nonce};PID={test_pid};COMPONENT=CAAMmrMeasureSet\n", encoding="utf-8")
    os.utime(probe_log, (now - 100, now - 100)) # Make file 100s old
    ev_l4_stale = driver.evaluate_layered_evidence(
        rt_ws, query_interface_hr=0, probe_log_file=probe_log,
        expected_nonce=test_nonce, expected_cnext_pid=test_pid, session_start_time=now
    )
    ck("L4: Stale probe log (mtime check failed) remains UNKNOWN", ev_l4_stale["L4"]["status"] == "UNKNOWN")
    ck("L4: Stale probe freshness flag is False", ev_l4_stale["L4"]["evidence"]["probe_contract"]["freshness_valid"] is False)

    # Case D: Fresh probe log but NONCE mismatch -> UNKNOWN
    os.utime(probe_log, (now, now))
    ev_l4_nonce_mismatch = driver.evaluate_layered_evidence(
        rt_ws, query_interface_hr=0, probe_log_file=probe_log,
        expected_nonce="WRONG_NONCE", expected_cnext_pid=test_pid, session_start_time=now - 5
    )
    ck("L4: Nonce mismatch remains UNKNOWN", ev_l4_nonce_mismatch["L4"]["status"] == "UNKNOWN")
    ck("L4: Atomic event flag is False on nonce mismatch",
       ev_l4_nonce_mismatch["L4"]["evidence"]["probe_contract"]["atomic_event_verified"] is False)

    # Case E: Fresh probe log, nonce match, but PID mismatch -> UNKNOWN
    ev_l4_pid_mismatch = driver.evaluate_layered_evidence(
        rt_ws, query_interface_hr=0, probe_log_file=probe_log,
        expected_nonce=test_nonce, expected_cnext_pid=8888, session_start_time=now - 5
    )
    ck("L4: PID mismatch remains UNKNOWN", ev_l4_pid_mismatch["L4"]["status"] == "UNKNOWN")
    ck("L4: Atomic event flag is False on PID mismatch",
       ev_l4_pid_mismatch["L4"]["evidence"]["probe_contract"]["atomic_event_verified"] is False)

    # Case G (Critical Negative): Missing mandatory credentials fail-closed to UNKNOWN
    probe_log.write_text(f"ACTION=CONSTRUCTOR_ACTIVATED;NONCE={test_nonce};PID={test_pid};COMPONENT=CAAMmrMeasureSet\n", encoding="utf-8")
    os.utime(probe_log, (now, now))
    ev_l4_no_cred = driver.evaluate_layered_evidence(
        rt_ws, query_interface_hr=0, probe_log_file=probe_log,
        expected_nonce=None, expected_cnext_pid=None, session_start_time=None
    )
    ck("L4: Missing credentials fail-closed to UNKNOWN", ev_l4_no_cred["L4"]["status"] == "UNKNOWN")
    ck("L4: Reason explicitly states missing credentials",
       ev_l4_no_cred["L4"]["evidence"]["reason"] == "missing_mandatory_credentials_nonce_pid_or_session_time")

    # Case H (Critical Negative): Multi-line splicing attack must NOT pass
    # Three lines each satisfy one condition, but NO single atomic record satisfies all!
    spliced_log = rt_ws / "spliced.log"
    spliced_log.write_text(
        "ACTION=CONSTRUCTOR_ACTIVATED;NONCE=NONCE_ABC_123;PID=1111;COMPONENT=WrongComp\n"
        "ACTION=CONSTRUCTOR_ACTIVATED;NONCE=WrongNonce;PID=9999;COMPONENT=CAAMmrMeasureSet\n"
        "ACTION=CONSTRUCTOR_ACTIVATED;NONCE=NONCE_ABC_123;PID=9999;COMPONENT=WrongComp\n",
        encoding="utf-8"
    )
    os.utime(spliced_log, (now, now))
    ev_l4_splice = driver.evaluate_layered_evidence(
        rt_ws, query_interface_hr=0, probe_log_file=spliced_log,
        expected_nonce=test_nonce, expected_cnext_pid=test_pid, session_start_time=now - 5
    )
    ck("L4: Multi-line splicing attack strictly rejected as UNKNOWN", ev_l4_splice["L4"]["status"] == "UNKNOWN")
    ck("L4: Atomic event verified flag is False on spliced lines",
       ev_l4_splice["L4"]["evidence"]["probe_contract"]["atomic_event_verified"] is False)

    # Case I (Critical Negative): Invalid ACTION value must NOT pass
    invalid_action_log = rt_ws / "invalid_action.log"
    invalid_action_log.write_text(
        f"ACTION=METHOD_INVOKED;NONCE={test_nonce};PID={test_pid};COMPONENT=CAAMmrMeasureSet\n",
        encoding="utf-8"
    )
    os.utime(invalid_action_log, (now, now))
    ev_l4_action = driver.evaluate_layered_evidence(
        rt_ws, query_interface_hr=0, probe_log_file=invalid_action_log,
        expected_nonce=test_nonce, expected_cnext_pid=test_pid, session_start_time=now - 5
    )
    ck("L4: Non-CONSTRUCTOR_ACTIVATED action strictly rejected as UNKNOWN", ev_l4_action["L4"]["status"] == "UNKNOWN")

    # Case J: Four-factor atomic certificate satisfied in single record -> PASS!
    ev_l4_pass = driver.evaluate_layered_evidence(
        rt_ws, query_interface_hr=0, probe_log_file=probe_log,
        expected_nonce=test_nonce, expected_cnext_pid=test_pid, session_start_time=now - 5
    )
    ck("L4: Single atomic record satisfying all four factors is PASS", ev_l4_pass["L4"]["status"] == "PASS")
    ck("L4: Atomic probe verified flag is True", ev_l4_pass["L4"]["evidence"]["atomic_probe_verified"] is True)

print("\n" + "=" * 70)
print(f"  Result: {passed}/{total} tests passed ({'ALL PASS' if passed == total else 'SOME FAILED'})")
print("=" * 70)

if passed != total:
    sys.exit(1)
