#!/usr/bin/env python3
"""
Knowledge Retrieval Visibility Suite
====================================
Regression guard for the failure mode this suite was written after:
``analyze()`` answered "Knowledge base searched" with zero hits and
``status=ok``, which is indistinguishable from "the API does not exist".
The agent then walked the SDK by hand instead of trusting the tool.

Contract under test:

  P0 — a zero-hit knowledge search reports ``found=False`` and non-empty
       ``next_steps``; a search that RAISED reports itself as broken
       instead of as a clean empty result. Both survive ``optimize()``.
  P1 — the shipped ``.dic`` index answers existence/attribution for names
       the curated catalog and HeaderMap cannot see (automation-only
       interfaces), and says so in a way that does not imply callability.

No network is required: Jev is optional in every path under test, and the
suite explicitly verifies the deterministic fallback by disabling it.
"""

import os
import sys
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  Knowledge Retrieval Visibility")
print("=" * 60)

from kernel import Kernel, KernelMode  # noqa: E402
from token_optimizer import optimize  # noqa: E402

k = Kernel(workspace_root=".")

# ───────────────────────────────────────────────────────────────
# [1] P0 — zero hit is a verdict, not a success
# ───────────────────────────────────────────────���───────────────
print("\n[1] Zero-hit knowledge search reports found=False")
for query in (
    "如何在CAA中创建场景",
    "爆炸图场景如何在 CAA 中生成",
    "场景怎么生成",
):
    r = k.execute(KernelMode.ANALYZE, query)
    ck(f"{query[:24]} → status not_found", r.get("status") == "not_found", r.get("status", "?"))
    ck(f"{query[:24]} → found is False", r.get("found") is False, str(r.get("found")))
    _steps = r.get("next_steps") or []
    ck(f"{query[:24]} → next_steps non-empty", bool(_steps), f"{len(_steps)} steps")

# The old wording must be gone: it is what made an empty result look fine.
r = k.execute(KernelMode.ANALYZE, "如何在CAA中创建场景")
ck("summary no longer says 'Knowledge base searched'",
   "Knowledge base searched" not in str(r.get("message", "")),
   r.get("message", ""))

# [2] P0 — a positive query must NOT be degraded into not_found
print("\n[2] Positive queries still succeed")
for query, min_refs in (
    ("对话框怎么创建", 5),
    ("how to create a dialog", 5),
    ("装配统计工具怎么做", 3),
):
    r = k.execute(KernelMode.ANALYZE, query)
    refs = len(r.get("references") or [])
    ck(f"{query[:24]} → ok", r.get("status") == "ok", r.get("status", "?"))
    ck(f"{query[:24]} → found True", r.get("found") is True, str(r.get("found")))
    ck(f"{query[:24]} → refs >= {min_refs}", refs >= min_refs, f"{refs} refs")

# [3] P0 — workspace operations are not reclassified as knowledge
print("\n[3] Workspace operations untouched")
for query in ("analyze the workspace", "list modules", "diagnose the workspace"):
    r = k.execute(KernelMode.ANALYZE, query)
    ck(f"{query[:24]} → ok", r.get("status") == "ok", r.get("status", "?"))
    ck(f"{query[:24]} → no knowledge verdict", "found" not in r, str(r.get("found")))

# A workspace request may contain a CAT-named module; it must stay a workspace
# request and must not be answered with a dictionary verdict about the module.
print("\n[3b] CAT-named module is not a dictionary lookup")
for query in ("analyze module CATFoo.m", "list modules in CATTest"):
    r = k.execute(KernelMode.ANALYZE, query)
    ck(f"{query[:24]} → not dic_lookup", r.get("query_type") != "dic_lookup",
       str(r.get("query_type")))
    ck(f"{query[:24]} → no found verdict", "found" not in r, str(r.get("found")))

# [4] P0 — survives the MCP optimizer
print("\n[4] Verdict survives optimize()")
raw = k.execute(KernelMode.ANALYZE, "如何在CAA中创建场景")
opt = optimize(raw)
ck("optimized keeps found=False", opt.get("found") is False, str(opt.get("found")))
_steps = opt.get("next_steps") or []
ck("optimized keeps next_steps", bool(_steps), f"{len(_steps)} steps")
ck("optimized ok is False", opt.get("ok") is False, str(opt.get("ok")))

