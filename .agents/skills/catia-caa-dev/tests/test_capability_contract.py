#!/usr/bin/env python3
"""
Capability Contract Suite
==========================
Thin wrapper that runs tools/check_capabilities.py as a master-test suite.

A capability is a PHANTOM when it has a file but no entry point and no
runtime path; a STALE DOC is the reverse (SKILL.md documents a name the
code no longer defines).  Either one means the capability contract has
drifted, so the suite fails.  Prints CAPABILITY CONTRACT OK when clean.

Pure stdlib.
"""

import importlib.util
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
CHECKER = SKILL_ROOT / "tools" / "check_capabilities.py"


def main() -> int:
    spec = importlib.util.spec_from_file_location("check_capabilities", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main()


if __name__ == "__main__":
    sys.exit(main())
