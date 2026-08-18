"""Design source for I_CADEBOMTool.bmp — regenerates the production asset.

Metaphor (rule-selected, no manual pick): official BOM vocabulary.
  LEFT  assembly tree: parent node + two children with INK connectors
        (specification-tree language)
  RIGHT white table card with 3 blue rows (I_DNBBOMtoXML language)
  Yellow node faces tie to the PartToAsm gear family; no badge.

Run:  python I_CADEBOMTool.py        (from anywhere)
Out:  I_CADEBOMTool.bmp rewritten next to this file (pipeline-gated).
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL = HERE.parents[3]                      # catia-caa-dev/
REPO = HERE.parents[6]                       # repository root
sys.path.insert(0, str(SKILL / "tools"))

from icon_design_lib import canvas, GEAR_FACE, INK, WHITE  # noqa: E402
from icon_gen_pipeline import process                     # noqa: E402

STEM = "I_CADEBOMTool"
ROW_BLUE = (0, 140, 255)   # BOM table row accent (I_DNBBOMtoXML)


def build():
    img, d = canvas()
    d.rectangle([2, 2, 7, 6], fill=GEAR_FACE, outline=INK)      # parent node
    d.rectangle([1, 12, 6, 16], fill=GEAR_FACE, outline=INK)    # child 1
    d.rectangle([1, 18, 6, 21], fill=GEAR_FACE, outline=INK)    # child 2
    d.line([(4, 6), (4, 9), (3, 9), (3, 12)], fill=INK)         # link 1
    d.line([(4, 9), (4, 18), (3, 18)], fill=INK)                # link 2
    d.rectangle([10, 8, 20, 20], fill=WHITE, outline=INK, width=2)  # table
    for i in range(3):
        d.line([(12, 11 + i * 3), (18, 11 + i * 3)], fill=ROW_BLUE)
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
