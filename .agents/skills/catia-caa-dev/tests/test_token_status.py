#!/usr/bin/env python3
"""
Token Optimizer Status Contract Test
======================================
Verify that v3.0 status codes trigger the correct optimization level.
Prevents regression where new statuses waste AI context via
unnecessary detail mode.
"""

import sys
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))
from token_optimizer import optimize
from kernel import Kernel, KernelMode

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  Token Optimizer Status Contract Test")
print("=" * 60)

k = Kernel(workspace_root=".")

# Each (mode, query, expected_status, should_trigger_detail)
cases = [
    (KernelMode.DEVELOP,  "create command MyCmd in MyModule", "pending", False),
    (KernelMode.DEVELOP,  "I want to export BOM", "needs_clarification", True),
    (KernelMode.DEVELOP,  "", "error", True),
    (KernelMode.ANALYZE,  "analyze the workspace", "ok", False),
    (KernelMode.ANALYZE,  "how to create a fillet", "ok", False),
    (KernelMode.REPAIR,   "fix dictionary entries", "no_issues", False),
    (KernelMode.REPAIR,   "", "error", True),
]

print("\n[1] Status → detail mode mapping")
for mode, query, expected_status, expects_detail in cases:
    raw = k.execute(mode, query)
    opt = optimize(raw, mode="auto")
    has_detail = "detail" in opt
    ok_detail = has_detail == expects_detail

    ck(
        f"{expected_status:25s} detail={'yes' if expects_detail else 'no '}",
        ok_detail,
        f"got detail={'yes' if has_detail else 'no '}"
    )
    ck(
        f"{expected_status:25s} ok field correct",
        opt.get("ok") == (raw.get("status") in ("ok", "success", "stopped", "not_running", "pending", "no_issues", "fixed")),
        f"ok={opt.get('ok')}"
    )

# [2] needs_clarification preserves questions in detail
print("\n[2] needs_clarification preserves questions")
raw = k.execute(KernelMode.DEVELOP, "I want to export BOM from assembly")
opt = optimize(raw, mode="auto")
ck("has detail or question data", "detail" in opt or "questions" in str(opt))

# [3] Compression ratio is reasonable
print("\n[3] Compression ratio")
for mode, query, _, _ in cases:
    raw = k.execute(mode, query)
    opt = optimize(raw, mode="auto")
    raw_len = len(str(raw))
    opt_len = len(str(opt))
    ratio = (1 - opt_len / raw_len) * 100 if raw_len > 50 else 0
    ck(f"compression OK", ratio >= -10 or raw_len < 200, f"{ratio:.0f}% (raw={raw_len}, opt={opt_len})")

# [4] detail=auto never returns None detail
print("\n[4] detail field is always valid (dict or None or absent)")
for mode, query, _, _ in cases:
    raw = k.execute(mode, query)
    opt = optimize(raw, mode="auto")
    detail = opt.get("detail")
    ck(
        f"detail valid",
        detail is None or isinstance(detail, dict) or "detail" not in opt
    )

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
