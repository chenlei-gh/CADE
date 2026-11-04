"""Resolve a requirement entity into a real CATIA late type.

Why this exists
---------------
``TypedRequirement.target_entity`` is a requirement-side classification
(``feature`` / ``document`` / ``component`` / ``workbench``). It is NOT a
CATIA late type. A late type is the component name that the CATIA dictionary
can bind an extension to, i.e. the fourth argument of
``CATImplementClass(<Ext>, DataExtension, <Adapter>, <LateType>)`` and the
first token of a ``.dico`` line.

Before this module existed the planner forwarded ``target_entity`` straight
into both places, which produces registrations for a component named
``feature`` — a name no CATIA dictionary contains.

What this module does (and does not)
------------------------------------
It answers two questions against read-only local evidence:

1. "Is this identifier a component that really exists?" — checked against
   the shipped ``.dic`` index (``sdk_dic_entries`` in
   ``cache/caadoc_index.json``, ~14.8k components) and the CAADoc sample
   dictionary entries (``dico_entries``, the developer-authored ``.dico``
   files shipped in ``CAADoc``).
2. "Which real components could serve as the extension target?" — returned as
   a bounded candidate list when the answer is not unique.

It deliberately does NOT contain an entity→late-type table. Inventing
``feature -> CATPart`` or ``feature -> Pad`` would replace one fabricated
registration with another. When the evidence does not pin down a single
component, the result is AMBIGUOUS/UNKNOWN and generation must stop until the
caller names a real type.

Data sources (read-only, already cached)
----------------------------------------
``cache/caadoc_index.json`` → ``sdk_dic_entries`` (shipped) and
``dico_entries`` (CAADoc samples). Same schema-2 cache that ``DicIndex`` and
``MethodIndex`` already consume; nothing is rescanned here.

CLI (for agents):

    python skills/late_type_resolver.py CAAMmrMeasureSet
    python skills/late_type_resolver.py --candidates CATI3DGeoVisu
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from dic_index import DicIndex

logger = logging.getLogger(__name__)

# Bounded so a clarification prompt stays readable.
MAX_CANDIDATES = 8

# Tokens that look like identifiers but are CAA vocabulary, not components.
_NON_COMPONENT_TOKENS = frozenset(
    {
        "CATIVisu",
        "CATI3DGeoVisu",
        "CATExtIVisu",
        "CATIModelEvents",
        "CATIEventSubscriber",
        "CATIValue",
        "CATIParmPublisher",
        "CATISpecObject",
        "CATCommand",
        "CATDlgDialog",
        "CATBaseUnknown",
        "CATRep",
        "CAT3DBagRep",
        "TIE_CATI3DGeoVisu",
    }
)

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CAMEL = re.compile(r"^[A-Z][A-Za-z0-9_]{2,}$")


class _SampleDictionary:
    """CAADoc ``.dico`` component/interface pairs (developer samples)."""

    __slots__ = ("by_component", "by_interface", "components")

    def __init__(self) -> None:
        self.by_component: Dict[str, Set[str]] = {}
        self.by_interface: Dict[str, Set[str]] = {}
        self.components: Set[str] = set()

    @classmethod
    def load(cls, skill_root: Path) -> "_SampleDictionary":
        data = _read_caadoc_index(skill_root)
        sample = cls()
        for entry in data.get("dico_entries") or []:
            comp = entry.get("component")
            iface = entry.get("interface")
            if not comp:
                continue
            sample.components.add(comp)
            if iface:
                sample.by_component.setdefault(comp, set()).add(iface)
                sample.by_interface.setdefault(iface, set()).add(comp)
        return sample


_CAADOC_CACHE: Dict[str, dict] = {}


def _read_caadoc_index(skill_root: Path) -> dict:
    """Load ``cache/caadoc_index.json`` once per (path, mtime, size)."""
    cache_path = Path(skill_root) / "cache" / "caadoc_index.json"
    try:
        stat = cache_path.stat()
        signature = f"{cache_path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}"
    except OSError:
        return {}
    if signature in _CAADOC_CACHE:
        return _CAADOC_CACHE[signature]
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("caadoc_index.json unreadable for LateTypeResolver: %s", exc)
        data = {}
    _CAADOC_CACHE.clear()
    _CAADOC_CACHE[signature] = data
    return data


class LateTypeResolver:
    """Verifies identifiers against the shipped dictionary and CAADoc samples."""

    def __init__(self, skill_root: Optional[Path] = None):
        self.skill_root = Path(skill_root) if skill_root else Path(__file__).resolve().parent.parent
        self._dic = None
        self._sample = None

    # ─── Loading ────────────────────────────────────────────────

    @property
    def dic(self) -> DicIndex:
        if self._dic is None:
            self._dic = DicIndex.load(self.skill_root)
        return self._dic

    @property
    def sample(self) -> _SampleDictionary:
        if self._sample is None:
            self._sample = _SampleDictionary.load(self.skill_root)
        return self._sample

    @property
    def available(self) -> bool:
        """True when at least one real dictionary could be read."""
        return bool(self.dic.component_count or self.sample.components)

    # ─── Queries ────────────────────────────────────────────────

    def is_known_late_type(self, name: str) -> bool:
        """True when `name` is a component that exists in local evidence."""
        if not name or not _IDENT.match(str(name)):
            return False
        name = str(name)
        if name in _NON_COMPONENT_TOKENS:
            return False
        return bool(self.dic.is_component(name) or name in self.sample.components)

    def describe(self, name: str) -> dict:
        """Evidence trail for one identifier."""
        name = str(name or "")
        in_shipped = bool(name) and self.dic.is_component(name)
        in_samples = name in (self.sample.components if name else set())
        interfaces: List[str] = []
        if in_shipped:
            interfaces.extend(self.dic.interfaces_of(name))
        if in_samples:
            for iface in sorted(self.sample.by_component.get(name, ())):
                if iface not in interfaces:
                    interfaces.append(iface)
        return {
            "name": name,
            "is_late_type": bool(in_shipped or in_samples),
            "in_shipped_dic": in_shipped,
            "in_caadoc_samples": in_samples,
            "interfaces": sorted(interfaces),
        }

    def candidates_for_interface(self, interface: str, limit: int = MAX_CANDIDATES) -> List[str]:
        """Real components that already implement `interface` in local evidence.

        CAADoc samples come first: those are the types whose extension recipe
        an example actually demonstrates. Shipped components follow. The list
        is deterministic and bounded; it is a clarification aid, never an
        automatic choice.
        """
        if not interface:
            return []
        sample_hits = sorted(self.sample.by_interface.get(interface, ()))
        shipped_hits = self.dic.implementers_of(interface)
        ordered: List[str] = []
        for name in sample_hits + shipped_hits:
            if name not in ordered:
                ordered.append(name)
            if len(ordered) >= limit:
                break
        return ordered

    def explicit_components_in(self, text: str, exclude: Iterable[str] = ()) -> List[str]:
        """CamelCase tokens in `text` that resolve to a real component."""
        blocked = {str(item) for item in (exclude or ()) if item}
        found: List[str] = []
        for token in re.split(r"[^A-Za-z0-9_]+", text or ""):
            if not token or token in blocked or not _CAMEL.match(token):
                continue
            if token in _NON_COMPONENT_TOKENS:
                continue
            if self.is_known_late_type(token) and token not in found:
                found.append(token)
        return found

    # ─── Resolution ─────────────────────────────────────────────

    def resolve(
        self,
        request: str = "",
        entity: str = "unknown",
        interfaces: Optional[Iterable[str]] = None,
        exclude: Iterable[str] = (),
    ) -> dict:
        """Resolve the extension target late type.

        Returns ``{status, late_type, candidates, reason, evidence}`` with
        ``status in {"CLEAR", "AMBIGUOUS", "UNKNOWN"}``. Only CLEAR carries a
        late_type. Anything else must block generation.
        """
        iface_list = [str(i) for i in (interfaces or []) if i]
        # Prefer the interface that actually lands in the dictionary: an
        # extension requests CATIVisu but is registered as CATI3DGeoVisu.
        primary_interface = next(
            (i for i in ("CATI3DGeoVisu", "CATIVisu") if i in iface_list),
            iface_list[0] if iface_list else "",
        )
        evidence = {
            "entity_category": entity,
            "primary_interface": primary_interface,
            "dictionary_available": self.available,
            "shipped_components": self.dic.component_count,
            "caadoc_sample_components": len(self.sample.components),
        }

        if not self.available:
            return {
                "status": "UNKNOWN",
                "late_type": None,
                "candidates": [],
                "reason": "late_type_index_unavailable",
                "evidence": dict(
                    evidence,
                    hint=(
                        "cache/caadoc_index.json is missing or empty. Rebuild it with "
                        "python tools/build_caadoc_index.py --write before generating an extension."
                    ),
                ),
            }

        named = self.explicit_components_in(request, exclude=exclude)
        if len(named) == 1:
            return {
                "status": "CLEAR",
                "late_type": named[0],
                "candidates": [named[0]],
                "reason": "explicit_component_named_in_request",
                "evidence": dict(evidence, component=self.describe(named[0])),
            }
        if len(named) > 1:
            return {
                "status": "AMBIGUOUS",
                "late_type": None,
                "candidates": named[:MAX_CANDIDATES],
                "reason": "multiple_real_components_named_in_request",
                "evidence": dict(evidence, named_components=named),
            }

        candidates = self.candidates_for_interface(primary_interface)
        if candidates:
            return {
                "status": "AMBIGUOUS",
                "late_type": None,
                "candidates": candidates,
                "reason": "entity_category_is_not_a_late_type",
                "evidence": dict(
                    evidence,
                    note=(
                        f"'{entity}' is a requirement category, not a component name. "
                        f"Pick a real component for the {primary_interface} extension."
                    ),
                ),
            }

        return {
            "status": "UNKNOWN",
            "late_type": None,
            "candidates": [],
            "reason": "no_verified_component_for_interface",
            "evidence": dict(
                evidence,
                note=(
                    "No local evidence lists a component for this interface, so no "
                    "late type can be named without guessing."
                ),
            ),
        }


# ─── CLI ─────────────────────────────────────────────────────────


def _cli(argv: List[str]) -> int:
    skill_root = Path(__file__).resolve().parent.parent
    resolver = LateTypeResolver(skill_root)
    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]

    if "--candidates" in flags:
        if not args:
            print("usage: late_type_resolver.py --candidates <Interface>")
            return 2
        hits = resolver.candidates_for_interface(args[0])
        print(f"{args[0]}: {len(hits)} candidate(s)")
        for name in hits:
            print(f"  - {name}")
        return 0 if hits else 1

    if not args:
        print("usage: late_type_resolver.py <Identifier> [...]")
        print("       late_type_resolver.py --candidates <Interface>")
        return 2

    rc = 0
    for name in args:
        info = resolver.describe(name)
        if info["is_late_type"]:
            src = []
            if info["in_shipped_dic"]:
                src.append("shipped .dic")
            if info["in_caadoc_samples"]:
                src.append("CAADoc samples")
            print(f"{name}  COMPONENT  ({', '.join(src)})  interfaces={len(info['interfaces'])}")
        else:
            print(f"{name}  NOT-A-COMPONENT (absent from shipped .dic and CAADoc samples)")
            rc = 1
    return rc


if __name__ == "__main__":
    import sys

    sys.exit(_cli(sys.argv[1:]))
