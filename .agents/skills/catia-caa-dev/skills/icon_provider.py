"""
CADE Icon Provider
==================
Multi-source icon resolution with local cache and offline fallback.

Sources (tried in order):
  1. Local cache   (~/.cade/cache/icons/)
  2. Iconify API  (Carbon Design — consistent engineering style)
  3. Generated BMP (24x24, command initial letter — never fails)

Network is optional — icon download failure never blocks generation.
Style is enforced via Iconify's "carbon" collection for visual consistency.
"""

import os
import shutil
import struct
from pathlib import Path
from typing import Optional

CACHE_DIR = Path.home() / ".cade" / "cache" / "icons"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ─── Domain-to-Icon Mapping (CAA engineering context) ──────────
DOMAIN_MAP = {
    # Manufacturing / Machining
    "hole": "drill", "pocket": "box", "contour": "contour-draw",
    "mill": "cube", "drill": "drill", "machine": "cog",
    # Assembly / Structure
    "assemble": "assembly", "part": "cube", "product": "package",
    "component": "cube", "constrain": "constraint",
    # Geometry / Modeling
    "pad": "box", "extrude": "extrusion", "revolve": "circle-dash",
    "fillet": "radius", "chamfer": "cut", "sketch": "draw",
    "surface": "surface", "wireframe": "wireframe", "point": "point",
    "line": "line", "curve": "curve", "split": "cut",
    "trim": "cut-out", "join": "join-straight", "transform": "move",
    # Analysis / Measure
    "measure": "ruler", "distance": "ruler-alt", "angle": "angle",
    "analyze": "analytics", "check": "checkmark", "verify": "checkmark-outline",
    "report": "report", "statistic": "chart-bar",
    # UI / Interaction
    "select": "cursor-1", "pick": "cursor-1", "dialog": "application-web",
    "setting": "settings", "config": "settings-adjust", "option": "chevron-down",
    "view": "view", "zoom": "zoom-in", "pan": "pan-horizontal",
    # Data / File
    "save": "save", "open": "folder-open", "export": "export",
    "import": "import-export", "file": "document", "catalog": "catalog",
    "database": "data-base", "search": "search", "filter": "filter",
}


def resolve_icon(command_name: str, hint: str = None) -> str:
    """
    Smart icon resolution from command name + domain hint.
    
    Args:
        command_name: e.g., "HoleCmd", "MeasureDistance"
        hint: optional domain keyword, e.g., "manufacturing", "analysis"
    
    Returns:
        Icon name for get_icon()
    """
    name_lower = command_name.lower().replace("cmd", "").replace("command", "")
    if hint:
        hint_lower = hint.lower()
        if hint_lower in DOMAIN_MAP:
            return DOMAIN_MAP[hint_lower]
    # Try each word in the command name
    for word in name_lower.split("_"):
        word = word.strip()
        if word in DOMAIN_MAP:
            return DOMAIN_MAP[word]
    # Try partial match
    for key, value in DOMAIN_MAP.items():
        if key in name_lower:
            return value
    # Fallback: use command name as icon search term
    return name_lower.split("_")[0] if "_" in name_lower else name_lower


def get_icon(icon_name: str, style: str = "carbon") -> Optional[Path]:
    """
    Resolve icon file path with style consistency.
    
    Default collection: IBM Carbon Design (engineering-focused, consistent style).
    Order: local cache → Iconify Carbon → generated BMP.
    
    Returns:
        Path to .bmp file (24x24), or None (caller proceeds without icon)
    """
    # 1. Check local cache
    cached = _check_cache(icon_name, style)
    if cached:
        return cached

    # 2. Try Iconify — Carbon collection only for style consistency
    path = _try_iconify(icon_name, style)
    if path:
        _cache(icon_name, style, path)
        return path

    # 3. Generate placeholder (never fails)
    path = _generate_bmp(icon_name)
    _cache(icon_name, style, path)
    return path


def _check_cache(icon_name: str, style: str) -> Optional[Path]:
    """Check local cache for icon."""
    key = _cache_key(icon_name, style)
    cached = CACHE_DIR / f"{key}.bmp"
    return cached if cached.exists() else None


def _cache(icon_name: str, style: str, source: Path):
    """Copy to local cache."""
    key = _cache_key(icon_name, style)
    shutil.copy(source, CACHE_DIR / f"{key}.bmp")


