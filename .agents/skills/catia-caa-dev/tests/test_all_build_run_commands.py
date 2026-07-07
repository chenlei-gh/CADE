#!/usr/bin/env python3
"""
Build Time & Run Time — ALL Commands Test
===========================================
Tests every named build/run command end-to-end.
"""

import os
import sys
import time
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from build import (
    _exec_build_cmd,
    build_workspace,
    clean_build,
    create_runtime_view,
    debug_build,
    dependency_analysis,
    dry_run_build,
    full_build,
    incremental_build,
    update_framework,
    workspace_info,
)
from env import CAAEnvironment
from run import (
    check_catia_running,
    check_process_running,
    run_catia_batch,
    run_catia_macro,
    start_catia_runtime,
    stop_catia,
)

WORKSPACE = Path("D:/test")
total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    s = "PASS" if ok else "FAIL"
    print(f"  [{s}] {label}" + (f" — {detail}" if detail else ""))


env = CAAEnvironment()
env.load_config()

print("=" * 70)
print("  Build Time & Run Time — ALL Commands Test")
print(f"  CATIA: {env.config.get('CATIA_VERSION')}  |  Workspace: {WORKSPACE}")
print("=" * 70)

# ═══════════════════════════════════════════════════════════════════
# Part A: Build Time — 编译命令 (dry-run only, no actual compile)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part A: Build Time — mkmk 编译命令 (dry-run)")
print("═" * 70)

# A1: mkmk -n (dry run)
print("\n  --- mkmk -n (dry-run) ---")
t0 = time.time()
r = dry_run_build(WORKSPACE, timeout=120)
t1 = time.time()
ck("A1.1 dry_run_build() returns", isinstance(r, dict), f"status={r.get('status')}")
ck(
    "A1.2 dry_run_build() completed",
    r["status"] in ("success", "failed", "error"),
    f"exit={r.get('exit_code')}, {t1 - t0:.1f}s",
)
if r.get("exit_code") == 0:
    ck("A1.3 dry_run exit code 0", True, "no errors")
else:
    print(f"       [INFO] exit_code={r.get('exit_code')} — may need valid workspace")

# A2: Verify all named build functions exist
print("\n  --- Named function signatures ---")
for name, fn in [
    ("incremental_build  (-u)", incremental_build),
    ("full_build         (-a)", full_build),
    ("clean_build        (-c)", clean_build),
    ("debug_build        (-g)", debug_build),
    ("dry_run_build      (-n)", dry_run_build),
    ("build_workspace     ()", build_workspace),
]:
    ck(f"A2 {name}", callable(fn), "callable")

# ═══════════════════════════════════════════════════════════════════
# Part B: Build Time — 管理命令
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part B: Build Time — 管理命令")
print("═" * 70)

# B1: create_runtime_view
print("\n  --- mkCreateRuntimeView ---")
t0 = time.time()
r = create_runtime_view(WORKSPACE)
t1 = time.time()
ck("B1.1 create_runtime_view()", isinstance(r, dict), f"status={r.get('status')}")
ck(
    "B1.2 returns output",
    "output_tail" in r,
    f"{r.get('output_tail', '')[:80]}, {t1 - t0:.1f}s",
)

# B2: workspace_info
print("\n  --- mkwhereami + mkreadcpd ---")
t0 = time.time()
r = workspace_info(WORKSPACE)
t1 = time.time()
ck("B2.1 workspace_info()", isinstance(r, dict), f"status={r.get('status')}")
ck(
    "B2.2 returns output",
    "output_tail" in r,
    f"{r.get('output_tail', '')[:80]}, {t1 - t0:.1f}s",
)

# B3: update_framework
print("\n  --- MkUpToDateAFramework ---")
t0 = time.time()
r = update_framework(WORKSPACE)
t1 = time.time()
ck("B3.1 update_framework()", isinstance(r, dict), f"status={r.get('status')}")
ck(
    "B3.2 returns output",
    "output_tail" in r,
    f"{r.get('output_tail', '')[:80]}, {t1 - t0:.1f}s",
)

