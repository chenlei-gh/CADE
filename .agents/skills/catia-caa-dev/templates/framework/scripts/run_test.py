#!/usr/bin/env python3
"""FrameworkName — Run FunctionTests"""

import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
RV = ROOT / "Build" / "win_b64" / "code"

if not RV.exists():
    print("Creating Runtime View...")
    subprocess.run(["mkCreateRuntimeView"], cwd=ROOT, check=True)

print("Starting CATIA with Runtime View...")
subprocess.run(["CNEXT", "-direnv", str(RV)], cwd=ROOT)
