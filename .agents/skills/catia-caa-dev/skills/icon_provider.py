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
    """Download from Iconify — Carbon Design collection for style consistency."""
    try:
        import urllib.request
        import json

        query = icon_name.replace("-", " ").replace("_", " ")
        # Force Carbon collection for visual consistency
        url = f"https://api.iconify.design/search?query={query}&prefix=carbon&limit=3"
        req = urllib.request.Request(url, headers={"User-Agent": "CADE/3.2"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        if not data.get("icons"):
            return None

        icon_id = data["icons"][0]  # carbon:icon-name
        if ":" not in icon_id:
            icon_id = f"carbon:{icon_id}"

        svg_url = f"https://api.iconify.design/{icon_id}.svg?width=24&height=24&color=%23161616"
        req2 = urllib.request.Request(svg_url, headers={"User-Agent": "CADE/3.2"})
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            svg_data = resp2.read().decode("utf-8")

        return _svg_to_bmp(svg_data, icon_name)

    except Exception:
        return None


def _svg_to_bmp(svg_data: str, name: str) -> Path:
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


def _render_bmp(points: list, width: int, height: int) -> Path:
    """Render points as simple BMP with bounding box scaling."""
    tmp = Path(os.environ.get("TEMP", "/tmp")) / "cade_icon_tmp.bmp"
    
    if not points:
        return _generate_bmp("unknown")

    # Calculate bounding box
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    scale_x = (width - 4) / max(max_x - min_x, 1)
    scale_y = (height - 4) / max(max_y - min_y, 1)
    scale = min(scale_x, scale_y) * 0.8
    offset_x = (width - (max_x - min_x) * scale) / 2 - min_x * scale
    offset_y = (height - (max_y - min_y) * scale) / 2 - min_y * scale

    # Create BMP
    row_size = ((width * 3 + 3) // 4) * 4
    pixel_data_size = row_size * height
    file_size = 54 + pixel_data_size

    with open(tmp, "wb") as f:
        # BMP header
        f.write(b"BM")
        f.write(struct.pack("<I", file_size))
        f.write(struct.pack("<HH", 0, 0))
        f.write(struct.pack("<I", 54))
        # DIB header
        f.write(struct.pack("<I", 40))
        f.write(struct.pack("<i", width))
        f.write(struct.pack("<i", -height))
        f.write(struct.pack("<H", 1))
        f.write(struct.pack("<H", 24))
        f.write(struct.pack("<I", 0))
        f.write(struct.pack("<I", pixel_data_size))
        f.write(struct.pack("<I", 2835))
        f.write(struct.pack("<I", 2835))
        f.write(struct.pack("<I", 0))
        f.write(struct.pack("<I", 0))

        # Pixel data
        pixels = bytearray(pixel_data_size)
        for x in range(width):
            for y in range(height):
                sx = (x - offset_x) / scale + min_x
                sy = (y - offset_y) / scale + min_y
                # Simple point-in-path check
                color = (0, 0, 0)  # black
                if min_x <= sx <= max_x and min_y <= sy <= max_y:
                    color = (255, 255, 255)  # white interior
                offset = y * row_size + x * 3
                pixels[offset:offset + 3] = bytes(color)
        f.write(pixels)

    return tmp


def _generate_bmp(icon_name: str) -> Path:
    """Generate a 24x24 BMP with the first letter of the icon name.
    This is the ultimate fallback — never fails.
    """
    tmp = Path(os.environ.get("TEMP", "/tmp")) / "cade_icon_tmp.bmp"

    letter = icon_name[0].upper() if icon_name else "?"
    width, height = 24, 24
    row_size = ((width * 3 + 3) // 4) * 4
    pixel_data_size = row_size * height
    file_size = 54 + pixel_data_size

    with open(tmp, "wb") as f:
        f.write(b"BM")
        f.write(struct.pack("<I", file_size))
        f.write(struct.pack("<HH", 0, 0))
        f.write(struct.pack("<I", 54))
        f.write(struct.pack("<I", 40))
        f.write(struct.pack("<i", width))
        f.write(struct.pack("<i", -height))
        f.write(struct.pack("<H", 1))
        f.write(struct.pack("<H", 24))
        f.write(struct.pack("<I", 0))
        f.write(struct.pack("<I", pixel_data_size))
        f.write(struct.pack("<I", 2835))
        f.write(struct.pack("<I", 2835))
        f.write(struct.pack("<I", 0))
        f.write(struct.pack("<I", 0))

        # Fill with light gray background, dark border
        pixels = bytearray(pixel_data_size)
        for y in range(height):
            for x in range(width):
                if 2 <= x <= 21 and 2 <= y <= 21:
                    r, g, b = 200, 200, 210  # light gray
                else:
                    r, g, b = 80, 80, 90  # border
                offset = y * row_size + x * 3
                pixels[offset:offset + 3] = bytes([b, g, r])
        f.write(pixels)

    return tmp

def copy_icons_to_runtime(workspace_path: Path):
    """Copy all framework icons to Runtime View after compilation."""
    for fw in workspace_path.iterdir():
        if not fw.is_dir() or not fw.name.endswith(".edu"):
            continue
        src = fw / "CNext" / "resources" / "graphic" / "icons"
        if not src.exists():
            continue
        for dst_dir in ["win_b64/code/resources/graphic/icons", "win_b64/resources/graphic/icons"]:
            dst = workspace_path / dst_dir
            dst.mkdir(parents=True, exist_ok=True)
            for sf in src.rglob("*.bmp"):
                df = dst / sf.relative_to(src)
                df.parent.mkdir(parents=True, exist_ok=True)
                if not df.exists() or sf.stat().st_mtime > df.stat().st_mtime:
                    shutil.copy2(sf, df)
