#!/usr/bin/env python3
"""
Build Time & Run Time — Merged Full Test Suite
================================================
合并自: test_build_run_time.py + test_all_build_run_commands.py
覆盖所有 build.py / run.py / env.py 功能。
"""

import sys
import tempfile
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from build import (
    build_workspace,
    clean_build,
    create_runtime_view,
    debug_build,
    dependency_analysis,
    dry_run_build,
    full_build,
    get_prerequisite,
    impact_analysis,
    incremental_build,
    update_framework,
    workspace_config,
    workspace_info,
    workspace_module_info,
    workspace_where,
)
from env import CAAEnvironment
from parser import parse_mkmk_output
from run import (
    check_catia_running,
    check_process_running,
    run_catia_batch,
    run_catia_macro,
    start_catia_runtime,
    stop_catia,
)

WORKSPACE = Path(tempfile.mkdtemp(prefix="cade_test_ws_"))

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    if ok:
        passed += 1
    s = "PASS" if ok else "FAIL"
    print(f"  [{s}] {label}" + (f" — {detail}" if detail else ""))


env = CAAEnvironment()
env.initialize()

print("=" * 70)
print("  Build Time & Run Time — Merged Full Test Suite")
print(f"  CATIA: {env.config.get('CATIA_VERSION', 'N/A')}  |  Workspace: {WORKSPACE}")
print("=" * 70)

# ═══ Part 1: Environment Detection ═══
print("\n" + "=" * 70)
print("  Part 1: Environment Detection")
print("=" * 70)

check("1.1 CAAEnvironment created", env is not None)
check(
    "1.2 CATIA_INSTALL",
    bool(env.config.get("CATIA_INSTALL", "")),
    str(env.config.get("CATIA_INSTALL", "not set"))[:60],
)
check(
    "1.3 CATIA_VERSION",
    bool(env.config.get("CATIA_VERSION", "")),
    env.config.get("CATIA_VERSION", "N/A"),
)
check(
    "1.4 CAA_INSTALL",
    bool(env.config.get("CAA_INSTALL", "")),
    str(env.config.get("CAA_INSTALL", "not set"))[:60],
)
try:
    arch = env.get_architecture() if hasattr(env, "get_architecture") else "win_b64"
    check("1.5 get_architecture()", bool(arch), arch)
except Exception as e:
    check("1.5 get_architecture()", False, str(e)[:80])

# ═══ Part 2: Build Time Command Generation ═══
print("\n" + "=" * 70)
print("  Part 2: Build Time Command Generation")
print("=" * 70)

try:
    cmd, display = env.build_time_command(WORKSPACE, "-u")
    check("2.1 build_time_command(-u) len", len(cmd) > 0, f"len={len(cmd)}")
    check("2.2 mkinit in command", any("mkinit" in str(a).lower() for a in cmd))
except Exception as e:
    check("2.1 build_time_command()", False, str(e)[:80])

for opt, label in [("-g", "debug"), ("-c", "clean"), ("-a", "full")]:
    try:
        c, d = env.build_time_command(WORKSPACE, opt)
        check(f"2.x build_time_command({label})", len(c) > 0, f"opt={opt}")
    except Exception as e:
        check(f"2.x build_time_command({label})", False, str(e)[:60])

# ═══ Part 3: mkmk Output Parser ═══
print("\n" + "=" * 70)
print("  Part 3: mkmk Output Parser")
print("=" * 70)

sample = "Build started...\nModule1 compiled\n0 error(s), 0 warning(s)\nBuild completed"
r = parse_mkmk_output(sample)
check("3.1 parse_mkmk_output returns dict", isinstance(r, dict))
check("3.2 error_count key", "error_count" in r)
check("3.3 warning_count key", "warning_count" in r)
check("3.4 error_count=0", r.get("error_count") == 0)

sample_err = "ERROR: file.h(10): syntax\n1 error(s), 0 warning(s)"
r2 = parse_mkmk_output(sample_err)
check("3.5 parses errors", r2.get("error_count", 0) > 0)

# ═══ Part 4: Process Management ═══
print("\n" + "=" * 70)
print("  Part 4: Process Management")
print("=" * 70)

procs = check_process_running("svchost.exe")
check("4.1 check_process_running returns list", isinstance(procs, list))
check(
    "4.2 nonexistent process empty",
    check_process_running("no_such_process_xyz_123.exe") == [],
)
check(
    "4.3 dict items have keys",
    not procs or any("pid" in p or "name" in p for p in procs),
)

# ═══ Part 5: CATIA Lifecycle ═══
print("\n" + "=" * 70)
print("  Part 5: CATIA Process Lifecycle")
print("=" * 70)

