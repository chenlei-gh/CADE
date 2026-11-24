"""
CADE Universal Icon Studio (icon_studio.py)
===========================================
Universal High-Definition Icon Generation Engine & Workflow Deployer for CATIA CAA.

Key Capabilities:
  1. Dual-Track Asset Pipeline:
     - 512x512 Master RGBA (metallic highlights, ambient soft shadows) -- design
       artefact and documentation source only, never downscaled into a toolbar icon
     - 256x256 HD / Documentation asset
     - 64x64 High-DPI UI asset
     - 32x32 CATIA Large Mode asset (RGBA PNG + 8-bit indexed BMP)
     - 22x22 CATIA Normal Mode asset (RGBA PNG + 8-bit indexed BMP)
  2. Micro-Icon Contract (22 / 32 px):
     - Rendered independently on an integer pixel grid, never resampled from the master:
       a 4px feature on a 512px master lands at 0.17px at 22px and cannot survive
     - Built the way official CATIA command icons are: a 1px navy silhouette
       encloses flat fills, with 1px internal creases and deliberate face accents.
       Pixel measurements of B28 I_Pad/I_Hole/I_Pocket confirm this construction.
     - Large mode is not the 22px artwork magnified -- each renderer has a native
       32px layout and spends the extra pixels on legible structural detail
     - Foreground colour budget: 16 colours at 22px, 24 at 32px (hard FAIL above)
     - Hard-edge ratio >= 0.85 and zero dither speckle
  3. CATIA CNEXT Dual-Transparency Contract:
     - 8-bit palettized BMP (<=256 colors)
     - CADE's own writer pins palette index 0 to the declared background mask
       (CATIA_BG gray, CATIA_INK navy and 180-gray are the recognised legal masks).
       Official B28 icons do not: their background sits at an arbitrary index, so
       lint_icon_asset(..., profile="official") judges it by colour instead.
     - Four-corner background snap guaranteeing zero dirty halos
  4. Parametric Morpheme & Semantic Resolver:
     - Automatically infers domain metaphors from any tool name (date/stamp, part/asm, bom/table,
       color/swatch, rename/tag, pad/solid, pocket/cavity, gear, curve/surface, etc.)
     - Supports custom metaphor overrides and external image/logo high-resolution remastering
  5. Full Workflow Integration:
     - deploy_tool_icon(): Generates assets, writes normal/large BMPs into CNext/resources/graphic/icons/normal/,
       and updates .CATRsc with both Icon.Normal and Icon.Large declarations
     - Seamlessly hooked into actions.create_command and build.sync_runtime_view
  6. Blocking Quality Gate:
     - G1 format / G2 colour budget / G3 contour / G4 geometry are hard checks
     - Any failure blocks deployment and `.CATRsc` injection; there is no WARN passthrough
"""

import json
import math
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter

# ── Paths & Core Imports ───────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
ASSETS_DIR = SKILL_ROOT / "assets" / "icons" / "generated"

# Official CATIA Color Constants
CATIA_BG   = (192, 192, 192)    # #C0C0C0 standard toolbar background gray
CATIA_INK  = (24, 16, 82)       # #181052 structure outline & 3D shadow
FACE_GOLD  = (255, 255, 150)    # PartDesign solid face lemon/engineering gold
GEAR_FACE  = (255, 238, 135)    # Assembly gear face
CYAN       = (75, 230, 255)     # Wireframe / geometry auxiliary lines
WHITE      = (255, 255, 255)    # Highlight
RED_MARK   = (195, 20, 20)      # Cut / operation target edge

MASTER_SIZE = 512
# Documentation / high-DPI exports only. The 22 and 32 CATIA runtime sizes are
# deliberately absent: they are rendered on their own pixel grid further down
# and must never be produced by resampling this master.
EXPORT_SPECS = [
    (512, "_512.png", "Master Ultra-HD (512x512) RGBA"),
    (256, "_256.png", "Documentation HD (256x256) RGBA"),
    (64,  "_64.png",  "High-DPI UI (64x64) RGBA"),
]


# ── Quality Gate Spec ──────────────────────────────────────────────
# Only the constants the gate actually reads live here; the micro-icon
# contract below owns the rest (previously MAX_COLORS=256 sat alongside the
# 16/24 budget and read as a live ceiling when nothing consumed it).
BG_TOLERANCE = 36
FG_MIN = 0.15

# Canvas-utilisation contract, measured on the installed B28 icon sets.
#
# 22x22 (`icons/normal`, 8286 files): content bounding box median 20x20, the
# dominant mask margins are 1px (47%) and 0px (42%). 32x32 (`icons/large`,
# 210 files at that size): bbox median 30x30.
#
# CADE used to draw into 18x18 and 27x27 -- one 2px margin where the official
# set keeps 1px -- so every generated icon carried ~20% less subject than the
# icons sitting beside it in the same toolbar, at a canvas size that cannot be
# raised. These two constants make that gap a gate failure instead of a taste
# judgement, so newly added metaphors inherit the official framing.
CONTENT_MARGIN = 1                       # every side keeps >= this much mask
CONTENT_MIN_EDGE = {22: 20, 32: 30}      # content bbox must reach this square


def fg_ratio_ceiling(size: int) -> float:
    """Largest legal foreground ratio at `size`, given the mask margin.

    A single global ceiling cannot express this contract: a fully painted
    subject that still keeps CONTENT_MARGIN occupies (size-2)^2 pixels, i.e.
    0.826 at 22px but 0.879 at 32px. A flat 0.85 ceiling therefore passed a
    22px solid face while rejecting the identical 32px drawing. Deriving the
    bound from the framing contract keeps the two from drifting apart.

    Calibration: the official 22x22 set is median 43.2% foreground, p90 87.6%,
    and 12.9% of its icons exceed 75%. The old 0.75 ceiling rejected that
    legitimate official-style iconography while still admitting a 100% painted
    canvas, which is the real degeneration -- the margin contract is what now
    guarantees an icon is never an unbounded colour block.
    """
    inner = max(1, size - 2 * CONTENT_MARGIN)
    return (inner * inner) / float(size * size)


# Micro-icon design contract (22/32 px). Owned by CADE, not by individual icons:
# every renderer that feeds a CATIA BMP must obey it, so new tool icons inherit
# the same bar automatically.
#
# Colour budget basis, measured across the 8293 official B28 22x22 icons:
# median 5 foreground colours, p90 = 20, p99 = 174, max 253. So 16 is stricter
# than the official median-plus-tail but still admits the bulk of real icons;
# it is a budget for *deliberate* palettes, not a claim that CATIA forbids more.
PIXEL_SIZES = (22, 32)
MAX_FG_COLORS = {22: 16, 32: 24}   # hard FAIL above this (background excluded)
SHARP_EDGE_DELTA = 56              # per-channel delta that counts as a "hard" edge
MIN_SHARP_RATIO = 0.85             # official icons 0.94+; degraded ones 0.21-0.43
MAX_ISOLATED_RATIO = 0.02          # anti dither / speckle gate
LEGAL_BG_COLORS = (CATIA_BG, CATIA_INK, (180, 180, 180))

# Geometry is authored in final-output pixels. A 32px icon therefore has its
# own 32-unit layout rather than reusing a 22-unit layout with larger pixels.
# Supersampling is only a rasterization aid: every physical output pixel is
# point-sampled once, so no resampling filter can introduce transitional colours.
PIXEL_SUPERSAMPLE = 4

# B28 I_Pad/I_Hole/I_Pocket use a one-physical-pixel navy contour. The previous
# 2px band consumed the small faces and made every metaphor look heavy.
PIXEL_INK_WIDTH = 1.0
POINT_SPLIT_WIDTH = 1.0


class _PixelGrid:
    """Supersampled drawing surface addressed in final-output pixels.

    Integer coordinates refer to output-pixel boundaries, not a shared logical
    22px grid. Renderers explicitly choose separate 22px and 32px geometry.
    """

    def __init__(self, size: int, bg_color: Tuple[int, int, int]):
        self.size = size
        self.design_size = size
        self.scale = float(PIXEL_SUPERSAMPLE)
        self.bg = tuple(bg_color)
        side = size * PIXEL_SUPERSAMPLE
        self.img = Image.new("RGB", (side, side), self.bg)
        self.d = ImageDraw.Draw(self.img)

    def s(self, v: float) -> float:
        """Design unit -> supersampled coordinate."""
        return v * self.scale

    def box(self, x0: float, y0: float, x1: float, y1: float) -> List[float]:
        return [self.s(x0), self.s(y0), self.s(x1), self.s(y1)]

    def poly(self, points: Sequence[Tuple[float, float]]) -> List[float]:
        flat: List[float] = []
        for x, y in points:
            flat.extend((self.s(x), self.s(y)))
        return flat

    def band(self, ink_px: float) -> int:
        """Contour width in supersampled pixels."""
        return max(1, int(round(ink_px * PIXEL_SUPERSAMPLE)))

    # -- primitives --------------------------------------------------------
    def face(self, points: Sequence[Tuple[float, float]],
             fill: Tuple[int, int, int], ink_px: float = PIXEL_INK_WIDTH) -> None:
        """Flat face wrapped in a constant-width ink contour.

        Pillow strokes `outline` inwards, so filling first and then outlining
        gives exactly `ink_px` of ink inside every edge without eroding the
        feature -- the failure mode of stroking a 6px shape from the outside.
        """
        flat = self.poly(points)
        self.d.polygon(flat, fill=fill)
        self.d.polygon(flat, outline=CATIA_INK, width=self.band(ink_px))

    def disc(self, cx: float, cy: float, r: float,
             fill: Tuple[int, int, int], ink_px: float = PIXEL_INK_WIDTH) -> None:
        """Disc with an ink bezel; the fill is stroked, never the silhouette."""
        bb = self.box(cx - r, cy - r, cx + r, cy + r)
        self.d.ellipse(bb, fill=fill)
        self.d.ellipse(bb, outline=CATIA_INK, width=self.band(ink_px))

    def bar(self, x0: float, y0: float, x1: float, y1: float,
            fill: Tuple[int, int, int]) -> None:
        self.d.rectangle(self.box(x0, y0, x1, y1), fill=fill)

    def rect(self, x0: float, y0: float, x1: float, y1: float,
             fill: Tuple[int, int, int], ink_px: float = PIXEL_INK_WIDTH,
             outline: Tuple[int, int, int] = CATIA_INK) -> None:
        self.d.rectangle(self.box(x0, y0, x1, y1), fill=fill,
                         outline=outline, width=self.band(ink_px))

    def solid(self, points: Sequence[Tuple[float, float]],
              fill: Tuple[int, int, int]) -> None:
        """Uncontoured fill -- only for faces that sit inside an existing ink body."""
        self.d.polygon(self.poly(points), fill=fill)

    def ring(self, cx: float, cy: float, r: float,
             color: Tuple[int, int, int], thick_px: float = PIXEL_INK_WIDTH) -> None:
        bb = self.box(cx - r, cy - r, cx + r, cy + r)
        self.d.ellipse(bb, outline=color, width=self.band(thick_px))


    def outline(self, points: Sequence[Tuple[float, float]],
                ink_px: float = PIXEL_INK_WIDTH) -> None:
        """Stroke a silhouette without repainting it -- outer contour only."""
        self.d.polygon(self.poly(points), outline=CATIA_INK, width=self.band(ink_px))

    def line(self, points: Sequence[Tuple[float, float]],
             color: Tuple[int, int, int] = CATIA_INK,
             width_px: float = POINT_SPLIT_WIDTH) -> None:
        flat: List[float] = []
        for x, y in points:
            flat.extend((self.s(x), self.s(y)))
        self.d.line(flat, fill=color, width=self.band(width_px))

    def edge(self, x0: float, y0: float, x1: float, y1: float,
             ink_px: float = POINT_SPLIT_WIDTH) -> None:
        """One-pixel internal crease, matching the outer contour weight."""
        self.line([(x0, y0), (x1, y1)], width_px=ink_px)

    def result(self) -> Image.Image:
        """Point-sample the centre of every physical pixel (no blur)."""
        off = PIXEL_SUPERSAMPLE // 2
        src = self.img.load()
        out = Image.new("RGB", (self.size, self.size))
        dst = out.load()
        for y in range(self.size):
            sy = y * PIXEL_SUPERSAMPLE + off
            for x in range(self.size):
                dst[x, y] = src[x * PIXEL_SUPERSAMPLE + off, sy]
        return out


