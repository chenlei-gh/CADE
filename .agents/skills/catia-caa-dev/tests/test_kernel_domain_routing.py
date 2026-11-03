#!/usr/bin/env python3
"""
Test P0-1: Business Intent to CAA Construct Domain Routing
===========================================================
Verify that:
1. User-explicit construct keywords have highest priority (never overridden).
2. Business domain requests (visualization, notification, knowledge) correctly route
   to typed constructs (e.g. CreateExtension with CATIVisu) via TypedRequirement.
3. Blind fallback to CreateCommand is completely eliminated.
4. Kernel._build_develop_plan respects TypedRequirement throughout the pipeline.
"""

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from requirements import RequirementsClarifier, TypedRequirement
from kernel import Kernel

total = passed = 0


def ck(label: str, ok: bool, detail: str = ""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    status = "PASS" if ok else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)


print("=" * 70)
print("  Test P0-1: Domain Routing & Elimination of Blind Fallback")
print("=" * 70)

clarifier = RequirementsClarifier()
kernel = Kernel(workspace_root=str(SKILL_ROOT))

# ── 1. Explicit Construct Priority Tests ───────────────────────
print("\n[1] Explicit Construct Keyword Priority")

explicit_cases = [
    ("创建命令 MyVisuCmd 给零件做高亮着色", "CreateCommand", "Explicit command with visu keywords"),
    ("create dialog ColorChooserDialog for visualization", "CreateDialog", "Explicit dialog with visu keywords"),
    ("创建特征 CustomHoleFeature 包含参数定义", "CreateFeature", "Explicit feature with knowledge keywords"),
    ("创建扩展 MyVisuExt 实现零件高亮", "CreateExtension", "Explicit extension"),
    ("create workbench MyCustomWorkbench", "CreateWorkbench", "Explicit workbench"),
]

for req, expected, desc in explicit_cases:
    res = clarifier.analyze(req)
    typed = getattr(res, "typed_requirement", None)
    ck(f"{desc}: clarifier typed_req", typed is not None and typed.user_explicit_type == expected,
       f"got {getattr(typed, 'user_explicit_type', None)}")
    detected = kernel._detect_intent_type(req.lower(), typed_req=typed)
    ck(f"{desc}: kernel detected", detected == expected, f"got {detected}")


# ── 2. Domain & Behavioral Deduction (No Explicit Construct) ───
print("\n[2] Domain-Based Construct Deduction")

domain_cases = [
    # Visualization domain
    ("给零件特征添加3D几何表现和高亮显示", "visualization", "CreateExtension", "Visu requirement -> CreateExtension"),
    ("实现模型对象的着色显示并在3D视图中渲染", "visualization", "CreateExtension", "Color/render -> CreateExtension"),
    ("implement GiveRep to return custom representation", "visualization", "CreateExtension", "GiveRep -> CreateExtension"),
    # Notification domain
    ("监听装配体产品结构变化并在发生改动时触发通知", "notification", "CreateExtension", "Notification -> CreateExtension"),
    ("在零件文档修改时注册回调监听器", "notification", "CreateExtension", "Callback listener -> CreateExtension"),
    # Knowledge domain
    ("为特征对象添加自定义属性参数", "knowledge", "CreateExtension", "Knowledge attribute -> CreateExtension"),
]

for req, exp_domain, exp_intent, desc in domain_cases:
    res = clarifier.analyze(req)
    ck(f"{desc} (domain={res.domain})", res.domain == exp_domain, f"expected {exp_domain}, got {res.domain}")
    typed = getattr(res, "typed_requirement", None)
    ck(f"{desc} (typed_req recommended={getattr(typed, 'recommended_intent_type', None)})",
       typed is not None and typed.recommended_intent_type == exp_intent,
       f"expected {exp_intent}")
    detected = kernel._detect_intent_type(req.lower(), typed_req=typed)
    ck(f"{desc} (kernel intent)", detected == exp_intent, f"expected {exp_intent}, got {detected}")


# ── 3. Elimination of Blind CreateCommand Fallback ─────────────
print("\n[3] Elimination of Blind Fallback")

undetermined_cases = [
    "完全无关的文本无意义字符串 abcxyz_123456789",
    "random gibberish without any caa semantics 987654",
]

for req in undetermined_cases:
    res = clarifier.analyze(req)
    typed = getattr(res, "typed_requirement", None)
    # Detect without typed requirement
    detected_raw = kernel._detect_intent_type(req.lower(), typed_req=None)
    ck(f"Raw detect without keywords returns None: '{req[:20]}...'", detected_raw is None, f"got {detected_raw}")
    # Detect with typed requirement
    detected_typed = kernel._detect_intent_type(req.lower(), typed_req=typed)
    ck(f"Typed detect without keywords returns None: '{req[:20]}...'", detected_typed is None, f"got {detected_typed}")

    # Build plan directly: must return None rather than creating a dummy CreateCommand
    plan = kernel._build_develop_plan(req, clarification=res)
    ck(f"Plan building returns None for undetermined intent", plan is None, f"got {plan}")


# ── 4. End-to-End Plan Generation for Visu Extension ───────────
print("\n[4] End-to-End Plan Generation")

visu_req = "给特征增加3D几何可视化表现 MyVisuExtension in VisualizationModule.m"
res_visu = clarifier.analyze(visu_req)
plan_visu = kernel._build_develop_plan(visu_req, clarification=res_visu)
ck("Visu plan generated", plan_visu is not None)
if plan_visu:
    intent_data = plan_visu.get("intent", {})
    ck("Visu intent is CreateExtension", intent_data.get("type") == "CreateExtension", f"got {intent_data.get('type')}")
    ck("Visu target module extracted", "VisualizationModule.m" in intent_data.get("module", ""), f"got {intent_data.get('module')}")

print("\n" + "=" * 70)
print(f"  Result: {passed}/{total} tests passed ({'ALL PASS' if passed == total else 'SOME FAILED'})")
print("=" * 70)

if passed != total:
    sys.exit(1)
