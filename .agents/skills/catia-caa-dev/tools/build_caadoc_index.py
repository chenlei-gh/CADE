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

Output is written to cache/caadoc_index.json (gitignored, machine-local,
since it embeds absolute paths into the user's CATIA install and CAADoc
content itself is not redistributed).

Usage:
    python tools/build_caadoc_index.py --write
    python tools/build_caadoc_index.py --write --query CATIVisProperties
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

    return {
        "meta": {
            "caadoc_root": str(caadoc_root),
            "refman_type_count": len(refman_records),
            "dico_entry_count": len(dico_entries),
            "build_seconds": round(elapsed, 2),
        },
        "types": refman_records,
        "types_by_name": by_name,
        "dico_entries": dico_entries,
        "implements_by_interface": implements_by_interface,
        "implements_by_component": implements_by_component,
    }


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

    if not matches and not implementers and not implemented:
        print("(no match in refman types or .dico entries)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true", help="Write cache/caadoc_index.json")
    p.add_argument("--query", help="Look up a type/interface/component name after building")
    args = p.parse_args()

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
        out_dir = Path(__file__).resolve().parent.parent / "cache"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "caadoc_index.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False)
        print(f"Wrote index to {out_file} ({out_file.stat().st_size // 1024} KB)")

    if args.query:
        query(index, args.query)
