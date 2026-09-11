"""
Build UseCaseIndex — Official Example Presence Index
=====================================================
Scans CAADoc use-case .cpp files (*.edu/*/src/*.cpp) and extracts RAW
TOKENS ONLY: included interfaces, method-call names, CAT-prefixed symbols.

Design boundary (governance):
  - This builder is DUMB. It records WHERE a token appears, never WHAT
    it means, WHO owns it, or WHETHER it is recommended.
  - Method->interface ownership is resolved at QUERY TIME by joining
    with MethodIndex.owners_of() — never inferred here.
  - "Existence of an official example" != "official best practice".
    Recommendations live in knowledge/failure_patterns, not in this index.

Scope (schema 3, 2026-09-11): the same *.edu frameworks also ship the
NON-cpp evidence a CAA developer needs — how the official samples are
BUILT and ORGANIZED, not just which APIs they call:

  kind="imakefile"     module.m/Imakefile.mk      (libs from LINK_WITH)
  kind="local_header"  module.m/LocalInterfaces/*.h (CATI* includes)
  kind="nls"           CNext/resources/msgcatalog/**/*.CATNls (left-side keys)
  kind="rsc"           CNext/resources/msgcatalog/**/*.CATRsc (left-side keys)

These land in a SEPARATE top-level "resources" section keyed by
CAADoc-relative path (unique by construction). The four source maps
(examples / by_interface / by_method / by_symbol) stay SOURCE-ONLY:
resource records never feed them, so every existing query behaves
exactly as before. Presence != recommendation, same as sources.

Output: cache/usecase_index.json  (gitignored, regenerated locally)

Usage:
    python tools/build_usecase_index.py [--verbose]

Pure stdlib.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

# ─── Token extraction (regex-level, no C++ parsing) ──────────────

# #include "CATIVisProperties.h"  ->  CATIVisProperties
_INCLUDE_RE = re.compile(r'#include\s+[<"](?P<name>CATI\w+)\.h[>"]')

# ptr->SetPropertiesAtt(  /  obj.Method(   ->  SetPropertiesAtt
# Must start with an uppercase letter (CAA method style), len >= 3.
_CALL_RE = re.compile(r'(?:->|\.)\s*(?P<name>[A-Z][A-Za-z0-9_]{2,})\s*\(')

# CAT-prefixed identifiers that are NOT includes and NOT calls:
# enums / constants like CATNoShowAttr, CATVPShow, CATVPGlobalType.
_SYMBOL_RE = re.compile(r'\bCAT[A-Z][A-Za-z0-9_]+\b')


def _scan_cpp(path: Path) -> dict:
    """Extract raw tokens from one .cpp file. No type resolution."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"interfaces": [], "methods": [], "symbols": []}

    interfaces = sorted({m.group("name") for m in _INCLUDE_RE.finditer(text)})
    methods = sorted({m.group("name") for m in _CALL_RE.finditer(text)})

    # Symbols: CAT-prefixed tokens minus include names minus call names.
    include_set = set(interfaces)
    call_set = set(methods)
    symbols = sorted({
        m.group(0) for m in _SYMBOL_RE.finditer(text)
        if m.group(0) not in include_set and m.group(0) not in call_set
    })
    return {"interfaces": interfaces, "methods": methods, "symbols": symbols}