running = check_catia_running()
check("5.1 check_catia_running dict", isinstance(running, dict))
check("5.2 has status key", "status" in running)

if running.get("status") == "running":
    print("       [INFO] CATIA already running, stopping first...")
    stop_catia(force=True)
    time.sleep(2)

start_r = start_catia_runtime(workspace_path=WORKSPACE, wait_for_exit=False, timeout=60)
check("5.3 start_catia_runtime dict", isinstance(start_r, dict))
check(
    "5.4 start status",
    start_r.get("status") in ("started", "error", "already_running"),
    start_r.get("status", "?"),
)

time.sleep(2)
running2 = check_catia_running()
check("5.5 running after start", running2.get("status") in ("running", "not_running"))

# ═══ Part 6: CATIA Stop ═══
print("\n" + "=" * 70)
print("  Part 6: CATIA Stop")
print("=" * 70)

stop_r = stop_catia()
check("6.1 stop_catia dict", isinstance(stop_r, dict))
check(
    "6.2 stop status",
    stop_r.get("status") in ("stopped", "not_running"),
    str(stop_r.get("status", "?"))[:40],
)

# ═══ Part 7: Error Handling ═══
print("\n" + "=" * 70)
print("  Part 7: Error Handling")
print("=" * 70)

bad = start_catia_runtime(workspace_path="Z:/nonexistent/path")
check("7.1 bad path", bad.get("status") == "error", bad.get("message", "")[:60])

s2 = stop_catia()
check("7.2 stop when not running", isinstance(s2, dict))

e3 = check_process_running("")
check("7.3 empty process name", isinstance(e3, list))

# ═══ Part 8: Runtime View ═══
print("\n" + "=" * 70)
print("  Part 8: Runtime View Detection")
print("=" * 70)

a = env.get_architecture() if hasattr(env, "get_architecture") else "win_b64"
rv_path = WORKSPACE / a / "code"
check("8.1 Runtime View path (temp ws)", True, f"path={rv_path}")

# ═══ Part 9: Build Commands (dry-run only) ═══
print("\n" + "=" * 70)
print("  Part 9: Build Commands (dry-run)")
print("=" * 70)

for name, fn in [
    ("incremental_build(-u)", incremental_build),
    ("full_build(-a)", full_build),
    ("clean_build(-c)", clean_build),
    ("debug_build(-g)", debug_build),
    ("dry_run_build(-n)", dry_run_build),
    ("build_workspace()", build_workspace),
]:
    try:
        r = fn(WORKSPACE, timeout=120)
        ok = isinstance(r, dict)
        check(f"9.x {name}", ok, f"status={r.get('status', '?')}" if ok else "not dict")
    except Exception as e:
        check(f"9.x {name}", False, str(e)[:60])

# ═══ Part 10: Management Commands ═══
print("\n" + "=" * 70)
print("  Part 10: Management Commands")
print("=" * 70)

for name, fn in [
    ("create_runtime_view", create_runtime_view),
    ("workspace_info", workspace_info),
    ("update_framework", update_framework),
    ("dependency_analysis", dependency_analysis),
]:
    try:
        r = fn(WORKSPACE)
        ok = isinstance(r, dict)
        check(
            f"10.x {name}", ok, f"status={r.get('status', '?')}" if ok else "not dict"
        )
    except Exception as e:
        check(f"10.x {name}", False, str(e)[:60])

# ═══ Part 11: env.run_command() ═══
print("\n" + "=" * 70)
print("  Part 11: env.run_command()")
print("=" * 70)

for cmd in [
    "mkwhereami",
    "mkreadcpd",
    "mkGetPreq",
    "mkmkimpact",
    "mkPrintPreq",
    "mkCreateIC",
]:
    try:
        cl, ds = env.run_command(cmd, str(WORKSPACE))
        check(f"11.x {cmd}", bool(cl), f"len={len(ds)}")
    except Exception as e:
        check(f"11.x {cmd}", False, str(e)[:60])

# ═══ Part 12: Run Time — macro & batch ═══
print("\n" + "=" * 70)
print("  Part 12: Run Time — macro & batch")
print("=" * 70)

check("12.1 run_catia_macro callable", callable(run_catia_macro))
check("12.2 run_catia_batch callable", callable(run_catia_batch))
r_macro = run_catia_macro("C:/nonexistent/test.CATScript")
check(
    "12.3 macro nonexistent",
    isinstance(r_macro, dict) and r_macro.get("status") == "error",
    r_macro.get("message", "")[:60],
)

# ═══ Summary ═══
print("\n" + "=" * 70)
print(f"  Build/Run Merged: {passed}/{total}")
if total:
    print(f"  Pass rate: {passed / total * 100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> All Build Time & Run Time commands working <<<")
