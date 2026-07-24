"""
CAA Method Index — Type-aware Method Existence Check
=====================================================
Answers "does type X really have method M?" for the static verifier,
so fabricated calls like ``spCont->GetAllChildren()`` on a
``CATIContainer_var`` are caught before compile (GetAllChildren exists
— but only on CATIProduct / CATIParmPublisher, not CATIContainer).

Data sources (read-only, no rescanning):
  1. cache/caadoc_index.json  — per-class method lists parsed from the
     real SDK headers by tools/build_caadoc_index.py (authoritative).
  2. SDK headers (via header_map paths) — parsed lazily, ONLY for base-
     class declarations, to walk the inheritance chain
     (e.g. CATIProduct → CATBaseUnknown). Results are memoized.

Two-layer verdict:
  - method found on type or any ancestor        → OK
  - method NOT found, and method exists on some
    other CAA type                              → warning (likely wrong
    receiver — the CATIContainer/GetAllChildren case)
  - method not found anywhere in the SDK        → warning (likely
    fabricated outright)

CLI:
  python skills/method_index.py CATIContainer GetAllChildren ListMembersHere
      → CATIContainer::GetAllChildren  NOT-FOUND  (exists on: CATIProduct, ...)
      → CATIContainer::ListMembersHere  OK
"""

from __future__ import annotations

import json
import re
import sys
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Optional, Set


# Base-class declaration:  class ExportedByX CATIProduct : public CATBaseUnknown {
_BASE_RE = re.compile(
    r"class\s+(?:ExportedBy\w+\s+)?(\w+)\s*:\s*public\s+(\w+)",
)
# Methods every COM-managed object has (from CATBaseUnknown root or _var
# semantics) — skip checks rather than resolve the full root chain.
_UNIVERSAL_METHODS = {
    "AddRef", "Release", "QueryInterface", "IsATypeOf", "GetType",
    "GetName", "GetId", "GetFather", "GetReference",
}
_MAX_ANCESTOR_DEPTH = 8


class MethodIndex:
    """Cached type → methods (own + inherited) lookup."""

    def __init__(self):
        self._methods: Dict[str, Set[str]] = {}   # type → bare method names
        self._bases: Dict[str, str] = {}          # type → direct base class
        self._catia_install = ""
        self._loaded = False

    # ─── Loading ─────────────────────────────────────────────────

    @classmethod
    def load(cls, skill_root: Path) -> "MethodIndex":
        mi = cls()
        skill_root = Path(skill_root)

        # 1. Method tables from the caadoc index cache (SDK header source)
        cache = skill_root / "cache" / "caadoc_index.json"
        if cache.is_file():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                for rec in data.get("header_classes", []):
                    names = {m.split("(", 1)[0].strip()
                             for m in rec.get("methods", [])}
                    if names:
                        mi._methods.setdefault(rec["name"], set()).update(names)
            except (json.JSONDecodeError, OSError):
                pass

        # 2. CATIA_INSTALL for lazy base-class header parsing
        try:
            sys.path.insert(0, str(skill_root / "skills"))
            from env import CAAEnvironment
            env = CAAEnvironment()
            env.load_config()
            mi._catia_install = env.config.get("CATIA_INSTALL", "")
        except Exception:
            pass

        mi._loaded = True
        return mi

    @property
    def type_count(self) -> int:
        return len(self._methods)

    # ─── Queries ─────────────────────────────────────────────────

    def has_type(self, type_name: str) -> bool:
        return type_name in self._methods

    def method_exists(self, type_name: str, method: str) -> Optional[bool]:
        """True if method is callable on type (own or inherited).

        Returns None when the type is unknown (can't judge).
        """
        if not self.has_type(type_name):
            return None
        if method in _UNIVERSAL_METHODS:
            return True
        visited: Set[str] = set()
        current: Optional[str] = type_name
        depth = 0
        while current and current not in visited and depth < _MAX_ANCESTOR_DEPTH:
            visited.add(current)
            if method in self._methods.get(current, ()):
                return True
            current = self._base_of(current)
            depth += 1
        return False

    def owners_of(self, method: str, limit: int = 5) -> List[str]:
        """Which known types declare this method (for hints)."""
        owners = [t for t, ms in self._methods.items() if method in ms]
        return sorted(owners)[:limit]

    def suggest_on(self, type_name: str, method: str, n: int = 3) -> List[str]:
        """Closest real methods on this type (typo correction)."""
        pool: Set[str] = set()
        visited: Set[str] = set()
        current: Optional[str] = type_name
        depth = 0
        while current and current not in visited and depth < _MAX_ANCESTOR_DEPTH:
            visited.add(current)
            pool.update(self._methods.get(current, ()))
            current = self._base_of(current)
            depth += 1
        return get_close_matches(method, sorted(pool), n=n, cutoff=0.65)

    # ─── Inheritance (lazy header parsing) ───────────────────────

    def _base_of(self, type_name: str) -> Optional[str]:
        if type_name in self._bases:
            return self._bases[type_name] or None
        base = self._parse_base(type_name)
        self._bases[type_name] = base or ""
        return base

    def _parse_base(self, type_name: str) -> Optional[str]:
        """Find 'class X : public Y' in the type's SDK header."""
        if not self._catia_install:
            return None
        try:
            from header_map import HeaderMap
            hm = HeaderMap.load(Path(self._catia_install).parent if False else
                                Path(__file__).resolve().parent.parent)
            entry = hm.lookup(type_name)
        except Exception:
            return None
        if not entry:
            return None
        _, fw = entry
        root = Path(self._catia_install) / fw
        for hdr in (root / "PublicInterfaces" / f"{type_name}.h",
                    root / "CNext" / "public" / "interfaces" / f"{type_name}.h"):
            if not hdr.exists():
                continue
            try:
                text = hdr.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            m = _BASE_RE.search(text)
            if m and m.group(1) == type_name:
                return m.group(2)
        return None


# ─── CLI ─────────────────────────────────────────────────────────

def _cli(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip())
        return 0
    type_name = argv[0]
    methods = argv[1:]

    skill_root = Path(__file__).resolve().parent.parent
    mi = MethodIndex.load(skill_root)

    if not mi.has_type(type_name):
        print(f"{type_name}  UNKNOWN-TYPE (not in SDK header index)")
        return 1

    rc = 0
    for meth in methods:
        meth = meth.rstrip("(").strip()
        ok = mi.method_exists(type_name, meth)
        if ok:
            print(f"{type_name}::{meth}  OK")
        else:
            rc = 1
            owners = mi.owners_of(meth)
            sugg = mi.suggest_on(type_name, meth)
            parts = [f"{type_name}::{meth}  NOT-FOUND"]
            if sugg:
                parts.append(f"did-you-mean-on-this-type: {', '.join(sugg)}")
            if owners:
                parts.append(f"exists-on: {', '.join(owners)}")
            print("  ".join(parts))
    return rc


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
