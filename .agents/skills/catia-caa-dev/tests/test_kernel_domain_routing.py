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

    # R-05-A: the requirement category must NOT become the late type.
    ck("R-05-A: 'feature' is not forwarded as the late type",
       params.get("target_late_type") is None and "target" not in params,
       f"target_late_type={params.get('target_late_type')} target={params.get('target')}")
    ck("R-05-A: late type state is reported, not guessed",
       params.get("target_late_type_state") == "AMBIGUOUS",
       f"got {params.get('target_late_type_state')}")
    ck("R-05-A: real candidate components are offered for clarification",
       bool(params.get("target_late_type_candidates")),
       f"got {params.get('target_late_type_candidates')}")

    # R-05: Construction Plan steps actually consumed candidate_interfaces, behavior_aspects, target
    steps = plan_visu.get("plan", {}).get("steps", [])
    create_step = next((t for t in steps if t.get("action") == "create_extension"), None)
    ck("Plan contains create_extension step", create_step is not None)
    if create_step:
        step_params = create_step.get("params", {})
        ck("Step params consumed interfaces (CATIVisu)", "CATIVisu" in step_params.get("interfaces", []), f"got {step_params.get('interfaces')}")
        ck("Step params consumed behavior_aspects", "visualization" in step_params.get("behavior_aspects", []), f"got {step_params.get('behavior_aspects')}")
        ck("R-05-A: step target_object is empty, not 'feature'",
           step_params.get("target_object") == "", f"got {step_params.get('target_object')!r}")
        ck("R-05-A: step keeps the requirement category separately",
           step_params.get("target_entity") == "feature", f"got {step_params.get('target_entity')}")

    gen_args = kernel._construction_generation_args(plan_visu)
    ck("Generation args carry CATIVisu", "CATIVisu" in gen_args.get("interfaces", []), f"got {gen_args}")
    ck("R-05-A: generation target is empty, never the category",
       gen_args.get("target_object") == "", f"got {gen_args.get('target_object')!r}")
    ck("R-05-A: generation args expose candidates for the clarification",
       bool(gen_args.get("late_type_candidates")), f"got {gen_args.get('late_type_candidates')}")

    # R-05-A end-to-end: an unresolved late type stops at needs_clarification.
    gate = kernel._extension_late_type_gate(plan_visu, res_visu)
    ck("R-05-A: kernel gate returns needs_clarification for a category target",
       gate is not None and gate.get("status") == "needs_clarification",
       f"got {(gate or {}).get('status')}")
    ck("R-05-A: gate carries real candidate components",
       bool((gate or {}).get("data", {}).get("target_late_type_candidates")),
       f"got {(gate or {}).get('data', {}).get('target_late_type_candidates')}")

    from unittest.mock import MagicMock, patch
    with patch("intents.create_extension", return_value={"status": "error", "message": "stopped-before-apply"}) as mocked:
        exec_visu = kernel._execute_develop_plan(plan_visu, preview=True)
        called = mocked.call_args.kwargs if mocked.called else {}
        ck("Executor calls create_extension", mocked.called, f"status={exec_visu.get('status')}")
        ck("Executor passes CATIVisu as implements", "CATIVisu" in (called.get("implements") or []), f"got {called.get('implements')}")
        ck("R-05-A: executor passes an empty target, not 'feature'",
           called.get("target_object") == "", f"got {called.get('target_object')!r}")
        ck("Executor passes visualization behavior", "visualization" in (called.get("behavior_aspects") or []), f"got {called.get('behavior_aspects')}")

    ctx = MagicMock()
    with patch("intents.objects.validate_module", return_value={"status": "ok"}):
        from intents.objects import create_extension
        visu = create_extension(
            ctx, name="VisuExt", target_object="CAAMmrMeasureSet", module="VisualizationModule.m",
            implements=["CATIVisu", "CATI3DGeoVisu"], behavior_aspects=["visualization"],
        )
        created_blob = "\n".join((visu.get("changeset") or {}).get("created", {}).values())
        ck("R-05: verified visu extension is pending, not an error placeholder",
           visu.get("status") == "pending", f"status={visu.get('status')} message={visu.get('message')}")
        ck("R-05: header derives CATExtIVisu, not CATBaseUnknown Execute",
           "class VisuExt : public CATExtIVisu" in created_blob and "Execute(" not in created_blob,
           "missing CATExtIVisu or still using Execute")
        ck("R-05: cpp binds TIE_CATI3DGeoVisu and the late type",
           "TIE_CATI3DGeoVisu(VisuExt);" in created_blob
           and "CATImplementClass(VisuExt, DataExtension, CATExtIVisu, CAAMmrMeasureSet);" in created_blob,
           "missing TIE or CATImplementClass")
        ck("R-05: BuildRep returns an empty CAT3DBagRep",
           "CAT3DBagRep *bag = new CAT3DBagRep();" in created_blob and "CATIDescendants" not in created_blob)
        ck("R-05: dictionary is the verified three-token line",
           "CAAMmrMeasureSet CATI3DGeoVisu libVisualizationModule" in created_blob)
        ck("R-05: CATIVisu is mapped, not redeclared",
           visu.get("extension", {}).get("interface_binding", {}).get("dictionary_interface") == "CATI3DGeoVisu"
           and '#include "CATIVisu.h"' not in created_blob
           and visu.get("extension", {}).get("b28_compiled") is False)
        ck("R-05: L4/L5 are not claimed by the generator",
           visu.get("extension", {}).get("runtime_registration") == "UNKNOWN"
           and visu.get("extension", {}).get("functional_verification") == "NOT_RUN")

        missing_target = create_extension(
            ctx, name="VisuExt", target_object="", module="VisualizationModule.m",
            implements=["CATIVisu"],
        )
        ck("R-05: empty target_object is error, not pending",
           missing_target.get("status") == "error" and missing_target.get("changeset") is None,
           f"status={missing_target.get('status')}")

        # R-05-A: a requirement category is not a CATIA component. Registering
        # it would emit CATImplementClass(..., DataExtension, CATExtIVisu, feature).
        category_target = create_extension(
            ctx, name="VisuExt", target_object="feature", module="VisualizationModule.m",
            implements=["CATIVisu"],
        )
        ck("R-05-A: requirement category 'feature' is rejected as a late type",
           category_target.get("status") == "error" and category_target.get("changeset") is None
           and "late type" in category_target.get("message", ""),
           f"status={category_target.get('status')} message={category_target.get('message')}")

        from late_type_resolver import LateTypeResolver
        _resolver = LateTypeResolver()
        ck("R-05-A: resolver confirms real components from local evidence",
           _resolver.is_known_late_type("CAAMmrMeasureSet")
           and _resolver.is_known_late_type("CATPart")
           and not _resolver.is_known_late_type("feature")
           and not _resolver.is_known_late_type("component"),
           "late type ground truth mismatch")
        _resolved = _resolver.resolve(
            request="create extension on CAAMmrMeasureSet",
            entity="feature", interfaces=["CATIVisu", "CATI3DGeoVisu"],
        )
        ck("R-05-A: an explicitly named real component resolves CLEAR",
           _resolved["status"] == "CLEAR" and _resolved["late_type"] == "CAAMmrMeasureSet",
           f"got {_resolved['status']}/{_resolved['late_type']}")
        _unresolved = _resolver.resolve(
            request="给特征增加3D表现", entity="feature", interfaces=["CATIVisu"]
        )
        ck("R-05-A: a category with no named component is AMBIGUOUS with candidates",
           _unresolved["status"] == "AMBIGUOUS" and _unresolved["late_type"] is None
           and bool(_unresolved["candidates"]),
           f"got {_unresolved['status']} candidates={_unresolved['candidates'][:3]}")
        ck("R-05-A: offered candidates are all real components",
           all(_resolver.is_known_late_type(c) for c in _unresolved["candidates"]),
           f"got {_unresolved['candidates']}")

        unverified = create_extension(
            ctx, name="EventExt", target_object="CAAMmrMeasureSet", module="VisualizationModule.m",
            implements=["CATIVisu", "CATIModelEvents"],
        )
        ck("R-05: unverified interface is error and does not implement only the first",
           unverified.get("status") == "error" and "CATIModelEvents" in unverified.get("message", ""),
           f"status={unverified.get('status')} message={unverified.get('message')}")

        data_only = create_extension(
            ctx, name="DataExt", target_object="CAAMmrMeasureSet", module="VisualizationModule.m",
            data_members=[{"name": "_length", "type": "double"}],
        )
        ck("R-05: data-only extension does not use the fake Execute component template",
           data_only.get("status") == "error" and "Execute" in data_only.get("message", ""),
           f"status={data_only.get('status')}")

    # R-05-B: the skeleton links CATExtIVisu::BuildRep and new CAT3DBagRep, so
    # the module must link CATVisualization/CATViz/JS0GROUP or it fails at link
    # time (LNK2019) after compiling cleanly.
    import tempfile

    class _StubFramework:
        def __init__(self, root: Path):
            self.root = root

        def dictionary_path(self) -> Path:
            return self.root / "code" / "dictionary" / "Stub.dico"

    class _StubModule:
        def __init__(self, root: Path):
            self.root = root
            self.framework = _StubFramework(root)

        def local_interfaces_dir(self) -> Path:
            d = self.root / "LocalInterfaces"
            d.mkdir(parents=True, exist_ok=True)
            return d

        def src_dir_path(self) -> Path:
            d = self.root / "src"
            d.mkdir(parents=True, exist_ok=True)
            return d

        def imakefile_path(self) -> Path:
            return self.root / "Imakefile.mk"

    class _StubSnapshot:
        def __init__(self, module):
            self._module = module

        def get_module(self, module, framework=None):
            return self._module

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        stub = _StubModule(root)
        # Shape copied from the official B28 sample Imakefile
        # (CAAMmrCCDataExtension.m): a LINK_WITH continuation chain.
        stub.imakefile_path().write_text(
            "BUILT_OBJECT_TYPE = SHARED LIBRARY\n"
            "LINK_WITH = \\\n"
            "            JS0GROUP \\\n"
            "            CATMechanicalModeler\n"
            "LOCAL_CCFLAGS= -DSPECDEBUG\n",
            encoding="utf-8",
        )
        ctx2 = MagicMock()
        ctx2.workspace_root = root
        ctx2.snapshot = _StubSnapshot(stub)
        with patch("intents.objects.validate_module", return_value={"status": "ok"}):
            linked = create_extension(
                ctx2, name="LinkExt", target_object="CAAMmrMeasureSet",
                module="VisualizationModule.m", implements=["CATIVisu"],
            )
            info = linked.get("extension", {})
            modified = (linked.get("changeset") or {}).get("modified", {})
            patched = "".join(str(v) for v in modified.values())
            ck("R-05-B: required libraries are declared as evidence-driven",
               info.get("required_libraries") == ["CATVisualization", "CATViz", "JS0GROUP"],
               f"got {info.get('required_libraries')}")
            ck("R-05-B: LINK_WITH was extended, not silently skipped",
               info.get("link_with_injected") is True, f"got {info.get('link_with_injected')}")
            ck("R-05-B: only the genuinely missing libraries are reported",
               info.get("link_with_added") == ["CATVisualization", "CATViz"],
               f"got {info.get('link_with_added')}")
            ck("R-05-B: patched Imakefile still holds the module's own libraries",
               "JS0GROUP" in patched and "CATMechanicalModeler" in patched,
               f"own libraries were dropped: {patched!r}")
            ck("R-05-B: the variable after LINK_WITH is not swallowed by a stray backslash",
               "LOCAL_CCFLAGS= -DSPECDEBUG" in patched
               and "CATViz" in patched,
               f"LOCAL_CCFLAGS corrupted: {patched!r}")
            ck("R-05-B: LINK_WITH is still the only definition",
               patched.count("LINK_WITH") == 1, f"got {patched.count('LINK_WITH')}")

            from intents.objects import _inject_link_with as _inj
            ck("R-05-B: injection is idempotent on an already-patched file",
               _inj(patched, ("CATVisualization", "CATViz", "JS0GROUP")) is None,
               "second injection was not a no-op")

    # A module with no Imakefile must not be reported as linked.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        stub = _StubModule(root)
        ctx3 = MagicMock()
        ctx3.workspace_root = root
        ctx3.snapshot = _StubSnapshot(stub)
        with patch("intents.objects.validate_module", return_value={"status": "ok"}):
            no_imake = create_extension(
                ctx3, name="NoImakeExt", target_object="CAAMmrMeasureSet",
                module="VisualizationModule.m", implements=["CATIVisu"],
            )
            ck("R-05-B: no Imakefile means link_with_injected is False, not a false claim",
               no_imake.get("extension", {}).get("link_with_injected") is False,
               f"got {no_imake.get('extension', {}).get('link_with_injected')}")


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

