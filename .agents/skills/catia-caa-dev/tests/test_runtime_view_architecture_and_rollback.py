#!/usr/bin/env python3
"""
Test Runtime View Architecture Steering, Safe Overwrite Rollback & Dict Sync Dedup
==================================================================================
Validates:
1. CAAEnvironment honors MKMK_ARCH override across get_architecture and run_command.
2. create_runtime_view respects architecture parameter and sets MKMK_ARCH for command.
3. create_runtime_view verifies essential runtime view structure (code/ directory).
4. create_runtime_view rolls back backup directory safely on command failure.
5. create_runtime_view rolls back backup directory safely on unhandled exception.
6. sync_runtime_view delegates dictionary copying to _copy_dictionaries_to_runtime without duplication.
"""

import os
import sys
import tempfile
import pathlib
from pathlib import Path
from unittest.mock import patch, MagicMock

TESTS_DIR = pathlib.Path(__file__).parent
SKILL_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from env import CAAEnvironment
from build import (
    create_runtime_view,
    sync_runtime_view,
    _copy_dictionaries_to_runtime,
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
print("  Test: Runtime View Architecture Steering & Overwrite Rollback")
print("=" * 70)

# ── 1. CAAEnvironment MKMK_ARCH Override ───────────────────────────
print("\n[1] CAAEnvironment Architecture Steering via MKMK_ARCH")
caa_env = CAAEnvironment()
old_env = os.environ.get("MKMK_ARCH")
try:
    os.environ["MKMK_ARCH"] = "intel_a"
    ck("1.1 get_architecture honors MKMK_ARCH=intel_a",
       caa_env.get_architecture() == "intel_a")

    with patch.object(caa_env, "_find_vcvars", return_value=Path(tempfile.gettempdir()) / "vcvarsall.bat"):
        with patch.object(caa_env, "resolve_tck_id", return_value=None):
            cmd_list, cmd_str = caa_env.run_command("mkCreateRuntimeView")
            ck("1.2 run_command path contains intel_a",
               "intel_a" in cmd_str)

    os.environ["MKMK_ARCH"] = "win_b64"
    ck("1.3 get_architecture honors MKMK_ARCH=win_b64",
       caa_env.get_architecture() == "win_b64")
finally:
    if old_env is not None:
        os.environ["MKMK_ARCH"] = old_env
    else:
        os.environ.pop("MKMK_ARCH", None)

# ── 2. create_runtime_view Architecture Parameter & Command Execution ──
print("\n[2] create_runtime_view Architecture Parameter")
with tempfile.TemporaryDirectory() as td:
    ws = Path(td)
    captured_arch = []

    def mock_exec_build_cmd(cmd_name, workspace_path):
        captured_arch.append(os.environ.get("MKMK_ARCH"))
        # Simulate mkCreateRuntimeView creating the directory
        arch = os.environ.get("MKMK_ARCH") or "win_b64"
        rt = workspace_path / arch
        (rt / "code" / "bin").mkdir(parents=True, exist_ok=True)
        return {"status": "success", "returncode": 0}

    with patch("build._exec_build_cmd", side_effect=mock_exec_build_cmd):
        res = create_runtime_view(ws, overwrite=False, architecture="intel_a")
        ck("2.1 create_runtime_view sets MKMK_ARCH during command execution",
           len(captured_arch) == 1 and captured_arch[0] == "intel_a")
        ck("2.2 create_runtime_view creates target runtime view at intel_a",
           res.get("runtime") == "intel_a" and (ws / "intel_a").is_dir())
        ck("2.3 MKMK_ARCH cleaned up after execution",
           "MKMK_ARCH" not in os.environ)

# ── 3. Overwrite Safety & Automatic Rollback on Incomplete Structure ─
print("\n[3] Overwrite Safety & Rollback on Incomplete Structure")
with tempfile.TemporaryDirectory() as td:
    ws = Path(td)
    rt = ws / "win_b64"
    code_dir = rt / "code" / "bin"
    code_dir.mkdir(parents=True)
    canary = code_dir / "canary.txt"
    canary.write_text("ORIGINAL_RUNTIME_VIEW", encoding="utf-8")

    def mock_failed_creation(cmd_name, workspace_path):
        # mkCreateRuntimeView failed and left an incomplete directory (no code/ directory)
        rt = workspace_path / "win_b64"
        rt.mkdir(parents=True, exist_ok=True)
        return {"status": "failed", "returncode": 1, "message": "Simulated toolchain error"}

    with patch("build._exec_build_cmd", side_effect=mock_failed_creation):
        res_fail = create_runtime_view(ws, overwrite=True)
        ck("3.1 Incomplete/failed creation reports failed status",
           res_fail.get("status") == "failed")
        ck("3.2 Previous runtime view rolled back successfully",
           canary.is_file() and canary.read_text(encoding="utf-8") == "ORIGINAL_RUNTIME_VIEW")

# ── 4. Overwrite Safety & Automatic Rollback on Unhandled Exception ──
print("\n[4] Overwrite Safety & Rollback on Unhandled Exception")
with tempfile.TemporaryDirectory() as td:
    ws = Path(td)
    rt = ws / "win_b64"
    code_dir = rt / "code" / "bin"
    code_dir.mkdir(parents=True)
    canary = code_dir / "canary_ex.txt"
    canary.write_text("SAVED_CANARY", encoding="utf-8")

    def mock_exploding_creation(cmd_name, workspace_path):
        raise OSError("Simulated disk I/O error during toolchain execution")

    with patch("build._exec_build_cmd", side_effect=mock_exploding_creation):
        res_ex = create_runtime_view(ws, overwrite=True)
        ck("4.1 Unhandled exception reports error status",
           res_ex.get("status") == "error")
        ck("4.2 Previous runtime view rolled back after exception",
           canary.is_file() and canary.read_text(encoding="utf-8") == "SAVED_CANARY")

    # 4.3 Explicit reporting when rollback restoration itself fails (no silent swallowing)
    orig_rename = Path.rename
    rename_calls = []
    def mock_conditional_rename(self, target, *args, **kwargs):
        rename_calls.append((self, target))
        if len(rename_calls) == 1:
            return orig_rename(self, target, *args, **kwargs)
        raise OSError("Simulated permission denied on backup rename")

    with patch("build._exec_build_cmd", side_effect=mock_exploding_creation):
        with patch.object(Path, "rename", side_effect=mock_conditional_rename, autospec=True):
            res_rb_fail = create_runtime_view(ws, overwrite=True)
            ck("4.3 Rollback failure explicitly reported in result",
               res_rb_fail.get("rollback_failed") is True)
            ck("4.4 Rollback error details preserved in result",
               "Simulated permission denied" in str(res_rb_fail.get("rollback_error", "")))

# ── 5. Dictionary Copy Dedup & sync_runtime_view Delegation ──────────
print("\n[5] Dictionary Copy Dedup & sync_runtime_view Delegation")
with tempfile.TemporaryDirectory() as td:
    ws = Path(td)
    fw = ws / "TestFw.edu"
    dico_src = fw / "CNext" / "code" / "dictionary"
    dico_src.mkdir(parents=True)
    dico_file = dico_src / "TestFw.dico"
    dico_file.write_text("Component Interface libTest\n", encoding="latin-1")

    # Call _copy_dictionaries_to_runtime directly
    copied = _copy_dictionaries_to_runtime(ws, arch="win_b64")
    ck("5.1 _copy_dictionaries_to_runtime returns list of copied files",
       "dictionary/TestFw.dico" in copied)
    ck("5.2 Destination dictionary file created",
       (ws / "win_b64" / "code" / "dictionary" / "TestFw.dico").is_file())

    # Verify sync_runtime_view delegates to it
    res_sync = sync_runtime_view(ws, arch="win_b64")
    ck("5.3 sync_runtime_view includes copied dictionaries",
       "dictionary/TestFw.dico" in res_sync["synced"])

print("\n" + "=" * 70)
print(f"  Result: {passed}/{total} tests passed ({'ALL PASS' if passed == total else 'SOME FAILED'})")
print("=" * 70)

sys.exit(0 if passed == total else 1)
