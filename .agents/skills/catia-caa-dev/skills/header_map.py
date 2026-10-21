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
  python skills/header_map.py --show CATIVisProperties [--method SetPropertiesAtt]
      → bounded read-only window. The editor cannot open the install tree;
        do not hand-roll a Python dump of path=.
  python skills/header_map.py --rebuild   # force cache rebuild
  python skills/header_map.py --stats     # cache stats

Python API:
  from header_map import HeaderMap
  hm = HeaderMap.load(skill_root)
  entry = hm.lookup("CATPathElement")  # ("CATViz", "VisualizationBase")
"""

from __future__ import annotations

import json
import re
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

    # Process-wide cache (per skill_root + JSON cache mtime) — mirrors
    # CatalogIndex/MethodIndex so every retrieval index shares the same
    # lifecycle; callers never guess which load() is cached and which not.
    _PROC_CACHE: Dict[str, "HeaderMap"] = {}
    _PROC_CACHE_MTIME: Dict[str, float] = {}

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
        automatically triggers a rebuild. Within a process the loaded
        map is cached per skill_root and invalidated when the JSON
        cache file's mtime changes (e.g. after --rebuild).
        """
        skill_root = Path(skill_root)
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
        key = str(skill_root.resolve())

        # Process-wide cache: valid while the JSON cache mtime is unchanged
        if not force_rebuild:
            try:
                mtime: Optional[float] = cache_file.stat().st_mtime
            except OSError:
                mtime = None
            if (mtime is not None
                    and cls._PROC_CACHE_MTIME.get(key) == mtime
                    and key in cls._PROC_CACHE):
                return cls._PROC_CACHE[key]

        hm = cls()
        if not force_rebuild and cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                hm._map = {k: tuple(v) for k, v in data.get("map", {}).items()}
                hm._frameworks = {k: list(v) for k, v in data.get("frameworks", {}).items()}
                hm._loaded = True
            except (json.JSONDecodeError, KeyError):
                pass  # corrupt cache, rebuild

        if not hm._loaded and catia_install:
            hm._build(catia_install)
            _warn_knowledge_release_gap(skill_root, catia_version)
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

        # Populate the process cache keyed by the on-disk cache mtime.
        # When no cache file exists (CATIA absent), skip caching so every
        # call re-checks whether the file appeared.
        try:
            cls._PROC_CACHE[key] = hm
            cls._PROC_CACHE_MTIME[key] = cache_file.stat().st_mtime
        except OSError:
            cls._PROC_CACHE.pop(key, None)
            cls._PROC_CACHE_MTIME.pop(key, None)
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


# ─── Knowledge-base release coverage check ─────────────────────────

_KB_RELEASE_RE = re.compile(r"^release:\s*\[([^\]]*)\]", re.M)

def _normalize_release(tok: str) -> Optional[str]:
    """Normalize a release token to a bare number string.

    CATIA_VERSION uses B-style ('B28'), knowledge frontmatter uses R-style
    ('R19', 'R28') — they denote the same releases, so both reduce to '28'.
    Returns None for unrecognized tokens (never raises).
    """
    tok = tok.strip().upper()
    for prefix in ("V5-6R", "V5R", "R", "B"):
        if tok.startswith(prefix):
            tok = tok[len(prefix):]
            break
    return tok if tok.isdigit() else None

def _warn_knowledge_release_gap(skill_root: Path, catia_version: str) -> None:
    """After a header-map rebuild, warn if the knowledge base predates the
    detected CATIA release. Verifier falls back to knowledge whitelists when
    a header is absent from the map; if the whitelist predates the install,
    post-release APIs risk being flagged as fabricated.

    Fail-open by design: any error is swallowed and this never blocks a build.
    """
    try:
        target = _normalize_release(catia_version)
        if not target:
            return
        kbase = Path(skill_root) / "knowledge"
        if not kbase.is_dir():
            return
        covered = set()
        scanned = 0
        for md in kbase.rglob("*.md"):
            scanned += 1
            try:
                head = md.read_text(encoding="utf-8", errors="replace")[:2048]
            except OSError:
                continue
            m = _KB_RELEASE_RE.search(head)
            if not m:
                continue
            for tok in m.group(1).split(","):
                rel = _normalize_release(tok)
                if rel:
                    covered.add(rel)
        if covered and target not in covered:
            print(
                f"WARN: knowledge base predates CATIA {catia_version} — "
                f"{scanned} knowledge files cover release(s) "
                f"{', '.join('R' + c for c in sorted(covered, key=int))} only; "
                f"post-R{target} APIs may be flagged as fabricated. "
                f"Update release: frontmatter in knowledge/**/*.md.",
                file=sys.stderr,
            )
    except Exception:
        pass  # never let a consistency check break the build


