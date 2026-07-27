#!/usr/bin/env python3
"""
Phantom Capability Checker
============================
Scan skills/**/*.py for public functions and CLI commands, then verify
each against the five-point capability contract: file / entry / test /
doc / runtime path.  A capability missing BOTH an entry point AND a
runtime path is flagged as PHANTOM.

Pure stdlib.  Run:  python tools/check_capabilities.py
"""

import ast
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
SKILLS_DIR = SKILL_ROOT / "skills"
TESTS_DIR = SKILL_ROOT / "tests"
SKILL_MD = SKILL_ROOT / "SKILL.md"


def collect_public_functions():
    """Return {name: file} for every top-level public def in skills/."""
    caps = {}
    for py in sorted(SKILLS_DIR.rglob("*.py")):
        if py.name.startswith("_"):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError:
            continue
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                rel = py.relative_to(SKILL_ROOT)
                caps.setdefault(node.name, str(rel))
    return caps


def collect_cli_commands():
    """Return {cmd_string: line_no} from cade.py main() elif branches."""
    cade = SKILLS_DIR / "cade.py"
    cmds = {}
    if not cade.exists():
        return cmds
    for i, line in enumerate(cade.read_text(encoding="utf-8").splitlines(), 1):
        m = re.search(r'elif cmd == "(\w+)"', line)
        if m:
            cmds[m.group(1)] = i
    return cmds


def collect_references():
    """Build lookup sets for entry / test / doc references."""
    entry_files = [SKILLS_DIR / f for f in ("cade.py", "kernel.py", "mcp_server.py")]
    entry_src = " ".join(
        f.read_text(encoding="utf-8") for f in entry_files if f.exists()
    )
    test_src = " ".join(
        f.read_text(encoding="utf-8")
        for f in TESTS_DIR.rglob("*.py")
        if f.is_file()
    )
    doc_src = SKILL_MD.read_text(encoding="utf-8") if SKILL_MD.exists() else ""
    return entry_src, test_src, doc_src


def check(name, file_path, entry_src, test_src, doc_src):
    """Check one capability against the five-point contract."""
    has_entry = name in entry_src
    has_test = name in test_src
    has_doc = name in doc_src
    # Runtime path: capability is reachable via kernel intent routing or
    # direct CLI dispatch.  We approximate this by checking whether the
    # kernel _detect_intent_type or cade main() mentions the name.
    kernel_src = (SKILLS_DIR / "kernel.py").read_text(encoding="utf-8")
    cade_src = (SKILLS_DIR / "cade.py").read_text(encoding="utf-8")
    has_runtime = name in kernel_src or name in cade_src
    status = "OK" if (has_entry or has_runtime) else "PHANTOM"
    return {
        "name": name,
        "file": file_path,
        "entry": "Y" if has_entry else "-",
        "test": "Y" if has_test else "-",
        "doc": "Y" if has_doc else "-",
        "runtime": "Y" if has_runtime else "-",
        "status": status,
    }


def main():
    caps = collect_public_functions()
    cli_cmds = collect_cli_commands()
    entry_src, test_src, doc_src = collect_references()

    rows = []
    for name, fpath in sorted(caps.items()):
        rows.append(check(name, fpath, entry_src, test_src, doc_src))

    # CLI commands are capabilities too
    for cmd, lineno in sorted(cli_cmds.items()):
        rows.append(check(cmd, f"cade.py:L{lineno}", entry_src, test_src, doc_src))

    # Print matrix
    hdr = f"{'Name':<40s} {'File':<40s} {'Entry':<6s} {'Test':<6s} {'Doc':<6s} {'Runtime':<8s} {'Status'}"
    print("=" * len(hdr))
    print("  CADE Phantom Capability Matrix")
    print("=" * len(hdr))
    print(hdr)
    print("-" * len(hdr))
    phantom_count = 0
    for r in rows:
        print(
            f"{r['name']:<40s} {r['file']:<40s} {r['entry']:<6s} "
            f"{r['test']:<6s} {r['doc']:<6s} {r['runtime']:<8s} {r['status']}"
        )
        if r["status"] == "PHANTOM":
            phantom_count += 1
    print("-" * len(hdr))
    print(f"  Total: {len(rows)} capabilities, {phantom_count} PHANTOM")
    print("=" * len(hdr))

    return 1 if phantom_count else 0


if __name__ == "__main__":
    sys.exit(main())
