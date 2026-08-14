#!/usr/bin/env python3
"""
UI Generator Clarifier Contract Tests
======================================
Verify UIGeneratorClarifier 4-axis clarification policy.

The four axes (selection_cardinality / behavior_target / commit_timing /
value_dependency) must behave as a "gap detector", not a question
generator: ask only when intent under-specifies behavior AND domain /
API / convention cannot safely disambiguate.

Cases A~I mirror the already-validated dry-run matrix from
docs/architecture/UI_GENERATOR_CLARIFICATION_POLICY.md.
"""

import sys
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from requirements import ClarificationResult, UIGeneratorClarifier

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  UI Generator Clarifier Tests (A~I)")
print("=" * 60)

clarifier = UIGeneratorClarifier()

# (name, intent, expected_unresolved_count, expected_axis_ids)
CASES = [
    ("A", "选择多个 Body，选择结果只保存在当前 UI 中；按 Category 筛选 PartName；用户点击 Apply 后，将修改后的实例名写回 CATIA。",
     0, None),
    ("B", "选择 Body，按 Category 筛选 PartName，编辑实例名，点击 Apply。",
     2, {"selection_cardinality", "behavior_target"}),
    ("C", "做一个 BOM 面板，可以选择零件、改名字和颜色。",
     3, {"selection_cardinality", "behavior_target", "commit_timing"}),
    ("D", "做一个按钮，把当前零件背景设为白色。",
     1, {"commit_timing"}),
    ("E", "做一个面板，选择零件类型和零件号，点击确定后保存。",
     1, {"behavior_target"}),
    ("F", "做一个 BOM 面板，显示当前装配体的零件名称、数量、材料和颜色，不允许编辑。",
     0, None),
    ("G", "做一个零件转换向导。第一步选择要转换的 Body，可以选择多个；第二步设置目标参数；点击下一步进入预览；最后点击完成执行转换，并显示转换进度。",
     0, None),
    ("H", "选择一个零件，将修改后的名称立即写回 CATIA。",
     0, None),
    ("I", "选择多个零件，按类别筛选零件名称，点击 Apply 后仅更新 UI 预览。",
     0, None),
]

for name, text, expected_count, expected_ids in CASES:
    print(f"\n[{name}] {text}")
    result = clarifier.analyze(text)
    ck(f"{name} returns ClarificationResult", isinstance(result, ClarificationResult))

    unresolved = result.unresolved if isinstance(result, ClarificationResult) else []
    ids = {d.id for d in unresolved}

    ck(f"{name} unresolved count == {expected_count}",
       len(unresolved) == expected_count,
       f"got {len(unresolved)}: {sorted(ids)}")

    if expected_ids is not None:
        ck(f"{name} unresolved ids == {sorted(expected_ids)}",
           ids == expected_ids,
           f"got {sorted(ids)}")

# Also verify the value_dependency axis stays silent in the MVP.
print("\n[VALUE_DEP] 联动信号不产出 Decision（MVP）")
dep_result = clarifier.analyze("按 Category 筛选 PartName。")
ck("筛选信号不触发 value_dependency",
   all(d.id != "value_dependency" for d in dep_result.unresolved),
   f"unresolved={[d.id for d in dep_result.unresolved]}")

# Domain context upstream resolution (J/K/L).
print("\n[DOMAIN_CTX] field_targets / value_dependencies upstream resolution")

# J: field_targets pre-resolves the behavior target, leaving only cardinality.
j = clarifier.analyze(
    "选择 Body，按 Category 筛选 PartName，编辑实例名，点击 Apply。",
    domain_context={"field_targets": {"实例名": "catia"}},
)
j_ids = {d.id for d in j.unresolved}
ck("J field_targets disambiguates behavior_target",
   len(j.unresolved) == 1 and "behavior_target" not in j_ids,
   f"unresolved={sorted(j_ids)}")
ck("J only selection_cardinality remains",
   j_ids == {"selection_cardinality"},
   f"got {sorted(j_ids)}")

# K: partial field_targets (missing 颜色) does NOT disambiguate.
k = clarifier.analyze(
    "做一个 BOM 面板，可以选择零件、改名字和颜色。",
    domain_context={"field_targets": {"名字": "catia"}},
)
k_ids = {d.id for d in k.unresolved}
ck("K partial field_targets still triggers behavior_target",
   len(k.unresolved) == 3 and "behavior_target" in k_ids,
   f"unresolved={sorted(k_ids)}")

# L: value_dependencies resolve into ``resolved``, never into a Decision.
l = clarifier.analyze(
    "选择 Category 和 PartName。",
    domain_context={"value_dependencies": [{"source": "category", "targets": ["partname"]}]},
)
ck("L value_dependency resolved into resolved",
   l.resolved.get("value_dependency") == "dependent",
   f"resolved={l.resolved}")
ck("L no unresolved decisions",
   len(l.unresolved) == 0,
   f"unresolved={[d.id for d in l.unresolved]}")

print(f"\n{'=' * 60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'=' * 60}")

if passed != total:
    sys.exit(1)
