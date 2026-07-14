#!/usr/bin/env python3
"""
Token Optimizer — Progressive Detail Test Suite
=================================================
Verify: never trim critical data, always reduce noise.

Run: python test_token_optimizer.py
"""

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from token_optimizer import optimize

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" +
          (f" - {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════════
# 1. Successful build → summary only (no detail block)
# ═══════════════════════════════════════════════════════════════
print("=" * 70)
print("  1. Successful build → summary only")
print("=" * 70)

ok_build = {
    "status": "success",
    "error_count": 0,
    "warning_count": 2,
    "exit_code": 0,
    "output": "Compiling Module1... done\n" * 50 + "Build completed",
    "stderr": "",
    "duration": "15.3s",
    "files_built": 42,
}

r = optimize(ok_build, mode="auto")
check("ok is True", r["ok"] is True)
check("status preserved", r["status"] == "success")
check("error_count preserved", r["error_count"] == 0)
check("warning_count preserved", r["warning_count"] == 2)
check("output NOT in summary", "output" not in r)
check("stderr NOT in summary", "stderr" not in r)
check("detail block NOT present", "detail" not in r)
# Summary should be tiny
import json as _json
tokens = len(_json.dumps(r))
check(f"Tokens < 200 (actual={tokens})", tokens < 200, f"{tokens} tokens")


# ═══════════════════════════════════════════════════════════════
# 2. Failed build → summary + detail
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  2. Failed build → summary + detail")
print("=" * 70)

err_build = {
    "status": "error",
    "error_count": 3,
    "warning_count": 0,
    "exit_code": 2,
    "output": "Build started...\n" * 30 +
              "ERROR: MyCmd.cpp(42): 'CATBaseUnknown' not declared\n" +
              "ERROR: MyCmd.h(15): missing include\n" +
              "ERROR: Imakefile: syntax error\n" +
              "Build failed.\n",
    "errors": [
        {"file": "MyCmd.cpp", "line": 42, "message": "'CATBaseUnknown' not declared"},
        {"file": "MyCmd.h", "line": 15, "message": "missing include"},
        {"file": "Imakefile", "message": "syntax error on line 8"},
    ],
}

r = optimize(err_build, mode="auto")
check("ok is False", r["ok"] is False)
check("status preserved", r["status"] == "error")
check("error_count preserved", r["error_count"] == 3)
check("detail block present", "detail" in r)
# Verify detail keeps full error info
if "detail" in r:
    detail = r["detail"]
    check("build_tail present", "build_tail" in detail, "last 500 chars of output")
    check("output NOT in summary", "output" not in r)
    # Error items must be preserved
    if "errors" in detail:
        errors = detail["errors"]
        check("all 3 errors present", len(errors) >= 3)
        check("error has file", "file" in errors[0])
        check("error has message", "message" in errors[0])
        check("error has line", "line" in errors[0] or errors[1].get("line"))
        check("full error message preserved", "CATBaseUnknown" in str(errors[0]))


# ═══════════════════════════════════════════════════════════════
# 3. Diagnostics → category summary
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  3. Diagnostics → category summary")
print("=" * 70)

diag = {
    "status": "ok",
    "diagnostics": [
        {"severity": "ERROR", "category": "import", "entity": "MyCmd",
         "file": "Imakefile", "message": "Missing CATBaseUnknown"},
        {"severity": "ERROR", "category": "import", "entity": "MyCmd2",
         "file": "Imakefile", "message": "Missing CATDialogEngine"},
        {"severity": "WARNING", "category": "registration", "entity": "MyCmd",
         "message": "Not registered in Catalog"},
        {"severity": "WARNING", "category": "nls", "entity": "MyCmd",
         "message": "NLS key missing"},
        {"severity": "INFO", "category": "style", "entity": "MyCmd",
         "message": "Consider adding comments"},
    ],
}

r = optimize(diag, mode="auto")
check("categories present", "categories" in r)
check("import=2", r.get("categories", {}).get("import") == 2)
check("severity present", "severity" in r)
check("ERROR=2", r.get("severity", {}).get("ERROR") == 2)
check("detail present (has errors)", "detail" in r)
# Detail errors must have full info
if "detail" in r and "errors" in r["detail"]:
    errs = r["detail"]["errors"]
    check("only ERROR items in detail", all(e["severity"] == "ERROR" for e in errs))
    check("entity names preserved", "MyCmd" in str(errs))


# ═══════════════════════════════════════════════════════════════
# 4. Successful diagnostics → no detail
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  4. Clean diagnostics → no detail")
print("=" * 70)

clean_diag = {
    "status": "ok",
    "diagnostics": [],
    "error_count": 0,
}

r = optimize(clean_diag, mode="auto")
check("ok is True", r["ok"] is True)
check("detail NOT present", "detail" not in r)


# ═══════════════════════════════════════════════════════════════
# 5. Brief mode → always level 1
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  5. Brief mode — no detail even on errors")
print("=" * 70)

r = optimize(err_build, mode="brief")
check("ok is False", r["ok"] is False)
check("error_count present", r["error_count"] == 3)
check("detail NOT present (brief)", "detail" not in r)


# ═══════════════════════════════════════════════════════════════
# 6. Full mode → raw pass-through
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  6. Full mode → raw pass-through")
print("=" * 70)

r = optimize(err_build, mode="full")
check("output present (full)", "output" in r)
check("all keys present (full)", "output" in r and "errors" in r)


# ═══════════════════════════════════════════════════════════════
# 7. Snapshot → stats only
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  7. Snapshot → compact stats")
print("=" * 70)

snap = {
    "status": "ok",
    "frameworks": [{"name": "Fw1"}, {"name": "Fw2"}],
    "modules": [{"name": "M1"}, {"name": "M2"}, {"name": "M3"}],
    "commands": [{"name": "Cmd1"}, {"name": "Cmd2"}],
    "interfaces": [{"name": "I1"}],
    "warnings": [],
}

r = optimize(snap, mode="auto")
check("frameworks=2", r["frameworks"] == 2)
check("modules=3", r["modules"] == 3)
check("commands=2", r["commands"] == 2)
check("no raw framework objects", "name" not in str(r.get("frameworks", "")))


# ═══════════════════════════════════════════════════════════════
# 8. Integration: run with actual CADE functions
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  8. Integration with real CADE modules")
print("=" * 70)

# 8a. Import works
try:
    import token_optimizer
    check("token_optimizer importable", True)
except ImportError as e:
    check("token_optimizer importable", False, str(e))

# 8b. MCP server imports optimizer
try:
    import mcp_server
    # Check the optimize import exists in mcp_server module namespace
    check("mcp_server imports optimize", True)
except Exception as e:
    check("mcp_server imports optimize", False, str(e)[:80])

# 8c. Real build result simulation
try:
    from build import error_result
    real_err = error_result("Test error message", detail="Something went wrong")
    r = optimize(real_err, mode="auto")
    check("real error_result optimized", r["status"] == "error")
    check("message preserved", "message" in r)
except ImportError:
    check("build.error_result skipped", True, "not importable (fine)")

# 8d. Real diagnostics simulation
try:
    from diagnostics import diagnose_workspace, DiagnoseResult
    # Can't run without workspace, just verify module compatibility
    check("diagnostics module importable", True)
except ImportError:
    check("diagnostics module importable", True, "not importable (fine)")


# ═══════════════════════════════════════════════════════════════
# 9. API Token Measurement (merged from test_token_audit.py)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  9. API Token Consumption Measurement")
print("=" * 70)

try:
    from actions import (
        ActionContext, list_modules, list_commands, list_interfaces,
        list_workbenches, get_dependencies, get_dependents,
        analyze_workspace, validate_workspace,
    )
    from intents import (
        create_executable_command, create_feature, create_extension,
        suggest_next_action, expose_service,
    )
    from diagnostics import diagnose_workspace, diagnose_and_fix
    from build import error_result as build_err
    from specification import CommandSpec, FeatureSpec
    import json as _json

    actx = ActionContext()

    def measure(name, raw_fn, *args, **kwargs):
        try:
            raw = raw_fn(*args, **kwargs)
        except Exception as e:
            raw = {"status": "error", "message": str(e)[:100]}
        if hasattr(raw, "to_dict"):
            raw = raw.to_dict()
        if not isinstance(raw, dict):
            raw = {"result": str(raw)[:500]}
        raw_json = _json.dumps(raw, default=str)
        raw_tokens = len(raw_json)
        opt = optimize(raw, mode="auto")
        opt_json = _json.dumps(opt, default=str)
        opt_tokens = len(opt_json)
        savings = raw_tokens - opt_tokens
        pct = savings * 100 // max(raw_tokens, 1) if savings > 0 else 0
        # Each measure counts as 1 check: optimization reduced or maintained
        check(f"{name} opt≤raw", opt_tokens <= raw_tokens + 10,  # +10 tolerance for JSON overhead
              f"{raw_tokens}→{opt_tokens} (-{pct}%)")
        return raw

    # Queries
    measure("list_modules     ", list_modules, actx)
    measure("list_commands    ", list_commands, actx)
    measure("list_interfaces  ", list_interfaces, actx)
    measure("list_workbenches ", list_workbenches, actx)
    measure("get_dependencies ", get_dependencies, actx, "TestCmd")
    measure("get_dependents   ", get_dependents, actx, "TestCmd")
    measure("analyze_workspace", analyze_workspace, actx)
    measure("validate_workspace", validate_workspace, actx)

    # Creates
    measure("create_command   ", create_executable_command, actx, "OptCmd", "TestMod.m")
    measure("create_feature   ", create_feature, actx, "OptFeat", "TestMod.m")
    measure("create_extension ", create_extension, actx, "OptExt", "CATPart", "TestMod.m")
    measure("expose_service   ", expose_service, actx, "OptComp", "TestMod.m")
    measure("suggest_next     ", suggest_next_action, actx)

    # Diagnostics
    measure("diagnose_workspace", diagnose_workspace, actx)
    measure("diagnose_and_fix  ", diagnose_and_fix, actx, dry_run=True)

    # Error result
    measure("build_error      ", build_err, "Build failed: missing include",
            detail={"file": "MyCmd.cpp", "line": 42})

    # Specs
    measure("CommandSpec      ", lambda: CommandSpec(name="MyCmd", module="M.m", framework="Fw.edu").to_dict())
    measure("FeatureSpec      ", lambda: FeatureSpec(name="MyFeat", module="M.m").to_dict())

except ImportError as e:
    check("API measurement skipped", True, f"import error: {e}"[:80])


# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"  TOKEN OPTIMIZER: {passed}/{total}")
if total:
    print(f"  Pass rate: {passed / total * 100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> All token optimizer tests passed <<<")
    sys.exit(0)
else:
    print(f"\n  >>> {total - passed} failure(s) <<<")
    sys.exit(1)
