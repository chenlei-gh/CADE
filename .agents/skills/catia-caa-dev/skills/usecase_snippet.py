"""
UseCase snippet reader — read-only window into official CAADoc samples
=======================================================================
The editor cannot open files under the CATIA install tree (they sit
outside the project). UseCaseIndex only records presence (which sample
mentions a token) plus a CAADoc-relative path. This module is the missing
read step: resolve that path, print a bounded source window, write nothing.

Boundary:
  - Read-only. Never creates, copies, or patches a file.
  - Presence is not a recommendation and not a verified call chain.
  - A miss means "no official sample found", not "the API does not exist".
  - Output is capped. This is not a full-file dump.

CLI:
  python skills/usecase_snippet.py --interface CATIVisProperties
  python skills/usecase_snippet.py --method SetPropertiesAtt --around 8
  python skills/usecase_snippet.py --example CAAMmrSetShowModeCmd --lines 40-90
  python skills/usecase_snippet.py --symbol CATNoShowAttr --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


DEFAULT_CONTEXT = 12
DEFAULT_MAX_HITS = 3
DEFAULT_MAX_LINES = 80
_TEXT_SUFFIXES = {".cpp", ".h", ".mk", ".catnls", ".catrsc"}


def resolve_caadoc_root(retrieval, skill_root: Path) -> Optional[Path]:
    """CAADoc root from the index meta, else CATIA_INSTALL/CAADoc.

    No hardcoded drive letters. A missing install returns None.
    """
    meta = {}
    try:
        meta = retrieval.usecase_index.get("meta", {}) or {}
    except Exception:
        meta = {}
    # Key present (even empty) means the index pinned a root. Do not
    # fall through to CATIA_INSTALL — a stale or missing pin is unavailable,
    # not a license to guess another install.
    if "caadoc_root" in meta:
        recorded = meta.get("caadoc_root") or ""
        if not recorded:
            return None
        root = Path(recorded)
        return root if root.is_dir() else None

    try:
        if str(skill_root) not in sys.path:
            sys.path.insert(0, str(skill_root))
        from skills.env import CAAEnvironment
        env = CAAEnvironment()
        env.load_config()
        catia = env.config.get("CATIA_INSTALL", "")
    except Exception:
        catia = ""
    if not catia:
        return None
    root = Path(catia) / "CAADoc"
    return root if root.is_dir() else None


def _safe_under(root: Path, rel: str) -> Optional[Path]:
    """Resolve a CAADoc-relative path and refuse anything outside the root."""
    if not rel or rel.startswith(("/", "\\")) or ".." in Path(rel).parts:
        return None
    try:
        full = (root / rel).resolve()
        full.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    if not full.is_file():
        return None
    return full


def select_examples(
    index: dict,
    *,
    interface: str = "",
    method: str = "",
    symbol: str = "",
    example: str = "",
    resource: str = "",
) -> List[dict]:
    """Pick index records. Empty filters do not mean 'every sample'."""
    examples = index.get("examples", {}) or {}
    resources = index.get("resources", {}) or {}
    picked: List[dict] = []
    seen = set()

    def _add_example(name: str) -> None:
        if name in seen or name not in examples:
            return
        seen.add(name)
        rec = examples[name]
        picked.append({
            "kind": "example",
            "name": name,
            "file": rec.get("file", ""),
            "interfaces": rec.get("interfaces", []),
            "methods": rec.get("methods", []),
            "symbols": rec.get("symbols", []),
        })

    def _add_resource(rel: str) -> None:
        if rel in seen or rel not in resources:
            return
        seen.add(rel)
        rec = resources[rel]
        picked.append({
            "kind": "resource",
            "name": rel,
            "file": rel,
            "resource_kind": rec.get("kind", ""),
            "framework": rec.get("framework", ""),
            "module": rec.get("module"),
        })

    if example:
        _add_example(example)
        # Disambiguated keys are "stem (module.m)". Accept a unique stem too.
        if example not in examples:
            stem_hits = [k for k in examples if k == example or k.startswith(example + " (")]
            for name in stem_hits:
                _add_example(name)
    if resource:
        _add_resource(resource)
        if resource not in resources:
            for rel, rec in resources.items():
                if Path(rel).name.lower() == resource.lower() or resource in rel:
                    _add_resource(rel)
                    if len(picked) >= DEFAULT_MAX_HITS:
                        break
    if interface:
        for name in index.get("by_interface", {}).get(interface, []):
            _add_example(name)
    if method:
        for name in index.get("by_method", {}).get(method, []):
            _add_example(name)
    if symbol:
        for name in index.get("by_symbol", {}).get(symbol, []):
            _add_example(name)
    return picked


def _read_lines(path: Path) -> Tuple[List[str], str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16", errors="replace")
        encoding = "utf-16"
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig", errors="replace")
        encoding = "utf-8-sig"
    else:
        # CAA NLS catalogs are GBK. UTF-8 is tried first; a hard failure
        # falls back. errors=replace keeps a window printable either way.
        try:
            text = raw.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            text = raw.decode("gbk", errors="replace")
            encoding = "gbk"
    return text.splitlines(), encoding


def _needle_lines(lines: Sequence[str], needles: Sequence[str]) -> List[int]:
    wanted = [n for n in needles if n]
    if not wanted:
        return []
    hits = []
    for i, line in enumerate(lines, start=1):
        if any(n in line for n in wanted):
            hits.append(i)
    return hits


def _windows(
    hit_lines: Sequence[int],
    *,
    context: int,
    line_count: int,
    explicit: Optional[Tuple[int, int]] = None,
) -> List[Tuple[int, int]]:
    if explicit:
        start, end = explicit
        start = max(1, start)
        end = min(line_count, max(start, end))
        return [(start, end)] if line_count else []
    if not hit_lines:
        if line_count <= 0:
            return []
        return [(1, min(line_count, DEFAULT_MAX_LINES))]
    merged: List[List[int]] = []
    for line in hit_lines:
        start = max(1, line - context)
        end = min(line_count, line + context)
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def _clip_windows(
    windows: Sequence[Tuple[int, int]],
    max_lines: int,
) -> Tuple[List[Tuple[int, int]], bool]:
    kept = []
    used = 0
    truncated = False
    for start, end in windows:
        span = end - start + 1
        if used >= max_lines:
            truncated = True
            break
        if used + span > max_lines:
            end = start + (max_lines - used) - 1
            truncated = True
        kept.append((start, end))
        used += end - start + 1
        if truncated:
            break
    if len(kept) < len(windows):
        truncated = True
    return kept, truncated


def read_snippet(
    retrieval,
    skill_root: Path,
    *,
    interface: str = "",
    method: str = "",
    symbol: str = "",
    example: str = "",
    resource: str = "",
    lines: str = "",
    context: int = DEFAULT_CONTEXT,
    max_hits: int = DEFAULT_MAX_HITS,
    max_lines: int = DEFAULT_MAX_LINES,
) -> dict:
    """Resolve official samples and return bounded source windows.

    status:
      ok                  — at least one window printed from disk
      not_found           — index has no matching sample
      source_unavailable  — index hit, but CAADoc root/file is not readable
    """
    index = retrieval.usecase_index or {}
    selected = select_examples(
        index,
        interface=interface,
        method=method,
        symbol=symbol,
        example=example,
        resource=resource,
    )
    query = {
        "interface": interface,
        "method": method,
        "symbol": symbol,
        "example": example,
        "resource": resource,
    }
    if not selected:
        return {
            "status": "not_found",
            "message": "No official example found",
            "query": query,
            "hits": [],
            "note": "A miss is not evidence that the API does not exist.",
        }

    root = resolve_caadoc_root(retrieval, skill_root)
    if root is None:
        return {
            "status": "source_unavailable",
            "message": "CAADoc root not found. Index has hits but source cannot be read.",
            "query": query,
            "match_count": len(selected),
            "matches": [item["name"] for item in selected[:max_hits]],
            "hits": [],
        }

    explicit = _parse_lines(lines)
    needles = [interface, method, symbol]
    shown = selected[:max_hits]
    hits = []
    for item in shown:
        full = _safe_under(root, item.get("file", ""))
        if full is None:
            hits.append({
                "name": item["name"],
                "file": item.get("file", ""),
                "status": "source_unavailable",
                "message": "Indexed path is missing or outside CAADoc.",
            })
            continue
        if full.suffix.lower() not in _TEXT_SUFFIXES and item["kind"] != "example":
            hits.append({
                "name": item["name"],
                "file": item.get("file", ""),
                "status": "skipped",
                "message": "Not a text sample.",
            })
            continue
        try:
            src_lines, encoding = _read_lines(full)
        except OSError as exc:
            hits.append({
                "name": item["name"],
                "file": item.get("file", ""),
                "status": "source_unavailable",
                "message": str(exc),
            })
            continue
        matched = _needle_lines(src_lines, needles)
        windows = _windows(
            matched,
            context=context,
            line_count=len(src_lines),
            explicit=explicit,
        )
        windows, truncated = _clip_windows(windows, max_lines)
        fragments = []
        for start, end in windows:
            fragments.append({
                "start": start,
                "end": end,
                "text": "\n".join(
                    f"{n:5d}|{src_lines[n - 1]}" for n in range(start, end + 1)
                ),
            })
        hits.append({
            "name": item["name"],
            "kind": item["kind"],
            "file": item.get("file", ""),
            "path": str(full),
            "encoding": encoding,
            "line_count": len(src_lines),
            "matched_lines": matched[:20],
            "truncated": truncated,
            "status": "ok",
            "fragments": fragments,
        })

    readable = [h for h in hits if h.get("status") == "ok"]
    status = "ok" if readable else "source_unavailable"
    return {
        "status": status,
        "query": query,
        "match_count": len(selected),
        "shown": len(shown),
        "omitted": max(0, len(selected) - len(shown)),
        "caadoc_root": str(root),
        "read_only": True,
        "note": (
            "Source window from an official CAADoc sample. "
            "Presence is not a recommendation and not a verified call chain."
        ),
        "hits": hits,
    }


def _parse_lines(spec: str) -> Optional[Tuple[int, int]]:
    text = (spec or "").strip()
    if not text:
        return None
    if "-" not in text:
        n = int(text)
        return n, n
    left, right = text.split("-", 1)
    return int(left), int(right)


def format_text(result: dict) -> str:
    status = result.get("status")
    if status == "not_found":
        return "NOT-FOUND  No official example found\n"
    lines = [
        f"status={status}  matches={result.get('match_count', 0)}  "
        f"shown={result.get('shown', 0)}  omitted={result.get('omitted', 0)}",
    ]
    if result.get("message") and status != "ok":
        lines.append(result["message"])
    for hit in result.get("hits", []):
        lines.append("")
        lines.append(
            f"## {hit.get('name')}  [{hit.get('status')}]  {hit.get('file', '')}"
        )
        if hit.get("status") != "ok":
            lines.append(hit.get("message", ""))
            continue
        if hit.get("truncated"):
            lines.append(f"truncated=true  file_lines={hit.get('line_count')}")
        for frag in hit.get("fragments", []):
            lines.append(f"--- L{frag['start']}-L{frag['end']} ---")
            lines.append(frag.get("text", ""))
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print a read-only source window from an official CAADoc sample.",
    )
    parser.add_argument("--interface", default="", help="CATI* include token")
    parser.add_argument("--method", default="", help="Method-call token")
    parser.add_argument("--symbol", default="", help="CAT* symbol / enum token")
    parser.add_argument("--example", default="", help="Example key or .cpp stem")
    parser.add_argument("--resource", default="", help="CAADoc-relative resource path or file name")
    parser.add_argument("--lines", default="", help="Explicit 1-based range, e.g. 40-90")
    parser.add_argument("--around", type=int, default=DEFAULT_CONTEXT, help="Context lines around a hit")
    parser.add_argument("--max-hits", type=int, default=DEFAULT_MAX_HITS)
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args(argv)

    if not any((args.interface, args.method, args.symbol, args.example, args.resource)):
        parser.error("one of --interface/--method/--symbol/--example/--resource is required")

    skill_root = Path(__file__).resolve().parent.parent
    if str(skill_root) not in sys.path:
        sys.path.insert(0, str(skill_root))
    skills_dir = skill_root / "skills"
    if str(skills_dir) not in sys.path:
        sys.path.insert(0, str(skills_dir))
    from retrieval import get_retrieval

    result = read_snippet(
        get_retrieval(skill_root),
        skill_root,
        interface=args.interface,
        method=args.method,
        symbol=args.symbol,
        example=args.example,
        resource=args.resource,
        lines=args.lines,
        context=max(0, args.around),
        max_hits=max(1, args.max_hits),
        max_lines=max(1, args.max_lines),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_text(result), end="")
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
