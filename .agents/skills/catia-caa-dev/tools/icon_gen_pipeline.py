"""
Generated-Base icon post-processing pipeline (ICON_GENERATION_SPEC §4).

Takes a text-to-image PNG from tmp/gen_inbox/, normalizes it into a
CATIA-native 22x22 8-bit palettized BMP, and emits:
  - <stem>.bmp          final asset (8-bit, background = palette index 0)
  - <stem>_8x.png       8x nearest-neighbor preview for human review
  - <stem>_gate.json    gate report (colors, fg%, corner purity) + provenance draft

Usage:
  python icon_gen_pipeline.py <input.png> <stem> [--out DIR]

Gate thresholds (spec §5):
  22x22, <=16 colors, pure four corners, fg% in [15%, 70%].
"""

import json, sys
from datetime import date
from pathlib import Path

from PIL import Image

# Reuse the CNEXT-safe BMP writer, style constants and B28 resolver.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills"))
from icon_provider import (  # noqa: E402
    _save_palette_bmp, _official_icons_dir, CATIA_BG,
)

# ── Spec constants (§2, §5) ──────────────────────────────────────────
CANVAS = 22                     # final canvas edge
MAX_COLORS = 16                 # MedianCut ceiling
BG_TOLERANCE = 36               # corner-snap tolerance (per channel)
FG_MIN, FG_MAX = 0.15, 0.70    # foreground ratio gate
PREVIEW_SCALE = 8               # 8x preview for human review


def _center_crop_square(img: Image.Image) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def _snap_background(rgb: Image.Image) -> Image.Image:
    """Four-corner sample → pixels within BG_TOLERANCE of the sampled
    background color are forced to exact CATIA_BG. Guarantees pure corners
    and a uniform background for CNEXT transparency."""
    px = rgb.load()
    w, h = rgb.size
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    # Average the four corners as the reference background.
    ref = tuple(sum(c[i] for c in corners) // 4 for i in range(3))
    snapped = 0
    for y in range(h):
        for x in range(w):
            p = px[x, y]
            if all(abs(p[i] - ref[i]) <= BG_TOLERANCE for i in range(3)):
                if p != CATIA_BG:
                    px[x, y] = CATIA_BG
                    snapped += 1
    return rgb, snapped


def _fg_ratio(rgb: Image.Image) -> float:
    """Fraction of pixels that differ from CATIA_BG by > BG_TOLERANCE."""
    px = rgb.load()
    w, h = rgb.size
    fg = 0
    for y in range(h):
        for x in range(w):
            p = px[x, y]
            if any(abs(p[i] - CATIA_BG[i]) > BG_TOLERANCE for i in range(3)):
                fg += 1
    return fg / (w * h)


def _corner_pure(rgb: Image.Image) -> bool:
    px = rgb.load()
    w, h = rgb.size
    return all(px[x, y] == CATIA_BG
               for x, y in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)])


def process(src: Path, stem: str, out_dir: Path) -> dict:
    img = Image.open(src).convert("RGB")

    # 1. center-crop square → LANCZOS to 22x22
    img = _center_crop_square(img)
    img = img.resize((CANVAS, CANVAS), Image.LANCZOS)

    # 2. MedianCut quantize ≤16 colors (no dithering)
    img = img.quantize(colors=MAX_COLORS, method=Image.Quantize.MEDIANCUT,
                       dither=Image.Dither.NONE).convert("RGB")

    # 3. background snap
    img, snapped = _snap_background(img)

    # 4. gate metrics
    colors = len(img.getcolors(maxcolors=256) or [])
    fg = _fg_ratio(img)
    corners_ok = _corner_pure(img)
    gate = {
        "size": f"{CANVAS}x{CANVAS}",
        "colors": colors,
        "colors_ok": colors <= MAX_COLORS,
        "fg": round(fg, 3),
        "fg_ok": FG_MIN <= fg <= FG_MAX,
        "corners_pure": corners_ok,
        "bg_snapped_px": snapped,
    }
    gate["pass"] = gate["colors_ok"] and gate["fg_ok"] and gate["corners_pure"]

    # 5. outputs
    out_dir.mkdir(parents=True, exist_ok=True)
    bmp_path = out_dir / f"{stem}.bmp"
    _save_palette_bmp(img, bmp_path)

    preview = img.resize((CANVAS * PREVIEW_SCALE, CANVAS * PREVIEW_SCALE),
                         Image.NEAREST)
    png_path = out_dir / f"{stem}_8x.png"
    preview.save(png_path)

    report = {
        "stem": stem,
        "source": str(src),
        "generated_at": str(date.today()),
        "pipeline": "icon_gen_pipeline.py v1",
        "gate": gate,
        "outputs": {"bmp": str(bmp_path), "preview": str(png_path)},
        # provenance draft — user fills model/prompt/seed/metaphor at review
        "provenance": {
            "stem": stem,
            "semantic": "",
            "model": "",
            "prompt": "",
            "seed": None,
            "metaphor": "",   # model's visual metaphor, recorded at review
            "generated_at": str(date.today()),
            "pipeline": "icon_gen_pipeline.py v1",
            "gate": {"colors": colors, "fg": round(fg, 3)},
            "approved_by": "",
            "approved_at": "",
        },
    }
    json_path = out_dir / f"{stem}_gate.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    return report


