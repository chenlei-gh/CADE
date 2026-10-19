"""
Shipped .dic Index — Interface/Component Ground Truth
=====================================================
Answers "does this CAA name really exist in the shipped product?" using the
TIE dictionary that CATIA generates at build time for every delivered
framework.

Why this exists
---------------
The retrieval fan-out (catalog / HeaderMap / MethodIndex) can all come back
empty for a name that genuinely ships with CATIA. The canonical example is
the scene API: ``CATIAScene`` is real (``OSMInterfaces``) but it is an
automation (IDL) interface published only under
``OSMInterfaces/PublicGenerated/win_b64`` — so HeaderMap never indexes it and
CAADoc refman never documents it. Before this index existed, ``analyze()``
answered "Knowledge base searched" with an empty result set, which is
indistinguishable from "this API does not exist". The agent then walked the
SDK by hand.

Data source (read-only, no rescanning)
--------------------------------------
``cache/caadoc_index.json`` → ``sdk_dic_entries`` (component, interface,
library, file), the same schema-2 cache that MethodIndex already consumes.
Roughly 73k component→interface pairs across ~885 shipped .dic files.

Query semantics
---------------
The index answers existence and attribution only. It deliberately does NOT
answer "how do I call it" — that stays with MethodIndex / HeaderMap /
CAADoc. A hit here means "the name is real and these components implement
it", not "you have a public C++ header for it".

CLI (for AI agents — never grep the dictionary by hand):

    python skills/dic_index.py CATIAScene
    python skills/dic_index.py --component CATNewSceneFeat
    python skills/dic_index.py --stats
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# Observability counters (same rationale as catalog.CACHE_STATS /
# method_index.CACHE_STATS).
CACHE_STATS: Dict[str, int] = {"disk_hit": 0, "missing": 0, "rebuilt": 0}


class DicIndex:
    """Cached interface ↔ component map built from the shipped .dic files."""

    _PROC_CACHE: Dict[str, "DicIndex"] = {}
    _PROC_CACHE_KEY: Dict[str, tuple] = {}

    def __init__(self):
        # interface → {component names}
        self._by_interface: Dict[str, set] = defaultdict(set)
        # component → {interface names}
        self._by_component: Dict[str, set] = defaultdict(set)
        # interface → first library seen (informational only; a single
        # interface can be implemented by several libraries)
        self._lib_by_interface: Dict[str, str] = {}
        self.interface_count = 0
        self.component_count = 0
        self.pair_count = 0
        self.source_version = ""
        self._loaded = False

    # ─── Loading ─────────────────────────────────────────────────

    @classmethod
    def load(cls, skill_root: Path) -> "DicIndex":
        """Load the .dic map from cache/caadoc_index.json.

        Cached per (skill_root, cache mtime + size) so a rebuilt index is
        picked up without restarting the process. A missing or unreadable
        cache yields a valid-but-empty index — callers get "not found",
        never an exception, matching the other retrieval indexes.
        """
        skill_root = Path(skill_root)
        cache = skill_root / "cache" / "caadoc_index.json"

        try:
            st = cache.stat()
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            CACHE_STATS["missing"] += 1
            di = cls()
            di._loaded = True
            return di

        key = str(skill_root.resolve())
        if cls._PROC_CACHE_KEY.get(key) == sig and key in cls._PROC_CACHE:
            CACHE_STATS["disk_hit"] += 1
            return cls._PROC_CACHE[key]

        di = cls()
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            di.source_version = (data.get("meta") or {}).get("source_version", "")
            for rec in data.get("sdk_dic_entries", []):
                iface = rec.get("interface")
                comp = rec.get("component")
                if not iface or not comp:
                    continue
                di._by_interface[iface].add(comp)
                di._by_component[comp].add(iface)
                if iface not in di._lib_by_interface and rec.get("library"):
                    di._lib_by_interface[iface] = rec["library"]
                di.pair_count += 1
            di.interface_count = len(di._by_interface)
            di.component_count = len(di._by_component)
            CACHE_STATS["rebuilt"] += 1
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("caadoc_index.json unreadable for DicIndex: %s", e)
            di = cls()

        di._loaded = True
        cls._PROC_CACHE[key] = di
        cls._PROC_CACHE_KEY[key] = sig
        return di

    # ─── Queries ─────────────────────────────────────────────────

    def is_interface(self, name: str) -> bool:
        return name in self._by_interface

    def is_component(self, name: str) -> bool:
        return name in self._by_component

    def implementers_of(self, interface: str) -> List[str]:
        """Components that declare implementation of `interface`."""
        return sorted(self._by_interface.get(interface, ()))

    def interfaces_of(self, component: str) -> List[str]:
        """Interfaces that `component` declares implementing."""
        return sorted(self._by_component.get(component, ()))

    def library_of(self, interface: str) -> str:
        """Library that ships the interface, when the .dic records one."""
        return self._lib_by_interface.get(interface, "")

    def resolve_name(self, name: str) -> dict:
        """Classify a bare identifier against the shipped dictionary.

        Returns a dict describing every way the name is known, so callers
        can tell the four cases apart instead of collapsing them into a
        boolean:

          interface_only_known  — name exists; these components implement it
          component_known       — name exists; these interfaces it implements
          known=False           — the name is not in any shipped .dic
        """
        implementers = self.implementers_of(name)
        interfaces = self.interfaces_of(name)
        return {
            "name": name,
            "known": bool(implementers or interfaces),
            "as_interface": {
                "implemented_by": implementers,
                "library": self.library_of(name),
            } if implementers else None,
            "as_component": {
                "implements": interfaces,
            } if interfaces else None,
        }


# ─── CLI ─────────────────────────────────────────────────────────

def _cli(argv: List[str]) -> int:
    skill_root = Path(__file__).resolve().parent.parent
    di = DicIndex.load(skill_root)

    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]

    if "--stats" in flags:
        print(
            f"interfaces={di.interface_count} components={di.component_count} "
            f"pairs={di.pair_count} version={di.source_version or '?'}"
        )
        return 0

    if not args:
        print("usage: dic_index.py <InterfaceOrComponent> [...]")
        print("       dic_index.py --component <Component> [...]")
        print("       dic_index.py --stats")
        return 2

    as_component = "--component" in flags
    rc = 0
    for name in args:
        if as_component:
            ifaces = di.interfaces_of(name)
            if ifaces:
                print(f"{name}  COMPONENT  implements {len(ifaces)} interfaces")
                for i in ifaces:
                    print(f"  - {i}")
            else:
                print(f"{name}  NOT-FOUND (no shipped component emits this name)")
                rc = 1
            continue

        res = di.resolve_name(name)
        if not res["known"]:
            print(f"{name}  NOT-FOUND (absent from every shipped .dic)")
            rc = 1
            continue
        if res["as_interface"]:
            impls = res["as_interface"]["implemented_by"]
            lib = res["as_interface"]["library"]
            lib_txt = f" lib={lib}" if lib else ""
            print(f"{name}  INTERFACE  implemented by {len(impls)} component(s){lib_txt}")
            for c in impls[:40]:
                print(f"  - {c}")
            if len(impls) > 40:
                print(f"  ... ({len(impls) - 40} more)")
        if res["as_component"]:
            ifaces = res["as_component"]["implements"]
            print(f"{name}  COMPONENT  implements {len(ifaces)} interface(s)")
            for i in ifaces[:20]:
                print(f"  - {i}")
            if len(ifaces) > 20:
                print(f"  ... ({len(ifaces) - 20} more)")
    return rc


if __name__ == "__main__":
    import sys
    sys.exit(_cli(sys.argv[1:]))
