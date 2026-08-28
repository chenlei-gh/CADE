"""
Token Optimizer — Progressive Detail Output
=============================================

Level 1 (summary): always returned, compact but complete
Level 2 (detail):  auto-included when errors > 0, or AI explicitly requests

Rules:
  NEVER trim: error messages, file paths, entity names, line numbers
  ONLY trim:  build logs, stack traces, empty fields, metadata noise
"""

import json
from typing import Any, Dict, List


# ═══ Core ═══════════════════════════════════════════════════════

def optimize(result: Any, mode: str = "auto") -> dict:
    """
    Progressive output for AI consumption.

    mode='auto':  summary if status=ok & error_count=0, else detail
    mode='brief': always level 1 summary
    mode='full':  skip optimization, return raw
    """
    if mode == "full":
        return result

    # Normalize to dict
    d = result.to_dict() if hasattr(result, "to_dict") else result
    if not isinstance(d, dict):
        return result

    # Always include level 1
    level1 = _extract_level1(d)

    # Level 2: auto when errors exist, or explicit brief
    if mode == "brief":
        return level1

    needs_detail = (d.get("error_count", 0) > 0 or
                    d.get("status") not in ("ok", "success", "stopped", "not_running",
                                             "pending", "no_issues", "fixed") or
                    d.get("status") == "needs_clarification" or
                    _has_errors_in_diagnostics(d))
    if needs_detail:
        level1["detail"] = _extract_level2(d)

    return level1


# ═══ Level 1: Summary ═══════════════════════════════════════════

def _has_errors_in_diagnostics(d: dict) -> bool:
    """Check if diagnostics list contains any ERROR severity items."""
    diags = d.get("diagnostics", [])
    return any(di.get("severity") == "ERROR" for di in diags if isinstance(di, dict))


# Fields the caller MUST see to act on the result. These are small by
# construction (question lists, recovery options, id handles) and stripping
# them breaks the workflow: e.g. a 'needs_clarification' response without
# its 'questions' forces the agent to guess or re-invoke blind, and a
# module-not-found error without 'available_modules' cannot self-correct.
_PASSTHROUGH_KEYS = (
    "questions",           # needs_clarification: the actual questions
    "available_modules",   # module-not-found recovery options
    "available_frameworks",#
    "suggestion",          # one-line fix hint
    "suggestions",         # next-step suggestions
    "existing_command",    # name-collision details
    "components",          # multi-artifact composition summary
    "verification_failed", # top-level flag set by kernel Phase 3
    "rollback_id",         # undo handle for an applied ChangeSet
)


def _compact_knowledge_refs(refs):
    """Reduce knowledge_refs to id + title (drop raw catalog lines etc.)."""
    if not isinstance(refs, list):
        return refs
    compact = []
    for r in refs[:5]:
        if isinstance(r, dict):
            compact.append({k: r[k] for k in ("id", "file", "title") if k in r})
        else:
            compact.append(r)
    return compact


def _compact_changeset(cs):
    """Reduce a serialized ChangeSet to file lists + counts.

    The full 'changeset' dict carries the complete file CONTENTS of every
    created/modified file — tens of thousands of tokens for a command with
    a dialog. The caller (preview workflow) needs the file manifest, not
    the bodies; re-running without --preview applies the real thing.
    """
    if not isinstance(cs, dict):
        return cs
    compact = {
        "action": cs.get("action", ""),
        "created": sorted(cs.get("created", {}).keys()),
        "modified": sorted(cs.get("modified", {}).keys()),
        "deleted": list(cs.get("deleted", [])),
        "total_changes": cs.get("total_changes", 0),
        "warnings": list(cs.get("warnings", [])),
        "metadata": cs.get("metadata", {}),
    }
    patches = cs.get("patches", [])
    if patches:
        compact["patches"] = [
            {k: p.get(k) for k in ("file", "operation", "target", "line_start", "line_end")}
            for p in patches if isinstance(p, dict)
        ]
    return compact


