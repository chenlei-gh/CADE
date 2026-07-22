"""
CADE Icon Provider v3.3
=======================
107 geometric patterns, 4x supersampling, true multi-color RGBA rendering.

Design: draw at 4x on RGBA with explicit colors, LANCZOS scale down,
quantize to 8-bit BMP. Each pattern can use BODY, EDGE, DIM, ACCENT colors.
Style aligned with official CATIA icons (sampled from B28 resources):
BODY=domain color, EDGE=dark navy ink (24,16,82), DIM=dark shade,
background=CATIA gray (192,192,192), no dithering (clean flat pixels).

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
CACHE_VER = "v3"                  # bump when render style changes

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
}

# ─── Domain → Color ───────────────────────────────────────────────
COLOR_MAP: Dict[str, Tuple[int,int,int]] = {
    "hole":(220,38,38),"pocket":(220,38,38),"contour":(220,38,38),
    "mill":(220,38,38),"drill":(220,38,38),"machine":(220,38,38),
    "cog":(220,38,38),"gear":(220,38,38),
    "assemble":(37,99,235),"part":(37,99,235),"product":(37,99,235),
    "component":(37,99,235),"cube":(37,99,235),"constrain":(37,99,235),
    "pad":(79,70,229),"extrude":(79,70,229),"revolve":(79,70,229),
    "fillet":(79,70,229),"chamfer":(79,70,229),"sketch":(79,70,229),
    "surface":(79,70,229),"wireframe":(79,70,229),"point":(79,70,229),
    "line":(79,70,229),"curve":(79,70,229),"split":(79,70,229),
    "trim":(79,70,229),"join":(79,70,229),"transform":(79,70,229),
    "measure":(22,163,74),"distance":(22,163,74),"angle":(22,163,74),
    "analyze":(22,163,74),"check":(22,163,74),"verify":(22,163,74),
    "report":(22,163,74),"statistic":(22,163,74),
    "select":(124,58,237),"pick":(124,58,237),"dialog":(124,58,237),
    "setting":(124,58,237),"config":(124,58,237),"configure":(124,58,237),
    "option":(124,58,237),"view":(124,58,237),"zoom":(124,58,237),
    "pan":(124,58,237),"save":(234,88,12),"open":(234,88,12),
    "export":(234,88,12),"import":(234,88,12),"file":(234,88,12),
    "catalog":(234,88,12),"database":(234,88,12),"search":(234,88,12),
    "filter":(234,88,12),"test":(13,148,136),"test_tool":(13,148,136),
    "dev":(13,148,136),
    "heart":(220,38,38),"lock":(234,170,8),"plus":(22,163,74),
    "lightning":(234,170,8),"flame":(234,88,12),"trophy":(234,170,8),
    "pin":(220,38,38),"forward":(22,163,74),"target":(220,38,38),
    "chat":(124,58,237),"shield":(37,99,235),
}


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════

def resolve_icon(command_name: str, hint: str = None) -> str:
    nl = command_name.lower().replace("cmd","").replace("command","")
    if hint and hint.lower() in DOMAIN_MAP: return DOMAIN_MAP[hint.lower()]
    for w in nl.split("_"):
        if w.strip() in DOMAIN_MAP: return DOMAIN_MAP[w.strip()]
    for k,v in DOMAIN_MAP.items():
        if k in nl: return v
    return nl.split("_")[0] if "_" in nl else nl

def _get_color_for_icon(icon_name: str) -> Tuple[int,int,int]:
    nl = icon_name.lower().replace("-","_").replace(" ","_")
    if nl in COLOR_MAP: return COLOR_MAP[nl]
    for k,c in COLOR_MAP.items():
        if k in nl: return c
    for dk,di in DOMAIN_MAP.items():
        if di==nl and dk in COLOR_MAP: return COLOR_MAP[dk]
    return (10, 0, 255)  # CATIA accent blue for unmapped icons (never ~bg gray)

def get_icon(icon_name: str, style: str = "geo") -> Optional[Path]:
    key = f"{icon_name}_{CACHE_VER}_{style}".replace("/","_").replace(" ","_").replace(":","_")
    cached = CACHE_DIR / f"{key}.bmp"
    if cached.exists(): return cached
    path = _render_icon(icon_name)
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
                if not df.exists() or sf.stat().st_mtime>df.stat().st_mtime: shutil.copy2(sf,df)


# ═══════════════════════════════════════════════════════════════════
#  Rendering Pipeline
# ═══════════════════════════════════════════════════════════════════

def _render_icon(icon_name: str) -> Path:
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
        "lightning": (255, 255, 100, 255),
        "sun": (255, 220, 50, 255),
        "trophy": (255, 215, 0, 255),
        "warning": (255, 200, 0, 255),
        "star": (255, 215, 0, 255),
        "heart": (255, 100, 100, 255),
        "target": (255, 50, 50, 255),
    }
    if icon_name in acmap:
        accent = acmap[icon_name]

    # Draw on official CATIA gray background
    img_big = Image.new("RGBA", (big_w, big_h), (*CATIA_BG, 255))
    draw_big = ImageDraw.Draw(img_big)
    _draw_icon_4x_rgba(draw_big, icon_name, S, body, edge, dim, accent)

    # Scale down, flatten to RGB, quantize without dithering (flat pixels)
    img = img_big.resize((22, 22), Image.LANCZOS).convert("RGB")
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
"box":       lambda:R([2*S,2*S,19*S,19*S],fill=B),
"circle":    lambda:O([1*S,1*S,20*S,20*S],fill=B),
"point":     lambda:O([c-4*S,c-4*S,c+4*S,c+4*S],fill=E),
"line":      lambda:L([2*S,c,19*S,c],fill=E,width=4*S),
"arc":       lambda:AR([1*S,1*S,20*S,20*S],180,360,fill=E,width=4*S),
"wave":      lambda:L([(1*S,17*S),(4*S,9*S),(7*S,17*S),(10*S,9*S),(13*S,17*S),(16*S,9*S),(20*S,17*S)],fill=E,width=3*S),
"grid":      lambda:[L([3*S,8*S,18*S,8*S],fill=D,width=S),L([3*S,14*S,18*S,14*S],fill=D,width=S),L([8*S,3*S,8*S,18*S],fill=D,width=S),L([14*S,3*S,14*S,18*S],fill=D,width=S)],
"play":      lambda:[P([4*S,2*S,4*S,19*S,19*S,c],fill=B),P([4*S,2*S,4*S,19*S,19*S,c],outline=E)],
"drill":     lambda:[P([c,2*S,3*S,16*S,18*S,16*S],fill=B),R([c-3*S,7*S,c+3*S,16*S],fill=BG)],
"cut":       lambda:[L([2*S,2*S,19*S,19*S],fill=E,width=3*S),L([19*S,2*S,2*S,19*S],fill=E,width=3*S)],
"cursor":    lambda:P([1*S,1*S,1*S,17*S,8*S,12*S,13*S,19*S,16*S,15*S,10*S,10*S,16*S,6*S],fill=B),
"move":      lambda:[P([c,1*S,c-6*S,9*S,c-2*S,9*S,c-2*S,18*S,c+2*S,18*S,c+2*S,9*S,c+6*S,9*S],fill=B),L([c,3*S,c,17*S],fill=E,width=2*S),P([1*S,c,9*S,c-6*S,9*S,c-2*S,18*S,c-2*S,18*S,c+2*S,9*S,c+2*S,9*S,c+6*S],fill=B),L([3*S,c,17*S,c],fill=E,width=2*S)],
"merge":     lambda:[L([3*S,3*S,c,13*S],fill=E,width=3*S),L([18*S,3*S,c,13*S],fill=E,width=3*S),L([c,13*S,c,19*S],fill=E,width=3*S)],
"settings":  lambda:_gear(draw,c,c,7*S,10),
"search":    lambda:[O([1*S,1*S,14*S,14*S],outline=E,width=2*S),L([12*S,12*S,20*S,20*S],fill=E,width=4*S)],
"pencil":    lambda:[L([2*S,19*S,17*S,4*S],fill=E,width=3*S),P([17*S,0,21*S,4*S,17*S,8*S,13*S,4*S],fill=B)],
"ruler":     lambda:[R([1*S,2*S,20*S,19*S],outline=E,width=S),L([1*S,6*S,12*S,6*S],fill=D,width=2*S),L([1*S,11*S,16*S,11*S],fill=B,width=2*S),L([1*S,16*S,9*S,16*S],fill=D,width=2*S)],
"magnify":   lambda:[O([0,0,15*S,15*S],outline=E,width=2*S),L([13*S,13*S,21*S,21*S],fill=E,width=4*S)],
"funnel":    lambda:[P([1*S,2*S,20*S,2*S,15*S,c,6*S,c],fill=B),P([1*S,2*S,20*S,2*S,15*S,c,6*S,c],outline=E)],
"window":    lambda:[R([1*S,1*S,20*S,20*S],outline=E,width=2*S),R([1*S,1*S,20*S,7*S],fill=E)],
"eye":       lambda:[O([0,7*S,21*S,14*S],outline=E,width=2*S),O([c-3*S,8*S,c+3*S,13*S],fill=E)],
"hand":      lambda:[R([8*S,1*S,13*S,9*S],fill=B),R([5*S,6*S,16*S,10*S],fill=B),R([3*S,10*S,18*S,14*S],fill=B),R([5*S,14*S,16*S,20*S],outline=E)],
"chevron":   lambda:[P([2*S,6*S,c,14*S,19*S,6*S],fill=B),P([2*S,6*S,c,14*S,19*S,6*S],outline=E)],
"doc":       lambda:[R([3*S,1*S,18*S,20*S],outline=E,width=2*S),L([6*S,5*S,15*S,5*S],fill=D,width=S),L([6*S,8*S,15*S,8*S],fill=B,width=2*S),L([6*S,12*S,13*S,12*S],fill=D,width=S)],
"folder":    lambda:[P([1*S,4*S,7*S,4*S,10*S,8*S,20*S,8*S,20*S,19*S,1*S,19*S],fill=B),P([1*S,4*S,7*S,4*S,10*S,8*S,20*S,8*S,20*S,19*S,1*S,19*S],outline=E)],
"disk":      lambda:[O([3*S,2*S,18*S,17*S],outline=E,width=2*S),O([8*S,6*S,13*S,11*S],fill=E),R([8*S,0,13*S,3*S],fill=B)],
"export":    lambda:[P([c,1*S,3*S,11*S,10*S,11*S],fill=B),P([c,1*S,3*S,11*S,10*S,11*S],outline=E),R([7*S,11*S,14*S,20*S],fill=E)],
"import":    lambda:[P([c,20*S,3*S,10*S,10*S,10*S],fill=B),P([c,20*S,3*S,10*S,10*S,10*S],outline=E),R([7*S,1*S,14*S,10*S],fill=E)],
"book":      lambda:[R([2*S,1*S,11*S,20*S],outline=E,width=2*S),R([10*S,1*S,19*S,20*S],outline=E,width=2*S),L([10*S,1*S,10*S,20*S],fill=E,width=2*S)],
"db":        lambda:[O([3*S,15*S,18*S,20*S],outline=D,width=S),O([3*S,9*S,18*S,14*S],outline=B,width=2*S),O([3*S,2*S,18*S,7*S],outline=E,width=2*S),L([3*S,4*S,3*S,12*S],fill=D,width=2*S),L([18*S,4*S,18*S,12*S],fill=D,width=2*S)],
"check":     lambda:L([2*S,11*S,9*S,18*S,20*S,3*S],fill=E,width=4*S),
"angle":     lambda:[L([2*S,19*S,2*S,4*S],fill=E,width=3*S),L([2*S,19*S,17*S,19*S],fill=E,width=3*S),AR([2*S,9*S,11*S,18*S],0,-90,fill=D,width=2*S)],
"chart":     lambda:[L([2*S,19*S,2*S,2*S],fill=D,width=S),L([2*S,19*S,20*S,19*S],fill=D,width=S),R([4*S,11*S,7*S,19*S],fill=B),R([9*S,5*S,12*S,19*S],fill=B),R([14*S,8*S,17*S,19*S],fill=E)],
"code":      lambda:[L([17*S,4*S,6*S,11*S,17*S,18*S],fill=E,width=3*S),L([5*S,4*S,16*S,11*S,5*S,18*S],fill=E,width=3*S)],
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