def _cache_key(icon_name: str, style: str) -> str:
    return f"{icon_name}_{style}".replace("/", "_").replace(" ", "_").replace(":", "_")


def _try_iconify(icon_name: str, style: str) -> Optional[Path]:
    """Download SVG from Iconify Carbon and render to 8-bit BMP."""
    try:
        import urllib.request
        import json

        query = icon_name.replace("-", " ").replace("_", " ")
        url = f"https://api.iconify.design/search?query={query}&prefix=carbon&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "CADE/3.2"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        if not data.get("icons"):
            return None

        icon_id = data["icons"][0]
        if ":" not in icon_id:
            icon_id = f"carbon:{icon_id}"

        # Download SVG
        svg_url = f"https://api.iconify.design/{icon_id}.svg?width=32&height=32"
        req2 = urllib.request.Request(svg_url, headers={"User-Agent": "CADE/3.2"})
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            svg_data = resp2.read().decode("utf-8")

        return svg_to_bmp8(svg_data, icon_name)

    except Exception:
        return None


def svg_to_bmp8(svg_data: str, name: str) -> Path:
    """Render SVG <path> outlines to 22x22 8-bit grayscale BMP for B28."""
    import re, struct as _struct
    tmp = Path(os.environ.get("TEMP", "/tmp")) / f"cade_icon_{name}.bmp"

    # Extract all path data strings
    paths = re.findall(r' d="([^"]+)"', svg_data)
    if not paths:
        return _generate_bmp(name)

    # Parse all path segments into point lists
    all_points = []
    for path_data in paths:
        # Tokenize SVG path with compact number handling
        # Split on command letters (including H/V for horizontal/vertical lines)
        segments = re.split(r'(?=[MLCZHVTQSAmclzhvtqsa])', path_data)
        points, cx, cy = [], 0, 0
        for seg in segments:
            if not seg.strip():
                continue
            cmd = seg[0].upper()
            # Parse numbers: handle compact format like "1.414-1.414"
            nums_str = seg[1:].strip()
            # Replace compact negative signs with space-separated negatives
            nums_str = re.sub(r'(?<=\d)-(?=\d)', ' -', nums_str)
            nums = [float(x) for x in nums_str.split()]
            cu = cmd
            if cu == 'M':
                cx, cy = nums[0], nums[1] if len(nums) > 1 else 0
                points.append((cx, cy))
            elif cu == 'L' and len(nums) >= 2:
                cx, cy = nums[0], nums[1]
                points.append((cx, cy))
            elif cu == 'H' and len(nums) >= 1:
                cx = nums[0]
                points.append((cx, cy))
            elif cu == 'V' and len(nums) >= 1:
                cy = nums[0]
                points.append((cx, cy))
            elif cu == 'C' and len(nums) >= 6:
                cx, cy = nums[4], nums[5]
                points.append((cx, cy))
            elif cu == 'Z':
                points.append(points[0] if points else (0, 0))
        if points:
            all_points.append(points)

    if not all_points:
        return _generate_bmp(name)

    # Calculate combined bounding box from all paths
    all_pts = [p for pts in all_points for p in pts]
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    w, h = max_x - min_x, max_y - min_y
    if w < 1: w = 1
    if h < 1: h = 1

    out_w, out_h = 22, 22
    margin = 2
    scale = min((out_w - 2 * margin) / w, (out_h - 2 * margin) / h)
    ox = (out_w - w * scale) / 2 - min_x * scale
    oy = (out_h - h * scale) / 2 - min_y * scale

    # 8-bit indexed BMP
    row_size = ((out_w + 3) // 4) * 4
    palette_size = 256 * 4
    pixel_size = row_size * out_h
    file_size = 54 + palette_size + pixel_size

    with open(tmp, "wb") as f:
        f.write(b"BM")
        f.write(_struct.pack("<I", file_size))
        f.write(_struct.pack("<HH", 0, 0))
        f.write(_struct.pack("<I", 54 + palette_size))
        f.write(_struct.pack("<I", 40))
        f.write(_struct.pack("<i", out_w))
        f.write(_struct.pack("<i", out_h))
        f.write(_struct.pack("<H", 1))
        f.write(_struct.pack("<H", 8))
        f.write(_struct.pack("<I", 0))
        f.write(_struct.pack("<I", pixel_size))
        f.write(_struct.pack("<I", 2835))
        f.write(_struct.pack("<I", 2835))
        f.write(_struct.pack("<I", 256))
        f.write(_struct.pack("<I", 0))
        # Grayscale palette: 0=white, 255=black
        for i in range(256):
            v = 255 - i if i < 128 else 0
            f.write(bytes([v, v, v, 0]))

        # Render: 0=white bg, dark for path interior
        pixels = bytearray(pixel_size)
        for y in range(out_h):
            for x in range(out_w):
                inside = False
                for pts in all_points:
                    # Point-in-polygon test
                    n = len(pts)
                    j = n - 1
                    for i in range(n):
                        xi, yi = pts[i]
                        xj, yj = pts[j]
                        syi = yi * scale + oy
                        syj = yj * scale + oy
                        sxi = xi * scale + ox
                        sxj = xj * scale + ox
                        if ((syi > y) != (syj > y)) and (x < (sxj - sxi) * (y - syi) / (syj - syi) + sxi):
                            inside = not inside
                        j = i
                pixels[y * row_size + x] = 50 if inside else 0
        f.write(pixels)

    return tmp
    """Convert PNG to B28-compatible 8-bit indexed BMP (22x22)."""
    import zlib, struct as _struct
    tmp = Path(os.environ.get("TEMP", "/tmp")) / f"cade_icon_{name}.bmp"

    if png_data[:8] != b'\x89PNG\r\n\x1a\n':
        return _generate_bmp(name)

    ihdr_start = 8 + 4
    width = int.from_bytes(png_data[ihdr_start:ihdr_start+4], 'big')
    height = int.from_bytes(png_data[ihdr_start+4:ihdr_start+8], 'big')
    color_type = png_data[ihdr_start+9]

    # Extract IDAT chunks
    pos, idat_data = 8, b''
    while pos < len(png_data):
        chunk_len = int.from_bytes(png_data[pos:pos+4], 'big')
        chunk_type = png_data[pos+4:pos+8].decode('ascii', errors='ignore')
        if chunk_type == 'IDAT':
            idat_data += png_data[pos+8:pos+8+chunk_len]
        elif chunk_type == 'IEND':
            break
        pos += 12 + chunk_len

    try:
        raw = zlib.decompress(idat_data)
    except Exception:
        return _generate_bmp(name)

    # B28-compatible: 22x22, 8-bit indexed, bottom-up
    out_w, out_h = 22, 22
    bpp = 1 if color_type == 0 else 8
    palette_size = 256 * 4 if bpp == 8 else 2 * 4
    row_size = ((out_w * bpp + 31) // 32) * 4
    pixel_size = row_size * out_h
    file_size = 54 + palette_size + pixel_size
    src_bpp = 4 if color_type == 6 else 3
    src_row = width * src_bpp

    with open(tmp, "wb") as f:
        f.write(b"BM")
        f.write(_struct.pack("<I", file_size))
        f.write(_struct.pack("<HH", 0, 0))
        f.write(_struct.pack("<I", 54 + palette_size))
        f.write(_struct.pack("<I", 40))
        f.write(_struct.pack("<i", out_w))
        f.write(_struct.pack("<i", out_h))  # positive = bottom-up for B28
        f.write(_struct.pack("<H", 1))
        f.write(_struct.pack("<H", bpp * 8))
        f.write(_struct.pack("<I", 0))
        f.write(_struct.pack("<I", pixel_size))
        f.write(_struct.pack("<I", 2835))
        f.write(_struct.pack("<I", 2835))
        if bpp == 8:
            f.write(_struct.pack("<I", 256))  # colors used
            f.write(_struct.pack("<I", 0))     # important colors
        else:
            f.write(_struct.pack("<I", 0))
            f.write(_struct.pack("<I", 0))

        # 8-bit grayscale palette
        if bpp == 8:
            for i in range(256):
                f.write(bytes([i, i, i, 0]))

        # Pixels (bottom-up, scaled)
        pixels = bytearray(pixel_size)
        for y in range(out_h):
            sy = int(y * height / out_h)
            for x in range(out_w):
                sx = int(x * width / out_w)
                so = sy * src_row + sx * src_bpp
                if so + 2 < len(raw):
                    r, g, b = raw[so], raw[so+1], raw[so+2]
                    gray = int(0.299 * r + 0.587 * g + 0.114 * b)
                    pixels[y * row_size + x] = gray if gray > 0 else 30
                else:
                    pixels[y * row_size + x] = 128
        f.write(pixels)

    return tmp
    """Convert SVG to 24x24 BMP using pure Python (no external deps).
    
    For complex SVGs, falls back to generated placeholder.
    """
    import re
    path_data = ""
    for pattern in [r'd="([^"]*)"', r"d='([^']*)'"]:
        m = re.search(pattern, svg_data)
        if m:
            path_data = m.group(1)
            break

    if not path_data:
        return _generate_bmp(name)

    # Simple SVG path → BMP rendering
    try:
        # Parse basic path commands (M, L, C, Z)
        commands = re.findall(r'([MLCZ])\s*([\d\s.-]+)', path_data, re.I)
        points = []
        for cmd, coords in commands:
            nums = [float(x) for x in coords.split()]
            if cmd.upper() == 'M':
                points.append(nums)
            elif cmd.upper() == 'L':
                if len(nums) >= 2:
                    points.append(nums[:2])
            elif cmd.upper() == 'C':
                if len(nums) >= 6:
                    points.append(nums[4:6])
    except Exception:
        return _generate_bmp(name)

    return _render_bmp(points, 24, 24)


def _generate_bmp(icon_name: str) -> Path:
    """Generate 22x22 8-bit placeholder BMP — never fails."""
    import struct as _struct
    tmp = Path(os.environ.get("TEMP", "/tmp")) / "cade_icon_tmp.bmp"

    out_w, out_h = 22, 22
    row_size = ((out_w + 3) // 4) * 4
    pixel_size = row_size * out_h
    palette_size = 256 * 4
    file_size = 54 + palette_size + pixel_size

    with open(tmp, "wb") as f:
        f.write(b"BM")
        f.write(_struct.pack("<I", file_size))
        f.write(_struct.pack("<HH", 0, 0))
        f.write(_struct.pack("<I", 54 + palette_size))
        f.write(_struct.pack("<I", 40))
        f.write(_struct.pack("<i", out_w))
        f.write(_struct.pack("<i", out_h))
        f.write(_struct.pack("<H", 1))
        f.write(_struct.pack("<H", 8))
        f.write(_struct.pack("<I", 0))
        f.write(_struct.pack("<I", pixel_size))
        f.write(_struct.pack("<I", 2835))
        f.write(_struct.pack("<I", 2835))
        f.write(_struct.pack("<I", 256))
        f.write(_struct.pack("<I", 0))
        # Grayscale palette
        for i in range(256):
            v = 255 - i if i < 128 else 0
            f.write(bytes([v, v, v, 0]))
        # Light gray fill with dark border
        pixels = bytearray(pixel_size)
        for y in range(out_h):
            for x in range(out_w):
                if 2 <= x <= 19 and 2 <= y <= 19:
                    pixels[y * row_size + x] = 200  # light gray
                else:
                    pixels[y * row_size + x] = 50   # dark border
        f.write(pixels)

    return tmp

def copy_icons_to_runtime(workspace_path: Path):
    """Copy all framework icons + CATRsc to Runtime View after compilation."""
    for fw in workspace_path.iterdir():
        if not fw.is_dir() or not fw.name.endswith(".edu"):
            continue

        # CATRsc (in msgcatalog/) → win_b64/resources/msgcatalog/
        rsc_dir = fw / "CNext" / "resources" / "msgcatalog"
        if rsc_dir.exists():
            for rsc in rsc_dir.glob("*.CATRsc"):
                rsc_dst = workspace_path / "win_b64" / "resources" / "msgcatalog" / rsc.name
                rsc_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(rsc, rsc_dst)

        # Icons → win_b64/resources/graphic/icons/
        src = fw / "CNext" / "resources" / "graphic" / "icons"
        if src.exists():
            dst = workspace_path / "win_b64" / "resources" / "graphic" / "icons"
            dst.mkdir(parents=True, exist_ok=True)
            for sf in src.rglob("*.bmp"):
                df = dst / sf.relative_to(src)
                df.parent.mkdir(parents=True, exist_ok=True)
                if not df.exists() or sf.stat().st_mtime > df.stat().st_mtime:
                    shutil.copy2(sf, df)
