"""
CADE Icon Provider v3.4
=======================
123 geometric patterns, 4x supersampling, true multi-color RGBA rendering.

Design: draw at 4x on RGBA with explicit colors, LANCZOS scale down,
quantize to 8-bit BMP. Each pattern can use BODY, EDGE, DIM, ACCENT colors.
Style aligned with official CATIA icons (sampled from B28 resources):
BODY=domain color, EDGE=dark navy ink (24,16,82), DIM=dark shade,
background=CATIA gray (192,192,192), no dithering (clean flat pixels).

Composition: verb-object parsing maps commands to (base pattern, corner
badge) — 'CreateHoleCmd' -> drill + plus badge, official style. Large
fills get a halftone checker like official teal-checker fills.

100% offline, instant.
"""

import os, shutil, re
from math import cos, pi, sin
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageDraw

CACHE_DIR = Path.home() / ".cade" / "cache" / "icons"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ─── Official CATIA icon style (sampled from B28 win_b64 resources) ───
CATIA_BG = (192, 192, 192)        # dominant official background gray
CATIA_INK = (24, 16, 82)          # dominant official dark-navy outline
CACHE_VER = "v5"                  # bump when render style changes (v5: 奶油黄主色)

# ─── Domain → Icon ───────────────────────────────────────────────
DOMAIN_MAP = {
    "hole":"drill","pocket":"box","contour":"contour","mill":"cube",
    "drill":"drill","machine":"settings","cog":"settings","gear":"settings",
    "assemble":"cube","part":"cube","product":"package","component":"cube",
    "constrain":"link","pad":"box","extrude":"arrow-up","revolve":"circle",
    "fillet":"arc","chamfer":"cut","sketch":"pencil","surface":"wave",
    "wireframe":"grid","point":"point","line":"line","curve":"curve",
    "split":"cut","trim":"cut","join":"merge","transform":"move",
    "measure":"ruler","distance":"ruler","angle":"angle","analyze":"chart",
    "check":"check","verify":"check","report":"doc","statistic":"chart",
    "select":"cursor","pick":"cursor","dialog":"window","setting":"settings",
    "config":"settings","configure":"settings","option":"chevron","view":"eye",
    "zoom":"magnify","pan":"hand","save":"disk","open":"folder",
    "export":"export","import":"import","file":"doc","catalog":"book",
    "database":"db","search":"search","filter":"funnel","test":"play",
    "test_tool":"play","dev":"code",
    "mirror":"mirror","symmetry":"mirror","plane":"plane","layer":"layer",
    "print":"print","pattern":"pattern","array":"pattern","sweep":"sweep",
    "loft":"loft","shell":"shell","draft":"draft","helix":"helix",
    "spring":"helix","thread":"helix","boolean":"boolean","axis":"axis",
    "rotate":"rotate","explode":"explode","material":"material",
    "dimension":"dimension",
}

# ─── Domain → Color ───────────────────────────────────────────────
# CATIA classic palette — 2026-07 重新从 B28 主流工具图标实证采样
# （I_Pad/I_Pocket/I_Hole/I_Assemble/I_Split/I_Rotate 等 22x22 图标）。
# 关键发现：主流建模/装配工具图标的主体色**不是按域分色**，而是统一的
# 奶油黄 (255,255,150) 主体 + 深蓝轮廓 (24,16,82) + 青蓝系辅助。
# 之前的 _CR/_BL/_TL/_GN/_PU 高饱和"域色"是从冷门工具（ABQ/Mold）误采的，
# 与主流工具风格不一致，已全部修正。
_CREAM = (255, 255, 150)  # 奶油黄主体 —— 主流建模/装配图标的主导色
_TEAL  = (59, 159, 164)   # 柔和青 —— Fillet/Shell 等的辅助面
_SKY   = (91, 169, 208)   # 柔蓝 —— Chamfer 等的辅助面
_CYAN  = (75, 230, 255)   # 亮青 —— Constraint/ThickSurface 的辅助高亮
_GN    = (0, 150, 0)      # 绿 —— measure/check 语义保留（官方 AnalysisMeasure 也有绿色元素）
_YL    = (255, 238, 135)  # 浅黄 —— 文件/保存类
_PU    = (128, 0, 128)    # 紫 —— 交互/设置类（低频，保留）
_MG    = (210, 0, 210)    # 品红 —— test/dev 语义
_OR    = (255, 100, 0)    # 橙 —— flame 等特殊语义