# R-06: a matched domain with no construct stays AMBIGUOUS.
# 装配/产品 are context nouns and must not invent a product domain.
# 工程图 is a real drawing-domain hit with no construct type.
unresolved_action_req = "在工程图里进行3D表现，并处理标注"
res_unres = clarifier.analyze(unresolved_action_req)
typed_unres = getattr(res_unres, "typed_requirement", None)
ck("R-06: Unresolved matched domain is not dropped to CLEAR",
   typed_unres is not None and typed_unres.ambiguity_state == "AMBIGUOUS" and "drawing" in typed_unres.unresolved_domains,
   f"state={getattr(typed_unres, 'ambiguity_state', None)} unresolved={getattr(typed_unres, 'unresolved_domains', None)}")

# R-06: Cross-domain target_entity priority aggregation (feature > document > component)
target_prio_req = "在装配体文档中为零件特征增加3D表现"
res_target = clarifier.analyze(target_prio_req)
typed_target = getattr(res_target, "typed_requirement", None)
ck("R-06: Target entity priority selects 'feature' over generic document/component",
   typed_target is not None and typed_target.target_entity == "feature",
   f"target_entity={getattr(typed_target, 'target_entity', None)}")

# R-06: a matched domain with no construct must stay unresolved, not be dropped
unresolved_domain_req = "在工程图里给特征增加3D表现"
res_none = clarifier.analyze(unresolved_domain_req)
typed_none = getattr(res_none, "typed_requirement", None)
ck("R-06: drawing+visualization is multi-domain",
   typed_none is not None and "drawing" in typed_none.matched_domains and "visualization" in typed_none.matched_domains,
   f"domains={getattr(typed_none, 'matched_domains', None)}")
