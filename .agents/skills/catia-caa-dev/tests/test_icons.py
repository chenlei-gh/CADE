#!/usr/bin/env python3
"""
Icon System Test Suite (v4.0 — Official-Only)
==============================================
Validates the Official-Only icon pipeline: semantic analysis, official
stem resolution, badge glyph rendering, BMP format, cache, and fallback.

Run: python test_icons.py
"""

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from icon_provider import (
    OBJECT_VOCAB, VERB_MAP, COMPOUND_MAP, BADGE_GLYPHS, ICON_HASH,
    DEFAULT_OFFICIAL_STEM,
    get_icon, resolve_icon, resolve_icon_ex,
    analyze_command, normalize_command_name,
    official_candidate_stem, resolve_official_icon, _official_icons_dir,
    _render_badge_plate, _render_placeholder, _compose_official,
    copy_icons_to_runtime, CACHE_DIR,
    _GENERATED_ICONS_DIR, _GENERATED_BASE_MAP,
    resolve_generated_stem, resolve_generated_icon,
)

total = passed = 0

def check(label, ok, detail=""):
    global total, passed
    total += 1; passed += 1 if ok else 0
    s = "PASS" if ok else "FAIL"
    print(f"  [{s}] {label}" + (f" — {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════════
#  PART A: Badge Glyph Completeness
# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("  A. Badge Glyph Completeness")
print("=" * 60)

# Extract badge glyph names from source
src = (SKILL_ROOT / "skills" / "icon_provider.py").read_text(encoding="utf-8")
all_glyphs = sorted(set(re.findall(r'"([a-z][a-z0-9_-]*)"\s*:\s*lambda', src)))

check("Badge glyph count == 23", len(all_glyphs) == 23,
      f"{len(all_glyphs)} glyphs found")

# Runtime extraction must match the test-side regex
check("BADGE_GLYPHS == source regex", set(all_glyphs) == set(BADGE_GLYPHS),
      f"{len(BADGE_GLYPHS)} runtime vs {len(all_glyphs)} source")

# Every VERB_MAP value must be a valid badge glyph
verb_glyphs = set(VERB_MAP.values())
missing = verb_glyphs - set(all_glyphs)
check("VERB_MAP → valid glyphs", len(missing) == 0,
      f"{len(missing)} missing: {missing}" if missing else "all covered")


# ═══════════════════════════════════════════════════════════════
#  PART B: Badge Glyph Rendering Integrity
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  B. Badge Glyph Rendering Integrity")
print("=" * 60)

render_ok = render_fail = 0
seen_hashes = set()
dup_count = 0

for name in all_glyphs:
    try:
        plate = _render_badge_plate(name, 8)
        # Convert to BMP bytes for format check
        import io
        buf = io.BytesIO()
        plate.convert("RGB").save(buf, format="BMP")
        data = buf.getvalue()
    except Exception as e:
        render_fail += 1
        print(f"  [FAIL] {name}: {e}")
        continue

    # Must have visible pixels (non-gray)
    px = data[54:]
    bg_rgb = (192, 192, 192)
    non_zero = 0
    for i in range(0, len(px) - 2, 3):
        b, g, r = px[i], px[i+1], px[i+2]
        if abs(r-bg_rgb[0]) >= 24 or abs(g-bg_rgb[1]) >= 24 or abs(b-bg_rgb[2]) >= 24:
            non_zero += 1
    if non_zero == 0:
        render_fail += 1
        print(f"  [FAIL] {name}: 0 visible pixels")
        continue

    px_hash = hash(bytes(px))
    if px_hash in seen_hashes:
        dup_count += 1
    seen_hashes.add(px_hash)
    render_ok += 1

check("All badge glyphs render", render_fail == 0,
      f"{render_ok}/{render_ok+render_fail} pass")

check("No duplicate glyph renders", dup_count == 0,
      f"{dup_count} duplicate pixel hashes across {len(all_glyphs)} glyphs")


# ═══════════════════════════════════════════════════════════════
#  PART C: Public API
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  C. Public API")
print("=" * 60)

# resolve_icon returns official stem or None
r = resolve_icon("CreateHoleCmd")
check("resolve_icon(CreateHoleCmd) -> I_Hole", r == "I_Hole", r)

r = resolve_icon("TotallyUnknownCmd")
check("resolve_icon(unknown) -> None", r is None, str(r))

# get_icon with cache
for f in CACHE_DIR.glob("*.bmp"):
    f.unlink()
for f in CACHE_DIR.glob("*.png"):
    f.unlink()

p1 = get_icon("CreateHoleCmd")
p2 = get_icon("CreateHoleCmd")
check("get_icon cache hit", p1 is not None and p2 is not None and p1 == p2,
      f"path={p1}")

# get_icon handles unknown gracefully (placeholder or default official)
p3 = get_icon("nonexistent_xyz")
check("get_icon fallback", p3 is not None and p3.exists())


# ═══════════════════════════════════════════════════════════════
#  PART D: Semantic Analysis
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  D. Semantic Analysis")
print("=" * 60)

sem = analyze_command("CreateCircleCmd")
check("semantic CreateCircleCmd EXACT", sem.operation == "CREATE"
      and sem.obj == "circle" and sem.confidence == "EXACT",
      f"{sem.operation}/{sem.obj}/{sem.confidence}")

sem = analyze_command("AutoRenameCmd")
check("semantic AutoRenameCmd EDIT/rename", sem.operation == "EDIT"
      and sem.obj == "rename" and "auto" in sem.modifier,
      f"{sem.operation}/{sem.obj}/{sem.modifier}")

sem = analyze_command("createhole")  # fused lowercase
check("semantic fused COMPOUND", sem.obj == "hole" and sem.badge == "plus"
      and sem.confidence == "COMPOUND", f"{sem.obj}/{sem.confidence}")

sem = analyze_command("TotallyUnknownCmd")
check("semantic FALLBACK", sem.base is None
      and sem.confidence == "FALLBACK", f"{sem.base}/{sem.confidence}")

check("normalize suffix chain", normalize_command_name("CreateHoleDlgCmd")
      == "CreateHole", normalize_command_name("CreateHoleDlgCmd"))

check("normalize keeps CAT-prefix semantics",
      normalize_command_name("CATPartCmd") == "CATPart",
      normalize_command_name("CATPartCmd"))

# Level 3 longest-first: 'pattern'(7) must beat 'part'(4)
b, g = resolve_icon_ex("PartpatternX")
check("longest-first substring", b == "I_CircularPattern" or b is None,
      f"pattern-related: {b}")

check("ICON_HASH format", isinstance(ICON_HASH, str) and len(ICON_HASH) == 8,
      ICON_HASH)

# Entity hint
b, g = resolve_icon_ex("FooCmd", hint="hole")
check("entity hint overrides name", b == "I_Hole", f"{b} (hint='hole')")

b, g = resolve_icon_ex("CreateFooCmd", hint="fillet")
check("hint + verb badge compose", b == "I_Fillet" and g == "plus", f"{b}+{g}")

sem = analyze_command("FooCmd", hint="hole")
check("hint confidence EXACT", sem.confidence == "EXACT"
      and sem.obj == "hole", f"{sem.obj}/{sem.confidence}")


# ═══════════════════════════════════════════════════════════════
#  PART E: Official Stem Resolution
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  E. Official Stem Resolution")
print("=" * 60)

check("hole -> I_Hole", official_candidate_stem("hole") == "I_Hole",
      official_candidate_stem("hole"))
check("sketch alias -> I_Sketcher",
      official_candidate_stem("sketch") == "I_Sketcher",
      official_candidate_stem("sketch"))
check("remove alias -> I_RemoveBody",
      official_candidate_stem("remove") == "I_RemoveBody",
      official_candidate_stem("remove"))
check("rename alias -> I_RenameFamily",
      official_candidate_stem("rename") == "I_RenameFamily",
      official_candidate_stem("rename"))
check("bom alias -> I_DNBBOMtoXML",
      official_candidate_stem("bom") == "I_DNBBOMtoXML",
      official_candidate_stem("bom"))
check("color alias -> I_AutomaticColorProperty",
      official_candidate_stem("color") == "I_AutomaticColorProperty",
      official_candidate_stem("color"))
check("properties alias -> I_Properties",
      official_candidate_stem("properties") == "I_Properties",
      official_candidate_stem("properties"))
check("circular pattern",
      official_candidate_stem("pattern", ("circular",)) == "I_CircularPattern",
      official_candidate_stem("pattern", ("circular",)))
check("bare pattern denied", official_candidate_stem("pattern") is None)
check("part+asm weak-blocked",
      official_candidate_stem("part", ("to", "asm")) is None)
check("bare part allowed", official_candidate_stem("part") == "I_Part",
      official_candidate_stem("part"))
check("loft alias -> I_ICMLoftLT (S6)",
      official_candidate_stem("loft") == "I_ICMLoftLT",
      official_candidate_stem("loft"))
check("numeric stem (no anchor -> default)",
      official_candidate_stem("numeric") == "I_Numeric",
      official_candidate_stem("numeric"))
check("tool denied (S5-verified)", official_candidate_stem("tool") is None)
check("mode denied (S5-verified)", official_candidate_stem("mode") is None)
check("assemble denied (S5-verified)", official_candidate_stem("assemble") is None)
check("reference denied (S5-verified)", official_candidate_stem("reference") is None)

# Batch-2 (S6 index, CATNls-title-verified) — 22 aliases added 2026-08-17
_BATCH2 = {
    "material": "I_ApplyMaterial", "pan": "I_Translate",
    "search": "I_Find", "revolve": "I_RevolutionSurface",
    "boolean": "I_CldBoolean", "arc": "I_ArcCircle",
    "curvature": "I_SurfCurvAna", "drill": "I_DrillHoles",
    "transform": "I_SpdTransform", "statistic": "I_CATFmtFollow",
    "configure": "I_VPMNavConfigure", "table": "I_DrwTable",
    "spring": "I_MldSpring", "boss": "I_SpdBoss", "gear": "I_GearJoint",
    "axis": "I_AxisLine", "annotation": "I_Sch_DatumSymbol",
    "distance": "I_BandAnalysis", "setting": "I_DNBVisuSettings",
    "mill": "I_MfgEndMillTool", "symmetry": "I_ShapeSymmetry",
}
for _tok, _stem in _BATCH2.items():
    check(f"batch2 {_tok} -> {_stem}",
          official_candidate_stem(_tok) == _stem,
          official_candidate_stem(_tok))


# ═══════════════════════════════════════════════════════════════
#  PART F: Official Icon Resolution (CATIA-dependent)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  F. Official Icon Resolution")
print("=" * 60)

off_dir = _official_icons_dir()
check("icons dir probe is Path or None",
      off_dir is None or (hasattr(off_dir, "is_dir") and off_dir.is_dir()),
      str(off_dir))

if off_dir is not None:
    # B28 installed: verify specific resolutions
    hole_off = resolve_official_icon("CreateHoleCmd")
    check("CreateHoleCmd -> I_Hole.bmp",
          hole_off is not None and hole_off.name == "I_Hole.bmp",
          hole_off.name if hole_off else None)
    circ = resolve_official_icon("CreateCircleCmd")
    check("CreateCircleCmd -> I_Circle.bmp",
          circ is not None and circ.name == "I_Circle.bmp",
          circ.name if circ else None)
    sk = resolve_official_icon("CreateSketchCmd")
    check("CreateSketchCmd -> I_Sketcher.bmp",
          sk is not None and sk.name == "I_Sketcher.bmp",
          sk.name if sk else None)
    # Production commands: verified aliases
    rn = resolve_official_icon("CAAAutoRename")
    check("CAAAutoRename -> I_RenameFamily.bmp",
          rn is not None and rn.name == "I_RenameFamily.bmp",
          rn.name if rn else None)
    cl = resolve_official_icon("CAAAutoColor")
    check("CAAAutoColor -> I_AutomaticColorProperty.bmp",
          cl is not None and cl.name == "I_AutomaticColorProperty.bmp",
          cl.name if cl else None)
    # Unknown command -> default fallback
    unk = resolve_official_icon("TotallyUnknownCmd")
    check("Unknown -> default official",
          unk is not None and unk.name == f"{DEFAULT_OFFICIAL_STEM}.bmp",
          unk.name if unk else None)
    # CAABOMTool: 'tool' is DENY -> falls to default
    bom = resolve_official_icon("CAABOMTool")
    check("CAABOMTool -> default (tool DENY)",
          bom is not None and bom.name == f"{DEFAULT_OFFICIAL_STEM}.bmp",
          bom.name if bom else None)
    # CAAPartToAsm: 'part' WEAK + modifier -> falls to default
    pta = resolve_official_icon("CAAPartToAsm")
    check("CAAPartToAsm -> default (part WEAK)",
          pta is not None and pta.name == f"{DEFAULT_OFFICIAL_STEM}.bmp",
          pta.name if pta else None)
    # S5 flips: properties now official; loft stem has no file -> default
    pr = resolve_official_icon("ShowPropertiesCmd")
    check("ShowPropertiesCmd -> I_Properties.bmp",
          pr is not None and pr.name == "I_Properties.bmp",
          pr.name if pr else None)
    lf = resolve_official_icon("CreateLoftCmd")
    check("CreateLoftCmd -> I_ICMLoftLT.bmp (S6 alias)",
          lf is not None and lf.name == "I_ICMLoftLT.bmp",
          lf.name if lf else None)
    # Batch-2 spot-checks: title-verified aliases resolve to real files
    for _cmd, _want in (("ApplyMaterialCmd", "I_ApplyMaterial.bmp"),
                        ("CreateArcCmd", "I_ArcCircle.bmp"),
                        ("CreateTableCmd", "I_DrwTable.bmp")):
        _r = resolve_official_icon(_cmd)
        check(f"{_cmd} -> {_want}",
              _r is not None and _r.name == _want,
              _r.name if _r else None)
else:
    check("B28 not installed: official lookup is None",
          resolve_official_icon("CreateHoleCmd") is None)


# ═══════════════════════════════════════════════════════════════
#  PART G: Composition (official + badge)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  G. Composition (official + badge)")
print("=" * 60)

b, g = resolve_icon_ex("CreateHoleCmd")
check("compose CreateHoleCmd -> I_Hole+plus", b == "I_Hole" and g == "plus",
      f"{b}+{g}")

b, g = resolve_icon_ex("HoleAnalysisCmd")
check("compose HoleAnalysisCmd -> I_Hole+chart", b == "I_Hole" and g == "chart",
      f"{b}+{g}")

b, g = resolve_icon_ex("MeasureDistanceCmd")
check("compose MeasureDistanceCmd -> I_BandAnalysis+ruler (S6)",
      b == "I_BandAnalysis" and g == "ruler", f"{b}+{g}")

b, g = resolve_icon_ex("createhole")
check("compose fused 'createhole' -> I_Hole+plus", b == "I_Hole" and g == "plus",
      f"{b}+{g}")

b, g = resolve_icon_ex("CreateCircleCmd")
check("compose CreateCircleCmd -> I_Circle+plus", b == "I_Circle" and g == "plus",
      f"{b}+{g}")

b, g = resolve_icon_ex("RenameInstanceCmd")
check("compose RenameInstanceCmd -> I_Instance+pencil (verb consumed)",
      b == "I_Instance" and g == "pencil", f"{b}+{g}")

b, g = resolve_icon_ex("RenameFamilyCmd")
check("compose RenameFamilyCmd -> I_RenameFamily+pencil",
      b == "I_RenameFamily" and g == "pencil", f"{b}+{g}")

b, g = resolve_icon_ex("CheckModelCmd")
check("compose CheckModelCmd -> I_Model+check (verb consumed)",
      b == "I_Model" and g == "check", f"{b}+{g}")


# ═══════════════════════════════════════════════════════════════
#  PART H: Icon Freshness on Compile
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  H. Icon Freshness on Compile")
print("=" * 60)

import tempfile

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

        # Pre-existing stale icon
        stale = icons_dir / "I_freshcmd.bmp"
        stale.write_bytes(b"STALE-GARBAGE-ICON")

        ctx = ActionContext(str(tmp))
        ctx.refresh()
        result = create_command(ctx, "FreshCmd", "TestMod.m")
        check("create_command pending", result["status"] == "pending",
              result.get("status", "?"))

        from changeset import ChangeSet
        cs = ChangeSet.from_dict(result["changeset"]) if isinstance(result["changeset"], dict) else result["changeset"]
        # An authorized ChangeSet carries a touched-path baseline, so apply()
        # refuses to run without a workspace_root to verify it against
        # (changeset.py step 0a2). Production always supplies one
        # (kernel._apply_changeset_dict); a bare apply() would be rejected here
        # and silently leave the stale icon on disk.
        unrooted = cs.apply()
        check("authorized changeset refuses bare apply",
              unrooted.get("status") == "rejected", str(unrooted.get("status")))
        applied = cs.apply(workspace_root=tmp)
        check("authorized changeset applies with workspace_root",
              applied.get("status") == "applied", str(applied.get("errors")))

        new_bytes = stale.read_bytes()
        check("stale icon overwritten", new_bytes != b"STALE-GARBAGE-ICON"
              and len(new_bytes) > 100, f"{len(new_bytes)} bytes")
        # Must be a valid 22x22 BMP. Bit depth depends on the source:
        # FreshCmd has no official match -> default I_P3DefaultIcon (4-bit
        # palette, copied byte-for-byte so CNEXT background transparency
        # works); a 24-bit BMP would show a flat background box in CATIA.
        check("fresh icon is 22x22 BMP (palette or 24bpp)",
              new_bytes[:2] == b"BM"
              and abs(int.from_bytes(new_bytes[18:22], "little", signed=True)) == 22
              and int.from_bytes(new_bytes[28:30], "little") in (4, 8, 24))

        # Runtime sync
        rv_icon = tmp / "win_b64" / "resources" / "graphic" / "icons" / "normal" / "I_freshcmd.bmp"
        rv_icon.parent.mkdir(parents=True, exist_ok=True)
        rv_icon.write_bytes(b"OLD-RUNTIME-ICON")
        copy_icons_to_runtime(tmp)
        check("runtime icon refreshed", rv_icon.read_bytes() == new_bytes)
        rv_icon.write_bytes(b"OLD-RUNTIME-ICON")
        copy_icons_to_runtime(mod)
        check("copy_icons_to_runtime(.m) still writes workspace root",
              rv_icon.read_bytes() == new_bytes and not (mod / "win_b64").exists())

        # Entity hint flows through create_command
        ctx3 = ActionContext(str(tmp))
        ctx3.refresh()
        r3 = create_command(ctx3, "ZzzCmd", "TestMod.m", category="hole")
        cs3 = ChangeSet.from_dict(r3["changeset"]) if isinstance(r3["changeset"], dict) else r3["changeset"]
        applied3 = cs3.apply(workspace_root=tmp)
        check("entity-hint changeset applies with workspace_root",
              applied3.get("status") == "applied", str(applied3.get("errors")))
        hinted = icons_dir / "I_zzzcmd.bmp"
        check("entity-hint icon written", hinted.exists(),
              f"{hinted.name} {hinted.stat().st_size if hinted.exists() else 0}B")
        if hinted.exists():
            hb, _ = resolve_icon_ex("ZzzCmd", hint="hole")
            check("opaque name + hint -> official stem", hb == "I_Hole", hb)

        # Identical icon not rewritten
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
#  PART I: HD Multi-Size Rendering
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  I. HD Multi-Size Rendering")
print("=" * 60)

def _bmp_info(data):
    w = abs(int.from_bytes(data[18:22], "little", signed=True))
    h = abs(int.from_bytes(data[22:26], "little", signed=True))
    bpp = int.from_bytes(data[28:30], "little")
    return w, h, bpp

if off_dir is not None:
    # HD from official source
    p48 = get_icon("CreateHoleCmd", size=48)
    check("HD 48x48 from official", p48 is not None and p48.exists())
    if p48:
        d48 = p48.read_bytes()
        w, h, bpp = _bmp_info(d48)
        check("HD 48x48 format", (w, h, bpp) == (48, 48, 24), f"{w}x{h} {bpp}bpp")

    p64 = get_icon("CreateHoleCmd", size=64, format="bmp")
    check("HD 64x64+badge", p64 is not None and p64.exists())
    if p64:
        d64 = p64.read_bytes()
        w, h, bpp = _bmp_info(d64)
        check("HD 64x64 format", (w, h, bpp) == (64, 64, 24), f"{w}x{h} {bpp}bpp")

    # PNG alpha
    pp = get_icon("CreateCircleCmd", size=64, format="png", alpha=True)
    check("PNG output", pp is not None and pp.suffix == ".png"
          and pp.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n",
          pp.name if pp else "?")
    from PIL import Image as _Img
    im = _Img.open(pp)
    has_alpha = im.mode == "RGBA" and any(a < 255 for *_, a in im.getdata())
    check("PNG transparent background", has_alpha)
else:
    # No CATIA: placeholder rendering
    d48 = _render_placeholder(size=48).read_bytes()
    w, h, bpp = _bmp_info(d48)
    check("placeholder 48x48 format", (w, h, bpp) == (48, 48, 24), f"{w}x{h} {bpp}bpp")

    d22 = _render_placeholder().read_bytes()
    w, h, bpp = _bmp_info(d22)
    check("placeholder 22x22 24-bit", (w, h, bpp) == (22, 22, 24), f"{w}x{h} {bpp}bpp")


# ═══════════════════════════════════════════════════════════════
#  PART J: Placeholder (no-CATIA fallback)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  J. Placeholder Rendering")
print("=" * 60)

# Placeholder must render without error
ph = _render_placeholder("plus")
check("placeholder renders", ph is not None and ph.exists())
if ph:
    d = ph.read_bytes()
    check("placeholder is 22x22 24bpp BMP",
          d[:2] == b"BM"
          and abs(int.from_bytes(d[18:22], "little", signed=True)) == 22
          and int.from_bytes(d[28:30], "little") == 24)
    ph.unlink()  # reading it was the last use

# Placeholder without badge
ph2 = _render_placeholder()
check("placeholder no badge", ph2 is not None and ph2.exists())
if ph2:
    ph2.unlink()  # reading it was the last use


# ═══════════════════════════════════════════════════════════════
#  PART K: Scratch-file ownership
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  K. Scratch-file ownership (get_icon)")
print("=" * 60)

# _compose_official / _render_placeholder hand back a scratch file in %TEMP%
# named with os.getpid(). get_icon copies it into the cache, and that copy is
# the file's last use, so get_icon must remove it. Otherwise every rendered
# (name, badge, size, format) combination stays behind for the life of the
# machine — one per process that ever rendered it.
#
# The names are predictable, and they are compared by name rather than by a
# before/after set diff: the scratch name embeds os.getpid(), so any combo
# rendered earlier in this same process would already be present in the
# "before" snapshot and a set diff would silently see nothing.
_TEMP = Path(os.environ.get("TEMP", "/tmp"))
_SCRATCH_CALLS = [
    ("CreateHoleCmd", 22, "bmp", False),
    ("CreateCircleCmd", 64, "png", True),
    ("nonexistent_xyz", 22, "bmp", False),
    ("CreateHoleCmd", 48, "bmp", False),
]

_scratch_paths = set()
for _name, _size, _fmt, _alpha in _SCRATCH_CALLS:
    _official = resolve_official_icon(_name)
    _badge = resolve_icon_ex(_name)[1]
    _ext = "png" if _fmt == "png" else "bmp"
    if _official is not None:
        _scratch_paths.add(
            _TEMP / f"cade_icon_off_{_official.stem}_{_badge or 'base'}"
                    f"_{_size}_{os.getpid()}.{_ext}"
        )
    _scratch_paths.add(
        _TEMP / f"cade_icon_placeholder_{_badge or 'base'}"
                f"_{_size}_{os.getpid()}.{_ext}"
    )

# Start from a clean slate: drop any scratch file this pid left earlier and
# force real renders, since a cache hit returns before making one.
for _p in _scratch_paths:
    if _p.exists():
        _p.unlink()
for f in CACHE_DIR.glob("*.bmp"):
    f.unlink()
for f in CACHE_DIR.glob("*.png"):
    f.unlink()

for _name, _size, _fmt, _alpha in _SCRATCH_CALLS:
    get_icon(_name, size=_size, format=_fmt, alpha=_alpha)

leaked = sorted(p.name for p in _scratch_paths if p.exists())
check("get_icon leaves no cade_icon_* scratch files", not leaked, str(leaked))

# The cache itself must still be populated — cleanup must not eat the result.
cached_ok = get_icon("CreateHoleCmd").exists()
check("get_icon still populates the cache", cached_ok)

# Deleting the scratch file must not have cost the cached copy its contents.
cached_path = get_icon("CreateHoleCmd")
check("cached icon is still a readable BMP",
      cached_path.read_bytes()[:2] == b"BM")


# ═══════════════════════════════════════════════════════════════
#  PART L: Generated Base Resolution (ADR §3 Rule 7 / §8)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  L. Generated Base Resolution (ADR §3 Rule 7 / §8)")
print("=" * 60)

check("generated icons dir exists", _GENERATED_ICONS_DIR.is_dir(), str(_GENERATED_ICONS_DIR))

# All 4 production assets must exist on disk
for _semantic, _stem in _GENERATED_BASE_MAP.items():
    _f = _GENERATED_ICONS_DIR / f"{_stem}.bmp"
    check(f"asset exists: {_stem}.bmp ({_semantic})", _f.is_file(), str(_f))

# Direct stem resolution and path retrieval
for _semantic, _stem in (
    ("parttoasm", "I_CADEPartToAsm"),
    ("bomtool", "I_CADEBOMTool"),
    ("autocolor", "I_CADEAutoColor"),
    ("autorename", "I_CADEAutoRename"),
):
    check(f"resolve_generated_stem({_semantic}) -> {_stem}",
          resolve_generated_stem(_semantic) == _stem)
    _path = resolve_generated_icon(_semantic)
    check(f"resolve_generated_icon({_semantic}) -> {_stem}.bmp",
          _path is not None and _path.name == f"{_stem}.bmp")

# Production command names and variants in resolve_icon_ex (badge must be None)
_GEN_VARIANTS = (
    ("CAAPartToAsm", "I_CADEPartToAsm"),
    ("CAAPartToAsmCmd", "I_CADEPartToAsm"),
    ("parttoasm", "I_CADEPartToAsm"),
    ("CAABOMTool", "I_CADEBOMTool"),
    ("CAABOMToolCmd", "I_CADEBOMTool"),
    ("bomtool", "I_CADEBOMTool"),
    ("CAAAutoColor", "I_CADEAutoColor"),
    ("CAAAutoColorCmd", "I_CADEAutoColor"),
    ("autocolor", "I_CADEAutoColor"),
    ("CAAAutoRename", "I_CADEAutoRename"),
    ("CAAAutoRenameCmd", "I_CADEAutoRename"),
    ("autorename", "I_CADEAutoRename"),
    ("I_CADEPartToAsm", "I_CADEPartToAsm"),
)
for _cmd, _expected_stem in _GEN_VARIANTS:
    _b, _g = resolve_icon_ex(_cmd)
    check(f"resolve_icon_ex({_cmd}) -> {_expected_stem} + no badge",
          _b == _expected_stem and _g is None, f"{_b}+{_g}")

# End-to-end get_icon returns cached BMP matching generated asset bytes
for _cmd, _expected_stem in (
    ("CAAPartToAsm", "I_CADEPartToAsm"),
    ("CAABOMTool", "I_CADEBOMTool"),
    ("CAAAutoColor", "I_CADEAutoColor"),
    ("CAAAutoRename", "I_CADEAutoRename"),
):
    _p = get_icon(_cmd)
    _gen_bmp = _GENERATED_ICONS_DIR / f"{_expected_stem}.bmp"
    check(f"get_icon({_cmd}) exists", _p is not None and _p.is_file(), str(_p))
    if _p and _gen_bmp.is_file():
        check(f"get_icon({_cmd}) byte-identical to {_expected_stem}.bmp",
              _p.read_bytes() == _gen_bmp.read_bytes())

# Verify create_command & inspect_header_resources CATRsc stem contract (ADR §8)
try:
    from actions import ActionContext, create_command, inspect_header_resources
    _tmp_adr = Path(tempfile.mkdtemp())
    try:
        _fw = _tmp_adr / "AdrFw.edu"
        (_fw / "IdentityCard").mkdir(parents=True)
        (_fw / "IdentityCard" / "IdentityCard.h").write_text('AddPrereqComponent("System",Public);')
        _mod = _fw / "AdrMod.m"
        (_mod / "src").mkdir(parents=True)
        (_mod / "LocalInterfaces").mkdir()
        (_mod / "Imakefile.mk").write_text("MODULE=AdrMod\nSOURCES = \\")

        _ctx = ActionContext(str(_tmp_adr))
        _ctx.refresh()
        _res = create_command(_ctx, "CAAPartToAsm", "AdrMod.m")
        check("create_command(CAAPartToAsm) status pending", _res["status"] == "pending")

        from changeset import ChangeSet
        _cs = ChangeSet.from_dict(_res["changeset"]) if isinstance(_res["changeset"], dict) else _res["changeset"]

        # 1. CATRsc must reference "I_CADEPartToAsm" (not "I_caaparttoasm")
        _rsc_key = str(_fw / "CNext" / "resources" / "msgcatalog" / "CAAPartToAsmHdr.CATRsc")
        _rsc_content = _cs.created.get(_rsc_key, "")
        check("CAAPartToAsm CATRsc Icon.Normal references I_CADEPartToAsm",
              'Icon.Normal = "I_CADEPartToAsm"' in _rsc_content, _rsc_content)
        check("CAAPartToAsm CATRsc Icon.Large references I_CADEPartToAsm_32",
              'Icon.Large  = "I_CADEPartToAsm_32"' in _rsc_content, _rsc_content)

        # 2. Binary icon must be written as I_CADEPartToAsm.bmp and I_CADEPartToAsm_32.bmp
        _ico_key = str(_fw / "CNext" / "resources" / "graphic" / "icons" / "normal" / "I_CADEPartToAsm.bmp")
        _ico_key_32 = str(_fw / "CNext" / "resources" / "graphic" / "icons" / "normal" / "I_CADEPartToAsm_32.bmp")
        check("CAAPartToAsm writes I_CADEPartToAsm.bmp in ChangeSet", _ico_key in _cs._binary)
        check("CAAPartToAsm writes I_CADEPartToAsm_32.bmp in ChangeSet", _ico_key_32 in _cs._binary)
        if _ico_key in _cs._binary:
            _expected_bytes = (_GENERATED_ICONS_DIR / "I_CADEPartToAsm.bmp").read_bytes()
            check("CAAPartToAsm icon bytes match I_CADEPartToAsm.bmp", _cs._binary[_ico_key] == _expected_bytes)
        if _ico_key_32 in _cs._binary:
            _expected_bytes_32 = (_GENERATED_ICONS_DIR / "I_CADEPartToAsm_32.bmp").read_bytes()
            check("CAAPartToAsm 32x32 icon bytes match I_CADEPartToAsm_32.bmp", _cs._binary[_ico_key_32] == _expected_bytes_32)

        # 3. inspect_header_resources resolves I_CADEPartToAsm
        from meta_model import Workbench
        _wb_entity = Workbench(name="AdrWb", path=_fw, framework=_ctx.snapshot.frameworks[0])
        _ctx.snapshot.frameworks[0].workbenches.append(_wb_entity)
        _insp = inspect_header_resources(
            _ctx,
            workbench_name="AdrWb",
            header_class="CAAPartToAsmHdr",
            header_id="CAAPartToAsm",
            command_name="CAAPartToAsm",
            cs=_cs,
        )
        check("inspect_header_resources(CAAPartToAsm) icon_ref == I_CADEPartToAsm",
              _insp.get("icon_ref") == "I_CADEPartToAsm", str(_insp.get("icon_ref")))
        check("inspect_header_resources(CAAPartToAsm) icon_file == I_CADEPartToAsm.bmp",
              _insp.get("icon_file") is not None and _insp["icon_file"].name == "I_CADEPartToAsm.bmp")
    finally:
        shutil.rmtree(_tmp_adr, ignore_errors=True)
except Exception as e:
    check("create_command ADR contract test", False, str(e))


# ═══════════════════════════════════════════════════════════════
#  PART M: Universal Icon Studio (Multi-Resolution & Quality Gate)
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  M. Universal Icon Studio Engine & Deployment")
print("=" * 60)

from icon_studio import UniversalIconStudio, lint_icon_asset, CATIA_BG
from PIL import Image

# 1. Metaphor Inference
for _tool_name, _expected_metaphor in (
    ("CAADateStamp", "stamp_clock"),
    ("ClockTriggerCmd", "stamp_clock"),
    ("CAAPartToAsm", "part_to_asm"),
    ("MyAssemblyTool", "part_to_asm"),
    ("ExportBOMTable", "bom_table"),
    ("AutoColorProperty", "color_swatch"),
    ("RenameFeatureCmd", "name_card"),
    ("GenericMilling", "cube_solid"),
):
    _m, _ = UniversalIconStudio.resolve_metaphor_from_name(_tool_name)
    check(f"resolve_metaphor_from_name({_tool_name}) -> {_expected_metaphor}",
          _m == _expected_metaphor, _m)

# 2. Dynamic Bundle Generation & Verification
_tmp_studio_dir = Path(tempfile.mkdtemp())
try:
    _gen_res = UniversalIconStudio.generate_icon_bundle(
        stem="I_CADETestTool",
        metaphor="stamp_clock",
        badge="plus",
        out_dir=_tmp_studio_dir,
    )
    check("UniversalIconStudio bundle status PASS", _gen_res["status"] == "PASS")

    _files = _gen_res["files"]
    for _k in ("png_512", "png_256", "png_64", "png_32", "png_22", "bmp_normal_22", "bmp_large_32", "manifest"):
        check(f"Bundle emitted {_k}", _k in _files and Path(_files[_k]).exists())

    # Check 32x32 BMP compliance
    _bmp_32_img = Image.open(_files["bmp_large_32"])
    _lint_32 = lint_icon_asset(_bmp_32_img, 32)
    _bmp_32_img.close()
    check("32x32 BMP passes size_exact", _lint_32["checks"]["size_exact"])
    check("32x32 BMP is palettized (8-bit)", _lint_32["checks"]["is_palettized"])
    check("32x32 BMP Palette[0] is CATIA_BG (192, 192, 192)", _lint_32["checks"]["palette_0_is_catia_bg"])
    check("32x32 BMP four corners index 0 pure", _lint_32["checks"]["four_corners_pure_index_0"])
    check("32x32 BMP fg ratio in [15%, 75%]", _lint_32["checks"]["fg_ratio_in_bounds"], f"{_lint_32['checks']['fg_ratio']:.1%}")

    # 3. deploy_tool_icon contract
    _fw_test = _tmp_studio_dir / "DeployFw.edu"
    _rsc_dir = _fw_test / "CNext" / "resources" / "msgcatalog"
    _rsc_dir.mkdir(parents=True)
    _test_rsc = _rsc_dir / "DeployTestHdr.CATRsc"
    _test_rsc.write_text('DeployTestHdr.DeployTest.Icon.Normal = "I_old";\n', encoding="utf-8")

    _dep_res = UniversalIconStudio.deploy_tool_icon("DeployTest", _fw_test, stem="I_CADEDeployTest", asset_dir=_tmp_studio_dir)
    check("deploy_tool_icon status SUCCESS", _dep_res["status"] == "SUCCESS")
    check("deployed normal 22x22 exists", Path(_dep_res["deployed_normal"]).exists())
    check("deployed large 32x32 exists", Path(_dep_res["deployed_large"]).exists())

    _new_rsc_text = _test_rsc.read_text(encoding="utf-8")
    check(".CATRsc updated with Icon.Normal", 'DeployTestHdr.DeployTest.Icon.Normal = "I_CADEDeployTest";' in _new_rsc_text)
    check(".CATRsc updated with Icon.Large", 'DeployTestHdr.DeployTest.Icon.Large = "I_CADEDeployTest_32";' in _new_rsc_text)
finally:
    shutil.rmtree(_tmp_studio_dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
#  PART N: Mainline Workflow Activation & CLI Integration
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  N. Mainline Workflow Activation & CLI Integration")
print("=" * 60)

from icon_studio import generate_icon, deploy_icon
from cade import cmd_icon
from requirements import RequirementsClarifier
from kernel import Kernel, KernelMode

_tmp_n_dir = Path(tempfile.mkdtemp())
try:
    # 1. Functional generate_icon
    _n_gen = generate_icon("MyCustomCmd", metaphor="part_to_asm", out_dir=_tmp_n_dir)
    check("generate_icon() returns PASS", _n_gen["status"] == "PASS")
    check("generate_icon() outputs 22 BMP", Path(_n_gen["files"]["bmp_normal_22"]).exists())
    check("generate_icon() outputs 32 BMP", Path(_n_gen["files"]["bmp_large_32"]).exists())

    # 2. Functional deploy_icon
    _n_fw = _tmp_n_dir / "MyFramework.edu"
    _n_rsc_dir = _n_fw / "CNext" / "resources" / "msgcatalog"
    _n_rsc_dir.mkdir(parents=True)
    _n_rsc_file = _n_rsc_dir / "MyCmdHdr.CATRsc"
    _n_rsc_file.write_text('MyCmdHdr.MyCmd.Icon.Normal = "I_Old";\n', encoding="utf-8")

    _n_dep = deploy_icon("MyCmd", framework_dir=_n_fw, asset_dir=_tmp_n_dir)
    check("deploy_icon() returns SUCCESS", _n_dep["status"] == "SUCCESS")
    check("deploy_icon() normal deployed", Path(_n_dep["deployed_normal"]).exists())
    check("deploy_icon() large deployed", Path(_n_dep["deployed_large"]).exists())

    # 3. CLI cmd_icon invocation
    _cli_rc = cmd_icon(["DateStamp", "--out-dir", str(_tmp_n_dir)])
    check("cmd_icon generate exit code 0", _cli_rc == 0)
    _cli_dep_rc = cmd_icon(["DateStamp", "--deploy", str(_n_fw), "--out-dir", str(_tmp_n_dir)])
    check("cmd_icon deploy exit code 0", _cli_dep_rc == 0)

    # 4. RequirementsClarifier intent routing
    _clar = RequirementsClarifier().analyze("给 CAADateStamp 生成一个高清图标")
    check("RequirementsClarifier domain == icon", _clar.domain == "icon")
    _tr = getattr(_clar, "typed_requirement", None)
    check("RequirementsClarifier recommended_intent_type == GenerateIcon",
          _tr is not None and _tr.recommended_intent_type == "GenerateIcon")

    # 5. Kernel execution with preview
    _kernel = Kernel(workspace_root=str(_tmp_n_dir))
    _k_preview = _kernel.execute(KernelMode.DEVELOP, "为 CAADateStamp 制作图标", preview=True)
    check("Kernel preview status == pending_execution", _k_preview.get("status") == "pending_execution")
    _plan = _k_preview.get("data", {}).get("execute_plan", {})
    check("Kernel preview action == generate_icon", _plan.get("action") == "generate_icon")

    # 6. Kernel execution live
    _k_live = _kernel.execute(KernelMode.DEVELOP, "为 CAADateStamp 制作图标")
    check("Kernel live execution status is successful", str(_k_live.get("status", "")).lower() in ("ok", "pass", "success"), str(_k_live.get("status")))

finally:
    shutil.rmtree(_tmp_n_dir, ignore_errors=True)


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
