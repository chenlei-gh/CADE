"""
Retrieval — Unified Knowledge Access Layer
===========================================
Single entry point for CADE's retrieval indexes (catalog, API registry,
header map, method index, use case index, shipped .dic index, sample data index). Exists for
two reasons:

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
  dic = r.dic_index        # DicIndex (shipped .dic ground truth)
  sdi = r.sample_data_index # SampleDataIndex (shipped sample models)
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
        self._usecase_index = None
        self._dic_index = None
        self._sample_data_index = None
        self._chain_explorer = None

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

    @property
    def dic_index(self):
        """Shipped .dic interface ↔ component ground truth.

        Answers "does this name ship at all?" for names HeaderMap never sees
        (automation/IDL interfaces such as CATIAScene under PublicGenerated).
        Loaded lazily; a missing cache yields an empty index, not an error.
        """
        if self._dic_index is None:
            from dic_index import DicIndex
            self._dic_index = DicIndex.load(self._root)
        return self._dic_index

    @property
    def sample_data_index(self):
        """Shipped sample CAD models (.CATPart, .CATProduct, .CATDrawing).

        Answers "what sample file can I open/test against?" without guessing.
        Loaded lazily; missing cache yields an empty index.
        """
        if self._sample_data_index is None:
            from sample_data_index import SampleDataIndex
            self._sample_data_index = SampleDataIndex.load(self._root)
        return self._sample_data_index

    def find_sample_data(
        self,
        query: str = "",
        framework: str = "",
        kind: str = "",
        source: str = "",
        category: str = "",
        limit: int = 20,
    ) -> list:
        """Find sample models (.CATPart, .CATProduct, .CATDrawing)."""
        return self.sample_data_index.find_samples(
            query=query,
            framework=framework,
            kind=kind,
            source=source,
            category=category,
            limit=limit,
        )

    @property
    def usecase_index(self) -> dict:
        """Lazy-load cache/usecase_index.json (Official Example Presence).

        Read-only presence evidence: WHERE a token appears in CAADoc
        use cases. Ownership/recommendation are NOT stored here — join
        with method_index.owners_of() at query time.
        """
        if self._usecase_index is None:
            import json
            p = self._root / "cache" / "usecase_index.json"
            if p.exists():
                self._usecase_index = json.loads(p.read_text(encoding="utf-8"))
            else:
                self._usecase_index = {"examples": {}, "by_interface": {},
                                       "by_method": {}, "by_symbol": {}}
        return self._usecase_index

    # ─── UseCase presence queries (passive, on-demand) ───────────

    def find_usecases_for_interface(self, interface: str) -> list:
        """Official CAADoc examples that #include this interface. [] if none."""
        return self.usecase_index.get("by_interface", {}).get(interface, [])

    def find_usecases_for_method(self, method: str) -> dict:
        """Official examples calling this method + ownership join.

        Returns {"owners": [...], "examples": [...]}. owners comes from
        MethodIndex (authority), examples from UseCaseIndex (presence).
        Empty examples = no official example found (not an error).
        """
        owners = self.method_index.owners_of(method)
        examples = self.usecase_index.get("by_method", {}).get(method, [])
        return {"owners": owners, "examples": examples}

    @property
    def chain_explorer(self):
        """Official use case sequential call chain explorer."""
        if self._chain_explorer is None:
            from chain_explorer import ChainExplorer
            self._chain_explorer = ChainExplorer(self._root, retrieval=self)
        return self._chain_explorer

    def explore_chain(
        self,
        start: str = "",
        target: str = "",
        query: str = "",
        max_candidates: int = 3,
    ) -> dict:
        """Explores grounded official calling sequences for unknown requirements."""
        return self.chain_explorer.explore(
            start=start, target=target, query=query, max_candidates=max_candidates
        )

    # ─── Diagnostics ─────────────────────────────────────────────

    def health(self) -> dict:
        """Health report for all five indexes — Agent-facing diagnostics.

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

        try:
            uc = self.usecase_index
            n_ex = len(uc.get("examples", {}))
            report["usecase_index"] = {
                "ok": n_ex > 0,
                "examples": n_ex,
                "interfaces": len(uc.get("by_interface", {})),
                "methods": len(uc.get("by_method", {})),
                "resources": len(uc.get("resources", {})),
            }
        except Exception as e:
            report["usecase_index"] = {"ok": False, "error": str(e)}

        try:
            import dic_index as _dic
            di = self.dic_index
            report["dic_index"] = {
                "ok": di.pair_count > 0,
                "interfaces": di.interface_count,
                "components": di.component_count,
                "pairs": di.pair_count,
                "version": di.source_version,
                "cache": dict(_dic.CACHE_STATS),
            }
        except Exception as e:
            report["dic_index"] = {"ok": False, "error": str(e)}

        try:
            import sample_data_index as _sdi
            sdi = self.sample_data_index
            report["sample_data_index"] = {
                "ok": sdi.total_count > 0,
                "total": sdi.total_count,
                "parts": sdi.part_count,
                "products": sdi.product_count,
                "drawings": sdi.drawing_count,
                "frameworks": sdi.framework_count,
                "cache": dict(_sdi.CACHE_STATS),
            }
        except Exception as e:
            report["sample_data_index"] = {"ok": False, "error": str(e)}

        # Core indexes determine primary retrieval health
        core_indexes = [
            "catalog", "method_index", "header_map", "api_registry",
            "usecase_index", "dic_index", "sample_data_index"
        ]
        report["core_ok"] = all(report.get(k, {}).get("ok", False) for k in core_indexes)

        # Chain explorer is an optional analytical extension
        try:
            ce = self.chain_explorer
            has_root = ce.caadoc_root is not None
            report["chain_explorer"] = {
                "ok": has_root,
                "status": "ready" if has_root else "degraded",
                "caadoc_root": str(ce.caadoc_root) if ce.caadoc_root else None,
                "note": "Optional source-grounded chain discovery extension."
            }
        except Exception as e:
            report["chain_explorer"] = {
                "ok": False,
                "status": "unavailable",
                "error": str(e),
                "note": "Optional source-grounded chain discovery extension."
            }

        # Overall retrieval health reflects core authority indexes
        report["ok"] = report["core_ok"]
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
