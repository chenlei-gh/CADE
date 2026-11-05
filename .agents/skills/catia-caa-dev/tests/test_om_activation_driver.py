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
from pathlib import Path
from unittest.mock import patch

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
# Test Level 1: Direct test against pure production method OMActivationDriver.verify_blueprint_contract
fake_ast_code = dict(uc["parsed_cpp_ast"], extension_type="CodeExtension")
fake_ast_comp = dict(uc["parsed_cpp_ast"], target_late_type="WrongLateType")
fake_ast_iface = dict(uc["parsed_cpp_ast"], tie_interface="WrongInterface")
fake_ast_base = dict(uc["parsed_cpp_ast"], base_class="WrongBaseClass")

ck("Line B: verify_blueprint_contract rejects CodeExtension",
   OMActivationDriver.verify_blueprint_contract(fake_ast_code, uc["parsed_dico"]) is False)
ck("Line B: verify_blueprint_contract rejects mismatched component",
   OMActivationDriver.verify_blueprint_contract(fake_ast_comp, uc["parsed_dico"]) is False)
ck("Line B: verify_blueprint_contract rejects mismatched interface",
   OMActivationDriver.verify_blueprint_contract(fake_ast_iface, uc["parsed_dico"]) is False)
ck("Line B: verify_blueprint_contract rejects mismatched base class",
   OMActivationDriver.verify_blueprint_contract(fake_ast_base, uc["parsed_dico"]) is False)

fake_dico_mismatch = {
    "parsed": True,
    "matching_entries": [
        {"component": "WrongComponent", "interface": "WrongInterface", "library": "libWrong"}
    ]
}
ck("Line B: verify_blueprint_contract rejects mismatched DICO entry",
   OMActivationDriver.verify_blueprint_contract(uc["parsed_cpp_ast"], fake_dico_mismatch) is False)

