"""Design source for I_CADEPartToAsm.bmp — regenerates the production asset.

Metaphor (user-approved, gate E passed 2026-08-18): official gear vocabulary.
  LEFT  single yellow 8-tooth gear r4  = part     (I_Part language)
  RIGHT cyan r3 (top) meshing yellow r4 (bottom) = assembly (I_Product language)
  gap between them = the part->assembly transition; no arrow, no badge.
Full-bleed composition, fg = 47.9% (user: 要铺满; v4 at 24% rejected).

Run:  python I_CADEPartToAsm.py        (from anywhere)
Out:  I_CADEPartToAsm.bmp rewritten next to this file (pipeline-gated).
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL = HERE.parents[3]                      # catia-caa-dev/
REPO = HERE.parents[6]                       # repository root
sys.path.insert(0, str(SKILL / "tools"))

from icon_design_lib import canvas, gear, CYAN, CYAN_EDGE  # noqa: E402
from icon_gen_pipeline import process                      # noqa: E402

STEM = "I_CADEPartToAsm"


def build():
    img, d = canvas()
    gear(d, 5, 12, 4)                                 # part: single yellow gear
    gear(d, 15, 6, 3, face=CYAN, edge=CYAN_EDGE)      # asm: cyan gear (top)
    gear(d, 16, 16, 4)                                # asm: yellow gear (bottom)
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