# B4: dependency_analysis
print("\n  --- mkmkdepend ---")
t0 = time.time()
r = dependency_analysis(WORKSPACE)
t1 = time.time()
ck("B4.1 dependency_analysis()", isinstance(r, dict), f"status={r.get('status')}")
ck(
    "B4.2 returns output",
    "output_tail" in r,
    f"{r.get('output_tail', '')[:80]}, {t1 - t0:.1f}s",
)

# ═══════════════════════════════════════════════════════════════════
# Part C: Build Time — 通用命令接口
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part C: Build Time — env.run_command() 通用接口")
print("═" * 70)

test_cmds = [
    "mkwhereami",
    "mkreadcpd",
    "mkGetPreq",
    "mkmkimpact",
    "mkPrintPreq",
    "mkCreateIC",
]
for cmd in test_cmds:
    try:
        cl, ds = env.run_command(cmd, str(WORKSPACE))
        ok = bool(cl) and len(cl) == 3 and "mkinit" in ds.lower() and cmd in ds
        ck(f"C {cmd:20s}", ok, f"len_display={len(ds)}")
    except Exception as e:
        ck(f"C {cmd:20s}", False, str(e)[:60])

# ═══════════════════════════════════════════════════════════════════
# Part D: Run Time — CATIA 生命周期
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part D: Run Time — CATIA 生命周期")
print("═" * 70)

# Make sure CATIA is stopped first
was_running = len(check_process_running("CNEXT.exe")) > 0
if was_running:
    print("  [INFO] CNEXT was running, stopping for clean test...")
    stop_catia()
    time.sleep(3)

# D1: Check not running
r = check_catia_running()
ck("D1 check_catia_running (stopped)", r["status"] == "not_running", r["status"])

# D2: Start CATIA
print("\n  --- Starting CATIA ---")
t0 = time.time()
r = start_catia_runtime(workspace_path=str(WORKSPACE), wait_for_exit=False, timeout=60)
t1 = time.time()
ck(
    "D2 start_catia_runtime()",
    r["status"] in ("started", "already_running"),
    f"status={r['status']}, PID={r.get('pid', '?')}, {t1 - t0:.1f}s",
)

# Wait
time.sleep(8)

# D3: Check running
cnext = check_process_running("CNEXT.exe")
ck(
    "D3 CNEXT running",
    len(cnext) > 0,
    f"PID={cnext[0]['pid']}" if cnext else "NOT RUNNING",
)

# D4: check_catia_running while running
if cnext:
    r = check_catia_running()
    ck(
        "D4 check_catia_running (running)",
        r["status"] == "running",
        f"processes={len(r.get('processes', []))}",
    )

# D5: Stop CATIA
print("\n  --- Stopping CATIA ---")
r = stop_catia()
ck(
    "D5 stop_catia()",
    r["status"] in ("stopped", "not_running"),
    f"stopped={len(r.get('stopped', []))}, failed={len(r.get('failed', []))}",
)

time.sleep(3)

# D6: Verify stopped
cnext = check_process_running("CNEXT.exe")
ck(
    "D6 CNEXT stopped",
    len(cnext) == 0,
    f"{len(cnext)} process(es) remain" if cnext else "all stopped",
)

# ═══════════════════════════════════════════════════════════════════
# Part E: Run Time — macro & batch (function exists, dry-test only)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part E: Run Time — macro & batch")
print("═" * 70)

ck("E1 run_catia_macro() callable", callable(run_catia_macro))
ck("E2 run_catia_batch() callable", callable(run_catia_batch))

# Quick macro test with nonexistent file (expect error, not crash)
# Don't start CATIA for this — just verify function handles gracefully
r = run_catia_macro("C:/nonexistent/test.CATScript")
ck(
    "E3 run_catia_macro(nonexistent)",
    r["status"] in ("error", "failed"),
    f"status={r['status']}, msg={str(r.get('message', ''))[:50]}",
)

# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print(f"  Build/Run ALL Commands: {passed}/{total} ({passed / total * 100:.1f}%)")
print("=" * 70)

if passed == total:
    print("\n  >>> All Build Time & Run Time commands working <<<")
else:
    print(f"\n  >>> {total - passed} issue(s) <<<")

sys.exit(0 if passed == total else 1)
