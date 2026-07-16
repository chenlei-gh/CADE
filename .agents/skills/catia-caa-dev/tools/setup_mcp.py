#!/usr/bin/env python3
"""
CADE MCP Auto-Setup — Auto-configure MCP for all detected editors.

Detects installed editors (Zed, Claude Desktop, Cursor, VS Code, Windsurf)
and writes the correct MCP configuration for each.

Usage:
  python tools/setup_mcp.py              # Auto-detect and configure all
  python tools/setup_mcp.py --dry-run    # Preview without writing
  python tools/setup_mcp.py --editor cursor  # Configure specific editor
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent  # catia-caa-dev/


def get_workspace():
    """Find the CAA workspace root (parent of .agents/)"""
    p = SKILL_ROOT
    while p.parent != p:
        if (p / ".agents").exists():
            return p
        p = p.parent
    return Path.cwd()


def mcp_config():
    """Generate MCP server config block."""
    return {
        "cade": {
            "command": "python",
            "args": ["skills/mcp_server.py"],
            "cwd": ".agents/skills/catia-caa-dev",
        }
    }


# ─── Editor Detectors ──────────────────────────────────────────────


def detect_zed() -> bool:
    """Zed auto-detects via SKILL.md — always 'configured'"""
    return (SKILL_ROOT / "SKILL.md").exists()


def detect_claude_desktop() -> Path | None:
    """Detect Claude Desktop config path."""
    if sys.platform == "win32":
        p = (
            Path(os.environ.get("APPDATA", ""))
            / "Claude"
            / "claude_desktop_config.json"
        )
    elif sys.platform == "darwin":
        p = (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    else:
        p = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    return p if p.parent.exists() or True else None  # Always return path


def detect_cursor() -> Path | None:
    """Detect Cursor MCP config path."""
    # Project-level takes priority
    ws = get_workspace()
    project_cfg = ws / ".cursor" / "mcp.json"
    # Global config
    if sys.platform == "win32":
        global_cfg = Path.home() / ".cursor" / "mcp.json"
    elif sys.platform == "darwin":
        global_cfg = (
            Path.home()
            / "Library"
            / "Application Support"
            / "Cursor"
            / "User"
            / "globalStorage"
            / "mcp.json"
        )
    else:
        global_cfg = Path.home() / ".config" / "Cursor" / "mcp.json"

    # Try to find Cursor executable as heuristic
    cursor_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Cursor" / "Cursor.exe",
        Path("/Applications/Cursor.app"),
    ]
    for p in cursor_paths:
        if p.exists():
            return project_cfg
    # Fallback: check global config
    if global_cfg.exists():
        return global_cfg
    return None


def detect_vscode() -> Path | None:
    """Detect VS Code MCP config path (for Copilot / Claude extension)."""
    # VS Code uses .vscode/mcp.json for project-level
    ws = get_workspace()
    project_cfg = ws / ".vscode" / "mcp.json"

    # Check if VS Code is installed
    vscode_paths = [
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Programs"
        / "Microsoft VS Code"
        / "Code.exe",
        Path("/Applications/Visual Studio Code.app"),
    ]
    for p in vscode_paths:
        if p.exists():
            return project_cfg
    # Check if .vscode/ already exists in workspace
    if (ws / ".vscode").exists():
        return project_cfg
    return None


def detect_windsurf() -> Path | None:
    """Detect Windsurf MCP config path."""
    ws = get_workspace()
    if (ws / ".windsurfrules").exists():
        return ws / ".windsurfrules"

    # Check for Windsurf executable
    windsurf_paths = [
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Programs"
        / "Windsurf"
        / "Windsurf.exe",
        Path("/Applications/Windsurf.app"),
    ]
    for p in windsurf_paths:
        if p.exists():
            return ws / ".windsurf" / "mcp.json"
    return None


# ─── Config Writers ─────────────────────────────────────────────────


def write_zed_config(dry_run=False):
    """Zed needs no config — just confirm SKILL.md exists."""
    if detect_zed():
        print("  [OK] Zed: Auto-detected via SKILL.md (no config needed)")
    else:
        print("  [WARN] Zed: SKILL.md not found")


def write_claude_config(config_path: Path, dry_run=False):
    """Write/update Claude Desktop MCP config."""
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["cade"] = mcp_config()["cade"]

    if not dry_run:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    print(f"  {'[DRY RUN]' if dry_run else '[OK]'} Claude Desktop: {config_path}")


def write_cursor_config(config_path: Path, dry_run=False):
    """Write Cursor MCP config."""
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["cade"] = mcp_config()["cade"]

    if not dry_run:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    print(f"  {'[DRY RUN]' if dry_run else '[OK]'} Cursor: {config_path}")


def write_vscode_config(config_path: Path, dry_run=False):
    """Write VS Code MCP config."""
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["cade"] = mcp_config()["cade"]

    if not dry_run:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    print(f"  {'[DRY RUN]' if dry_run else '[OK]'} VS Code: {config_path}")


def write_windsurf_config(config_path: Path, dry_run=False):
    """Write Windsurf MCP config."""
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["cade"] = mcp_config()["cade"]

    if not dry_run:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    print(f"  {'[DRY RUN]' if dry_run else '[OK]'} Windsurf: {config_path}")


# ─── Main ───────────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CADE MCP Auto-Setup")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without writing"
    )
    parser.add_argument(
        "--editor",
        choices=["zed", "claude", "cursor", "vscode", "windsurf"],
        help="Configure specific editor only",
    )
    args = parser.parse_args()

    workspace = get_workspace()
    print(f"\n🔧 CADE MCP Auto-Setup")
    print(f"   Workspace: {workspace}")
    print(f"   Skill:     {SKILL_ROOT}")
    print()

    editors = {
        "zed": (detect_zed, write_zed_config, None),
        "claude": (detect_claude_desktop, write_claude_config, None),
        "cursor": (detect_cursor, write_cursor_config, None),
        "vscode": (detect_vscode, write_vscode_config, None),
        "windsurf": (detect_windsurf, write_windsurf_config, None),
    }

    if args.editor:
        editors = {args.editor: editors[args.editor]}

    configured = 0
    for name, (detector, writer, _) in editors.items():
        result = detector()
        if result is None:
            print(f"  ⬜ {name.title()}: Not detected")
            continue
        if isinstance(result, bool) and result:
            writer(dry_run=args.dry_run)
            configured += 1
        elif isinstance(result, Path):
            writer(result, dry_run=args.dry_run)
            configured += 1

    print()
    if args.dry_run:
        print("  ℹ️  Dry run — no files were modified. Remove --dry-run to apply.")
    else:
        print(f"  🎉 Done! Configured {configured} editor(s).")
        print("  Restart your editor to activate MCP tools.")
    print()


if __name__ == "__main__":
    main()