# ─── CLI ───────────────────────────────────────────────────────────

def _resolve_header_path(catia_install: str, fw_name: str, stem: str) -> Optional[str]:
    """Probe the two candidate locations for a header's absolute path."""
    found = resolve_header_file(catia_install, fw_name, stem)
    return str(found) if found else None


def resolve_header_file(catia_install: str, fw_name: str, stem: str) -> Optional[Path]:
    """Same probe as _resolve_header_path, but only if the file stays under CATIA_INSTALL."""
    if not catia_install or not fw_name or not stem:
        return None
    if ".." in Path(fw_name).parts or ".." in Path(stem).parts:
        return None
    root = Path(catia_install)
    base = root / fw_name
    for candidate in (base / "PublicInterfaces" / f"{stem}.h",
                      base / "CNext" / "public" / "interfaces" / f"{stem}.h"):
        try:
            full = candidate.resolve()
            full.relative_to(root.resolve())
        except (OSError, ValueError):
            continue
        if full.is_file():
            return full
    return None


def read_header_window(
    catia_install: str,
    fw_name: str,
    stem: str,
    *,
    method: str = "",
    context: int = 8,
    max_lines: int = 60,
) -> dict:
    """Bounded read-only window of an SDK header. Writes nothing.

    status: ok | not_found | source_unavailable
    The editor cannot open CATIA-install paths. This is the supported read.
    A window is a signature excerpt, not a verified call chain.
    """
    if not catia_install:
        return {
            "status": "source_unavailable",
            "message": "CATIA_INSTALL is empty. Header source cannot be read.",
            "name": stem,
            "read_only": True,
        }
    full = resolve_header_file(catia_install, fw_name, stem)
    if full is None:
        return {
            "status": "not_found",
            "message": "Header file not found under CATIA_INSTALL.",
            "name": stem,
            "framework": fw_name,
            "read_only": True,
        }
    try:
        raw = full.read_bytes()
        text = raw.decode("utf-8", errors="replace")
    except OSError as exc:
        return {
            "status": "source_unavailable",
            "message": str(exc),
            "name": stem,
            "read_only": True,
        }
    src = text.splitlines()
    code_hits = []
    comment_hits = []
    if method:
        for i, line in enumerate(src, start=1):
            if method not in line:
                continue
            if _is_comment_line(line):
                comment_hits.append(i)
            else:
                code_hits.append(i)
    # A comment mention (@href, prose) is not the declaration. Prefer code.
    hits = code_hits or comment_hits
    declaration_in_header = bool(code_hits) if method else None
    declared_on = "" if code_hits else _comment_declared_on(src, method)
    if not hits:
        # Class / declaration line, else the top of the file.
        hits = [i for i, line in enumerate(src, start=1)
                if stem in line and not _is_comment_line(line)][:1]
        if not hits:
            hits = [i for i, line in enumerate(src, start=1) if stem in line][:1]
    windows = []
    if hits:
        for line in hits:
            start = max(1, line - context)
            end = min(len(src), line + context)
            if windows and start <= windows[-1][1] + 1:
                windows[-1][1] = max(windows[-1][1], end)
            else:
                windows.append([start, end])
    elif src:
        windows = [[1, min(len(src), max_lines)]]
    kept = []
    used = 0
    truncated = False
    for start, end in windows:
        if used >= max_lines:
            truncated = True
            break
        if used + (end - start + 1) > max_lines:
            end = start + (max_lines - used) - 1
            truncated = True
        kept.append((start, end))
        used += end - start + 1
        if truncated:
            break
    fragments = []
    for start, end in kept:
        fragments.append({
            "start": start,
            "end": end,
            "text": "\n".join(f"{n:5d}|{src[n - 1]}" for n in range(start, end + 1)),
        })
    return {
        "status": "ok",
        "name": stem,
        "framework": fw_name,
        "path": str(full),
        "line_count": len(src),
        "truncated": truncated,
        "matched_lines": hits[:20],
        "declaration_in_header": declaration_in_header,
        "declared_on": declared_on,
        "read_only": True,
        "note": (
            "SDK header window. A comment mention is not a declaration. "
            "Presence of a declaration is not a call recipe."
        ),
        "fragments": fragments,
    }


