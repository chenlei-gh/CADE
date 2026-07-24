"""
Build Gate — pre-compile static verification gate
==================================================
Purpose: Block mkmk when error-level findings (fabricated CAA APIs) are
         detected in workspace sources. The gate only READS sources; it
         never modifies anything. It is fail-open: a gate malfunction
         never blocks the build.

Verdicts:
  PASS   no findings               → build proceeds
  WARN   warnings only             → build proceeds (findings printed)
  BLOCK  error-level findings      → build refused (fix, or --skip-gate)
  SKIP   bypassed via --skip-gate  → build proceeds (still logged)

Telemetry: every run appends fact records to cache/build_gate_log.jsonl —
one line per finding plus one run summary. SKIP is logged too, so monthly
stats can distinguish "AI got better" from "everyone bypassed the gate".

Usage:
  python build_gate.py <workspace> [--json] [--skip]
  python build_gate.py --stats [--days N] [--log PATH]
  from build_gate import run_gate; result = run_gate(workspace_path)
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = SKILL_ROOT / "cache" / "build_gate_log.jsonl"

_SYMBOL_RE = re.compile(r"'([^']+)'")


def _evidence_of(issue) -> str:
    """Which index backs this finding (fact, not conclusion)."""
    if "has no method" in issue.message:
        return "method_index"
    if issue.category in ("include", "naming"):
        return "header_map"
    return "verifier"


def _symbol_of(issue) -> str:
    m = _SYMBOL_RE.search(issue.message)
    return m.group(1) if m else ""


def _append_log(records: list):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def run_gate(workspace, skip: bool = False) -> dict:
    """Verify all *.m modules under workspace. Returns a result dict with
    decision PASS/WARN/BLOCK/SKIP. Fail-open on any internal error."""
    t0 = time.perf_counter()
    ws = Path(workspace)
    now = datetime.now().isoformat(timespec="seconds")
    base = {"time": now, "workspace": str(ws)}
    try:
        if skip:
            _append_log([{**base, "kind": "run", "decision": "SKIP",
                          "duration_ms": 0}])
            return {"status": "success", "decision": "SKIP", "errors": 0,
                    "warnings": 0, "modules": 0, "files_checked": 0,
                    "duration_ms": 0, "findings": [], "log": str(LOG_FILE)}

        from verifier import CodeVerifier
        verifier = CodeVerifier(SKILL_ROOT)
        modules = [m for fw in sorted(ws.rglob("*.edu")) if fw.is_dir()
                   for m in sorted(fw.glob("*.m")) if m.is_dir()]

        findings, files_checked = [], 0
        for mod in modules:
            r = verifier.verify_module(mod)
            files_checked += r.files_checked
            for i in r.issues:
                if i.severity in ("error", "warning"):
                    findings.append({"module": mod.name, "rule": i.category,
                                     "severity": i.severity, "file": i.file,
                                     "message": i.message,
                                     "suggestion": i.suggestion,
                                     "symbol": _symbol_of(i),
                                     "evidence": _evidence_of(i)})

        errors = sum(1 for f in findings if f["severity"] == "error")
        warnings = len(findings) - errors
        decision = "BLOCK" if errors else ("WARN" if warnings else "PASS")
        ms = round((time.perf_counter() - t0) * 1000)

        records = [{**base, "kind": "finding", "decision": decision,
                    "duration_ms": ms, **f} for f in findings]
        records.append({**base, "kind": "run", "decision": decision,
                        "modules": len(modules), "files_checked": files_checked,
                        "errors": errors, "warnings": warnings,
                        "duration_ms": ms})
        _append_log(records)

        return {"status": "blocked" if errors else "success",
                "decision": decision, "errors": errors, "warnings": warnings,
                "modules": len(modules), "files_checked": files_checked,
                "duration_ms": ms, "findings": findings, "log": str(LOG_FILE)}
    except Exception as e:
        # Fail-open: the gate is advisory infrastructure; a gate bug must
        # never prevent compilation. Logged so the failure is visible.
        _append_log([{**base, "kind": "run", "decision": "PASS",
                      "gate_error": str(e),
                      "duration_ms": round((time.perf_counter() - t0) * 1000)}])
        return {"status": "success", "decision": "PASS", "errors": 0,
                "warnings": 0, "modules": 0, "files_checked": 0,
                "duration_ms": 0, "findings": [], "log": str(LOG_FILE),
                "gate_error": str(e)}


def print_stats(days: int = 30, log_path=None) -> int:
    """Aggregate the JSONL telemetry and print a monthly summary.

    Answers the two questions Phase 2 investment depends on:
      1. Is the gate catching real fabrications (BLOCK) or being bypassed (SKIP)?
      2. Which rules/modules produce the most findings (where to invest next)?
    """
    from collections import Counter
    log = Path(log_path) if log_path else LOG_FILE
    if not log.exists():
        print(f"No gate log found: {log}")
        return 1
    cutoff = datetime.now().timestamp() - days * 86400
    runs, findings = [], []
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            if datetime.fromisoformat(r["time"]).timestamp() < cutoff:
                continue
            (runs if r.get("kind") == "run" else findings).append(r)
        except (ValueError, KeyError):
            continue
    if not runs:
        print(f"No gate runs in the last {days} day(s): {log}")
        return 1

    dec = Counter(r["decision"] for r in runs)
    total = sum(dec.values())
    print(f"Build Gate stats — last {days} day(s), {total} run(s)")
    print(f"  Log: {log}")
    for d in ("PASS", "WARN", "BLOCK", "SKIP"):
        if dec.get(d):
            print(f"  {d:5s} {dec[d]:4d}  ({dec[d] * 100 // total}%)")
    if dec.get("SKIP"):
        print(f"  -> SKIP/BLOCK ratio: "
              f"{dec['SKIP'] / max(dec.get('BLOCK', 0), 1):.1f} "
              f"(high = people bypassing, not AI improving)")
    errs = [f for f in findings if f.get("severity") == "error"]
    if errs:
        print(f"  Top error rules: "
              + ", ".join(f"{k}({v})" for k, v in
                          Counter(f["rule"] for f in errs).most_common(3)))
        print(f"  Top error modules: "
              + ", ".join(f"{k}({v})" for k, v in
                          Counter(f["module"] for f in errs).most_common(3)))
    durs = [r["duration_ms"] for r in runs if r.get("duration_ms")]
    if durs:
        print(f"  Duration: avg {sum(durs) // len(durs)}ms, max {max(durs)}ms")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Pre-compile static verification gate (fabricated API detection)")
    parser.add_argument("workspace", nargs="?", help="Workspace path")
    parser.add_argument("--json", action="store_true",
                        help="Print full result as JSON")
    parser.add_argument("--skip", action="store_true",
                        help="Bypass the gate (logged as SKIP)")
    parser.add_argument("--stats", action="store_true",
                        help="Print telemetry summary instead of running the gate")
    parser.add_argument("--days", type=int, default=30,
                        help="Stats window in days (default: 30)")
    parser.add_argument("--log", default=None,
                        help="Stats: read a different log file "
                             "(e.g. another skill copy's build_gate_log.jsonl)")
    args = parser.parse_args()

    if args.stats:
        sys.exit(print_stats(args.days, args.log))
    if not args.workspace:
        parser.error("workspace is required unless --stats is given")

    result = run_gate(Path(args.workspace).resolve(), skip=args.skip)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif result["decision"] == "PASS" and not result.get("gate_error"):
        print(f"Gate PASS ({result['files_checked']} files, "
              f"{result['duration_ms']}ms)")
    else:
        print(f"Gate {result['decision']}: {result['errors']} error(s), "
              f"{result['warnings']} warning(s)")
        for f in result["findings"]:
            print(f"  [{f['severity']}][{f['rule']}] {f['module']}: "
                  f"{f['message']}")
        if result.get("gate_error"):
            print(f"  (gate fail-open: {result['gate_error']})")

    sys.exit(1 if result["decision"] == "BLOCK" else 0)


if __name__ == "__main__":
    main()
