#!/usr/bin/env python3
"""
Golden Icon Sample Generator (DEPRECATED — v4.0 Official-Only)
==============================================================
This script is no longer functional. The v4.0 Official-Only refactor
deleted the primitive renderer (_render_icon) that this script depended
on. Golden visual regression samples are no longer generated from code.

Official icons are now sourced directly from the local CATIA B28
installation at runtime and are never copied into the repo.

To visually verify icons, use the CLI audit with --render:
  python skills/icon_provider.py --render tmp/icons CreateHoleCmd ...

Or inspect the composed output directly:
  python -c "from icon_provider import get_icon; print(get_icon('CreateHoleCmd'))"
"""

import sys

def main():
    print("DEPRECATED: update_golden_icons.py is no longer functional.")
    print("The primitive renderer (_render_icon) was deleted in v4.0.")
    print("Use 'python skills/icon_provider.py --render DIR Name ...' instead.")
    sys.exit(1)

if __name__ == "__main__":
    main()
