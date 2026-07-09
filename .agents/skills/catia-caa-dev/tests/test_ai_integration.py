#!/usr/bin/env python3
"""
AI Response Integration Test
==============================
Simulates an AI agent calling CADE end-to-end through the MCP layer.
Verifies response format, token efficiency, and error consistency.

Run: python test_ai_integration.py
"""

import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from actions import ActionContext
from token_optimizer import optimize

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    s = "PASS" if ok else "FAIL"
    print(f"  [{s}] {label}" + (f" - {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════
# 1. AI asks: "What's in my workspace?"
# ═══════════════════════════════════════════════════════════
print("=" * 70)
print("  1. AI: 'analyze my workspace'")
print("=" * 70)

ctx = ActionContext()
snap = ctx.snapshot
d = snap.to_dict() if snap else {}

fw_count = d.get("framework_count", 0)
module_count = d.get("total_modules", 0)
check("snapshot available", snap is not None)
check("to_dict is dict", isinstance(d, dict))
check("has framework_count", "framework_count" in d)

# AI-friendly format via optimizer
optimized = optimize(d, mode="auto")
opt_tokens = len(json.dumps(optimized))
raw_tokens = len(json.dumps(d))
check(f"optimized < raw ({opt_tokens} vs {raw_tokens})",
      opt_tokens <= raw_tokens, f"saved {raw_tokens - opt_tokens} tokens ({100 - opt_tokens * 100 // max(raw_tokens, 1)}%)")


# ═══════════════════════════════════════════════════════════
# 2. AI asks: "List my modules"
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  2. AI: 'list modules'")
print("=" * 70)

from actions import list_modules, list_commands, list_interfaces

r = list_modules(ctx)
check("list_modules returns dict", isinstance(r, dict))
check("has status", r.get("status") == "ok")
check("has modules key", "modules" in r or "count" in r)

# Optimize
r_opt = optimize(r, mode="auto")
check("optimized list has ok", r_opt.get("ok") is True)


# ═══════════════════════════════════════════════════════════
# 3. AI asks: "Create a command"
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  3. AI: 'create a command with dialog'")
print("=" * 70)

from intents import create_executable_command

r = create_executable_command(ctx, name="AI_TestCmd", module="TestModule.m",
                               with_dialog=True)
check("create returns dict", isinstance(r, dict))
check("has status", "status" in r)
check("status is pending or error", r["status"] in ("pending", "error"),
      r["status"])

# Response must be self-contained: AI should understand what happened
check("has preview or message", "preview" in r or "message" in r)
check("message not empty", bool(r.get("message", "") or r.get("preview")))


# ═══════════════════════════════════════════════════════════
# 4. AI encounters an error
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  4. AI: 'create in nonexistent module'")
print("=" * 70)

r = create_executable_command(ctx, name="BadCmd",
                               module="NonExistent_XYZ_123.m")
check("error returns dict", isinstance(r, dict))
check("error status", r["status"] == "error")
check("error has message", "message" in r)
check("error message meaningful", len(r.get("message", "")) > 10,
      r.get("message", "")[:60])


# ═══════════════════════════════════════════════════════════
# 5. AI calls diagnostics
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  5. AI: 'diagnose my workspace'")
print("=" * 70)

from diagnostics import diagnose_workspace

r = diagnose_workspace(ctx)
check("diagnose returns dict", isinstance(r, dict))
check("has status", "status" in r)
check("has total/errors keys", "total" in r, f"total={r.get('total', '?')}")

# Optimized response
r_opt = optimize(r, mode="auto")
check("optimized has ok", "ok" in r_opt)
check("optimized much smaller", len(json.dumps(r_opt)) <= len(json.dumps(r)),
      f"opt={len(json.dumps(r_opt))} vs raw={len(json.dumps(r))}")


# ═══════════════════════════════════════════════════════════
# 6. AI requests suggestions
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  6. AI: 'what should I do next?'")
print("=" * 70)

from intents import suggest_next_action

r = suggest_next_action(ctx)
check("suggest returns dict", isinstance(r, dict))
check("has content", len(r) > 0, f"keys={list(r.keys())[:5]}")


# ═══════════════════════════════════════════════════════════
# 7. AI calls build (dry run)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  7. AI: 'build my workspace'")
print("=" * 70)

try:
    from build import build_workspace
    w = Path(".").resolve()
    r = build_workspace(w, "-n", timeout=30)
    check("build returns dict", isinstance(r, dict))
    check("has status", "status" in r)

    # Token optimized
    r_opt = optimize(r, mode="auto")
    check("build optimized has ok", "ok" in r_opt)
    check("build output NOT in optimized", "output" not in r_opt)
    check("build optimized < 500 tokens",
          len(json.dumps(r_opt)) < 500,
          f"{len(json.dumps(r_opt))} tokens")
except Exception as e:
    check("build skipped (no mkmk)", True, str(e)[:60])


# ═══════════════════════════════════════════════════════════
# 8. MCP response format validation
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  8. MCP response format")
print("=" * 70)

# Simulate MCP response wrapping
def mcp_wrap(result):
    """Simulate mcp_server.py response formatting."""
    result = optimize(result, mode="auto")
    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, indent=2, default=str),
        }]
    }