# LINK_WITH = \n#   JS0GROUP \n#   CATMathematics
_LINK_WITH_RE = re.compile(
    r"LINK_WITH\s*=\s*(?P<body>.*?)(?=^\s*[A-Z_]+\s*=|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Comment / continuation artifacts inside a LINK_WITH body.
_LINK_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _scan_imakefile(path: Path) -> dict:
    """Extract LINK_WITH library tokens from one Imakefile.mk.

    Raw tokens only: the listed library names, no prerequisite inference.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"libs": []}
    m = _LINK_WITH_RE.search(text)
    if not m:
        return {"libs": []}
    body = m.group("body").replace("\\", " ")
    libs = sorted({
        tok for tok in body.split()
        if _LINK_TOKEN_RE.match(tok) and not tok.startswith("DIROBJ")
    })
    return {"libs": libs}


def _scan_local_header(path: Path) -> dict:
    """Extract CATI* includes from one LocalInterfaces/*.h."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"interfaces": []}
    interfaces = sorted({m.group("name") for m in _INCLUDE_RE.finditer(text)})
    return {"interfaces": interfaces}


# AniCommandHeader.CreateOneImage.Title = "...";   (both .CATNls/.CATRsc)
_RSC_KEY_RE = re.compile(r"^\s*(?P<key>[A-Za-z_][A-Za-z0-9_.]*)\s*=")


def _scan_msgcat_keys(path: Path) -> dict:
    """Extract left-side keys from one .CATNls/.CATRsc file.

    Raw facts only: which key appears in which file. Keys can span lines
    (quoted values with embedded newlines), so the regex is line-anchored
    and simply ignores lines without a leading key.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"keys": []}
    keys = sorted({
        m.group("key")
        for line in text.splitlines()
        for m in [_RSC_KEY_RE.match(line)]
        if m
    })
    return {"keys": keys}


def _edu_module(path: Path, caadoc_root: Path) -> tuple:
    """(framework.edu, module.m-or-None) for a file under CAADoc."""
    parts = path.relative_to(caadoc_root).parts
    framework = parts[0] if parts else ""
    module = next((part for part in parts if part.endswith(".m")), None)
    return framework, module


def _scan_resources(caadoc_root: Path) -> tuple:
    """Scan *.edu for non-source evidence files.

    Returns (resources, by_kind):
      resources: rel_path -> {"kind", "framework", "module", + kind tokens}
      by_kind:   kind -> [rel_path, ...]  (sorted)
    """
    resources = {}
    by_kind = {}

    def _add(path: Path, kind: str, extra: dict) -> None:
        rel = str(path.relative_to(caadoc_root)).replace("\\", "/")
        framework, module = _edu_module(path, caadoc_root)
        resources[rel] = {
            "kind": kind,
            "framework": framework,
            "module": module,
            **extra,
        }
        by_kind.setdefault(kind, []).append(rel)

    for mk in sorted(caadoc_root.glob("*.edu/*/*.mk")):
        if mk.name.lower() == "imakefile.mk":
            _add(mk, "imakefile", _scan_imakefile(mk))
    for h in sorted(caadoc_root.glob("*.edu/*/LocalInterfaces/*.h")):
        _add(h, "local_header", _scan_local_header(h))
    for nls in sorted(caadoc_root.glob("*.edu/**/msgcatalog/**/*.CATNls")):
        _add(nls, "nls", _scan_msgcat_keys(nls))
    for rsc in sorted(caadoc_root.glob("*.edu/**/msgcatalog/**/*.CATRsc")):
        _add(rsc, "rsc", _scan_msgcat_keys(rsc))

    for kind in by_kind:
        by_kind[kind].sort()
    return resources, by_kind


def find_catia_root():
    """CATIA_INSTALL root via CADE env config (same as build_caadoc_index)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from skills.env import CAAEnvironment
    env = CAAEnvironment()
    env.load_config()
    catia = env.config.get("CATIA_INSTALL", "")
    if not catia:
        return None
    root = Path(catia)
    return root if root.is_dir() else None


def cache_path():
    return Path(__file__).resolve().parent.parent / "cache" / "usecase_index.json"


def build_index(caadoc_root: Path) -> dict:
    """Scan all use-case .cpp under *.edu/*/src/ and build the index.

    Key collision fix (2026-07-31): 1233 files on disk share only 1214
    unique .cpp stems (e.g. 9 different modules each ship their own
    main.cpp). Using the bare stem as the examples[] dict key silently
    dropped 19 files, and worse, made by_interface/by_method/by_symbol
    point a different module's tokens at whichever file happened to be
    written last during the scan (verified: by_method["Release"] listed
    "main", but examples["main"]["file"] resolved to a main.cpp that
    never calls Release() — the token actually came from a different
    main.cpp). Fix: only the files whose stem collides get a
    disambiguated key "stem (module.m)"; the 1203 non-colliding files
    keep their bare stem unchanged, so existing lookups by plain example
    name (e.g. "CAAMmrSetShowModeCmd") are unaffected.
    """
    t0 = time.time()

    cpp_files = sorted(caadoc_root.glob("*.edu/*/src/**/*.cpp"))

    stem_counts: dict = {}
    for cpp in cpp_files:
        stem_counts[cpp.stem] = stem_counts.get(cpp.stem, 0) + 1

    examples = {}
    by_interface = {}
    by_method = {}
    by_symbol = {}

    for cpp in cpp_files:
        tokens = _scan_cpp(cpp)
        rel = str(cpp.relative_to(caadoc_root)).replace("\\", "/")
        if stem_counts[cpp.stem] > 1:
            module = next((part for part in cpp.parts if part.endswith(".m")), cpp.parent.name)
            key = f"{cpp.stem} ({module})"
        else:
            key = cpp.stem
        examples[key] = {"file": rel, **tokens}
        for iface in tokens["interfaces"]:
            by_interface.setdefault(iface, []).append(key)
        for meth in tokens["methods"]:
            by_method.setdefault(meth, []).append(key)
        for sym in tokens["symbols"]:
            by_symbol.setdefault(sym, []).append(key)

    resources, by_kind = _scan_resources(caadoc_root)

    return {
        "meta": {
            "caadoc_root": str(caadoc_root),
            "example_count": len(examples),
            "interface_token_count": len(by_interface),
            "method_token_count": len(by_method),
            "symbol_token_count": len(by_symbol),
            "resource_count": len(resources),
            "resource_kind_counts": {k: len(v) for k, v in sorted(by_kind.items())},
            "build_seconds": round(time.time() - t0, 2),
            "schema": 3,
        },
        "examples": examples,
        "by_interface": by_interface,
        "by_method": by_method,
        "by_symbol": by_symbol,
        "resources": resources,
        "by_kind": by_kind,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Build CAADoc use-case presence index")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    catia = find_catia_root()
    if not catia:
        print("ERROR: CATIA_INSTALL not configured", file=sys.stderr)
        return 1
    caadoc = catia / "CAADoc"
    if not caadoc.is_dir():
        print(f"ERROR: CAADoc not found under {catia}", file=sys.stderr)
        return 1

    index = build_index(caadoc)
    out = cache_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    meta = index["meta"]
    print(f"UseCaseIndex built: {meta['example_count']} examples, "
          f"{meta['interface_token_count']} interfaces, "
          f"{meta['method_token_count']} methods, "
          f"{meta['symbol_token_count']} symbols, "
          f"{meta['resource_count']} resources {meta['resource_kind_counts']} "
          f"({meta['build_seconds']}s) -> {out}")
    if args.verbose:
        # Smoke: the canonical verified case
        hits = index["by_interface"].get("CATIVisProperties", [])
        print(f"smoke: CATIVisProperties examples = {len(hits)}, "
              f"CAAMmrSetShowModeCmd present = {'CAAMmrSetShowModeCmd' in hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
