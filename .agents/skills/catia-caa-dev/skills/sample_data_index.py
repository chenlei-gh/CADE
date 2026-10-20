"""
SampleDataIndex — CATIA Built-in Sample & Test Data Ground Truth
=================================================================
Provides fast lookup for sample CAD documents (.CATPart, .CATProduct,
.CATDrawing) that ship with CATIA (CAADoc test fixtures and win_b64/startup
catalog models).

Design boundary (governance):
  - Answers "what sample file can I open/test against for framework X or
    kind Y?", NOT "what features/geometry are inside this part?".
  - Does NOT attempt to parse proprietary binary V5_CFV2 files.
  - Returns absolute paths on the local machine when CATIA_INSTALL is known.

Usage:
  from sample_data_index import SampleDataIndex
  sdi = SampleDataIndex.load(skill_root)
  results = sdi.find_samples(framework="CAAApplicationFrame", kind="part")

CLI:
  python skills/sample_data_index.py CAAAfrPart
  python skills/sample_data_index.py --kind part --framework CAAMechanicalModeler
  python skills/sample_data_index.py --kind product --search screw
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

CACHE_STATS: Dict[str, int] = {"disk_hit": 0, "missing": 0, "rebuilt": 0}


class SampleDataIndex:
    """Cached index of sample and test models shipping with CATIA."""

    _PROC_CACHE: Dict[str, "SampleDataIndex"] = {}
    _PROC_CACHE_KEY: Dict[str, tuple] = {}

    def __init__(self):
        self.samples: List[dict] = []
        self.catia_install: str = ""
        self.meta: dict = {}
        self._by_kind: Dict[str, List[int]] = {}
        self._by_source: Dict[str, List[int]] = {}
        self._by_framework: Dict[str, List[int]] = {}
        self._by_category: Dict[str, List[int]] = {}
        self._name_map: Dict[str, List[int]] = {}
        self.total_count: int = 0
        self.part_count: int = 0
        self.product_count: int = 0
        self.drawing_count: int = 0
        self.framework_count: int = 0
        self._loaded: bool = False

    @classmethod
    def load(cls, skill_root: Path) -> "SampleDataIndex":
        """Load the sample data index from cache/sample_data_index.json.

        Cached per (skill_root, cache mtime + size). A missing cache
        yields a valid-but-empty index — callers get empty results, never
        an unhandled exception.
        """
        skill_root = Path(skill_root)
        cache = skill_root / "cache" / "sample_data_index.json"

        try:
            st = cache.stat()
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            CACHE_STATS["missing"] += 1
            sdi = cls()
            sdi._loaded = True
            return sdi

        key = str(skill_root.resolve())
        if cls._PROC_CACHE_KEY.get(key) == sig and key in cls._PROC_CACHE:
            CACHE_STATS["disk_hit"] += 1
            return cls._PROC_CACHE[key]

        sdi = cls()
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            sdi.meta = data.get("meta") or {}
            sdi.catia_install = sdi.meta.get("catia_install", "")
            sdi.samples = data.get("samples") or []
            sdi._by_kind = data.get("by_kind") or {}
            sdi._by_source = data.get("by_source") or {}
            sdi._by_framework = data.get("by_framework") or {}
            sdi._by_category = data.get("by_category") or {}

            sdi.total_count = len(sdi.samples)
            sdi.part_count = len(sdi._by_kind.get("part", []))
            sdi.product_count = len(sdi._by_kind.get("product", []))
            sdi.drawing_count = len(sdi._by_kind.get("drawing", []))
            sdi.framework_count = len(sdi._by_framework)

            # Build fast lowercase name lookup
            for idx, s in enumerate(sdi.samples):
                nm = s.get("name", "").lower()
                sdi._name_map.setdefault(nm, []).append(idx)

            sdi._loaded = True
            CACHE_STATS["rebuilt"] += 1
            cls._PROC_CACHE[key] = sdi
            cls._PROC_CACHE_KEY[key] = sig
            return sdi
        except Exception:
            CACHE_STATS["missing"] += 1
            sdi._loaded = True
            return sdi

    # ─── Query API ───────────────────────────────────────────────

    def find_samples(
        self,
        query: str = "",
        framework: str = "",
        kind: str = "",
        source: str = "",
        category: str = "",
        limit: int = 20,
    ) -> List[dict]:
        """Search for sample files matching filters.

        Args:
            query: Substring or keyword in file name, stem, or path.
            framework: CAA framework name (e.g. 'CAAApplicationFrame').
            kind: 'part', 'product', or 'drawing'.
            source: 'caadoc' or 'startup_catalog'.
            category: Subdirectory / category token.
            limit: Maximum items to return (default: 20).
        """
        if not self.samples:
            return []

        # Candidate pool based on highest-selectivity filter
        candidate_indices: Optional[Set[int]] = None

        if framework and self._by_framework:
            fw_matches = set()
            fw_lower = framework.lower()
            for fw, idxs in self._by_framework.items():
                if fw_lower in fw.lower():
                    fw_matches.update(idxs)
            candidate_indices = fw_matches

        if kind and kind in self._by_kind:
            kind_set = set(self._by_kind[kind])
            if candidate_indices is None:
                candidate_indices = kind_set
            else:
                candidate_indices &= kind_set

        if source and source in self._by_source:
            source_set = set(self._by_source[source])
            if candidate_indices is None:
                candidate_indices = source_set
            else:
                candidate_indices &= source_set

        if category and self._by_category:
            cat_matches = set()
            cat_lower = category.lower()
            for cat, idxs in self._by_category.items():
                if cat_lower in cat.lower():
                    cat_matches.update(idxs)
            if candidate_indices is None:
                candidate_indices = cat_matches
            else:
                candidate_indices &= cat_matches

        # If no categorical filter applied, consider all
        all_indices = candidate_indices if candidate_indices is not None else range(len(self.samples))

        query_lower = (query or "").strip().lower()
        results = []
        install_root = Path(self.catia_install) if self.catia_install else None

        for idx in all_indices:
            s = self.samples[idx]
            if query_lower:
                name_match = query_lower in s["name"].lower()
                stem_match = query_lower in s["stem"].lower()
                rel_match = query_lower in s["rel_path"].lower()
                if not (name_match or stem_match or rel_match):
                    continue

            # Format record with resolved local path
            rec = dict(s)
            if install_root:
                abs_p = install_root / s["rel_path"]
                rec["abs_path"] = str(abs_p)
                rec["exists"] = abs_p.is_file()
            else:
                rec["abs_path"] = ""
                rec["exists"] = False

            results.append(rec)
            if limit and len(results) >= limit:
                break

        return results

    def get_sample_by_name(self, name: str) -> Optional[dict]:
        """Find the first sample matching exact or case-insensitive filename."""
        hits = self._name_map.get(name.lower(), [])
        if not hits:
            return None
        s = self.samples[hits[0]]
        rec = dict(s)
        if self.catia_install:
            abs_p = Path(self.catia_install) / s["rel_path"]
            rec["abs_path"] = str(abs_p)
            rec["exists"] = abs_p.is_file()
        else:
            rec["abs_path"] = ""
            rec["exists"] = False
        return rec

    def list_frameworks(self) -> List[str]:
        """List all frameworks that provide sample models."""
        return sorted(self._by_framework.keys())

    def list_categories(self) -> List[str]:
        """List all categories / subdirectories in startup catalog."""
        return sorted(self._by_category.keys())


# ─── CLI Entrypoint ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Search CATIA built-in sample models (.CATPart, .CATProduct, .CATDrawing)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python skills/sample_data_index.py CAAAfrPart
  python skills/sample_data_index.py --kind part --framework CAAApplicationFrame
  python skills/sample_data_index.py --kind product --source caadoc
  python skills/sample_data_index.py --kind part --search screw --limit 5
""",
    )
    parser.add_argument("query", nargs="?", default="", help="Search query (name or path)")
    parser.add_argument("--kind", choices=["part", "product", "drawing"], help="Filter by document kind")
    parser.add_argument("--framework", help="Filter by CAA framework name (e.g. CAAApplicationFrame)")
    parser.add_argument("--source", choices=["caadoc", "startup_catalog"], help="Filter by origin source")
    parser.add_argument("--category", help="Filter by category / folder name")
    parser.add_argument("--limit", type=int, default=15, help="Max results to display (default: 15)")

    args = parser.parse_args()

    skill_root = Path(__file__).resolve().parent.parent
    sdi = SampleDataIndex.load(skill_root)

    if not sdi.total_count:
        print("WARN: SampleDataIndex is empty or cache/sample_data_index.json is missing.")
        print("Run: python tools/build_sample_data_index.py")
        sys.exit(1)

    hits = sdi.find_samples(
        query=args.query,
        framework=args.framework or "",
        kind=args.kind or "",
        source=args.source or "",
        category=args.category or "",
        limit=args.limit,
    )

    print(
        f"SampleDataIndex: {sdi.total_count} files indexed "
        f"({sdi.part_count} parts, {sdi.product_count} products, {sdi.drawing_count} drawings across {sdi.framework_count} frameworks)"
    )
    print(f"Query filters: query='{args.query}', kind='{args.kind or '*'}', framework='{args.framework or '*'}' -> {len(hits)} shown\n")

    if not hits:
        print("  (no matching sample data found)")
        return

    for i, h in enumerate(hits, 1):
        fw_tag = f"[{h['framework']}] " if h.get("framework") else ""
        sz_kb = h.get("size_bytes", 0) // 1024
        print(f"  {i}. {fw_tag}{h['name']} ({h['kind']}, {sz_kb} KB, {h['source']})")
        print(f"     Path: {h.get('abs_path') or h.get('rel_path')}")


if __name__ == "__main__":
    main()
