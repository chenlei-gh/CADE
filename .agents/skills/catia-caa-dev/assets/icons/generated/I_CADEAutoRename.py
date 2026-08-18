"""Design source for I_CADEAutoRename.bmp — regenerates the production asset.

Metaphor (rule-selected, no manual pick): official rename vocabulary.
  LEFT  white name card with hand-drawn pixel 'A' (I_RenameFamily language)
  RIGHT yellow gear r3 = automation
  The 'A' MUST be letter_a(): PIL's default font anti-aliases (Pillow >= 10)
  and violates the spec's hard-edge clause; no badge.

Run:  python I_CADEAutoRename.py        (from anywhere)
Out:  I_CADEAutoRename.bmp rewritten next to this file (pipeline-gated).
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL = HERE.parents[3]                      # catia-caa-dev/
REPO = HERE.parents[6]                       # repository root
sys.path.insert(0, str(SKILL / "tools"))

from icon_design_lib import canvas, gear, letter_a, INK, WHITE  # noqa: E402
from icon_gen_pipeline import process                           # noqa: E402

STEM = "I_CADEAutoRename"


def build():
    img, d = canvas()
    d.rectangle([2, 3, 15, 18], fill=WHITE, outline=INK, width=2)   # card
    d.rectangle([4, 5, 13, 16], fill=WHITE)                         # inner white
    letter_a(d, 5, 6)                                               # pixel 'A'
    gear(d, 16, 15, 3)                                              # automation
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
