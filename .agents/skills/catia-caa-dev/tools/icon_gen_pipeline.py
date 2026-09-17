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


def _check_edge_collision(rgb: Image.Image) -> tuple:
    """Check if foreground subject collides heavily with canvas outer borders.
    Returns (passed, edge_stats). If >60% of any single border is foreground,
    it indicates hard canvas truncation."""
    px = rgb.load()
    w, h = rgb.size
    
    def is_fg(p):
        return any(abs(p[i] - CATIA_BG[i]) > BG_TOLERANCE for i in range(3))

    top_fg = sum(1 for x in range(w) if is_fg(px[x, 0]))
    bottom_fg = sum(1 for x in range(w) if is_fg(px[x, h - 1]))
    left_fg = sum(1 for y in range(h) if is_fg(px[0, y]))
    right_fg = sum(1 for y in range(h) if is_fg(px[w - 1, y]))

    stats = {
        "top_fg_ratio": round(top_fg / w, 2),
        "bottom_fg_ratio": round(bottom_fg / w, 2),
        "left_fg_ratio": round(left_fg / h, 2),
        "right_fg_ratio": round(right_fg / h, 2),
    }
    # Pass if no edge is severely cut off (> 60% clipped)
    no_collision = all(r <= 0.60 for r in stats.values())
    return no_collision, stats


def _detect_isolated_noise(rgb: Image.Image) -> int:
    """Soft lint: counts isolated foreground pixels that have no 8-neighbors.
    Returns count of stray isolated pixels.
    NOTE: Used for report and human review; not a hard gate failure condition."""
    px = rgb.load()
    w, h = rgb.size
    
    def is_fg(x, y):
        if not (0 <= x < w and 0 <= y < h):
            return False
        p = px[x, y]
        return any(abs(p[i] - CATIA_BG[i]) > BG_TOLERANCE for i in range(3))

    isolated_count = 0
    for y in range(h):
        for x in range(w):
            if is_fg(x, y):
                # Count neighbors
                neighbors = 0
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if (dx != 0 or dy != 0) and is_fg(x + dx, y + dy):
                            neighbors += 1
                if neighbors == 0:
                    isolated_count += 1
    return isolated_count


def lint_bmp_asset(bmp_path: Path) -> dict:
    """Reusable engineering lint for any 22x22 CATIA runtime BMP.
    Returns hard_checks, soft_lints, and overall pass/fail status."""
    with Image.open(bmp_path) as im:
        assert im.size == (CANVAS, CANVAS), f"BMP must be {CANVAS}x{CANVAS}, got {im.size}"
        bmp_mode_ok = (im.mode == "P")
        pal = im.getpalette() or []
        palette_bg_ok = (len(pal) >= 3 and (pal[0], pal[1], pal[2]) == CATIA_BG)
        colors = len(im.getcolors(maxcolors=256) or [])

        rgb = im.convert("RGB")
        corners_ok = _corner_pure(rgb)
        no_collision, edge_stats = _check_edge_collision(rgb)
        fg = _fg_ratio(rgb)
        noise_px = _detect_isolated_noise(rgb)

    hard_checks = {
        "colors_ceiling_ok": colors <= MAX_COLORS,
        "corners_pure": corners_ok,
        "no_edge_collision": no_collision,
        "bmp_format_ok": bmp_mode_ok and palette_bg_ok,
    }

    soft_lints = {
        "fg_ratio": round(fg, 3),
        "fg_in_guidance": FG_MIN <= fg <= FG_MAX,
        "fg_guidance_note": "15%-70% general envelope; 68%-72% recommended for centered solid mechanical parts",
        "isolated_noise_px": noise_px,
        "isolated_noise_note": "Report-only soft lint; does not trigger hard failure",
        "edge_ratios": edge_stats,
    }

    return {
        "file": str(bmp_path),
        "colors": colors,
        "hard_checks": hard_checks,
        "soft_lints": soft_lints,
        "pass": all(hard_checks.values()),
    }


