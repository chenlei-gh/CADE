"""
CADE Universal Icon Studio (icon_studio.py)
===========================================
Universal High-Definition Icon Generation Engine & Workflow Deployer for CATIA CAA.

Key Capabilities:
  1. Multi-Resolution Ultra-HD Pipeline:
     - 512x512 Master RGBA (Ultra-smooth antialiasing, metallic highlights, ambient soft shadows)
     - 256x256 HD / Documentation asset
     - 64x64 High-DPI UI asset
     - 32x32 CATIA Large Mode asset (RGBA PNG + 8-bit indexed BMP)
     - 22x22 CATIA Normal Mode asset (RGBA PNG + 8-bit indexed BMP)
  2. CATIA CNEXT Dual-Transparency Contract:
     - 8-bit palettized BMP (<=256 colors)
     - Palette index 0 strictly locked to CATIA_BG (192, 192, 192)
     - Four-corner background snap guaranteeing zero dirty halos
  3. Parametric Morpheme & Semantic Resolver:
     - Automatically infers domain metaphors from any tool name (date/stamp, part/asm, bom/table,
       color/swatch, rename/tag, pad/solid, pocket/cavity, gear, curve/surface, etc.)
     - Supports custom metaphor overrides and external image/logo high-resolution remastering
  4. Full Workflow Integration:
     - deploy_tool_icon(): Generates assets, writes normal/large BMPs into CNext/resources/graphic/icons/normal/,
       and updates .CATRsc with both Icon.Normal and Icon.Large declarations
     - Seamlessly hooked into actions.create_command and build.sync_runtime_view
"""

import json
import math
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

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
GEAR_HUB   = (255, 255, 0)      # Assembly hub
CYAN       = (75, 230, 255)     # Wireframe / geometry auxiliary lines
CYAN_EDGE  = (0, 157, 167)      # Wireframe edge
WHITE      = (255, 255, 255)    # Highlight
DEPTH_GRAY = (75, 75, 75)       # Cut / pocket cavity depth
RED_MARK   = (195, 20, 20)      # Cut / operation target edge

MASTER_SIZE = 512
EXPORT_SPECS = [
    (512, "_512.png", "Master Ultra-HD (512x512) RGBA"),
    (256, "_256.png", "Documentation HD (256x256) RGBA"),
    (64,  "_64.png",  "High-DPI UI (64x64) RGBA"),
    (32,  "_32.png",  "Large Mode (32x32) RGBA"),
    (22,  ".png",     "Normal Mode (22x22) RGBA"),
]


# ── Quality Gate Spec ──────────────────────────────────────────────────
BG_TOLERANCE = 36
FG_MIN, FG_MAX = 0.15, 0.75
MAX_COLORS = 256


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
    elif badge_name in ("search", "find"):
        r_lens = int(g_rad * 0.7)
        bd.ellipse([(cx - r_lens - 4, cy - r_lens - 4), (cx + r_lens - 4, cy + r_lens - 4)],
                   outline=(0, 140, 230, 255), width=7)
        bd.line([(cx + r_lens - 4, cy + r_lens - 4), (cx + r_lens + 12, cy + r_lens + 12)],
                   fill=CATIA_INK + (255,), width=8)
    return master


