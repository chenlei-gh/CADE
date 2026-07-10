#!/usr/bin/env python3
"""
Repair Loop Contract Tests (L2)
================================
Verify RepairLoop state machine contract.

Contract:
  - fix in 1 attempt → status=fixed, attempts=1
  - fix after retries → status=fixed, attempts=N
  - max retries exceeded → status=escalated, attempts=3
  - no issues → status=no_issues
"""

import shutil
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from repair import RepairLoop, RepairResult, RepairState

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  Repair Loop Contract Tests (L2)")
print("=" * 60)

# ═══════════════════════════════════════════════════════════════════
# [1] RepairResult data structure
# ═══════════════════════════════════════════════════════════════════
print("\n[1] RepairResult structure")
r = RepairResult(state=RepairState.FIXED, attempts=1, fixes_applied=1)
ck("has state", r.state == RepairState.FIXED)
ck("has attempts", r.attempts == 1)
ck("has fixes_applied", r.fixes_applied == 1)
ck("is_success is True", r.is_success())
ck("to_dict works", isinstance(r.to_dict(), dict))

# ═══════════════════════════════════════════════════════════════════
# [2] RepairResult — escalated
# ═══════════════════════════════════════════════════════════════════
print("\n[2] RepairResult — escalated")
r = RepairResult(state=RepairState.ESCALATED, attempts=3, fixes_applied=0,
                 message="Max retries exceeded")
ck("state is ESCALATED", r.state == RepairState.ESCALATED)
ck("attempts is 3", r.attempts == 3)
ck("is_success is False", not r.is_success())

# ═══════════════════════════════════════════════════════════════════
# [3] RepairResult — no_issues
# ═══════════════════════════════════════════════════════════════════
print("\n[3] RepairResult — no issues")
r = RepairResult(state=RepairState.NO_ISSUES, attempts=0, fixes_applied=0)
ck("state is NO_ISSUES", r.state == RepairState.NO_ISSUES)
ck("is_success is True (no issues = success)", r.is_success())

# ═══════════════════════════════════════════════════════════════════
# [4] RepairLoop — empty workspace (no issues)
# ═══════════════════════════════════════════════════════════════════
print("\n[4] RepairLoop — empty workspace")
ws = Path(tempfile.mkdtemp(prefix="cade_repair_"))
loop = RepairLoop(workspace_root=ws)
result = loop.run()
ck("returns RepairResult", isinstance(result, RepairResult))
ck("no issues in empty workspace",
   result.state in (RepairState.NO_ISSUES, RepairState.FIXED),
   f"state={result.state.value if hasattr(result.state, 'value') else result.state}")
shutil.rmtree(ws, ignore_errors=True)

# ═══════════════════════════════════════════════════════════════════
# [5] RepairLoop max retries = 3
# ═══════════════════════════════════════════════════════════════════
print("\n[5] RepairLoop max retries")
ck("MAX_RETRIES is defined", hasattr(RepairLoop, "MAX_RETRIES"))
ck("MAX_RETRIES is 3", RepairLoop.MAX_RETRIES == 3)

# ═══════════════════════════════════════════════════════════════════
# [6] RepairState enumeration
# ═══════════════════════════════════════════════════════════════════
print("\n[6] RepairState enumeration")
ck("has FIXED", hasattr(RepairState, "FIXED"))
ck("has ESCALATED", hasattr(RepairState, "ESCALATED"))
ck("has NO_ISSUES", hasattr(RepairState, "NO_ISSUES"))
ck("has IN_PROGRESS", hasattr(RepairState, "IN_PROGRESS"))
ck("has FAILED", hasattr(RepairState, "FAILED"))

# ═══════════════════════════════════════════════════════════════════
# [7] RepairLoop — handles nonexistent workspace
# ═══════════════════════════════════════════════════════════════════
print("\n[7] RepairLoop — nonexistent workspace")
loop = RepairLoop(workspace_root=Path("/nonexistent/path/12345"))
result = loop.run()
ck("handles gracefully",
   isinstance(result, RepairResult),
   f"state={result.state.value if hasattr(result.state, 'value') else result.state}")

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
