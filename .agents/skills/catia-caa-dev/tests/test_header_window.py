#!/usr/bin/env python3
"""
SDK header window — offline contract
=====================================
The reader prints a bounded window from a header that sits under
CATIA_INSTALL, outside the editor workspace. These cases never touch a
real CATIA install: a fake tree is injected.

Not registered in test_master.py SUITES. Run directly:

  python tests/test_header_window.py
"""

import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from header_map import (  # noqa: E402
    _comment_declared_on,
    format_header_window,
    read_header_window,
    resolve_header_file,
)


total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    suffix = f" — {detail}" if detail else ""
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{suffix}")


print("=" * 60)
print("  Header window (offline)")
print("=" * 60)

ck(
    "href names the declaring interface",
    _comment_declared_on(
        [" * @href CATIVisPropertiesAbstract#SetPropertiesAtt"],
        "SetPropertiesAtt",
    ) == "CATIVisPropertiesAbstract",
)
ck("empty install is refused", resolve_header_file("", "Dialog", "CATDlgEditor") is None)
ck("dotdot framework refused", resolve_header_file("C:/catia", "..", "CATDlgEditor") is None)
ck("dotdot stem refused", resolve_header_file("C:/catia", "Dialog", "..\\secret") is None)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    header_dir = root / "Visualization" / "PublicInterfaces"
    header_dir.mkdir(parents=True)
    lines = [f"line {i}" for i in range(1, 40)]
    lines[11] = " * @href CATIVisPropertiesAbstract#SetPropertiesAtt"
    lines[19] = "class CATIVisProperties : public CATBaseUnknown {"
    lines[24] = "    virtual HRESULT SetPropertiesAtt();"
    (header_dir / "CATIVisProperties.h").write_text("\n".join(lines) + "\n", encoding="utf-8")

    outside = root.parent / "secret.h"
    try:
        outside.write_text("secret", encoding="utf-8")
        escaped = resolve_header_file(str(root), "..", "secret")
        ck("escape via .. is refused", escaped is None, str(escaped))
    finally:
        if outside.exists():
            outside.unlink()

    found = resolve_header_file(str(root), "Visualization", "CATIVisProperties")
    ck("header under install accepted", found is not None and found.name == "CATIVisProperties.h")
    ck("missing header is None", resolve_header_file(str(root), "Visualization", "NoSuch") is None)

    empty = read_header_window("", "Visualization", "CATIVisProperties")
    ck("empty install is source_unavailable", empty["status"] == "source_unavailable" and empty["read_only"] is True)

    missing = read_header_window(str(root), "Visualization", "NoSuch")
    ck("missing file is not_found", missing["status"] == "not_found")

    hit = read_header_window(
        str(root), "Visualization", "CATIVisProperties",
        method="SetPropertiesAtt", context=1, max_lines=60,
    )
    ck("method hit is ok", hit["status"] == "ok" and hit["read_only"] is True)
    ck("method line is in the window", any("SetPropertiesAtt" in f["text"] for f in hit["fragments"]))
    ck("window is numbered", "   25|" in hit["fragments"][0]["text"])
    window_lines = sum(f["text"].count("|") for f in hit["fragments"])
    ck("method hit prefers the code line", hit.get("declaration_in_header") is True)
    ck("comment mention is not the window anchor", hit["matched_lines"][:1] == [25])
    ck("comment-only names the declaring interface", hit.get("declared_on") == "")
    ck(
        "method window is a small excerpt of the file",
        hit["line_count"] == 39 and hit["truncated"] is False and window_lines <= 5,
        f"file={hit['line_count']} window={window_lines}",
    )
    shown = format_header_window(hit)
    ck("format prints status and line range", "status=ok" in shown and "--- L" in shown)

    clipped = read_header_window(
        str(root), "Visualization", "CATIVisProperties",
        method="", context=8, max_lines=5,
    )
    ck("max_lines truncates", clipped["truncated"] is True)
    text = "\n".join(f["text"] for f in clipped["fragments"])
    ck("truncated window stays within max_lines", text.count("|") <= 5, str(text.count("|")))

print()
print(f"  {passed}/{total} passed")
sys.exit(0 if passed == total else 1)
