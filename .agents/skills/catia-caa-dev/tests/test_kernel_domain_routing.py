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
from kernel import Kernel, KernelMode, KernelState

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

    # R-01: End-to-end kernel.execute must transition to NEEDS_CLARIFICATION, NOT FAILED / error
    exec_res = kernel.execute(KernelMode.DEVELOP, req)
    ck(f"E2E kernel execution returns needs_clarification: '{req[:20]}...'",
       exec_res.get("status") == "needs_clarification",
       f"got status={exec_res.get('status')}")
    ck(f"Kernel state is CLARIFYING: '{req[:20]}...'",
       kernel._state == KernelState.CLARIFYING,
       f"got state={kernel._state}")


# ── 4. End-to-End Plan Generation for Visu Extension & Semantic Injection (R-05) ───
print("\n[4] End-to-End Plan Generation & Semantic Field Injection")

visu_req = "给特征增加3D几何可视化表现 MyVisuExtension in VisualizationModule.m"
res_visu = clarifier.analyze(visu_req)
plan_visu = kernel._build_develop_plan(visu_req, clarification=res_visu)
ck("Visu plan generated", plan_visu is not None)
if plan_visu:
    intent_data = plan_visu.get("intent", {})
    ck("Visu intent is CreateExtension", intent_data.get("type") == "CreateExtension", f"got {intent_data.get('type')}")
    ck("Visu target module extracted", "VisualizationModule.m" in intent_data.get("module", ""), f"got {intent_data.get('module')}")
    # R-05 checks
    params = intent_data.get("params", {})
    ck("Semantic params injected into Intent: behavior_aspect", params.get("behavior_aspect") == "visualization", f"got {params.get('behavior_aspect')}")
    ck("Semantic params injected into Intent: target_entity", params.get("target_entity") == "feature", f"got {params.get('target_entity')}")
    ck("Semantic candidate_interfaces contains CATIVisu", "CATIVisu" in params.get("candidate_interfaces", []), f"got {params.get('candidate_interfaces')}")
    plan_typed_req = plan_visu.get("typed_requirement", {})
    ck("TypedRequirement present in plan dict", plan_typed_req.get("domain") == "visualization")

    # R-05: Construction Plan steps actually consumed candidate_interfaces, behavior_aspects, target
    steps = plan_visu.get("plan", {}).get("steps", [])
    create_step = next((t for t in steps if t.get("action") == "create_extension"), None)
    ck("Plan contains create_extension step", create_step is not None)
    if create_step:
        step_params = create_step.get("params", {})
        ck("Step params consumed interfaces (CATIVisu)", "CATIVisu" in step_params.get("interfaces", []), f"got {step_params.get('interfaces')}")
        ck("Step params consumed target_object (feature)", step_params.get("target_object") == "feature", f"got {step_params.get('target_object')}")
        ck("Step params consumed behavior_aspects", "visualization" in step_params.get("behavior_aspects", []), f"got {step_params.get('behavior_aspects')}")


# ── 5. Multi-Domain Detection & Disambiguation (R-06) ───────────
print("\n[5] Multi-Domain Detection & Semantic Aggregation")

multi_req = "对装配结构进行3D表现并监听变化"
res_multi = clarifier.analyze(multi_req)
typed_multi = getattr(res_multi, "typed_requirement", None)
ck("Multi-domain detected flag is True", typed_multi is not None and typed_multi.is_multi_domain is True)
ck("Matched domains includes visualization & notification",
   set(["visualization", "notification"]).issubset(set(getattr(typed_multi, "matched_domains", []))),
   f"got {getattr(typed_multi, 'matched_domains', [])}")
ck("Multi-domain aggregates candidate interfaces from both domains",
   "CATIVisu" in getattr(typed_multi, "candidate_interfaces", []) and
   "CATIModelEvents" in getattr(typed_multi, "candidate_interfaces", []),
   f"got {getattr(typed_multi, 'candidate_interfaces', [])}")
ck("Multi-domain aggregates behavior aspects",
   "visualization" in getattr(typed_multi, "behavior_aspects", []) and
   "event_listening" in getattr(typed_multi, "behavior_aspects", []),
   f"got {getattr(typed_multi, 'behavior_aspects', [])}")
ck("Multi-domain compatible construct recommended as CreateExtension",
   getattr(typed_multi, "recommended_intent_type", None) == "CreateExtension",
   f"got {getattr(typed_multi, 'recommended_intent_type', None)}")

# Multi-domain construct conflict without user explicit keywords -> AMBIGUOUS
conflict_req = "统计零件结构并为模型自定义属性参数"
res_conflict = clarifier.analyze(conflict_req)
typed_conflict = getattr(res_conflict, "typed_requirement", None)
ck("Multi-domain construct conflict returns AMBIGUOUS",
   typed_conflict is not None and typed_conflict.ambiguity_state == "AMBIGUOUS",
   f"state={getattr(typed_conflict, 'ambiguity_state', None)}")

# R-06: Multi-domain with unresolved action domain alongside action domain -> AMBIGUOUS (not silently dropped to CLEAR)
unresolved_action_req = "对装配结构进行3D表现，并处理产品结构"
res_unres = clarifier.analyze(unresolved_action_req)
typed_unres = getattr(res_unres, "typed_requirement", None)
ck("R-06: Unresolved parallel action domain triggers AMBIGUOUS",
   typed_unres is not None and typed_unres.ambiguity_state == "AMBIGUOUS",
   f"state={getattr(typed_unres, 'ambiguity_state', None)}")

# R-06: Cross-domain target_entity priority aggregation (feature > document > component)
target_prio_req = "在装配体文档中为零件特征增加3D表现"
res_target = clarifier.analyze(target_prio_req)
typed_target = getattr(res_target, "typed_requirement", None)
ck("R-06: Target entity priority selects 'feature' over generic document/component",
   typed_target is not None and typed_target.target_entity == "feature",
   f"target_entity={getattr(typed_target, 'target_entity', None)}")

print("\n" + "=" * 70)
print(f"  Result: {passed}/{total} tests passed ({'ALL PASS' if passed == total else 'SOME FAILED'})")
print("=" * 70)

if passed != total:
    sys.exit(1)
