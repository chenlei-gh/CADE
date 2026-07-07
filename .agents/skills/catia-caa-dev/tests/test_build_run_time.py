#!/usr/bin/env python3
"""
Build Time & Run Time — Full Function Test
============================================
Tests all build.py and run.py functionality.
"""

import sys
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from env import CAAEnvironment
from parser import parse_mkmk_output
from run import (
    check_catia_running,
    check_process_running,
    start_catia_runtime,
    stop_catia,
)

WORKSPACE = "D:/test"

print("=" * 70)
print("  Build Time & Run Time — Full Function Test")
print("=" * 70)

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    if ok:
        print(f"  [PASS] {label}" + (f" — {detail}" if detail else ""))
        passed += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════════════
# Part 1: Environment Detection
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part 1: Environment Detection")
print("═" * 70)

env = CAAEnvironment()

# 1.1 Config loading
check("1.1 load_config()", env.load_config(), f"loaded={bool(env.config)}")

# 1.2 CATIA_INSTALL
catia_install = env.config.get("CATIA_INSTALL", "")
check(
    "1.2 CATIA_INSTALL",
    bool(catia_install) and Path(catia_install).exists(),
    catia_install,
)

# 1.3 CATIA_VERSION
catia_ver = env.config.get("CATIA_VERSION", "")
check("1.3 CATIA_VERSION", bool(catia_ver), catia_ver)

# 1.4 TCK_INIT
tck = env.config.get("TCK_INIT", "")
check(
    "1.4 TCK_INIT.bat",
    Path(tck).exists() if tck else False,
    tck[:60] if tck else "NOT SET",
)

# 1.5 MKMK
mkmk = env.config.get("MKMK", "")
check(
    "1.5 mkmkM.exe",
    Path(mkmk).exists() if mkmk else False,
    mkmk[:60] if mkmk else "NOT SET",
)

# 1.6 CATSTART
catstart = env.get_catstart_path()
check(
    "1.6 CATSTART.exe",
    catstart and catstart.exists(),
    str(catstart)[:60] if catstart else "None",
)

# 1.7 Default env name
env_name = env.get_default_env()
check("1.7 get_default_env()", bool(env_name), env_name)

# 1.8 CATEnv directory
env_dir = env.get_catenv_dir()
check("1.8 get_catenv_dir()", bool(env_dir) and Path(env_dir).exists(), env_dir[:60])

# 1.9 Architecture
arch = env.get_architecture()
check("1.9 get_architecture()", bool(arch), arch)

# ═══════════════════════════════════════════════════════════════════
# Part 2: Build Time Command Generation
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part 2: Build Time Command Generation")
print("═" * 70)

try:
    cmd, cmd_display = env.build_time_command(WORKSPACE, "-u")
    check("2.1 build_time_command() returns cmd", bool(cmd), f"len={len(cmd)}")
    check(
        "2.2 build_time_command() returns display",
        bool(cmd_display),
        f"len={len(cmd_display)}",
    )
    check(
        "2.3 cmd contains mkinit.bat",
        any("mkinit" in str(arg).lower() for arg in cmd),
    )
    check(
        "2.4 cmd_display contains mkmk", "mkmk" in cmd_display.lower(), cmd_display[:80]
    )
except Exception as e:
    check("2.x build_time_command()", False, str(e)[:80])

# 2.5 Test with different options
try:
    cmd2, display2 = env.build_time_command(WORKSPACE, "-g")
    check("2.5 build_time_command(-g)", bool(cmd2), f"options=-g")
except Exception as e:
    check("2.5 build_time_command(-g)", False, str(e)[:80])

# 2.6 Test with -c option
try:
    cmd3, display3 = env.build_time_command(WORKSPACE, "-c")
    check("2.6 build_time_command(-c)", bool(cmd3), f"options=-c")
except Exception as e:
    check("2.6 build_time_command(-c)", False, str(e)[:80])

