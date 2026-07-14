#!/usr/bin/env python3
"""
Multi-Intent Decomposition Tests
==================================
Validates compound request splitting into independent sub-intents.

Run: python test_multi_intent.py
"""

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from requirements import MultiIntentDecomposer, SubIntent
from kernel import Kernel, KernelMode

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    s = "PASS" if ok else "FAIL"
    print(f"  [{s}] {label}" + (f" — {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════════
# 1. Single Intent — No Decomposition
# ═══════════════════════════════════════════════════════════════
print("=" * 70)
print("  1. Single Intent — No Decomposition")
print("=" * 70)

md = MultiIntentDecomposer()

for req, expected_domain in [
    ("create command ExportBOM in MyModule", "general"),
    ("export BOM to CSV", "product"),
    ("check fillet radius", "part"),
    ("create a dialog", "ui"),
]:
    results = md.decompose(req)
    check(f"single: {req[:40]}", len(results) == 1, f"got {len(results)}")
    if results:
        check(f"  has goal", bool(results[0].goal))
        check(f"  has description", bool(results[0].description))

# ═══════════════════════════════════════════════════════════════
# 2. Compound Request — CN Connectors
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  2. Compound Request — Chinese Connectors")
print("=" * 70)

compound_cases = [
    ("导出BOM并自动着色", ["export", "color"], 2),
    ("做装配统计工具，包含导出BOM和自动着色", ["统计", "导出", "着色"], 3),
    ("检查圆角并检查孔径", ["检查", "检查"], 2),
    ("创建对话框同时创建右键菜单", ["对话框", "菜单"], 2),
    ("曲面分析以及工程图标注", ["曲面", "工程图"], 2),
]

for req, keywords, expected_min in compound_cases:
    results = md.decompose(req)
    check(f"compound: {req[:40]}", len(results) >= expected_min,
          f"expected >= {expected_min}, got {len(results)}")
    for i, r in enumerate(results):
        check(f"  sub[{i}] has goal", bool(r.goal), r.goal[:40])

# ═══════════════════════════════════════════════════════════════
# 3. Compound Request — EN Connectors
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  3. Compound Request — English Connectors")
print("=" * 70)

en_cases = [
    ("export BOM and also auto color parts", 2),
    ("check fillets plus check holes", 2),
]

for req, expected_min in en_cases:
    results = md.decompose(req)
    check(f"EN compound: {req[:40]}", len(results) >= expected_min,
          f"got {len(results)}")

# ═══════════════════════════════════════════════════════════════
# 4. Domain Inference
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  4. Domain Inference")
print("=" * 70)

domain_cases = [
    ("导出BOM到Excel", "product"),
    ("自动着色所有零件", "product"),
    ("检查圆角半径", "part"),
    ("生成工程图", "drawing"),
    ("曲面展平分析", "surface"),
    ("创建设置对话框", "ui"),
    ("无明确领域的关键词", ""),
]

for text, expected in domain_cases:
    domain = md._infer_domain(text)
    check(f"domain: {text[:20]}", domain == expected, f"got '{domain}'")

# ═══════════════════════════════════════════════════════════════
# 5. Edge Cases
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  5. Edge Cases")
print("=" * 70)

edge_cases = [
    ("", 0, "empty request"),
    ("a", 1, "too short"),
    ("   ", 0, "whitespace only"),
    ("做一个工具", 1, "vague but valid"),
]

for req, expected, label in edge_cases:
    results = md.decompose(req)
    check(f"edge: {label}", len(results) == expected, f"got {len(results)}")

# ═══════════════════════════════════════════════════════════════
# 6. Kernel Multi-Intent Integration
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  6. Kernel Multi-Intent Integration")
print("=" * 70)

import tempfile, shutil

ws = Path(tempfile.mkdtemp(prefix="cade_mi_"))
fw = ws / "TestFW.edu"
fw.mkdir(parents=True)
(fw / "IdentityCard.h").write_text("// IC\n", encoding="utf-8")
mod = fw / "TestModule.m"
mod.mkdir()
(mod / "src").mkdir()
(mod / "LocalInterfaces").mkdir()
(mod / "PublicInterfaces").mkdir()
(mod / "Imakefile.mk").write_text(
    "SOURCES =\nLINK_WITH =\nBUILT_OBJECT_TYPE = SHARED_LIBRARY\n",
    encoding="utf-8",
)

k = Kernel(workspace_root=str(ws))

# Single intent — normal path
r = k.execute(KernelMode.DEVELOP, "create command TestCmd in TestModule.m TestFW.edu")
check("single: returns ok/pending", r["status"] in ("ok", "pending"), r["status"])

# Compound intent — multi path
r2 = k.execute(KernelMode.DEVELOP, "export BOM and auto color parts in TestModule.m TestFW.edu")
check("compound: status not error", r2["status"] != "error", r2["status"])
check("compound: has results", "results" in r2)
check("compound: multi_intent flag", r2.get("multi_intent") or r2["status"] == "partial")

shutil.rmtree(ws, ignore_errors=True)

# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"  MULTI-INTENT: {passed}/{total}")
if total:
    print(f"  Pass rate: {passed / total * 100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> All multi-intent tests passed <<<")
    sys.exit(0)
else:
    print(f"\n  >>> {total - passed} failure(s) <<<")
    sys.exit(1)