# Test Level 2: End-to-end negative test invoking production inspect_official_usecase with overridden source
with tempfile.TemporaryDirectory() as td:
    fake_cpp_path = Path(td) / "CAAEMmrFakeVisu.cpp"
    fake_cpp_path.write_text(
        '#include "CAAEMmrFakeVisu.h"\n'
        'CATImplementClass(CAAEMmrFakeVisu, CodeExtension, CATExtIVisu, CAAMmrMeasureSet);\n'
        'TIE_CATI3DGeoVisu(CAAEMmrFakeVisu);\n',
        encoding="utf-8"
    )
    uc_fake_prod = driver.inspect_official_usecase(cpp_path_override=fake_cpp_path)
    ck("Line B: Production inspect_official_usecase parses overridden CodeExtension",
       uc_fake_prod["parsed_cpp_ast"]["extension_type"] == "CodeExtension")
    ck("Line B: Production inspect_official_usecase strictly rejects CodeExtension blueprint",
       uc_fake_prod["official_blueprint_verified"] is False)

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

    # 3.2 L2: Target Process Identity (Strict Unified Reuse)
    ev_l2_raw = driver.evaluate_layered_evidence(rt_ws, cnext_pid=12345)
    ck("L2: raw cnext_pid without session identity proof is strictly UNKNOWN",
       ev_l2_raw["L2"]["status"] == "UNKNOWN" and ev_l2_raw["L2"]["evidence"]["cnext_pid"] == 12345)

    with patch("verify_om_activation.identify_target_cnext", return_value=("PASS", 12345, {"method": "mock_process_tree"})):
        ev_l2_ident = driver.evaluate_layered_evidence(rt_ws, t_start=time.time())
    ck("L2: verified cnext_identity from run.identify_target_cnext is PASS",
       ev_l2_ident["L2"]["status"] == "PASS" and ev_l2_ident["L2"]["evidence"]["cnext_pid"] == 12345)

    # 3.3 L3: Exact Module Path Matching (Strict Invariant Unified with run.verify_module_loaded)
    fake_dll_path = str(bin_dir / "AcceptanceMod.dll")
    other_sys_dll = str(Path(tempfile.gettempdir()) / "System32" / "other.dll")
    with patch("verify_om_activation.identify_target_cnext", return_value=("PASS", 12345, {"method": "mock_process_tree"})):
        with patch("verify_om_activation.verify_module_loaded", return_value=("FAIL", {"reason": "dll_not_loaded", "enumeration_complete": True, "exact_match_pass": False})):
            ev_l3_miss = driver.evaluate_layered_evidence(rt_ws, t_start=time.time())
    ck("L3: missing target DLL in loaded modules is FAIL", ev_l3_miss["L3"]["status"] == "FAIL")

    # Critical Reviewer Point: Same DLL name from wrong path MUST FAIL
    stray_wrong_path = str(Path(tempfile.gettempdir()) / "StrayWorkspace" / "win_b64" / "code" / "bin" / "AcceptanceMod.dll")
    with patch("verify_om_activation.identify_target_cnext", return_value=("PASS", 12345, {"method": "mock_process_tree"})):
        with patch("verify_om_activation.verify_module_loaded", return_value=("FAIL", {"stray_mismatch_path": stray_wrong_path, "exact_match_pass": False, "reason": "stray_dll_loaded_from_wrong_path"})):
            ev_l3_stray = driver.evaluate_layered_evidence(rt_ws, t_start=time.time())
    ck("L3: same filename from wrong path MUST FAIL (stray path violation)", ev_l3_stray["L3"]["status"] == "FAIL")
    ck("L3: stray path captured in evidence", ev_l3_stray["L3"]["evidence"]["stray_mismatch_path"] == stray_wrong_path)
    ck("L3: exact match is False on stray path", ev_l3_stray["L3"]["evidence"]["exact_match_pass"] is False)

    # Exact path match PASS
    with patch("verify_om_activation.identify_target_cnext", return_value=("PASS", 12345, {"method": "mock_process_tree"})):
        with patch("verify_om_activation.verify_module_loaded", return_value=("PASS", {"matched_path": fake_dll_path, "exact_matched_path": fake_dll_path, "exact_match_pass": True, "enumeration_complete": True})):
            ev_l3_hit = driver.evaluate_layered_evidence(rt_ws, t_start=time.time())
    ck("L3: exact target DLL path in loaded modules is PASS", ev_l3_hit["L3"]["status"] == "PASS")
    ck("L3: exact path confirmed", ev_l3_hit["L3"]["evidence"]["exact_match_pass"] is True)

    # Defensive Anti-Bypass Testing: evaluate_layered_evidence strictly rejects bypass parameters
    cnext_id_rejected = False
    try:
        driver.evaluate_layered_evidence(rt_ws, cnext_identity=("PASS", 12345, {}))
    except TypeError:
        cnext_id_rejected = True
    ck("L2 Defensive: evaluate_layered_evidence rejects cnext_identity kwarg", cnext_id_rejected)

    l3_res_rejected = False
    try:
        driver.evaluate_layered_evidence(rt_ws, l3_result=("PASS", {}))
    except TypeError:
        l3_res_rejected = True
    ck("L3 Defensive: evaluate_layered_evidence rejects l3_result kwarg", l3_res_rejected)

    # Defensive Anti-Bypass Testing: Forged internal session snapshot is strictly rejected
    class ForgedSessionSnapshot:
        _token = object()  # Token does not match driver._auth_token
        l2_identity = ("PASS", 77777, {"method": "forged"})
        l3_result = ("PASS", {"matched_path": "forged", "exact_match_pass": True})

    driver._active_session_snapshot = ForgedSessionSnapshot()
    ev_forged = driver.evaluate_layered_evidence(rt_ws)
    driver._active_session_snapshot = None
    ck("Defensive: Forged internal snapshot rejected, L2 is NOT_RUN", ev_forged["L2"]["status"] == "NOT_RUN")
    ck("Defensive: Forged internal snapshot rejected, L3 is NOT_RUN", ev_forged["L3"]["status"] == "NOT_RUN")

    # 3.4 L4: Object Modeler Resolution & Extension Activation (4-Factor Probe Contract)
    probe_log = rt_ws / "probe.log"
    now = time.time()
    test_nonce = "NONCE_ABC_123"
    test_pid = 9999

    # Case A: Probe log does NOT exist -> UNKNOWN
    ev_l4_no_probe = driver.evaluate_layered_evidence(rt_ws, probe_log_file=probe_log)
    ck("L4: Probe log missing strictly remains UNKNOWN",
       ev_l4_no_probe["L4"]["status"] == "UNKNOWN")

    # Case B: Without authentic 4-factor probe, L4 strictly remains UNKNOWN (no false FAIL/PASS)
    ev_l4_unverified = driver.evaluate_layered_evidence(rt_ws, probe_log_file=probe_log)
    ck("L4: Unverified call strictly remains UNKNOWN (no false FAIL/PASS)",
       ev_l4_unverified["L4"]["status"] == "UNKNOWN")

    # Case C: Probe log exists but is STALE (mtime < session_start_time) -> UNKNOWN
    probe_log.write_text(f"ACTION=CONSTRUCTOR_ACTIVATED;NONCE={test_nonce};PID={test_pid};COMPONENT=CAAMmrMeasureSet\n", encoding="utf-8")
    os.utime(probe_log, (now - 100, now - 100)) # Make file 100s old
    ev_l4_stale = driver.evaluate_layered_evidence(
        rt_ws, probe_log_file=probe_log,
        expected_nonce=test_nonce, expected_cnext_pid=test_pid, session_start_time=now
    )
    ck("L4: Stale probe log (mtime check failed) remains UNKNOWN", ev_l4_stale["L4"]["status"] == "UNKNOWN")
    ck("L4: Stale probe freshness flag is False", ev_l4_stale["L4"]["evidence"]["probe_contract"]["freshness_valid"] is False)

    # Case D: Fresh probe log but NONCE mismatch -> UNKNOWN
    os.utime(probe_log, (now, now))
    ev_l4_nonce_mismatch = driver.evaluate_layered_evidence(
        rt_ws, probe_log_file=probe_log,
        expected_nonce="WRONG_NONCE", expected_cnext_pid=test_pid, session_start_time=now - 5
    )
    ck("L4: Nonce mismatch remains UNKNOWN", ev_l4_nonce_mismatch["L4"]["status"] == "UNKNOWN")
    ck("L4: Atomic event flag is False on nonce mismatch",
       ev_l4_nonce_mismatch["L4"]["evidence"]["probe_contract"]["atomic_event_verified"] is False)

    # Case E: Fresh probe log, nonce match, but PID mismatch -> UNKNOWN
    ev_l4_pid_mismatch = driver.evaluate_layered_evidence(
        rt_ws, probe_log_file=probe_log,
        expected_nonce=test_nonce, expected_cnext_pid=8888, session_start_time=now - 5
    )
    ck("L4: PID mismatch remains UNKNOWN", ev_l4_pid_mismatch["L4"]["status"] == "UNKNOWN")
    ck("L4: Atomic event flag is False on PID mismatch",
       ev_l4_pid_mismatch["L4"]["evidence"]["probe_contract"]["atomic_event_verified"] is False)

    # Case G (Critical Negative): Missing mandatory credentials fail-closed to UNKNOWN
    probe_log.write_text(f"ACTION=CONSTRUCTOR_ACTIVATED;NONCE={test_nonce};PID={test_pid};COMPONENT=CAAMmrMeasureSet\n", encoding="utf-8")
    os.utime(probe_log, (now, now))
    ev_l4_no_cred = driver.evaluate_layered_evidence(
        rt_ws, probe_log_file=probe_log,
        expected_nonce=None, expected_cnext_pid=None, session_start_time=None
    )
    ck("L4: Missing credentials fail-closed to UNKNOWN", ev_l4_no_cred["L4"]["status"] == "UNKNOWN")
    ck("L4: Reason explicitly states missing credentials",
       ev_l4_no_cred["L4"]["evidence"]["reason"] == "missing_mandatory_credentials_nonce_pid_or_session_time")

    # Case G2 (Strict Type Boundary Defense): Reject bool PID (isinstance(True, int) is True)
    ev_l4_bool_pid = driver.evaluate_layered_evidence(
        rt_ws, probe_log_file=probe_log,
        expected_nonce=test_nonce, expected_cnext_pid=True, session_start_time=now - 5
    )
    ck("L4: bool PID (True) strictly rejected by type guard", ev_l4_bool_pid["L4"]["status"] == "UNKNOWN")
    ck("L4: bool PID fails credentials_provided",
       ev_l4_bool_pid["L4"]["evidence"]["probe_contract"]["credentials_provided"] is False)

    # Case G3 (Strict Type Boundary Defense): Reject bool session_start_time
    ev_l4_bool_time = driver.evaluate_layered_evidence(
        rt_ws, probe_log_file=probe_log,
        expected_nonce=test_nonce, expected_cnext_pid=test_pid, session_start_time=True
    )
    ck("L4: bool session_start_time (True) strictly rejected by type guard", ev_l4_bool_time["L4"]["status"] == "UNKNOWN")
    ck("L4: bool time fails credentials_provided",
       ev_l4_bool_time["L4"]["evidence"]["probe_contract"]["credentials_provided"] is False)

    # Case G4 (Strict Type Boundary Defense): Reject non-finite session_start_time (inf, nan)
    import math
    ev_l4_inf_time = driver.evaluate_layered_evidence(
        rt_ws, probe_log_file=probe_log,
        expected_nonce=test_nonce, expected_cnext_pid=test_pid, session_start_time=float("inf")
    )
    ck("L4: inf session_start_time strictly rejected", ev_l4_inf_time["L4"]["status"] == "UNKNOWN")

    ev_l4_nan_time = driver.evaluate_layered_evidence(
        rt_ws, probe_log_file=probe_log,
        expected_nonce=test_nonce, expected_cnext_pid=test_pid, session_start_time=float("nan")
    )
    ck("L4: nan session_start_time strictly rejected", ev_l4_nan_time["L4"]["status"] == "UNKNOWN")

    # Case G5 (Strict Value Boundary Defense): Reject non-positive PID and whitespace nonce
    ev_l4_zero_pid = driver.evaluate_layered_evidence(
        rt_ws, probe_log_file=probe_log,
        expected_nonce=test_nonce, expected_cnext_pid=0, session_start_time=now - 5
    )
    ck("L4: PID=0 strictly rejected", ev_l4_zero_pid["L4"]["status"] == "UNKNOWN")

    ev_l4_blank_nonce = driver.evaluate_layered_evidence(
        rt_ws, probe_log_file=probe_log,
        expected_nonce="   ", expected_cnext_pid=test_pid, session_start_time=now - 5
    )
    ck("L4: whitespace nonce strictly rejected", ev_l4_blank_nonce["L4"]["status"] == "UNKNOWN")

    # Case G6 (Strict Arithmetic Overflow Defense): Reject ultra-large int timestamp causing OverflowError in math.isfinite
    ev_l4_overflow_time = driver.evaluate_layered_evidence(
        rt_ws, probe_log_file=probe_log,
        expected_nonce=test_nonce, expected_cnext_pid=test_pid, session_start_time=10**3000
    )
    ck("L4: 10**3000 overflow session_start_time safely fail-closed to UNKNOWN",
       ev_l4_overflow_time["L4"]["status"] == "UNKNOWN")
    ck("L4: overflow time fails credentials_provided",
       ev_l4_overflow_time["L4"]["evidence"]["probe_contract"]["credentials_provided"] is False)

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
        rt_ws, probe_log_file=spliced_log,
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
        rt_ws, probe_log_file=invalid_action_log,
        expected_nonce=test_nonce, expected_cnext_pid=test_pid, session_start_time=now - 5
    )
    ck("L4: Non-CONSTRUCTOR_ACTIVATED action strictly rejected as UNKNOWN", ev_l4_action["L4"]["status"] == "UNKNOWN")

    # Case J: Four-factor atomic certificate satisfies constructor probe -> Constructor verified, but QI unproven!
    ev_l4_pass = driver.evaluate_layered_evidence(
        rt_ws, probe_log_file=probe_log,
        expected_nonce=test_nonce, expected_cnext_pid=test_pid, session_start_time=now - 5
    )
    ck("L4: Single atomic record satisfies constructor probe verification",
       ev_l4_pass["L4"]["evidence"]["constructor_probe_verified"] is True)
    ck("L4: Status explicitly states CONSTRUCTOR_ACTIVATED_QI_UNPROVEN",
       ev_l4_pass["L4"]["evidence"]["status"] == "CONSTRUCTOR_ACTIVATED_QI_UNPROVEN")
    ck("L4: Reason indicates missing authentic in-session QI probe certificate",
       ev_l4_pass["L4"]["evidence"]["reason"] == "query_interface_unverified_requires_in_session_qi_probe_certificate")

    # Case K: L2 & L3 reuse unified run.py infrastructure
    mock_cnext_id = ("PASS", 54321, {"method": "process_tree_ancestor_match"})
    with patch("verify_om_activation.identify_target_cnext", return_value=mock_cnext_id):
        ev_l2_unified = driver.evaluate_layered_evidence(rt_ws, t_start=now)
    ck("L2: Reuses identify_target_cnext result with source tracking",
       ev_l2_unified["L2"]["status"] == "PASS" and ev_l2_unified["L2"]["evidence"]["source"] == "run.identify_target_cnext")
    ck("L2: Correctly captures PID from unified identity",
       ev_l2_unified["L2"]["evidence"]["cnext_pid"] == 54321)

