"""Validated 22x22 icon design primitives (PartToAsm pilot, 2026-08-18).

Official-palette constants sampled from B28 icons + drawing helpers that
passed gate E (CATIA toolbar). Generated Base icons compose these instead
of reinventing shapes — see ICON_GENERATION_SPEC §2.1 (official vocabulary
extraction): don't invent visual language, reuse CATIA's own encoding.

Palette provenance (sampled, not guessed):
  INK / FACE      <- I_Pad / I_Hole   (PartDesign solids)
  GEAR_* / CYAN*  <- I_Part / I_Product (gear = part, gear pair = assembly)
"""
import math

from PIL import Image, ImageDraw

# ── Official sampled palette ─────────────────────────────────────────
BG        = (192, 192, 192)   # standard toolbar background gray
DOC_BG    = (180, 180, 180)   # document-family background (I_Part/I_Product)
INK       = (24, 16, 82)      # outline / pseudo-3D extrusion navy
FACE      = (255, 255, 150)   # PartDesign solid face (lemon yellow)
GEAR_FACE = (255, 238, 135)   # gear face
GEAR_HUB  = (255, 255, 0)     # gear hub bright yellow
CYAN      = (75, 230, 255)    # secondary gear face
CYAN_EDGE = (0, 157, 167)     # secondary gear edge
WHITE     = (255, 255, 255)   # top-left highlight

CANVAS = 22


def canvas(bg=BG):
    """22x22 RGB canvas at official background gray."""
    img = Image.new("RGB", (CANVAS, CANVAS), bg)
    return img, ImageDraw.Draw(img)


def gear(d, cx, cy, r, face=GEAR_FACE, edge=INK, hub=GEAR_HUB):
    """Official-style gear (I_Part/I_Product vocabulary).

    Disc + 4 axis teeth (+ 4 diagonal teeth when r >= 4, the official
    8-tooth look) + square hub. r = disc radius without teeth.
    Validated at r=4 (yellow) and r=3 (cyan) on the production toolbar.
    """
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=face, outline=edge)
    w = 2
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        tx, ty = cx + dx * (r + 1), cy + dy * (r + 1)
        d.rectangle([tx - w + 1, ty - w + 1, tx + w - 1, ty + w - 1],
                    fill=face, outline=edge)
    if r >= 4:
        dd = r - 1
        for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            tx, ty = cx + sx * dd, cy + sy * dd
            d.rectangle([tx, ty, tx + 1, ty + 1], fill=face, outline=edge)
    if hub is not None:
        if r >= 4:
            d.rectangle([cx - 1, cy - 1, cx + 1, cy + 1],
                        fill=hub, outline=edge)
        else:
            d.point([(cx, cy)], fill=edge)


def cube3d(d, x0, y0, s, depth=2, face=FACE):
    """PartDesign-style solid (I_Pad/I_Hole vocabulary).

    Lemon face + navy pseudo-3D extrusion down-right + white top/left
    highlight. s = face edge length, depth = extrusion offset in px.
    """
    d.polygon([(x0, y0 + s - 1), (x0 + depth, y0 + s - 1 + depth),
               (x0 + s - 1 + depth, y0 + s - 1 + depth),
               (x0 + s - 1 + depth, y0 + depth), (x0 + s - 1, y0)], fill=INK)
    d.rectangle([x0, y0, x0 + s - 1, y0 + s - 1], fill=face, outline=INK)
    d.line([(x0 + 1, y0 + 1), (x0 + s - 2, y0 + 1)], fill=WHITE)
    d.line([(x0 + 1, y0 + 1), (x0 + 1, y0 + s - 2)], fill=WHITE)


def frame(d, x0, y0, s, w=2, color=INK):
    """Hollow nested-outline frame (assembly container / boundary)."""
    for i in range(w):
        d.rectangle([x0 + i, y0 + i, x0 + s - 1 - i, y0 + s - 1 - i],
                    outline=color)


# Official color-swatch palette (I_AutomaticColorProperty grid order)
SWATCHES = [(255, 0, 0), (0, 255, 0), (0, 0, 255),
            (255, 0, 255), (160, 80, 40), (255, 255, 0)]


def swatches(d, x0, y0, cols, rows, sw, sh, colors=SWATCHES, gap=1):
    """Official color vocabulary: saturated swatch grid with INK borders
    (I_AutomaticColorProperty encoding). Cells clip silently at canvas
    edges; caller keeps them inside."""
    for r in range(rows):
        for c in range(cols):
            col = colors[(r * cols + c) % len(colors)]
            x, y = x0 + c * (sw + gap), y0 + r * (sh + gap)
            d.rectangle([x, y, x + sw - 1, y + sh - 1],
                        fill=col, outline=INK)


