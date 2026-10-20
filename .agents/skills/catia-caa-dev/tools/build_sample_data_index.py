"""
Build SampleDataIndex — CATIA Built-in Sample & Test Data Index
================================================================
Scans CATIA installation directories (CAADoc test fixtures and
win_b64/startup catalog components) for binary sample models (.CATPart,
.CATProduct, .CATDrawing).

Design boundary (governance):
  - This builder records METADATA AND LOCATION ONLY (paths, size, kind,
    owning framework or startup domain).
  - It does NOT attempt to parse proprietary V5_CFV2 binary geometry or
    feature trees.
  - Answers "what sample file can I open/test against?", not "what
    parameters does this part contain?".

Output: cache/sample_data_index.json (gitignored, regenerated locally)

Usage:
    python tools/build_sample_data_index.py [--verbose]

Pure stdlib.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))


def find_catia_install() -> Path | None:
    """Locate CATIA installation directory via env or standard paths."""
    try:
        from env import CAAEnvironment
        env = CAAEnvironment()
        env.load_config()
        catia = env.config.get("CATIA_INSTALL", "")
        if catia and Path(catia).is_dir():
            return Path(catia)
    except Exception:
        pass

    for candidate in [
        r"C:\Program Files\Dassault Systemes\B28",
        r"C:\Program Files\Dassault Systemes\B27",
        r"C:\Program Files\Dassault Systemes\B26",
    ]:
        p = Path(candidate)
        if p.is_dir():
            return p
    return None


def cache_path() -> Path:
    return SKILL_ROOT / "cache" / "sample_data_index.json"


_EXT_MAP = {
    ".catpart": "part",
    ".catproduct": "product",
    ".catdrawing": "drawing",
}


def scan_samples(catia_root: Path, verbose: bool = False) -> dict:
    t0 = time.time()
    samples = []

    # ── 1. Scan CAADoc ──────────────────────────────────────────────
    caadoc_dir = catia_root / "CAADoc"
    if caadoc_dir.is_dir():
        for p in caadoc_dir.rglob("*"):
            ext = p.suffix.lower()
            kind = _EXT_MAP.get(ext)
            if not kind:
                continue

            try:
                rel_caadoc = p.relative_to(caadoc_dir).parts
                rel_root = p.relative_to(catia_root).as_posix()
                sz = p.stat().st_size
            except OSError:
                continue

            fw = rel_caadoc[0].replace(".edu", "") if rel_caadoc else ""
            category = rel_caadoc[1] if len(rel_caadoc) > 2 else ""

            samples.append({
                "name": p.name,
                "stem": p.stem,
                "kind": kind,
                "ext": ext,
                "rel_path": rel_root,
                "size_bytes": sz,
                "source": "caadoc",
                "framework": fw,
                "category": category,
            })

    # ── 2. Scan win_b64/startup ────────────────────────────────────
    startup_dir = catia_root / "win_b64" / "startup"
    if startup_dir.is_dir():
        for p in startup_dir.rglob("*"):
            ext = p.suffix.lower()
            kind = _EXT_MAP.get(ext)
            if not kind:
                continue

            try:
                rel_startup = p.relative_to(startup_dir).parts
                rel_root = p.relative_to(catia_root).as_posix()
                sz = p.stat().st_size
            except OSError:
                continue

            category = "/".join(rel_startup[:2]) if len(rel_startup) >= 2 else (rel_startup[0] if rel_startup else "")

            samples.append({
                "name": p.name,
                "stem": p.stem,
                "kind": kind,
                "ext": ext,
                "rel_path": rel_root,
                "size_bytes": sz,
                "source": "startup_catalog",
                "framework": "",
                "category": category,
            })

    # ── Build inverted lookups ──────────────────────────────────────
    by_kind = {"part": [], "product": [], "drawing": []}
    by_source = {"caadoc": [], "startup_catalog": []}
    by_framework = {}
    by_category = {}

    for idx, s in enumerate(samples):
        k = s["kind"]
        if k in by_kind:
            by_kind[k].append(idx)

        src = s["source"]
        if src in by_source:
            by_source[src].append(idx)

        fw = s.get("framework")
        if fw:
            by_framework.setdefault(fw, []).append(idx)

        cat = s.get("category")
        if cat:
            by_category.setdefault(cat, []).append(idx)

    # Sort samples by name for deterministic ordering
    meta = {
        "generated_at": datetime.now().isoformat(),
        "catia_install": str(catia_root),
        "total_count": len(samples),
        "by_kind_counts": {k: len(v) for k, v in sorted(by_kind.items())},
        "by_source_counts": {k: len(v) for k, v in sorted(by_source.items())},
        "framework_count": len(by_framework),
        "build_duration_sec": round(time.time() - t0, 2),
    }

    return {
        "meta": meta,
        "samples": samples,
        "by_kind": by_kind,
        "by_source": by_source,
        "by_framework": by_framework,
        "by_category": by_category,
    }


def main():
    parser = argparse.ArgumentParser(description="Build CATIA Sample Data Index")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress")
    args = parser.parse_args()

    catia_root = find_catia_install()
    if not catia_root:
        print("ERROR: CATIA installation not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning sample data in {catia_root} ...")
    data = scan_samples(catia_root, verbose=args.verbose)

    out = cache_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    meta = data["meta"]
    print(
        f"SampleDataIndex built: {meta['total_count']} files "
        f"({meta['by_kind_counts']}) in {meta['build_duration_sec']}s -> {out}"
    )


if __name__ == "__main__":
    main()