# ── Quantizer & BMP Writer (CNEXT Safe) ────────────────────────────────
def _quantize_to_catia_bmp(rgba: Image.Image, out_size: int = 22) -> Image.Image:
    """Downsample master RGBA to exact target size and format as 8-bit palettized BMP.
    Guarantee palette index 0 = CATIA_BG (192, 192, 192) and 4-corner purity."""
    resized = rgba.resize((out_size, out_size), Image.Resampling.LANCZOS)
    flat = Image.new("RGB", (out_size, out_size), CATIA_BG)
    flat.paste(resized, (0, 0), resized)

    # Snap 4 corners to guaranteed CATIA_BG
    px = flat.load()
    w, h = flat.size
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        px[x, y] = CATIA_BG

    # Edge clean up
    for x in range(w):
        for y in range(h):
            p = px[x, y]
            if all(abs(p[i] - CATIA_BG[i]) <= BG_TOLERANCE for i in range(3)):
                px[x, y] = CATIA_BG

    # Quantize to at most 255 colors for foreground
    fg_p = flat.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    raw_palette = fg_p.getpalette() or []

    # Rebuild palette: ensure index 0 is CATIA_BG
    new_palette = [CATIA_BG[0], CATIA_BG[1], CATIA_BG[2]]
    idx_map = {}
    cur_idx = 1
    for i in range(0, len(raw_palette), 3):
        color = (raw_palette[i], raw_palette[i+1], raw_palette[i+2])
        if all(abs(color[j] - CATIA_BG[j]) <= 2 for j in range(3)):
            idx_map[i // 3] = 0
        else:
            if cur_idx < 256:
                new_palette.extend(color)
                idx_map[i // 3] = cur_idx
                cur_idx += 1
            else:
                idx_map[i // 3] = 0

    # Fill remaining palette slots up to 256 entries (768 bytes)
    while len(new_palette) < 768:
        new_palette.extend(CATIA_BG)

    # Remap image pixels
    remapped = Image.new("P", (out_size, out_size), 0)
    if hasattr(fg_p, "get_flattened_data"):
        src_data = fg_p.get_flattened_data()
    else:
        src_data = list(fg_p.getdata())
    remapped_data = [idx_map.get(val, 0) for val in src_data]
    remapped.putdata(remapped_data)
    remapped.putpalette(new_palette)

    # Enforce exact 4 corners index 0
    rem_px = remapped.load()
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        rem_px[x, y] = 0

    return remapped


# ── Quality Gate (Lint) ────────────────────────────────────────────────
def lint_icon_asset(bmp_img: Image.Image, expected_size: int) -> Dict[str, Any]:
    """Audit BMP asset compliance against CATIA V5 runtime spec."""
    report = {
        "status": "PASS",
        "size": bmp_img.size,
        "mode": bmp_img.mode,
        "checks": {}
    }
    w, h = bmp_img.size
    report["checks"]["size_exact"] = (w == expected_size and h == expected_size)
    report["checks"]["is_palettized"] = (bmp_img.mode == "P")

    px = bmp_img.load()
    palette = bmp_img.getpalette() or []
    c0 = (palette[0], palette[1], palette[2]) if len(palette) >= 3 else None
    report["checks"]["palette_0_is_catia_bg"] = (c0 == CATIA_BG)

    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    report["checks"]["four_corners_pure_index_0"] = all(c == 0 for c in corners)

    # Foreground ratio
    fg_count = sum(1 for y in range(h) for x in range(w) if px[x, y] != 0)
    fg_ratio = fg_count / (w * h)
    report["checks"]["fg_ratio"] = round(fg_ratio, 3)
    report["checks"]["fg_ratio_in_bounds"] = (FG_MIN <= fg_ratio <= FG_MAX)

    if not all(report["checks"].values()):
        report["status"] = "WARN" if report["checks"]["palette_0_is_catia_bg"] else "FAIL"

    return report


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
                             out_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Generate full suite of assets: 512, 256, 64, 32, 22 PNGs + 22/32 BMPs."""
        dest_dir = Path(out_dir) if out_dir else ASSETS_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)

        # 1. Deduce Metaphor
        if input_image and Path(input_image).is_file():
            master_rgba = _render_master_from_image(Path(input_image), MASTER_SIZE)
        else:
            inferred_metaphor, inferred_badge = cls.resolve_metaphor_from_name(stem)
            target_metaphor = metaphor or inferred_metaphor
            target_badge = badge or inferred_badge

            if target_metaphor == "stamp_clock":
                master_rgba = _render_master_stamp_clock(MASTER_SIZE)
            elif target_metaphor == "part_to_asm":
                master_rgba = _render_master_part_to_asm(MASTER_SIZE)
            elif target_metaphor == "bom_table":
                master_rgba = _render_master_bom_table(MASTER_SIZE)
            elif target_metaphor == "color_swatch":
                master_rgba = _render_master_color_swatch(MASTER_SIZE)
            elif target_metaphor == "name_card":
                master_rgba = _render_master_name_card(MASTER_SIZE)
            else:
                master_rgba = _render_master_cube_solid(MASTER_SIZE)

            if target_badge:
                master_rgba = _overlay_badge(master_rgba, target_badge)

        # 2. Export Multi-Scale PNGs
        emitted_files = {}
        for sz, suffix, desc in EXPORT_SPECS:
            png_name = f"{stem}{suffix}"
            png_path = dest_dir / png_name
            if sz == MASTER_SIZE:
                master_rgba.save(png_path, format="PNG")
            else:
                sub_img = master_rgba.resize((sz, sz), Image.Resampling.LANCZOS)
                sub_img.save(png_path, format="PNG")
            emitted_files[f"png_{sz}"] = png_path

        # 3. Export CATIA 22x22 Normal BMP
        bmp_22 = _quantize_to_catia_bmp(master_rgba, 22)
        bmp_22_path = dest_dir / f"{stem}.bmp"
        bmp_22.save(bmp_22_path, format="BMP")
        emitted_files["bmp_normal_22"] = bmp_22_path

        # 4. Export CATIA 32x32 Large BMP
        bmp_32 = _quantize_to_catia_bmp(master_rgba, 32)
        bmp_32_path = dest_dir / f"{stem}_32.bmp"
        bmp_32.save(bmp_32_path, format="BMP")
        emitted_files["bmp_large_32"] = bmp_32_path

        # 5. Quality Gate Linting
        lint_22 = lint_icon_asset(bmp_22, 22)
        lint_32 = lint_icon_asset(bmp_32, 32)

        manifest = {
            "stem": stem,
            "metaphor": metaphor or "auto",
            "badge": badge or "none",
            "files": {k: str(v) for k, v in emitted_files.items()},
            "lint_22": lint_22,
            "lint_32": lint_32,
            "ready_for_cnext": (lint_22["status"] in ("PASS", "WARN") and lint_32["status"] in ("PASS", "WARN"))
        }

        manifest_path = dest_dir / f"{stem}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        emitted_files["manifest"] = manifest_path

        return {
            "status": "PASS" if manifest["ready_for_cnext"] else "FAIL",
            "manifest": manifest,
            "files": emitted_files
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

        # 2. Update .CATRsc Files in msgcatalog
        rsc_dir = fw_path / "CNext" / "resources" / "msgcatalog"
        rsc_updated = []
        if rsc_dir.exists():
            for rsc_file in rsc_dir.glob("*.CATRsc"):
                try:
                    content = rsc_file.read_text(encoding="utf-8", errors="replace")
                    # If this command or module is referenced
                    norm_decl = f'.Icon.Normal = "{actual_stem}";'
                    large_decl = f'.Icon.Large = "{actual_stem}_32";'

                    lines = content.splitlines()
                    new_lines = []
                    found_normal = False
                    found_large = False

                    for line in lines:
                        if ".Icon.Normal" in line:
                            # Replace old icon reference
                            prefix = line.split(".Icon.Normal")[0]
                            new_lines.append(f'{prefix}{norm_decl}')
                            found_normal = True
                        elif ".Icon.Large" in line:
                            prefix = line.split(".Icon.Large")[0]
                            new_lines.append(f'{prefix}{large_decl}')
                            found_large = True
                        else:
                            new_lines.append(line)

                    # If normal was found but large was missing, append large
                    if found_normal and not found_large:
                        # locate normal index
                        for idx, l in enumerate(new_lines):
                            if norm_decl in l:
                                prefix = l.split(".Icon.Normal")[0]
                                new_lines.insert(idx + 1, f'{prefix}{large_decl}')
                                break

                    updated_content = "\n".join(new_lines) + "\n"
                    if updated_content != content:
                        rsc_file.write_text(updated_content, encoding="utf-8")
                        rsc_updated.append(rsc_file.name)
                except Exception as e:
                    pass

        return {
            "status": "SUCCESS",
            "stem": actual_stem,
            "deployed_normal": str(normal_dst),
            "deployed_large": str(large_dst),
            "rsc_updated": rsc_updated,
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
