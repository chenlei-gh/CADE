"""
Retrieval — Unified Knowledge Access Layer
===========================================
Single entry point for CADE's retrieval indexes (catalog, API registry,
header map, method index). Exists for two reasons:

1. Correctness: every index is loaded at most once per process through
   get_retrieval(). Before this module, diagnostics.py re-called
   HeaderMap.load() per check and method_index re-loaded the header map
   for every unknown type in an inheritance walk.

2. Direction: callers should ask for a retrieval resource, not know
   which file implements it. This is the seam where capability-aware
   retrieval (find_capability) will plug in later — see
   docs/CAPABILITY_HISTORY.md for the capability-vs-file distinction.

Not a capability in capabilities.yaml terms: this is internal plumbing
shared by kernel/verifier/diagnostics, not a user-facing feature.

Usage:
  from retrieval import get_retrieval
  r = get_retrieval(skill_root)
  hm = r.header_map        # HeaderMap, loaded once per process
  mi = r.method_index      # MethodIndex (header_map injected)
  reg = r.registry         # ApiRegistry
  cat = r.catalog          # CatalogIndex
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Optional


class Retrieval:
    """Lazy, process-shared access to the skill's retrieval indexes."""

    def __init__(self, skill_root: Path):
        self._root = Path(skill_root)
        self._catalog = None
        self._registry = None
        self._header_map = None
        self._method_index = None

    @property
    def skill_root(self) -> Path:
        return self._root

    @property
    def catalog(self):
        if self._catalog is None:
            from catalog import CatalogIndex
            self._catalog = CatalogIndex.load(self._root)
        return self._catalog

    @property
    def registry(self):
        if self._registry is None:
            from api_registry import get_registry
            self._registry = get_registry(self._root)
        return self._registry

    @property
    def header_map(self):
        if self._header_map is None:
            from header_map import HeaderMap
            self._header_map = HeaderMap.load(self._root)
        return self._header_map

    @property
    def method_index(self):
        if self._method_index is None:
            from method_index import MethodIndex
            # Inject the shared HeaderMap so inheritance-chain walks do not
            # re-load it per unknown type.
            self._method_index = MethodIndex.load(
                self._root, header_map=self.header_map)
        return self._method_index

    # ─── Diagnostics ─────────────────────────────────────────────

    def health(self) -> dict:
        """Health report for all four indexes — Agent-facing diagnostics.

        Each index reports independently so one broken index cannot hide
        the state of the others. Top-level "ok" is True only when every
        index loaded with data. Run from CLI:
            python skills/retrieval.py
        """
        report: Dict[str, dict] = {}

        try:
            from catalog import CatalogIndex
            cat = self.catalog
            report["catalog"] = {
                "ok": len(cat.entries) > 0,
                "entries": len(cat.entries),
                "aliases": len(cat.aliases),
                "cache": dict(CatalogIndex.CACHE_STATS),
            }
        except Exception as e:
            report["catalog"] = {"ok": False, "error": str(e)}

        try:
            import method_index as _mix
            mi = self.method_index
            report["method_index"] = {
                "ok": mi.type_count > 0,
                "types": mi.type_count,
                "cache": dict(_mix.CACHE_STATS),
            }
        except Exception as e:
            report["method_index"] = {"ok": False, "error": str(e)}

        try:
            from header_map import HeaderMap
            hm = self.header_map
            report["header_map"] = {
                "ok": hm.header_count > 0,
                "headers": hm.header_count,
                "frameworks": hm.framework_count,
                "proc_cached": str(self._root.resolve()) in HeaderMap._PROC_CACHE,
            }
        except Exception as e:
            report["header_map"] = {"ok": False, "error": str(e)}

        try:
            reg = self.registry
            report["api_registry"] = {
                "ok": len(reg.apis) > 0,
                "apis": len(reg.apis),
                "headers": len(reg.headers),
                "sources": reg.stats().get("sources", {}),
            }
        except Exception as e:
            report["api_registry"] = {"ok": False, "error": str(e)}

        report["ok"] = all(v.get("ok") for v in report.values())
        return report


# ─── Process-wide singleton ──────────────────────────────────────

_CACHE: "Dict[str, Retrieval]" = {}


def get_retrieval(skill_root: Optional[Path] = None) -> Retrieval:
    """One Retrieval per skill_root per process."""
    if skill_root is None:
        skill_root = Path(__file__).resolve().parent.parent
    key = str(Path(skill_root).resolve())
    if key not in _CACHE:
        _CACHE[key] = Retrieval(Path(skill_root))
    return _CACHE[key]


if __name__ == "__main__":
    import json
    print(json.dumps(get_retrieval().health(), indent=2, ensure_ascii=False))