# ── Batch mode + comparison sheet (spec §3, §8) ─────────────────────
ANCHOR_STEMS = ["I_Hole", "I_Pad", "I_Pocket"]  # official style anchors


def _load_anchor() -> list:
    """Official B28 anchors at 22x22 RGB for the comparison sheet.
    Empty list when CATIA install not found (sheet still emitted)."""
    d = _official_icons_dir()
    out = []
    if d is None:
        return out
    for stem in ANCHOR_STEMS:
        p = d / f"{stem}.bmp"
        if p.is_file():
            out.append((stem, Image.open(p).convert("RGB")))
    return out


def _comparison_sheet(cands: list, anchors: list, out: Path) -> Path:
    """Side-by-side 8x sheet: official anchors (top row) vs candidates
    (bottom row). Direct Visual-QA artifact for spec §5-C/E."""
    from PIL import ImageDraw
    cell = CANVAS * PREVIEW_SCALE
    label_h, gap = 18, 6
    cols = max(len(cands), len(anchors), 1)
    rows = 2 if anchors else 1
    sheet = Image.new("RGB",
                      (cols * (cell + gap) + gap,
                       rows * (cell + label_h + gap) + gap),
                      (230, 230, 230))
    draw = ImageDraw.Draw(sheet)

    def _paste(img, stem, row, col):
        x = gap + col * (cell + gap)
        y = gap + row * (cell + label_h + gap)
        sheet.paste(img.resize((cell, cell), Image.NEAREST), (x, y))
        draw.text((x + 2, y + cell + 2), stem, fill=(20, 20, 20))

    for i, (stem, img) in enumerate(anchors):
        _paste(img, stem, 0, i)
    row = 1 if anchors else 0
    for i, (stem, img) in enumerate(cands):
        _paste(img, stem, row, i)
    sheet.save(out)
    return out


def batch(in_dir: Path, stem: str, out_dir: Path) -> list:
    """Process every candidate PNG in in_dir (excluding pipeline outputs),
    stems suffixed _A/_B/... in sorted order, then emit one sheet."""
    srcs = sorted(p for p in in_dir.glob("*.png")
                  if not p.stem.endswith(("_8x", "_sheet")))
    if not srcs:
        sys.exit(f"no candidate PNGs in {in_dir}")
    reports, cands = [], []
    for i, src in enumerate(srcs):
        cstem = f"{stem}_{chr(65 + i)}"
        rep = process(src, cstem, out_dir)
        reports.append(rep)
        cands.append((cstem, Image.open(rep["outputs"]["bmp"]).convert("RGB")))
        g = rep["gate"]
        print(f"[{'PASS' if g['pass'] else 'FAIL'}] {cstem}  "
              f"colors={g['colors']} fg={g['fg']:.1%} "
              f"corners={'pure' if g['corners_pure'] else 'DIRTY'}  ← {src.name}")
    sheet = _comparison_sheet(cands, _load_anchor(),
                              out_dir / f"{stem}_sheet.png")
    print(f"sheet : {sheet}")
    if any(not r["gate"]["pass"] for r in reports):
        sys.exit(1)
    return reports


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Generated-base icon pipeline")
    ap.add_argument("input", type=Path,
                    help="source PNG, or candidate directory with --batch")
    ap.add_argument("stem", help="asset stem, e.g. I_CADEPartToAsm")
    ap.add_argument("--out", type=Path,
                    default=Path("tmp/gen_inbox"),
                    help="output directory (default: tmp/gen_inbox/)")
    ap.add_argument("--batch", action="store_true",
                    help="process all PNGs in input dir, stems get _A/_B/... "
                         "suffixes, emit comparison sheet vs official anchors")
    args = ap.parse_args()

    if args.batch:
        if not args.input.is_dir():
            sys.exit(f"--batch needs a directory: {args.input}")
        batch(args.input, args.stem, args.out)
        return

    if not args.input.exists():
        sys.exit(f"input not found: {args.input}")

    report = process(args.input, args.stem, args.out)
    g = report["gate"]
    status = "PASS" if g["pass"] else "FAIL"
    print(f"[{status}] {args.stem}")
    print(f"  size    : {g['size']}")
    print(f"  colors  : {g['colors']} (max {MAX_COLORS})")
    print(f"  fg      : {g['fg']:.1%} (gate [{FG_MIN:.0%}, {FG_MAX:.0%}])")
    print(f"  corners : {'pure' if g['corners_pure'] else 'DIRTY'}")
    print(f"  snapped : {g['bg_snapped_px']} px → CATIA_BG")
    print(f"  outputs : {report['outputs']['bmp']}")
    print(f"            {report['outputs']['preview']}")
    print(f"            {args.out / (args.stem + '_gate.json')}")
    if not g["pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
