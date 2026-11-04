#!/usr/bin/env python3
"""
Test P0-2: Layered Evidence Verification for CATIA Runtime
===========================================================
Verify that:
1. L0 verifies physical directory presence (PASS/FAIL).
2. L1 verifies asset integrity (DLLs, DICOs, non-zero sizes).
3. L2 identifies target CNEXT PID without naive launcher PID assumption.
4. L3 verifies target module loaded with exact physical absolute path match.
5. L4 honestly reports UNKNOWN (never fake PASS with offline DICO checks).
6. L5 reports NOT_RUN unless end-to-end invocation occurs.
7. Highest verified level is derived strictly without level-skipping.
"""

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from runtime_view import (
    check_runtime_view_l0,
    check_runtime_view_l1,
    check_runtime_view,
)
from run import (
    identify_target_cnext,
    verify_module_loaded,
    start_catia_runtime,
)

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
print("  Test P0-2: Runtime Layered Evidence Verification")
print("=" * 70)

# ── 1. L0 Directory Verification ───────────────────────────────
print("\n[1] L0: Directory Presence")

with tempfile.TemporaryDirectory(prefix="cade_l0_") as tmp_dir:
    ws = Path(tmp_dir)

    # Empty ws -> FAIL
    res_fail = check_runtime_view_l0(ws, architecture="win_b64")
    ck("L0 FAIL on non-existent directory", res_fail["status"] == "FAIL", f"got {res_fail['status']}")

    # Create win_b64 -> PASS
    rt_dir = ws / "win_b64"
    rt_dir.mkdir()
    res_pass = check_runtime_view_l0(ws, architecture="win_b64")
    ck("L0 PASS on existing directory", res_pass["status"] == "PASS", f"got {res_pass['status']}")


# ── 2. L1 Asset Integrity Verification ─────────────────────────
print("\n[2] L1: Asset Integrity")