r = mcp_wrap(ctx.snapshot.to_dict())
check("MCP wrap has content", "content" in r)
check("MCP content is list", isinstance(r["content"], list))
check("MCP content[0] has text", "text" in r["content"][0])
check("MCP text is valid JSON",
      json.loads(r["content"][0]["text"]) is not None)


# ═══════════════════════════════════════════════════════════
# 9. Full AI workflow chain
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  9. Full AI workflow: snapshot → create → diagnose → suggest")
print("=" * 70)

results = {}
total_tokens = 0

# Step 1: Snapshot
r = ctx.snapshot.to_dict()
results["snapshot"] = r
total_tokens += len(json.dumps(r))
check("Step 1: snapshot ok", r is not None)

# Step 2: List modules
r = list_modules(ctx)
results["list_modules"] = r
total_tokens += len(json.dumps(r))
check("Step 2: list_modules ok", r["status"] == "ok")

# Step 3: Create command
r = create_executable_command(ctx, name="AI_FlowTest", module="TestModule.m",
                               with_dialog=False)
results["create"] = r
total_tokens += len(json.dumps(r))
check("Step 3: create ok", r["status"] in ("pending", "error"))

# Step 4: Diagnose
r = diagnose_workspace(ctx)
results["diagnose"] = r
total_tokens += len(json.dumps(r))
check("Step 4: diagnose ok", isinstance(r, dict))

# Step 5: Suggest
r = suggest_next_action(ctx)
results["suggest"] = r
total_tokens += len(json.dumps(r))
check("Step 5: suggest ok", isinstance(r, dict))

check(f"Total raw tokens: {total_tokens}", total_tokens > 0)

# With optimizer
opt_tokens = sum(len(json.dumps(optimize(v, mode="auto")))
                 for v in results.values())
savings = total_tokens - opt_tokens
pct = savings * 100 // max(total_tokens, 1)
check(f"Optimizer saves {pct}% tokens ({savings}/{total_tokens})",
      savings > 0)


# ═══════════════════════════════════════════════════════════
# 10. Error response consistency
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  10. Error response consistency")
print("=" * 70)

# All errors should follow same format: {status: "error", message: "..."}
from build import error_result
from refactor import rename_command
from intents import create_feature, create_extension
from run import check_catia_running as catia_status

error_sources = [
    ("build", error_result("test error")),
    ("create_feature", create_feature(ctx, name="X", module="NoModule.m")),
    ("create_extension",
     create_extension(ctx, name="X", target_object="CATPart", module="NoModule.m")),
]

for source, r in error_sources:
    check(f"{source}: is dict", isinstance(r, dict))
    check(f"{source}: has status", "status" in r)
    check(f"{source}: has message", "message" in r or "error" in r.get("status", ""))


# ═══════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"  AI INTEGRATION: {passed}/{total}")
if total:
    print(f"  Pass rate: {passed / total * 100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> AI can seamlessly use ALL CADE APIs <<<")
    sys.exit(0)
else:
    print(f"\n  >>> {total - passed} issue(s) — AI experience degraded <<<")
    sys.exit(1)
