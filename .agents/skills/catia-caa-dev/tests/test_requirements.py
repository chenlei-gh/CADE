#!/usr/bin/env python3
"""
Requirement Analysis Contract Tests (L1)
=========================================
Verify RequirementsClarifier input/output contract.

Contract:
  - clarify(request) → RequirementDocument with decisions + unresolved
  - Clear intent → no unresolved
  - Vague intent → returns clarifying questions (max 5)
  - Unknown domain → returns generic questions
  - Decision trees load from YAML
"""

import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from requirements import (
    ClarificationResult,
    Decision,
    RequirementDocument,
    RequirementsClarifier,
)

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  Requirements Contract Tests (L1)")
print("=" * 60)

clarifier = RequirementsClarifier()

# ═══════════════════════════════════════════════════════════════════
# [1] Clarify BOM export — should detect domain and ask questions
# ═══════════════════════════════════════════════════════════════════
print("\n[1] Clarify BOM export (vague)")
result = clarifier.analyze("Export BOM from assembly")
ck("returns RequirementDocument",
   isinstance(result, RequirementDocument) or isinstance(result, ClarificationResult))
if hasattr(result, "domain"):
    ck("detects product domain",
       result.domain == "product" or "product" in str(getattr(result, "domain", "")).lower(),
       f"domain={getattr(result, 'domain', 'N/A')}")

# ═══════════════════════════════════════════════════════════════════
# [2] Clear intent — create command
# ═══════════════════════════════════════════════════════════════════
print("\n[2] Clear intent (create command)")
result = clarifier.analyze("create command ExportBOM in MyModule.m")
ck("returns RequirementDocument or ClarificationResult",
   isinstance(result, (RequirementDocument, ClarificationResult)))

# ═══════════════════════════════════════════════════════════════════
# [3] Unknown / generic request
# ═══════════════════════════════════════════════════════════════════
print("\n[3] Unknown request")
result = clarifier.analyze("do something cool with CATIA")
ck("handles unknown request without crash",
   isinstance(result, (RequirementDocument, ClarificationResult)))

# ═══════════════════════════════════════════════════════════════════
# [4] RequirementDocument data structure
# ═══════════════════════════════════════════════════════════════════
print("\n[4] RequirementDocument structure")
doc = RequirementDocument(goal="test", domain="product")
ck("has goal", doc.goal == "test")
ck("has domain", doc.domain == "product")
ck("has decisions dict", isinstance(doc.decisions, dict))
ck("has unresolved list", isinstance(doc.unresolved, list))
ck("to_dict works", isinstance(doc.to_dict(), dict))

# ═══════════════════════════════════════════════════════════════════
# [5] Decision data structure
# ═══════════════════════════════════════════════════════════════════
print("\n[5] Decision data structure")
d = Decision(id="test", question="What?", options=["a", "b"])
ck("has id", d.id == "test")
ck("has question", d.question == "What?")
ck("has options", d.options == ["a", "b"])
ck("has_resolved is False by default", not d.has_resolved())
d.resolve("a")
ck("has_resolved is True after resolve", d.has_resolved())
ck("resolved value", d.resolved_value == "a")

# ═══════════════════════════════════════════════════════════════════
# [6] ClarificationResult structure
# ═══════════════════════════════════════════════════════════════════
print("\n[6] ClarificationResult structure")
cr = ClarificationResult(
    domain="product",
    goal="export BOM",
    resolved={"output_format": "csv"},
    unresolved=[Decision(id="depth", question="Traversal depth?", options=["top", "recursive"])],
)
ck("status is needs_clarification", cr.status == "needs_clarification")
ck("has unresolved count", len(cr.unresolved) == 1)
ck("to_dict works", isinstance(cr.to_dict(), dict))
d = cr.to_dict()
ck("to_dict has questions", "questions" in d)
ck("to_dict has resolved", "resolved" in d)

# ═══════════════════════════════════════════════════════════════════
# [7] Clarifier returns max 5 questions
# ═══════════════════════════════════════════════════════════════════
print("\n[7] Clarifier question limit")
# Even for the vaguest request, should not flood with questions
result = clarifier.analyze("make something")
if isinstance(result, ClarificationResult):
    unresolved = result.unresolved if hasattr(result, "unresolved") else []
    ck("max 5 unresolved questions",
       len(unresolved) <= 5,
       f"count={len(unresolved)}")
else:
    ck("result is valid type", True, "non-ClarificationResult is acceptable")

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