COLOR_MAP: Dict[str, Tuple[int,int,int]] = {
    # 建模类：主体奶油黄（与 I_Pad/I_Pocket/I_Hole/I_Split/I_Rotate 一致）
    "hole":_CREAM,"pocket":_CREAM,"pad":_CREAM,"extrude":_CREAM,
    "revolve":_CREAM,"split":_CREAM,"trim":_CREAM,"rotate":_CREAM,
    "sketch":_CREAM,"point":_CREAM,"line":_CREAM,"curve":_CREAM,
    "plane":_CREAM,"axis":_CREAM,"mirror":_CREAM,"symmetry":_CREAM,
    "pattern":_CREAM,"array":_CREAM,"sweep":_CREAM,"loft":_CREAM,
    "shell":_CREAM,"draft":_CREAM,"boolean":_CREAM,"transform":_CREAM,
    "join":_CREAM,"surface":_CREAM,"wireframe":_CREAM,"reference":_CREAM,
    "helix":_CREAM,"spring":_CREAM,"box":_CREAM,"contour":_CREAM,
    # 圆角/倒角类：青/蓝辅助（与 I_Fillet/I_Chamfer 一致）
    "fillet":_TEAL,"chamfer":_SKY,
    # 装配/约束类：主体奶油黄 + 约束可用亮青高亮（与 I_Assemble/I_*Constraint 一致）
    "assemble":_CREAM,"part":_CREAM,"product":_CREAM,"component":_CREAM,
    "cube":_CREAM,"explode":_CREAM,"package":_CREAM,
    "constrain":_CYAN,"link":_CYAN,
    # 加工/齿轮类：奶油黄（官方 AssyPrtHOLE 等也是奶油黄，非深红）
    "mill":_CREAM,"drill":_CREAM,"machine":_CREAM,"cog":_CREAM,
    "gear":_CREAM,"thread":_CREAM,"cut":_CREAM,
    # 测量/分析类：绿（语义色，官方 AnalysisMeasure 含绿色元素）
    "measure":_GN,"distance":_GN,"angle":_GN,"analyze":_GN,
    "check":_GN,"verify":_GN,"report":_GN,"statistic":_GN,
    "dimension":_GN,"material":_GN,"chart":_GN,
    # 交互/设置类：紫（低频）
    "select":_PU,"pick":_PU,"dialog":_PU,"setting":_PU,
    "config":_PU,"configure":_PU,"option":_PU,"view":_PU,
    "zoom":_PU,"pan":_PU,"cursor":_PU,"window":_PU,
    "eye":_PU,"magnify":_PU,"hand":_PU,"layer":_PU,
    "chevron":_PU,"chat":_PU,
    # 文件/保存/导入导出类：浅黄
    "save":_YL,"open":_YL,"export":_YL,"import":_YL,"file":_YL,
    "catalog":_YL,"database":_YL,"search":_YL,"filter":_YL,
    "print":_YL,"disk":_YL,"folder":_YL,"doc":_YL,"book":_YL,
    "db":_YL,"funnel":_YL,
    # 测试/开发类：品红（语义色）
    "test":_MG,"test_tool":_MG,"dev":_MG,"play":_MG,"code":_MG,
    # 特殊语义图标
    "heart":(155,0,0),"lock":_YL,"plus":_GN,"lightning":_YL,
    "flame":_OR,"trophy":_YL,"pin":(155,0,0),"forward":_GN,
    "target":(255,0,0),"shield":_SKY,"star":_YL,"merge":_CREAM,
    "move":_CREAM,"ruler":_GN,"arc":_TEAL,"circle":_CREAM,
    "pencil":_CREAM,"grid":_CREAM,"wave":_CREAM,"arrow_up":_CREAM,
    "settings":_PU,
    # 命名/编辑/更新类（常用工具动词）
    "rename":_CREAM,"edit":_CREAM,"update":_CREAM,"modify":_CREAM,
    "replace":_CREAM,"delete":_CREAM,"remove":_CREAM,"copy":_CREAM,
    "paste":_CREAM,"undo":_CREAM,"redo":_CREAM,"refresh":_CREAM,
    "apply":_CREAM,"ok":_CREAM,"cancel":_CREAM,"reset":_CREAM,
    "batch":_CREAM,"auto":_CREAM,"wizard":_CREAM,"preview":_CREAM,
}


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════

# ─── Verb → Badge (official corner-badge composition) ─────────────
VERB_MAP: Dict[str, str] = {
    "create":"plus","new":"star","add":"plus",
    "delete":"multiply","del":"multiply","remove":"minus","clear":"multiply",
    "edit":"pencil","modify":"pencil",
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
}

_CAMEL = re.compile(r'[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+')

def _tokenize(name: str) -> List[str]:
    name = re.sub(r'(command|cmd)$', '', name, flags=re.I)
    toks = []
    for part in re.split(r'[_\-\s]+', name):
        toks += _CAMEL.findall(part)
    return [t.lower() for t in toks if t]

def resolve_icon_ex(command_name: str, hint: str = None) -> Tuple[str, Optional[str]]:
    """Verb-object parse: object -> base pattern, verb -> corner badge.

    'CreateHoleCmd' -> ('drill','plus'); 'HoleAnalysisCmd' -> ('drill','chart');
    plain pattern names pass through with badge=None.
    """
    base = DOMAIN_MAP[hint.lower()] if hint and hint.lower() in DOMAIN_MAP else None
    toks = _tokenize(command_name)
    verb = next((t for t in toks if t in VERB_MAP), None)

    if base is None:
        for t in toks:
            if t != verb and t in DOMAIN_MAP:
                base = DOMAIN_MAP[t]; break
    if base is None:
        # fused token like 'createhole' (actions.py passes lowercased names)
        for t in toks:
            for v in VERB_MAP:
                if t.startswith(v) and len(t) > len(v) and t[len(v):] in DOMAIN_MAP:
                    verb = verb or v
                    base = DOMAIN_MAP[t[len(v):]]; break
            if base: break
    if base is None:
        nl = command_name.lower().replace("cmd","").replace("command","")
        for k, v in DOMAIN_MAP.items():
            if k in nl: base = v; break
    if base is None:
        base = command_name.lower().split("_")[0] if "_" in command_name else command_name.lower()

    badge = VERB_MAP.get(verb) if verb else None
    if badge == base:  # 'MeasureDistance' -> ruler+ruler is redundant
        badge = None
    return base, badge

def resolve_icon(command_name: str, hint: str = None) -> str:
    """Back-compat: returns base pattern name (badge dropped)."""
    return resolve_icon_ex(command_name, hint)[0]

def _get_color_for_icon(icon_name: str) -> Tuple[int,int,int]:
    nl = icon_name.lower().replace("-","_").replace(" ","_")
    if nl in COLOR_MAP: return COLOR_MAP[nl]
    for k,c in COLOR_MAP.items():
        if k in nl: return c
    for dk,di in DOMAIN_MAP.items():
        if di==nl and dk in COLOR_MAP: return COLOR_MAP[dk]
    return (10, 0, 255)  # CATIA accent blue for unmapped icons (never ~bg gray)

def get_icon(icon_name: str, style: str = "geo") -> Optional[Path]:
    base, badge = resolve_icon_ex(icon_name)
    cache_name = f"{icon_name}+{badge}" if badge else icon_name
    key = f"{cache_name}_{CACHE_VER}_{style}".replace("/","_").replace(" ","_").replace(":","_")
    cached = CACHE_DIR / f"{key}.bmp"
    if cached.exists(): return cached
    path = _render_icon(base, badge)
    if path: shutil.copy(path, cached)
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
    plate_sz = 10*S
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


