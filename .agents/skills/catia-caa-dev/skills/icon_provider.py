"""
CADE Icon Provider v4.0 (Official-Only)
========================================
No in-repo primitive icon library. Every icon is a CATIA official BMP
(runtime-read via the local B28 install, never copied into the repo)
plus the existing corner-badge plate when the command carries a verb.

Pipeline:
  command name -> normalize_command_name() -> IconSemantic
    (operation / object / modifier, confidence EXACT|COMPOUND|LONGEST|FALLBACK)
  -> official_candidate_stem(): exact Pascal stem, alias table for naming
     traps, deny list for CADE-specific semantics
  -> resolve_official_icon(): stem + B28 normal/ exists() -> official BMP
     miss / no CATIA -> DEFAULT_OFFICIAL_STEM (I_P3DefaultIcon)
  -> compose: official BMP as canvas + badge plate (bottom-right)
  -> rasterizer:
       CATIA renderer : 22x22, official pixels kept, 24-bit BMP
       HD renderer    : NEAREST upscale, 24-bit BMP / RGBA PNG

Style (inherited via the official BMPs themselves):
  CATIA gray (192,192,192) background; badge plate = gray plate + navy ink
  border, 10/22 of canvas, flush bottom-right.

Cache keys derive via ICON_HASH (vocab+mapping+renderer source), so any
render-affecting change invalidates automatically.

CLI:
  python icon_provider.py Name1 Name2 ...        semantic audit
  python icon_provider.py --render DIR Name ...  audit + 22px BMP / 64px PNG

100% offline, instant. CATIA install optional (placeholder fallback).
"""

import os, shutil, re
from math import cos, pi, sin
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple
from PIL import Image, ImageDraw

CACHE_DIR = Path.home() / ".cade" / "cache" / "icons"
# NOTE: CACHE_DIR is NOT created at import time — mkdir is deferred to the
# first actual icon write in get_icon(), so importing this module is safe in
# read-only environments (CI runners, test sandboxes).

# ─── Official CATIA icon style (badge plate only; body = official BMP) ───
CATIA_BG = (192, 192, 192)        # dominant official background gray
CATIA_INK = (24, 16, 82)          # dominant official dark-navy outline
CACHE_VER = "v13"                 # salt for ICON_HASH (v13: Official-Only, primitives deleted)

# ─── Object vocabulary (semantic layer) ────────────────────────────
# Pure token set: which tokens are recognized as "objects". No longer maps
# to any in-repo pattern — only feeds official_candidate_stem().
OBJECT_VOCAB = frozenset({
    "hole", "pocket", "contour", "mill", "drill", "machine", "cog", "gear",
    "assemble", "part", "product", "component", "constrain", "pad",
    "extrude", "revolve", "fillet", "chamfer", "sketch", "surface",
    "wireframe", "point", "line", "curve", "split", "trim", "join",
    "transform", "measure", "distance", "angle", "analyze", "check",
    "verify", "report", "statistic", "select", "pick", "dialog", "setting",
    "config", "configure", "option", "view", "zoom", "pan", "save", "open",
    "export", "import", "file", "catalog", "database", "search", "filter",
    "test", "test_tool", "dev", "mirror", "symmetry", "plane", "layer",
    "print", "pattern", "array", "sweep", "loft", "shell", "draft",
    "helix", "spring", "thread", "boolean", "axis", "rotate", "explode",
    "material", "dimension", "circle", "arc", "body", "model", "instance",
    "rename", "update", "refresh", "batch", "process", "wizard", "boss",
    "groove", "slot", "rib", "stiffener", "spiral", "tap", "geometry",
    "feature", "curves", "profile", "sections", "boundary", "mass",
    "thickness", "curvature", "step", "iges", "constraint", "element",
    "properties", "tool", "mode", "numeric", "drawing", "annotation",
    "table", "tolerance", "workbench", "section", "link", "bom", "color",
})


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════

# ─── Verb → Badge (official corner-badge composition) ─────────────
VERB_MAP: Dict[str, str] = {
    "create":"plus","new":"star","add":"plus",
    "delete":"multiply","del":"multiply","remove":"minus","clear":"multiply",
    "edit":"pencil","modify":"pencil",
    "rename":"pencil","update":"refresh",
    "measure":"ruler",
    "check":"check","verify":"check","validate":"check",
    "copy":"copy","duplicate":"copy",
    "import":"import","export":"export",
    "save":"disk","open":"folder",
    "search":"search","find":"search","analyze":"chart","analysis":"chart",
    "view":"eye","show":"eye","preview":"eye",
    "run":"play","execute":"play","launch":"play","start":"play",
    "test":"play","play":"play",
    "lock":"lock","info":"info","help":"question",
    "setting":"settings","config":"settings",
    # Phase A: real CADE command verb coverage (audit 2026-08)
    "apply":"check","extract":"contour","insert":"plus",
    "move":"move","replace":"refresh","unlock":"lock",
    "paste":"copy",
}