def lint_alpha_png(png_path: Path) -> dict:
    """Reusable engineering lint for transparent multi-scale PNG assets.
    Verifies Alpha integrity, corner transparency, and detects halo/dirty edges."""
    with Image.open(png_path) as im:
        assert im.mode == "RGBA", f"PNG must be RGBA mode, got {im.mode}"
        w, h = im.size
        alpha = im.getchannel("A")
        min_a, max_a = alpha.getextrema()
        has_transparency = min_a < 255

        # Check four corners are 100% transparent (A == 0)
        px_a = alpha.load()
        corners_alpha_zero = all(
            px_a[x, y] == 0
            for x, y in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
        )

        # Transparency dirty edge / contamination check:
        # For pixels with A == 0, RGB should be clean (ideally (0,0,0) or uniform).
        px = im.load()
        dirty_zero_alpha_px = 0
        semi_trans_count = 0
        opaque_count = 0
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0:
                    if (r, g, b) != (0, 0, 0):
                        dirty_zero_alpha_px += 1
                elif a < 255:
                    semi_trans_count += 1
                else:
                    opaque_count += 1

        total_visible = semi_trans_count + opaque_count
        semi_ratio = round(semi_trans_count / total_visible, 3) if total_visible > 0 else 0.0

        # Alpha is clean if corners are fully transparent and zero-alpha pixels carry no dirty RGB spill
        alpha_clean = corners_alpha_zero and has_transparency and (dirty_zero_alpha_px == 0)

        return {
            "file": str(png_path),
            "size": f"{w}x{h}",
            "has_transparency": has_transparency,
            "corners_alpha_zero": corners_alpha_zero,
            "dirty_zero_alpha_pixels": dirty_zero_alpha_px,
            "semi_transparent_ratio": semi_ratio,
            "alpha_clean": alpha_clean,
        }


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

    # 4. output paths
    out_dir.mkdir(parents=True, exist_ok=True)
    bmp_path = out_dir / f"{stem}.bmp"
    _save_palette_bmp(img, bmp_path)

    preview = img.resize((CANVAS * PREVIEW_SCALE, CANVAS * PREVIEW_SCALE),
                         Image.NEAREST)
    png_path = out_dir / f"{stem}_8x.png"
    preview.save(png_path)

    # 5. Engineering Linting via reusable lint_bmp_asset
    bmp_lint = lint_bmp_asset(bmp_path)
    colors = bmp_lint["colors"]
    fg = bmp_lint["soft_lints"]["fg_ratio"]
    corners_ok = bmp_lint["hard_checks"]["corners_pure"]

    gate = {
        "size": f"{CANVAS}x{CANVAS}",
        "colors": colors,
        "colors_ok": bmp_lint["hard_checks"]["colors_ceiling_ok"],
        "fg": fg,
        "fg_ok": bmp_lint["soft_lints"]["fg_in_guidance"],
        "corners_pure": corners_ok,
        "bg_snapped_px": snapped,
        "hard_checks": bmp_lint["hard_checks"],
        "soft_lints": bmp_lint["soft_lints"],
        "pass": bmp_lint["pass"],
    }

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
ANCHOR_STEMS = ["I_Hole", "I_Pad", "I_Pocket"]  # default style anchors


def _load_anchor(stems=None) -> list:
    """Official B28 anchors at 22x22 RGB for the comparison sheet.
    Empty list when CATIA install not found (sheet still emitted)."""
    d = _official_icons_dir()
    out = []
    if d is None:
        return out
    for stem in (stems or ANCHOR_STEMS):
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


def batch(in_dir: Path, stem: str, out_dir: Path,
          anchors: list = None) -> list:
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
    sheet = _comparison_sheet(cands, _load_anchor(anchors),
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
    ap.add_argument("--anchors", type=lambda s: s.split(","), default=None,
                    help="comma-separated official anchor stems for the sheet, "
                         "e.g. I_Part,I_Product (default: I_Hole,I_Pad,I_Pocket)")
    args = ap.parse_args()

    if args.batch:
        if not args.input.is_dir():
            sys.exit(f"--batch needs a directory: {args.input}")
        batch(args.input, args.stem, args.out, anchors=args.anchors)
        return

    if not args.input.exists():
        sys.exit(f"input not found: {args.input}")

    report = process(args.input, args.stem, args.out)
    g = report["gate"]
    status = "PASS" if g["pass"] else "FAIL"
    print(f"[{status}] {args.stem}")
    print(f"  size        : {g['size']}")
    print(f"  colors      : {g['colors']} (max {MAX_COLORS})")
    print(f"  hard_checks : {g['hard_checks']}")
    print(f"  soft_lints  : fg={g['soft_lints']['fg_ratio']:.1%} (guidance [{FG_MIN:.0%}, {FG_MAX:.0%}]), noise={g['soft_lints']['isolated_noise_px']}px")
    print(f"  outputs     : {report['outputs']['bmp']}")
    print(f"                {report['outputs']['preview']}")
    print(f"                {args.out / (args.stem + '_gate.json')}")
    if not g["pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
