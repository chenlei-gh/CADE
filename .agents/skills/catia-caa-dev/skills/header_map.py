"""
CAA Header → Module → Framework Mapper
=======================================
Scans the CATIA installation to build a cached mapping from CAA header
names (e.g. "CATPathElement") to the module and framework that provide
them. This mapping powers the LINK_WITH coverage check in diagnostics:

  source code #include "CATPathElement.h"
  → header_map["CATPathElement"] = ("CATViz", "VisualizationBase")
  → diagnostics checks LINK_WITH has "CATViz" and IdentityCard has
    "VisualizationBase" prerequisite

The scan is slow (503 frameworks, thousands of headers), so results are
cached to JSON keyed by CATIA version. Cache lives in CADE's cache dir.

CLI (for AI agents — never guess <Framework>/PublicInterfaces paths):
  python skills/header_map.py CATDlgEditor [CATPathElement ...]
      → CATDlgEditor  fw=Dialog  mod=CATDlgBitmap  path=<abs path to .h>
  python skills/header_map.py --rebuild   # force cache rebuild
  python skills/header_map.py --stats     # cache stats

Python API:
  from header_map import HeaderMap
  hm = HeaderMap.load(skill_root)
  entry = hm.lookup("CATPathElement")  # ("CATViz", "VisualizationBase")
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Module names that are pure runtime infrastructure — never need LINK_WITH
# (they're always available via JS0GROUP etc.)
_ALWAYS_LINKED = {"JS0GROUP", "JS0FM", "JS0CORBA", "JS03", "JS0LIBRA",
                  "JS0SCBAK", "JS0ERROR", "JS0CATLang", "SystemUC"}

# Frameworks that are always available (declared as prerequisites by the
# workspace's CATIAV5Level, not per-framework IdentityCard). Also includes
# frameworks whose name doubles as a module name (System, ObjectModelerBase)
# to avoid false "framework name in LINK_WITH" flags.
_ALWAYS_AVAILABLE = {"System", "ObjectModelerBase", "CATIAApplicationFrame",
                    "ApplicationFrame", "DialogEngine", "InteractiveInterfaces"}


class HeaderMap:
    """Cached header → (module, framework) lookup table."""

    def __init__(self):
        self._map: Dict[str, Tuple[str, str]] = {}
        self._frameworks: Dict[str, List[str]] = {}  # fw → [module names]
        self._loaded = False

    @property
    def framework_count(self) -> int:
        return len(self._frameworks)

    @property
    def header_count(self) -> int:
        return len(self._map)

    def lookup(self, header_stem: str) -> Optional[Tuple[str, str]]:
        """Return (module_name, framework_name) for a header stem,
        or None if not found."""
        return self._map.get(header_stem)

    def framework_of_module(self, module_name: str) -> Optional[str]:
        """Reverse lookup: module name → framework name."""
        for fw, mods in self._frameworks.items():
            if module_name in mods:
                return fw
        return None

    def is_known_framework(self, name: str) -> bool:
        """Check if a name is a framework name (vs a module name)."""
        return name in self._frameworks

    def is_framework_only(self, name: str) -> bool:
        """True if name is a framework but NOT also a module name.
        Used to detect framework-name-in-LINK_WITH confusion (error #3)."""
        return (name in self._frameworks
                and not self.is_known_module(name)
                and name not in _ALWAYS_AVAILABLE)

    def is_known_module(self, name: str) -> bool:
        """Check if a name is a module name."""
        for mods in self._frameworks.values():
            if name in mods:
                return True
        return False

    @classmethod
    def load(cls, skill_root: Path, force_rebuild: bool = False) -> "HeaderMap":
        """Load the cached header map, building it if necessary.

        The cache is keyed by CATIA version so a version upgrade
        automatically triggers a rebuild.
        """
        hm = cls()
        cache_dir = skill_root / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Determine CATIA version for cache key
        try:
            sys.path.insert(0, str(skill_root / "skills"))
            from env import CAAEnvironment
            env = CAAEnvironment()
            env.load_config()
            catia_version = env.config.get("CATIA_VERSION", "unknown")
            catia_install = env.config.get("CATIA_INSTALL", "")
        except Exception:
            catia_version = "unknown"
            catia_install = ""

        cache_file = cache_dir / f"header_map_{catia_version}.json"

        if not force_rebuild and cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                hm._map = {k: tuple(v) for k, v in data.get("map", {}).items()}
                hm._frameworks = {k: list(v) for k, v in data.get("frameworks", {}).items()}
                hm._loaded = True
                return hm
            except (json.JSONDecodeError, KeyError):
                pass  # corrupt cache, rebuild

        if catia_install:
            hm._build(catia_install)
            # Save cache
            try:
                cache_file.write_text(json.dumps({
                    "map": {k: list(v) for k, v in hm._map.items()},
                    "frameworks": hm._frameworks,
                    "catia_version": catia_version,
                }, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass  # cache write failed — still return in-memory map

        hm._loaded = True
        return hm

    def _build(self, catia_install: str):
        """Scan CATIA installation to build the mapping.

        Frameworks are top-level directories under the install root
        that contain an IdentityCard/ directory.
        Headers live in {framework}/PublicInterfaces/*.h
        Modules are {framework}/*.m/ directories with Imakefile.mk
        """
        root = Path(catia_install)
        if not root.exists():
            return

        for fw_dir in root.iterdir():
            if not fw_dir.is_dir():
                continue
            # Frameworks have IdentityCard/
            if not (fw_dir / "IdentityCard").exists():
                continue

            fw_name = fw_dir.name
            modules = []
            mod_names = []

            # Collect modules (.m dirs with Imakefile.mk)
            for item in fw_dir.iterdir():
                if item.is_dir() and item.name.endswith(".m"):
                    if (item / "Imakefile.mk").exists():
                        mod_names.append(item.name.replace(".m", ""))

            self._frameworks[fw_name] = mod_names

            # Collect headers from PublicInterfaces/
            pi_dir = fw_dir / "PublicInterfaces"
            if pi_dir.is_dir():
                for hdr in pi_dir.glob("*.h"):
                    stem = hdr.stem  # e.g. "CATPathElement"
                    if stem not in self._map:
                        # First module that provides it wins
                        self._map[stem] = (mod_names[0] if mod_names else fw_name, fw_name)

            # Also check CNext/public/interfaces/ (alternate location)
            cpi_dir = fw_dir / "CNext" / "public" / "interfaces"
            if cpi_dir.is_dir():
                for hdr in cpi_dir.glob("*.h"):
                    stem = hdr.stem
                    if stem not in self._map:
                        self._map[stem] = (mod_names[0] if mod_names else fw_name, fw_name)


# ─── CLI ───────────────────────────────────────────────────────────

def _resolve_header_path(catia_install: str, fw_name: str, stem: str) -> Optional[str]:
    """Probe the two candidate locations for a header's absolute path."""
    if not catia_install:
        return None
    root = Path(catia_install) / fw_name
    for candidate in (root / "PublicInterfaces" / f"{stem}.h",
                      root / "CNext" / "public" / "interfaces" / f"{stem}.h"):
        if candidate.exists():
            return str(candidate)
    return None


def _cli(argv: List[str]) -> int:
    from difflib import get_close_matches

    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}

    skill_root = Path(__file__).resolve().parent.parent
    hm = HeaderMap.load(skill_root, force_rebuild="--rebuild" in flags)

    if "--stats" in flags:
        print(f"frameworks={hm.framework_count} headers={hm.header_count}")
        return 0

    if not args:
        print(__doc__.strip())
        return 0

    # CATIA_INSTALL for absolute path resolution
    catia_install = ""
    try:
        sys.path.insert(0, str(skill_root / "skills"))
        from env import CAAEnvironment
        env = CAAEnvironment()
        env.load_config()
        catia_install = env.config.get("CATIA_INSTALL", "")
    except Exception:
        pass

    rc = 0
    for name in args:
        stem = Path(name).stem  # tolerate CATDlgEditor.h
        entry = hm.lookup(stem)
        if entry:
            mod, fw = entry
            line = f"{stem}  fw={fw}  mod={mod}"
            path = _resolve_header_path(catia_install, fw, stem)
            if path:
                line += f"  path={path}"
            print(line)
        else:
            rc = 1
            sugg = get_close_matches(stem, sorted(hm._map.keys()), n=3, cutoff=0.70)
            hint = f"  did-you-mean: {', '.join(sugg)}" if sugg else ""
            print(f"{stem}  NOT-FOUND{hint}")
    return rc


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