# ── 4. Live Activation Protocol & Execution Driver (Phase A ~ D) ────
print("\n[4] Live Activation Protocol & Execution Driver (Phase A ~ D)")

import struct

def make_test_pe_image():
    file_align = 512
    sec_align = 0x1000
    size_opt_hdr = 240
    dos_hdr = b"MZ" + b"\x00" * 0x3A + struct.pack("<I", 0x40)
    pe_sig = b"PE\x00\x00"
    coff_hdr = struct.pack(
        "<HHIIIHH", 0x8664, 1, 0, 0, 0, size_opt_hdr, 0x2002
    )
    opt = bytearray(size_opt_hdr)
    struct.pack_into("<H", opt, 0, 0x020B)
    struct.pack_into("<I", opt, 32, sec_align)
    struct.pack_into("<I", opt, 36, file_align)
    struct.pack_into("<I", opt, 56, 0x2000)
    struct.pack_into("<I", opt, 60, file_align)
    sec_hdr = b".text\x00\x00\x00" + struct.pack(
        "<IIII", 0x100, sec_align, file_align, file_align
    ) + b"\x00" * 16
    blob = dos_hdr + pe_sig + coff_hdr + bytes(opt) + sec_hdr
    if len(blob) < file_align * 2:
        blob += b"\x00" * (file_align * 2 - len(blob))
    return blob

