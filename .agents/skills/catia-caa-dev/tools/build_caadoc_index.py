#!/usr/bin/env python
"""Build a local, structured index of CAADoc reference manual + dictionaries.

This is a *lookup accelerator* for verifying CAA API signatures against the
official CAADoc, not a knowledge source in itself. It scans:

1. Doc/generated/refman/**/*.htm
   -> one record per class/interface/enum/typedef/function, with its
      framework, defining file, and full method-signature list (parsed
      from the "Method Index" -> "o <signature>" pattern also used
      manually via `grep "^  o "` during API audits).

2. **/*.dico
   -> component -> interface implementation map (which concrete component
      classes declare "TIE_" implementation of which interface, in which
      library). This is the authoritative source for "does component X
      actually implement interface Y" questions (e.g. it settled whether
      CATIProduct implements CATIVisProperties -- it does not).

A reverse method-name index is also built (which types declare a method
with a given bare name), to answer "which interfaces have a SetColor
method" style questions without re-grepping CAADoc by hand.

Output is written to cache/caadoc_index.json (gitignored, machine-local,
since it embeds absolute paths into the user's CATIA install and CAADoc
content itself is not redistributed). By default, --query/--search reuse
that cache when present instead of rescanning (rescanning ~6600 files
takes ~2s; loading the cached JSON takes a fraction of that). Use
--rebuild to force a fresh scan, or --write to persist a fresh scan.

Usage:
    python tools/build_caadoc_index.py --write
    python tools/build_caadoc_index.py --query CATIVisProperties
    python tools/build_caadoc_index.py --query CATIProduct --query CATICst
    python tools/build_caadoc_index.py --search VisProp
    python tools/build_caadoc_index.py --rebuild --write --query CATIProduct
    python tools/build_caadoc_index.py --repl   # interactive: 'q <name>', 's <pattern>'
"""
import argparse
import html
import json
import re
import sys
import time
from pathlib import Path


def find_caadoc_root():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from skills.env import CAAEnvironment

    env = CAAEnvironment()
    env.load_config()
    catia = env.config.get("CATIA_INSTALL", "")
    if not catia:
        return None
    root = Path(catia) / "CAADoc"
    return root if root.is_dir() else None


def cache_path():
    return Path(__file__).resolve().parent.parent / "cache" / "caadoc_index.json"


_NAME_RE = re.compile(r'getCurrentObjectName\(\)\s*\{\s*return "(.*?)"')
_KIND_RE = re.compile(r'getCurrentType\(\)\s*\{\s*return "(.*?)"')
_METHOD_RE = re.compile(r'^\s*o\s+(\S.*)$', re.MULTILINE)
_TAG_RE = re.compile(r'<[^>]*>')


def parse_refman_file(path: Path, refman_root: Path):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    plain = _TAG_RE.sub("", text)

    m = _NAME_RE.search(plain)
    if not m:
        return None
    name = m.group(1)

    m2 = _KIND_RE.search(plain)
    kind = m2.group(1) if m2 else "unknown"

    try:
        rel = path.relative_to(refman_root)
        framework = rel.parts[0] if len(rel.parts) > 1 else "(root)"
    except ValueError:
        framework = "(unknown)"

    methods = [html.unescape(m.strip()) for m in _METHOD_RE.findall(plain)]
    # Each method typically appears twice on a refman page: once with a full
    # parenthesized signature (Method Index anchor block) and once as a bare
    # name with no parentheses (Methods detail section anchor). De-duplicate
    # on the bare method name, preferring whichever version has a signature.
    by_base_name = {}
    order = []
    for meth in methods:
        base = meth.split("(", 1)[0].strip()
        if base not in by_base_name:
            by_base_name[base] = meth
            order.append(base)
        elif "(" in meth and "(" not in by_base_name[base]:
            by_base_name[base] = meth
    unique_methods = [by_base_name[base] for base in order]

    return {
        "name": name,
        "kind": kind,
        "framework": framework,
        "file": str(path),
        "methods": unique_methods,
    }


def scan_refman(caadoc_root: Path):
    refman = caadoc_root / "Doc" / "generated" / "refman"
    if not refman.is_dir():
        print(f"WARNING: refman not found at {refman}", file=sys.stderr)
        return []
    records = []
    for hf in refman.glob("**/*.htm"):
        if hf.stem.lower() == "visidx.txt":
            continue  # global index page, not a type/framework doc
        rec = parse_refman_file(hf, refman)
        if rec:
            records.append(rec)
    return records