_CAMEL = re.compile(r'[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+')

# ─── Name normalization (prefix/suffix only, never global replace) ───
NAME_SUFFIXES = ("command", "cmd", "dlg", "addin", "action", "handler")
NAME_PREFIXES = sorted(
    ("caabom", "caa", "deg", "mmr", "afr", "gvi", "at"),
    key=len, reverse=True)  # longest first: 'caabom' before 'caa'

def normalize_command_name(name: str) -> str:
    """Strip framework suffixes iteratively ('CreateHoleDlgCmd' -> 'CreateHole').
    Strip known CAA/AT project prefixes ('CAADegCreatePointCmd' -> 'CreatePoint').
    Prefixes like CAT are kept — 'CATPart' carries real semantics."""
    out = name
    # Strip known CAA/AT project prefixes (iterative: CAADeg -> Deg -> strip deg)
    for _ in range(3):  # at most 3 levels of nesting
        nl = out.lower()
        stripped = False
        for pre in NAME_PREFIXES:
            if nl.startswith(pre) and len(out) > len(pre) and out[len(pre)].isupper():
                out = out[len(pre):]
                stripped = True
                break
        if not stripped:
            break
    for suf in NAME_SUFFIXES:
        if out.lower().endswith(suf) and len(out) > len(suf):
            out = out[:-len(suf)]
    return out

# ─── Icon Semantic Model ──────────────────────────────────────────
# Canonical operations for audit; badge glyph still comes from VERB_MAP.
OP_GROUPS = {
    "CREATE":  {"create","new","add"},
    "DELETE":  {"delete","del","remove","clear"},
    "EDIT":    {"edit","modify","rename"},
    "UPDATE":  {"update","refresh"},
    "MEASURE": {"measure"},
    "CHECK":   {"check","verify","validate"},
    "COPY":    {"copy","duplicate"},
    "IMPORT":  {"import"}, "EXPORT": {"export"},
    "SAVE":    {"save"},   "OPEN":   {"open"},
    "SEARCH":  {"search","find"},
    "ANALYZE": {"analyze","analysis"},
    "VIEW":    {"view","show","preview"},
    "RUN":     {"run","execute","launch","start","test","play"},
    "LOCK":    {"lock","unlock"}, "INFO": {"info"}, "HELP": {"help"},
    "SETTING": {"setting","config"},
    # Phase A: additional real CADE verb groups
    "APPLY":   {"apply"},
    "EXTRACT": {"extract"},
    "MOVE":    {"move"},
    "REPLACE": {"replace"},
    "INSERT":  {"insert"},
    "PASTE":   {"paste"},
}
_VERB2OP = {v: op for op, vs in OP_GROUPS.items() for v in vs}

# Exact multi-token compounds, checked before single-token fallback
COMPOUND_MAP = {
    "circularpattern": "pattern",
}

# Style spec constants (22px reference canvas)
BADGE_PLATE_RATIO = 10 / 22   # badge plate edge / canvas edge, flush bottom-right

class IconSemantic(NamedTuple):
    operation: Optional[str]   # canonical op from OP_GROUPS, None if absent
    obj: Optional[str]         # OBJECT_VOCAB token, None if unresolved
    modifier: Tuple[str, ...]  # leftover tokens (e.g. 'auto', 'batch')
    base: Optional[str]        # official I_* stem, None when unresolved
    badge: Optional[str]       # final badge glyph
    confidence: str            # EXACT | COMPOUND | LONGEST | FALLBACK
    tokens: Tuple[str, ...]

def _tokenize(name: str) -> List[str]:
    name = normalize_command_name(name)
    toks = []
    for part in re.split(r'[_\-\s]+', name):
        toks += _CAMEL.findall(part)
    return [t.lower() for t in toks if t]

