#!/usr/bin/env python3
"""Run the two second-scale static audits that catch documentation drift.

These suites are script-style (they call sys.exit themselves). Do not run
them under pytest. They do not start CATIA, compile, or touch a workspace.

  python scripts/static_audit.py

Exit 0 only when both suites exit 0.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "catia-caa-dev"
SUITES = (
    "tests/test_cross_reference.py",
    "tests/test_deep_audit.py",
)


def main() -> int:
    missing = [name for name in SUITES if not (SKILL_ROOT / name).is_file()]
    if missing:
        print("static audit: skill root or suite missing:", file=sys.stderr)
        for name in missing:
            print(f"  {SKILL_ROOT / name}", file=sys.stderr)
        return 2

    failed = 0
    for name in SUITES:
        script = SKILL_ROOT / name
        print(f"\n==> {name}", flush=True)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(SKILL_ROOT),
            env=env,
        )
        if result.returncode != 0:
            failed += 1
            print(f"FAIL {name} (exit {result.returncode})", file=sys.stderr)
        else:
            print(f"PASS {name}")

    if failed:
        print(f"\nstatic audit: {failed}/{len(SUITES)} suite(s) failed", file=sys.stderr)
        return 1
    print(f"\nstatic audit: {len(SUITES)}/{len(SUITES)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
