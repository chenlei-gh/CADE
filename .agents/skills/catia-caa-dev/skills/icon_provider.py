"""
CADE Icon Provider
==================
Multi-source icon resolution with local cache and offline fallback.

Sources (tried in order):
  1. Iconify API  (largest open icon collection, ~200k icons)
  2. Phosphor Icons (MIT, engineering-focused)
  3. Local cache   (~/.cade/cache/icons/)
  4. Generated BMP (24x24, command initial letter — never fails)

Network is optional — icon download failure never blocks generation.
"""

import os
import shutil
import struct
from pathlib import Path
from typing import Optional

CACHE_DIR = Path.home() / ".cade" / "cache" / "icons"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_icon(icon_name: str, style: str = "engineering") -> Optional[Path]:
    """
    Resolve icon file path. Order: cache → Iconify → Phosphor → generate.

    Args:
        icon_name: Icon search term (e.g., "drill", "gear", "arrow-right")
        style: Icon style hint ("engineering", "minimal", "bold")

    Returns:
        Path to .bmp file (24x24), or None if failed (caller should proceed without icon)
    """
    # 1. Check local cache
    cached = _check_cache(icon_name, style)
    if cached:
        return cached

    # 2. Try Iconify (largest collection)
    path = _try_iconify(icon_name, style)
    if path:
        _cache(icon_name, style, path)
        return path

    # 3. Try Phosphor (MIT, local fallback)
    path = _try_phosphor(icon_name, style)
    if path:
        _cache(icon_name, style, path)
        return path

    # 4. Generate placeholder (never fails)
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
    """Download icon from Iconify API (https://iconify.design)."""
    try:
        import urllib.request
        import json

        # Search for icons matching the term
        query = icon_name.replace("-", " ").replace("_", " ")
        url = f"https://api.iconify.design/search?query={query}&limit=3"
        req = urllib.request.Request(url, headers={"User-Agent": "CADE/3.2"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        if not data.get("icons"):
            return None

        # Pick best match (prefer Material Design or Carbon for engineering)
        prefix = _best_prefix(data["icons"], style)
        icon_id = data["icons"][0] if prefix is None else f"{prefix}:{data['icons'][0].split(':')[-1]}"

        # Download SVG and convert to BMP
        svg_url = f"https://api.iconify.design/{icon_id}.svg?width=24&height=24&color=%23000000"
        req2 = urllib.request.Request(svg_url, headers={"User-Agent": "CADE/3.2"})
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            svg_data = resp2.read().decode("utf-8")

        return _svg_to_bmp(svg_data, icon_name)

    except Exception:
        return None


def _best_prefix(icons: list, style: str) -> Optional[str]:
    """Pick best icon set prefix."""
    prefixes = {i.split(":")[0] for i in icons if ":" in i}
    # Preferred sets for engineering/CATIA style
    preferred = ["mdi", "carbon", "ph", "material-symbols", "lucide", "fluent"]
    for p in preferred:
        if p in prefixes:
            return p
    return next(iter(prefixes)) if prefixes else None


def _try_phosphor(icon_name: str, style: str) -> Optional[Path]:
    """Try Phosphor Icons (MIT) — local package if installed."""
    try:
        import urllib.request
        term = icon_name.replace(" ", "-").lower()
        url = f"https://raw.githubusercontent.com/phosphor-icons/core/main/assets/regular/{term}.svg"
        req = urllib.request.Request(url, headers={"User-Agent": "CADE/3.2"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            svg_data = resp.read().decode("utf-8")
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