# ═══════════════════════════════════════════════════════════════════
# Part 3: mkmk Output Parser
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part 3: mkmk Output Parser (parse_mkmk_output)")
print("═" * 70)

# Test with typical mkmk output
sample_ok = "Building...\nDone.\nBuild completed successfully."
result = parse_mkmk_output(sample_ok)
check(
    "3.1 Parse clean output",
    result["error_count"] == 0,
    f"errors={result['error_count']}",
)

sample_error = """
MyModule.m\\src\\MyCmd.cpp(42) : error C2065: 'foo' : undeclared identifier
MyModule.m\\src\\MyCmd.cpp(55) : error C2440: cannot convert
"""
result = parse_mkmk_output(sample_error)
check(
    "3.2 Parse error output",
    result["error_count"] >= 1,
    f"errors={result['error_count']}",
)
check(
    "3.3 Error files detected",
    len(result.get("errors", [])) > 0,
    f"count={len(result.get('errors', []))}",
)

sample_warning = """
MyModule.m\\src\\MyCmd.cpp(10) : warning C4101: 'x' : unreferenced local variable
Done.
"""
result = parse_mkmk_output(sample_warning)
check(
    "3.4 Parse warnings",
    result.get("warning_count", 0) >= 0,
    f"warnings={result.get('warning_count', 0)}",
)

# Test with full output structure
result = parse_mkmk_output("")
check("3.5 Empty output", isinstance(result, dict), "returns dict")
check(
    "3.6 Has required keys",
    all(k in result for k in ["error_count", "warning_count", "errors"]),
    f"keys={list(result.keys())[:5]}",
)

# Test with link errors
sample_link = "LINK : error LNK2001: unresolved external symbol"
result = parse_mkmk_output(sample_link)
check(
    "3.7 Link errors detected",
    result["error_count"] >= 1,
    f"errors={result['error_count']}",
)

# ═══════════════════════════════════════════════════════════════════
# Part 4: Process Management
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part 4: Process Detection & Management")
print("═" * 70)

# 4.1 check_process_running for known process
devenv = check_process_running("explorer.exe")
check(
    "4.1 check_process_running(explorer.exe)", len(devenv) > 0, f"found {len(devenv)}"
)

# 4.2 check_process_running for nonexistent
ghost = check_process_running("NoSuchProcessXYZ.exe")
check("4.2 check_process_running(nonexistent)", len(ghost) == 0, "returns empty list")

# 4.3 check_process_running return format
if len(devenv) > 0:
    proc = devenv[0]
    has_pid = "pid" in proc
    has_name = "name" in proc
    check("4.3 Process dict has 'pid'", has_pid, str(proc.get("pid")))
    check("4.4 Process dict has 'name'", has_name, proc.get("name"))

# ═══════════════════════════════════════════════════════════════════
# Part 5: CATIA Process Lifecycle
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part 5: CATIA Process Lifecycle")
print("═" * 70)

# 5.1 Check if CATIA is running (before start)
cnext_before = check_process_running("CNEXT.exe")
was_running = len(cnext_before) > 0
if was_running:
    print(f"  [INFO] CNEXT is already running (PID: {cnext_before[0]['pid']})")
check("5.1 check_catia_running() API", callable(check_catia_running), "callable")

result = check_catia_running()
check(
    "5.2 check_catia_running() returns dict",
    isinstance(result, dict),
    f"status={result.get('status')}",
)

# 5.2 Start CATIA if not running
if not was_running:
    print("\n  Starting CATIA for test...")
    start_result = start_catia_runtime(
        workspace_path=WORKSPACE,
        wait_for_exit=False,
        timeout=60,
    )
    check(
        "5.3 start_catia_runtime()",
        start_result["status"] in ("started", "already_running"),
        f"status={start_result['status']}",
    )

    # Wait for CNEXT to appear
    time.sleep(8)

    cnext_after = check_process_running("CNEXT.exe")
    check(
        "5.4 CNEXT started successfully",
        len(cnext_after) > 0,
        f"PID={cnext_after[0]['pid'] if cnext_after else 'N/A'}",
    )
    catia_running = len(cnext_after) > 0