# 4.1 Trigger Macro Generator Test
with tempfile.TemporaryDirectory() as td_macro:
    m_dir = Path(td_macro)
    model_p = m_dir / "TestModel.CATPart"
    model_p.write_bytes(b"DUMMY_CATPART")
    script_p = m_dir / "trigger.CATScript"

    macro_text = driver.generate_trigger_macro(model_p, script_p)
    ck("Phase C: generate_trigger_macro writes CATScript file", script_p.is_file())
    ck("Phase C: trigger macro contains Documents.Open", 'CATIA.Documents.Open' in macro_text or 'docs.Open' in macro_text)
    ck("Phase C: trigger macro invokes ActiveViewer.Reframe", 'viewer.Reframe' in macro_text)
    ck("Phase C: trigger macro closes document", 'doc.Close' in macro_text)
    ck("Phase C: trigger macro exits CATIA via Quit", 'CATIA.Quit' in macro_text)

# 4.2 End-to-End Live Activation Positive Test (All L0~L4 PASS, L5 NOT_RUN)
with tempfile.TemporaryDirectory() as td_live:
    live_ws = Path(td_live)
    bin_dir = live_ws / "win_b64" / "code" / "bin"
    dico_dir = live_ws / "win_b64" / "code" / "dictionary"
    bin_dir.mkdir(parents=True)
    dico_dir.mkdir(parents=True)

    target_dll = bin_dir / "AcceptanceMod.dll"
    target_dll.write_bytes(make_test_pe_image())

    target_dico = dico_dir / "AcceptanceFw.dico"
    target_dico.write_text("CAAMmrMeasureSet CATI3DGeoVisu libAcceptanceMod\n", encoding="latin-1")

    # Mock runner simulating successful CNEXT -macro execution and constructor probe emission
    simulated_cnext_pid = 24680
    probe_captured_in_runner = {}

    def mock_successful_runner(macro_path: str, workspace_path: str, timeout: int):
        p_file = os.environ.get("CADE_PROBE_FILE")
        p_nonce = os.environ.get("CADE_PROBE_NONCE")
        probe_captured_in_runner["file"] = p_file
        probe_captured_in_runner["nonce"] = p_nonce
        if p_file:
            with open(p_file, "a", encoding="utf-8") as fp:
                fp.write(
                    f"ACTION=CONSTRUCTOR_ACTIVATED;NONCE={p_nonce};"
                    f"PID={simulated_cnext_pid};COMPONENT=CAAMmrMeasureSet\n"
                )
        return {
            "status": "success",
            "message": "Macro execution completed (exit 0)",
        }

    mock_id_return = ("PASS", simulated_cnext_pid, {"method": "mock_session_tree"})
    mock_l3_return = ("PASS", {
        "matched_path": str(target_dll),
        "exact_matched_path": str(target_dll),
        "exact_match_pass": True,
        "source": "run.verify_module_loaded",
    })

    with patch("verify_om_activation.identify_target_cnext", return_value=mock_id_return) as mock_id:
        with patch("verify_om_activation.verify_module_loaded", return_value=mock_l3_return) as mock_l3:
            res_live = driver.execute_live_activation(
                workspace_path=str(live_ws),
                runner_fn=mock_successful_runner,
            )
            ck("Single Source of Truth: identify_target_cnext was called", mock_id.called)
            ck("Single Source of Truth: verify_module_loaded was called for target PID",
               mock_l3.called and mock_l3.call_args[0][0] == simulated_cnext_pid)

    ck("Live Activation: Protocol identified as Live_Activation_Protocol_CNEXT_Macro",
       res_live["protocol"] == "Live_Activation_Protocol_CNEXT_Macro")
    ck("Live Activation: Overall status remains UNKNOWN without in-session QI probe (no false PASS)",
       res_live["overall_status"] == "UNKNOWN")
    ck("Phase A: Runtime view bin directory validated", res_live["phase_a_runtime_view"]["bin_exists"] is True)
    ck("Phase A: Runtime view dictionary directory validated", res_live["phase_a_runtime_view"]["dictionary_dir_exists"] is True)
    ck("Phase A: Target DLL confirmed present", res_live["phase_a_runtime_view"]["target_dll_exists"] is True)
    ck("Phase A: Target DICO confirmed present", res_live["phase_a_runtime_view"]["target_dico_exists"] is True)
    ck("Phase B: Official model resolved and exists", res_live["phase_b_model"]["model_exists"] is True)
    ck("Phase B: Target component confirmed as CAAMmrMeasureSet", res_live["phase_b_model"]["component"] == "CAAMmrMeasureSet")
    ck("Phase C: Macro execution status is success", res_live["phase_c_macro_execution"]["status"] == "success")
    ck("Phase C & D: Probe environment variables were injected to runner",
       bool(probe_captured_in_runner.get("file")) and bool(probe_captured_in_runner.get("nonce")))
    ck("Phase C & D: Probe environment variables safely cleaned up afterwards",
       "CADE_PROBE_FILE" not in os.environ and "CADE_PROBE_NONCE" not in os.environ)

    # Layered evidence status verification
    ev_live = res_live["phase_d_evidence"]
    ck("Phase D: L0 status is PASS", ev_live["L0"]["status"] == "PASS")
    ck("Phase D: L1 status is PASS", ev_live["L1"]["status"] == "PASS")
    ck("Phase D: L2 status is PASS", ev_live["L2"]["status"] == "PASS")
    ck("Phase D: L3 status is PASS", ev_live["L3"]["status"] == "PASS")
    ck("Phase D: L3 exact matched path matches target DLL",
       os.path.normcase(ev_live["L3"]["evidence"]["exact_matched_path"]) == os.path.normcase(str(target_dll)))
    ck("Phase D: L4 constructor probe is verified",
       ev_live["L4"]["evidence"]["constructor_probe_verified"] is True)
    ck("Phase D: L4 status strictly remains UNKNOWN (prevents QI false pass)",
       ev_live["L4"]["status"] == "UNKNOWN")
    ck("Phase D: L4 activated extension confirmed as MyVisuExtension",
       ev_live["L4"]["evidence"]["activated_extension"] == "MyVisuExtension")
    ck("Phase D: L5 status strictly retained as NOT_RUN", ev_live["L5"]["status"] == "NOT_RUN")

