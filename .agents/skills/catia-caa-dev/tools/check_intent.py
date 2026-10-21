#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CADE Intent Gate -- declarative checkpoint for controlled-asset commits
=======================================================================

WHY THIS EXISTS
---------------
``AGENTS.md`` section 3 already requires an agent to *declare* intent before
hand-editing a CADE controlled asset (.cpp/.h/Imakefile.mk/IdentityCard.xml/
.dico/.CATNls/.CATRsc).  Section 4 admits that rule had no teeth: the
Provenance Guard records provenance but never blocks anything, so an
undeclared hand edit left no artifact a later reader could check.

This tool gives that declaration a machine-checkable form.  It gates
*commits*, not *editors*: it never tries to guess who touched a file, only
whether the change was declared.

WHAT IS CHECKED
---------------
Only paths staged for the current commit, and only those the Provenance
Guard already classifies as controlled assets.  Classification is imported
from ``skills/provenance_guard.py`` on purpose -- a second, drifting copy of
the rules would be worse than no gate at all.  Everything else
(``docs/*.md``, ``*.py``, build output under ``win_b64``) is out of scope and
never inspected.

HOW A CHANGE GETS DECLARED
--------------------------
A) Commit-message trailer -- one line the author is writing a message
   anyway, and it travels with history::

       Fix flatten degenerate branch

       CADE-Intent: hand-tuned the degenerate branch; CADE has no capability

   ``CADE-Intent-Files: a/b.cpp, c/d.h`` narrows the claim to those paths.
   Omitting it covers every controlled asset in *this one commit*.

B) ``<workspace>/.cade/intent/*.json`` -- a reusable, local claim::

       {"schema_version": 1, "kind": "manual", "author": "chenlei",
        "reason": "...", "files": ["a/b.cpp"],
        "expires_at": "2026-11-01T00:00:00"}

   ``kind`` is ``manual`` (an authored declaration) or ``cade`` (a ChangeSet
   CADE recorded; ``rollback_id`` is kept for traceability).  A claim that
   sets neither ``files`` nor ``expires_at`` is rejected: it would silently
   bless every future edit forever.

FAIL-OPEN CONTRACT
------------------
A gate that locks a repository because of its own breakage is worse than no
gate.  Missing classifier, unusable index, non-git directory, or any internal
error yields exit code 0 with a DEGRADED verdict.  Only a readable index
containing genuinely undeclared controlled assets yields BLOCK.

USAGE
-----
    python check_intent.py --workspace <ws>
    python check_intent.py --workspace <ws> --commit-msg-file .git/COMMIT_EDITMSG
    python check_intent.py --workspace <ws> --files a.cpp b.h --json
    python check_intent.py --workspace <ws> --bless manual --reason "..."

Exit codes: 0 = allowed (PASS / WARN / DEGRADED)
            1 = BLOCK (undeclared controlled assets)
            2 = gate could not evaluate (callers should fail open)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1
INTENT_SUBDIR = (".cade", "intent")

# Matches "CADE-Intent: ..." and "CADE-Intent-Files: ..." (case-insensitive).
TRAILER_RE = re.compile(r"^(cade-intent(?:-files)?)\s*:\s*(.*)$", re.IGNORECASE)

_PROVENANCE: Optional[tuple] = None


# ─── Authoritative asset classification ──────────────────────────────


def _provenance():
    """Return (is_controlled_source_asset, config_or_error).

    Imported lazily and cached: this module must stay importable (and the CLI
    runnable) even if ``provenance_guard`` is missing, because the gate is
    required to fail open rather than block.
    """
    global _PROVENANCE
    if _PROVENANCE is None:
        sys.path.insert(0, str(SKILL_ROOT / "skills"))
        try:
            from provenance_guard import (  # noqa: WPS433 (deliberate late import)
                DEFAULT_ASSET_CONFIG,
                is_controlled_source_asset,
            )

            _PROVENANCE = (is_controlled_source_asset, DEFAULT_ASSET_CONFIG)
        except Exception as exc:  # pragma: no cover - only when the skill is broken
            _PROVENANCE = (None, exc)
    return _PROVENANCE


# ─── Path helpers ────────────────────────────────────────────────────


def normalize_path(path) -> str:
    """Normalize to a workspace-relative POSIX string for comparison."""
    p = str(path).replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def to_relative(raw, workspace: Path) -> str:
    """Best-effort conversion of an absolute or relative path to workspace-relative."""
    p = Path(str(raw).replace("\\", "/"))
    try:
        if p.is_absolute():
            return p.resolve().relative_to(workspace.resolve()).as_posix()
    except (ValueError, OSError):
        pass
    return normalize_path(raw)


# ─── Git index inspection ────────────────────────────────────────────


def _run_git(workspace: Path, args: Sequence[str]) -> Optional[bytes]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(workspace), *args],
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def staged_paths(workspace: Path) -> Optional[List[str]]:
    """Return absolute-free, workspace-relative paths staged for this commit.

    ``--no-renames`` keeps a rename visible as a plain delete + add pair, so
    no path can hide inside a rename record.  ``-z`` avoids git's C-style
    path quoting, which would mangle non-ASCII CAA directory names.
    """
    out = _run_git(
        workspace, ["diff", "--cached", "--no-renames", "--name-only", "-z"]
    )
    if out is None:
        return None
    text = out.decode("utf-8", "surrogateescape")
    return [p for p in text.split("\0") if p]


def in_progress_merge(workspace: Path) -> bool:
    """True when the commit about to be made is a merge resolution.

    Merge commits are not gated: the commits they integrate were already
    checked individually, and blocking an automatic merge message would be
    pure friction.
    """
    return _run_git(workspace, ["rev-parse", "-q", "--verify", "MERGE_HEAD"]) is not None


# ─── Claims ──────────────────────────────────────────────────────────


@dataclass
class Claim:
    """A declaration that covers some set of controlled assets."""

    source: str
    kind: str = "manual"
    reason: str = ""
    files: Optional[List[str]] = None  # None = covers everything
    rollback_id: str = ""
    expires_at: Optional[str] = None
    problems: List[str] = field(default_factory=list)

    def covers(self, path: str) -> bool:
        if self.problems:
            return False
        if not self.files:
            return True
        target = path.casefold()
        return any(f.casefold() == target for f in self.files)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "kind": self.kind,
            "reason": self.reason,
            "files": self.files,
            "rollback_id": self.rollback_id,
            "expires_at": self.expires_at,
            "problems": self.problems,
        }


def _is_future(iso: str) -> bool:
    try:
        dt = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return False
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    return dt > now


def claim_from_dict(source: str, data) -> Claim:
    """Build a Claim from a JSON object, recording every reason it is unusable."""
    if not isinstance(data, dict):
        return Claim(source=source, problems=["claim is not a JSON object"])

    problems: List[str] = []
    schema = data.get("schema_version", 0)
    if schema != SCHEMA_VERSION:
        problems.append(f"schema_version {schema!r} != {SCHEMA_VERSION}")

    raw_files = data.get("files")
    files: Optional[List[str]] = None
    if raw_files is not None:
        if isinstance(raw_files, list):
            files = [normalize_path(x) for x in raw_files if str(x).strip()]
        else:
            problems.append("'files' must be a list of paths")

    expires = data.get("expires_at")
    if expires is not None and not _is_future(expires):
        problems.append(f"expired at {expires}")

    # An unbounded claim with no expiry would bless every future edit forever.
    if not files and expires is None:
        problems.append("claim covers every controlled asset forever; set 'files' or 'expires_at'")

    return Claim(
        source=source,
        kind=str(data.get("kind") or "manual"),
        reason=str(data.get("reason") or ""),
        files=files,
        rollback_id=str(data.get("rollback_id") or ""),
        expires_at=expires,
        problems=problems,
    )


def load_claims(workspace: Path) -> List[Claim]:
    """Load every claim under <workspace>/.cade/intent/*.json (sorted, stable)."""
    intent_dir = workspace.joinpath(*INTENT_SUBDIR)
    if not intent_dir.is_dir():
        return []
    claims: List[Claim] = []
    for path in sorted(intent_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            claims.append(Claim(source=f"file:{path.name}", problems=[f"unreadable: {exc}"]))
            continue
        claims.append(claim_from_dict(f"file:{path.name}", data))
    return claims


def parse_trailer_claims(message: str) -> List[Claim]:
    """Extract CADE-Intent / CADE-Intent-Files trailers from a commit message."""
    reason: Optional[str] = None
    files: Optional[List[str]] = None
    for raw in message.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = TRAILER_RE.match(line)
        if not match:
            continue
        key = match.group(1).lower()
        value = match.group(2).strip()
        if key == "cade-intent":
            reason = value
        else:
            files = [normalize_path(x) for x in value.split(",") if x.strip()]
    if not reason:
        return []
    return [Claim(source="trailer", kind="manual", reason=reason, files=files or None)]


def read_commit_message(workspace: Path, msg_file: Optional[str]) -> Optional[str]:
    if not msg_file:
        return None
    candidate = Path(msg_file)
    if not candidate.is_absolute():
        # git runs commit-msg hooks with cwd at the repository top level.
        candidate = workspace / candidate
    try:
        return candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


# ─── Evaluation ──────────────────────────────────────────────────────


def evaluate(
    workspace: Path,
    paths: Optional[List[str]] = None,
    message: Optional[str] = None,
    warn_only: bool = False,
    message_expected: bool = False,
) -> dict:
    """Decide whether the staged controlled assets are declared.

    Returns a result dict whose ``gate`` is PASS / WARN / BLOCK / DEGRADED.

    ``message_expected`` means the caller passed a commit-message file.  If
    that file then could not be read, the declaration channel is missing, not
    empty -- reporting BLOCK there would accuse an author who may well have
    declared the change.  That case degrades instead.
    """
    result = {
        "workspace": str(workspace),
        "gate": "PASS",
        "reason": "",
        "inspected": [],
        "controlled": [],
        "undeclared": [],
        "claims": [],
        "claim_problems": [],
    }

    classifier, config = _provenance()
    if classifier is None:
        result["gate"] = "DEGRADED"
        result["reason"] = f"asset classifier unavailable: {config}"
        return result

    from_index = paths is None
    if from_index:
        paths = staged_paths(workspace)
        if paths is None:
            result["gate"] = "DEGRADED"
            result["reason"] = "not a git work tree, or the index could not be read"
            return result

    normalized = sorted({to_relative(p, workspace) for p in paths if str(p).strip()})
    result["inspected"] = normalized

    controlled = [
        p for p in normalized if classifier(Path(p), workspace, config)
    ]
    result["controlled"] = controlled
    if not controlled:
        result["reason"] = "no controlled assets staged"
        return result

    claims = load_claims(workspace) + parse_trailer_claims(message or "")
    result["claims"] = [c.to_dict() for c in claims]
    result["claim_problems"] = [
        {"source": c.source, "problems": c.problems} for c in claims if c.problems
    ]

    # A declared-but-unreadable commit message is missing evidence, not
    # absent evidence.  Fail open rather than accuse the author.
    if message_expected and message is None:
        result["gate"] = "DEGRADED"
        result["reason"] = "commit message file was passed but could not be read"
        return result

    undeclared = [p for p in controlled if not any(c.covers(p) for c in claims)]
    result["undeclared"] = undeclared

    if not undeclared:
        result["reason"] = f"all {len(controlled)} controlled asset(s) declared"
        return result

    # Merge resolutions are not re-gated: the commits being integrated were
    # each checked before they landed, so a merge can only introduce a
    # conflict resolution, not an undiscussed change of intent.  Only applies
    # when this is an actual commit (paths came from the index); an explicit
    # --files query is a targeted question and is answered normally.
    if from_index and in_progress_merge(workspace):
        result["gate"] = "WARN"
        result["reason"] = (
            f"{len(undeclared)} undeclared controlled asset(s) in a merge resolution; "
            "allowed because the merged commits were gated individually"
        )
        return result

    result["gate"] = "WARN" if warn_only else "BLOCK"
    result["reason"] = (
        f"{len(undeclared)} of {len(controlled)} controlled asset(s) staged without a declaration"
    )
    return result


# ─── Declaration emission ────────────────────────────────────────────


def _files_from_rollback(workspace: Path, rollback_id: str) -> Optional[List[str]]:
    """Read the changed-file list out of a CADE backup manifest."""
    manifest = workspace / ".caa_backups" / rollback_id / "manifest.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    files: List[str] = []
    for key in ("created", "modified"):
        for item in data.get(key) or []:
            files.append(to_relative(item, workspace))
    return sorted(set(files)) or None


def _unique_claim_path(intent_dir: Path, stamp: str, kind: str) -> Path:
    candidate = intent_dir / f"{stamp}-{kind}.json"
    suffix = 1
    while candidate.exists():
        candidate = intent_dir / f"{stamp}-{kind}-{suffix}.json"
        suffix += 1
    return candidate


def bless(
    workspace: Path,
    kind: str,
    reason: str,
    files: Optional[List[str]] = None,
    rollback_id: Optional[str] = None,
    author: Optional[str] = None,
) -> dict:
    """Write a claim under <workspace>/.cade/intent and return its details."""
    if files is None and rollback_id:
        files = _files_from_rollback(workspace, rollback_id)
    if files is None:
        staged = staged_paths(workspace) or []
        classifier, config = _provenance()
        if classifier is None:
            return {"status": "error", "errors": [f"asset classifier unavailable: {config}"]}
        files = [
            p for p in staged
            if classifier(Path(p), workspace, config)
        ]
    if not files:
        return {"status": "error", "errors": ["nothing to declare: no controlled asset given or staged"]}

    files = sorted({to_relative(f, workspace) for f in files})
    claim = {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "author": author or "",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "reason": reason,
        "files": files,
    }
    if rollback_id:
        claim["rollback_id"] = rollback_id

    intent_dir = workspace.joinpath(*INTENT_SUBDIR)
    intent_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = _unique_claim_path(intent_dir, stamp, kind)
    target.write_text(json.dumps(claim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "status": "written",
        "claim_path": str(target),
        "files": files,
        "tracked_by_git": False,
    }


# ─── Reporting ───────────────────────────────────────────────────────


def _print_human(result: dict, gate_py: Path) -> int:
    gate = result["gate"]
    workspace = result["workspace"]

    print("CADE Intent Gate")
    print("=" * 70)
    print(f"  workspace : {workspace}")
    print(f"  verdict   : {gate}")

    if result["controlled"]:
        print(f"  controlled: {len(result['controlled'])} staged")
    if result["reason"]:
        print(f"  reason    : {result['reason']}")

    if result.get("claim_problems"):
        print("\n  Unusable declaration(s) (ignored):")
        for item in result["claim_problems"]:
            print(f"    - {item['source']}: {'; '.join(item['problems'])}")

    if gate in ("PASS",):
        print("=" * 70)
        print("RESULT: PASS")
        return 0

    if gate == "DEGRADED":
        print("=" * 70)
        print("RESULT: DEGRADED (commit allowed -- the gate could not evaluate)")
        return 0

    if gate == "WARN":
        print("\n  Undeclared controlled asset(s):")
        for p in result["undeclared"]:
            print(f"    - {p}")
        print("=" * 70)
        print("RESULT: WARN (commit allowed)")
        return 0

    print("\n  Undeclared controlled asset(s):")
    for p in result["undeclared"]:
        print(f"    - {p}")

    print("\n  Declare this commit in one of two ways:\n")
    print("  1) Add a trailer to the commit message (travels with history):\n")
    print('       git commit -m "<subject>" -m "CADE-Intent: <why this edit exists>"\n')
    print("     Narrow it to specific files with a second trailer:\n")
    print('       CADE-Intent-Files: <comma-separated paths>\n')
    print("  2) Emit a local claim, then re-run the same commit:\n")
    print(
        f'       "{sys.executable}" "{gate_py}" --workspace "{workspace}" '
        f'--bless manual --reason "<why this edit exists>"\n'
    )

    print("  Documented escape hatch: git commit --no-verify  (AGENTS.md section 4)")
    print("=" * 70)
    print(f"RESULT: BLOCK ({len(result['undeclared'])} undeclared controlled asset(s))")
    return 1


# ─── CLI ─────────────────────────────────────────────────────────────


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="CADE intent gate: require a declaration for controlled-asset commits",
    )
    parser.add_argument("--workspace", required=True, help="CAA workspace root")
    parser.add_argument(
        "--files",
        nargs="+",
        help="evaluate these paths instead of the git index (absolute or worktree-relative)",
    )
    parser.add_argument(
        "--commit-msg-file",
        help="path to the commit message file (as passed to a commit-msg hook)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="report BLOCK as WARN and exit 0 (soft rollout)",
    )
    parser.add_argument(
        "--bless",
        choices=["manual", "cade"],
        help="write a declaration claim instead of evaluating",
    )
    parser.add_argument("--reason", default="", help="why this change exists (with --bless)")
    parser.add_argument(
        "--rollback-id",
        help="CADE backup id; its manifest supplies the file list (with --bless cade)",
    )
    parser.add_argument("--author", default="", help="declared author (with --bless)")
    parser.add_argument(
        "--install-hooks",
        action="store_true",
        help="install the pre-commit/commit-msg hooks into the workspace's git repo",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="remove hooks created by --install-hooks (with --install-hooks)",
    )
    args = parser.parse_args(argv)

    workspace = Path(args.workspace)
    if not workspace.is_dir():
        print(f"ERROR: not a directory: {workspace}", file=sys.stderr)
        return 2

    if args.install_hooks:
        try:
            from intent_hook_install import install_hooks, uninstall_hooks
        except ImportError as exc:
            print(f"ERROR: hook installer unavailable: {exc}", file=sys.stderr)
            return 2
        outcome = (
            uninstall_hooks(workspace) if args.uninstall
            else install_hooks(workspace, warn_only=args.warn_only)
        )
        if args.json:
            print(json.dumps({"workspace": str(workspace), **outcome}, ensure_ascii=False, indent=2))
            return 0 if outcome.get("status") in ("installed", "uninstalled") else 1
        if outcome.get("status") in ("conflict", "error"):
            for err in outcome.get("errors", []):
                print(f"ERROR: {err}", file=sys.stderr)
            return 1
        if outcome.get("status") == "uninstalled":
            for path in outcome["removed"]:
                print(f"removed  {path}")
            for path in outcome["kept_foreign_hooks"]:
                print(f"kept     {path}  (not created by the intent gate)")
            return 0
        print(f"Installed intent gate hooks in {outcome['hooks_dir']}")
        for path in outcome["hooks"]:
            print(f"  - {path}")
        print(f"\nGate    : {outcome['gate']}")
        print(f"Workspace: {outcome['workspace']}")
        if outcome["warn_only"]:
            print("Mode    : WARN-ONLY (nothing is blocked)")
        print("\nReplay this installation on another machine with:")
        print(f"  {outcome['replay']}")
        return 0

    if args.bless:
        if not args.reason.strip():
            print("ERROR: --bless requires --reason", file=sys.stderr)
            return 2
        outcome = bless(
            workspace,
            kind=args.bless,
            reason=args.reason.strip(),
            files=args.files,
            rollback_id=args.rollback_id,
            author=args.author,
        )
        if outcome.get("status") != "written":
            payload = {"workspace": str(workspace), **outcome}
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                for err in outcome.get("errors", []):
                    print(f"ERROR: {err}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps({"workspace": str(workspace), **outcome}, ensure_ascii=False, indent=2))
            return 0
        print(f"Wrote declaration: {outcome['claim_path']}")
        print(f"  covers {len(outcome['files'])} file(s):")
        for p in outcome["files"]:
            print(f"    - {p}")
        print("  .cade/ is outside version control, so no 'git add' is needed.")
        return 0

    message = read_commit_message(workspace, args.commit_msg_file)
    result = evaluate(
        workspace,
        paths=args.files,
        message=message,
        warn_only=args.warn_only,
        message_expected=bool(args.commit_msg_file),
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["gate"] in ("PASS", "WARN", "DEGRADED") else 1

    return _print_human(result, Path(__file__).resolve())


if __name__ == "__main__":
    sys.exit(main())