ck("R-06: None construct is recorded, not dropped",
   typed_none is not None and typed_none.domain_constructs.get("drawing") is None,
   f"constructs={getattr(typed_none, 'domain_constructs', None)}")
ck("R-06: unresolved domain is not reported CLEAR",
   typed_none is not None and typed_none.ambiguity_state == "AMBIGUOUS" and typed_none.recommended_intent_type is None,
   f"state={getattr(typed_none, 'ambiguity_state', None)} rec={getattr(typed_none, 'recommended_intent_type', None)}")

# Context nouns must not invent a second domain
context_req = "给零件特征添加3D几何表现和高亮显示"
res_ctx = clarifier.analyze(context_req)
typed_ctx = getattr(res_ctx, "typed_requirement", None)
ck("R-06: 零件/特征 context does not open an unresolved product/part domain",
   typed_ctx is not None and typed_ctx.ambiguity_state == "CLEAR" and "product" not in typed_ctx.matched_domains and "part" not in typed_ctx.matched_domains,
   f"domains={getattr(typed_ctx, 'matched_domains', None)} state={getattr(typed_ctx, 'ambiguity_state', None)}")

# Combination coverage. These use existing keywords; they do not add context nouns.
single_action = clarifier.analyze("给特征增加高亮显示").typed_requirement
ck("R-06: single-domain single-action stays visualization CreateExtension",
   single_action is not None and single_action.is_multi_domain is False
   and single_action.recommended_intent_type == "CreateExtension"
   and single_action.matched_domains == ["visualization"],
   f"domains={getattr(single_action, 'matched_domains', None)} rec={getattr(single_action, 'recommended_intent_type', None)}")

