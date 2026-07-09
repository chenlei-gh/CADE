#!/usr/bin/env python3
"""FrameworkName — Package for deployment"""

import shutil, zipfile
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
BUILD = ROOT / "Build" / "win_b64" / "code"
DIST = ROOT / "dist"
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

if not BUILD.exists():
    print(f"Error: Build directory not found: {BUILD}")
    print("Run full_build.py first.")
    exit(1)

DIST.mkdir(exist_ok=True)
zip_path = DIST / f"FrameworkName_{timestamp}.zip"

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for dll in BUILD.rglob("*.dll"):
        zf.write(dll, dll.relative_to(BUILD.parent))
    for h in ROOT.rglob("*.h"):
        if "PublicInterfaces" in str(h):
            zf.write(h, h.relative_to(ROOT))

print(f"Packaged: {zip_path}")
print(f"Size: {zip_path.stat().st_size / 1024:.1f} KB")
