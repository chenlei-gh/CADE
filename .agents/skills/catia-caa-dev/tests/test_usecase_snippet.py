#!/usr/bin/env python3
"""
UseCase snippet reader — offline contract
==========================================
The reader prints a bounded window from official CAADoc samples that sit
outside the editor workspace. These cases never touch a real CATIA install
or cache/usecase_index.json: a fake index and a temp tree are injected.

Not registered in test_master.py SUITES. Run directly:

  python tests/test_usecase_snippet.py
"""

import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from usecase_snippet import (  # noqa: E402
    _clip_windows,
    _parse_lines,
    _safe_under,
    _windows,
    read_snippet,
    select_examples,
)


total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    suffix = f" — {detail}" if detail else ""
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{suffix}")


class _FakeRetrieval:
    def __init__(self, index):
        self.usecase_index = index


def _index():
    return {
        "meta": {},
        "examples": {
            "SampleCmd": {
                "file": "CAASample.edu/CAASample.m/src/SampleCmd.cpp",
                "interfaces": ["CATIVisProperties"],
                "methods": ["SetPropertiesAtt"],
                "symbols": ["CATNoShowAttr"],
            },
            "Other (Mod.m)": {
                "file": "CAAOther.edu/Mod.m/src/Other.cpp",
                "interfaces": [],
                "methods": [],
                "symbols": [],
            },
        },
        "resources": {
            "CAASample.edu/CAASample.m/Imakefile.mk": {
                "kind": "imakefile",
                "framework": "CAASample.edu",
                "module": "CAASample.m",
            },
        },
        "by_interface": {"CATIVisProperties": ["SampleCmd"]},
        "by_method": {"SetPropertiesAtt": ["SampleCmd"]},
        "by_symbol": {"CATNoShowAttr": ["SampleCmd"]},
    }


print("=" * 60)
print("  UseCase snippet (offline)")
print("=" * 60)

# Window merge + clip, no disk.
merged = _windows([10, 12, 40], context=2, line_count=100)
ck("windows merge adjacent hits", merged == [(8, 14), (38, 42)], str(merged))
clipped, truncated = _clip_windows([(1, 5), (10, 20)], 8)
ck("clip stops at max_lines", clipped == [(1, 5), (10, 12)] and truncated, str(clipped))
explicit = _windows([], context=2, line_count=100, explicit=_parse_lines("40-90"))
ck("explicit range wins", explicit == [(40, 90)], str(explicit))
ck("single line spec", _parse_lines("12") == (12, 12))
ck("empty line spec", _parse_lines("") is None)

# Path jail.
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    sample = root / "CAASample.edu" / "CAASample.m" / "src"
    sample.mkdir(parents=True)
    src = sample / "SampleCmd.cpp"
    src.write_text(
        "\n".join(f"line {i}" for i in range(1, 31))
        + "\nCATIVisProperties* p = 0;\np->SetPropertiesAtt();\n",
        encoding="utf-8",
    )
    (root / "CAASample.edu" / "CAASample.m" / "Imakefile.mk").write_text(
        "BUILT_OBJECT_TYPE=SHARED LIBRARY\n", encoding="utf-8"
    )
    ck("safe path accepted", _safe_under(root, "CAASample.edu/CAASample.m/src/SampleCmd.cpp") == src.resolve())
    ck("dotdot refused", _safe_under(root, "../secret.cpp") is None)
    ck("absolute refused", _safe_under(root, "/etc/passwd") is None)

    index = _index()
    index["meta"]["caadoc_root"] = str(root)
    r = _FakeRetrieval(index)

    empty = read_snippet(r, SKILL)
    ck("empty query is not_found", empty["status"] == "not_found" and empty["hits"] == [])

    hit = read_snippet(
        r, SKILL,
        interface="CATIVisProperties",
        method="SetPropertiesAtt",
        context=1,
        max_lines=20,
    )
    ck("interface hit is ok", hit["status"] == "ok" and hit["read_only"] is True)
    frag = hit["hits"][0]["fragments"][0]["text"]
    ck("window has line numbers", "SetPropertiesAtt" in frag and "|" in frag)
    ck("does not dump the whole file", hit["hits"][0]["line_count"] == 32 and "line 1" not in frag)

    stem = select_examples(index, example="Other")
    ck("stem disambiguation", len(stem) == 1 and stem[0]["name"] == "Other (Mod.m)")

    pinned_missing = _index()
    pinned_missing["meta"]["caadoc_root"] = ""
    unavailable = read_snippet(_FakeRetrieval(pinned_missing), SKILL, example="SampleCmd")
    ck(
        "pinned missing CAADoc is source_unavailable",
        unavailable["status"] == "source_unavailable" and unavailable["hits"] == [],
    )
    ck(
        "does not fall through to another install",
        "caadoc_root" not in unavailable,
    )

print()
print(f"  {passed}/{total} passed")
raise SystemExit(0 if passed == total else 1)