# [5] P0 — Jev is optional (deterministic fallback)
print("\n[5] Works with Jev disabled")
_saved_key = os.environ.get("TYPESAFE_API_KEY")
_saved_flag = os.environ.get("CADE_JEV")
os.environ["TYPESAFE_API_KEY"] = ""
try:
    k2 = Kernel(workspace_root=".")
    r = k2.execute(KernelMode.ANALYZE, "爆炸图场景如何在 CAA 中生成")
    ck("no-key: zero-hit still reports not_found", r.get("status") == "not_found", r.get("status", "?"))
    ck("no-key: found is False", r.get("found") is False, str(r.get("found")))
    _steps = r.get("next_steps") or []
    ck("no-key: next_steps non-empty", bool(_steps), f"{len(_steps)} steps")
finally:
    if _saved_key is None:
        os.environ.pop("TYPESAFE_API_KEY", None)
    else:
        os.environ["TYPESAFE_API_KEY"] = _saved_key
    if _saved_flag is None:
        os.environ.pop("CADE_JEV", None)
    else:
        os.environ["CADE_JEV"] = _saved_flag

# ───────────────────────────────────────────────────────────────
# [6] P1 — shipped .dic ground truth
# ───────────────────────────────────────────────────────────────
print("\n[6] Shipped .dic answers what the catalog cannot")
r = Kernel(workspace_root=".").execute(KernelMode.ANALYZE, "CATIAScene 是什么")
ck("CATIAScene → ok", r.get("status") == "ok", r.get("status", "?"))
ck("CATIAScene → dic_lookup", r.get("query_type") == "dic_lookup", str(r.get("query_type")))
ck("CATIAScene → found True", r.get("found") is True, str(r.get("found")))
ck("CATIAScene → attributed to CATNewSceneFeat",
   "CATNewSceneFeat" in str(r.get("facts", "")), str(r.get("facts", ""))[:80])
# The load-bearing distinction: present in .dic does NOT mean callable.
ck("CATIAScene → callability caveat present", bool(r.get("caveat")),
   str(r.get("caveat", ""))[:60])
ck("CATIAScene → no public header recorded",
   (r.get("header_presence") or {}).get("CATIAScene", {}).get("public_header") is False,
   str(r.get("header_presence")))

# [7] P1 — absence is also a verdict, with a usable number behind it
print("\n[7] Absent name is reported as absent")
r = Kernel(workspace_root=".").execute(KernelMode.ANALYZE, "CATIThisDoesNotExist 是什么")
ck("unknown name → not_found", r.get("status") == "not_found", r.get("status", "?"))
ck("unknown name → found False", r.get("found") is False, str(r.get("found")))
ck("unknown name → pair count stated",
   (r.get("dic") or {}).get("pairs", 0) > 1000, str(r.get("dic")))
ck("unknown name → next_steps non-empty", bool(r.get("next_steps")),
   f"{len(r.get('next_steps') or [])} steps")

# [8] P1 — a known component is described by what it implements
print("\n[8] Component side of the dictionary")
r = Kernel(workspace_root=".").execute(KernelMode.ANALYZE, "CATFrmEditor 是什么")
ck("CATFrmEditor → ok", r.get("status") == "ok", r.get("status", "?"))
ck("CATFrmEditor → dic_lookup", r.get("query_type") == "dic_lookup", str(r.get("query_type")))
ck("CATFrmEditor → implements interfaces",
   "COMPONENT" in str(r.get("facts", "")), str(r.get("facts", ""))[:80])

# [9] P1 — the index is reachable through the sanctioned facade
print("\n[9] DicIndex via retrieval facade")
from retrieval import get_retrieval  # noqa: E402
_index = get_retrieval(SKILL).dic_index
ck("dic_index loaded", _index.pair_count > 1000, f"{_index.pair_count} pairs")
ck("dic_index version recorded", bool(_index.source_version), _index.source_version)
ck("dic_index knows CATIAScene", _index.is_interface("CATIAScene"))
ck("dic_index rejects fabricated name", not _index.resolve_name("CATIThisDoesNotExist")["known"])
ck("facade health includes dic_index", "dic_index" in get_retrieval(SKILL).health())

print("-" * 60)
print(f"  RESULT: {passed}/{total} passed")
print("=" * 60)
print("KNOWLEDGE VISIBILITY OK" if passed == total else "KNOWLEDGE VISIBILITY FAILED")
sys.exit(0 if passed == total else 1)