def _apply_checker(img: Image.Image, body_rgb: Tuple[int,int,int]) -> Image.Image:
    """Official-style halftone: lighten every other pixel on large body
    fills. Applied at 22x22 for a crisp 1px checker."""
    px = img.load()
    W, H = img.size
    count = 0
    for y in range(H):
        for x in range(W):
            if px[x, y] == body_rgb:
                count += 1
    if count < W*H//5:  # small fills stay flat
        return img
    light = tuple(min(255, int(c + (255 - c) * 0.45)) for c in body_rgb)
    for y in range(H):
        for x in range(W):
            if px[x, y] == body_rgb and ((x + y) & 1) == 0:
                px[x, y] = light
    return img


def _render_icon(icon_name: str, badge: str = None) -> Path:
    """Render to 22x22 8-bit BMP, official CATIA style: gray bg, navy ink, no dither."""
    color = _get_color_for_icon(icon_name)
    r,g,b = color
    S = 4
    big_w,big_h = 22*S,22*S

    # Build color palette for this icon
    body = (r, g, b, 255)
    edge = (*CATIA_INK, 255)
    dim  = (r//2, g//2, b//2, 255)

    # Some patterns get accent colors (for multi-color effect)
    accent = None
    acmap = {
        "flame": (255, 200, 0, 255),
        "lightning": (255, 255, 0, 255),
        "sun": (255, 200, 0, 255),
        "trophy": (255, 200, 0, 255),
        "warning": (255, 200, 0, 255),
        "star": (255, 200, 0, 255),
        "heart": (255, 100, 100, 255),
        "target": (255, 0, 0, 255),
    }
    if icon_name in acmap:
        accent = acmap[icon_name]

    # Draw on official CATIA gray background
    img_big = Image.new("RGBA", (big_w, big_h), (*CATIA_BG, 255))
    draw_big = ImageDraw.Draw(img_big)
    _draw_icon_4x_rgba(draw_big, icon_name, S, body, edge, dim, accent)

    # Corner badge composition (official verb-badge style)
    if badge:
        plate = _render_badge_plate(badge, S)
        img_big.alpha_composite(plate, (big_w - plate.width, big_h - plate.height))

    # Scale down, flatten to RGB, halftone large fills, quantize w/o dither
    img = img_big.resize((22, 22), Image.LANCZOS).convert("RGB")
    img = _apply_checker(img, (r, g, b))
    img_p = img.quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)

    tmp = Path(os.environ.get("TEMP", "/tmp")) / f"cade_icon_{icon_name}.bmp"
    img_p.save(tmp, format="BMP")
    return tmp