_DICO_LINE_RE = re.compile(r'^\s*(\S+)\s+(\S+)\s+(\S+)\s*$')


def scan_dico(caadoc_root: Path):
    """Parse component -> interface -> library dictionary files.

    Lines look like:
        CAAPstINFPoint    CATIVisProperties    libCAAPstINFModeler
    Comment lines start with '#' or '//' and are skipped; blank lines and
    section headers without exactly 3 tokens are skipped too.
    """
    entries = []
    for df in caadoc_root.glob("**/*.dico"):
        try:
            text = df.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                continue
            m = _DICO_LINE_RE.match(stripped)
            if not m:
                continue
            component, interface, library = m.groups()
            entries.append({
                "component": component,
                "interface": interface,
                "library": library,
                "file": str(df),
            })
    return entries


def build_method_index(refman_records):
    """Reverse index: bare method name -> list of {type, kind, framework, signature}.

    Answers "which types declare a method named X" without re-grepping
    CAADoc. Keyed by exact bare name; callers needing substring/case-
    insensitive search should scan the keys themselves (see `search`).
    """
    idx = {}
    for rec in refman_records:
        for meth in rec["methods"]:
            base = meth.split("(", 1)[0].strip()
            idx.setdefault(base, []).append({
                "type": rec["name"],
                "kind": rec["kind"],
                "framework": rec["framework"],
                "signature": meth,
            })
    return idx


def build_index(caadoc_root: Path):
    t0 = time.time()
    refman_records = scan_refman(caadoc_root)
    dico_entries = scan_dico(caadoc_root)
    elapsed = time.time() - t0

    by_name = {}
    for rec in refman_records:
        by_name.setdefault(rec["name"], []).append(rec)

    implements_by_interface = {}
    implements_by_component = {}
    for e in dico_entries:
        implements_by_interface.setdefault(e["interface"], []).append(e["component"])
        implements_by_component.setdefault(e["component"], []).append(e["interface"])

    methods_by_name = build_method_index(refman_records)

    return {
        "meta": {
            "caadoc_root": str(caadoc_root),
            "refman_type_count": len(refman_records),
            "dico_entry_count": len(dico_entries),
            "method_name_count": len(methods_by_name),
            "build_seconds": round(elapsed, 2),
        },
        "types": refman_records,
        "types_by_name": by_name,
        "dico_entries": dico_entries,
        "implements_by_interface": implements_by_interface,
        "implements_by_component": implements_by_component,
        "methods_by_name": methods_by_name,
    }


def load_cached_index(path: Path):
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"WARNING: failed to load cache {path}: {exc}", file=sys.stderr)
        return None


def query(index: dict, name: str):
    matches = index["types_by_name"].get(name)
    if not matches:
        # case-insensitive fallback
        lname = name.lower()
        matches = [
            rec for rec in index["types"] if rec["name"].lower() == lname
        ]
    if matches:
        for rec in matches:
            print(f"\n=== {rec['kind']} {rec['name']}  [{rec['framework']}] ===")
            print(f"file: {rec['file']}")
            if rec["methods"]:
                print(f"methods ({len(rec['methods'])}):")
                for m in rec["methods"]:
                    print(f"  o {m}")
            else:
                print("(no methods found in index block)")
    else:
        print(f"No refman type named '{name}' found.")

    implementers = index["implements_by_interface"].get(name)
    if implementers:
        print(f"\nComponents declaring implementation of '{name}' (.dico):")
        for c in sorted(set(implementers)):
            print(f"  - {c}")

    implemented = index["implements_by_component"].get(name)
    if implemented:
        print(f"\nInterfaces implemented by component '{name}' (.dico):")
        for i in sorted(set(implemented)):
            print(f"  - {i}")

    # Reverse method-name lookup: is `name` itself a method name shared
    # across types? Useful when the query looks like "SetColor" rather
    # than a type name.
    method_hits = index.get("methods_by_name", {}).get(name)
    if not method_hits:
        lname = name.lower()
        for base, hits in index.get("methods_by_name", {}).items():
            if base.lower() == lname:
                method_hits = hits
                break
    if method_hits:
        print(f"\nTypes declaring a method named '{name}':")
        for h in method_hits:
            print(f"  {h['type']:35s} [{h['framework']}] :: {h['signature']}")

    if not matches and not implementers and not implemented and not method_hits:
        print("(no match in refman types, .dico entries, or method index)")