with tempfile.TemporaryDirectory(prefix="cade_l1_") as tmp_dir:
    ws = Path(tmp_dir)
    rt_dir = ws / "win_b64"

    # L0 not ready -> L1 NOT_RUN
    res_not_run = check_runtime_view_l1(ws, architecture="win_b64")
    ck("L1 NOT_RUN when L0 is absent", res_not_run["status"] == "NOT_RUN", f"got {res_not_run['status']}")

    # Create structure but with empty / zero-byte files -> FAIL
    rt_dir.mkdir()
    bin_dir = rt_dir / "code" / "bin"
    dico_dir = rt_dir / "code" / "dictionary"
    bin_dir.mkdir(parents=True)
    dico_dir.mkdir(parents=True)

    zero_dll = bin_dir / "EmptyMod.dll"
    zero_dll.write_bytes(b"")  # 0 bytes
    zero_dico = dico_dir / "EmptyMod.dico"
    zero_dico.write_bytes(b"")  # 0 bytes

    res_zero = check_runtime_view_l1(ws, architecture="win_b64")
    ck("L1 FAIL on 0-byte assets", res_zero["status"] == "FAIL", f"got {res_zero['status']}")

    # Populate valid assets -> PASS
    # Minimal valid 64-bit Windows PE (AMD64 + PE32+) for win_b64
    import struct
    def make_valid_pe(machine=0x8664, opt_magic=0x020B, num_sections=1, characteristics=0x2002, file_alignment=512):
        dos_hdr = b"MZ" + b"\x00" * 0x3A + struct.pack("<I", 0x40)
        pe_sig = b"PE\x00\x00"
        coff_hdr = struct.pack("<HHIIIHH", machine, num_sections, 0, 0, 0, 240, characteristics)
        opt = bytearray(240)
        struct.pack_into("<H", opt, 0, opt_magic)
        struct.pack_into("<I", opt, 36, file_alignment)
        opt_hdr = bytes(opt)
        sec_hdr = b""
        if num_sections > 0:
            # 40 bytes section header. Raw size/pointer 0 are multiples of FileAlignment.
            sec_hdr = b".text\x00\x00\x00" + struct.pack("<IIII", 0x1000, 0x1000, 0, 0) + b"\x00" * 16
        return dos_hdr + pe_sig + coff_hdr + opt_hdr + sec_hdr

    pe_header = make_valid_pe(machine=0x8664, opt_magic=0x020B)
    valid_dll = bin_dir / "MyModule.dll"
    valid_dll.write_bytes(pe_header)
    valid_dico = dico_dir / "MyModule.dico"
    valid_dico.write_bytes(b"MyClass CATIInterface libMyModule\n")

    res_valid = check_runtime_view_l1(ws, architecture="win_b64", target_module="MyModule.m")
    ck("L1 PASS on valid target module assets", res_valid["status"] == "PASS", f"got {res_valid['status']}")
    ck("L1 reports valid PE count in assets", res_valid["evidence"]["assets"]["dll"]["valid_pe_count"] == 1)
    ck("L1 reports valid DICO syntax in assets", res_valid["evidence"]["assets"]["dico"]["valid_syntax"] is True)

    # R-03: Arch mismatch (32-bit PE in win_b64) -> FAIL
    pe_32bit = make_valid_pe(machine=0x014C, opt_magic=0x010B)
    valid_dll.write_bytes(pe_32bit)
    res_arch_mismatch = check_runtime_view_l1(ws, architecture="win_b64", target_module="MyModule.m")
    ck("R-03: L1 FAIL on PE architecture mismatch (32-bit in win_b64)", res_arch_mismatch["status"] == "FAIL", f"got {res_arch_mismatch['status']}")
    valid_dll.write_bytes(pe_header)

    # R-03: DICO syntax valid but does NOT mention target module -> FAIL
    valid_dico.write_bytes(b"OtherClass CATIInterface libOtherModule\n")
    res_dico_unbound = check_runtime_view_l1(ws, architecture="win_b64", target_module="MyModule.m")
    ck("R-03: L1 FAIL when DICO does not mention target module", res_dico_unbound["status"] == "FAIL", f"got {res_dico_unbound['status']}")

    # R-03: DICO substring match rejected (e.g. libMyModuleExtra must NOT match MyModule)
    valid_dico.write_bytes(b"MyClass CATIInterface libMyModuleExtra\n")
    res_dico_substr = check_runtime_view_l1(ws, architecture="win_b64", target_module="MyModule.m")
    ck("R-03: L1 FAIL when DICO only has substring match (libMyModuleExtra vs MyModule)", res_dico_substr["status"] == "FAIL", f"got {res_dico_substr['status']}")

    # R-03: PE Section boundary out of bounds -> FAIL
    sec_oob = b".text\x00\x00\x00" + struct.pack("<IIII", 0x1000, 0x1000, 0x2000, 0x2000) + b"\x00" * 16
    pe_oob = b"MZ" + b"\x00" * 0x3A + struct.pack("<I", 0x40) + b"PE\x00\x00" + struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, 240, 0x0002) + struct.pack("<H", 0x020B) + b"\x00" * 238 + sec_oob
    valid_dll.write_bytes(pe_oob)
    res_sec_oob = check_runtime_view_l1(ws, architecture="win_b64", target_module="MyModule.m")
    ck("R-03: L1 FAIL when PE section raw_ptr + raw_size exceeds file boundary", res_sec_oob["status"] == "FAIL", f"got {res_sec_oob['status']}")

    # R-03: missing IMAGE_FILE_DLL, zero FileAlignment, and a bad DICO line are FAIL
    valid_dll.write_bytes(make_valid_pe(characteristics=0x0002))
    valid_dico.write_bytes(b"MyClass CATIInterface libMyModule\n")
    res_not_dll = check_runtime_view_l1(ws, architecture="win_b64", target_module="MyModule.m")
    ck("R-03: L1 FAIL when PE lacks IMAGE_FILE_DLL", res_not_dll["status"] == "FAIL", f"got {res_not_dll['status']}")

    valid_dll.write_bytes(make_valid_pe(file_alignment=0))
    res_align = check_runtime_view_l1(ws, architecture="win_b64", target_module="MyModule.m")
    ck("R-03: L1 FAIL when FileAlignment is not a power of two in 512..65536", res_align["status"] == "FAIL", f"got {res_align['status']}")

    valid_dll.write_bytes(pe_header)
    valid_dico.write_bytes(b"MyClass CATIInterface libMyModule\nthis is not a dico entry\n")
    res_bad_line = check_runtime_view_l1(ws, architecture="win_b64", target_module="MyModule.m")
    ck("R-03: L1 FAIL when one DICO line is illegal", res_bad_line["status"] == "FAIL", f"got {res_bad_line['status']}")

    # Restore valid assets
    valid_dll.write_bytes(pe_header)
    valid_dico.write_bytes(b"MyClass CATIInterface libMyModule\n")

    # Invalidate PE header (non-PE DLL) -> FAIL
    valid_dll.write_bytes(b"NON_PE_CORRUPT_BYTES_DATA")
    res_corrupt_pe = check_runtime_view_l1(ws, architecture="win_b64", target_module="MyModule.m")
    ck("L1 FAIL when DLL fails PE format validation", res_corrupt_pe["status"] == "FAIL", f"got {res_corrupt_pe['status']}")
    # Restore valid PE
    valid_dll.write_bytes(pe_header)

    res_mismatch = check_runtime_view_l1(ws, architecture="win_b64", target_module="NonExistentModule.m")
    ck("L1 FAIL when target module DLL missing", res_mismatch["status"] == "FAIL", f"got {res_mismatch['status']}")


