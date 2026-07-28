#!/usr/bin/env python3
"""
UseCaseIndex Acceptance Suite
==============================
Three acceptance cases for the Official Example Presence Index:

  Case 1 — find by interface: CATIVisProperties must locate the
           verified official sample CAAMmrSetShowModeCmd.
  Case 2 — method->owner join: SetPropertiesAtt must combine
           UseCaseIndex (examples) with MethodIndex (owners).
  Case 3 — negative: a fabricated name must return empty
           ("No official example found"), never a guessed hit.

Boundary under test: the index records PRESENCE only. Ownership comes
from MethodIndex at query time; the builder never infers it.
"""

import sys
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

total = passed = 0

def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  UseCaseIndex Acceptance")
print("=" * 60)

from retrieval import get_retrieval
r = get_retrieval(SKILL)

# Index must be present and non-trivial
uc = r.usecase_index
ck("index loaded", len(uc.get("examples", {})) > 1000,
   f"{len(uc.get('examples', {}))} examples")

# ── Case 1: find by interface ────────────────────────────────────
hits = r.find_usecases_for_interface("CATIVisProperties")
ck("Case1: CATIVisProperties finds examples", len(hits) > 0, f"{len(hits)} hits")
ck("Case1: CAAMmrSetShowModeCmd present (verified sample)",
   "CAAMmrSetShowModeCmd" in hits)

# ── Case 2: method -> examples + owners join ─────────────────────
res = r.find_usecases_for_method("SetPropertiesAtt")
ck("Case2: SetPropertiesAtt has official examples",
   "CAAMmrSetShowModeCmd" in res["examples"])
ck("Case2: ownership joined from MethodIndex",
   len(res["owners"]) > 0 and "CATIVisPropertiesAbstract" in res["owners"],
   f"owners={res['owners']}")

# ── Case 3: negative — fabricated name returns empty ─────────────
fake_iface = r.find_usecases_for_interface("CATFakeInterface")
fake_meth = r.find_usecases_for_method("SetShowNonexistent")
ck("Case3: CATFakeInterface -> no official example", fake_iface == [])
ck("Case3: fabricated method -> empty examples", fake_meth["examples"] == [])

print("-" * 60)
print(f"  RESULT: {passed}/{total} passed")
print("=" * 60)
print("USECASE INDEX OK" if passed == total else "USECASE INDEX FAILED")
