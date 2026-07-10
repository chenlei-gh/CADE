#!/usr/bin/env python3
"""
Token Consumption Audit
========================
Measure actual token usage for every CADE API call.

Run: python test_token_audit.py
"""

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

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
from build import error_result
from specification import CommandSpec, FeatureSpec
from token_optimizer import optimize

ctx = ActionContext()

print("=" * 80)
print(f"  CADE TOKEN CONSUMPTION AUDIT")
print(f"  Mode: AI calls via MCP (all optimized)")
print("=" * 80)

rows = []

def measure(name, raw_fn, *args, **kwargs):
    """Run API, measure raw + optimized token counts."""
    try:
        raw = raw_fn(*args, **kwargs)
    except Exception as e:
        raw = {"status": "error", "message": str(e)[:100]}

    if hasattr(raw, "to_dict"):
        raw = raw.to_dict()
    if not isinstance(raw, dict):
        raw = {"result": str(raw)[:500]}

    raw_json = json.dumps(raw, default=str)
    raw_tokens = len(raw_json)

    opt = optimize(raw, mode="auto")
    opt_json = json.dumps(opt, default=str)
    opt_tokens = len(opt_json)

    savings = raw_tokens - opt_tokens
    pct = savings * 100 // max(raw_tokens, 1) if savings > 0 else 0

    rows.append((name, raw_tokens, opt_tokens, pct))
    return raw


# ═══ Queries ═══════════════════════════════════════════════
print("\n  Queries:")
measure("list_modules     ", list_modules, ctx)
measure("list_commands    ", list_commands, ctx)
measure("list_interfaces  ", list_interfaces, ctx)
measure("list_workbenches ", list_workbenches, ctx)
measure("get_dependencies ", get_dependencies, ctx, "TestCmd")
measure("get_dependents   ", get_dependents, ctx, "TestCmd")
measure("analyze_workspace", analyze_workspace, ctx)
measure("validate_workspace", validate_workspace, ctx)

# ═══ Creates ═══════════════════════════════════════════════
print("  Creates:")
measure("create_command   ", create_executable_command, ctx, "AuditCmd", "TestMod.m")
measure("create_feature   ", create_feature, ctx, "AuditFeat", "TestMod.m")
measure("create_extension ", create_extension, ctx, "AuditExt", "CATPart", "TestMod.m")
measure("expose_service   ", expose_service, ctx, "AuditComp", "TestMod.m")
measure("suggest_next     ", suggest_next_action, ctx)

# ═══ Diagnostics ═══════════════════════════════════════════
print("  Diagnostics:")
measure("diagnose_workspace", diagnose_workspace, ctx)
measure("diagnose_and_fix  ", diagnose_and_fix, ctx, dry_run=True)

# ═══ Errors ═══════════════════════════════════════════════
print("  Errors:")
measure("error_result     ", error_result, "Build failed: missing include", detail={"file": "MyCmd.cpp", "line": 42})

# ═══ Specifications ═══════════════════════════════════════
print("  Specs:")
measure("CommandSpec.to_dict", lambda: CommandSpec(name="MyCmd", module="M.m", framework="Fw.edu").to_dict())
measure("FeatureSpec.to_dict", lambda: FeatureSpec(name="MyFeat", module="M.m").to_dict())

# ═══ Summary ═══════════════════════════════════════════════
print("\n" + "=" * 80)
print(f"  {'API':<22s} {'Raw':>6s} {'Optimized':>10s} {'Savings':>8s}")
print("  " + "-" * 50)

total_raw = total_opt = 0
for name, raw, opt, pct in rows:
    bar = "#" * (pct // 5)
    print(f"  {name:<22s} {raw:>6d} {opt:>10d} {pct:>6d}% {bar}")
    total_raw += raw
    total_opt += opt

print("  " + "-" * 50)
total_pct = (total_raw - total_opt) * 100 // max(total_raw, 1)
print(f"  {'TOTAL':22s} {total_raw:>6d} {total_opt:>10d} {total_pct:>6d}%")
print("=" * 80)

# Severity classification
print(f"\n  HIGH (>1000 raw tokens):")
for name, raw, _, _ in rows:
    if raw > 1000:
        print(f"     {name.strip()}  {raw} tokens")

print(f"\n  MEDIUM (500-1000):")
for name, raw, _, _ in rows:
    if 500 <= raw <= 1000:
        print(f"     {name.strip()}  {raw} tokens")

print(f"\n  LOW (<500):")
for name, raw, _, _ in rows:
    if raw < 500:
        print(f"     {name.strip()}  {raw} tokens")

print()