def analyze_command(command_name: str, hint: str = None) -> IconSemantic:
    """Name -> IconSemantic. Four-level resolution:
    EXACT (token hit) -> COMPOUND (fused/multi-token) -> LONGEST (substring,
    longest key first) -> FALLBACK (no object resolved).
    base = official_candidate_stem(obj, modifier) or None."""
    toks = _tokenize(command_name)
    verb = next((t for t in toks if t in VERB_MAP), None)
    operation = _VERB2OP.get(verb) if verb else None

    base_key, confidence = None, None
    if hint and hint.lower() in OBJECT_VOCAB:
        base_key, confidence = hint.lower(), "EXACT"
    if base_key is None:  # Level 1: exact token
        for t in toks:
            if t != verb and t in OBJECT_VOCAB:
                base_key, confidence = t, "EXACT"; break
    if base_key is None:  # Level 2a: multi-token compound
        joined = "".join(toks)
        for comp, pat in COMPOUND_MAP.items():
            if comp in joined:
                base_key, confidence = pat, "COMPOUND"; break
    if base_key is None:  # Level 2b: fused verb+object in one token ('createhole')
        for t in toks:
            for v in VERB_MAP:
                if t.startswith(v) and len(t) > len(v) and t[len(v):] in OBJECT_VOCAB:
                    verb = verb or v
                    operation = operation or _VERB2OP.get(v)
                    base_key = t[len(v):]
                    confidence = "COMPOUND"
                    break
            if base_key: break
    if base_key is None:  # Level 3: longest-key substring (not dict order)
        nl = normalize_command_name(command_name).lower()
        for k in sorted(OBJECT_VOCAB, key=len, reverse=True):
            if k in nl:
                base_key, confidence = k, "LONGEST"; break
    if base_key is None:  # Level 4: unresolved
        confidence = "FALLBACK"

    badge = VERB_MAP.get(verb) if verb else None
    modifier = tuple(t for t in toks if t != verb and t != base_key)
    base = official_candidate_stem(base_key, modifier) if base_key else None
    return IconSemantic(operation, base_key, modifier, base, badge,
                        confidence, tuple(toks))

def resolve_icon_ex(command_name: str, hint: str = None) -> Tuple[Optional[str], Optional[str]]:
    """Back-compat: returns (official stem or None, corner badge).
    'CreateHoleCmd' -> ('I_Hole','plus'); semantic detail via analyze_command()."""
    sem = analyze_command(command_name, hint)
    return sem.base, sem.badge

def resolve_icon(command_name: str, hint: str = None) -> Optional[str]:
    """Back-compat: returns official stem or None (badge dropped)."""
    return resolve_icon_ex(command_name, hint)[0]


# ─── Official Base (runtime lookup, never copied into the repo) ───
# Alias table covers NAMING TRAPS and verified semantic equivalents only.
# Verified 2026-08 via B28 msgcatalog cross-reference (CATRsc -> CATNls).
_OFFICIAL_ALIAS: Dict[str, str] = {
    "sketch": "I_Sketcher",
    "remove": "I_RemoveBody",   # boolean remove; generic I_Remove is a trap
    # Verified semantic equivalents (msgcatalog title cross-checked):
    "rename": "I_RenameFamily",             # CATFileMngtCmdHeader.RenameHdr: "Rename"
    "bom":    "I_DNBBOMtoXML",              # DNBProcCmdHeader: "Export MBOM to XML"
    "color":  "I_AutomaticColorProperty",   # CATGraphicPropertiesToolbar: "Automatic color"
    "properties": "I_Properties",           # CATEditHeader.OpenProperty: "Properties" (5 refs, S5)
    # ── Batch-2A (S6 index, CATNls-title-verified, generic) ──
    "material": "I_ApplyMaterial",        # "Apply Material" (17 refs)
    "pan": "I_Translate",                 # "Pan" — filename search can never find this
    "loft": "I_ICMLoftLT",                # "Loft"
    "search": "I_Find",                   # "Search..."
    "revolve": "I_RevolutionSurface",     # "Revolve..."
    "boolean": "I_CldBoolean",            # "Boolean Operations..."
    "arc": "I_ArcCircle",                 # "Arc"
    "curvature": "I_SurfCurvAna",         # "Surfacic Curvature Analysis"
    "drill": "I_DrillHoles",              # "Drill Holes"
    "transform": "I_SpdTransform",        # "Transform"
    "statistic": "I_CATFmtFollow",        # "Statistics"
    "configure": "I_VPMNavConfigure",     # "Configure"
    "table": "I_DrwTable",                # "Table" (generic; NOT composites PlyTable)
    # ── Batch-2B (S6 index; domain-specific, included per max-inclusion) ──
    "spring": "I_MldSpring",              # "Spring..." (Mold domain)
    "boss": "I_SpdBoss",                  # "Boss" (Mold domain)
    "gear": "I_GearJoint",                # "Gear..." (kinematic joint, not gear part)
    "axis": "I_AxisLine",                 # "Axis..."
    "annotation": "I_Sch_DatumSymbol",    # "Place annotation symbol" (schematic)
    "distance": "I_BandAnalysis",         # "Distance and Band Analysis"
    "setting": "I_DNBVisuSettings",       # "Visualization Settings"
    "mill": "I_MfgEndMillTool",           # "End Mill" (Mfg tool)
    "symmetry": "I_ShapeSymmetry",        # "Symmetry..." (generic shape op; NOT composites)
}
_OFFICIAL_DENY = frozenset({
    # S5-verified (2026-08): proven semantically inequivalent via CATRsc→CATNls.
    "tool",      # candidates all Mfg-domain tooling (I_MfgToolChange "Tool Change")
    "mode",      # candidates all context-specific modes; no generic I_Mode.bmp
    "assemble",  # I_Assemble = geometric join (GSD/Boolean), not asm creation
    "reference", # candidates all ops ("Change Reference..."); no generic I_Reference.bmp
})
# S5 taxonomy cleanup — removed from DENY (exact I_<X>.bmp does not exist,
# so they fall through to DEFAULT_OFFICIAL_STEM; not "proven inequivalent"):
#   numeric         NONE: 6 candidates all orphan, no official semantic anchor
#   feature/element ALIAS-conditional: official icons are Selection/Filter
#                   context (I_SelectFeatureMode / I_ElementType)
#   loft            ALIAS-conditional: I_PositiveLoft (solid) vs
#                   I_LoftOnCurveNetwork (surface) — needs modifier logic
#   axis            ALIAS-conditional: I_AxisLine (GSD wireframe) vs I_3DAxisSystem
#   boss            ALIAS-conditional: I_SpdBoss (Molded Part domain)
_OFFICIAL_WEAK = frozenset({
    # Generic CATIA objects: official I_Part / I_Product exist but only
    # apply when the command is that object itself, not a compound.
    "part", "product", "body", "model", "instance", "geometry",
    "component", "link",
})
_OFFICIAL_NOISE = frozenset({
    "auto", "batch", "all", "new", "my", "the", "and", "or",
    "to", "of", "for", "with", "from",
})

