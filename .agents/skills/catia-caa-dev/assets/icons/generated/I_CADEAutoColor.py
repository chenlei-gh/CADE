"""Design source for I_CADEAutoColor.bmp — regenerates the production asset.

Metaphor (rule-selected, no manual pick): official color vocabulary.
  LEFT  2x3 saturated swatch grid (I_AutomaticColorProperty language)
  RIGHT yellow 8-tooth gear r4 pressing the swatch edge = automation
  Dense composition: gear overlaps the right swatch column; no badge.

Run:  python I_CADEAutoColor.py        (from anywhere)
Out:  I_CADEAutoColor.bmp rewritten next to this file (pipeline-gated).
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL = HERE.parents[3]                      # catia-caa-dev/
REPO = HERE.parents[6]                       # repository root
sys.path.insert(0, str(SKILL / "tools"))

from icon_design_lib import canvas, gear, swatches  # noqa: E402
from icon_gen_pipeline import process               # noqa: E402

STEM = "I_CADEAutoColor"


def build():
    img, d = canvas()
    swatches(d, 1, 2, 2, 3, 6, 6)   # 2 cols x 3 rows, y=2..7/9..14/16..21
    gear(d, 15, 14, 4)              # automation gear over swatch right edge
    return img


if __name__ == "__main__":
    build_dir = REPO / "tmp" / "gen_inbox" / "design_build"
    build_dir.mkdir(parents=True, exist_ok=True)
    src = build_dir / f"{STEM}_src.png"
    build().save(src)
    rep = process(src, STEM, build_dir)
    dst = HERE.with_suffix(".bmp")
    shutil.copy(rep["outputs"]["bmp"], dst)
    g = rep["gate"]
    ok = "PASS" if g["pass"] else "FAIL"
    print(f"[{ok}] {STEM} regenerated -> {dst}")
    print(f"  colors={g['colors']} fg={g['fg']:.1%} "
          f"corners={'pure' if g['corners_pure'] else 'DIRTY'}")
    sys.exit(0 if g["pass"] else 1)