# ── Drawing Primitives for 512 Master ──────────────────────────────────
def _draw_gradient_polygon(target: Image.Image, points: List[Tuple[float, float]],
                           c_top: Tuple[int, int, int, int], c_bot: Tuple[int, int, int, int]):
    """Draw smooth vertical linear gradient across convex polygon."""
    w, h = target.size
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.polygon(points, fill=255)

    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)
    span = max(max_y - min_y, 1.0)

    grad = Image.new("RGBA", (w, h), c_top)
    gd = ImageDraw.Draw(grad)
    for y in range(int(min_y), int(max_y) + 1):
        t = (y - min_y) / span
        c = tuple(int(c_top[i] * (1.0 - t) + c_bot[i] * t) for i in range(4))
        gd.line([(0, y), (w, y)], fill=c)
    target.paste(grad, (0, 0), mask)


def _draw_metallic_cylinder(target: Image.Image, cx: float, cy_top: float, cy_bot: float, r: float,
                            c_base: Tuple[int, int, int], c_spec: Tuple[int, int, int],
                            c_shadow: Tuple[int, int, int], c_rim: Tuple[int, int, int]):
    """Render metallic cylinder surface shading with Phong specular highlight."""
    w, h = target.size
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle([cx - r, cy_top, cx + r, cy_bot], fill=255)

    cyl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cyl)

    for x in range(int(cx - r), int(cx + r) + 1):
        nx = (x - cx) / r if r > 0 else 0
        spec_dist = abs(nx - (-0.35))
        spec_int = max(0.0, 1.0 - (spec_dist / 0.35)) ** 2
        diffuse = max(0.0, -nx * 0.7 + 0.3)
        rim_int = max(0.0, (nx - 0.7) / 0.3) ** 1.5 if nx > 0.7 else 0.0

        r_col = int(c_base[0] * diffuse + c_shadow[0] * (1.0 - diffuse) + c_spec[0] * spec_int + c_rim[0] * rim_int)
        g_col = int(c_base[1] * diffuse + c_shadow[1] * (1.0 - diffuse) + c_spec[1] * spec_int + c_rim[1] * rim_int)
        b_col = int(c_base[2] * diffuse + c_shadow[2] * (1.0 - diffuse) + c_spec[2] * spec_int + c_rim[2] * rim_int)

        col = (min(255, max(0, r_col)), min(255, max(0, g_col)), min(255, max(0, b_col)), 255)
        cd.line([(x, cy_top), (x, cy_bot)], fill=col)

    target.paste(cyl, (0, 0), mask)


# ── Semantic Morphemes & Renderers ─────────────────────────────────────
def _render_master_stamp_clock(canvas_size: int = MASTER_SIZE) -> Image.Image:
    """Precision Mold-Making Date Stamp / Time Clock Metaphor (CAT-009)."""
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

    # 1. Contact Ambient Shadow
    shadow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([(60, 220), (452, 490)], fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    img = Image.alpha_composite(img, shadow)

    # 2. Beveled Outer Mold Housing Ring (Heavy Alloy Steels)
    housing = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    hd = ImageDraw.Draw(housing)
    # Beveled rim outer
    hd.ellipse([(55, 65), (457, 467)], fill=(130, 140, 155, 255), outline=CATIA_INK + (255,), width=8)
    _draw_gradient_polygon(housing, [(55, 65), (457, 65), (457, 467), (55, 467)],
                           (240, 245, 255, 255), (95, 105, 120, 255))
    # Outer slot notches (indexing notches for date core pins)
    for ang in (0, 90, 180, 270):
        rad = math.radians(ang)
        nx = 256 + 195 * math.cos(rad)
        ny = 266 + 195 * math.sin(rad)
        hd.ellipse([(nx - 16, ny - 16), (nx + 16, ny + 16)], fill=(30, 35, 45, 255), outline=CATIA_INK + (255,), width=4)

    # Inner Dial Plate (Engineering Gold / Precision Copper Face)
    inner_poly = [(110, 120), (402, 120), (402, 412), (110, 412)]
    _draw_gradient_polygon(housing, inner_poly, (255, 255, 175, 255), (230, 210, 90, 255))
    hd.ellipse([(110, 120), (402, 412)], outline=CATIA_INK + (255,), width=6)

    # 12-Hour Calibration Dial Ticks (Precision Mold Engraving)
    cx, cy, r_tick = 256, 266, 125
    for h_idx in range(12):
        rad = math.radians(h_idx * 30 - 90)
        t_outer_x = cx + r_tick * math.cos(rad)
        t_outer_y = cy + r_tick * math.sin(rad)
        inner_r = r_tick - (26 if h_idx % 3 == 0 else 16)
        t_inner_x = cx + inner_r * math.cos(rad)
        t_inner_y = cy + inner_r * math.sin(rad)
        w_line = 6 if h_idx % 3 == 0 else 4
        col = (195, 20, 20, 255) if h_idx == 0 else CATIA_INK + (255,)
        hd.line([(t_inner_x, t_inner_y), (t_outer_x, t_outer_y)], fill=col, width=w_line)

    # Central Core Pin (Slot screw head for adjusting date year/month)
    hd.ellipse([(cx - 42, cy - 42), (cx + 42, cy + 42)], fill=(160, 170, 185, 255), outline=CATIA_INK + (255,), width=5)
    hd.ellipse([(cx - 36, cy - 36), (cx + 36, cy + 36)], fill=(245, 248, 255, 220))
    hd.ellipse([(cx - 30, cy - 30), (cx + 30, cy + 30)], fill=(45, 52, 65, 255))
    # Screw slot
    hd.polygon([(cx - 24, cy - 6), (cx + 24, cy - 6), (cx + 24, cy + 6), (cx - 24, cy + 6)], fill=(15, 18, 24, 255))

    # Core Engraving Arrow (Indicating Current Month / Rotation)
    arrow_poly = [(cx, cy - 95), (cx + 20, cy - 30), (cx - 20, cy - 30)]
    hd.polygon(arrow_poly, fill=(200, 25, 25, 255), outline=CATIA_INK + (255,))

    img = Image.alpha_composite(img, housing)
    return img


def _render_master_part_to_asm(canvas_size: int = MASTER_SIZE) -> Image.Image:
    """Precision Assembly Flanged Bushing & Housing Base (PartToAsm)."""
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

    # 1. Contact shadow
    shadow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.polygon([(60, 445), (256, 498), (460, 435), (390, 375), (110, 385)], fill=(0, 0, 0, 95))
    sd.ellipse([(175, 235), (337, 295)], fill=(0, 0, 0, 135))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img, shadow)

    # 2. Base layer
    base_layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(base_layer)
    _draw_gradient_polygon(base_layer, [(55, 292), (256, 180), (457, 292), (256, 404)],
                           (245, 248, 254, 255), (165, 175, 192, 255))
    _draw_gradient_polygon(base_layer, [(55, 292), (256, 404), (256, 465), (55, 355)],
                           (155, 166, 180, 255), (98, 108, 122, 255))
    _draw_gradient_polygon(base_layer, [(256, 404), (457, 292), (457, 355), (256, 465)],
                           (110, 120, 134, 255), (65, 72, 85, 255))

    # Center Bore
    bd.ellipse([(256 - 68, 292 - 37), (256 + 68, 292 + 37)], fill=(130, 140, 158, 255), outline=CATIA_INK + (255,), width=3)
    _draw_gradient_polygon(base_layer, [(256 - 54, 292), (256 + 54, 292), (256 + 54, 292 + 52), (256 - 54, 292 + 52)],
                           (32, 38, 50, 255), (8, 10, 16, 255))

    # Stepped Bushing (Gold Part)
    _draw_metallic_cylinder(base_layer, 256, 75, 215, 62, (255, 230, 110), (255, 255, 210), (190, 145, 45), (255, 245, 160))
    bd.ellipse([(256 - 62, 75 - 32), (256 + 62, 75 + 32)], fill=(255, 255, 175, 255), outline=CATIA_INK + (255,), width=4)
    bd.ellipse([(256 - 32, 75 - 16), (256 + 32, 75 + 16)], fill=(35, 40, 52, 255), outline=CATIA_INK + (255,), width=3)

    img = Image.alpha_composite(img, base_layer)
    return img