_HREF_RE = re.compile(r"@href\s+([A-Za-z_][A-Za-z0-9_]*)#([A-Za-z_][A-Za-z0-9_]*)")


def _comment_declared_on(src, method: str) -> str:
    """Interface named by @href Type#method when this header only mentions it."""
    if not method:
        return ""
    for line in src:
        if method not in line or not _is_comment_line(line):
            continue
        for type_name, meth in _HREF_RE.findall(line):
            if meth == method and type_name:
                return type_name
    return ""


def _is_comment_line(line: str) -> bool:
    """True for a comment-only line. A code line that also has // stays code."""
    stripped = line.strip()
    if stripped.startswith(("//", "*", "/*")):
        return True
    code = stripped.split("//", 1)[0]
    return "/*" in code and "*/" not in code.split("/*", 1)[0]


def format_header_window(result: dict) -> str:
    status = result.get("status")
    if status != "ok":
        return f"{status}  {result.get('message', '')}\n"
    declared = result.get("declaration_in_header")
    declared_text = ""
    if declared is True:
        declared_text = "  declaration=code"
    elif declared is False:
        where = result.get("declared_on") or ""
        declared_text = "  declaration=comment-only"
        if where:
            declared_text += f"  declared_on={where}"
    lines = [
        f"status=ok  {result.get('name')}  fw={result.get('framework')}  "
        f"lines={result.get('line_count')}  truncated={str(result.get('truncated')).lower()}"
        f"{declared_text}",
    ]
    for frag in result.get("fragments", []):
        lines.append(f"--- L{frag['start']}-L{frag['end']} ---")
        lines.append(frag.get("text", ""))
    lines.append("")
    return "\n".join(lines)


def _catia_install(skill_root: Path) -> str:
    try:
        if str(skill_root / "skills") not in sys.path:
            sys.path.insert(0, str(skill_root / "skills"))
        from env import CAAEnvironment
        env = CAAEnvironment()
        env.load_config()
        return env.config.get("CATIA_INSTALL", "") or ""
    except Exception:
        return ""


def _cli(argv: List[str]) -> int:
    from difflib import get_close_matches

    show = "--show" in argv
    method = ""
    cleaned = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--method" and i + 1 < len(argv):
            method = argv[i + 1]
            i += 2
            continue
        if tok == "--show":
            i += 1
            continue
        cleaned.append(tok)
        i += 1
    args = [a for a in cleaned if not a.startswith("--")]
    flags = {a for a in cleaned if a.startswith("--")}

    skill_root = Path(__file__).resolve().parent.parent
    hm = HeaderMap.load(skill_root, force_rebuild="--rebuild" in flags)

    if "--stats" in flags:
        print(f"frameworks={hm.framework_count} headers={hm.header_count}")
        return 0

    if not args:
        print(__doc__.strip())
        return 0

    catia_install = _catia_install(skill_root)

    if show:
        rc = 0
        for name in args:
            stem = Path(name).stem
            entry = hm.lookup(stem)
            if not entry:
                rc = 1
                sugg = get_close_matches(stem, sorted(hm._map.keys()), n=3, cutoff=0.70)
                hint = f"  did-you-mean: {', '.join(sugg)}" if sugg else ""
                print(f"{stem}  NOT-FOUND{hint}")
                continue
            _mod, fw = entry
            result = read_header_window(
                catia_install, fw, stem, method=method,
            )
            print(format_header_window(result), end="")
            if result.get("status") != "ok":
                rc = 1
                continue
            # Comment-only @href Type#method: follow one hop to the real header.
            declared_on = result.get("declared_on") or ""
            if method and declared_on and declared_on != stem:
                followed = hm.lookup(declared_on)
                if followed:
                    _fmod, ffw = followed
                    followed_result = read_header_window(
                        catia_install, ffw, declared_on, method=method,
                    )
                    print(f"followed {declared_on}#{method}")
                    print(format_header_window(followed_result), end="")
                    if followed_result.get("status") != "ok":
                        rc = 1
        return rc

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