# Default official icon when no semantic match exists. I_P3DefaultIcon is
# the CATIA "default command" glyph — no CADE semantic pollution.
DEFAULT_OFFICIAL_STEM = "I_P3DefaultIcon"


def _official_icons_dir() -> Optional[Path]:
    """Local B28 normal/ from CATIA_INSTALL. None if missing. Never writes."""
    cached = getattr(_official_icons_dir, "_cached", None)
    if cached is not None:
        return cached if cached is not False else None
    result: Optional[Path] = None
    try:
        cfg = Path(__file__).resolve().parent.parent / "config" / "caa_env_config.txt"
        if cfg.is_file():
            install = ""
            for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("CATIA_INSTALL="):
                    install = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
            if install:
                for arch in ("win_b64", "intel_a"):
                    d = Path(install) / arch / "resources" / "graphic" / "icons" / "normal"
                    if d.is_dir():
                        result = d
                        break
    except Exception:
        result = None
    _official_icons_dir._cached = result if result is not None else False
    return result


def official_candidate_stem(obj: Optional[str],
                            modifiers: Tuple[str, ...] = ()) -> Optional[str]:
    """Finite official I_* stem for a semantic object, or None.

    Exact Pascal name only. No glob, no fuzzy search, no 9832-file scan.
    Alias table is for naming traps and verified semantic equivalents.
    """
    if not obj or obj in _OFFICIAL_DENY:
        return None
    mods = tuple(m for m in modifiers if m and m not in _OFFICIAL_NOISE)
    if obj == "pattern":
        if "circular" in modifiers or "circ" in modifiers:
            return "I_CircularPattern"
        if "rectangular" in modifiers or "rect" in modifiers:
            return "I_RectangularPattern"
        return None  # no generic I_Pattern.bmp
    if obj in _OFFICIAL_ALIAS:
        return _OFFICIAL_ALIAS[obj]
    if obj in _OFFICIAL_WEAK and mods:
        return None
    return "I_" + obj[:1].upper() + obj[1:]


def resolve_official_icon(command_name: str, hint: str = None) -> Optional[Path]:
    """Read-only path to a B28 official BMP.

    Resolution order:
      1. analyze_command() -> sem.base (explicit official stem)
      2. DEFAULT_OFFICIAL_STEM (universal fallback — never Primitive)
      3. None only when CATIA is not installed / file truly missing
    """
    sem = analyze_command(command_name, hint)
    d = _official_icons_dir()
    if d is None:
        return None
    stem = sem.base if sem.base else DEFAULT_OFFICIAL_STEM
    path = d / f"{stem}.bmp"
    if path.is_file():
        return path
    # Explicit stem missing on disk -> try default before giving up
    if stem != DEFAULT_OFFICIAL_STEM:
        path = d / f"{DEFAULT_OFFICIAL_STEM}.bmp"
        if path.is_file():
            return path
    return None