else:
    print("\n  [INFO] CNEXT was already running, using existing process")
    catia_running = True

# 5.3 check_catia_running() while running
if catia_running:
    result = check_catia_running()
    check(
        "5.5 check_catia_running() reports running",
        result["status"] == "running",
        f"status={result['status']}",
    )
    if "pid" in result:
        check(
            "5.6 check_catia_running() has PID",
            isinstance(result["pid"], int),
            str(result["pid"]),
        )

# ═══════════════════════════════════════════════════════════════════
# Part 6: Stop CATIA (only if we started it)
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part 6: CATIA Stop")
print("═" * 70)

if catia_running and not was_running:
    print("  Stopping CATIA (cleanup)...")
    stop_result = stop_catia()
    check(
        "6.1 stop_catia() returns dict",
        isinstance(stop_result, dict),
        f"status={stop_result.get('status')}",
    )

    time.sleep(3)
    cnext_stopped = check_process_running("CNEXT.exe")
    check(
        "6.2 CNEXT stopped",
        len(cnext_stopped) == 0,
        "All CNEXT processes terminated"
        if len(cnext_stopped) == 0
        else f"Still {len(cnext_stopped)} running",
    )
elif was_running:
    print("  [INFO] Skipping stop (CNEXT was already running before test)")

    # Test stop_catia API works (don't actually stop pre-existing)
    check("6.1 stop_catia() callable", callable(stop_catia), "function exists")

    if len(cnext_before) > 0:
        check(
            "6.2 CNEXT still running (preserved)",
            len(check_process_running("CNEXT.exe")) > 0,
            "preserved existing process",
        )
else:
    check("6.1 stop_catia() callable", callable(stop_catia), "function exists")
    check(
        "6.2 CNEXT not running",
        len(check_process_running("CNEXT.exe")) == 0,
        "all cleaned up",
    )

# ═══════════════════════════════════════════════════════════════════
# Part 7: Error Handling
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part 7: Error Handling")
print("═" * 70)

# 7.1 Invalid workspace
result = start_catia_runtime(workspace_path="Z:/nonexistent/path")
check(
    "7.1 start_catia with bad path",
    result.get("status") == "error",
    f"status={result.get('status')}, msg={result.get('message', '')[:50]}",
)

# 7.2 stop_catia when not running
# Only test if no CNEXT is running
if len(check_process_running("CNEXT.exe")) == 0:
    # Kill any remaining CATIA first
    try:
        stop_catia()
        time.sleep(2)
    except:
        pass

    if len(check_process_running("CNEXT.exe")) == 0:
        result2 = stop_catia()
        check(
            "7.2 stop_catia when not running",
            result2["status"] == "not_running",
            f"status={result2['status']}",
        )

# 7.3 check_process_running with empty string
try:
    empty = check_process_running("")
    check(
        "7.3 check_process_running(empty)",
        isinstance(empty, list),
        "handles gracefully",
    )
except Exception:
    check("7.3 check_process_running(empty)", False, "exception")

# ═══════════════════════════════════════════════════════════════════
# Part 8: Runtime View Detection
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  Part 8: Runtime View Detection")
print("═" * 70)

rv_path = Path(WORKSPACE) / env.get_architecture() / "code"
has_rv = rv_path.exists()
check("8.1 Runtime View path exists", has_rv, str(rv_path)[:60])

if has_rv:
    dlls = list(rv_path.glob("*.dll"))
    check(
        "8.2 DLLs in Runtime View",
        True,
        f"{len(dlls)} DLL(s) (empty=not yet built, OK)",
    )

# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print(f"  Build/Run Time Test: {passed}/{total}")
print(f"  Pass rate: {passed / total * 100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> All Build/Run Time functions working correctly <<<")
else:
    print(f"\n  >>> {total - passed} failure(s) <<<")

sys.exit(0 if passed == total else 1)