def letter_a(d, x, y, color=INK):
    """Hand-drawn 7x9 hard-edge pixel 'A' (2px legs + crossbar).
    PIL's default font is a vector face in Pillow >= 10 and anti-aliases,
    which violates the spec's hard-edge clause — letters must be drawn
    as pixels."""
    d.rectangle([x + 1, y, x + 5, y], fill=color)            # top bar
    for yy in range(y + 1, y + 9):
        d.rectangle([x, yy, x + 1, yy], fill=color)          # left leg
        d.rectangle([x + 5, yy, x + 6, yy], fill=color)      # right leg
    d.rectangle([x, y + 4, x + 6, y + 5], fill=color)        # crossbar


# ── Morpheme reserve (B28 semantic audit 2026-08-18) ─────────────────
# Extracted from official recurrence across the 40 high-frequency icons —
# see knowledge/ui/official_icon_semantics.md section 7.2. NOT yet gate-E
# validated on a real command: defined for future demand only; wire one
# into a production icon only through the full A-E gate.
RED_MARK   = (155, 0, 0)     # cut / target-edge marker
                             # (I_Groove red slot, I_Chamfer/I_Fillet dashes)
REF_BLUE   = (10, 0, 255)    # reference / copy / array element
                             # (I_Offset dashed copy, I_CircularPattern items)
DEPTH_GRAY = (75, 75, 75)    # cavity interior shading (I_Pocket / I_Hole)


def _dash_hline(d, x0, x1, y, color, dash, gap):
    x = x0
    while x <= x1:
        d.line([(x, y), (min(x + dash - 1, x1), y)], fill=color)
        x += dash + gap


def _dash_vline(d, y0, y1, x, color, dash, gap):
    y = y0
    while y <= y1:
        d.line([(x, y), (x, min(y + dash - 1, y1))], fill=color)
        y += dash + gap


def _dash_rect(d, box, color, dash, gap):
    x0, y0, x1, y1 = box
    _dash_hline(d, x0, x1, y0, color, dash, gap)
    _dash_hline(d, x0, x1, y1, color, dash, gap)
    _dash_vline(d, y0, y1, x0, color, dash, gap)
    _dash_vline(d, y0, y1, x1, color, dash, gap)


def red_marker(d, box, dash=2, gap=1, color=RED_MARK):
    """Red dashed frame marking the edge/face a feature acts on
    (I_Chamfer/I_Fillet vocabulary). Reserve morpheme — official also
    uses dashed ellipses; rect is the simplest form. box=(x0,y0,x1,y1)."""
    _dash_rect(d, box, color, dash, gap)


def dashed_copy(d, box, color=REF_BLUE, dash=2, gap=1):
    """Blue dashed square = offset copy / reference / array instance
    (I_Offset/I_CircularPattern vocabulary). Reserve morpheme."""
    _dash_rect(d, box, color, dash, gap)


def boss(d, x0, y0, s, face=FACE, edge=INK):
    """Protruding solid block = add-material (I_Pad vocabulary).
    Yellow face + ink outline + white top-left highlight. Reserve."""
    d.rectangle([x0, y0, x0 + s - 1, y0 + s - 1], fill=face, outline=edge)
    d.line([(x0 + 1, y0 + 1), (x0 + s - 2, y0 + 1)], fill=WHITE)
    d.line([(x0 + 1, y0 + 1), (x0 + 1, y0 + s - 2)], fill=WHITE)


def notch(d, x0, y0, w, h, edge=INK, depth=DEPTH_GRAY):
    """Recessed cavity = remove-material (I_Pocket/I_Hole vocabulary).
    Ink outline + dark-gray interior depth. Reserve."""
    d.rectangle([x0, y0, x0 + w - 1, y0 + h - 1], outline=edge)
    d.rectangle([x0 + 1, y0 + 1, x0 + w - 2, y0 + h - 2], fill=depth)


def ctrl_point(d, cx, cy, color=CYAN, edge=INK):
    """Geometry control point, 3x3 cyan with ink border
    (I_Point/I_Line/I_Circle vocabulary: cyan = geometry aid). Reserve."""
    d.rectangle([cx - 1, cy - 1, cx + 1, cy + 1], fill=color, outline=edge)


def cycle_arrows(d, cx, cy, r, color=INK, accent=CYAN_EDGE, width=2):
    """Refresh/update double arc (I_Update vocabulary — the most-referenced
    official icon, 40 CATRsc refs). Two opposing arcs + square heads.
    Simplified reserve — redraw from I_Update if a real command needs it."""
    d.arc([cx - r, cy - r, cx + r, cy + r], 210, 330, fill=color, width=width)
    d.arc([cx - r, cy - r, cx + r, cy + r], 30, 150, fill=accent, width=width)
    for ang, col in ((330, color), (150, accent)):
        a = math.radians(ang)
        x = round(cx + r * math.cos(a))
        y = round(cy + r * math.sin(a))
        d.rectangle([x - 1, y - 1, x + 1, y + 1], fill=col)