def _draw_icon_4x_rgba(draw, name, S, BODY, EDGE, DIM, ACCENT):
    """107 patterns at 4x on RGBA. BODY/EDGE/DIM/ACCENT = RGBA tuples."""
    W,H=22*S,22*S; c=W//2; B,E,D,AC=BODY,EDGE,DIM,ACCENT
    BG=(*CATIA_BG,255)  # cutout color: shows the gray background through

    def R(xy,**kw): draw.rectangle(xy,**kw)
    def O(xy,**kw): draw.ellipse(xy,**kw)
    def P(pts,**kw): draw.polygon(pts,**kw)
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

    def _cube():
        R([4*S,6*S,15*S,17*S],outline=E,width=2*S)
        P([4*S,6*S,9*S,1*S,19*S,1*S,14*S,6*S],outline=E,fill=B)
        P([14*S,6*S,19*S,1*S,19*S,11*S,14*S,17*S],outline=E,fill=D)

    def _star(cx,cy,ir,or_,pts):
        v=[]; [v.append((cx+(or_ if i%2==0 else ir)*cos(-pi/2+pi*i/pts),cy+(or_ if i%2==0 else ir)*sin(-pi/2+pi*i/pts))) for i in range(pts*2)]
        P(v,fill=B); P(v,outline=E)

    def _bez(x0,y0,cx,cy,x1,y1):
        pts=[(u**2*x0+2*u*t*cx+t**2*x1,u**2*y0+2*u*t*cy+t**2*y1) for i in range(13) for t,u in [(i/12.0,1-i/12.0)]]
        [L([pts[i],pts[i+1]],fill=E,width=3*S) for i in range(len(pts)-1)]

    def _ngon(cx,cy,r,n):
        pts=[(cx+r*cos(-pi/2+2*pi*i/n),cy+r*sin(-pi/2+2*pi*i/n)) for i in range(n)]
        P(pts,fill=B); P(pts,outline=E)

    def _sun_rays():
        for a in [i*pi/4 for i in range(8)]:
            L([c+7*S*cos(a),c+7*S*sin(a),c+10*S*cos(a),c+10*S*sin(a)],fill=E,width=2*S)

    _ = {
"box":       lambda:[P([3*S,19*S,3*S,5*S,19*S,5*S,19*S,19*S],fill=B),P([3*S,19*S,3*S,5*S,19*S,5*S,19*S,19*S],outline=E),R([8*S,5*S,14*S,13*S],fill=BG),L([8*S,5*S,8*S,13*S],fill=E,width=S),L([14*S,5*S,14*S,13*S],fill=E,width=S),L([8*S,13*S,14*S,13*S],fill=E,width=S)],
"circle":    lambda:O([1*S,1*S,20*S,20*S],fill=B),
"point":     lambda:[O([c-6*S,c-6*S,c+6*S,c+6*S],fill=B),O([c-6*S,c-6*S,c+6*S,c+6*S],outline=E,width=S),O([c-2*S,c-2*S,c+2*S,c+2*S],fill=E)],
"line":      lambda:L([2*S,c,19*S,c],fill=E,width=4*S),
"arc":       lambda:AR([1*S,1*S,20*S,20*S],180,360,fill=E,width=4*S),
"wave":      lambda:[L([(1*S+i*18*S//16,c+int(5*S*sin(i*pi/8))) for i in range(17)],fill=B,width=3*S),L([(1*S+i*18*S//16,c+6*S+int(3*S*sin(i*pi/8))) for i in range(17)],fill=D,width=2*S)],
"grid":      lambda:[L([3*S,8*S,18*S,8*S],fill=D,width=S),L([3*S,14*S,18*S,14*S],fill=D,width=S),L([8*S,3*S,8*S,18*S],fill=D,width=S),L([14*S,3*S,14*S,18*S],fill=D,width=S)],
"play":      lambda:[P([4*S,2*S,4*S,19*S,19*S,c],fill=B),P([4*S,2*S,4*S,19*S,19*S,c],outline=E)],
"drill":     lambda:[R([c-4*S,2*S,c+4*S,14*S],fill=B),P([c-4*S,14*S,c+4*S,14*S,c,20*S],fill=B),R([c-4*S,2*S,c+4*S,14*S],outline=E),P([c-4*S,14*S,c+4*S,14*S,c,20*S],outline=E),L([c-2*S,3*S,c+2*S,9*S],fill=E,width=S),L([c+2*S,6*S,c-2*S,12*S],fill=E,width=S)],
"cut":       lambda:[P([3*S,3*S,15*S,3*S,19*S,7*S,19*S,19*S,3*S,19*S],fill=B),P([3*S,3*S,15*S,3*S,19*S,7*S,19*S,19*S,3*S,19*S],outline=E),L([15*S,3*S,19*S,7*S],fill=D,width=2*S)],
"cursor":    lambda:P([1*S,1*S,1*S,17*S,8*S,12*S,13*S,19*S,16*S,15*S,10*S,10*S,16*S,6*S],fill=B),
"move":      lambda:[L([c,3*S,c,19*S],fill=E,width=2*S),L([3*S,c,19*S,c],fill=E,width=2*S),P([c,1*S,c-3*S,6*S,c+3*S,6*S],fill=B),P([c,21*S,c-3*S,16*S,c+3*S,16*S],fill=B),P([1*S,c,6*S,c-3*S,6*S,c+3*S],fill=B),P([21*S,c,16*S,c-3*S,16*S,c+3*S],fill=B)],
"merge":     lambda:[L([3*S,3*S,c,13*S],fill=E,width=3*S),L([18*S,3*S,c,13*S],fill=E,width=3*S),L([c,13*S,c,19*S],fill=E,width=3*S)],
"settings":  lambda:_gear(draw,c,c,7*S,10),
"search":    lambda:[O([1*S,1*S,14*S,14*S],outline=E,width=2*S),L([12*S,12*S,20*S,20*S],fill=E,width=4*S)],
"pencil":    lambda:[P([4*S,16*S,13*S,7*S,17*S,11*S,8*S,20*S],fill=B),P([4*S,16*S,13*S,7*S,17*S,11*S,8*S,20*S],outline=E),P([4*S,16*S,8*S,20*S,3*S,21*S],fill=E),L([13*S,7*S,17*S,11*S],fill=D,width=3*S)],
"ruler":     lambda:[R([1*S,2*S,20*S,19*S],outline=E,width=S),L([1*S,6*S,12*S,6*S],fill=D,width=2*S),L([1*S,11*S,16*S,11*S],fill=B,width=2*S),L([1*S,16*S,9*S,16*S],fill=D,width=2*S)],
"magnify":   lambda:[O([0,0,15*S,15*S],outline=E,width=2*S),L([13*S,13*S,21*S,21*S],fill=E,width=4*S)],
"funnel":    lambda:[P([1*S,2*S,20*S,2*S,15*S,c,6*S,c],fill=B),P([1*S,2*S,20*S,2*S,15*S,c,6*S,c],outline=E)],
"window":    lambda:[R([1*S,1*S,20*S,20*S],outline=E,width=2*S),R([1*S,1*S,20*S,7*S],fill=E)],
"eye":       lambda:[O([0,7*S,21*S,14*S],outline=E,width=2*S),O([c-3*S,8*S,c+3*S,13*S],fill=E)],
"hand":      lambda:[draw.rounded_rectangle([4*S,8*S,18*S,19*S],radius=3*S,fill=B,outline=E,width=S),draw.rounded_rectangle([6*S,3*S,9*S,10*S],radius=S,fill=B,outline=E,width=S),draw.rounded_rectangle([10*S,2*S,13*S,10*S],radius=S,fill=B,outline=E,width=S),draw.rounded_rectangle([14*S,4*S,17*S,10*S],radius=S,fill=B,outline=E,width=S)],
"chevron":   lambda:[L([4*S,6*S,c,13*S,18*S,6*S],fill=E,width=3*S),L([4*S,11*S,c,18*S,18*S,11*S],fill=B,width=3*S)],
"doc":       lambda:[R([3*S,1*S,18*S,20*S],outline=E,width=2*S),L([6*S,5*S,15*S,5*S],fill=D,width=S),L([6*S,8*S,15*S,8*S],fill=B,width=2*S),L([6*S,12*S,13*S,12*S],fill=D,width=S)],
"folder":    lambda:[P([1*S,4*S,7*S,4*S,10*S,8*S,20*S,8*S,20*S,19*S,1*S,19*S],fill=B),P([1*S,4*S,7*S,4*S,10*S,8*S,20*S,8*S,20*S,19*S,1*S,19*S],outline=E)],
"disk":      lambda:[P([3*S,3*S,15*S,3*S,19*S,7*S,19*S,19*S,3*S,19*S],fill=B),P([3*S,3*S,15*S,3*S,19*S,7*S,19*S,19*S,3*S,19*S],outline=E),R([7*S,3*S,14*S,9*S],fill=E),R([11*S,4*S,13*S,8*S],fill=BG),R([7*S,12*S,15*S,19*S],fill=BG),R([7*S,12*S,15*S,19*S],outline=E,width=S)],
"export":    lambda:[L([3*S,19*S,3*S,3*S,13*S,3*S],fill=E,width=2*S),L([3*S,19*S,13*S,19*S],fill=E,width=2*S),L([8*S,c,15*S,c],fill=B,width=3*S),P([14*S,c-4*S,20*S,c,14*S,c+4*S],fill=B)],
"import":    lambda:[L([19*S,19*S,19*S,3*S,9*S,3*S],fill=E,width=2*S),L([19*S,19*S,9*S,19*S],fill=E,width=2*S),L([2*S,c,13*S,c],fill=B,width=3*S),P([8*S,c-4*S,14*S,c,8*S,c+4*S],fill=B)],
"book":      lambda:[R([2*S,1*S,11*S,20*S],outline=E,width=2*S),R([10*S,1*S,19*S,20*S],outline=E,width=2*S),L([10*S,1*S,10*S,20*S],fill=E,width=2*S)],
"db":        lambda:[O([3*S,15*S,18*S,20*S],outline=D,width=S),O([3*S,9*S,18*S,14*S],outline=B,width=2*S),O([3*S,2*S,18*S,7*S],outline=E,width=2*S),L([3*S,4*S,3*S,12*S],fill=D,width=2*S),L([18*S,4*S,18*S,12*S],fill=D,width=2*S)],
"check":     lambda:L([2*S,11*S,9*S,18*S,20*S,3*S],fill=E,width=4*S),
"angle":     lambda:[L([2*S,19*S,2*S,4*S],fill=E,width=3*S),L([2*S,19*S,17*S,19*S],fill=E,width=3*S),AR([2*S,9*S,11*S,18*S],0,-90,fill=D,width=2*S)],
"chart":     lambda:[L([2*S,19*S,2*S,2*S],fill=D,width=S),L([2*S,19*S,20*S,19*S],fill=D,width=S),R([4*S,11*S,7*S,19*S],fill=B),R([9*S,5*S,12*S,19*S],fill=B),R([14*S,8*S,17*S,19*S],fill=E)],
"code":      lambda:[L([8*S,5*S,3*S,c],fill=E,width=2*S),L([3*S,c,8*S,17*S],fill=E,width=2*S),L([14*S,5*S,19*S,c],fill=E,width=2*S),L([19*S,c,14*S,17*S],fill=E,width=2*S),L([13*S,3*S,9*S,19*S],fill=B,width=2*S)],
"link":      lambda:[AR([1*S,2*S,14*S,15*S],-200,20,fill=E,width=3*S),AR([7*S,8*S,20*S,21*S],-200,20,fill=E,width=3*S)],
"cube":      lambda:_cube(),
"contour":   lambda:[R([2*S,2*S,19*S,12*S],outline=E,width=2*S),R([6*S,6*S,15*S,19*S],outline=B,width=S)],
"package":   lambda:[R([2*S,6*S,19*S,19*S],outline=B,width=2*S),P([9*S,1*S,6*S,6*S,15*S,6*S,12*S,1*S],fill=B),P([9*S,1*S,6*S,6*S,15*S,6*S,12*S,1*S],outline=E)],
"arrow-up":  lambda:[P([c,1*S,2*S,12*S,7*S,12*S,7*S,20*S,14*S,20*S,14*S,12*S,19*S,12*S],fill=B),P([c,1*S,2*S,12*S,7*S,12*S,7*S,20*S,14*S,20*S,14*S,12*S,19*S,12*S],outline=E)],
"curve":     lambda:_bez(2*S,19*S,c,2*S,19*S,19*S),
"star":      lambda:_star(c,c,4*S,10*S,5),
"heart":     lambda:[O([3*S,2*S,10*S,9*S],fill=B),O([11*S,2*S,18*S,9*S],fill=B),P([3*S,6*S,18*S,6*S,c,19*S],fill=B),O([3*S,2*S,10*S,9*S],outline=E),O([11*S,2*S,18*S,9*S],outline=E),P([3*S,6*S,18*S,6*S,c,19*S],outline=E)],
"lock":      lambda:[AR([4*S,4*S,17*S,12*S],180,0,fill=E,width=3*S),R([5*S,10*S,16*S,20*S],fill=B),R([5*S,10*S,16*S,20*S],outline=E),O([8*S,13*S,13*S,18*S],fill=BG),R([8*S,14*S,13*S,18*S],fill=E)],
"plus":      lambda:[R([c-2*S,4*S,c+2*S,17*S],fill=B),R([4*S,c-2*S,17*S,c+2*S],fill=B),R([c-2*S,4*S,c+2*S,17*S],outline=E),R([4*S,c-2*S,17*S,c+2*S],outline=E)],
"triangle":  lambda:P([c,1*S,1*S,20*S,20*S,20*S],fill=B),
"diamond":   lambda:P([(c,1*S),(20*S,c),(c,20*S),(1*S,c)],fill=B),
"hexagon":   lambda:_ngon(c,c,9*S,6),
"pentagon":  lambda:_ngon(c,c,9*S,5),
"octagon":   lambda:_ngon(c,c,9*S,8),
"cross":     lambda:[L([c,2*S,c,19*S],fill=B,width=4*S),L([2*S,c,19*S,c],fill=B,width=4*S)],
"slash":     lambda:L([3*S,2*S,18*S,19*S],fill=E,width=3*S),
"dots":      lambda:[O([c-2*S,c-2*S,c+2*S,c+2*S],fill=E),O([c-2*S,3*S,c+2*S,7*S],fill=B),O([c-2*S,14*S,c+2*S,18*S],fill=B)],
"ring":      lambda:O([2*S,2*S,19*S,19*S],outline=E,width=3*S),
"target":    lambda:[O([2*S,2*S,19*S,19*S],outline=E,width=S),O([6*S,6*S,15*S,15*S],outline=B,width=S),O([c-2*S,c-2*S,c+2*S,c+2*S],fill=E)],
"arrow-down":lambda:[P([c,20*S,2*S,9*S,7*S,9*S,7*S,1*S,14*S,1*S,14*S,9*S,19*S,9*S],fill=B),P([c,20*S,2*S,9*S,7*S,9*S,7*S,1*S,14*S,1*S,14*S,9*S,19*S,9*S],outline=E)],
"arrow-left":lambda:[P([1*S,c,12*S,2*S,12*S,7*S,20*S,7*S,20*S,14*S,12*S,14*S,12*S,19*S],fill=B),P([1*S,c,12*S,2*S,12*S,7*S,20*S,7*S,20*S,14*S,12*S,14*S,12*S,19*S],outline=E)],
"arrow-right":lambda:[P([20*S,c,9*S,2*S,9*S,7*S,1*S,7*S,1*S,14*S,9*S,14*S,9*S,19*S],fill=B),P([20*S,c,9*S,2*S,9*S,7*S,1*S,7*S,1*S,14*S,9*S,14*S,9*S,19*S],outline=E)],
"refresh":   lambda:[AR([2*S,2*S,14*S,14*S],180,450,fill=E,width=3*S),P([13*S,1*S,13*S,6*S,18*S,1*S],fill=E)],
"chevron-down":lambda:P([2*S,7*S,c,15*S,19*S,7*S],fill=B),
"chevron-up":lambda:P([2*S,14*S,c,6*S,19*S,14*S],fill=B),
"pause":     lambda:[R([5*S,2*S,9*S,19*S],fill=B),R([12*S,2*S,16*S,19*S],fill=B)],
"stop":      lambda:R([3*S,3*S,18*S,18*S],fill=B),
"forward":   lambda:[P([4*S,2*S,4*S,19*S,14*S,c],fill=B),P([14*S,2*S,14*S,19*S,20*S,c],fill=B)],
"backward":  lambda:[P([17*S,2*S,17*S,19*S,7*S,c],fill=B),P([7*S,2*S,7*S,19*S,1*S,c],fill=B)],
"key":       lambda:[O([c-2*S,c-2*S,c+2*S,c+2*S],fill=E),L([c,c,18*S,5*S],fill=B,width=3*S),L([13*S,7*S,19*S,4*S],fill=B,width=2*S)],
"bell":      lambda:[P([c,1*S,2*S,8*S,2*S,14*S,19*S,14*S,19*S,8*S],fill=B),R([8*S,14*S,13*S,17*S],fill=B),O([9*S,17*S,12*S,20*S],fill=D)],
"tag":       lambda:[P([2*S,2*S,18*S,2*S,18*S,12*S,c,19*S,2*S,12*S],fill=B),O([c-3*S,c-3*S,c+3*S,c+3*S],fill=BG)],
"pin":       lambda:[O([5*S,1*S,16*S,12*S],fill=B),P([8*S,10*S,13*S,10*S,c,20*S],fill=B)],
"flag":      lambda:[L([3*S,1*S,3*S,20*S],fill=E,width=2*S),P([3*S,1*S,18*S,4*S,3*S,8*S],fill=B)],
"trophy":    lambda:[AR([2*S,2*S,9*S,9*S],180,0,fill=B,width=3*S),AR([12*S,2*S,19*S,9*S],180,0,fill=B,width=3*S),R([5*S,7*S,16*S,15*S],fill=B),R([7*S,15*S,14*S,20*S],fill=B)],
"shield":    lambda:[P([c,1*S,19*S,5*S,19*S,14*S,c,20*S,2*S,14*S,2*S,5*S],fill=B),P([c,1*S,19*S,5*S,19*S,14*S,c,20*S,2*S,14*S,2*S,5*S],outline=E)],
"clock":     lambda:[O([2*S,2*S,19*S,19*S],outline=E,width=2*S),L([c,c,c,6*S],fill=E,width=2*S),L([c,c,14*S,c],fill=B,width=2*S)],
"delete":    lambda:[R([4*S,5*S,17*S,18*S],fill=B),R([2*S,1*S,19*S,5*S],fill=E),R([7*S,0,14*S,1*S],fill=E)],
"copy":      lambda:[R([6*S,1*S,17*S,12*S],outline=E,width=S),R([1*S,6*S,12*S,17*S],fill=B),R([1*S,6*S,12*S,17*S],outline=E)],
"paste":     lambda:[R([5*S,2*S,12*S,9*S],fill=B),R([3*S,6*S,18*S,19*S],outline=E,width=2*S)],
"undo":      lambda:[AR([2*S,4*S,14*S,17*S],90,270,fill=E,width=3*S),P([3*S,19*S,8*S,17*S,3*S,14*S],fill=E)],
"redo":      lambda:[AR([7*S,4*S,19*S,17*S],270,90,fill=E,width=3*S),P([18*S,19*S,13*S,17*S,18*S,14*S],fill=E)],
"zoom-in":   lambda:[O([1*S,1*S,14*S,14*S],outline=E,width=2*S),L([12*S,12*S,20*S,20*S],fill=E,width=3*S),L([4*S,c,10*S,c],fill=D,width=S),L([c,4*S,c,10*S],fill=D,width=S)],
"zoom-out":  lambda:[O([1*S,1*S,14*S,14*S],outline=E,width=2*S),L([12*S,12*S,20*S,20*S],fill=E,width=3*S),L([4*S,c,10*S,c],fill=D,width=S)],
"mail":      lambda:[R([2*S,4*S,19*S,17*S],outline=E,width=S),P([2*S,4*S,c,10*S,19*S,4*S],fill=B)],
"chat":      lambda:[O([4*S,2*S,17*S,12*S],fill=B),P([6*S,10*S,10*S,19*S,14*S,13*S],fill=B)],
"phone":     lambda:[R([6*S,3*S,15*S,18*S],outline=E,width=2*S),O([8*S,5*S,13*S,10*S],outline=D,width=S)],
"share":     lambda:[O([7*S,1*S,14*S,8*S],fill=B),O([1*S,9*S,8*S,16*S],fill=B),O([13*S,9*S,20*S,16*S],fill=B),L([c,6*S,4*S,11*S],fill=E,width=S),L([c,6*S,17*S,11*S],fill=E,width=S)],
"wifi":      lambda:[AR([c-8*S,10*S,c+8*S,c],180,0,fill=E,width=2*S),AR([c-5*S,6*S,c+5*S,c-4*S],180,0,fill=B,width=2*S),AR([c-2*S,2*S,c+2*S,c-8*S],180,0,fill=D,width=2*S),O([c-1*S,c+4*S,c+1*S,c+6*S],fill=E)],
"minus":     lambda:L([4*S,c,17*S,c],fill=B,width=4*S),
"multiply":  lambda:[L([3*S,3*S,18*S,18*S],fill=B,width=3*S),L([18*S,3*S,3*S,18*S],fill=B,width=3*S)],
"divide":    lambda:[O([c-3*S,2*S,c+3*S,7*S],fill=B),L([4*S,c,17*S,c],fill=E,width=2*S),O([c-3*S,13*S,c+3*S,18*S],fill=B)],
"equal":     lambda:[L([4*S,7*S,17*S,7*S],fill=E,width=3*S),L([4*S,13*S,17*S,13*S],fill=E,width=3*S)],
"percent":   lambda:[O([2*S,2*S,8*S,8*S],fill=B),L([15*S,3*S,8*S,18*S],fill=E,width=2*S),O([11*S,13*S,17*S,19*S],fill=B)],
"sun":       lambda:[O([5*S,5*S,16*S,16*S],fill=B),_sun_rays()],
"moon":      lambda:[O([5*S,2*S,16*S,19*S],fill=B),O([9*S,3*S,20*S,18*S],fill=BG)],
"cloud":     lambda:[O([2*S,8*S,12*S,15*S],fill=B),O([8*S,4*S,18*S,11*S],fill=B),O([2*S,13*S,19*S,20*S],fill=B)],
"lightning": lambda:P([c,1*S,7*S,11*S,8*S,11*S,3*S,18*S,14*S,9*S,12*S,9*S,18*S,1*S],fill=E),
"flame":     lambda:[O([4*S,10*S,17*S,20*S],fill=B),P([c,2*S,4*S,12*S,7*S,10*S],fill=B),P([c,2*S,14*S,10*S,17*S,12*S],fill=B)],
"home":      lambda:[P([c,1*S,1*S,9*S,20*S,9*S],fill=B),R([3*S,9*S,18*S,20*S],outline=E,width=S),R([7*S,12*S,14*S,20*S],outline=D,width=S)],
"user":      lambda:[O([c-4*S,1*S,c+4*S,9*S],fill=E),AR([2*S,8*S,19*S,20*S],180,360,fill=B,width=5*S)],
"calendar":  lambda:[R([2*S,3*S,19*S,19*S],outline=E,width=S),R([2*S,3*S,19*S,7*S],fill=B),L([5*S,1*S,5*S,5*S],fill=E,width=2*S),L([16*S,1*S,16*S,5*S],fill=E,width=2*S),L([5*S,10*S,12*S,10*S],fill=D,width=S),L([5*S,13*S,8*S,13*S],fill=D,width=S)],
"camera":    lambda:[R([2*S,5*S,19*S,17*S],outline=E,width=2*S),R([7*S,1*S,14*S,5*S],fill=B),O([6*S,8*S,15*S,14*S],outline=D)],
"map":       lambda:[P([2*S,2*S,14*S,2*S,14*S,14*S,2*S,14*S],fill=B),P([14*S,14*S,7*S,14*S,7*S,19*S,14*S,19*S],fill=B),P([2*S,2*S,14*S,2*S,14*S,14*S,2*S,14*S],outline=E)],
"battery":   lambda:[R([2*S,5*S,16*S,15*S],outline=E,width=S),R([17*S,7*S,19*S,13*S],fill=E),R([4*S,7*S,9*S,13*S],fill=B),R([10*S,7*S,14*S,13*S],fill=D)],
"download":  lambda:[P([c,19*S,4*S,11*S,10*S,11*S],fill=B),R([7*S,2*S,14*S,11*S],fill=B),P([c,19*S,4*S,11*S,10*S,11*S],outline=E),R([7*S,2*S,14*S,11*S],outline=E)],
"upload":    lambda:[P([c,2*S,4*S,10*S,10*S,10*S],fill=B),R([7*S,10*S,14*S,19*S],fill=B),P([c,2*S,4*S,10*S,10*S,10*S],outline=E),R([7*S,10*S,14*S,19*S],outline=E)],
"power":     lambda:[AR([2*S,2*S,19*S,19*S],225,315,fill=E,width=3*S),L([c,2*S,c,10*S],fill=E,width=2*S)],
"info":      lambda:[O([2*S,2*S,19*S,19*S],outline=E,width=2*S),R([c-1*S,9*S,c+1*S,12*S],fill=B),O([c-1*S,14*S,c+1*S,16*S],fill=B)],
"warning":   lambda:[P([c,1*S,1*S,17*S,20*S,17*S],fill=B),P([c,1*S,1*S,17*S,20*S,17*S],outline=E),R([c-1*S,7*S,c+1*S,11*S],fill=E),O([c-1*S,12*S,c+1*S,14*S],fill=E)],
"question":  lambda:[O([2*S,2*S,19*S,19*S],outline=E,width=2*S),AR([6*S,5*S,14*S,11*S],180,0,fill=B,width=2*S),O([c-1*S,13*S,c+1*S,15*S],fill=B)],
"globe":     lambda:[O([2*S,2*S,19*S,19*S],outline=E,width=2*S),O([c-1*S,2*S,c+1*S,19*S],fill=D),L([2*S,c,19*S,c],fill=D,width=S)],
"mirror":    lambda:[P([3*S,4*S,9*S,c,3*S,18*S],fill=B),P([3*S,4*S,9*S,c,3*S,18*S],outline=E),P([19*S,4*S,13*S,c,19*S,18*S],outline=E),L([c,2*S,c,20*S],fill=D,width=S)],
"plane":     lambda:[P([2*S,16*S,8*S,8*S,20*S,8*S,14*S,16*S],fill=B),P([2*S,16*S,8*S,8*S,20*S,8*S,14*S,16*S],outline=E),L([c,8*S,c,2*S],fill=E,width=2*S),P([c,1*S,c-2*S,5*S,c+2*S,5*S],fill=E)],
"layer":     lambda:[P([2*S,6*S,c,2*S,20*S,6*S,c,10*S],fill=B),P([2*S,6*S,c,2*S,20*S,6*S,c,10*S],outline=E),P([2*S,11*S,c,7*S,20*S,11*S,c,15*S],fill=D),P([2*S,11*S,c,7*S,20*S,11*S,c,15*S],outline=E),P([2*S,16*S,c,12*S,20*S,16*S,c,20*S],fill=B),P([2*S,16*S,c,12*S,20*S,16*S,c,20*S],outline=E)],
"print":     lambda:[R([6*S,2*S,16*S,8*S],fill=BG,outline=E,width=S),R([3*S,8*S,19*S,15*S],fill=B),R([3*S,8*S,19*S,15*S],outline=E),R([6*S,13*S,16*S,20*S],fill=BG,outline=E,width=S),L([8*S,16*S,14*S,16*S],fill=D,width=S),L([8*S,18*S,14*S,18*S],fill=D,width=S)],
"pattern":   lambda:[R([x*S,y*S,x*S+5*S,y*S+5*S],fill=B,outline=E) for y in (2,9,16) for x in (2,9,16)],
"sweep":     lambda:[O([2*S,13*S,8*S,19*S],fill=B),O([2*S,13*S,8*S,19*S],outline=E),_bez(5*S,16*S,15*S,18*S,19*S,4*S)],
"loft":      lambda:[R([3*S,14*S,11*S,19*S],fill=B),R([3*S,14*S,11*S,19*S],outline=E),R([11*S,3*S,19*S,8*S],fill=B),R([11*S,3*S,19*S,8*S],outline=E),L([3*S,14*S,11*S,3*S],fill=D,width=S),L([11*S,19*S,19*S,8*S],fill=D,width=S)],
"shell":     lambda:[R([3*S,3*S,19*S,19*S],fill=B),R([3*S,3*S,19*S,19*S],outline=E),R([7*S,7*S,19*S,19*S],fill=BG),L([7*S,7*S,7*S,19*S],fill=E,width=S),L([7*S,7*S,19*S,7*S],fill=E,width=S)],
"draft":     lambda:[P([5*S,3*S,17*S,3*S,20*S,19*S,2*S,19*S],fill=B),P([5*S,3*S,17*S,3*S,20*S,19*S,2*S,19*S],outline=E),L([c,3*S,c,19*S],fill=D,width=S)],
"helix":     lambda:[AR([5*S,2*S,17*S,8*S],0,360,fill=E,width=2*S),AR([5*S,8*S,17*S,14*S],0,360,fill=B,width=2*S),AR([5*S,14*S,17*S,20*S],0,360,fill=E,width=2*S)],
"boolean":   lambda:[O([3*S,5*S,13*S,16*S],fill=B),O([3*S,5*S,13*S,16*S],outline=E),O([9*S,5*S,19*S,16*S],fill=D),O([9*S,5*S,19*S,16*S],outline=E)],
"axis":      lambda:[L([c,2*S,c,20*S],fill=E,width=S),L([2*S,c,20*S,c],fill=E,width=S),O([c-4*S,c-4*S,c+4*S,c+4*S],outline=B,width=2*S)],
"rotate":    lambda:[AR([3*S,3*S,19*S,19*S],30,330,fill=B,width=3*S),P([15*S,2*S,20*S,6*S,13*S,8*S],fill=B)],
"explode":   lambda:[R([8*S,8*S,14*S,14*S],fill=B),R([8*S,8*S,14*S,14*S],outline=E),L([c,1*S,c,6*S],fill=E,width=2*S),L([c,16*S,c,21*S],fill=E,width=2*S),L([1*S,c,6*S,c],fill=E,width=2*S),L([16*S,c,21*S,c],fill=E,width=2*S),P([c,1*S,c-2*S,4*S,c+2*S,4*S],fill=E),P([c,21*S,c-2*S,18*S,c+2*S,18*S],fill=E),P([1*S,c,4*S,c-2*S,4*S,c+2*S],fill=E),P([21*S,c,18*S,c-2*S,18*S,c+2*S],fill=E)],
"material":  lambda:[R([3*S,3*S,19*S,19*S],fill=B),R([3*S,3*S,19*S,19*S],outline=E),R([5*S,5*S,9*S,9*S],fill=D),R([13*S,5*S,17*S,9*S],fill=D),R([9*S,9*S,13*S,13*S],fill=D),R([5*S,13*S,9*S,17*S],fill=D),R([13*S,13*S,17*S,17*S],fill=D)],
"dimension": lambda:[L([4*S,3*S,4*S,10*S],fill=E,width=S),L([18*S,3*S,18*S,10*S],fill=E,width=S),L([4*S,7*S,18*S,7*S],fill=B,width=2*S),P([4*S,7*S,7*S,5*S,7*S,9*S],fill=B),P([18*S,7*S,15*S,5*S,15*S,9*S],fill=B),R([7*S,12*S,15*S,17*S],fill=BG,outline=E,width=S)],
    }
    if name in _: _[name]()
    else: r=9*S; P([(c,c-r),(c+r,c),(c,c+r),(c-r,c)],fill=B); P([(c,c-r),(c+r,c),(c,c+r),(c-r,c)],outline=E)

    # Post-draw accent overlays for multi-color icons
    if AC:
        if name == "heart":
            O([5*S,3*S,8*S,6*S],fill=AC)
        elif name == "flame":
            P([c,6*S,7*S,10*S,14*S,10*S],fill=AC)
        elif name == "lightning":
            P([c,2*S,8*S,10*S,9*S,10*S,4*S,16*S,13*S,9*S,11*S,9*S,17*S,2*S],fill=AC)  # glow
        elif name == "sun":
            for a in [i*pi/4 for i in range(8)]:
                L([c+6*S*cos(a),c+6*S*sin(a),c+9*S*cos(a),c+9*S*sin(a)],fill=AC,width=2*S)
        elif name == "star":
            _star(c,c,5*S,10*S,5)  # larger star overlay
        elif name == "trophy":
            O([c-2*S,8*S,c+2*S,12*S],fill=AC)
        elif name == "warning":
            O([c-1*S,12*S,c+1*S,14*S],fill=AC)
