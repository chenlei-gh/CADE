#!/usr/bin/env python3
"""
Kernel Public API Contract Tests (L0)
=====================================
Verify the 3-mode external interface that AI sees.
These tests define the contract — they must pass regardless of
internal refactoring.

Contract:
  - develop(request) → {status, ...}   (Command — may modify files)
  - analyze(request)  → {status, ...}   (Query   — read-only)
  - repair(request)   → {status, ...}   (Command — may modify with recovery)
"""

import shutil
import sys
import tempfile
from pathlib import Path

# Add skills to path
SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from kernel import Kernel, KernelMode

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  Kernel Public API Contract Tests (L0)")
print("=" * 60)

# ═══════════════════════════════════════════════════════════════════
# Setup: temporary workspace
# ═══════════════════════════════════════════════════════════════════

ws = Path(tempfile.mkdtemp(prefix="cade_kernel_"))
kernel = Kernel(workspace_root=str(ws))
print(f"\nWorkspace: {ws}")

# ═══════════════════════════════════════════════════════════════════
# [1] develop() — clear intent → succeeds
# ═══════════════════════════════════════════════════════════════════
print("\n[1] develop() — clear intent succeeds")
result = kernel.execute(KernelMode.DEVELOP, "create command MyCmd in MyModule.m")
ck("returns ok", result["status"] in ("ok", "pending"),
   f"status={result['status']}")
ck("has changeset", "changeset" in result or "preview" in result,
   f"keys={list(result.keys())}")
ck("has message", "message" in result or "preview" in result)

# ═══════════════════════════════════════════════════════════════════
# [2] develop() — vague intent → needs clarification
# ═══════════════════════════════════════════════════════════════════
print("\n[2] develop() — vague intent needs clarification")
result = kernel.execute(KernelMode.DEVELOP, "I want to make an assembly statistics tool")
ck("returns needs_clarification or ok",
   result["status"] in ("needs_clarification", "ok"),
   f"status={result['status']}")

# ═══════════════════════════════════════════════════════════════════
# [3] develop() — empty request
# ═══════════════════════════════════════════════════════════════════
print("\n[3] develop() — empty request")
result = kernel.execute(KernelMode.DEVELOP, "")
ck("returns error for empty request",
   result["status"] in ("error", "needs_clarification"),
   f"status={result['status']}")

# ═══════════════════════════════════════════════════════════════════
# [4] analyze() — workspace analysis
# ═══════════════════════════════════════════════════════════════════
print("\n[4] analyze() — workspace analysis")
result = kernel.execute(KernelMode.ANALYZE, "analyze the workspace")
ck("returns ok", result["status"] in ("ok", "valid"),
   f"status={result['status']}")

# ═══════════════════════════════════════════════════════════════════
# [5] analyze() — is read-only (no file changes)
# ═══════════════════════════════════════════════════════════════════
print("\n[5] analyze() — is read-only")
files_before = set(str(p.relative_to(ws)) for p in ws.rglob("*") if p.is_file()
                   if ".caa_backups" not in str(p))
result = kernel.execute(KernelMode.ANALYZE, "list modules in the workspace")
files_after = set(str(p.relative_to(ws)) for p in ws.rglob("*") if p.is_file()
                  if ".caa_backups" not in str(p))
ck("analyze does not modify files",
   files_before == files_after,
   f"before={len(files_before)} after={len(files_after)}")

# ═══════════════════════════════════════════════════════════════════
# [6] analyze() — diagnostics
# ═══════════════════════════════════════════════════════════════════
print("\n[6] analyze() — diagnostics")
result = kernel.execute(KernelMode.ANALYZE, "diagnose the workspace")
ck("returns ok or has diagnostics",
   result["status"] in ("ok", "valid") or "diagnostics" in result,
   f"status={result['status']}")

# ═══════════════════════════════════════════════════════════════════
# [7] repair() — basic repair (dry-run)
# ═══════════════════════════════════════════════════════════════════
print("\n[7] repair() — basic repair")
result = kernel.execute(KernelMode.REPAIR, "fix missing dictionary entries")
ck("returns ok or not_applicable",
   result["status"] in ("ok", "fixed", "no_issues", "not_applicable"),
   f"status={result['status']}")

# ═══════════════════════════════════════════════════════════════════
# [8] repair() — empty request
# ═══════════════════════════════════════════════════════════════════
print("\n[8] repair() — empty request")
result = kernel.execute(KernelMode.REPAIR, "")
ck("returns error for empty request",
   result["status"] in ("error", "no_issues"),
   f"status={result['status']}")

# ═══════════════════════════════════════════════════════════════════
# [9] KernelMode validation
# ═══════════════════════════════════════════════════════════════════
print("\n[9] KernelMode enumeration")
ck("has DEVELOP", hasattr(KernelMode, "DEVELOP"))
ck("has ANALYZE", hasattr(KernelMode, "ANALYZE"))
ck("has REPAIR", hasattr(KernelMode, "REPAIR"))
ck("DEVELOP is develop", KernelMode.DEVELOP.value == "develop")
ck("ANALYZE is analyze", KernelMode.ANALYZE.value == "analyze")
ck("REPAIR is repair", KernelMode.REPAIR.value == "repair")

# ═══════════════════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════════════════

shutil.rmtree(ws, ignore_errors=True)

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