def search(index: dict, pattern: str, limit: int = 50):
    """Substring search (case-insensitive) over type names and method
    signatures. Use this when you don't know the exact name and are
    exploring candidates -- it replaces ad-hoc `find`/`grep` over CAADoc
    for "what's the real name of the thing that does X" questions.
    """
    pat = pattern.lower()

    print(f"\n--- Type name matches for '{pattern}' ---")
    count = 0
    for rec in index["types"]:
        if pat in rec["name"].lower():
            print(f"  {rec['kind']:10s} {rec['name']:40s} [{rec['framework']}]")
            count += 1
            if count >= limit:
                print(f"  ... (truncated at {limit}; narrow the pattern for more)")
                break
    if count == 0:
        print("  (no type name matches)")

    print(f"\n--- Method signature matches for '{pattern}' ---")
    count = 0
    for base, hits in index.get("methods_by_name", {}).items():
        if pat not in base.lower():
            continue
        for h in hits:
            print(f"  {h['type']:30s} [{h['framework']}] :: {h['signature']}")
            count += 1
            if count >= limit:
                break
        if count >= limit:
            print(f"  ... (truncated at {limit}; narrow the pattern for more)")
            break
    if count == 0:
        print("  (no method signature matches)")

    print(f"\n--- Component/.dico matches for '{pattern}' ---")
    count = 0
    seen_pairs = set()
    for e in index.get("dico_entries", []):
        if pat in e["component"].lower() or pat in e["interface"].lower():
            key = (e["component"], e["interface"])
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            print(f"  {e['component']:35s} implements {e['interface']}")
            count += 1
            if count >= limit:
                print(f"  ... (truncated at {limit}; narrow the pattern for more)")
                break
    if count == 0:
        print("  (no .dico matches)")


def run_repl(index: dict):
    """Interactive loop for exploring the index without relaunching the
    process per lookup. Commands:
      q <name>      exact/case-insensitive query (same as --query)
      s <pattern>   substring search (same as --search)
      <bare text>   treated as a query if no prefix given
      exit / quit   leave the REPL
    """
    print("\nCAADoc index REPL. Commands: 'q <name>', 's <pattern>', or bare text for query. Ctrl-D/'exit' to quit.")
    while True:
        try:
            line = input("caadoc> ").strip()
        except EOFError:
            print()
            break
        if not line:
            continue
        if line in ("exit", "quit"):
            break
        if line.startswith("s "):
            search(index, line[2:].strip())
        elif line.startswith("q "):
            query(index, line[2:].strip())
        else:
            query(index, line)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true", help="Rescan and write cache/caadoc_index.json")
    p.add_argument("--rebuild", action="store_true", help="Force a fresh scan even if a cache file exists")
    p.add_argument("--query", action="append", default=[], help="Look up a type/interface/component/method name (repeatable)")
    p.add_argument("--search", action="append", default=[], help="Substring search over type names, method signatures, and .dico entries (repeatable)")
    p.add_argument("--repl", action="store_true", help="Enter an interactive query/search loop after loading/building the index")
    args = p.parse_args()

    cache_file = cache_path()
    need_fresh_scan = args.write or args.rebuild

    index = None
    if not need_fresh_scan:
        index = load_cached_index(cache_file)
        if index is not None:
            meta = index["meta"]
            print(
                f"Loaded cached index from {cache_file} "
                f"({meta['refman_type_count']} types, {meta['dico_entry_count']} dico entries, "
                f"{meta.get('method_name_count', '?')} unique method names)"
            )

    if index is None:
        root = find_caadoc_root()
        if not root:
            print("ERROR: Cannot locate CAADoc (check CATIA_INSTALL config)", file=sys.stderr)
            sys.exit(1)
        print(f"Scanning CAADoc at {root} ...")
        index = build_index(root)
        meta = index["meta"]
        print(
            f"Parsed {meta['refman_type_count']} refman types and "
            f"{meta['dico_entry_count']} .dico entries in {meta['build_seconds']}s"
        )

    if args.write:
        out_dir = cache_file.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False)
        print(f"Wrote index to {cache_file} ({cache_file.stat().st_size // 1024} KB)")

    for name in args.query:
        query(index, name)

    for pattern in args.search:
        search(index, pattern)

    if args.repl:
        run_repl(index)
