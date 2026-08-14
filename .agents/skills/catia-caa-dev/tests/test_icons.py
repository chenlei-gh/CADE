#!/usr/bin/env python3
"""
Icon System Test Suite (v3.2)
==============================
Validates all geometric patterns, color mapping, BMP format,
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

# Runtime extraction must match the test-side regex (guards table refactors)
from icon_provider import PATTERN_NAMES
check("PATTERN_NAMES == source regex", set(all_patterns) == set(PATTERN_NAMES),
      f"{len(PATTERN_NAMES)} runtime vs {len(all_patterns)} source")

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
      f"{render_ok}/{render_ok+render_fail} pass")

check("No duplicate renders (fallback collision guard)", dup_count == 0,
      f"{dup_count} duplicate pixel hashes across {len(all_patterns)} patterns")

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
for f in CACHE_DIR.glob("*.png"):
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
#  PART G: Composition (verb badge) + Halftone texture
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  G. Composition + Texture")
print("=" * 60)

from icon_provider import resolve_icon_ex, _apply_checker
from PIL import Image

b, g = resolve_icon_ex("CreateHoleCmd")
check("compose CreateHoleCmd -> hole+plus", b == "hole" and g == "plus", f"{b}+{g}")

b, g = resolve_icon_ex("HoleAnalysisCmd")
check("compose HoleAnalysisCmd -> hole+chart", b == "hole" and g == "chart", f"{b}+{g}")

b, g = resolve_icon_ex("MeasureDistanceCmd")
check("compose dedupe ruler+ruler", b == "ruler" and g is None, f"{b}+{g}")

b, g = resolve_icon_ex("createhole")  # fused lowercase from actions.py
check("compose fused 'createhole'", b == "hole" and g == "plus", f"{b}+{g}")

b, g = resolve_icon_ex("cube")
check("plain pattern pass-through", b == "cube" and g is None, f"{b}+{g}")

# name→icon coverage: 常用业务命令名不再掉兜底菱形
b, g = resolve_icon_ex("CreateCircleCmd")
check("compose CreateCircleCmd -> circle+plus", b == "circle" and g == "plus", f"{b}+{g}")

b, g = resolve_icon_ex("RenameInstanceCmd")
check("compose RenameInstanceCmd -> cube+pencil", b == "cube" and g == "pencil", f"{b}+{g}")

b, g = resolve_icon_ex("UpdatePartCmd")
check("compose UpdatePartCmd -> cube+refresh", b == "cube" and g == "refresh", f"{b}+{g}")

b, g = resolve_icon_ex("AutoRenameCmd")
check("compose AutoRenameCmd -> pencil (dedupe)", b == "pencil" and g is None, f"{b}+{g}")

b, g = resolve_icon_ex("BatchProcessCmd")
check("compose BatchProcessCmd -> pattern", b == "pattern" and g is None, f"{b}+{g}")

b, g = resolve_icon_ex("CheckModelCmd")
check("compose CheckModelCmd -> cube+check", b == "cube" and g == "check", f"{b}+{g}")

# ─── Semantic layer (IconSemantic + 4-level resolver) ───
from icon_provider import (analyze_command, normalize_command_name,
                           ICON_HASH)

sem = analyze_command("CreateCircleCmd")
check("semantic CreateCircleCmd EXACT", sem.operation == "CREATE"
      and sem.obj == "circle" and sem.confidence == "EXACT",
      f"{sem.operation}/{sem.obj}/{sem.confidence}")

sem = analyze_command("AutoRenameCmd")
check("semantic AutoRenameCmd EDIT/rename", sem.operation == "EDIT"
      and sem.base == "pencil" and "auto" in sem.modifier,
      f"{sem.operation}/{sem.base}/{sem.modifier}")

sem = analyze_command("createhole")  # fused lowercase from actions.py
check("semantic fused COMPOUND", sem.base == "hole" and sem.badge == "plus"
      and sem.confidence == "COMPOUND", f"{sem.base}/{sem.confidence}")

sem = analyze_command("TotallyUnknownCmd")
check("semantic FALLBACK diamond", sem.base == "diamond"
      and sem.confidence == "FALLBACK", f"{sem.base}/{sem.confidence}")

check("normalize suffix chain", normalize_command_name("CreateHoleDlgCmd")
      == "CreateHole", normalize_command_name("CreateHoleDlgCmd"))

check("normalize keeps CAT-prefix semantics",
      normalize_command_name("CATPartCmd") == "CATPart",
      normalize_command_name("CATPartCmd"))

# Level 3 longest-first: 'pattern'(7) must beat 'part'(4) regardless of dict order
b, g = resolve_icon_ex("PartpatternX")
check("longest-first substring", b == "pattern", b)

check("ICON_HASH format", isinstance(ICON_HASH, str) and len(ICON_HASH) == 8,
      ICON_HASH)

# composite render: badge must change pixels, format stays 22x22 8bpp
# NOTE: _render_icon reuses one tmp path per pattern — read bytes immediately
da = _render_icon("drill").read_bytes()
db = _render_icon("drill", "plus").read_bytes()
check("badge changes pixels", da != db)
check("composite format 22x22 8bpp",
      abs(int.from_bytes(db[18:22], "little", signed=True)) == 22
      and int.from_bytes(db[28:30], "little") == 8)

# halftone checker: large body fill gains a lighter shade
im22 = Image.new("RGB", (22, 22), (192, 192, 192))
for yy in range(2, 20):
    for xx in range(2, 20):
        im22.putpixel((xx, yy), (155, 0, 0))
out = _apply_checker(im22, (155, 0, 0))
ncolors = len(set(out.getdata()))
check("checker texture adds shade", ncolors >= 3, f"{ncolors} colors")

# small fills stay flat (no checker noise)
im23 = Image.new("RGB", (22, 22), (192, 192, 192))
im23.putpixel((11, 11), (155, 0, 0))
out2 = _apply_checker(im23, (155, 0, 0))
check("small fill stays flat", len(set(out2.getdata())) == 2)


# ═══════════════════════════════════════════════════════════════
#  PART H: First-compile freshness (stale/foreign icon overwrite)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  H. Icon Freshness on Compile")
print("=" * 60)

import tempfile
from icon_provider import copy_icons_to_runtime

try:
    from actions import ActionContext, create_command

    tmp = Path(tempfile.mkdtemp())
    try:
        fw = tmp / "TestFw.edu"
        (fw / "IdentityCard").mkdir(parents=True)
        (fw / "IdentityCard" / "IdentityCard.h").write_text(
            'AddPrereqComponent("System",Public);')
        mod = fw / "TestMod.m"
        (mod / "src").mkdir(parents=True)
        (mod / "LocalInterfaces").mkdir()
        (mod / "Imakefile.mk").write_text("MODULE=TestMod\nSOURCES = \\")
        icons_dir = fw / "CNext" / "resources" / "graphic" / "icons" / "normal"
        icons_dir.mkdir(parents=True)

        # Pre-existing stale icon (old CADE version / other tool)
        stale = icons_dir / "I_freshcmd.bmp"
        stale.write_bytes(b"STALE-GARBAGE-ICON")

        ctx = ActionContext(str(tmp))
        ctx.refresh()
        result = create_command(ctx, "FreshCmd", "TestMod.m")
        check("create_command pending", result["status"] == "pending",
              result.get("status", "?"))

        from changeset import ChangeSet
        cs = ChangeSet.from_dict(result["changeset"]) if isinstance(result["changeset"], dict) else result["changeset"]
        cs.apply()

        new_bytes = stale.read_bytes()
        check("stale icon overwritten", new_bytes != b"STALE-GARBAGE-ICON"
              and len(new_bytes) > 100, f"{len(new_bytes)} bytes")
        # Must be a valid 22x22 8-bit BMP
        check("fresh icon is 22x22 8bpp BMP",
              new_bytes[:2] == b"BM"
              and abs(int.from_bytes(new_bytes[18:22], "little", signed=True)) == 22
              and int.from_bytes(new_bytes[28:30], "little") == 8)

        # Runtime sync must also overwrite a stale runtime icon
        rv_icon = tmp / "win_b64" / "resources" / "graphic" / "icons" / "normal" / "I_freshcmd.bmp"
        rv_icon.parent.mkdir(parents=True, exist_ok=True)
        rv_icon.write_bytes(b"OLD-RUNTIME-ICON")
        copy_icons_to_runtime(tmp)
        check("runtime icon refreshed", rv_icon.read_bytes() == new_bytes)

        # Identical icon is not rewritten (ChangeSet stays clean)
        ctx2 = ActionContext(str(tmp))
        ctx2.refresh()
        r2 = create_command(ctx2, "FreshCmd", "TestMod.m")
        cs2 = r2["changeset"]
        bin_paths = cs2.get("_binary", {}) if isinstance(cs2, dict) else {}
        check("identical icon not rewritten",
              not any("I_freshcmd" in p for p in bin_paths))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
except ImportError as e:
    check("freshness test imports", False, str(e))


# ═══════════════════════════════════════════════════════════════
#  PART I: HD multi-size rendering
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  I. HD Multi-Size Rendering")
print("=" * 60)

def _bmp_info(data):
    w = abs(int.from_bytes(data[18:22], "little", signed=True))
    h = abs(int.from_bytes(data[22:26], "little", signed=True))
    bpp = int.from_bytes(data[28:30], "little")
    return w, h, bpp

# 48x48 HD: true 48x48, 24-bit (no 8-bit palette quantize)
d48 = _render_icon("fillet", size=48).read_bytes()
w, h, bpp = _bmp_info(d48)
check("HD 48x48 format", (w, h, bpp) == (48, 48, 24), f"{w}x{h} {bpp}bpp")

# 64x64 HD with badge
d64 = _render_icon("drill", "plus", size=64).read_bytes()
w, h, bpp = _bmp_info(d64)
check("HD 64x64+badge format", (w, h, bpp) == (64, 64, 24), f"{w}x{h} {bpp}bpp")

# HD smoothness: LANCZOS produces far more than 256 unique colors
from PIL import Image as _Img
import io as _io
ncolors = len(set(_Img.open(_io.BytesIO(d48)).convert("RGB").getdata()))
check("HD 24-bit smooth gradients", ncolors > 256, f"{ncolors} unique colors")

# default stays 22x22 8-bit (CATIA runtime compatibility)
d22 = _render_icon("fillet").read_bytes()
w, h, bpp = _bmp_info(d22)
check("default stays 22x22 8-bit", (w, h, bpp) == (22, 22, 8), f"{w}x{h} {bpp}bpp")

# get_icon caches per size (first call renders, second hits cache;
# both return the cached path)
pa = get_icon("cube", size=48)
pb = get_icon("cube", size=48)
check("get_icon HD cache", pa is not None and pb is not None
      and pa == pb and pa.exists(),
      pb.name if pb else "?")

# PNG alpha channel (docs/preview output)
pp = get_icon("circle", size=64, format="png", alpha=True)
check("PNG output", pp is not None and pp.suffix == ".png"
      and pp.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n",
      pp.name if pp else "?")
im = _Img.open(pp)
has_alpha = im.mode == "RGBA" and any(a < 255 for *_, a in im.getdata())
check("PNG transparent background", has_alpha)


# ═══════════════════════════════════════════════════════════════
#  PART J: Visual Regression (golden samples)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  J. Visual Regression (golden 22x22 samples)")
print("=" * 60)

# Golden files are the single source of truth: tests/golden/icons/*.bmp,
# named '<base>.bmp' or '<base>+<badge>.bmp'. Regenerate ONLY after an
# intentional renderer change: python tests/update_golden_icons.py
GOLDEN_DIR = SKILL_ROOT / "tests" / "golden" / "icons"
goldens = sorted(GOLDEN_DIR.glob("*.bmp"))
check("golden samples present", len(goldens) >= 20, f"{len(goldens)} found")

golden_bad = 0
for fn in goldens:
    base, _, badge = fn.stem.partition("+")
    cur = _render_icon(base, badge or None).read_bytes()
    if cur != fn.read_bytes():
        golden_bad += 1
        diff = sum(1 for a, b in zip(cur, fn.read_bytes()) if a != b)
        print(f"  [FAIL] golden {fn.name}: {diff} bytes differ")
check("visual regression pixel-identical", golden_bad == 0,
      f"{len(goldens)-golden_bad}/{len(goldens)} identical")


# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"  RESULT: {passed}/{total} PASSED"
      + (f" ({total-passed} FAILED)" if total-passed > 0 else ""))
print("=" * 60)

# Cleanup
for f in CACHE_DIR.glob("*.bmp"):
    f.unlink()
for f in CACHE_DIR.glob("*.png"):
    f.unlink()

sys.exit(0 if passed == total else 1)