def get_icon(icon_name: str, style: str = "geo", size: int = 22,
             format: str = "bmp", alpha: bool = False,
             hint: str = None) -> Optional[Path]:
    """Resolve + render + cache. Always returns the cached path.
    format='bmp' (CATIA runtime) or 'png' (docs/previews; alpha=True for
    transparent background). hint = entity-level domain hint (e.g. the
    Command's category), takes priority over name parsing.
    Official Base: the local B28 I_*.bmp is the canvas and the existing
    badge plate is composited. Falls back to a placeholder only when
    CATIA is not installed (CI/test environments).
    Cache key includes ICON_HASH and the official stem (if any)."""
    base, badge = resolve_icon_ex(icon_name, hint)
    official = resolve_official_icon(icon_name, hint)
    tag = official.stem if official is not None else "noph"
    cache_name = f"{icon_name}+{badge}" if badge else icon_name
    key = (f"{cache_name}_{tag}_{ICON_HASH}_{style}_{size}{'a' if alpha else ''}"
           .replace("/","_").replace(" ","_").replace(":","_"))
    ext = "png" if format == "png" else "bmp"
    cached = CACHE_DIR / f"{key}.{ext}"
    if cached.exists(): return cached
    path = None
    if official is not None:
        try:
            path = _compose_official(official, badge, size=size,
                                     format=format, alpha=alpha)
        except Exception:
            path = None  # corrupt / unreadable official BMP → placeholder
    if path is None:
        path = _render_placeholder(badge, size=size, format=format, alpha=alpha)
    if path:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, cached)
        return cached
    return path

def copy_icons_to_runtime(workspace_path: Path):
    for fw in workspace_path.iterdir():
        if not fw.is_dir() or not fw.name.endswith(".edu"): continue
        rsc_dir = fw / "CNext" / "resources" / "msgcatalog"
        if rsc_dir.exists():
            for rsc in rsc_dir.glob("*.CATRsc"):
                d = workspace_path/"win_b64"/"resources"/"msgcatalog"/rsc.name
                d.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(rsc,d)
        src = fw / "CNext" / "resources" / "graphic" / "icons"
        if src.exists():
            dst = workspace_path/"win_b64"/"resources"/"graphic"/"icons"
            dst.mkdir(parents=True,exist_ok=True)
            for sf in src.rglob("*.bmp"):
                df = dst/sf.relative_to(src); df.parent.mkdir(parents=True,exist_ok=True)
                # Content compare, not mtime (git checkout restores old mtimes)
                if not df.exists() or df.read_bytes() != sf.read_bytes(): shutil.copy2(sf,df)


# ═══════════════════════════════════════════════════════════════════
#  Rendering Pipeline
# ═══════════════════════════════════════════════════════════════════