def _render_master_bom_table(canvas_size: int = MASTER_SIZE) -> Image.Image:
    """Precision Engineering BOM Table & Data Export Metaphor."""
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

    # Shadow
    shadow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rectangle([65, 85, 455, 465], fill=(0, 0, 0, 95))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    img = Image.alpha_composite(img, shadow)

    # Main Card
    card = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rectangle([60, 60, 452, 452], fill=(255, 255, 255, 255), outline=CATIA_INK + (255,), width=6)

    # Header Row (Navy/Gold Accent)
    _draw_gradient_polygon(card, [(60, 60), (452, 60), (452, 140), (60, 140)],
                           (24, 16, 82, 255), (42, 30, 120, 255))
    cd.rectangle([75, 80, 145, 120], fill=FACE_GOLD + (255,))
    cd.rectangle([165, 80, 315, 120], fill=(255, 255, 255, 240))
    cd.rectangle([335, 80, 435, 120], fill=CYAN + (255,))

    # Data Rows
    row_y = 150
    for r in range(4):
        bg_col = (245, 248, 255, 255) if r % 2 == 0 else (255, 255, 255, 255)
        cd.rectangle([63, row_y, 449, row_y + 55], fill=bg_col)
        cd.rectangle([80, row_y + 14, 130, row_y + 42], fill=(180, 190, 205, 255))
        cd.rectangle([150, row_y + 14, 320, row_y + 42], fill=(130, 140, 160, 255))
        cd.rectangle([345, row_y + 14, 430, row_y + 42], fill=(210, 220, 235, 255))
        cd.line([(60, row_y + 55), (452, row_y + 55)], fill=(200, 210, 225, 255), width=2)
        row_y += 62

    # Vertical Column Separators
    for cx in (140, 330):
        cd.line([(cx, 60), (cx, 452)], fill=CATIA_INK + (200,), width=3)

    # Green Export Arrow
    arrow_layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    ad = ImageDraw.Draw(arrow_layer)
    ad.polygon([(290, 340), (370, 340), (370, 290), (450, 370), (370, 450), (370, 400), (290, 400)],
               fill=(40, 185, 80, 255), outline=CATIA_INK + (255,), width=5)
    img = Image.alpha_composite(img, card)
    img = Image.alpha_composite(img, arrow_layer)
    return img


def _render_master_color_swatch(canvas_size: int = MASTER_SIZE) -> Image.Image:
    """Color Swatch Grid + Automation Gear Metaphor (AutoColor)."""
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

    # Shadow
    shadow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rectangle([55, 75, 345, 465], fill=(0, 0, 0, 95))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    img = Image.alpha_composite(img, shadow)

    # 2x3 Color Swatch Card
    card = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rectangle([50, 70, 340, 460], fill=(255, 255, 255, 255), outline=CATIA_INK + (255,), width=6)

    colors = [
        [(235, 45, 45), (45, 180, 75)],
        [(45, 110, 235), (225, 60, 190)],
        [(245, 150, 30), (245, 220, 50)]
    ]
    sw_w, sw_h = 115, 105
    for r in range(3):
        for c in range(2):
            x1 = 70 + c * 135
            y1 = 90 + r * 118
            col = colors[r][c]
            cd.rectangle([x1, y1, x1 + sw_w, y1 + sw_h], fill=col + (255,), outline=CATIA_INK + (255,), width=4)
            cd.line([(x1 + 4, y1 + 4), (x1 + sw_w - 4, y1 + 4)], fill=(255, 255, 255, 180), width=3)

    # Automation Gear on Right Edge
    gear_layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gear_layer)
    cx, cy, r_hub, r_tip = 360, 310, 95, 135
    for tooth in range(8):
        ang = tooth * 45
        rad = math.radians(ang)
        p1 = (cx + r_hub * math.cos(rad - 0.22), cy + r_hub * math.sin(rad - 0.22))
        p2 = (cx + r_tip * math.cos(rad - 0.12), cy + r_tip * math.sin(rad - 0.12))
        p3 = (cx + r_tip * math.cos(rad + 0.12), cy + r_tip * math.sin(rad + 0.12))
        p4 = (cx + r_hub * math.cos(rad + 0.22), cy + r_hub * math.sin(rad + 0.22))
        gd.polygon([p1, p2, p3, p4], fill=GEAR_FACE + (255,), outline=CATIA_INK + (255,))
    gd.ellipse([(cx - r_hub, cy - r_hub), (cx + r_hub, cy + r_hub)], fill=GEAR_FACE + (255,), outline=CATIA_INK + (255,), width=5)
    gd.ellipse([(cx - 40, cy - 40), (cx + 40, cy + 40)], fill=(75, 85, 100, 255), outline=CATIA_INK + (255,), width=4)

    img = Image.alpha_composite(img, card)
    img = Image.alpha_composite(img, gear_layer)
    return img


def _render_master_name_card(canvas_size: int = MASTER_SIZE) -> Image.Image:
    """Document Name Card + Letter A + Automation Gear Metaphor (AutoRename)."""
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

    # Shadow
    shadow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rectangle([65, 85, 365, 465], fill=(0, 0, 0, 95))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    img = Image.alpha_composite(img, shadow)

    # Name Card
    card = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rectangle([60, 80, 360, 460], fill=(255, 255, 255, 255), outline=CATIA_INK + (255,), width=6)
    _draw_gradient_polygon(card, [(60, 80), (360, 80), (360, 150), (60, 150)],
                           (45, 110, 235, 255), (20, 60, 160, 255))
    cd.rectangle([80, 100, 180, 130], fill=(255, 255, 255, 240))

    # Precision Bold Letter 'A'
    cd.polygon([(190, 190), (230, 190), (310, 420), (265, 420), (245, 360), (175, 360), (155, 420), (110, 420)],
               fill=CATIA_INK + (255,))
    cd.polygon([(185, 320), (235, 320), (210, 245)], fill=(255, 255, 255, 255))

    # Gear on bottom right
    gear_layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gear_layer)
    cx, cy, r_hub, r_tip = 360, 340, 85, 120
    for tooth in range(8):
        ang = tooth * 45
        rad = math.radians(ang)
        p1 = (cx + r_hub * math.cos(rad - 0.22), cy + r_hub * math.sin(rad - 0.22))
        p2 = (cx + r_tip * math.cos(rad - 0.12), cy + r_tip * math.sin(rad - 0.12))
        p3 = (cx + r_tip * math.cos(rad + 0.12), cy + r_tip * math.sin(rad + 0.12))
        p4 = (cx + r_hub * math.cos(rad + 0.22), cy + r_hub * math.sin(rad + 0.22))
        gd.polygon([p1, p2, p3, p4], fill=GEAR_FACE + (255,), outline=CATIA_INK + (255,))
    gd.ellipse([(cx - r_hub, cy - r_hub), (cx + r_hub, cy + r_hub)], fill=GEAR_FACE + (255,), outline=CATIA_INK + (255,), width=5)
    gd.ellipse([(cx - 36, cy - 36), (cx + 36, cy + 36)], fill=(75, 85, 100, 255), outline=CATIA_INK + (255,), width=4)

    img = Image.alpha_composite(img, card)
    img = Image.alpha_composite(img, gear_layer)
    return img


def _render_master_cube_solid(canvas_size: int = MASTER_SIZE,
                             face_color: Tuple[int, int, int] = FACE_GOLD,
                             badge: Optional[str] = None) -> Image.Image:
    """Standard PartDesign Solid Pad/Pocket Metaphor (Cube3D)."""
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

    # Shadow
    shadow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.polygon([(100, 450), (390, 490), (460, 420), (220, 380)], fill=(0, 0, 0, 95))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    img = Image.alpha_composite(img, shadow)

    # 3D Extrusion
    solid = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(solid)

    # Top Face
    top_face = [(90, 180), (256, 85), (422, 180), (256, 275)]
    _draw_gradient_polygon(solid, top_face, (255, 255, 220, 255), face_color + (255,))
    sd.polygon(top_face, outline=CATIA_INK + (255,), width=6)

    # Left Face
    left_face = [(90, 180), (256, 275), (256, 425), (90, 330)]
    _draw_gradient_polygon(solid, left_face, face_color + (255,), (185, 180, 80, 255))
    sd.polygon(left_face, outline=CATIA_INK + (255,), width=6)

    # Right Face
    right_face = [(256, 275), (422, 180), (422, 330), (256, 425)]
    _draw_gradient_polygon(solid, right_face, (170, 160, 70, 255), (105, 95, 40, 255))
    sd.polygon(right_face, outline=CATIA_INK + (255,), width=6)

    # Highlight lines
    sd.line([(93, 180), (256, 272)], fill=(255, 255, 255, 240), width=4)
    sd.line([(256, 89), (93, 180)], fill=(255, 255, 255, 240), width=4)

    img = Image.alpha_composite(img, solid)
    return img


def _render_master_from_image(input_image_path: Path, canvas_size: int = MASTER_SIZE) -> Image.Image:
    """Remaster any external image/logo into an Ultra-HD Master asset."""
    src = Image.open(input_image_path).convert("RGBA")
    w, h = src.size

    # Fit into safe zone (65% canvas edge to prevent edge collisions)
    safe_edge = int(canvas_size * 0.70)
    ratio = min(safe_edge / w, safe_edge / h)
    new_w = max(1, int(w * ratio))
    new_h = max(1, int(h * ratio))
    resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)

    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

    # Contact shadow
    alpha_mask = resized.split()[-1]
    shadow = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 100))
    shadow.putalpha(alpha_mask)
    shadow_full = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    pos_x = (canvas_size - new_w) // 2
    pos_y = (canvas_size - new_h) // 2
    shadow_full.paste(shadow, (pos_x + 8, pos_y + 14), shadow)
    shadow_full = shadow_full.filter(ImageFilter.GaussianBlur(16))
    img = Image.alpha_composite(img, shadow_full)

    # Paste subject
    img.paste(resized, (pos_x, pos_y), resized)
    return img


# ── Pixel-Grid Renderers for CATIA BMPs (22 / 32) ─────────────────────
# Anything smaller than 64px is a *different* artwork, not a downscaled master.
#
# B28 references use one-pixel navy structure, flat engineering colours and
# sparse face accents. Fine detail comes from native-size geometry, never from
# blur, dithering or an unrestricted transitional-colour ramp.

PIXEL_STEEL = (160, 165, 170)      # lit plate face
PIXEL_STEEL_DEEP = (106, 116, 128) # plate side wall
PIXEL_STEEL_SHADE = (75, 75, 75)   # official I_Hole/I_Pocket shadow grey
PIXEL_GREEN = (40, 185, 80)
PIXEL_BLUE = (45, 110, 235)
PIXEL_GOLD_LEFT = (220, 210, 105)
PIXEL_GOLD_RIGHT = (165, 145, 65)
PIXEL_GOLD_SHADE = (190, 165, 65)


def _new_pixel_canvas(size: int, bg_color: Tuple[int, int, int]) -> Image.Image:
    """Flat RGB canvas: no alpha means no compositing blend artifacts."""
    return Image.new("RGB", (size, size), tuple(bg_color))