def _extract_level1(d: dict) -> dict:
    """Extract the 'what happened in one glance' fields."""
    summary = {
        "ok": d.get("status") in ("ok", "success", "stopped", "not_running",
                                     "pending", "no_issues", "fixed"),
        "status": d.get("status", "?"),
    }

    # Metrics
    for k in ("error_count", "warning_count", "exit_code", "duration",
              "total", "pass_rate", "auto_fixable"):
        if k in d:
            summary[k] = d[k]

    # Category breakdown (diagnostics)
    if "diagnostics" in d:
        diags = d["diagnostics"]
        if isinstance(diags, list) and diags and isinstance(diags[0], dict):
            cats = {}
            for di in diags:
                c = di.get("category", di.get("type", "other"))
                cats[c] = cats.get(c, 0) + 1
            sevs = {}
            for di in diags:
                s = di.get("severity", "?")
                sevs[s] = sevs.get(s, 0) + 1
            summary["categories"] = cats
            summary["severity"] = sevs
        else:
            summary["diagnostics_count"] = len(diags)

    # Snapshot stats
    for k in ("frameworks", "framework_count", "modules", "module_count",
              "commands", "command_count", "interfaces"):
        if k in d:
            val = d[k]
            if isinstance(val, list):
                summary[k.replace("_count", "s")] = len(val)
            else:
                summary[k] = val

    # Workspace check
    if "issues" in d:
        summary["issues_found"] = len(d["issues"])

    # Message (if short enough)
    msg = d.get("message", "")
    if msg and len(msg) < 200:
        summary["message"] = msg

    # AI-actionable fields — never stripped (see _PASSTHROUGH_KEYS)
    for k in _PASSTHROUGH_KEYS:
        v = d.get(k)
        if v:
            summary[k] = v

    # Knowledge grounding: keep ids/titles (compact), keep content — the
    # kernel injects it specifically so agents generate against verified
    # API patterns; stripping it turned that quality lever into dead IO.
    if d.get("knowledge_refs"):
        summary["knowledge_refs"] = _compact_knowledge_refs(d["knowledge_refs"])
    if d.get("knowledge_content"):
        summary["knowledge_content"] = d["knowledge_content"]

    # Preview workflow: the caller explicitly asked for the plan — surface
    # the manifest (file lists), not the full file bodies.
    if d.get("preview"):
        summary["preview"] = d["preview"]
    if d.get("changeset"):
        summary["changeset"] = _compact_changeset(d["changeset"])

    return summary


# ═══ Level 2: Detail (only when things went wrong) ════════════

def _extract_level2(d: dict) -> dict:
    """Extract actionable error details. NEVER trims error content."""
    detail = {}

    # Static-verification violations (kernel Phase 3): the fix list the
    # agent must work through — never strip these.
    if d.get("verification_errors"):
        detail["verification_errors"] = d["verification_errors"]

    # Errors (keep full message, file, line)
    if "errors" in d:
        errs = d["errors"]
        if isinstance(errs, list) and errs:
            detail["errors"] = [_keep_actionable(e) for e in errs[:10]]

    # Diagnostics
    if "diagnostics" in d:
        diags = d["diagnostics"]
        if isinstance(diags, list) and diags and isinstance(diags[0], dict):
            err_diags = [di for di in diags if di.get("severity") == "ERROR"]
        if err_diags:
            detail["errors"] = detail.get("errors", []) + [
                _keep_actionable(di) for di in err_diags[:10]
            ]

    # Build output tail (last 500 chars are usually where errors appear)
    for k in ("output", "stderr"):
        if k in d and isinstance(d[k], str) and d.get("error_count", 0) > 0:
            detail["build_tail"] = d[k][-500:]

    return detail if detail else None


def _keep_actionable(item: Any) -> dict:
    """Keep only fields AI can act on: file, line, message, entity name."""
    if isinstance(item, str):
        return {"message": item[:200]}
    if isinstance(item, dict):
        keep = {}
        for k in ("file", "line", "message", "entity", "name", "module",
                  "framework", "type", "severity", "fix", "code", "path"):
            if k in item and item[k] is not None:
                keep[k] = item[k]
        return keep
    return {"raw": str(item)[:200]}
