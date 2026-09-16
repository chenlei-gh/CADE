"""
Count Knowledge Assets — single source of truth for README's asset numbers
==========================================================================
One Knowledge Asset = one curated .md file living in a formal asset root.

Rule model (positive, no exclusion list):
    formal asset root -> *.md -> basename != README.md -> classify

A file is counted iff its path falls under one of ASSET_ROOTS. Anything else
(CHANGELOG.md, docs/**, tests/**, templates/**, cache/**, catalog/) is simply
not under a root, so it is never counted — there is no per-file deny list to
keep in sync. Adding or removing assets (or whole subdirectories) changes the
count automatically.

Classification is FIRST MATCH over ASSET_ROOTS, so each file lands in exactly
one bucket. The order is therefore significant: specific subdirectories are
listed before their parent "knowledge" fallback.

  C  capabilities/            P  playbooks/        PB patterns/
  E  examples/                FW knowledge/frameworks/
  PH knowledge/philosophy/    FP knowledge/failure_patterns/
  K  knowledge/** (everything remaining, so C+P+PB+E+FW+PH+FP+K = total)

Why K is the remainder rather than all of knowledge/: philosophy and
failure_patterns live INSIDE knowledge/. Counting knowledge/ wholesale while
also listing PH/FP would double-count those 20 files and inflate the total
from 241 to 261. Making K the remainder keeps every file in exactly one
bucket while preserving the per-category breakdown.

Scope boundary: docs/examples/*.md are documentation, NOT knowledge assets.
If they should ever count, promote them to a formal asset root first — do not
widen this script's scope, or the "what counts" question reopens and the drift
this script exists to kill comes straight back.

Numbers only. This script never edits README.md or any other file, so the
count and the document stay decoupled until both are proven stable.

Usage:
    python tools/count_knowledge_assets.py [--json]

Pure stdlib.
"""

import argparse
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

# Order is significant: first match wins (see module docstring).
ASSET_ROOTS = [
    ("C", "capabilities"),
    ("P", "playbooks"),
    ("PB", "patterns"),
    ("E", "examples"),
    ("FW", "knowledge/frameworks"),
    ("PH", "knowledge/philosophy"),
    ("FP", "knowledge/failure_patterns"),
    ("K", "knowledge"),
]

# Catalog order for display (matches README's breakdown convention).
DISPLAY_ORDER = ["K", "P", "C", "PB", "FW", "E", "PH", "FP"]

# Documentation/registry files are not assets wherever they sit.
IGNORED_BASENAMES = {"README.md"}


def _classify(rel: Path) -> str:
    """Asset category for a repo-relative path, or "" if it is not an asset.

    Single exit point for the "what counts" rule: non-.md, documentation
    basenames, and paths outside every asset root all answer "".
    """
    if rel.suffix.lower() != ".md":
        return ""
    if rel.name in IGNORED_BASENAMES:
        return ""
    parts = rel.parts
    for key, root in ASSET_ROOTS:
        root_parts = tuple(root.split("/"))
        if parts[:len(root_parts)] == root_parts:
            return key
    return ""


def count(skill_root: Path = SKILL_ROOT) -> dict:
    """Return {"total": N, "counts": {key: N}} over formal asset roots."""
    counts = {key: 0 for key, _ in ASSET_ROOTS}

    for md in skill_root.rglob("*.md"):
        if "__pycache__" in md.parts or ".pytest_cache" in md.parts:
            continue
        try:
            rel = md.relative_to(skill_root)
        except ValueError:
            continue
        key = _classify(rel)
        if key:
            counts[key] += 1

    return {"total": sum(counts.values()), "counts": counts}


def format_breakdown(counts: dict) -> str:
    """README-style '52K + 14P + ...' -- zero-count categories are omitted."""
    parts = [f"{counts[k]}{k}" for k in DISPLAY_ORDER if counts.get(k)]
    return " + ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Count CADE knowledge assets")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    ap.add_argument("--skill-root", default=None, help="override skill root")
    args = ap.parse_args()

    root = Path(args.skill_root).resolve() if args.skill_root else SKILL_ROOT
    if not (root / "catalog").is_dir():
        print(f"error: not a skill root: {root}", file=sys.stderr)
        return 2

    result = count(root)
    counts = result["counts"]

    if args.json:
        print(json.dumps({
            "total": result["total"],
            "breakdown": format_breakdown(counts),
            "counts": counts,
            "skill_root": str(root),
        }, ensure_ascii=False, indent=2))
        return 0

    print("=" * 60)
    print("  CADE Knowledge Assets")
    print("=" * 60)
    for key, rel in ASSET_ROOTS:
        label = "knowledge/** (rest)" if key == "K" else rel
        print(f"  {key:>3}  {label:<26} {counts[key]:>5}")
    print("-" * 60)
    print(f"  {'':>3}  {'Total':<26} {result['total']:>5}")
    print("=" * 60)
    print(f"  {result['total']} Knowledge Assets")
    print(f"  ({format_breakdown(counts)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
