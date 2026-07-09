#!/usr/bin/env python3
"""FrameworkName — Install to CATIA"""

import shutil, sys
from pathlib import Path
from env import CAAEnvironment

env = CAAEnvironment()
env.initialize()
catia = Path(env.config.get("CATIA_INSTALL", ""))

if not catia.exists():
    print(f"Error: CATIA not found at {catia}")
    sys.exit(1)

ROOT = Path(__file__).parent.parent
BUILD = ROOT / "Build" / "win_b64" / "code"
DLL_DIR = catia / "win_b64" / "code" / "bin"

if not BUILD.exists():
    print("Run full_build.py first.")
    sys.exit(1)

DLL_DIR.mkdir(parents=True, exist_ok=True)
for dll in BUILD.rglob("*.dll"):
    shutil.copy2(dll, DLL_DIR / dll.name)
    print(f"  Installed: {dll.name}")

print("Install complete. Restart CATIA.")
