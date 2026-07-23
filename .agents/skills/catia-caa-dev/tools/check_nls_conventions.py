#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NLS Convention Checker for CATIA CAA Workspaces
================================================
Scans a CAA workspace for the three historical NLS mistakes that make
tools stay English-only in a Chinese CATIA session:

  1. `*_Chinese.CATNls` flat files — CATIA never loads these.
     Correct convention: `msgcatalog/Simplified_Chinese/<same-name>.CATNls`.
  2. Hardcoded `SetTitle("literal")` in dialog source — overrides CATIA's
     automatic NLS lookup. Correct: zero-code NLS via control-path keys
     (`FrameId.LabelId.Title`) in the dialog's own `<ClassName>.CATNls`.
  3. English catalogs without a `Simplified_Chinese/` counterpart.

Usage:
    python check_nls_conventions.py <workspace_path>          # report only
    python check_nls_conventions.py <workspace_path> --fix    # auto-fix #1 (move files)
    python check_nls_conventions.py <workspace_path> --json   # machine-readable

Exit code: 0 = clean, 1 = issues found, 2 = usage error.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Matches SetTitle("...") with a string literal (not a variable / NLS key expr)
SET_TITLE_RE = re.compile(r'SetTitle\s*\(\s*(?:CATUnicodeString\s*\(\s*)?"([^"]+)"')
# Lines that are commented out should not be flagged
COMMENT_RE = re.compile(r"^\s*(//|\*)")


# Directories that are never actionable sources: CADE backups and the
# Runtime View (win_b64/resources is a sync target of the .edu/CNext source).
SKIP_DIR_NAMES = {".caa_backups", "__pycache__"}


def _is_skippable(p: Path, ws: Path) -> bool:
    parts = set(p.relative_to(ws).parts)
    if parts & SKIP_DIR_NAMES:
        return True
    # Runtime View: <ws>/<arch>/resources/msgcatalog — synced from .edu/CNext
    if "win_b64" in parts or "win64_b64" in parts:
        return True
    return False


def scan_workspace(ws: Path) -> dict:
    issues = {"flat_chinese": [], "hardcoded_settitle": [], "missing_zh": []}

    # ── 1. Flat *_Chinese.CATNls files ──────────────────────────────
    for f in ws.rglob("*_Chinese.CATNls"):
        if _is_skippable(f, ws):
            continue
        # Only flag ones directly under a msgcatalog dir (the broken layout)
        if f.parent.name.lower() == "msgcatalog":
            target = f.parent / "Simplified_Chinese" / f.name.replace(
                "_Chinese.CATNls", ".CATNls"
            )
            issues["flat_chinese"].append(
                {"file": str(f), "fix_target": str(target), "target_exists": target.exists()}
            )

    # ── 2. Hardcoded SetTitle("...") in dialog sources ──────────────
    # Heuristic: only scan .cpp files that include CATDlg headers (real dialogs),
    # skip edu samples / third-party code outside *.m/src.
    for src_dir in ws.rglob("*.m"):
        if not src_dir.is_dir():
            continue
        src = src_dir / "src"
        if not src.exists():
            continue
        for cpp in src.glob("*.cpp"):
            try:
                text = cpp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "CATDlg" not in text:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if COMMENT_RE.match(line):
                    continue
                m = SET_TITLE_RE.search(line)
                if m:
                    issues["hardcoded_settitle"].append(
                        {"file": str(cpp), "line": i, "literal": m.group(1)}
                    )

    # ── 3. English catalogs missing a Simplified_Chinese counterpart ─
    for msg in ws.rglob("msgcatalog"):
        if not msg.is_dir() or _is_skippable(msg, ws):
            continue
        # Skip nested msgcatalog inside a language dir (not a thing, but be safe)
        if msg.parent.name in ("Simplified_Chinese", "Chinese"):
            continue
        zh_dir = msg / "Simplified_Chinese"
        for en_cat in msg.glob("*.CATNls"):
            if en_cat.stem.endswith("_Chinese"):
                continue  # already reported in #1
            if not (zh_dir / en_cat.name).exists():
                issues["missing_zh"].append(
                    {
                        "file": str(en_cat),
                        "expected": str(zh_dir / en_cat.name),
                    }
                )

    return issues


def apply_fixes(ws: Path, issues: dict) -> list:
    """Auto-fix #1: move flat *_Chinese.CATNls into Simplified_Chinese/."""
    fixed = []
    for item in issues["flat_chinese"]:
        src = Path(item["file"])
        dst = Path(item["fix_target"])
        if item["target_exists"]:
            continue  # don't clobber an existing zh catalog
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        fixed.append({"moved": str(src), "to": str(dst)})
    return fixed


def main() -> int:
    ap = argparse.ArgumentParser(description="CAA workspace NLS convention checker")
    ap.add_argument("workspace", help="CAA workspace root (contains *.edu frameworks)")
    ap.add_argument("--fix", action="store_true", help="move *_Chinese.CATNls into Simplified_Chinese/")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    ws = Path(args.workspace)
    if not ws.is_dir():
        print(f"ERROR: not a directory: {ws}", file=sys.stderr)
        return 2

    issues = scan_workspace(ws)
    total = sum(len(v) for v in issues.values())

    fixed = []
    if args.fix and issues["flat_chinese"]:
        fixed = apply_fixes(ws, issues)

    if args.json:
        print(json.dumps({"workspace": str(ws), "issue_count": total, "issues": issues, "fixed": fixed}, ensure_ascii=False, indent=2))
        return 1 if total and not fixed else (0 if not total else 1)

    print(f"NLS convention scan: {ws}")
    print("=" * 70)

    if issues["flat_chinese"]:
        print(f"\n[1] Flat *_Chinese.CATNls files (CATIA never loads these): {len(issues['flat_chinese'])}")
        for it in issues["flat_chinese"]:
            flag = " [target exists, skipped by --fix]" if it["target_exists"] else ""
            print(f"  - {it['file']}\n    -> should be: {it['fix_target']}{flag}")

    if issues["hardcoded_settitle"]:
        print(f"\n[2] Hardcoded SetTitle literals (override NLS, manual fix needed): {len(issues['hardcoded_settitle'])}")
        for it in issues["hardcoded_settitle"]:
            print(f"  - {it['file']}:{it['line']}  \"{it['literal']}\"")
        print("    Hint: remove the SetTitle call and add a control-path key")
        print("    (FrameId.ControlId.Title) to the dialog's <ClassName>.CATNls")
        print("    (+ Simplified_Chinese/<ClassName>.CATNls for Chinese).")

    if issues["missing_zh"]:
        print(f"\n[3] English catalogs without Simplified_Chinese counterpart: {len(issues['missing_zh'])}")
        for it in issues["missing_zh"]:
            print(f"  - {it['file']}\n    -> missing: {it['expected']}")

    if fixed:
        print(f"\n[FIX] Moved {len(fixed)} files into Simplified_Chinese/:")
        for f in fixed:
            print(f"  - {f['moved']} -> {f['to']}")

    print("\n" + "=" * 70)
    if total == 0:
        print("RESULT: CLEAN — all NLS conventions OK")
        return 0
    print(f"RESULT: {total} issue(s) found"
          + (f", {len(fixed)} auto-fixed" if fixed else " (run with --fix to auto-move flat Chinese catalogs)"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
