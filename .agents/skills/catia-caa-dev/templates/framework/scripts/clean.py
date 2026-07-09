#!/usr/bin/env python3
"""FrameworkName — Clean Build (mkmk -c)"""

import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
result = subprocess.run(["mkmk", "-c"], cwd=ROOT, capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr, file=sys.stderr)
sys.exit(result.returncode)