# ── 3. L2 Target Process Identity Verification ─────────────────
print("\n[3] L2: Target Process Identity")

# Case A: Parent process tree ancestor match
fake_snapshot_tree = [
    {"pid": 1000, "parent_pid": 100, "name": "cmd.exe"},         # launcher
    {"pid": 1001, "parent_pid": 1000, "name": "cmd.exe"},        # child cmd
    {"pid": 2000, "parent_pid": 1001, "name": "CNEXT.exe"},      # target CNEXT
    {"pid": 3000, "parent_pid": 50, "name": "CNEXT.exe"},        # unrelated CNEXT
]

with patch("run.get_processes_snapshot_win32", return_value=fake_snapshot_tree):
    st, pid, ev = identify_target_cnext(launcher_pid=1000, t_start=None)
    ck("L2 process tree match identifies correct PID", st == "PASS" and pid == 2000,
       f"status={st}, pid={pid}")
    ck("L2 identification method recorded", ev.get("identification_method") == "process_tree_ancestor_match")

# Case B: Creation time window match
t_now = time.time()
fake_snapshot_time = [
    {"pid": 4001, "parent_pid": 99, "name": "CNEXT.exe"},
    {"pid": 4002, "parent_pid": 98, "name": "CNEXT.exe"},
]

def mock_creation_time(pid):
    if pid == 4001:
        return t_now - 1000.0  # old process
    if pid == 4002:
        return t_now + 0.5     # newly launched process
    return None

with patch("run.get_processes_snapshot_win32", return_value=fake_snapshot_time), \
     patch("run.get_process_creation_time_win32", side_effect=mock_creation_time):
    st, pid, ev = identify_target_cnext(launcher_pid=9999, t_start=t_now)
    ck("L2 creation window identifies fresh CNEXT", st == "PASS" and pid == 4002,
       f"status={st}, pid={pid}")

# Case B2: R-02 Fix — Creation time exceeding upper window bound must be rejected
def mock_creation_time_late(pid):
    if pid == 4002:
        return t_now + 35.0  # beyond 30.0s upper bound
    return t_now - 1000.0

