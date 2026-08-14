#!/usr/bin/env python3
"""
Golden Icon Sample Generator
=============================
Regenerates tests/golden/icons/*.bmp — the visual regression baseline
for test_icons.py Part J.

Run ONLY after an intentional renderer/style change, then EYEBALL the
golden files (they encode the official CATIA visual language; the test
locks pixels, a human locks style).

Usage: python tests/update_golden_icons.py
"""

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from icon_provider import _render_icon

# (base, badge) — curated to cover: core modeling patterns, each badge
# glyph in use, accent/multi-color patterns, and the neutral fallback.
GOLDEN = [
    ("circle", None), ("circle", "plus"),
    ("cube", None), ("cube", "pencil"), ("cube", "check"), ("cube", "refresh"),
    ("hole", None), ("drill", "plus"), ("drill", "chart"),
    ("fillet", None), ("chamfer", None), ("split", None), ("rotate", None),
    ("shell", None), ("sweep", None), ("loft", None), ("helix", None),
    ("plane", None), ("axis", None), ("mirror", None), ("boolean", None),
    ("pattern", None), ("pencil", None), ("ruler", None), ("window", None),
    ("settings", None), ("star", None), ("heart", None),
    ("diamond", None),  # fallback
]


def main():
    out = SKILL_ROOT / "tests" / "golden" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for base, badge in GOLDEN:
        fn = out / (f"{base}+{badge}.bmp" if badge else f"{base}.bmp")
        fn.write_bytes(_render_icon(base, badge).read_bytes())
        print("wrote", fn.name)
    print(f"\n{len(GOLDEN)} golden samples in {out}")
    print("REMINDER: eyeball the samples — the test locks pixels, you lock style.")


if __name__ == "__main__":
    main()