multi_action = clarifier.analyze("对特征着色并高亮显示").typed_requirement
ck("R-06: two visualization actions do not invent a second domain",
   multi_action is not None and multi_action.is_multi_domain is False
   and multi_action.behavior_aspects == ["visualization"],
   f"domains={getattr(multi_action, 'matched_domains', None)} aspects={getattr(multi_action, 'behavior_aspects', None)}")

shared_target = clarifier.analyze("给特征增加3D表现并监听特征变更").typed_requirement
ck("R-06: shared-target multi-domain keeps both behaviors",
   shared_target is not None and shared_target.is_multi_domain is True
   and "visualization" in shared_target.behavior_aspects and "event_listening" in shared_target.behavior_aspects,
   f"aspects={getattr(shared_target, 'behavior_aspects', None)}")

different_targets = clarifier.analyze("给特征增加3D表现，并监听装配结构变化").typed_requirement
ck("R-06: different per-domain targets are retained, not collapsed",
   different_targets is not None
   and different_targets.domain_targets.get("visualization") == "feature"
   and different_targets.domain_targets.get("notification") == "document",
   f"targets={getattr(different_targets, 'domain_targets', None)}")

explicit_command = clarifier.analyze("创建一个命令，用来高亮显示特征").typed_requirement
ck("R-06: explicit construct wins over visualization inference",
   explicit_command is not None and explicit_command.user_explicit_type == "CreateCommand"
   and explicit_command.recommended_intent_type == "CreateCommand"
   and "visualization" in explicit_command.matched_domains,
   f"explicit={getattr(explicit_command, 'user_explicit_type', None)} domains={getattr(explicit_command, 'matched_domains', None)}")

no_construct = clarifier.analyze("打开一张工程图").typed_requirement
ck("R-06: a clear domain without an action does not invent a construct",
   no_construct is not None and "drawing" in no_construct.matched_domains
   and no_construct.ambiguity_state == "AMBIGUOUS" and no_construct.recommended_intent_type is None,
   f"state={getattr(no_construct, 'ambiguity_state', None)} rec={getattr(no_construct, 'recommended_intent_type', None)}")

print("\n" + "=" * 70)
print(f"  Result: {passed}/{total} tests passed ({'ALL PASS' if passed == total else 'SOME FAILED'})")
print("=" * 70)

import unittest


class TestKernelDomainRoutingDiscovery(unittest.TestCase):
    """Formal discovery entry. The checks above already ran at import."""

    def test_script_checks_passed(self):
        self.assertEqual(passed, total)


if __name__ == "__main__" and passed != total:
    sys.exit(1)