with patch("run.get_processes_snapshot_win32", return_value=fake_snapshot_time), \
     patch("run.get_process_creation_time_win32", side_effect=mock_creation_time_late):
    st_late, pid_late, ev_late = identify_target_cnext(launcher_pid=9999, t_start=t_now, max_window_seconds=30.0)
    ck("R-02: Creation time beyond upper bound rejected from candidate window", st_late != "PASS", f"status={st_late}")

# Case B3: R-02 Fix — Baseline PIDs filtered out
with patch("run.get_processes_snapshot_win32", return_value=fake_snapshot_time), \
     patch("run.get_process_creation_time_win32", side_effect=mock_creation_time):
    st_base, pid_base, ev_base = identify_target_cnext(launcher_pid=9999, t_start=t_now, baseline_pids={4002})
    ck("R-02: Baseline pre-existing PID filtered from fresh candidates", pid_base != 4002, f"pid={pid_base}")

# Case C: Ambiguous multiple instances
with patch("run.get_processes_snapshot_win32", return_value=fake_snapshot_time), \
     patch("run.get_process_creation_time_win32", return_value=t_now + 0.1):
    st, pid, ev = identify_target_cnext(launcher_pid=9999, t_start=t_now)
    ck("L2 marks AMBIGUOUS when multiple instances cannot disambiguate", st == "AMBIGUOUS", f"status={st}")

# Case D: R-02 Fix — Single global instance WITHOUT tree or time correlation must be UNKNOWN, NEVER PASS
fake_single_unverified = [
    {"pid": 7001, "parent_pid": 1, "name": "CNEXT.exe"},
]
with patch("run.get_processes_snapshot_win32", return_value=fake_single_unverified), \
     patch("run.get_process_creation_time_win32", return_value=None):
    st_single, pid_single, ev_single = identify_target_cnext(launcher_pid=9999, t_start=None)
    ck("R-02: Single global instance without correlation returns UNKNOWN, never PASS",
       st_single == "UNKNOWN" and pid_single == 7001,
       f"status={st_single}, pid={pid_single}")
    ck("R-02: Method recorded as single_global_instance_unverified",
       ev_single.get("identification_method") == "single_global_instance_unverified")


# ── 4. L3 Module Loaded Verification ───────────────────────────
print("\n[4] L3: Target Module Loaded Exact Path")

fake_loaded = [
    r"C:\Windows\System32\kernel32.dll",
    r"C:\Program Files\Dassault Systemes\B28\win_b64\code\bin\CATSysMain.dll",
    r"D:\Vault\DevTools\CADE\win_b64\code\bin\MyCustomModule.dll",
]

with patch("run.get_process_loaded_modules", return_value=fake_loaded):
    # Match exact path
    target_match = Path(r"D:\Vault\DevTools\CADE\win_b64\code\bin\MyCustomModule.dll")
    st_match, ev_match = verify_module_loaded(pid=2000, expected_dll_path=target_match)
    ck("L3 PASS on exact physical path match", st_match == "PASS", f"status={st_match}")
    ck("L3 match_scope is exact_absolute_physical_path",
       ev_match.get("match_scope") == "exact_absolute_physical_path")

    # Case E: R-08 Fix — Truncated module enumeration returns UNKNOWN, not fake FAIL
    with patch("run.get_process_loaded_modules", return_value=(fake_loaded, False)):
        st_trunc, ev_trunc = verify_module_loaded(pid=2000, expected_dll_path=Path(r"D:\Vault\Unlisted.dll"))
        ck("R-08: L3 UNKNOWN on incomplete PSAPI buffer truncation", st_trunc == "UNKNOWN", f"status={st_trunc}")
        ck("R-08: Reason indicates buffer capacity exceeded", ev_trunc.get("reason") == "module_enumeration_incomplete_capacity_exceeded")

    # No PID available
    st_nopid, _ = verify_module_loaded(pid=None, expected_dll_path=target_match)
    ck("L3 NOT_RUN when PID is None", st_nopid == "NOT_RUN", f"status={st_nopid}")


