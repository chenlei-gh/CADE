#!/usr/bin/env python3
"""
SampleDataIndex Acceptance Suite
=================================
Verifies the SampleDataIndex (Ground Truth for CATIA built-in CAD test
models .CATPart, .CATProduct, .CATDrawing).

Cases covered:
  1. Index loading and cache consistency
  2. Kind filtering (part / product / drawing exclusivity)
  3. Framework resolution (e.g. CAAApplicationFrame)
  4. Source distinction (caadoc vs startup_catalog)
  5. Exact lookup by filename (get_sample_by_name)
  6. Negative lookups (fabricated names return empty / None, never throw)
  7. Facade integration (retrieval.py health and query delegation)
  8. CLI exit code and output format

Pure stdlib.
"""

import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

total = passed = 0


def ck(label: str, ok: bool, detail: str = ""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  SampleDataIndex Acceptance Suite")
print("=" * 60)

# ── 1. Index loading ──────────────────────────────────────────────
print("\n[1] Index Loading & Meta")
from sample_data_index import SampleDataIndex, CACHE_STATS

sdi = SampleDataIndex.load(SKILL_ROOT)
ck("index loaded", sdi._loaded, f"{sdi.total_count} files")
ck("has parts", sdi.part_count > 500, f"{sdi.part_count} parts")
ck("has products", sdi.product_count > 100, f"{sdi.product_count} products")
ck("has drawings", sdi.drawing_count > 0, f"{sdi.drawing_count} drawings")
ck("has frameworks", sdi.framework_count > 10, f"{sdi.framework_count} frameworks")

# Re-load should hit process cache
sdi2 = SampleDataIndex.load(SKILL_ROOT)
ck("process cache hit", sdi is sdi2)

# ── 2. Kind filtering exclusivity ────────────────────────────────
print("\n[2] Kind Exclusivity")
parts = sdi.find_samples(kind="part", limit=50)
ck("part query non-empty", len(parts) > 0, f"{len(parts)} returned")
ck("all are parts", all(p["kind"] == "part" and p["ext"] == ".catpart" for p in parts))

products = sdi.find_samples(kind="product", limit=50)
ck("product query non-empty", len(products) > 0, f"{len(products)} returned")
ck("all are products", all(p["kind"] == "product" and p["ext"] == ".catproduct" for p in products))

drawings = sdi.find_samples(kind="drawing", limit=50)
ck("drawing query non-empty", len(drawings) > 0, f"{len(drawings)} returned")
ck("all are drawings", all(p["kind"] == "drawing" and p["ext"] == ".catdrawing" for p in drawings))

# ── 3. Framework resolution ──────────────────────────────────────
print("\n[3] Framework Resolution")
afr_parts = sdi.find_samples(framework="CAAApplicationFrame", kind="part")
ck("CAAApplicationFrame parts found", len(afr_parts) >= 2, f"{len(afr_parts)} models")
afr_names = {p["name"] for p in afr_parts}
ck("contains CAAAfrPart1.CATPart", "CAAAfrPart1.CATPart" in afr_names)
ck("contains CAAAfrPart2.CATPart", "CAAAfrPart2.CATPart" in afr_names)
ck("source is caadoc", all(p["source"] == "caadoc" for p in afr_parts))

# ── 4. Source distinction ────────────────────────────────────────
print("\n[4] Source Distinction (caadoc vs startup_catalog)")
caadoc_samples = sdi.find_samples(source="caadoc", limit=20)
ck("caadoc source hits", len(caadoc_samples) == 20)
ck("caadoc items have framework", all(bool(p["framework"]) for p in caadoc_samples))

startup_samples = sdi.find_samples(source="startup_catalog", limit=20)
ck("startup_catalog source hits", len(startup_samples) == 20)
ck("startup items have category", all(bool(p["category"]) for p in startup_samples))

# ── 5. Exact lookup by name ──────────────────────────────────────
print("\n[5] Exact Lookup by Name")
hit = sdi.get_sample_by_name("CAAAfrPart1.CATPart")
ck("exact name found", hit is not None)
if hit:
    ck("hit has name", hit["name"] == "CAAAfrPart1.CATPart")
    ck("hit has abs_path", bool(hit.get("abs_path")))
    ck("hit has size", hit.get("size_bytes", 0) > 0)
    ck("hit exists on disk", hit.get("exists", False), hit.get("abs_path", ""))

# Case insensitivity
hit_case = sdi.get_sample_by_name("caaafrpart1.catpart")
ck("case insensitive lookup", hit_case is not None and hit_case["name"] == "CAAAfrPart1.CATPart")

# ── 6. Negative lookups ──────────────────────────────────────────
print("\n[6] Negative Lookups")
bogus_query = sdi.find_samples(query="BogusModelXYZ_NonExistent_12345")
ck("bogus query returns empty", len(bogus_query) == 0)

bogus_fw = sdi.find_samples(framework="BogusFrameworkNonExistent")
ck("bogus framework returns empty", len(bogus_fw) == 0)

bogus_hit = sdi.get_sample_by_name("BogusFile_9999.CATPart")
ck("bogus name returns None", bogus_hit is None)

# ── 7. Facade Integration ────────────────────────────────────────
print("\n[7] Retrieval Facade Integration")
from retrieval import get_retrieval

r = get_retrieval(SKILL_ROOT)
facade_sdi = r.sample_data_index
ck("facade provides sample_data_index", facade_sdi is not None)
ck("facade shares total_count", facade_sdi.total_count == sdi.total_count)

facade_hits = r.find_sample_data(query="CAAAfrPart1")
ck("facade find_sample_data works", len(facade_hits) >= 1)

health = r.health()
ck("health report has sample_data_index", "sample_data_index" in health)
sdi_health = health.get("sample_data_index", {})
ck("sample_data_index health ok", sdi_health.get("ok", False))
ck("health reports total", sdi_health.get("total", 0) > 0)
ck("health reports parts", sdi_health.get("parts", 0) > 0)

# ── 8. CLI Entrypoint ────────────────────────────────────────────
print("\n[8] CLI Entrypoint")
res = subprocess.run(
    [sys.executable, str(SKILL_ROOT / "skills" / "sample_data_index.py"), "CAAAfrPart1"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
ck("CLI executes successfully", res.returncode == 0, f"code {res.returncode}")
ck("CLI output mentions CAAAfrPart1.CATPart", "CAAAfrPart1.CATPart" in res.stdout)
ck("CLI output mentions framework", "[CAAApplicationFrame]" in res.stdout)

# ── Summary ──────────────────────────────────────────────────────
print("\n" + "-" * 60)
print(f"  RESULT: {passed}/{total} passed")
print("=" * 60)

if passed != total:
    print(f"FAILED: {total - passed} checks failed", file=sys.stderr)
    sys.exit(1)

print("SAMPLE DATA ACCEPTANCE OK")
