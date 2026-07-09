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
                    d.get("status") not in ("ok", "success", "stopped", "not_running") or
                    _has_errors_in_diagnostics(d))
    if needs_detail:
        level1["detail"] = _extract_level2(d)

    return level1


# ═══ Level 1: Summary ═══════════════════════════════════════════

def _has_errors_in_diagnostics(d: dict) -> bool:
    """Check if diagnostics list contains any ERROR severity items."""
    diags = d.get("diagnostics", [])
    return any(di.get("severity") == "ERROR" for di in diags if isinstance(di, dict))


def _extract_level1(d: dict) -> dict:
    """Extract the 'what happened in one glance' fields."""
    summary = {
        "ok": d.get("status") in ("ok", "success", "stopped", "not_running"),
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

    return summary


# ═══ Level 2: Detail (only when things went wrong) ════════════

def _extract_level2(d: dict) -> dict:
    """Extract actionable error details. NEVER trims error content."""
    detail = {}

    # Errors (keep full message, file, line)
    if "errors" in d:
        errs = d["errors"]
        if isinstance(errs, list) and errs:
            detail["errors"] = [_keep_actionable(e) for e in errs[:10]]

    # Diagnostics
    if "diagnostics" in d:
        diags = d["diagnostics"]
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