def _render_badge_plate(badge: str, S: int) -> Image.Image:
    """Official-style corner badge: glyph on gray plate with ink border."""
    plate_sz = round(22 * S * BADGE_PLATE_RATIO)
    plate = Image.new("RGBA", (plate_sz, plate_sz), (*CATIA_BG, 255))
    glyph = Image.new("RGBA", (22*S, 22*S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glyph)
    _draw_icon_4x_rgba(gd, badge, S, (10, 0, 255, 255), (*CATIA_INK, 255),
                       (0, 0, 150, 255), None)
    glyph = glyph.resize((plate_sz - 2*S, plate_sz - 2*S), Image.LANCZOS)
    plate.alpha_composite(glyph, (S, S))
    pd = ImageDraw.Draw(plate)
    pd.rectangle([0, 0, plate_sz-1, plate_sz-1], outline=(*CATIA_INK, 255),
                 width=max(1, S//2))
    return plate


def _rasterize_hd(img_big: Image.Image, size: int, fmt: str, alpha: bool,
                  tmp: Path) -> Path:
    """HD renderer: proportional canvas + LANCZOS; 24-bit BMP or RGBA PNG."""
    img = img_big.resize((size, size), Image.LANCZOS)
    if fmt == "png":
        if not alpha:
            img = img.convert("RGB")
        img.save(tmp, format="PNG")
    else:
        img.convert("RGB").save(tmp, format="BMP")
    return tmp


def _compose_official(official: Path, badge: str = None, size: int = 22,
                      format: str = "bmp", alpha: bool = False) -> Path:
    """Official BMP as canvas + existing badge plate. Never writes the source.

    22px BMP keeps official pixels; only the badge corner is replaced.
    HD / PNG nearest-scales the 22px composite. Gray punch for alpha PNG."""
    src = Image.open(official).convert("RGB")
    if src.size != (22, 22):
        src = src.resize((22, 22), Image.NEAREST)
    hd = size > 22 or format == "png"
    ext = "png" if format == "png" else "bmp"
    tmp = Path(os.environ.get("TEMP", "/tmp")) / \
        f"cade_icon_off_{official.stem}_{badge or 'base'}_{size}_{os.getpid()}.{ext}"
    if not hd:
        # Keep official 22px pixels; only the badge corner is replaced.
        canvas = src.convert("RGBA")
        if badge:
            plate = _render_badge_plate(badge, 8)
            plate_sz = round(22 * BADGE_PLATE_RATIO)
            plate = plate.resize((plate_sz, plate_sz), Image.BOX)
            canvas.alpha_composite(plate, (22 - plate_sz, 22 - plate_sz))
        canvas.convert("RGB").save(tmp, format="BMP")
        return tmp
    S = max(8, round(8 * size / 22))
    big = src.resize((22 * S, 22 * S), Image.NEAREST).convert("RGBA")
    if badge:
        plate = _render_badge_plate(badge, S)
        big.alpha_composite(plate, (big.width - plate.width,
                                    big.height - plate.height))
    img = big.resize((size, size), Image.NEAREST)
    if format == "png":
        if alpha:
            px = img.load()
            for y in range(img.height):
                for x in range(img.width):
                    r, g, b, a = px[x, y]
                    if abs(r - CATIA_BG[0]) < 8 and abs(g - CATIA_BG[1]) < 8 \
                            and abs(b - CATIA_BG[2]) < 8:
                        px[x, y] = (r, g, b, 0)
        else:
            img = img.convert("RGB")
        img.save(tmp, format="PNG")
        return tmp
    img.convert("RGB").save(tmp, format="BMP")
    return tmp


def _render_placeholder(badge: str = None, size: int = 22,
                        format: str = "bmp", alpha: bool = False) -> Path:
    """Gray placeholder + badge plate. Only used when CATIA is not installed
    (CI / test environments). Production always has an official BMP."""
    hd = size > 22 or format == "png"
    S = 8 if not hd else max(8, round(8 * size / 22))
    big_w, big_h = 22*S, 22*S
    bg = (0, 0, 0, 0) if (alpha and format == "png") else (*CATIA_BG, 255)
    img_big = Image.new("RGBA", (big_w, big_h), bg)
    draw_big = ImageDraw.Draw(img_big)
    # Simple centered question-mark diamond to signal "no CATIA"
    c = big_w // 2
    r = 7 * S
    draw_big.polygon([(c, c-r), (c+r, c), (c, c+r), (c-r, c)],
                     fill=(160, 160, 160, 255), outline=(*CATIA_INK, 255))
    if badge:
        plate = _render_badge_plate(badge, S)
        img_big.alpha_composite(plate, (big_w - plate.width, big_h - plate.height))
    ext = "png" if format == "png" else "bmp"
    tmp = Path(os.environ.get("TEMP", "/tmp")) / \
        f"cade_icon_placeholder_{badge or 'base'}_{size}_{os.getpid()}.{ext}"
    if not hd:
        img = img_big.resize((22, 22), Image.BOX).convert("RGB")
        img.save(tmp, format="BMP")
        return tmp
    return _rasterize_hd(img_big, size, format, alpha, tmp)


def _draw_icon_4x_rgba(draw, name, S, BODY, EDGE, DIM, ACCENT, BG=None):
    """23 badge glyphs at 4x on RGBA. BODY/EDGE/DIM/ACCENT = RGBA tuples.
    BG = cutout color: default CATIA gray; transparent in alpha-PNG mode.
    Only badge glyph names are valid (from VERB_MAP values)."""
    W,H=22*S,22*S; c=W//2; B,E,D,AC=BODY,EDGE,DIM,ACCENT
    if BG is None: BG=(*CATIA_BG,255)  # cutout color: shows the gray background through

    def R(xy,**kw):
        if kw.get('outline') and 'width' not in kw: kw['width']=S
        draw.rectangle(xy,**kw)
    def O(xy,**kw):
        if kw.get('outline') and 'width' not in kw: kw['width']=S
        draw.ellipse(xy,**kw)
    def P(pts,**kw):
        o=kw.get('outline')
        if o and 'width' not in kw:
            f=kw.get('fill')
            if f: draw.polygon(pts,fill=f)
            p=list(pts)
            p=p+[p[0],p[1]] if isinstance(p[0],(int,float)) else p+[p[0]]
            draw.line(p,fill=o,width=S,joint='curve')
        else:
            draw.polygon(pts,**kw)
    def L(xy,**kw): draw.line(xy,**kw)
    def AR(xy,s,e,**kw): draw.arc(xy,s,e,**kw)

    def _gear(draw,cx,cy,r,teeth):
        # solid body disc, official style: filled gear with dark ink outline
        O([cx-r-2,cy-r-2,cx+r+2,cy+r+2],fill=B)
        for i in range(teeth):
            a=2*pi*i/teeth; nx=cx+(r+2)*cos(a); ny=cy+(r+2)*sin(a)
            O([nx-3,ny-3,nx+3,ny+3],fill=B)
        O([cx-r-2,cy-r-2,cx+r+2,cy+r+2],outline=E,width=3)
        O([cx-5,cy-5,cx+5,cy+5],fill=E)
        O([cx-3,cy-3,cx+3,cy+3],fill=BG)

    def _star(cx,cy,ir,or_,pts):
        v=[]; [v.append((cx+(or_ if i%2==0 else ir)*cos(-pi/2+pi*i/pts),cy+(or_ if i%2==0 else ir)*sin(-pi/2+pi*i/pts))) for i in range(pts*2)]
        P(v,fill=B); P(v,outline=E)


    _ = {
"plus":      lambda:[R([c-2*S,4*S,c+2*S,17*S],fill=B),R([4*S,c-2*S,17*S,c+2*S],fill=B),R([c-2*S,4*S,c+2*S,17*S],outline=E),R([4*S,c-2*S,17*S,c+2*S],outline=E)],
"minus":     lambda:L([4*S,c,17*S,c],fill=B,width=4*S),
"multiply":  lambda:[L([3*S,3*S,18*S,18*S],fill=B,width=3*S),L([18*S,3*S,3*S,18*S],fill=B,width=3*S)],
"pencil":    lambda:[P([4*S,16*S,13*S,7*S,17*S,11*S,8*S,20*S],fill=B),P([4*S,16*S,13*S,7*S,17*S,11*S,8*S,20*S],outline=E),P([4*S,16*S,8*S,20*S,3*S,21*S],fill=E),L([13*S,7*S,17*S,11*S],fill=D,width=3*S)],
"refresh":   lambda:[AR([2*S,2*S,14*S,14*S],180,450,fill=E,width=3*S),P([13*S,1*S,13*S,6*S,18*S,1*S],fill=E)],
"ruler":     lambda:[R([1*S,2*S,20*S,19*S],outline=E,width=S),L([1*S,6*S,12*S,6*S],fill=D,width=2*S),L([1*S,11*S,16*S,11*S],fill=B,width=2*S),L([1*S,16*S,9*S,16*S],fill=D,width=2*S)],
"check":     lambda:L([2*S,11*S,9*S,18*S,20*S,3*S],fill=E,width=4*S),
"copy":      lambda:[R([6*S,1*S,17*S,12*S],outline=E,width=S),R([1*S,6*S,12*S,17*S],fill=B),R([1*S,6*S,12*S,17*S],outline=E)],
"import":    lambda:[L([19*S,19*S,19*S,3*S,9*S,3*S],fill=E,width=2*S),L([19*S,19*S,9*S,19*S],fill=E,width=2*S),L([2*S,c,13*S,c],fill=B,width=3*S),P([8*S,c-4*S,14*S,c,8*S,c+4*S],fill=B)],
"export":    lambda:[L([3*S,19*S,3*S,3*S,13*S,3*S],fill=E,width=2*S),L([3*S,19*S,13*S,19*S],fill=E,width=2*S),L([8*S,c,15*S,c],fill=B,width=3*S),P([14*S,c-4*S,20*S,c,14*S,c+4*S],fill=B)],
"disk":      lambda:[P([3*S,3*S,15*S,3*S,19*S,7*S,19*S,19*S],fill=B),P([3*S,3*S,15*S,3*S,19*S,7*S,19*S,19*S],outline=E),R([7*S,3*S,14*S,9*S],fill=E),R([11*S,4*S,13*S,8*S],fill=BG),R([7*S,12*S,15*S,19*S],fill=BG),R([7*S,12*S,15*S,19*S],outline=E,width=S)],
"folder":    lambda:[P([1*S,4*S,7*S,4*S,10*S,8*S,20*S,8*S,20*S,19*S,1*S,19*S],fill=B),P([1*S,4*S,7*S,4*S,10*S,8*S,20*S,8*S,20*S,19*S,1*S,19*S],outline=E)],
"search":    lambda:[O([1*S,1*S,14*S,14*S],outline=E,width=2*S),L([12*S,12*S,20*S,20*S],fill=E,width=4*S)],
"chart":     lambda:[L([2*S,19*S,2*S,2*S],fill=D,width=S),L([2*S,19*S,20*S,19*S],fill=D,width=S),R([4*S,11*S,7*S,19*S],fill=B),R([9*S,5*S,12*S,19*S],fill=B),R([14*S,8*S,17*S,19*S],fill=E)],
"eye":       lambda:[O([0,7*S,21*S,14*S],outline=E,width=2*S),O([c-3*S,8*S,c+3*S,13*S],fill=E)],
"play":      lambda:[P([4*S,2*S,4*S,19*S,19*S,c],fill=B),P([4*S,2*S,4*S,19*S,19*S,c],outline=E)],
"lock":      lambda:[AR([4*S,4*S,17*S,12*S],180,0,fill=E,width=3*S),R([5*S,10*S,16*S,20*S],fill=B),R([5*S,10*S,16*S,20*S],outline=E),O([8*S,13*S,13*S,18*S],fill=BG),R([8*S,14*S,13*S,18*S],fill=E)],
"info":      lambda:[O([2*S,2*S,19*S,19*S],outline=E,width=2*S),R([c-1*S,9*S,c+1*S,12*S],fill=B),O([c-1*S,14*S,c+1*S,16*S],fill=B)],
"question":  lambda:[O([2*S,2*S,19*S,19*S],outline=E,width=2*S),AR([6*S,5*S,14*S,11*S],180,0,fill=B,width=2*S),O([c-1*S,13*S,c+1*S,15*S],fill=B)],
"settings":  lambda:_gear(draw,c,c,7*S,10),
"move":      lambda:[L([c,3*S,c,19*S],fill=E,width=2*S),L([3*S,c,19*S,c],fill=E,width=2*S),P([c,1*S,c-3*S,6*S,c+3*S,6*S],fill=B),P([c,21*S,c-3*S,16*S,c+3*S,16*S],fill=B),P([1*S,c,6*S,c-3*S,6*S,c+3*S],fill=B),P([21*S,c,16*S,c-3*S,16*S,c+3*S],fill=B)],
"contour":   lambda:[R([2*S,2*S,19*S,12*S],outline=E,width=2*S),R([6*S,6*S,15*S,19*S],outline=B,width=S)],
"star":      lambda:_star(c,c,4*S,10*S,5),
    }
    if name in _: _[name]()
    # Unknown names render nothing (badge plate stays empty gray)


# ═══════════════════════════════════════════════════════════════════
#  Cache invalidation: ICON_HASH
# ═══════════════════════════════════════════════════════════════════

def _badge_glyph_names() -> frozenset:
    """Badge glyph names = geometry-dispatch entries, extracted via regex."""
    import inspect
    src = inspect.getsource(_draw_icon_4x_rgba)
    return frozenset(re.findall(r'"([a-z][a-z0-9_-]*)"\s*:\s*lambda', src))

BADGE_GLYPHS = _badge_glyph_names()


def _compute_icon_hash() -> str:
    """Hash ONLY what affects pixels: vocab, mapping dicts, badge glyphs,
    badge plate, rasterizers. Unrelated edits elsewhere in this file do
    NOT invalidate the cache."""
    import hashlib, inspect
    parts = [
        CACHE_VER,
        repr(sorted(OBJECT_VOCAB)),
        repr(sorted(VERB_MAP.items())),
        repr(sorted(COMPOUND_MAP.items())),
        repr(sorted(_OFFICIAL_ALIAS.items())),
        repr(sorted(_OFFICIAL_DENY)),
        repr(sorted(_OFFICIAL_WEAK)),
        repr(sorted(_OFFICIAL_NOISE)),
        DEFAULT_OFFICIAL_STEM,
        inspect.getsource(_draw_icon_4x_rgba),
        inspect.getsource(_render_badge_plate),
        inspect.getsource(_compose_official),
        inspect.getsource(_render_placeholder),
        inspect.getsource(official_candidate_stem),
        inspect.getsource(_rasterize_hd),
    ]
    return hashlib.sha1("\x00".join(parts).encode("utf-8")).hexdigest()[:8]

ICON_HASH = _compute_icon_hash()


# ═══════════════════════════════════════════════════════════════════
#  CLI: semantic audit + preview render
# ═══════════════════════════════════════════════════════════════════

def audit(names: List[str], render_dir: Path = None) -> int:
    """Print semantic resolution per name; exit 1 if any FALLBACK."""
    counts = {"EXACT": 0, "COMPOUND": 0, "LONGEST": 0, "FALLBACK": 0}
    for n in names:
        sem = analyze_command(n)
        counts[sem.confidence] += 1
        print(f"{n}")
        print(f"  tokens:     {' / '.join(sem.tokens) or '-'}")
        print(f"  operation:  {sem.operation or '-'}")
        print(f"  object:     {sem.obj or '-'}")
        print(f"  modifier:   {' / '.join(sem.modifier) or '-'}")
        print(f"  base:       {sem.base or '(default)'}")
        print(f"  badge:      {sem.badge or '-'}")
        print(f"  fallback:   {'YES' if sem.confidence == 'FALLBACK' else 'no'}")
        print(f"  confidence: {sem.confidence}")
        official = resolve_official_icon(n)
        print(f"  official:   {official.name if official else '(no CATIA)'}")
        if render_dir:
            render_dir.mkdir(parents=True, exist_ok=True)
            rendered = get_icon(n, size=22, format="bmp")
            if rendered:
                shutil.copy(rendered, render_dir / f"{n}_22.bmp")
            rendered64 = get_icon(n, size=64, format="png", alpha=True)
            if rendered64:
                shutil.copy(rendered64, render_dir / f"{n}_64.png")
    print(f"\n{len(names)} names: "
          + ", ".join(f"{k}={v}" for k, v in counts.items()))
    return 1 if counts["FALLBACK"] else 0


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    render_dir = None
    if "--render" in args:
        i = args.index("--render")
        render_dir = Path(args[i + 1])
        del args[i:i + 2]
    if not args:
        print(__doc__)
        sys.exit(2)
    sys.exit(audit(args, render_dir))
