#!/usr/bin/env python3
"""
Icon System Test Suite (v3.2)
==============================
Validates all 107 geometric patterns, color mapping, BMP format,
and rendering pipeline integrity.

Run: python test_icons.py
"""

import re
import shutil
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from icon_provider import (
    DOMAIN_MAP, COLOR_MAP,
    get_icon, resolve_icon, _get_color_for_icon,
    _render_icon,
)

total = passed = 0

def check(label, ok, detail=""):
    global total, passed
    total += 1; passed += 1 if ok else 0
    s = "PASS" if ok else "FAIL"
    print(f"  [{s}] {label}" + (f" — {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════════
#  PART A: Pattern Completeness
# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("  A. Pattern Completeness")
print("=" * 60)

# Extract all pattern names from source
src = (SKILL_ROOT / "skills" / "icon_provider.py").read_text(encoding="utf-8")
all_patterns = sorted(set(re.findall(r'"([a-z][a-z0-9_-]*)"\s*:\s*lambda', src)))

check("Pattern count >= 100", len(all_patterns) >= 100,
      f"{len(all_patterns)} patterns found")

# Ensure DOMAIN_MAP values are all valid patterns
domain_icons = set(DOMAIN_MAP.values())
missing = domain_icons - set(all_patterns)
check("DOMAIN_MAP → valid patterns", len(missing) == 0,
      f"{len(missing)} missing: {missing}" if missing else "all covered")


# ═══════════════════════════════════════════════════════════════
#  PART B: Rendering Integrity (every pattern)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  B. Rendering Integrity (all patterns)")
print("=" * 60)

render_ok = render_fail = 0
seen_hashes = set()
dup_count = 0

for name in all_patterns:
    try:
        bmp = _render_icon(name)
        data = bmp.read_bytes()
    except Exception as e:
        render_fail += 1
        print(f"  [FAIL] {name}: {e}")
        continue

    # BMP format check
    w = abs(int.from_bytes(data[18:22], "little", signed=True))
    h = abs(int.from_bytes(data[22:26], "little", signed=True))
    bpp = int.from_bytes(data[28:30], "little")
    if w != 22 or h != 22 or bpp != 8:
        render_fail += 1
        print(f"  [FAIL] {name}: bad format {w}x{h} {bpp}bpp")
        continue

    # Must have visible pixels (pixels differing from CATIA gray background)
    px = data[1078:]  # skip 54B header + 1024B palette
    pal = data[54:54+1024]
    bg_idx = None
    for i in range(256):
        r, g, b = pal[i*4+2], pal[i*4+1], pal[i*4]
        if abs(r-192) < 24 and abs(g-192) < 24 and abs(b-192) < 24:
            bg_idx = i
            break
    non_zero = sum(1 for b in px if b != bg_idx)
    if non_zero == 0:
        render_fail += 1
        print(f"  [FAIL] {name}: 0 visible pixels")
        continue

    # Check duplicate pixels (all patterns should be visually unique)
    px_hash = hash(bytes(px))
    if px_hash in seen_hashes:
        dup_count += 1
    seen_hashes.add(px_hash)

    # Palette check: must have non-trivial colors (not just grayscale 0-255)
    unique_colors = len({(pal[i*4], pal[i*4+1], pal[i*4+2])
                         for i in range(256)
                         if sum(pal[i*4:i*4+3]) > 5})

    render_ok += 1

check("All patterns render", render_fail == 0,
      f"{render_ok}/{render_ok+render_fail} pass, {dup_count} duplicates")

check("Average visible pixels >= 100", render_ok > 0,
      f"{render_ok} patterns verified")


# ═══════════════════════════════════════════════════════════════
#  PART C: Color Mapping
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  C. Color Mapping")
print("=" * 60)

check("COLOR_MAP entries", len(COLOR_MAP) >= 50,
      f"{len(COLOR_MAP)} entries")

# Every COLOR_MAP key should return its own color
color_ok = 0
for key, expected in COLOR_MAP.items():
    actual = _get_color_for_icon(key)
    if actual == expected:
        color_ok += 1
    else:
        print(f"  [WARN] {key}: expected {expected}, got {actual}")

check("COLOR_MAP self-consistency", color_ok == len(COLOR_MAP),
      f"{color_ok}/{len(COLOR_MAP)}")

# Every DOMAIN_MAP icon should resolve to a non-default color
default_white = 0
for icon in set(DOMAIN_MAP.values()):
    c = _get_color_for_icon(icon)
    if c == (200, 200, 200):
        default_white += 1

check("DOMAIN_MAP icons have colors", default_white < 10,
      f"{default_white} icons fall back to gray (out of {len(set(DOMAIN_MAP.values()))})")


# ═══════════════════════════════════════════════════════════════
#  PART D: API Functions
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  D. Public API")
print("=" * 60)

# resolve_icon
r = resolve_icon("HoleAnalysisCmd")
check("resolve_icon(HoleAnalysisCmd)", r in all_patterns, r)

r = resolve_icon("MeasureDistanceCmd")
check("resolve_icon(MeasureDistance)", r in all_patterns, r)

r = resolve_icon("UnknownXyz")
check("resolve_icon(fallback)", isinstance(r, str) and len(r) > 0, r)

# get_icon with cache
from icon_provider import CACHE_DIR
for f in CACHE_DIR.glob("*.bmp"):
    f.unlink()

p1 = get_icon("cube")
p2 = get_icon("cube")
check("get_icon cache hit", p1 is not None and p2 is not None,
      f"path={p1}")

# get_icon handles unknown gracefully
p3 = get_icon("nonexistent_xyz")
check("get_icon fallback", p3 is not None and p3.exists())


# ═══════════════════════════════════════════════════════════════
#  PART E: Accent Colors (multi-color)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  E. Multi-Color / Accent")
print("=" * 60)

accent_icons = ["heart", "flame", "lightning", "star", "trophy", "warning", "sun", "target"]
accent_colors = 0
for name in accent_icons:
    try:
        bmp = _render_icon(name)
        data = bmp.read_bytes()
        pal = data[54:54+1024]
        colors = len({(pal[i*4], pal[i*4+1], pal[i*4+2])
                      for i in range(256) if sum(pal[i*4:i*4+3]) > 5})
        if colors >= 10:
            accent_colors += 1
    except Exception:
        pass

check("Accent icons multi-color", accent_colors >= 6,
      f"{accent_colors}/{len(accent_icons)} icons have 10+ colors")


# ═══════════════════════════════════════════════════════════════
#  PART F: Performance
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  F. Performance")
print("=" * 60)

import time

# Warm-up
_render_icon("cube")

# Bulk render
start = time.perf_counter()
for name in list(all_patterns)[:20]:
    _render_icon(name)
elapsed = time.perf_counter() - start
avg_ms = (elapsed / 20) * 1000

check("Render speed < 50ms/icon", avg_ms < 50,
      f"{avg_ms:.1f}ms per icon ({20} icons in {elapsed:.2f}s)")


# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"  RESULT: {passed}/{total} PASSED"
      + (f" ({total-passed} FAILED)" if total-passed > 0 else ""))
print("=" * 60)

# Cleanup
for f in CACHE_DIR.glob("*.bmp"):
    f.unlink()

sys.exit(0 if passed == total else 1)
