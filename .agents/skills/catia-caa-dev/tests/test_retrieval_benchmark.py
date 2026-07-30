#!/usr/bin/env python3
"""
Retrieval Benchmark & Health
=============================
Regression tripwire for the retrieval layer: cold/warm load timings,
disk-cache engagement, and the Retrieval.health() report.

Why this exists: the catalog disk cache was silently broken for months
(a NameError swallowed by a broad except) and nobody noticed until a
manual audit. Timing bounds below are >=10x the observed values — this
suite guards against silent regressions, it is NOT a performance gate.
"""

import sys, time, json
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
print("  Retrieval Benchmark & Health")
print("=" * 60)

timings = {}

# ═══════════════════════════════════════════════════════════════
# [1] Cold load per index (process caches cleared)
# ═══════════════════════════════════════════════════════════════
print("\n[1] Cold load per index")
from catalog import CatalogIndex
from header_map import HeaderMap
import method_index as _mix
from api_registry import ApiRegistry

CatalogIndex._PROC_CACHE.clear(); CatalogIndex._PROC_CACHE_MTIME.clear()
HeaderMap._PROC_CACHE.clear(); HeaderMap._PROC_CACHE_MTIME.clear()
CatalogIndex.reset_stats()

t0 = time.perf_counter(); _cat = CatalogIndex.load(SKILL)
timings["catalog"] = (time.perf_counter() - t0) * 1000
ck("catalog cold load < 500ms", timings["catalog"] < 500,
   f"{timings['catalog']:.1f}ms")

t0 = time.perf_counter(); _hm = HeaderMap.load(SKILL)
timings["header_map"] = (time.perf_counter() - t0) * 1000
ck("header_map cold load < 1000ms", timings["header_map"] < 1000,
   f"{timings['header_map']:.1f}ms")

t0 = time.perf_counter(); _mi = _mix.MethodIndex.load(SKILL)
timings["method_index"] = (time.perf_counter() - t0) * 1000
ck("method_index cold load < 2000ms", timings["method_index"] < 2000,
   f"{timings['method_index']:.1f}ms")

t0 = time.perf_counter(); _reg = ApiRegistry.load(SKILL)
timings["api_registry"] = (time.perf_counter() - t0) * 1000
ck("api_registry cold load < 1000ms", timings["api_registry"] < 1000,
   f"{timings['api_registry']:.1f}ms")

# ═══════════════════════════════════════════════════════════════
# [2] Disk caches engage on second process load
# ═══════════════════════════════════════════════════════════════
print("\n[2] Disk caches engage")
CatalogIndex._PROC_CACHE.clear(); CatalogIndex._PROC_CACHE_MTIME.clear()
CatalogIndex.reset_stats()
_cat2 = CatalogIndex.load(SKILL)
ck("catalog disk cache hit", CatalogIndex.CACHE_STATS["disk_hit"] >= 1,
   str(CatalogIndex.CACHE_STATS))

_mix.CACHE_STATS["disk_hit"] = 0
_mi2 = _mix.MethodIndex.load(SKILL)
ck("method_index disk cache hit", _mix.CACHE_STATS["disk_hit"] == 1,
   str(_mix.CACHE_STATS))
ck("method_index pickle matches source data", _mi2._methods == _mi._methods)

ck("catalog pickle exists", (SKILL / "cache" / "catalog_index.pickle").exists())
ck("method_index pickle exists", (SKILL / "cache" / "method_index.pickle").exists())

# ═══════════════════════════════════════════════════════════════
# [3] Warm access via the retrieval facade
# ═══════════════════════════════════════════════════════════════
print("\n[3] Warm access via retrieval facade")
from retrieval import get_retrieval
_r = get_retrieval(SKILL)
t0 = time.perf_counter()
_ = (_r.catalog, _r.header_map, _r.method_index, _r.registry)
timings["facade_warm"] = (time.perf_counter() - t0) * 1000
ck("facade warm access < 200ms", timings["facade_warm"] < 200,
   f"{timings['facade_warm']:.1f}ms")
ck("facade shares instances across calls",
   get_retrieval(SKILL).header_map is _r.header_map)

# ═══════════════════════════════════════════════════════════════
# [4] health() report complete and ok
# ═══════════════════════════════════════════════════════════════
print("\n[4] Retrieval health report")
_h = _r.health()
for name in ("catalog", "method_index", "header_map", "api_registry"):
    ck(f"health includes {name}", name in _h and _h[name].get("ok") is True)
ck("health top-level ok", _h.get("ok") is True)
ck("catalog non-empty", _h["catalog"]["entries"] > 0,
   f"{_h['catalog']['entries']} entries")
ck("method_index non-empty", _h["method_index"]["types"] > 0,
   f"{_h['method_index']['types']} types")
ck("header_map non-empty", _h["header_map"]["headers"] > 0,
   f"{_h['header_map']['headers']} headers")
ck("api_registry non-empty", _h["api_registry"]["apis"] > 0,
   f"{_h['api_registry']['apis']} apis")

# ═══════════════════════════════════════════════════════════════
# [5] Catalog coverage: every knowledge/pattern/playbook/capability
#     markdown file must be reachable via CatalogIndex.entries.
#     Why: knowledge/frameworks/*.md (148 files) went unindexed for
#     months because index.yaml only recorded a file count, not real
#     table rows — this guards against that class of silent gap.
# ═══════════════════════════════════════════════════════════════
print("\n[5] Catalog coverage vs. disk")
indexed_files = {e.file for e in _cat.entries if e.file}
missing = []
for sub in ("knowledge", "patterns", "playbooks", "capabilities"):
    d = SKILL / sub
    if not d.is_dir():
        continue
    for p in d.rglob("*.md"):
        if p.name == "README.md":
            continue
        rel = p.relative_to(SKILL).as_posix()
        if rel not in indexed_files:
            missing.append(rel)

ck("all knowledge/pattern/playbook/capability .md files are indexed",
   len(missing) == 0,
   f"{len(missing)} missing" + (f": {missing[:5]}" if missing else ""))

print("\n-- health JSON --")
print(json.dumps(_h, indent=2, ensure_ascii=False))

print("\n-- timings (ms) --")
for k, v in timings.items():
    print(f"  {k:16s} {v:8.1f}")

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