def _render_pixel_stamp_clock(size: int, bg_color: Tuple[int, int, int]) -> Image.Image:
    """Mold-date dial with a readable gold bezel and size-specific tick layout.

    The dial spans the full official framing (pixels 1..20 at 22px, 1..30 at
    32px) so it reads at the same weight as the B28 icons beside it.
    """
    g = _PixelGrid(size, bg_color)
    large = size >= 32
    cx = cy = 16.0 if large else 11.0
    outer_r = 15.0 if large else 10.0
    face_r = 11.5 if large else 7.5

    g.disc(cx, cy, outer_r, FACE_GOLD)
    g.d.ellipse(g.box(cx - face_r, cy - face_r, cx + face_r, cy + face_r), fill=WHITE)

    # Normal mode retains four cardinal marks; Large adds four square diagonal
    # marks. Diagonal hairlines missed pixel centres and disappeared at 32px.
    for angle in range(0, 360, 45 if large else 90):
        rad = math.radians(angle)
        dx, dy = math.cos(rad), math.sin(rad)
        if large and angle % 90:
            tx = cx + dx * (face_r - 1.0)
            ty = cy + dy * (face_r - 1.0)
            g.bar(tx - 1, ty - 1, tx + 1, ty + 1, CATIA_INK)
        else:
            g.line([(cx + dx * (face_r + 0.4), cy + dy * (face_r + 0.4)),
                    (cx + dx * (outer_r - 1.4), cy + dy * (outer_r - 1.4))])

    hand_length = 11.0 if large else 5.5
    g.line([(cx, cy + 0.5), (cx, cy - hand_length)], RED_MARK, width_px=2.0)
    g.line([(cx - 0.5, cy), (cx + hand_length, cy)], RED_MARK, width_px=2.0)
    g.bar(cx - 1, cy - 1, cx + 1, cy + 1, CATIA_INK)
    if large:
        g.bar(cx, cy, cx + 1, cy + 1, FACE_GOLD)
    return g.result()


def _render_pixel_part_to_asm(size: int, bg_color: Tuple[int, int, int]) -> Image.Image:
    """A gold component seated on an isometric assembly plate."""
    g = _PixelGrid(size, bg_color)
    large = size >= 32
    if large:
        plate_top = [(16, 17), (31, 22), (16, 27), (1, 22)]
        plate_bottom, plate_left_bottom, plate_right_bottom = (16, 31), (1, 26), (31, 26)
        cube_top = [(16, 1), (23, 5), (16, 9), (9, 5)]
        cube_bottom, cube_left_bottom, cube_right_bottom = (16, 21), (9, 17), (23, 17)
    else:
        plate_top = [(10.5, 10), (21, 14), (10.5, 18), (1, 14)]
        plate_bottom, plate_left_bottom, plate_right_bottom = (10.5, 21), (1, 17), (21, 17)
        cube_top = [(10.5, 1), (16, 4.5), (10.5, 8), (5, 4.5)]
        cube_bottom, cube_left_bottom, cube_right_bottom = (10.5, 15), (5, 12), (16, 12)

    plate_left = [plate_top[3], plate_top[2], plate_bottom, plate_left_bottom]
    plate_right = [plate_top[2], plate_top[1], plate_right_bottom, plate_bottom]
    g.solid(plate_left, PIXEL_STEEL_DEEP)
    g.solid(plate_right, PIXEL_STEEL_SHADE)
    g.solid(plate_top, PIXEL_STEEL)
    g.outline([plate_top[3], plate_top[2], plate_bottom, plate_right_bottom,
               plate_top[1], plate_top[0]])
    g.line([plate_top[2], plate_bottom])

    if large:
        # Two mounting holes fit only in Large mode; at 22px they become noise.
        g.solid([(8, 23), (10, 22), (12, 23), (10, 24)], CATIA_INK)
        g.solid([(20, 23), (22, 22), (24, 23), (22, 24)], CATIA_INK)

    cube_left = [cube_top[3], cube_top[2], cube_bottom, cube_left_bottom]
    cube_right = [cube_top[2], cube_top[1], cube_right_bottom, cube_bottom]
    g.solid(cube_left, PIXEL_GOLD_LEFT)
    g.solid(cube_right, PIXEL_GOLD_RIGHT)
    g.solid(cube_top, FACE_GOLD)
    g.outline([cube_top[0], cube_top[1], cube_right_bottom, cube_bottom,
               cube_left_bottom, cube_top[3]])
    g.line([cube_top[3], cube_top[2], cube_top[1]])
    g.line([cube_top[2], cube_bottom])
    g.line([(cube_top[3][0] + 1, cube_top[3][1] + 1),
            (cube_left_bottom[0] + 1, cube_left_bottom[1] - 1)], WHITE)
    return g.result()


def _render_pixel_bom_table(size: int, bg_color: Tuple[int, int, int]) -> Image.Image:
    """Ruled BOM sheet with column structure and a separate export arrow."""
    g = _PixelGrid(size, bg_color)
    large = size >= 32
    if large:
        g.bar(3, 3, 26, 31, PIXEL_STEEL_SHADE)
        g.rect(1, 1, 24, 30, WHITE)
        g.bar(2, 2, 23, 9, PIXEL_BLUE)
        for x in (4, 10, 16):
            g.bar(x, 5, x + 4, 7, WHITE)
        g.edge(2, 9, 23, 9)
        for row_y in (13, 17, 21, 25):
            g.line([(2, row_y), (23, row_y)], PIXEL_STEEL_SHADE)
        for col_x in (9, 16):
            g.line([(col_x, 10), (col_x, 29)], PIXEL_STEEL_SHADE)
        arrow = [(17, 16), (23, 16), (23, 13), (31, 21),
                 (23, 29), (23, 26), (17, 26)]
    else:
        g.bar(2, 2, 18, 21, PIXEL_STEEL_SHADE)
        g.rect(1, 1, 16, 21, WHITE)
        g.bar(2, 2, 15, 6, PIXEL_BLUE)
        g.edge(2, 6, 15, 6)
        for row_y in (9, 12, 15, 18):
            g.line([(2, row_y), (15, row_y)], PIXEL_STEEL_SHADE)
        g.line([(6, 7), (6, 20)], PIXEL_STEEL_SHADE)
        arrow = [(11, 10), (15, 10), (15, 8), (21, 14),
                 (15, 20), (15, 18), (11, 18)]

    g.face(arrow, PIXEL_GREEN)
    if large:
        g.line([(19, 18), (23, 18), (23, 16), (28, 20)], WHITE)
    return g.result()


def _render_pixel_color_swatch(size: int, bg_color: Tuple[int, int, int]) -> Image.Image:
    """Four colour chips on a layered card; Large adds flat enamel highlights."""
    g = _PixelGrid(size, bg_color)
    large = size >= 32
    if large:
        g.bar(2, 2, 31, 31, PIXEL_STEEL_SHADE)
        g.rect(1, 1, 31, 31, WHITE)
        chips = [(3, 3, RED_MARK, (255, 120, 110)),
                 (17, 3, PIXEL_GREEN, (145, 240, 150)),
                 (3, 17, PIXEL_BLUE, (135, 190, 255)),
                 (17, 17, FACE_GOLD, WHITE)]
        chip_size = 12
    else:
        g.bar(2, 2, 21, 21, PIXEL_STEEL_SHADE)
        g.rect(1, 1, 21, 21, WHITE)
        chips = [(3, 3, RED_MARK, None), (12, 3, PIXEL_GREEN, None),
                 (3, 12, PIXEL_BLUE, None), (12, 12, FACE_GOLD, None)]
        chip_size = 8

    for x0, y0, colour, highlight in chips:
        g.rect(x0, y0, x0 + chip_size, y0 + chip_size, colour)
        if highlight is not None:
            g.line([(x0 + 1, y0 + chip_size - 2), (x0 + 1, y0 + 1),
                    (x0 + chip_size - 2, y0 + 1)], highlight)
    return g.result()


def _render_pixel_name_card(size: int, bg_color: Tuple[int, int, int]) -> Image.Image:
    """Layered name card with a solid, legible A and a blue title band."""
    g = _PixelGrid(size, bg_color)
    large = size >= 32
    if large:
        g.bar(2, 2, 31, 31, PIXEL_STEEL_SHADE)
        g.rect(1, 1, 31, 31, WHITE)
        g.bar(2, 2, 30, 11, PIXEL_BLUE)
        g.edge(2, 11, 30, 11)
        g.bar(3, 3, 13, 5, WHITE)
        g.bar(17, 3, 25, 5, CYAN)
        g.solid([(4, 30), (13, 12), (17, 12), (12, 30)], CATIA_INK)
        g.solid([(17, 12), (21, 12), (29, 30), (24, 30)], CATIA_INK)
        g.bar(12, 22, 23, 25, CATIA_INK)
        g.bar(3, 28, 12, 30, CATIA_INK)
        g.bar(22, 28, 30, 30, CATIA_INK)
    else:
        g.bar(2, 2, 21, 21, PIXEL_STEEL_SHADE)
        g.rect(1, 1, 21, 21, WHITE)
        g.bar(2, 2, 20, 8, PIXEL_BLUE)
        g.edge(2, 8, 20, 8)
        g.solid([(3, 20), (7, 9), (9, 9), (6, 20)], CATIA_INK)
        g.solid([(9, 9), (12, 9), (16, 20), (13, 20)], CATIA_INK)
        g.bar(6, 15, 13, 17, CATIA_INK)
    return g.result()


def _render_pixel_cube_solid(size: int, bg_color: Tuple[int, int, int]) -> Image.Image:
    """Isometric engineering solid with three faces and sparse bevel accents."""
    g = _PixelGrid(size, bg_color)
    large = size >= 32
    if large:
        top = [(15.5, 1), (31, 9), (15.5, 17), (1, 9)]
        bottom, left_bottom, right_bottom = (15.5, 31), (1, 23), (31, 23)
    else:
        top = [(10.5, 1), (21, 6), (10.5, 11), (1, 6)]
        bottom, left_bottom, right_bottom = (10.5, 21), (1, 16), (20, 16)

    left = [top[3], top[2], bottom, left_bottom]
    right = [top[2], top[1], right_bottom, bottom]
    g.solid(left, PIXEL_GOLD_LEFT)
    g.solid(right, PIXEL_GOLD_RIGHT)
    g.solid(top, FACE_GOLD)
    g.outline([top[0], top[1], right_bottom, bottom, left_bottom, top[3]])
    g.line([top[3], top[2], top[1]])
    g.line([top[2], bottom])

    # A vertical enamel highlight survives point sampling; diagonal hairlines
    # on the top face broke into bright specks and were intentionally removed.
    g.line([(top[3][0] + 1, top[3][1] + 2),
            (left_bottom[0] + 1, left_bottom[1] - 1)], FACE_GOLD)
    if large:
        g.line([(top[1][0] - 1, top[1][1] + 2),
                (right_bottom[0] - 1, right_bottom[1] - 1)], PIXEL_GOLD_SHADE)
        g.line([(left_bottom[0] + 2, left_bottom[1]),
                (bottom[0], bottom[1] - 2)], PIXEL_GOLD_SHADE)
    return g.result()


