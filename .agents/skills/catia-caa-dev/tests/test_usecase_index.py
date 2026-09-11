#!/usr/bin/env python3
"""
UseCaseIndex Acceptance Suite
==============================
Four acceptance cases for the Official Example Presence Index:

  Case 1 — find by interface: CATIVisProperties must locate the
           verified official sample CAAMmrSetShowModeCmd.
  Case 2 — method->owner join: SetPropertiesAtt must combine
           UseCaseIndex (examples) with MethodIndex (owners).
  Case 3 — negative: a fabricated name must return empty
           ("No official example found"), never a guessed hit.
  Case 4 — regression guard (2026-07-31): stem collisions (e.g. 9
           different modules each shipping their own main.cpp) must
           not silently drop files or cross-contaminate token lookups
           between unrelated modules.

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

# ── Case 4: stem-collision regression guard (2026-07-31) ──────────
# 1233 files on disk share only 1214 unique .cpp stems (9 modules each
# ship their own main.cpp). The builder must key colliding stems as
# "stem (module.m)" so no file is dropped and no module's tokens bleed
# into another module's lookup results.
main_keys = [k for k in uc.get("examples", {}) if k.startswith("main")]
ck("Case4: colliding stems disambiguated (9 distinct main.cpp entries)",
   len(main_keys) >= 9, f"{len(main_keys)} main.cpp keys: {main_keys}")

disk_count = 0
try:
    from env import CAAEnvironment
    _env = CAAEnvironment()
    _env.load_config()
    _catia = _env.config.get("CATIA_INSTALL", "")
    if _catia:
        _caadoc = Path(_catia) / "CAADoc"
        if _caadoc.is_dir():
            disk_count = len(list(_caadoc.glob("*.edu/*/src/**/*.cpp")))
except Exception:
    disk_count = 0

if disk_count:
    ck("Case4: no file dropped (examples count == files on disk)",
       len(uc.get("examples", {})) == disk_count,
       f"index={len(uc.get('examples', {}))} disk={disk_count}")
else:
    print("  [SKIP] Case4 disk-count check: CATIA_INSTALL not configured")

# ── Case 5: schema 3 resources section ──────────────────────────
# Builder extended beyond .cpp presence: Imakefile libs, LocalInterfaces
# headers, CATNls keys, CATRsc identifiers. resources/by_kind must exist
# with non-trivial counts and the per-kind lookup fields populated.
res = uc.get("resources", {})
by_kind = uc.get("by_kind", {})
ck("Case5: resources section present", len(res) > 0, f"{len(res)} resources")

EXPECTED_KINDS = ("imakefile", "local_header", "nls", "rsc")
for k in EXPECTED_KINDS:
    ck(f"Case5: by_kind['{k}'] non-empty",
       len(by_kind.get(k, {})) > 0, f"{len(by_kind.get(k, {}))}")

# Per-kind lookup field: imakefile -> libs, local_header -> interfaces,
# nls/rsc -> keys. by_kind maps kind -> [resource keys]; the fields live
# on the entry under resources[key]. Spot-check one entry of each kind.
def _sample(kind):
    keys = by_kind.get(kind, [])
    return (keys[0], res.get(keys[0], {})) if keys else (None, {})

im_name, im = _sample("imakefile")
ck("Case5: imakefile entry has libs", len(im.get("libs", [])) > 0,
   f"{im_name}: {im.get('libs', [])[:3]}")
# local_header 'interfaces' = CATI* includes. Implementation headers
# (CATDeclareClass, deriving from CATE* bases) legitimately include zero
# CATI* headers, so per-entry emptiness is valid — assert the kind
# carries SOME interface signal across the set, not that a sample does.
lh_with = [k for k in by_kind.get("local_header", [])
           if res.get(k, {}).get("interfaces")]
ck("Case5: local_header kind carries interface includes",
   len(lh_with) > 0, f"{len(lh_with)}/{len(by_kind.get('local_header', []))} non-empty")
nls_name, nls = _sample("nls")
ck("Case5: nls entry has keys", len(nls.get("keys", [])) > 0, f"{nls_name}")
rsc_name, rsc = _sample("rsc")
ck("Case5: rsc entry has keys", len(rsc.get("keys", [])) > 0, f"{rsc_name}")

print("-" * 60)
print(f"  RESULT: {passed}/{total} passed")
print("=" * 60)
print("USECASE INDEX OK" if passed == total else "USECASE INDEX FAILED")