# ── 5. Full Start Runtime Layered Evidence & Honest Boundaries ──
print("\n[5] Full start_catia_runtime Layered Structure & Honest Boundaries")

with tempfile.TemporaryDirectory(prefix="cade_full_rt_") as tmp_dir:
    ws = Path(tmp_dir)
    # Prepare minimal workspace assets
    rt_win = ws / "win_b64"
    bin_p = rt_win / "code" / "bin"
    dic_p = rt_win / "code" / "dictionary"
    bin_p.mkdir(parents=True)
    dic_p.mkdir(parents=True)
    import struct
    pe_bytes = make_valid_pe(machine=0x8664, opt_magic=0x020B)
    (bin_p / "TestModule.dll").write_bytes(pe_bytes)
    (dic_p / "TestModule.dico").write_bytes(b"TestClass CATIInterface libTestModule\n")

    mock_loaded = [str(bin_p / "TestModule.dll")]

    with patch("subprocess.Popen") as mock_popen, \
         patch("run.identify_target_cnext", return_value=("PASS", 8888, {"identification_method": "mock_test"})), \
         patch("run.get_process_loaded_modules", return_value=mock_loaded), \
         patch("run.stop_catia"), \
         patch("run.check_process_running", return_value=[]):

        mock_proc = mock_popen.return_value
        mock_proc.pid = 7777

        result = start_catia_runtime(
            workspace_path=str(ws),
            target_module="TestModule",
            wait_for_exit=False,
        )

        ck("Runtime status is started", result["status"] == "started", f"status={result['status']}")
        ck("Runtime view present is True", result["runtime_view_present"] is True)
        ck("PID is target CNEXT PID (8888), not launcher PID (7777)", result["pid"] == 8888, f"got {result['pid']}")

        verif = result.get("runtime_verification", {})
        levels = verif.get("levels", {})

        ck("L0 is PASS", levels.get("L0", {}).get("status") == "PASS")
        ck("L1 is PASS", levels.get("L1", {}).get("status") == "PASS")
        ck("L2 is PASS", levels.get("L2", {}).get("status") == "PASS")
        ck("L3 is PASS", levels.get("L3", {}).get("status") == "PASS")

        # P5.3 Envelope dynamic instance_scope check
        env_scope = result.get("verification", {}).get("evidence", {}).get("instance_scope")
        ck("P5.3 Envelope instance_scope is target_instance_verified on L2 PASS",
           env_scope == "target_instance_verified", f"scope={env_scope}")

        # Crucial honest boundary check:
        l4_status = levels.get("L4", {}).get("status")
        ck("L4 is honestly UNKNOWN (no fake PASS)", l4_status == "UNKNOWN", f"got {l4_status}")
        ck("L4 evidence explains lack of B28 probe",
           "no_runtime_hook_in_b28" in levels.get("L4", {}).get("evidence", {}).get("reason", ""))

        l5_status = levels.get("L5", {}).get("status")
        ck("L5 is NOT_RUN (no unverified functional claim)", l5_status == "NOT_RUN", f"got {l5_status}")

        ck("Highest verified level is L3", verif.get("highest_verified_level") == "L3",
           f"got {verif.get('highest_verified_level')}")
        ck("Deprecated alias notice present", "runtime_view_mounted_deprecated_notice" in result)

    # R-04: Test start_catia_runtime without target_module: L3 MUST be NOT_RUN, never pick arbitrary first DLL
    with patch("subprocess.Popen") as mock_popen, \
         patch("run.identify_target_cnext", return_value=("PASS", 8888, {"identification_method": "mock_test"})), \
         patch("run.get_process_loaded_modules", return_value=mock_loaded), \
         patch("run.stop_catia"), \
         patch("run.check_process_running", return_value=[]):

        mock_proc = mock_popen.return_value
        mock_proc.pid = 7777

        result_no_mod = start_catia_runtime(
            workspace_path=str(ws),
            target_module=None,  # omitted
            wait_for_exit=False,
        )
        l3_no_mod = result_no_mod.get("runtime_verification", {}).get("levels", {}).get("L3", {})
        ck("R-04: L3 is NOT_RUN when target_module is omitted",
           l3_no_mod.get("status") == "NOT_RUN",
           f"status={l3_no_mod.get('status')}")
        ck("R-04: L3 reason explains target_module_not_specified",
           l3_no_mod.get("evidence", {}).get("reason") == "target_module_not_specified")

    # Case F: R-02 Fix — Polling state clearing: UNKNOWN followed by AMBIGUOUS clears unverified PID
    poll_steps = [
        ("UNKNOWN", 5001, {"reason": "sole_cnext"}),
        ("AMBIGUOUS", None, {"reason": "multiple"}),
    ]
    def mock_poll_cnext(**kwargs):
        if poll_steps:
            return poll_steps.pop(0)
        return ("AMBIGUOUS", None, {"reason": "multiple"})

    with patch("subprocess.Popen") as mock_popen, \
         patch("run.identify_target_cnext", side_effect=mock_poll_cnext), \
         patch("run.stop_catia"), \
         patch("run.check_process_running", return_value=[]):
        mock_proc = mock_popen.return_value
        mock_proc.pid = 1111
        res_amb = start_catia_runtime(wait_for_exit=False)
        l2_amb = res_amb.get("runtime_verification", {}).get("levels", {}).get("L2", {})
        ck("R-02: L2 AMBIGUOUS clears previous UNKNOWN PID (does not leak 5001)",
           l2_amb.get("status") == "AMBIGUOUS" and res_amb.get("pid") is None,
           f"l2_status={l2_amb.get('status')}, pid={res_amb.get('pid')}")

    # Case G: later UNKNOWN must not overwrite an earlier AMBIGUOUS
    seq = {"n": 0}

    def mock_poll_sticky(**kwargs):
        seq["n"] += 1
        if seq["n"] == 1:
            return ("UNKNOWN", 5001, {"reason": "sole"})
        if seq["n"] == 2:
            return ("AMBIGUOUS", None, {"reason": "multiple"})
        return ("UNKNOWN", 5001, {"reason": "old_pid_again"})

    with patch("subprocess.Popen") as mock_popen, \
         patch("run.identify_target_cnext", side_effect=mock_poll_sticky), \
         patch("run.stop_catia"), \
         patch("run.time.sleep", return_value=None), \
         patch("run.check_process_running", return_value=[]):
        mock_proc = mock_popen.return_value
        mock_proc.pid = 1111
        res_sticky = start_catia_runtime(wait_for_exit=False)
        l2_sticky = res_sticky.get("runtime_verification", {}).get("levels", {}).get("L2", {})
        ck("R-02: later UNKNOWN does not replace AMBIGUOUS or revive PID 5001",
           l2_sticky.get("status") == "AMBIGUOUS" and res_sticky.get("pid") is None,
           f"l2_status={l2_sticky.get('status')}, pid={res_sticky.get('pid')}")

from run import _psapi_buffer_status
ck("R-08: last short buffer is incomplete, not a grow",
   _psapi_buffer_status(9000, 4096, 3, 4) == "incomplete")
ck("R-08: fitting buffer is complete",
   _psapi_buffer_status(100, 4096, 0, 4) == "complete")


print("\n" + "=" * 70)
print(f"  Result: {passed}/{total} tests passed ({'ALL PASS' if passed == total else 'SOME FAILED'})")
print("=" * 70)

import unittest


class TestRuntimeLayeredVerificationDiscovery(unittest.TestCase):
    """Formal discovery entry. The checks above already ran at import."""

    def test_script_checks_passed(self):
        self.assertEqual(passed, total)


if __name__ == "__main__" and passed != total:
    sys.exit(1)