def _render_pixel_from_image(input_image_path: Path, size: int,
                            bg_color: Tuple[int, int, int]) -> Image.Image:
    """Remaster an external logo at final size onto the pixel grid.

    BOX averaging is used instead of LANCZOS: it never overshoots into ringing
    halos. The result is then posterized to flat regions, because a photographic
    gradient has no chance of holding a hard contour at 22px -- the gate would
    reject it, and rightly so.
    """
    src = Image.open(input_image_path).convert("RGBA")
    # Trim the source's own transparent padding first. Most exported logos are
    # drawn inside a square canvas with margin baked in; scaling that canvas to
    # the content box preserved the padding and left the subject at 15x15 on a
    # 22px icon, which reads smaller than every generated metaphor and fails
    # the framing contract. Trimming makes the subject, not the canvas, fill
    # the frame. Threshold matches the alpha cut below, so faint resample dust
    # around the artwork does not enlarge the crop.
    _bbox = src.split()[-1].point(lambda a: 255 if a >= 128 else 0).getbbox()
    if _bbox:
        src = src.crop(_bbox)
    w, h = src.size
    # Frame the asset to the same content box the built-in metaphors use:
    # a 1px mask margin with the subject spanning the rest of the canvas. Using
    # a fixed 0.92 factor left a 2px margin at 22px and a 3px margin at 32px,
    # i.e. an imported logo was framed smaller than every generated icon.
    safe = max(1, size - 2 * CONTENT_MARGIN)
    ratio = min(safe / float(w), safe / float(h))
    new_w = max(1, int(round(w * ratio)))
    new_h = max(1, int(round(h * ratio)))
    resized = src.resize((new_w, new_h), Image.Resampling.BOX)
    alpha = resized.split()[-1].point(lambda a: 255 if a >= 128 else 0)

    img = _new_pixel_canvas(size, bg_color)
    ox, oy = (size - new_w) // 2, (size - new_h) // 2
    img.paste(resized, (ox, oy), resized)

    # Flatten the tonal ramp into a few hard bands so contours stay crisp.
    # Above ~4 levels the adjacent bands land within SHARP_EDGE_DELTA of each
    # other, which reads as a soft ramp again and fails the contour gate.
    levels = 3 if size <= 22 else 4
    img = Image.eval(img, lambda v: round(v * (levels - 1) / 255.0) * 255 // (levels - 1))

    # Re-apply the *original* transparency: only pixels the source declared
    # transparent go back to the mask colour. Matching by colour would eat the
    # subject whenever it happens to share a hue with the background.
    px = img.load()
    ap = alpha.load()
    for y in range(size):
        for x in range(size):
            ax, ay = x - ox, y - oy
            if 0 <= ax < new_w and 0 <= ay < new_h:
                if ap[ax, ay] == 0:
                    px[x, y] = tuple(bg_color)
            else:
                px[x, y] = tuple(bg_color)
    return img


def _overlay_pixel_badge(img: Image.Image, badge_name: str) -> Image.Image:
    """Small verb badge for 32px assets only, authored on the native grid.

    The badge is inset by CONTENT_MARGIN on its outer side: the previous
    centre/r of 24.5/6.5 put the disc's edge exactly on pixel 31, which broke
    the mask margin the rest of the contract guarantees and made every
    badged 32px icon a 31x31 (margin 0) outlier.
    """
    size = img.size[0]
    if size < 32:
        return img
    d = ImageDraw.Draw(img)
    unit = size / 32.0
    u = lambda v: v * unit
    w = max(1, int(round(unit)))

    r = u(6.0)
    # Pixel-boundary coordinates: the disc must end at or before size-CONTENT_MARGIN
    # so the outermost column/row stays mask. With r in design units, that puts
    # the centre at (size - CONTENT_MARGIN - r) - 0.5 of a design unit short;
    # using the boundary value directly ate the margin (measured 31x31, margin 0).
    cx = cy = size - CONTENT_MARGIN - r - 0.5
    d.ellipse([cx - r, cy - r, cx + r, cy + r],
              fill=WHITE, outline=CATIA_INK, width=max(1, int(round(unit))))

    arm = u(2.4)
    thick = max(2, int(round(unit * 1.4)))
    if badge_name in ("plus", "create", "new", "add"):
        d.line([(cx - arm, cy), (cx + arm, cy)], fill=PIXEL_GREEN, width=thick)
        d.line([(cx, cy - arm), (cx, cy + arm)], fill=PIXEL_GREEN, width=thick)
    elif badge_name in ("pencil", "edit", "modify", "rename"):
        d.line([(cx - arm, cy + arm), (cx + arm, cy - arm)], fill=CATIA_INK, width=thick)
        d.line([(cx - arm, cy + arm), (cx - arm + w, cy + arm)], fill=PIXEL_BLUE, width=thick)
    elif badge_name in ("refresh", "update"):
        d.arc([cx - arm, cy - arm, cx + arm, cy + arm], 40, 320,
              fill=PIXEL_BLUE, width=thick)
    elif badge_name in ("check", "verify", "validate"):
        d.line([(cx - arm, cy), (cx - arm * 0.2, cy + arm)], fill=PIXEL_GREEN, width=thick)
        d.line([(cx - arm * 0.2, cy + arm), (cx + arm, cy - arm)], fill=PIXEL_GREEN, width=thick)
    elif badge_name in ("search", "find"):
        d.ellipse([cx - arm, cy - arm, cx + arm * 0.3, cy + arm * 0.3],
                  outline=PIXEL_BLUE, width=thick)
        d.line([(cx + arm * 0.3, cy + arm * 0.3), (cx + arm, cy + arm)],
               fill=CATIA_INK, width=thick)
    else:
        d.line([(cx - arm, cy), (cx + arm, cy)], fill=PIXEL_GREEN, width=thick)
        d.line([(cx, cy - arm), (cx, cy + arm)], fill=PIXEL_GREEN, width=thick)
    return img


PIXEL_RENDERERS = {
    "stamp_clock": _render_pixel_stamp_clock,
    "part_to_asm": _render_pixel_part_to_asm,
    "bom_table": _render_pixel_bom_table,
    "color_swatch": _render_pixel_color_swatch,
    "name_card": _render_pixel_name_card,
    "notch_pocket": _render_pixel_cube_solid,
    "cube_solid": _render_pixel_cube_solid,
}


def _render_pixel(metaphor: str, size: int, bg_color: Tuple[int, int, int] = CATIA_BG,
                  badge: Optional[str] = None,
                  input_image: Optional[Path] = None) -> Image.Image:
    """Render one CATIA-size asset directly at `size` pixels."""
    if input_image and Path(input_image).is_file():
        img = _render_pixel_from_image(Path(input_image), size, bg_color)
    else:
        renderer = PIXEL_RENDERERS.get(metaphor, _render_pixel_cube_solid)
        img = renderer(size, bg_color)
    if badge:
        img = _overlay_pixel_badge(img, badge)
    return img


# ── Badge Rendering for Master 512 ─────────────────────────────────────
def _overlay_badge(master: Image.Image, badge_name: str) -> Image.Image:
    """Overlay standard CATIA-styled verb badge at bottom-right corner."""
    w, h = master.size
    bd = ImageDraw.Draw(master)
    b_size = int(w * 0.36)
    x0 = w - b_size - 16
    y0 = h - b_size - 16
    cx, cy = x0 + b_size // 2, y0 + b_size // 2

    # Circular badge plate (White enamel with Ink border)
    bd.ellipse([(x0 - 4, y0 - 4), (x0 + b_size + 4, y0 + b_size + 4)],
               fill=(0, 0, 0, 60))
    bd.ellipse([(x0, y0), (x0 + b_size, y0 + b_size)],
               fill=(255, 255, 255, 250), outline=CATIA_INK + (255,), width=6)

    # Glyphs
    g_rad = b_size * 0.28
    if badge_name in ("plus", "create", "new", "add"):
        arm = int(g_rad * 0.8)
        th = max(6, int(b_size * 0.16))
        bd.line([(cx - arm, cy), (cx + arm, cy)], fill=(35, 175, 75, 255), width=th)
        bd.line([(cx, cy - arm), (cx, cy + arm)], fill=(35, 175, 75, 255), width=th)
    elif badge_name in ("pencil", "edit", "modify", "rename"):
        bd.polygon([(cx - 16, cy + 24), (cx + 24, cy - 16), (cx + 34, cy - 6), (cx - 6, cy + 34)],
                   fill=(255, 165, 0, 255), outline=CATIA_INK + (255,), width=3)
    elif badge_name in ("refresh", "update"):
        bd.arc([(cx - g_rad, cy - g_rad), (cx + g_rad, cy + g_rad)], 30, 300, fill=(0, 140, 230, 255), width=8)
    elif badge_name in ("check", "verify", "validate"):
        bd.line([(cx - 16, cy), (cx - 4, cy + 14)], fill=(35, 175, 75, 255), width=8)
        bd.line([(cx - 4, cy + 14), (cx + 20, cy - 14)], fill=(35, 175, 75, 255), width=8)
    elif badge_name in ("search", "find", "analyze"):
        r_lens = int(g_rad * 0.7)
        bd.ellipse([(cx - r_lens - 4, cy - r_lens - 4), (cx + r_lens - 4, cy + r_lens - 4)],
                   outline=(0, 140, 230, 255), width=7)
        bd.line([(cx + r_lens - 4, cy + r_lens - 4), (cx + r_lens + 12, cy + r_lens + 12)],
                   fill=CATIA_INK + (255,), width=8)
    elif badge_name in ("export", "import"):
        # Direction matters: export leaves, import arrives.
        going_out = badge_name == "export"
        tip_x = cx + (int(g_rad) if going_out else -int(g_rad))
        tail_x = cx - (int(g_rad) if going_out else -int(g_rad))
        bd.line([(tail_x, cy), (tip_x, cy)], fill=(0, 140, 230, 255), width=8)
        bd.polygon([(tip_x + (14 if going_out else -14), cy),
                    (tip_x, cy - 16), (tip_x, cy + 16)],
                   fill=(0, 140, 230, 255), outline=CATIA_INK + (255,))
    else:
        # Unknown verb: draw the neutral plus rather than a blank white disc,
        # which previously shipped as an empty badge and looked like a defect.
        arm = int(g_rad * 0.8)
        th = max(6, int(b_size * 0.16))
        bd.line([(cx - arm, cy), (cx + arm, cy)], fill=(35, 175, 75, 255), width=th)
        bd.line([(cx, cy - arm), (cx, cy + arm)], fill=(35, 175, 75, 255), width=th)
    return master


# ── Quantizer & BMP Writer (CNEXT Safe) ──────────────────────────────
def _quantize_to_catia_bmp(rgba: Image.Image, out_size: int = 22,
                           bg_color: Tuple[int, int, int] = CATIA_BG,
                           max_colors: Optional[int] = None) -> Image.Image:
    """Format an image into a CNEXT-safe 8-bit palettized BMP.

    Contract:
      * palette index 0 == ``bg_color`` (the declared transparency mask)
      * background is an exact mask colour, never a near-miss blend
      * at most ``max_colors`` distinct *foreground* colours survive
      * dithering is OFF -- Floyd-Steinberg on a 22px canvas is pure speckle
    """
    if max_colors is None:
        max_colors = MAX_FG_COLORS.get(out_size, 64)

    # 1. Flatten alpha over the declared background.
    flat_src = Image.new("RGB", rgba.size, tuple(bg_color))
    if rgba.mode in ("RGBA", "LA", "PA") or "A" in rgba.mode:
        flat_src.paste(rgba, (0, 0), rgba.convert("RGBA"))
    else:
        flat_src.paste(rgba.convert("RGB"), (0, 0))

    # 2. Reach the target size. BOX averages without ringing halos; the pixel
    #    renderers already emit exact size, so this only guards legacy masters.
    if flat_src.size != (out_size, out_size):
        flat_src = flat_src.resize((out_size, out_size), Image.Resampling.BOX)

    px = flat_src.load()
    w, h = flat_src.size

    def _snap(x: int, y: int) -> None:
        p = px[x, y]
        if all(abs(p[i] - bg_color[i]) <= BG_TOLERANCE for i in range(3)):
            px[x, y] = tuple(bg_color)

    # 3. Mask the outer ring only. Interior colours that merely resemble the
    #    background must survive -- blanket tolerance wiping is what bleached
    #    the previous generation of icons.
    for x in range(w):
        _snap(x, 0)
        _snap(x, h - 1)
    for y in range(h):
        _snap(0, y)
        _snap(w - 1, y)
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        px[x, y] = tuple(bg_color)

    # 4. Reduce to (foreground budget + one background slot), dither disabled.
    quant = flat_src.quantize(colors=max(2, min(256, max_colors + 1)),
                              method=Image.Quantize.MEDIANCUT,
                              dither=Image.Dither.NONE)
    raw_palette = quant.getpalette() or []

    # 5. Rebuild palette with index 0 pinned to the declared background colour;
    #    any palette entry that is effectively the background folds into 0.
    new_palette = [bg_color[0], bg_color[1], bg_color[2]]
    idx_map: Dict[int, int] = {}
    cur_idx = 1
    for i in range(0, len(raw_palette), 3):
        color = (raw_palette[i], raw_palette[i + 1], raw_palette[i + 2])
        if all(abs(color[j] - bg_color[j]) <= 2 for j in range(3)):
            idx_map[i // 3] = 0
        elif cur_idx <= max_colors:
            new_palette.extend(color)
            idx_map[i // 3] = cur_idx
            cur_idx += 1
        else:
            idx_map[i // 3] = 0

    while len(new_palette) < 768:
        new_palette.extend(bg_color)

    if hasattr(quant, "get_flattened_data"):
        src_data = quant.get_flattened_data()
    else:
        src_data = list(quant.getdata())

    remapped = Image.new("P", (out_size, out_size), 0)
    remapped.putdata([idx_map.get(val, 0) for val in src_data])
    remapped.putpalette(new_palette)

    # 6. Re-assert the mask corners after remapping.
    rem_px = remapped.load()
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        rem_px[x, y] = 0

    return remapped


# ── Quality Gate (Lint) ───────────────────────────────────────────────
def _palette_color(img: Image.Image, index: int) -> Optional[Tuple[int, int, int]]:
    pal = img.getpalette() or []
    base = index * 3
    if len(pal) < base + 3:
        return None
    return (pal[base], pal[base + 1], pal[base + 2])


def _icon_metrics(bmp_img: Image.Image,
                  bg_color: Tuple[int, int, int] = CATIA_BG,
                  profile: str = "cade") -> Dict[str, Any]:
    """Measure the pixel-level properties the gate reasons about.

    ``profile`` selects how the *background* is identified:

    * ``cade``     -- CADE's own writer pins the mask to palette index 0, so an
      index test is exact.
    * ``official`` -- B28 icons place the background at an arbitrary palette
      index (I_Pad uses 13, I_Pocket 2, I_MeasureBetween 4). Index 0 is an
      ordinary colour there, so foreground must be identified by colour.
    """
    w, h = bmp_img.size
    if bmp_img.mode != "P":
        bmp_img = bmp_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
    px = bmp_img.load()
    rgb = bmp_img.convert("RGB")
    rpx = rgb.load()
    bg = tuple(bg_color)

    if profile == "official":
        fg_pixels = [(x, y) for y in range(h) for x in range(w) if rpx[x, y] != bg]
        fg_colors = {rpx[x, y] for x, y in fg_pixels}
    else:
        fg_pixels = [(x, y) for y in range(h) for x in range(w) if px[x, y] != 0]
        # Foreground palette entries actually referenced (background excluded).
        used_idx = {px[x, y] for x, y in fg_pixels}
        fg_colors = {_palette_color(bmp_img, i) for i in used_idx}
    fg_count = len(fg_pixels)

    # Hard-edge ratio: among 4-neighbour pairs that actually differ, the share
    # whose max channel delta is >= SHARP_EDGE_DELTA. Same-colour runs inside a
    # flat fill are not edges, so they must not dilute the measurement.
    differing_edges = sharp_edges = 0
    for y in range(h):
        for x in range(w):
            a = rpx[x, y]
            for dx, dy in ((1, 0), (0, 1)):
                nx, ny = x + dx, y + dy
                if nx >= w or ny >= h:
                    continue
                b = rpx[nx, ny]
                delta = max(abs(a[i] - b[i]) for i in range(3))
                if delta == 0:
                    continue
                differing_edges += 1
                if delta >= SHARP_EDGE_DELTA:
                    sharp_edges += 1

    # Isolated foreground islands (8-neighbourhood) -- these are dither speckle.
    fg_set = set(fg_pixels)
    isolated = 0
    for (x, y) in fg_pixels:
        if not any((x + dx, y + dy) in fg_set
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                   if (dx, dy) != (0, 0)):
            isolated += 1

    # Foreground bounding box and the mask margin around it. This is what the
    # official framing contract is expressed in: B28 22x22 icons keep a median
    # 20x20 subject with a 1px margin, so matching that framing is a property
    # of the drawing, not of the palette.
    if fg_pixels:
        xs = [x for x, _ in fg_pixels]
        ys = [y for _, y in fg_pixels]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        content_bbox = (x1 - x0 + 1, y1 - y0 + 1)
        content_margin = min(x0, y0, w - 1 - x1, h - 1 - y1)
    else:
        content_bbox = (0, 0)
        content_margin = 0

    return {
        "fg_count": fg_count,
        "fg_ratio": (fg_count / float(w * h)) if w and h else 0.0,
        "fg_color_count": len(fg_colors),
        "fg_colors": fg_colors,
        "sharp_ratio": (sharp_edges / float(differing_edges)) if differing_edges else 0.0,
        "isolated_ratio": (isolated / float(fg_count)) if fg_count else 0.0,
        "content_bbox": content_bbox,
        "content_margin": content_margin,
    }


def lint_icon_asset(bmp_img: Image.Image, expected_size: int,
                    bg_color: Tuple[int, int, int] = CATIA_BG,
                    profile: str = "cade") -> Dict[str, Any]:
    """Audit a BMP asset against the CADE micro-icon contract.

    Four blocking layers (G1 format, G2 colour budget, G3 contour quality,
    G4 geometry) plus G5 real-display, which only the B28 runtime can judge.
    Any blocked layer fails the asset outright: there is no WARN downgrade,
    because a WARN still reached `.CATRsc` in the previous implementation.

    ``profile="cade"`` is the generation contract: palette index 0 *is* the
    mask, and the four corners must be index 0. ``profile="official"`` is an
    audit of existing B28 icons, which do not pin the background to index 0
    (measured: 141 of 153 sampled 22x22 icons keep it elsewhere). That profile
    judges the corners and the foreground by colour instead of index, and is
    never used on the path that deploys a CADE icon.
    """
    if profile not in ("cade", "official"):
        raise ValueError(f"unknown icon lint profile: {profile}")

    w, h = bmp_img.size
    orig_mode = bmp_img.mode
    if bmp_img.mode != "P":
        # Measure on a palettized copy so index-based logic is coherent; the
        # format gate below still judges the original, unconverted asset.
        bmp_img = bmp_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
    px = bmp_img.load()
    palette = bmp_img.getpalette() or []
    c0 = (palette[0], palette[1], palette[2]) if len(palette) >= 3 else None
    bg = tuple(bg_color)

    m = _icon_metrics(bmp_img, bg_color=bg, profile=profile)
    color_budget = MAX_FG_COLORS.get(expected_size, max(MAX_FG_COLORS.values()))

    checks: Dict[str, Any] = {}

    # G1 -- format & transparency mask
    checks["size_exact"] = (w == expected_size and h == expected_size)
    checks["is_palettized"] = (orig_mode == "P")
    checks["bg_color_legal"] = (bg in LEGAL_BG_COLORS)
    corner_idx = (px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1])
    if profile == "cade":
        checks["palette_0_is_catia_bg"] = (c0 == bg)
        checks["four_corners_pure_index_0"] = all(c == 0 for c in corner_idx)
    else:
        # Official icons do not reserve index 0 for the mask. The corners must
        # still be the declared background colour, wherever it sits in the palette.
        checks["four_corners_are_bg"] = all(
            _palette_color(bmp_img, c) == bg for c in corner_idx
        )

    # G2 -- colour budget
    checks["fg_color_count"] = m["fg_color_count"]
    checks["fg_color_budget_ok"] = (m["fg_color_count"] <= color_budget)
    # The mask colour is reserved for transparency: a foreground pixel that
    # reuses it punches a hole in the subject, so the icon cannot be trusted.
    # Under the official profile the foreground is defined as "not the mask
    # colour", so this check is satisfied by construction.
    checks["fg_excludes_bg_mask"] = (bg not in m["fg_colors"])

    # G3 -- contour quality
    checks["sharp_ratio"] = round(m["sharp_ratio"], 3)
    checks["sharp_ratio_ok"] = (m["sharp_ratio"] >= MIN_SHARP_RATIO)
    checks["isolated_ratio"] = round(m["isolated_ratio"], 3)
    checks["no_dither_speckle"] = (m["isolated_ratio"] <= MAX_ISOLATED_RATIO)

    # G4 -- geometry
    checks["fg_ratio"] = round(m["fg_ratio"], 3)
    ratio_ceiling = fg_ratio_ceiling(expected_size)
    checks["fg_ratio_ceiling"] = round(ratio_ceiling, 3)
    checks["fg_ratio_in_bounds"] = (FG_MIN <= m["fg_ratio"] <= ratio_ceiling)

    # G4b -- canvas utilisation. Official B28 icons fill the frame (22px content
    # bbox median 20x20 with a 1px mask margin; 32px median 30x30), so an icon
    # that draws into a smaller box reads as visibly smaller and lighter than
    # its neighbours in the same toolbar. Measured on the foreground bbox, not
    # on colour count, so it cannot be satisfied by repainting the canvas.
    checks["content_bbox"] = tuple(m["content_bbox"])
    target_edge = CONTENT_MIN_EDGE.get(expected_size, expected_size - 2)
    checks["content_reaches_official_framing"] = (
        m["content_bbox"][0] >= target_edge and m["content_bbox"][1] >= target_edge)
    checks["content_keeps_mask_margin"] = (m["content_margin"] >= CONTENT_MARGIN)

    # G5 -- real display, only verifiable inside CATIA on B28
    checks["runtime_display_verified"] = "not_checked"

    blocking = [
        "size_exact", "is_palettized", "bg_color_legal",
        "fg_color_budget_ok", "fg_excludes_bg_mask",
        "sharp_ratio_ok", "no_dither_speckle", "fg_ratio_in_bounds",
    ]
    if profile == "cade":
        blocking += ["palette_0_is_catia_bg", "four_corners_pure_index_0"]
        # The framing contract is a *generation* rule: CADE must fill the canvas
        # the way the official set does. Under profile="official" the same
        # numbers are still reported, but they are an audit of artwork CADE did
        # not author, so they must not veto a real B28 icon that legitimately
        # draws smaller than the 20x20 / 30x30 frame.
        blocking += ["content_reaches_official_framing", "content_keeps_mask_margin"]
    else:
        blocking += ["four_corners_are_bg"]
    failures = [k for k in blocking if not checks[k]]

    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "size": bmp_img.size,
        "mode": bmp_img.mode,
        "bg_color": tuple(bg_color),
        "color_budget": color_budget,
        "checks": checks,
    }


def _clear_transparent_rgb(img: Image.Image) -> Image.Image:
    """Zero the RGB of every fully transparent pixel.

    Resampling (LANCZOS/BOX) blends colour into A=0 neighbours, so an exported
    PNG ends up with transparent pixels carrying a faint tint. Viewers that
    ignore the alpha band -- or composite onto a dark toolbar -- render that as
    a halo around the artwork.
    """
    if "A" not in img.mode:
        return img
    rgba = img.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    for y in range(h):
        for x in range(w):
            if px[x, y][3] == 0:
                px[x, y] = (0, 0, 0, 0)
    return rgba


def lint_png_asset(png_img: Image.Image) -> Dict[str, Any]:
    """Audit the documentation PNGs against the alpha purity contract.

    The BMP gate cannot see this: an indexed BMP has no alpha, so the
    transparent-pixel hygiene of the 512/256/64 exports needs its own check.
    Contract: every pixel with A=0 must carry RGB=0 too, otherwise a viewer
    that ignores alpha (or composites onto a dark toolbar) shows a halo.
    """
    checks: Dict[str, Any] = {"has_alpha": ("A" in png_img.mode)}
    if not checks["has_alpha"]:
        return {"status": "PASS", "failures": [], "checks": checks,
                "dirty_transparent": 0, "transparent_px": 0}

    px = png_img.convert("RGBA").load()
    w, h = png_img.size
    transparent = dirty = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                transparent += 1
                if r or g or b:
                    dirty += 1

    checks["transparent_px"] = transparent
    checks["dirty_transparent_px"] = dirty
    checks["alpha_pure"] = (dirty == 0)
    failures = [] if checks["alpha_pure"] else ["alpha_pure"]
    return {"status": "PASS" if not failures else "FAIL",
            "failures": failures, "checks": checks,
            "dirty_transparent": dirty, "transparent_px": transparent}


def _repo_root() -> Optional[Path]:
    """Nearest ancestor containing `.git`, or None outside a repo."""
    for cand in Path(__file__).resolve().parents:
        if (cand / ".git").exists():
            return cand
    return None


def _portable_path(p: Path) -> str:
    """Repo-relative, forward-slash path so committed manifests stay portable.

    Writing `str(path)` produced absolute `D:\\Vault\\...` entries that are
    meaningless on any other checkout and leak the author's directory layout.
    """
    resolved = Path(p).resolve()
    root = _repo_root()
    if root is not None:
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            pass
    return resolved.as_posix()


# ── Universal Icon Studio Engine ───────────────────────────────────────
class UniversalIconStudio:
    """Master Icon Factory: Transforms any tool name, semantic or image into production assets."""

    @staticmethod
    def resolve_metaphor_from_name(name: str) -> Tuple[str, Optional[str]]:
        """Deduce primary visual metaphor and secondary badge from tool name."""
        lower = name.lower()
        badge = None
        for b_cand in ("create", "add", "new", "modify", "edit", "rename", "update", "refresh",
                      "check", "verify", "search", "find", "analyze", "export", "import"):
            if b_cand in lower:
                badge = b_cand
                break

        if any(k in lower for k in ("datestamp", "date", "stamp", "clock", "calendar", "time", "logo")):
            return "stamp_clock", badge
        if any(k in lower for k in ("parttoasm", "part_to_asm", "assemble", "assembly", "asm")):
            return "part_to_asm", badge
        if any(k in lower for k in ("bom", "table", "billofmaterial", "report")):
            return "bom_table", badge
        if any(k in lower for k in ("color", "swatch", "property")):
            return "color_swatch", badge
        if any(k in lower for k in ("rename", "autorename", "tag", "name")):
            return "name_card", badge
        if any(k in lower for k in ("pocket", "hole", "cavity", "cut", "slot", "groove")):
            return "notch_pocket", badge

        # Default engineering solid
        return "cube_solid", badge

    @classmethod
    def generate_icon_bundle(cls, stem: str,
                             metaphor: Optional[str] = None,
                             badge: Optional[str] = None,
                             input_image: Optional[Path] = None,
                             out_dir: Optional[Path] = None,
                             bg_color: Tuple[int, int, int] = CATIA_BG) -> Dict[str, Any]:
        """Generate the full asset suite: 512/256/64 PNG + 22/32 PNG & BMP.

        The 512 master is a design artefact only. The two CATIA runtime sizes are
        rendered independently on a pixel grid, because a 512px illustration
        downscaled to 22px cannot keep a 1px contour intact.
        """
        dest_dir = Path(out_dir) if out_dir else ASSETS_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)

        if bg_color not in LEGAL_BG_COLORS:
            return {"status": "FAIL",
                    "reason": f"bg_color {tuple(bg_color)} is not a legal CATIA mask colour",
                    "manifest": {}, "files": {}}

        # 1. Resolve metaphor/badge, then render the 512 design master
        if input_image and Path(input_image).is_file():
            master_rgba = _render_master_from_image(Path(input_image), MASTER_SIZE)
            target_metaphor = metaphor or "cube_solid"
            target_badge = badge
        else:
            inferred_metaphor, inferred_badge = cls.resolve_metaphor_from_name(stem)
            target_metaphor = metaphor or inferred_metaphor
            target_badge = badge or inferred_badge

            master_renderers = {
                "stamp_clock": _render_master_stamp_clock,
                "part_to_asm": _render_master_part_to_asm,
                "bom_table": _render_master_bom_table,
                "color_swatch": _render_master_color_swatch,
                "name_card": _render_master_name_card,
                "notch_pocket": _render_master_cube_solid,
                "cube_solid": _render_master_cube_solid,
            }
            master_rgba = master_renderers.get(target_metaphor, _render_master_cube_solid)(MASTER_SIZE)
            if target_badge:
                master_rgba = _overlay_badge(master_rgba, target_badge)

        # 2. Export large PNGs (documentation / high-DPI UI only)
        emitted_files: Dict[str, Any] = {}
        png_lint: Dict[str, Any] = {}
        for sz, suffix, _desc in EXPORT_SPECS:
            png_name = f"{stem}{suffix}"
            png_path = dest_dir / png_name
            if sz == MASTER_SIZE:
                master_rgba.save(png_path, format="PNG")
            else:
                down = master_rgba.resize((sz, sz), Image.Resampling.LANCZOS)
                # LANCZOS bleeds colour into fully transparent pixels; zero the
                # RGB of A=0 samples so the exported PNG stays halo-free.
                down = _clear_transparent_rgb(down)
                down.save(png_path, format="PNG")
            emitted_files[f"png_{sz}"] = png_path
            with Image.open(png_path) as _ph:
                png_lint[f"png_{sz}"] = lint_png_asset(_ph.convert("RGBA"))

        # 3. Render CATIA runtime sizes independently, then quantize.
        # 22 and 32 keep their historical filenames (`<stem>.png` / `<stem>_32.png`)
        # so existing asset trees and manifest consumers stay valid.
        bmps: Dict[int, Image.Image] = {}
        for sz in PIXEL_SIZES:
            pixel_img = _render_pixel(target_metaphor, sz, bg_color=bg_color,
                                      badge=target_badge, input_image=input_image)
            png_path = dest_dir / (f"{stem}.png" if sz == 22 else f"{stem}_{sz}.png")
            pixel_img.save(png_path, format="PNG")
            emitted_files[f"png_{sz}"] = png_path

            bmp = _quantize_to_catia_bmp(pixel_img, sz, bg_color=bg_color,
                                         max_colors=MAX_FG_COLORS[sz])
            bmp_path = dest_dir / (f"{stem}.bmp" if sz == 22 else f"{stem}_{sz}.bmp")
            bmp.save(bmp_path, format="BMP")
            bmps[sz] = bmp
            emitted_files["bmp_normal_22" if sz == 22 else "bmp_large_32"] = bmp_path

        # 4. Quality gate: any FAIL blocks deployment and .CATRsc injection.
        lint_22 = lint_icon_asset(bmps[22], 22, bg_color=bg_color)
        lint_32 = lint_icon_asset(bmps[32], 32, bg_color=bg_color)
        png_ok = all(v["status"] == "PASS" for v in png_lint.values())
        gated = (lint_22["status"] == "PASS" and lint_32["status"] == "PASS" and png_ok)

        manifest = {
            "stem": stem,
            "metaphor": target_metaphor,
            "badge": target_badge or "none",
            "bg_color": tuple(bg_color),
            "design_contract": {
                "max_fg_colors": dict(MAX_FG_COLORS),
                "min_sharp_ratio": MIN_SHARP_RATIO,
                # Per size, because a flat bound cannot describe the framing
                # contract: a fully painted subject that still keeps the mask
                # margin fills 0.826 of a 22px canvas but 0.879 of a 32px one.
                "fg_ratio_bounds": {
                    str(sz): [FG_MIN, round(fg_ratio_ceiling(sz), 3)]
                    for sz in PIXEL_SIZES
                },
                "max_isolated_ratio": MAX_ISOLATED_RATIO,
                "content_margin": CONTENT_MARGIN,
                "content_min_edge": dict(CONTENT_MIN_EDGE),
            },
            "files": {k: _portable_path(v) for k, v in emitted_files.items()},
            "lint_22": lint_22,
            "lint_32": lint_32,
            "lint_png": png_lint,
            "ready_for_cnext": gated,
        }

        manifest_path = dest_dir / f"{stem}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        emitted_files["manifest"] = manifest_path

        return {
            "status": "PASS" if gated else "FAIL",
            "manifest": manifest,
            "files": emitted_files,
        }

    @classmethod
    def deploy_tool_icon(cls, tool_name: str, framework_dir: Path,
                         stem: Optional[str] = None,
                         metaphor: Optional[str] = None,
                         badge: Optional[str] = None,
                         input_image: Optional[Path] = None,
                         asset_dir: Optional[Path] = None) -> Dict[str, Any]:
        """One-Click Deployment: Generates icon assets and seamlessly injects into CAA module."""
        fw_path = Path(framework_dir)
        if not fw_path.exists():
            return {"status": "FAIL", "reason": f"Framework directory not found: {fw_path}"}

        actual_stem = stem or f"I_CADE{tool_name.replace(' ', '')}"
        res = cls.generate_icon_bundle(actual_stem, metaphor=metaphor, badge=badge, input_image=input_image, out_dir=asset_dir)
        if res["status"] != "PASS":
            return res

        # 1. Target Directory for CATIA Runtime Icons
        icons_dir = fw_path / "CNext" / "resources" / "graphic" / "icons" / "normal"
        icons_dir.mkdir(parents=True, exist_ok=True)

        # Deploy Normal (22x22) and Large (32x32)
        normal_src = res["files"]["bmp_normal_22"]
        large_src = res["files"]["bmp_large_32"]

        normal_dst = icons_dir / f"{actual_stem}.bmp"
        large_dst = icons_dir / f"{actual_stem}_32.bmp"

        shutil.copyfile(normal_src, normal_dst)
        shutil.copyfile(large_src, large_dst)

        # 2. Update the .CATRsc declarations that belong to *this* tool.
        #
        # A CAA msgcatalog directory holds one .CATRsc per command header and
        # each file may declare several commands. Rewriting every
        # `.Icon.Normal` line in every file (the previous behaviour) repointed
        # the icons of unrelated commands at the newly generated stem, so
        # deploying one icon silently destroyed the rest of the module.
        # We therefore only touch lines whose stored icon reference resolves
        # back to this tool: same stem, or the auto-derived `I_<toolname>`.
        rsc_dir = fw_path / "CNext" / "resources" / "msgcatalog"
        rsc_updated, rsc_skipped = [], []
        tool_key = tool_name.replace(" ", "").lower()
        own_refs = {
            actual_stem.lower(),
            f"i_{tool_key}",
        }

        def _decl_prefix(line: str) -> Optional[str]:
            """Return `<Header>.<Id>` for an `....Icon.Normal = "x";` line."""
            if ".Icon." not in line:
                return None
            return line.split(".Icon.")[0]

        def _ref_of(line: str) -> Optional[str]:
            """Return the icon stem a declaration line points at."""
            _, sep, tail = line.partition("=")
            if not sep:
                return None
            return tail.strip().rstrip(";").strip().strip('"')

        def _owns(line: str) -> bool:
            """True when the declaration belongs to this tool.

            Ownership is decided by the header prefix (production files look
            like `CAADateStampCmdHdr.CAADateStampCmd.Icon.Normal`), falling back
            to the icon reference itself for files whose prefix carries no name.
            """
            prefix = _decl_prefix(line)
            if prefix is None:
                return False
            if tool_key and tool_key in prefix.replace(" ", "").lower():
                return True
            ref = _ref_of(line)
            return ref is not None and ref.lower() in own_refs

        if rsc_dir.exists():
            for rsc_file in sorted(rsc_dir.glob("*.CATRsc")):
                try:
                    content = rsc_file.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    rsc_skipped.append(f"{rsc_file.name}: unreadable ({exc})")
                    continue

                norm_decl = f'.Icon.Normal = "{actual_stem}";'
                large_decl = f'.Icon.Large = "{actual_stem}_32";'

                new_lines: List[str] = []
                found_normal = found_large = touched = False
                for line in content.splitlines():
                    if _owns(line):
                        touched = True
                        if ".Icon.Normal" in line:
                            new_lines.append(line.split(".Icon.Normal")[0] + norm_decl)
                            found_normal = True
                        else:
                            new_lines.append(line.split(".Icon.Large")[0] + large_decl)
                            found_large = True
                    else:
                        new_lines.append(line)

                # A Large declaration is mandatory for high-DPI toolbars: add
                # one right after Normal when the file only had Normal.
                if touched and found_normal and not found_large:
                    for idx, line in enumerate(new_lines):
                        if line.endswith(norm_decl):
                            new_lines.insert(idx + 1, line.split(".Icon.Normal")[0] + large_decl)
                            break

                updated_content = "\n".join(new_lines) + "\n"
                if touched and updated_content != content:
                    try:
                        rsc_file.write_text(updated_content, encoding="utf-8")
                        rsc_updated.append(rsc_file.name)
                    except OSError as exc:
                        rsc_skipped.append(f"{rsc_file.name}: unwritable ({exc})")

        return {
            "status": "SUCCESS",
            "stem": actual_stem,
            "deployed_normal": str(normal_dst),
            "deployed_large": str(large_dst),
            "rsc_updated": rsc_updated,
            "rsc_skipped": rsc_skipped,
        }


# ── Top-Level Public Functional APIs ──────────────────────────────────
def generate_icon(stem_or_name: str,
                  metaphor: Optional[str] = None,
                  badge: Optional[str] = None,
                  input_image: Optional[Path] = None,
                  out_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Generate multi-resolution Ultra-HD PNGs and 8-bit palettized CATIA BMPs.

    Args:
        stem_or_name: Base stem or tool name (e.g. 'I_CADEDateStamp', 'BOMTool')
        metaphor: Visual metaphor ('stamp_clock', 'part_to_asm', 'bom_table', 'color_swatch', 'name_card', 'cube_solid')
        badge: Optional verb badge ('plus', 'pencil', 'refresh', 'check', 'search')
        input_image: Optional external logo/image path to remaster
        out_dir: Destination directory (defaults to assets/icons/generated)

    Returns:
        Dict with status, manifest, and emitted file paths
    """
    stem = stem_or_name if stem_or_name.startswith("I_") else f"I_CADE{stem_or_name.replace(' ', '')}"
    return UniversalIconStudio.generate_icon_bundle(
        stem=stem,
        metaphor=metaphor,
        badge=badge,
        input_image=input_image,
        out_dir=out_dir
    )


def deploy_icon(tool_name: str,
                framework_dir: Path,
                stem: Optional[str] = None,
                metaphor: Optional[str] = None,
                badge: Optional[str] = None,
                input_image: Optional[Path] = None,
                asset_dir: Optional[Path] = None) -> Dict[str, Any]:
    """One-click generation and injection of CATIA dual icons (22x22 Normal & 32x32 Large)
    into a CAA framework, updating .CATRsc dual resource declarations.

    Args:
        tool_name: Command/tool name (e.g. 'DateStamp')
        framework_dir: Path to the CAA framework directory
        stem: Explicit icon stem (e.g. 'I_CADEDateStamp')
        metaphor: Visual metaphor override
        badge: Secondary verb badge
        input_image: Optional external logo image to remaster
        asset_dir: Optional output asset directory

    Returns:
        Deployment result dict with paths and updated resource files
    """
    return UniversalIconStudio.deploy_tool_icon(
        tool_name=tool_name,
        framework_dir=framework_dir,
        stem=stem,
        metaphor=metaphor,
        badge=badge,
        input_image=input_image,
        asset_dir=asset_dir
    )


# ── CLI Interface ──────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="CADE Universal Icon Studio CLI")
    parser.add_argument("name", help="Tool or command name (e.g. DateStamp, BOMTool, CustomMilling)")
    parser.add_argument("--stem", default=None, help="Explicit icon stem (e.g. I_CADEDateStamp)")
    parser.add_argument("--metaphor", default=None, help="Visual metaphor (stamp_clock, part_to_asm, bom_table, cube_solid)")
    parser.add_argument("--badge", default=None, help="Secondary verb badge (plus, pencil, refresh, check, search)")
    parser.add_argument("--image", default=None, help="Path to custom image/logo to remaster")
    parser.add_argument("--out-dir", default=None, help="Destination directory for output assets")
    parser.add_argument("--deploy", default=None, help="Target CAA framework directory to automatically deploy into")

    args = parser.parse_args()
    stem = args.stem or f"I_CADE{args.name.replace(' ', '')}"
    input_img = Path(args.image) if args.image else None

    if args.deploy:
        res = UniversalIconStudio.deploy_tool_icon(
            tool_name=args.name,
            framework_dir=Path(args.deploy),
            stem=stem,
            metaphor=args.metaphor,
            badge=args.badge,
            input_image=input_img
        )
        print(f"Deploy Result: {res['status']}")
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        out_d = Path(args.out_dir) if args.out_dir else ASSETS_DIR
        res = UniversalIconStudio.generate_icon_bundle(
            stem=stem,
            metaphor=args.metaphor,
            badge=args.badge,
            input_image=input_img,
            out_dir=out_d
        )
        print(f"Generation Result: {res['status']}")
        print(f"Emitted to: {out_d}")
        print(json.dumps(res["manifest"]["lint_22"], indent=2))


if __name__ == "__main__":
    main()