# 4.3 Negative & Defensive Scenarios
with tempfile.TemporaryDirectory() as td_neg:
    neg_ws = Path(td_neg)
    bin_neg = neg_ws / "win_b64" / "code" / "bin"
    dico_neg = neg_ws / "win_b64" / "code" / "dictionary"
    bin_neg.mkdir(parents=True)
    dico_neg.mkdir(parents=True)
    dll_neg = bin_neg / "AcceptanceMod.dll"
    dll_neg.write_bytes(make_test_pe_image())
    dico_neg_file = dico_neg / "AcceptanceFw.dico"
    dico_neg_file.write_text("CAAMmrMeasureSet CATI3DGeoVisu libAcceptanceMod\n", encoding="latin-1")

    # Scenario A: Runner fails with non-zero exit code
    def mock_failing_runner(macro_path: str, workspace_path: str, timeout: int):
        return {
            "status": "failed",
            "message": "Macro execution failed (exit 1)",
        }

    with patch("verify_om_activation.identify_target_cnext", return_value=("PASS", 1111, {"method": "mock_tree"})):
        with patch("verify_om_activation.verify_module_loaded", return_value=("PASS", {"matched_path": str(dll_neg), "exact_matched_path": str(dll_neg), "exact_match_pass": True})):
            res_fail = driver.execute_live_activation(
                workspace_path=str(neg_ws),
                runner_fn=mock_failing_runner,
            )
    ck("Negative Scenario A: Failing macro run fails overall status", res_fail["overall_status"] == "FAIL")
    ck("Negative Scenario A: QueryInterface remains UNKNOWN without authentic QI probe (no false FAIL)",
       res_fail["phase_d_evidence"]["L4"]["status"] == "UNKNOWN")

    # Scenario B: Target DLL loaded from wrong stray path (L3 stray violation)
    stray_path = str(Path(tempfile.gettempdir()) / "StrayPath" / "AcceptanceMod.dll")
    def mock_stray_runner(macro_path: str, workspace_path: str, timeout: int):
        return {
            "status": "success",
        }

    with patch("verify_om_activation.identify_target_cnext", return_value=("PASS", 2222, {"method": "mock_tree"})):
        with patch("verify_om_activation.verify_module_loaded", return_value=("FAIL", {"stray_mismatch_path": stray_path, "exact_match_pass": False, "reason": "stray_dll_loaded_from_wrong_path"})):
            res_stray = driver.execute_live_activation(
                workspace_path=str(neg_ws),
                runner_fn=mock_stray_runner,
            )
    ck("Negative Scenario B: Stray path violation results in L3 FAIL", res_stray["phase_d_evidence"]["L3"]["status"] == "FAIL")
    ck("Negative Scenario B: Overall status is FAIL on L3 violation", res_stray["overall_status"] == "FAIL")

    # Scenario C: Runner throws unexpected exception (safe exception handling)
    def mock_exploding_runner(macro_path: str, workspace_path: str, timeout: int):
        raise RuntimeError("Simulated process explosion")

    res_crash = driver.execute_live_activation(
        workspace_path=str(neg_ws),
        runner_fn=mock_exploding_runner,
    )
    ck("Negative Scenario C: Exception safely handled in macro_execution",
       res_crash["phase_c_macro_execution"]["status"] == "error")
    ck("Negative Scenario C: Overall status fails gracefully", res_crash["overall_status"] == "FAIL")
    ck("Negative Scenario C: Environment variables cleaned up after crash",
       "CADE_PROBE_FILE" not in os.environ and "CADE_PROBE_NONCE" not in os.environ)

print("\n" + "=" * 70)
print(f"  Result: {passed}/{total} tests passed ({'ALL PASS' if passed == total else 'SOME FAILED'})")
print("=" * 70)

if passed != total:
    sys.exit(1)
