#!/usr/bin/env python
"""Build a local, structured index of CAADoc + the real CAA SDK/shipped files.

This is a *lookup accelerator* for verifying CAA API signatures against the
official CATIA installation, not a knowledge source in itself. It scans four
independent sources and cross-checks them against each other:

1. Doc/generated/refman/**/*.htm  (under CATIA_INSTALL/CAADoc)
   -> one record per class/interface/enum/typedef/function, with its
      framework, defining file, and full method-signature list (parsed
      from the "Method Index" -> "o <signature>" pattern also used
      manually via `grep "^  o "` during API audits).

2. **/*.dico  (under CATIA_INSTALL/CAADoc)
   -> component -> interface implementation map, but only for the ~40
      CAADoc *.edu tutorial frameworks that happen to ship a .dico file
      (44 files, ~400 component/interface pairs). Useful, but a curated
      subset -- see source 4 below for the real ground truth.

3. */PublicInterfaces/*.h  (under CATIA_INSTALL itself, i.e. the actual SDK
   headers the refman htm pages are generated from). This is the MOST
   authoritative source for method/enum signatures, and it carries
   information the generated refman pages sometimes drop or never had, such
   as the "// CATIXxx" inline comments mapping a global-instantiation enum
   value (e.g. CATTPSComponent) to the concrete interface it produces. It
   also lets us detect refman generation gaps: an interface documented in
   refman but whose real header shows a different method set. --query and
   --search report a "SDK/refman mismatch" warning whenever the two
   disagree, so a modeled-but-missing method (or a refman method that
   doesn't exist in the header) surfaces automatically instead of requiring
   a manual re-check.

4. <arch>/code/dictionary/*.dic  (under CATIA_INSTALL itself, e.g.
   win_b64/code/dictionary -- NOT CAADoc's **/*.dico from source 2). This is
   the shipped-product TIE dictionary: component -> interface -> library for
   every framework actually delivered with the installation, generated at
   build time. It is the GROUND TRUTH for "does concrete component X really
   implement interface Y", and it is far larger than source 2 (roughly 885
   files / 73k pairs vs. 44 files / ~400 pairs). This is what proves, for
   example, that CATTPSSet implements CATITPSFactoryElementary (and
   CATIACaptureFactory) even though no CAADoc tutorial .dico happens to say
   so -- a fact that was previously undiscoverable by this tool and had to
   be found via manual grep of the shipped dictionary files.

Why this matters: during CAA API audits it's tempting to treat "not found
by --query" as proof an API doesn't exist or can't be obtained. That was
wrong at least three times in this project's history:
  - CATITPSSet::CreateCapture() genuinely isn't on CATITPSSet (it's on the
    separate CATITPSCaptureFactory interface -- refman and the header
    agree, so no mismatch there).
  - DfTPS_ItfTPSFactoryElementary (a plausible-looking enum value some
    knowledge docs invented) does not exist in the real CATTPSComponent
    enum at all -- only found by reading the SDK header itself, since the
    refman enum page has no way to show why a value is absent.
  - CATITPSFactoryElementary (a real interface, confirmed by both refman
    and the SDK header) has no documented "how do I get an instance"
    tutorial anywhere in CAADoc's *.edu samples -- but the shipped .dic
    dictionary (source 4) reveals CATTPSSet implements it directly, so the
    real access pattern is `pSet->QueryInterface(IID_CATITPSFactoryElementary, ...)`,
    the same pattern used for CATITPSCaptureFactory and CATITPSViewFactory.
The lesson: prefer --query's "SDK/refman mismatch" flag, the header-derived
method/enum list, and the shipped .dic "ground truth" implementer list over
refman/CAADoc .dico alone when something looks inconsistent or missing.

A reverse method-name index is also built (which types declare a method
with a given bare name), to answer "which interfaces have a SetColor
method" style questions without re-grepping CAADoc by hand.

KNOWN LIMITATION: refman htm pages are split into Public/Protected/Private
views, but this tool's htm parser only reads whichever "Method Index" block
is physically present in the page it fetched (usually Public). If a method
exists only in the Protected/Private view of a page that also has a Public
view section, it can be missed. The SDK header scan does not have this
limitation (it sees every `virtual ... = 0` in the class body regardless of
access section), so prefer the header-derived results when in doubt.

Output is written to cache/caadoc_index.json (gitignored, machine-local,
since it embeds absolute paths into the user's CATIA install and CAADoc
content itself is not redistributed). By default, --query/--search reuse
that cache when present instead of rescanning (rescanning ~6600 refman
files + ~5600 SDK headers + ~885 shipped .dic files takes a few seconds;
loading the cached JSON takes a fraction of that). Use --rebuild to force a
fresh scan, or --write to persist a fresh scan.

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


def find_catia_root():
    """Return the CATIA_INSTALL root (parent of CAADoc, and the directory
    under which every framework's PublicInterfaces/*.h SDK headers live)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from skills.env import CAAEnvironment

    env = CAAEnvironment()
    env.load_config()
    catia = env.config.get("CATIA_INSTALL", "")
    if not catia:
        return None
    root = Path(catia)
    return root if root.is_dir() else None


def find_caadoc_root():
    root = find_catia_root()
    if not root:
        return None
    caadoc = root / "CAADoc"
    return caadoc if caadoc.is_dir() else None


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


def find_dictionary_dir(catia_root: Path):
    """Return <CATIA_INSTALL>/<arch>/code/dictionary, trying the same
    architecture directory names catia_detector.py knows about. This is the
    shipped-product TIE dictionary (component -> interface -> library),
    generated at build time for every framework actually delivered with the
    installation -- not just the ~40 CAADoc tutorial frameworks that ship a
    **/*.dico file. It is dramatically larger (roughly 885 files / 73k
    component/interface pairs vs. 44 files / ~400 pairs for the CAADoc
    .dico set) and is the authoritative answer to "does shipped component X
    really implement interface Y" -- e.g. it is what proves CATTPSSet
    implements CATITPSFactoryElementary (and CATIACaptureFactory), which no
    CAADoc tutorial .dico happens to mention."""
    if catia_root is None:
        return None
    for arch in ("intel_a", "win_b64", "win64", "amd64_win64"):
        d = catia_root / arch / "code" / "dictionary"
        if d.is_dir():
            return d
    return None


def scan_sdk_dictionaries(catia_root: Path):
    """Parse the shipped product's component -> interface -> library `.dic`
    files (NOT the CAADoc tutorial `.dico` files scanned by scan_dico).

    Lines look like:
        CATTPSSet    CATITPSFactoryElementary    libCATTPSEDITORUI
    with occasional extra trailing tokens (a library alias, a '##' comment,
    etc.) that are ignored -- only the first three whitespace-separated
    tokens are taken as component/interface/library. The library field is
    sometimes "Delegated" instead of a real lib name for compiler-generated
    interface delegation; that is kept as-is rather than filtered out.
    """
    dict_dir = find_dictionary_dir(catia_root)
    if not dict_dir:
        return []
    entries = []
    for df in dict_dir.glob("*.dic"):
        try:
            text = df.read_text(encoding="latin-1", errors="replace")
        except Exception:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                continue
            parts = stripped.split()
            if len(parts) < 3:
                continue
            component, interface, library = parts[0], parts[1], parts[2]
            entries.append({
                "component": component,
                "interface": interface,
                "library": library,
                "file": str(df),
            })
    return entries


# ---------------------------------------------------------------------------
# SDK header scanning (the actual C++ headers the refman htm is generated
# from). This is the most authoritative source available locally: it can
# reveal enum-value -> interface mappings and complete method lists that the
# generated refman pages omit or never had.
# ---------------------------------------------------------------------------

_HDR_CLASS_RE = re.compile(
    r'class\s+(?:ExportedBy\w+\s+)?(CATI\w+|CAT\w+)\s*(?::\s*public\s+[\w:]+)?\s*\{',
    re.MULTILINE,
)
# Matches "virtual <ret> Name(args) [const] = 0;" pure-virtual declarations.
_HDR_METHOD_RE = re.compile(
    r'virtual\s+[\w:<>*&,\s]+?\s+(\w+)\s*\(([^;{}]*?)\)\s*(?:const\s*)?=\s*0\s*;',
    re.MULTILINE,
)
_HDR_ENUM_RE = re.compile(r'enum\s+(\w+)?\s*\{([^}]*)\}', re.MULTILINE)
_HDR_ENUM_VALUE_RE = re.compile(
    r'^\s*(\w+)\s*(?:=\s*[^,/]+)?\s*,?\s*(?://\s*(.*))?$'
)


def _find_matching_brace(text: str, open_brace_pos: int) -> int:
    """Given the index right after an opening '{', return the index of the
    matching closing '}' (naive depth counter; good enough for header decls
    without string/char literals containing braces, which CAA headers don't
    use in class bodies)."""
    depth = 1
    i = open_brace_pos
    n = len(text)
    while i < n and depth > 0:
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    return i


def parse_header_file(path: Path, framework: str):
    """Extract interface classes (name + pure-virtual method signatures) and
    enums (name + value list, keeping any trailing '// Comment' which is
    often the only place an enum value's real meaning is documented) from a
    single SDK header file."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return [], []

    classes = []
    for m in _HDR_CLASS_RE.finditer(text):
        name = m.group(1)
        body_end = _find_matching_brace(text, m.end())
        body = text[m.end():body_end]
        methods = []
        for meth_m in _HDR_METHOD_RE.finditer(body):
            meth_name = meth_m.group(1)
            args = " ".join(meth_m.group(2).split())
            methods.append(f"{meth_name}({args})")
        classes.append({
            "name": name,
            "framework": framework,
            "file": str(path),
            "methods": methods,
        })

    enums = []
    for m in _HDR_ENUM_RE.finditer(text):
        enum_name = m.group(1)
        if not enum_name:
            continue
        values = []
        for line in m.group(2).splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            vm = _HDR_ENUM_VALUE_RE.match(line)
            if not vm:
                continue
            value_name = vm.group(1)
            comment = (vm.group(2) or "").strip()
            values.append({"value": value_name, "comment": comment})
        if values:
            enums.append({
                "name": enum_name,
                "framework": framework,
                "file": str(path),
                "values": values,
            })

    return classes, enums


def scan_sdk_headers(catia_root: Path):
    """Scan every */PublicInterfaces/*.h under the CATIA install for
    interface class declarations and enum definitions."""
    header_classes = []
    header_enums = []
    for hf in catia_root.glob("*/PublicInterfaces/*.h"):
        framework = hf.parent.parent.name
        classes, enums = parse_header_file(hf, framework)
        header_classes.extend(classes)
        header_enums.extend(enums)
    return header_classes, header_enums


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


def build_index(caadoc_root: Path, catia_root=None, scan_headers: bool = True):
    t0 = time.time()
    refman_records = scan_refman(caadoc_root)
    dico_entries = scan_dico(caadoc_root)
    header_classes, header_enums = ([], [])
    sdk_dic_entries = []
    if catia_root is not None:
        if scan_headers:
            header_classes, header_enums = scan_sdk_headers(catia_root)
        sdk_dic_entries = scan_sdk_dictionaries(catia_root)
    elapsed = time.time() - t0

    by_name = {}
    for rec in refman_records:
        by_name.setdefault(rec["name"], []).append(rec)

    implements_by_interface = {}
    implements_by_component = {}
    for e in dico_entries:
        implements_by_interface.setdefault(e["interface"], []).append(e["component"])
        implements_by_component.setdefault(e["component"], []).append(e["interface"])

    # The shipped-product dictionary is a separate, much larger source; keep
    # it in its own maps (rather than merging into implements_by_*) so query()
    # can label which source a hit came from -- CAADoc .dico entries are a
    # curated subset used in official tutorials, while the shipped .dic
    # entries are the ground truth for what's actually compiled and
    # delivered.
    sdk_implements_by_interface = {}
    sdk_implements_by_component = {}
    for e in sdk_dic_entries:
        sdk_implements_by_interface.setdefault(e["interface"], []).append(e["component"])
        sdk_implements_by_component.setdefault(e["component"], []).append(e["interface"])

    methods_by_name = build_method_index(refman_records)

    headers_by_name = {}
    for rec in header_classes:
        headers_by_name.setdefault(rec["name"], []).append(rec)

    enums_by_name = {}
    for rec in header_enums:
        enums_by_name.setdefault(rec["name"], []).append(rec)

    return {
        "meta": {
            "caadoc_root": str(caadoc_root),
            "catia_root": str(catia_root) if catia_root else None,
            "refman_type_count": len(refman_records),
            "dico_entry_count": len(dico_entries),
            "sdk_dic_entry_count": len(sdk_dic_entries),
            "method_name_count": len(methods_by_name),
            "header_class_count": len(header_classes),
            "header_enum_count": len(header_enums),
            "build_seconds": round(elapsed, 2),
        },
        "types": refman_records,
        "types_by_name": by_name,
        "dico_entries": dico_entries,
        "implements_by_interface": implements_by_interface,
        "implements_by_component": implements_by_component,
        "sdk_dic_entries": sdk_dic_entries,
        "sdk_implements_by_interface": sdk_implements_by_interface,
        "sdk_implements_by_component": sdk_implements_by_component,
        "methods_by_name": methods_by_name,
        "header_classes": header_classes,
        "headers_by_name": headers_by_name,
        "header_enums": header_enums,
        "enums_by_name": enums_by_name,
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


def _method_base_names(methods):
    return {m.split("(", 1)[0].strip() for m in methods}


def _print_header_cross_check(index: dict, name: str, refman_methods):
    """Compare refman-derived methods against the real SDK header (if any
    class with this name was found there) and flag any mismatch. This is
    what catches cases like a method the refman page's parser missed
    (Protected/Private view) or, more importantly, a method that was
    invented in downstream knowledge docs and never existed in either
    source."""
    header_recs = index.get("headers_by_name", {}).get(name)
    if not header_recs:
        return

    for hrec in header_recs:
        header_methods = hrec["methods"]
        print(f"\nSDK header {hrec['file']}:")
        if header_methods:
            print(f"  methods ({len(header_methods)}):")
            for m in header_methods:
                print(f"    o {m}")
        else:
            print("  (no pure-virtual methods found in class body)")

        refman_base = _method_base_names(refman_methods) if refman_methods else set()
        header_base = _method_base_names(header_methods)
        only_in_refman = refman_base - header_base
        only_in_header = header_base - refman_base
        if only_in_refman or only_in_header:
            print("  *** SDK/refman mismatch ***")
            if only_in_refman:
                print(f"    in refman but NOT in SDK header: {sorted(only_in_refman)}")
            if only_in_header:
                print(f"    in SDK header but NOT in refman: {sorted(only_in_header)}")
        else:
            print("  (SDK header agrees with refman method list)")


def query(index: dict, name: str):
    matches = index["types_by_name"].get(name)
    if not matches:
        # case-insensitive fallback
        lname = name.lower()
        matches = [
            rec for rec in index["types"] if rec["name"].lower() == lname
        ]
    refman_methods_for_crosscheck = None
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
            refman_methods_for_crosscheck = rec["methods"]
    else:
        print(f"No refman type named '{name}' found.")

    implementers = index["implements_by_interface"].get(name)
    if implementers:
        print(f"\nComponents declaring implementation of '{name}' (CAADoc .dico):")
        for c in sorted(set(implementers)):
            print(f"  - {c}")

    implemented = index["implements_by_component"].get(name)
    if implemented:
        print(f"\nInterfaces implemented by component '{name}' (CAADoc .dico):")
        for i in sorted(set(implemented)):
            print(f"  - {i}")

    sdk_implementers = index.get("sdk_implements_by_interface", {}).get(name)
    if sdk_implementers:
        print(f"\nComponents declaring implementation of '{name}' (shipped .dic, ground truth):")
        for c in sorted(set(sdk_implementers)):
            print(f"  - {c}")

    sdk_implemented = index.get("sdk_implements_by_component", {}).get(name)
    if sdk_implemented:
        print(f"\nInterfaces implemented by component '{name}' (shipped .dic, ground truth):")
        for i in sorted(set(sdk_implemented)):
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

    # Cross-check against the real SDK header, and/or show the header alone
    # if refman had no match for this name at all (e.g. an enum).
    _print_header_cross_check(index, name, refman_methods_for_crosscheck)

    enum_hits = index.get("enums_by_name", {}).get(name)
    if enum_hits:
        for erec in enum_hits:
            print(f"\nSDK header enum {erec['name']} [{erec['framework']}] ({erec['file']}):")
            for v in erec["values"]:
                comment = f"  // {v['comment']}" if v["comment"] else ""
                print(f"  {v['value']}{comment}")

    if (not matches and not implementers and not implemented and not sdk_implementers
            and not sdk_implemented and not method_hits
            and not index.get("headers_by_name", {}).get(name) and not enum_hits):
        print("(no match in refman types, .dico/.dic entries, method index, SDK headers, or SDK enums)")


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

    print(f"\n--- Component/.dico matches for '{pattern}' (CAADoc tutorials) ---")
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

    print(f"\n--- Component/.dic matches for '{pattern}' (shipped product, ground truth) ---")
    count = 0
    seen_pairs = set()
    for e in index.get("sdk_dic_entries", []):
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
        print("  (no shipped .dic matches)")

    print(f"\n--- SDK header enum value matches for '{pattern}' ---")
    count = 0
    for erec in index.get("header_enums", []):
        for v in erec["values"]:
            if pat in v["value"].lower() or pat in (v["comment"] or "").lower():
                comment = f"  // {v['comment']}" if v["comment"] else ""
                print(f"  {erec['name']:30s} [{erec['framework']}] :: {v['value']}{comment}")
                count += 1
                if count >= limit:
                    break
        if count >= limit:
            print(f"  ... (truncated at {limit}; narrow the pattern for more)")
            break
    if count == 0:
        print("  (no SDK header enum matches)")


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
    p.add_argument("--query", action="append", default=[], help="Look up a type/interface/component/method/enum name (repeatable)")
    p.add_argument("--search", action="append", default=[], help="Substring search over type names, method signatures, .dico entries, and SDK enum values (repeatable)")
    p.add_argument("--repl", action="store_true", help="Enter an interactive query/search loop after loading/building the index")
    p.add_argument("--no-headers", action="store_true", help="Skip scanning the SDK PublicInterfaces/*.h headers (refman + .dico + shipped .dic only, faster but loses method/enum cross-checking)")
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
                f"{meta.get('sdk_dic_entry_count', 0)} shipped .dic entries, "
                f"{meta.get('method_name_count', '?')} unique method names, "
                f"{meta.get('header_class_count', 0)} SDK header classes, "
                f"{meta.get('header_enum_count', 0)} SDK header enums)"
            )

    if index is None:
        root = find_caadoc_root()
        if not root:
            print("ERROR: Cannot locate CAADoc (check CATIA_INSTALL config)", file=sys.stderr)
            sys.exit(1)
        catia_root = find_catia_root()
        print(f"Scanning CAADoc at {root} ...")
        if catia_root:
            if not args.no_headers:
                print(f"Scanning SDK headers under {catia_root} ...")
            print(f"Scanning shipped .dic dictionaries under {catia_root} ...")
        index = build_index(root, catia_root, scan_headers=not args.no_headers)
        meta = index["meta"]
        print(
            f"Parsed {meta['refman_type_count']} refman types, "
            f"{meta['dico_entry_count']} .dico entries, "
            f"{meta.get('sdk_dic_entry_count', 0)} shipped .dic entries, "
            f"{meta['header_class_count']} SDK header classes, and "
            f"{meta['header_enum_count']} SDK header enums in {meta['build_seconds']}s"
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
