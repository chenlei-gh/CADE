"""
CAA Requirements Clarifier
===========================
Converts vague user requests into structured RequirementDocuments
through decision trees and clarifying questions.

Design principle:
  Never generate code until requirements are fully specified.
  Each decision eliminates one dimension of ambiguity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Decision ─────────────────────────────────────────────────────


@dataclass
class Decision:
    """A single decision point in the requirements process"""
    id: str
    question: str
    options: List[str]
    default: str = ""
    resolved_value: str = ""

    def has_resolved(self) -> bool:
        return bool(self.resolved_value)

    def resolve(self, value: str) -> None:
        if value in self.options:
            self.resolved_value = value
        else:
            raise ValueError(f"Invalid option '{value}' for decision '{self.id}'. "
                           f"Valid options: {self.options}")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "question": self.question,
            "options": self.options,
            "default": self.default,
            "resolved": self.resolved_value,
        }


# ─── RequirementDocument ──────────────────────────────────────────


@dataclass
class RequirementDocument:
    """Structured requirements document — the output of clarification"""
    goal: str
    domain: str = ""
    decisions: Dict[str, str] = field(default_factory=dict)
    unresolved: List[Decision] = field(default_factory=list)

    def has_unresolved(self) -> bool:
        return len(self.unresolved) > 0

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "domain": self.domain,
            "decisions": self.decisions,
            "unresolved": [d.to_dict() for d in self.unresolved],
            "unresolved_count": len(self.unresolved),
        }


@dataclass
class TypedRequirement:
    """Structured CAA requirement bridging business intent to construction plan."""
    domain: str = "unknown"
    target_entity: str = "unknown"       # feature | component | document | workbench | unknown
    behavior_aspect: str = "unknown"     # visualization | event_listening | attribute | interaction | unknown
    behavior_aspects: List[str] = field(default_factory=list) # multi-domain behavior aspects
    extension_point: str = "unknown"     # interface_implementation | command_action | dialog_ui | unknown
    user_explicit_type: Optional[str] = None  # CreateCommand | CreateDialog | ... (word-level explicit)
    ambiguity_state: str = "UNKNOWN"     # CLEAR | AMBIGUOUS | UNKNOWN
    recommended_intent_type: Optional[str] = None
    candidate_interfaces: List[str] = field(default_factory=list)
    matched_domains: List[str] = field(default_factory=list)
    is_multi_domain: bool = False
    # Per-domain construct recommendation. None is preserved; it must not be dropped.
    domain_constructs: Dict[str, Optional[str]] = field(default_factory=dict)
    unresolved_domains: List[str] = field(default_factory=list)
    domain_targets: Dict[str, str] = field(default_factory=dict)
    # CATIA late type the extension is registered against. Distinct from
    # target_entity, which is a requirement category (feature/component/...).
    # None means "not established from local evidence" — generation must stop.
    target_late_type: Optional[str] = None
    target_late_type_state: str = "UNKNOWN"   # CLEAR | AMBIGUOUS | UNKNOWN
    target_late_type_candidates: List[str] = field(default_factory=list)
    target_late_type_reason: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "target_entity": self.target_entity,
            "target_late_type": self.target_late_type,
            "target_late_type_state": self.target_late_type_state,
            "target_late_type_candidates": self.target_late_type_candidates,
            "target_late_type_reason": self.target_late_type_reason,
            "behavior_aspect": self.behavior_aspect,
            "behavior_aspects": self.behavior_aspects,
            "extension_point": self.extension_point,
            "user_explicit_type": self.user_explicit_type,
            "ambiguity_state": self.ambiguity_state,
            "recommended_intent_type": self.recommended_intent_type,
            "candidate_interfaces": self.candidate_interfaces,
            "matched_domains": self.matched_domains,
            "is_multi_domain": self.is_multi_domain,
            "domain_constructs": self.domain_constructs,
            "unresolved_domains": self.unresolved_domains,
            "domain_targets": self.domain_targets,
            "notes": self.notes,
        }


# ─── ClarificationResult ──────────────────────────────────────────


@dataclass
class ClarificationResult:
    """Result of requirements clarification — may have unresolved decisions"""
    status: str = "needs_clarification"
    domain: str = ""
    goal: str = ""
    resolved: Dict[str, str] = field(default_factory=dict)
    unresolved: List[Decision] = field(default_factory=list)
    typed_requirement: Optional[TypedRequirement] = None

    def to_dict(self) -> dict:
        d = {
            "status": self.status,
            "domain": self.domain,
            "goal": self.goal,
            "resolved": self.resolved,
            "questions": [
                {
                    "id": d.id,
                    "question": d.question,
                    "options": d.options,
                    "default": d.default,
                }
                for d in self.unresolved
            ],
        }
        if self.typed_requirement:
            d["typed_requirement"] = self.typed_requirement.to_dict()
        return d


# ─── RequirementsClarifier ────────────────────────────────────────


class RequirementsClarifier:
    """
    Converts vague user requests into structured requirements.

    Uses domain detection + decision trees to identify what needs
    to be clarified. Returns ClarificationResult with up to 5
    unresolved questions.
    """

    MAX_QUESTIONS = 5

    # Domain detection keywords
    DOMAIN_KEYWORDS = {
        # Object nouns such as 装配/零件/特征/视图 are context, not a second
        # unresolved action. Matching them created false multi-domain hits that
        # were then dropped. Keep task words only.
        "product": ["assembly", "product", "bom", "catproduct", "物料清单", "物料",
                     "统计", "导出", "export", "statistics"],
        "part": ["fillet", "hole", "chamfer", "pad", "pocket",
                 "圆角", "孔", "倒角", "check", "检查"],
        "drawing": ["drawing", "sheet", "annotation", "dimension", "工程图",
                     "图纸", "标注"],
        "surface": ["surface", "gsd", "extrude", "sweep", "flatten", "offset",
                     "曲面", "拉伸", "扫掠", "展平"],
        "ui": ["dialog", "command", "toolbar", "menu", "workbench", "对话框",
                "命令", "菜单", "工作台", "工具栏"],
        "fta": ["fta", "3d annotation", "pmi", "tolerance", "gd&t", "3d标注",
                 "公差", "基准", "capture"],
        "visualization": ["visu", "visualization", "color", "rep", "highlight", "material",
                          "着色", "高亮", "显示", "表现", "材质", "cativisu"],
        "notification": ["event", "callback", "listener", "notification", "dispatch",
                         "监听", "回调", "事件", "通知", "变更", "结构变化"],
        "knowledge": ["parameter", "attribute", "relation", "formula", "cke", "userparameter",
                      "参数", "属性", "公式", "知识", "自定义属性"],
    }

    def analyze(self, request: str) -> ClarificationResult:
        """
        Analyze a natural language request and identify what needs clarification.

        Args:
            request: Natural language request from user/AI

        Returns:
            ClarificationResult with resolved decisions and unresolved questions
        """
        if not request or not request.strip():
            return ClarificationResult(
                domain="unknown",
                goal="unspecified",
                unresolved=[
                    Decision(id="goal", question="What would you like to do?",
                             options=["create a command", "export data",
                                      "analyze workspace", "run diagnostics"]),
                ],
            )

        request_lower = request.lower()

        # Step 1: Detect domain(s)
        matched_domains_scored = self._detect_domains(request_lower)
        matched_domains = [d for d, _ in matched_domains_scored]
        is_multi_domain = len(matched_domains) > 1
        domain = matched_domains[0] if matched_domains else "general"

        # Step 2: Detect goal
        goal = self._detect_goal(request_lower)

        # Step 3: Build decisions based on domain
        resolved = {}
        unresolved = []

        if domain == "product":
            resolved, unresolved = self._clarify_product(request_lower)
        elif domain == "part":
            resolved, unresolved = self._clarify_part(request_lower)
        elif domain == "drawing":
            resolved, unresolved = self._clarify_drawing(request_lower)
        elif domain == "surface":
            resolved, unresolved = self._clarify_surface(request_lower)
        elif domain == "ui":
            resolved, unresolved = self._clarify_ui(request_lower)

        # Step 4: Build TypedRequirement bridging business domain to CAA constructs
        typed_req = self._build_typed_requirement(
            request, domain, goal,
            matched_domains=matched_domains,
            is_multi_domain=is_multi_domain,
        )

        # Step 4.5: Resolve the CATIA late type for extension intents.
        # target_entity is a requirement category; the dictionary and
        # CATImplementClass need a component that really exists.
        self._resolve_late_type(typed_req, request)

        # If the request is already clear enough with clear construct mapping
        if self._is_clear_command(request_lower) and typed_req.ambiguity_state == "CLEAR":
            return ClarificationResult(
                status="ok",
                domain=domain,
                goal=goal,
                resolved=resolved,
                unresolved=[],
                typed_requirement=typed_req,
            )

        # UI Generator 4-axis clarification (behavior target / commit timing /
        # value dependency / selection cardinality). Domain-agnostic: triggers
        # only on selection/edit/constraint signals, so non-UI requests pass
        # through unchanged.
        ui_result = UIGeneratorClarifier().analyze(request)
        resolved.update(ui_result.resolved)
        unresolved.extend(ui_result.unresolved)

        # Provide candidate paths when ambiguity remains and no decisions are open
        if not unresolved and typed_req.ambiguity_state in ("UNKNOWN", "AMBIGUOUS"):
            if typed_req.ambiguity_state == "UNKNOWN":
                unresolved.append(Decision(
                    id="construct_intent",
                    question=f"无法从输入推断目标 CAA 构件或操作类型: '{request}'。请澄清目标实现形式：",
                    options=["CreateCommand (创建独立命令)", "CreateExtension (扩展已有对象)", "CreateDialog (创建对话框界面)", "CreateFeature (创建特征定义)"],
                    default="CreateCommand (创建独立命令)",
                ))
            elif typed_req.ambiguity_state == "AMBIGUOUS":
                unresolved.append(Decision(
                    id="action_intent",
                    question=f"请求所属领域为 [{domain}]，但未指定具体动作或构件形式。请选择拟实施路径：",
                    options=["CreateCommand (创建领域操作命令)", "CreateExtension (实现领域接口扩展)"],
                    default="CreateCommand (创建领域操作命令)",
                ))

        # A resolved construct still cannot be generated when the extension
        # target is not a real component. Ask for a concrete late type rather
        # than emitting CATImplementClass for a requirement category.
        self._ask_for_late_type(typed_req, request, unresolved)

        # Limit unresolved questions
        unresolved = unresolved[:self.MAX_QUESTIONS]

        if unresolved or typed_req.ambiguity_state in ("UNKNOWN", "AMBIGUOUS"):
            return ClarificationResult(
                status="needs_clarification",
                domain=domain,
                goal=goal,
                resolved=resolved,
                unresolved=unresolved,
                typed_requirement=typed_req,
            )
        else:
            return ClarificationResult(
                status="ok",
                domain=domain,
                goal=goal,
                resolved=resolved,
                unresolved=[],
                typed_requirement=typed_req,
            )

    # ─── Late Type Resolution ───────

    def _ask_for_late_type(self, typed: "TypedRequirement", request: str, unresolved: List[Decision]) -> None:
        """Add one clarification decision when the extension target is unknown.

        Only for extension intents whose construct is otherwise resolved: a
        missing late type is the last thing standing between the plan and a
        real dictionary registration.
        """
        if typed is None or typed.recommended_intent_type != "CreateExtension":
            return
        if typed.target_late_type_state == "CLEAR":
            return
        if any(d.id == "target_late_type" for d in unresolved):
            return
        candidates = typed.target_late_type_candidates or []
        if not candidates:
            candidates = ["（无本地证据候选，请指定已安装的 CAA 组件名）"]
        unresolved.append(Decision(
            id="target_late_type",
            question=(
                f"扩展需要注册到真实 CATIA 组件（late type），但 '{typed.target_entity}' "
                f"是需求分类而非组件名（{typed.target_late_type_reason or '未解析'}）。"
                "请指定扩展的目标组件："
            ),
            options=candidates,
            default=candidates[0] if candidates else "",
        ))

    def _resolve_late_type(self, typed: "TypedRequirement", request: str) -> None:
        """Attach the real late type an extension would register against.

        Only extension intents need it: they emit CATImplementClass and a
        dictionary line, both of which must name a component that exists.
        Other constructs (command/dialog/workbench/module) do not register an
        extension target, so their state stays UNKNOWN by construction rather
        than being silently marked CLEAR.
        """
        if typed is None:
            return
        construct = typed.recommended_intent_type or typed.user_explicit_type
        if construct != "CreateExtension":
            typed.target_late_type_state = "NOT_APPLICABLE"
            typed.target_late_type_reason = f"construct_{construct or 'unknown'}_has_no_extension_target"
            return

        try:
            from late_type_resolver import LateTypeResolver
        except ImportError:
            typed.target_late_type_state = "UNKNOWN"
            typed.target_late_type_reason = "late_type_resolver_unavailable"
            return

        resolver = LateTypeResolver()
        result = resolver.resolve(
            request=request,
            entity=typed.target_entity,
            interfaces=typed.candidate_interfaces,
        )
        typed.target_late_type_state = result["status"]
        typed.target_late_type = result.get("late_type")
        typed.target_late_type_candidates = list(result.get("candidates") or [])
        typed.target_late_type_reason = result.get("reason", "")
        if result["status"] == "CLEAR":
            typed.notes.append(
                f"Late type resolved to {typed.target_late_type} ({result['reason']})."
            )
        else:
            typed.notes.append(
                f"Late type {result['status']} ({result.get('reason')}): "
                f"target_entity '{typed.target_entity}' is not a component name. "
                f"Candidates: {typed.target_late_type_candidates}"
            )

    # ─── Domain Detection ──────────────────────────────────────

    def _detect_domains(self, request: str) -> List[Tuple[str, int]]:
        """Detect all matched CAA domains with scores, sorted descending."""
        scores = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in request)
            if score > 0:
                scores[domain] = score

        if not scores:
            return []

        # Sort by score descending
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def _detect_domain(self, request: str) -> str:
        """Detect primary CAA domain from request keywords"""
        scored = self._detect_domains(request)
        if not scored:
            return "general"
        return scored[0][0]

    def _detect_goal(self, request: str) -> str:
        """Extract the primary goal from the request"""
        # Extract first meaningful sentence or phrase
        goals = {
            "create": "create" in request,
            "export": "export" in request or "导出" in request,
            "analyze": "analyze" in request or "分析" in request or "diagnos" in request,
            "check": "check" in request or "检查" in request or "验证" in request,
            "fix": "fix" in request or "repair" in request or "修复" in request,
            "statistics": "statistic" in request or "统计" in request,
            "visualize": "visualiz" in request or "color" in request or "着色" in request or "高亮" in request or "表现" in request,
            "notify": "listen" in request or "callback" in request or "监听" in request or "回调" in request or "通知" in request,
            "attribute": "attribute" in request or "param" in request or "属性" in request or "参数" in request,
        }
        for goal, found in goals.items():
            if found:
                return goal
        return request[:50]  # truncate

    def _build_typed_requirement(
        self,
        request: str,
        domain: str,
        goal: str,
        matched_domains: Optional[List[str]] = None,
        is_multi_domain: bool = False,
    ) -> TypedRequirement:
        """Construct TypedRequirement from request, domain, and goal."""
        req_lower = request.lower()

        # 1. Check explicit component keywords (Highest Priority - never override user intent)
        # Note: "feature" is both a CAA construct (CreateFeature) and a CAD target entity (Pad/Pocket/Feature).
        # When preceded by target prepositions (给/为/对/针对/面向/for/to/on) or paired with visualization/attributes,
        # it denotes the target entity rather than the intent to create a feature construct.
        is_target_feature = any(p in req_lower for p in (
            "给零件特征", "给特征", "为特征", "对特征", "针对特征", "面向特征",
            "for feature", "to feature", "on feature", "in feature"
        )) or (domain in ("visualization", "notification") and not any(k in req_lower for k in ("创建特征", "新建特征", "create feature", "make feature")))

        explicit_mapping = [
            (("对话框", "dialog"), "CreateDialog"),
            (("命令", "command"), "CreateCommand"),
            (("特征", "feature"), "CreateFeature"),
            (("扩展", "extension"), "CreateExtension"),
            (("接口", "interface"), "CreateInterface"),
            (("工作台", "workbench"), "CreateWorkbench"),
            (("组件", "component"), "CreateComponent"),
            (("模块", "module"), "CreateModule"),
            (("框架", "framework"), "CreateFramework"),
        ]
        user_explicit = None
        for keywords, itype in explicit_mapping:
            if itype == "CreateFeature" and is_target_feature:
                continue
            if any(k in req_lower for k in keywords):
                user_explicit = itype
                break

        typed = TypedRequirement(
            domain=domain,
            user_explicit_type=user_explicit,
            matched_domains=matched_domains or ([domain] if domain != "general" else []),
            is_multi_domain=is_multi_domain,
        )

        if is_multi_domain and matched_domains:
            typed.notes.append(f"Multiple domains detected: {matched_domains}")

        # 2. Enrich semantic domain attributes (with multi-domain aggregation)
        all_domains = matched_domains if matched_domains else ([domain] if domain != "general" else [])
        collected_interfaces = []
        collected_aspects = []
        domain_recommended_types = {}

        def _resolve_single_domain_attributes(d_name: str):
            aspect = "unknown"
            target = "component"
            ext_pt = "unknown"
            ifaces = []
            rec_type = None

            if d_name == "visualization":
                aspect = "visualization"
                target = "feature" if ("feature" in req_lower or "特征" in req_lower) else "component"
                ext_pt = "interface_implementation"
                ifaces = ["CATIVisu", "CATI3DGeoVisu"]
                rec_type = "CreateExtension"
            elif d_name == "notification":
                aspect = "event_listening"
                target = "document" if any(k in req_lower for k in ("document", "product", "文档", "结构", "装配")) else "component"
                ext_pt = "interface_implementation"
                ifaces = ["CATIModelEvents", "CATIEventSubscriber"]
                rec_type = "CreateExtension"
            elif d_name == "knowledge":
                aspect = "attribute"
                target = "feature"
                ext_pt = "interface_implementation"
                ifaces = ["CATIValue", "CATIParmPublisher"]
                if any(k in req_lower for k in ("创建特征", "新建特征", "create feature", "make feature")):
                    rec_type = "CreateFeature"
                else:
                    rec_type = "CreateExtension"
            elif d_name == "ui":
                aspect = "interaction"
                if any(k in req_lower for k in ("dialog", "对话框", "界面")):
                    ext_pt = "dialog_ui"
                    ifaces = ["CATDlgDialog"]
                    rec_type = "CreateDialog"
                else:
                    ext_pt = "command_action"
                    ifaces = ["CATCommand"]
                    rec_type = "CreateCommand"
            elif d_name in ("product", "part", "drawing", "surface"):
                if any(k in req_lower for k in ("export", "导出", "统计", "statistic", "check", "检查", "analyze", "分析", "生成", "计算")):
                    aspect = "interaction"
                    ext_pt = "command_action"
                    rec_type = "CreateCommand"
                else:
                    rec_type = None  # ambiguous
            return aspect, target, ext_pt, ifaces, rec_type

        # Primary domain baseline
        pri_aspect, pri_target, pri_ext_pt, pri_ifaces, pri_rec = _resolve_single_domain_attributes(domain)
        typed.behavior_aspect = pri_aspect
        typed.target_entity = pri_target
        typed.extension_point = pri_ext_pt

        # Aggregate across all matched domains
        for d in all_domains:
            asp, tgt, ext, ifs, rt = _resolve_single_domain_attributes(d)
            if asp != "unknown" and asp not in collected_aspects:
                collected_aspects.append(asp)
            for iface in ifs:
                if iface not in collected_interfaces:
                    collected_interfaces.append(iface)
            domain_recommended_types[d] = rt

        typed.behavior_aspects = collected_aspects if collected_aspects else ([pri_aspect] if pri_aspect != "unknown" else [])
        typed.candidate_interfaces = collected_interfaces if collected_interfaces else pri_ifaces
        # Preserve None. Dropping it is what let a single resolved domain look CLEAR.
        typed.domain_constructs = dict(domain_recommended_types)
        typed.unresolved_domains = [d for d, rt in domain_recommended_types.items() if rt is None]
        typed.domain_targets = {
            d: _resolve_single_domain_attributes(d)[1] for d in all_domains
        }
        distinct_targets = {target for target in typed.domain_targets.values() if target}
        if len(distinct_targets) > 1:
            typed.notes.append(
                "Per-domain targets differ and are retained in domain_targets: "
                f"{typed.domain_targets}. target_entity remains the priority aggregate."
            )

        # Target entity aggregation across domains (Priority: feature > document/product > component)
        all_targets = [tgt for _, tgt, _, _, _ in [_resolve_single_domain_attributes(d) for d in all_domains]]
        if "feature" in all_targets or ("feature" in req_lower or "特征" in req_lower):
            typed.target_entity = "feature"
        elif "document" in all_targets or any(k in req_lower for k in ("document", "product", "文档", "结构", "装配")):
            typed.target_entity = "document"
        elif pri_target != "component":
            typed.target_entity = pri_target
        else:
            typed.target_entity = "component"

        if user_explicit:
            typed.ambiguity_state = "CLEAR"
            typed.recommended_intent_type = user_explicit
            typed.notes.append(f"Explicit construct keyword matched: {user_explicit}")
            return typed

        # 3. Domain-driven Typed Requirement inference (when user did NOT specify a construct)
        # R-06 fix: Handle multi-domain compatibility, unresolved domains, and conflict resolution
        if is_multi_domain:
            resolved_types = {d: rt for d, rt in domain_recommended_types.items() if rt is not None}
            unresolved_domains = list(typed.unresolved_domains)
            unique_rec_types = set(resolved_types.values())

            # A matched domain with no construct is unresolved. Do not drop None
            # and then call the remaining domain CLEAR.
            if unresolved_domains:
                typed.ambiguity_state = "AMBIGUOUS"
                typed.recommended_intent_type = None
                typed.notes.append(
                    f"Unresolved construct for {unresolved_domains}; not dropped in favor of {list(unique_rec_types) or 'none'}"
                )
                return typed
            if len(unique_rec_types) > 1:
                typed.ambiguity_state = "AMBIGUOUS"
                typed.recommended_intent_type = None
                typed.notes.append(f"Multi-domain construct conflict across {all_domains}: candidates {list(unique_rec_types)}")
                return typed
            if len(unique_rec_types) == 1:
                single_rec = list(unique_rec_types)[0]
                typed.recommended_intent_type = single_rec
                typed.ambiguity_state = "CLEAR"
                typed.notes.append(f"Multi-domain compatible ({all_domains}): aggregated {single_rec} with interfaces {typed.candidate_interfaces}")
                return typed
            typed.ambiguity_state = "AMBIGUOUS" if all_domains else "UNKNOWN"
            typed.recommended_intent_type = None
            typed.notes.append(f"Multi-domain without actionable construct across {all_domains}")
            return typed

        # Single domain inference
        if pri_rec:
            typed.recommended_intent_type = pri_rec
            typed.ambiguity_state = "CLEAR"
        elif domain in ("product", "part", "drawing", "surface"):
            typed.ambiguity_state = "AMBIGUOUS"
            typed.recommended_intent_type = None
            typed.notes.append("Domain clear but no concrete action or construct specified")
        else:
            typed.ambiguity_state = "UNKNOWN"
            typed.recommended_intent_type = None
            typed.notes.append("Unknown domain and no explicit construct keyword")

        return typed

    # ─── Domain-specific clarifications ────────────────────────

    def _clarify_product(self, request: str) -> tuple:
        """Clarify product/assembly domain requests"""
        resolved = {}
        unresolved = []

        if "export" in request or "bom" in request or "导出" in request:
            if "csv" in request:
                resolved["output_format"] = "csv"
            elif "excel" in request or "xlsx" in request:
                resolved["output_format"] = "excel"
            elif "json" in request:
                resolved["output_format"] = "json"
            else:
                unresolved.append(Decision(
                    id="output_format",
                    question="Output format for the export?",
                    options=["csv", "excel", "json"],
                    default="csv",
                ))

            if "recursive" in request or "递归" in request or "所有" in request:
                resolved["traversal_depth"] = "recursive"
            elif "top" in request or "顶层" in request:
                resolved["traversal_depth"] = "top_level"
            else:
                unresolved.append(Decision(
                    id="traversal_depth",
                    question="How deep should the assembly be traversed?",
                    options=["top_level", "recursive", "leaf_only"],
                    default="recursive",
                ))

        if "statistic" in request or "统计" in request:
            unresolved.append(Decision(
                id="stat_type",
                question="What statistics are needed?",
                options=["part_count", "mass_summary", "attribute_summary", "full_report"],
                default="full_report",
            ))

        return resolved, unresolved

    def _clarify_part(self, request: str) -> tuple:
        """Clarify part design domain requests"""
        resolved = {}
        unresolved = []

        if "check" in request or "检查" in request or "analyze" in request:
            unresolved.append(Decision(
                id="check_target",
                question="What should be checked?",
                options=["fillet_radius", "hole_diameter", "chamfer_angle",
                         "wall_thickness", "feature_type"],
                default="feature_type",
            ))

        return resolved, unresolved

    def _clarify_drawing(self, request: str) -> tuple:
        """Clarify drawing domain requests"""
        resolved = {}
        unresolved = []

        unresolved.append(Decision(
            id="drawing_type",
            question="What type of drawing operation?",
            options=["create_view", "add_annotation", "generate_bom_table",
                     "batch_generate", "export_to_dwg"],
            default="create_view",
        ))

        return resolved, unresolved

    def _clarify_surface(self, request: str) -> tuple:
        """Clarify surface/GSD domain requests"""
        return {}, []

    def _clarify_ui(self, request: str) -> tuple:
        """Clarify UI domain requests"""
        resolved = {}
        unresolved = []

        if "command" in request and "dialog" not in request and "对话框" not in request:
            unresolved.append(Decision(
                id="with_dialog",
                question="Should the command have a dialog?",
                options=["yes", "no"],
                default="no",
            ))

        if "menu" in request or "右键" in request or "right click" in request or "context" in request:
            unresolved.append(Decision(
                id="menu_type",
                question="Where should the menu item appear?",
                options=["toolbar", "context_menu", "workbench_menu"],
                default="context_menu",
            ))

        return resolved, unresolved

    # ─── Helpers ───────────────────────────────────────────────

    def _is_clear_command(self, request: str) -> bool:
        """Check if the request is already a clear command specification"""
        import re
        # Pattern: "create command <Name> in <Module>"
        if re.search(r'create\s+(?:a\s+)?(?:command|dialog|feature|workbench|interface)\s+\w+', request):
            return True
        # Pattern: "<verb> command <Name> <Module>"
        if re.search(r'(?:add|make|generate)\s+(?:a\s+)?(?:command|dialog|feature|workbench|interface|module|framework|extension|component)\s+\w+', request):
            return True
        return False


# ─── UI Generator Clarifier (4-axis policy) ──────────────────────


class UIGeneratorClarifier:
    """
    UI Generator clarification engine — the 4-axis "unsafe-to-infer"
    boundary check.

    Detects decision axes that a CAA UI Generator cannot safely resolve
    from the CATDlg API, CATIA domain API, or CAA conventions. Each
    triggered-and-unresolved axis becomes a clarifying question.

    This is NOT a UI semantic model / ontology. It is a gap detector:
    it asks only when intent genuinely under-specifies behavior AND
    domain/API/convention cannot disambiguate.

    Axes:
      1. selection_cardinality — single vs multiple selection
      2. behavior_target       — write to CATIA vs UI-only draft
      3. commit_timing         — immediate vs on-Apply/confirm
      4. value_dependency      — one value constrains another

    Domain/Intent resolution (e.g. what "颜色" refers to) is explicitly
    OUT OF SCOPE and belongs to an upstream resolver. Its output is
    consumed here via ``analyze(domain_context=...)``:
      - field_targets: {field_word: "catia"|"ui_draft"|"read_only"}
      - value_dependencies: [{"source": w, "targets": [w, ...]}]
    No knowledge retrieval happens inside this class.
    """

    # ── Selection axis signals ──────────────────────────────
    SELECTION_VERBS = ["选择", "选取", "选中", "勾选", "select", "choose", "pick"]
    ENTITY_OBJECTS = ["body", "part", "component", "feature", "零件", "部件",
                      "组件", "对象", "项", "条目", "元素", "成员", "行", "实体"]
    PROPERTY_WORDS = ["类型", "编号", "号", "名称", "属性", "格式", "名字",
                      "颜色", "材料", "数量", "等级"]
    MULTI_SIGNALS = ["多个", "多选", "multiple", "multi"]
    SINGLE_SIGNALS = ["单个", "单选", "single", "one", "一个"]
    CARDINALITY_WINDOW = 10

    # ── Edit / commit axis signals ──────────────────────────
    EDIT_VERBS = ["编辑", "修改", "改", "设置", "设为", "调整", "填写", "输入",
                  "更新", "重命名", "改名", "rename", "modify", "edit",
                  "update", "change", "set"]
    IMMEDIATE_SIGNALS = ["立即", "即时", "马上", "实时", "立刻", "immediately",
                         "directly"]
    DEFERRED_SIGNALS = ["apply", "应用后", "点击应用", "确认后", "确定后",
                        "完成后", "点击完成", "提交后", "保存后", "on apply",
                        "after apply", "after confirm"]
    NEGATION_SIGNALS = ["不允许", "不可编辑", "不能编辑", "禁止编辑", "只读",
                        "不能改", "不可改", "read-only", "readonly",
                        "not editable", "cannot edit"]

    # ── Behavior target axis signals ────────────────────────
    FIELD_WORDS = ["名称", "名字", "实例名", "编号", "颜色", "等级", "类型",
                   "属性", "材料", "数量"]
    DOMAIN_TARGET_SIGNALS = ["写回", "更新模型", "保存到模型", "写入",
                             "写到产品", "save to model", "write back"]
    UI_TARGET_SIGNALS = ["仅ui", "仅更新ui", "草稿", "临时", "只改显示",
                         "仅当前显示", "仅内存", "不写", "ui_draft_only",
                         "draft", "preview"]

    # Valid behavior-target values supplied via domain_context
    VALID_FIELD_TARGETS = {"catia", "ui_draft", "read_only"}

    # Construct-level requests. "create extension X on Type" contains no
    # editable field, so an edit/commit axis would be a false positive.
    CONSTRUCT_ONLY_VERBS = ["create", "make", "generate", "build", "add",
                            "创建", "新建", "生成", "添加", "增加", "建立",
                            "实现", "implement"]
    CONSTRUCT_NOUNS = ["extension", "component", "interface", "command",
                       "dialog", "workbench", "feature", "addin", "module",
                       "framework", "扩展", "组件", "接口", "命令", "对话框",
                       "工作台", "特征", "模块", "框架"]

    # ── Public API ──────────────────────────────────────────

    def analyze(self, intent: str,
                domain_context: Optional[Dict[str, Any]] = None) -> ClarificationResult:
        """
        Analyze a user intent and return unresolved UI-generation decisions.

        Args:
            intent: Natural-language user intent for a CAA UI.
            domain_context: Upstream Domain/Intent resolution output. Two
                optional keys are consumed (see class docstring):
                  - ``field_targets``: {field_word: "catia"|"ui_draft"|"read_only"}
                    pre-resolves a field's behavior target.
                  - ``value_dependencies``: [{"source": w, "targets": [w, ...]}]
                    pre-resolves an intrinsic value dependency.
                No knowledge retrieval happens here — the resolver is upstream.

        Returns:
            ClarificationResult whose ``unresolved`` holds the triggered
            axis Decisions (reusing the existing ``Decision`` model).
        """
        if not intent or not intent.strip():
            return ClarificationResult(status="ok", goal="", unresolved=[])

        text = intent.lower()
        ctx = domain_context or {}
        resolved = {}
        unresolved = []

        # Read-only displays: suppress edit-related axes.
        negated = self._has_negation(text)
        # A pure construct request ("create extension X on Type") edits no
        # field, so edit axes do not apply to it.
        construct_only = self._is_construct_only(text)

        cardinality = self._check_selection_cardinality(text)
        if cardinality is not None:
            unresolved.append(cardinality)

        if not negated and not construct_only:
            behavior_target = self._check_behavior_target(text, ctx)
            if behavior_target is not None:
                unresolved.append(behavior_target)

            commit_timing = self._check_commit_timing(text)
            if commit_timing is not None:
                unresolved.append(commit_timing)

        # value_dependency is never asked on its own; domain_context may
        # resolve an intrinsic dependency instead.
        resolved.update(self._resolve_value_dependency(text, ctx))

        if unresolved:
            return ClarificationResult(
                status="needs_clarification",
                goal=intent,
                resolved=resolved,
                unresolved=unresolved,
            )
        return ClarificationResult(
            status="ok",
            goal=intent,
            resolved=resolved,
            unresolved=[],
        )

    # ── Axis checks ─────────────────────────────────────────

    def _has_negation(self, text: str) -> bool:
        return any(s in text for s in self.NEGATION_SIGNALS)

    def _is_construct_only(self, text: str) -> bool:
        """True when the request only names a construct and its target.

        Requires a construct verb AND a construct noun AND no value field:
        "create extension X on CAAMmrMeasureSet" qualifies, while
        "做一个按钮，把当前零件背景设为白色" (a field edit) does not.
        """
        if not any(n in text for n in self.CONSTRUCT_NOUNS):
            return False
        if not any(v in text for v in self.CONSTRUCT_ONLY_VERBS):
            return False
        return not any(f in text for f in self.FIELD_WORDS)

    def _has_entity_object(self, text: str) -> bool:
        """True if text mentions a selectable entity object.

        English entity words are matched at word boundaries so ``part``
        does not match ``partname``; Chinese words use substring matching
        (they have no word boundaries).
        """
        for o in self.ENTITY_OBJECTS:
            if o.isascii():
                if re.search(rf"\b{re.escape(o)}\b", text):
                    return True
            elif o in text:
                return True
        return False

    def _check_selection_cardinality(self, text: str) -> Optional[Decision]:
        """Selection cardinality: single vs multiple."""
        if not any(v in text for v in self.SELECTION_VERBS):
            return None
        if not self._has_entity_object(text):
            return None
        if self._explicit_cardinality(text) is not None:
            return None
        if self._is_property_selection(text):
            return None
        return Decision(
            id="selection_cardinality",
            question="选择是单选还是多选？",
            options=["single", "multiple"],
            default="",
        )

    def _explicit_cardinality(self, text: str) -> Optional[str]:
        """Return 'single'/'multiple' if a selection verb is followed by an
        explicit cardinality marker within a short window."""
        for verb in self.SELECTION_VERBS:
            start = text.find(verb)
            while start != -1:
                tail = text[start + len(verb): start + len(verb) + self.CARDINALITY_WINDOW]
                if any(s in tail for s in self.MULTI_SIGNALS):
                    return "multiple"
                if any(s in tail for s in self.SINGLE_SIGNALS):
                    return "single"
                start = text.find(verb, start + 1)
        return None

    def _is_property_selection(self, text: str) -> bool:
        """True if selection targets an attribute, e.g. '选择零件类型'."""
        for entity in self.ENTITY_OBJECTS:
            for prop in self.PROPERTY_WORDS:
                if entity + prop in text:
                    return True
        return False

    def _check_behavior_target(self, text: str,
                               domain_context: Dict[str, Any]) -> Optional[Decision]:
        """Behavior target: write to CATIA vs UI-only draft.

        ``domain_context["field_targets"]`` may pre-resolve a field's
        target, in which case this axis does not ask.
        """
        compact = text.replace(" ", "")
        if any(s in compact for s in self.DOMAIN_TARGET_SIGNALS):
            return None
        if any(s in compact for s in self.UI_TARGET_SIGNALS):
            return None

        has_edit = any(v in text for v in self.EDIT_VERBS)
        matched_fields = [f for f in self.FIELD_WORDS if f in text]
        if has_edit and matched_fields:
            if self._all_fields_resolved(matched_fields, domain_context):
                return None
            return Decision(
                id="behavior_target",
                question="修改后写回 CATIA 领域，还是仅保留为 UI/内存草稿？",
                options=["write_to_catia", "ui_draft_only"],
                default="",
            )

        # A bare "save" with no target also needs a behavior target.
        if "保存" in text and not any(
                s in text for s in ("保存到", "保存至", "保存为", "保存后", "写回", "写入")):
            return Decision(
                id="behavior_target",
                question="修改后写回 CATIA 领域，还是仅保留为 UI/内存草稿？",
                options=["write_to_catia", "ui_draft_only"],
                default="",
            )

        return None

    def _all_fields_resolved(self, matched_fields: List[str],
                             domain_context: Dict[str, Any]) -> bool:
        """True if every matched field has a valid target in domain_context."""
        field_targets = domain_context.get("field_targets", {})
        if not field_targets:
            return False
        return all(
            f in field_targets and field_targets[f] in self.VALID_FIELD_TARGETS
            for f in matched_fields
        )

    def _check_commit_timing(self, text: str) -> Optional[Decision]:
        """Commit timing: immediate vs on-Apply/confirm."""
        if not any(v in text for v in self.EDIT_VERBS):
            return None
        if any(s in text for s in self.IMMEDIATE_SIGNALS):
            return None
        if any(s in text for s in self.DEFERRED_SIGNALS):
            return None
        return Decision(
            id="commit_timing",
            question="修改是立即生效，还是点击 Apply/确认后生效？",
            options=["immediate", "on_apply"],
            default="",
        )

    def _resolve_value_dependency(self, text: str,
                                  domain_context: Dict[str, Any]) -> Dict[str, str]:
        """Resolve an intrinsic value dependency from domain_context.

        The value_dependency axis never asks on its own: a dependency
        signal (筛选/取决于/根据/联动) already expresses the constraint;
        its absence is not grounds to ask — two values existing does NOT
        imply a dependency. When domain_context supplies an intrinsic
        dependency that the intent mentions, resolve it instead of asking.
        """
        resolved = {}
        for dep in domain_context.get("value_dependencies", []):
            source = dep.get("source", "")
            targets = dep.get("targets", [])
            if source and source in text and any(t in text for t in targets):
                resolved["value_dependency"] = "dependent"
                break
        return resolved


class RequirementsDecomposer:
    """
    Enhances clarified requirements with cross-domain knowledge.

    Maps decisions from RequirementDocument into actionable extras:
      - playbooks: which playbooks to reference
      - capabilities: which capabilities are needed
      - extra_components: additional CAA components to generate (data_extension, etc.)
      - imakefile_deps: additional LINK_WITH frameworks

    Design principle:
      Detects patterns in decisions that imply cross-domain needs
      (e.g., "trigger=context_menu" → needs DataExtension).
      Zero changes to existing Intent/Planner/Generator.
    """

    # Decision value → extras mapping
    DECISION_EXTRAS = {
        ("trigger", "context_menu"): {
            "extra_components": ["data_extension"],
            "capabilities": ["cap.selection"],
        },
        ("trigger", "batch"): {
            "imakefile_deps": ["AutomationInterfaces"],
            "capabilities": ["cap.document_export"],
        },
        ("output_format", "excel"): {
            "imakefile_deps": ["AutomationInterfaces"],
        },
        ("output_format", "csv"): {
            "capabilities": ["cap.document_export"],
        },
        ("traversal_depth", "recursive"): {
            "capabilities": ["cap.assembly_tree"],
        },
        # UI decisions
        ("with_dialog", "yes"): {
            "knowledge_refs": ["ui.dialog", "ui.dialog_patterns"],
        },
        ("menu_type", "context_menu"): {
            "knowledge_refs": ["ui.context_menu"],
            "pattern_refs": ["ui.context_menu_pattern"],
        },
        ("menu_type", "toolbar"): {
            "knowledge_refs": ["ui.toolbar"],
        },
        # Drawing decisions
        ("drawing_type", "create_view"): {
            "knowledge_refs": ["drawing.basics"],
        },
        ("drawing_type", "add_annotation"): {
            "knowledge_refs": ["drawing.annotations"],
        },
        ("drawing_type", "generate_bom_table"): {
            "knowledge_refs": ["drawing.annotations"],
            "capabilities": ["cap.assembly_tree"],
        },
    }

    # Domain → default playbooks
    DOMAIN_PLAYBOOKS = {
        "product": ["pb.export_bom", "pb.assembly_stats", "pb.batch_update_save",
                     "pb.assembly_constraint_check"],
        "part": ["pb.batch_feature_check", "pb.geometry_quality_check", "pb.parameter_editor"],
        "surface": ["pb.surface_analysis"],
        "drawing": ["pb.batch_drawing"],
        "fta": ["pb.auto_annotate_3d"],
        "ui": ["pb.create_context_menu", "pb.custom_viewer", "pb.dialog_wizard"],
    }

    # Domain → default capabilities
    DOMAIN_CAPABILITIES = {
        "product": ["cap.assembly_tree", "cap.update_mechanism", "cap.persistence"],
        "part": ["cap.feature_recognition", "cap.parameter_system", "cap.geometry_query"],
        "surface": ["cap.surface_operations", "cap.geometry_query", "cap.document_export"],
        "drawing": ["cap.document_export", "cap.assembly_tree"],
        "fta": ["cap.annotation", "cap.geometry_query", "cap.selection"],
        "ui": ["cap.selection", "cap.visualization", "cap.parameter_system"],
    }

    def enhance(self, result) -> dict:
        """
        Extract enhancement extras from a ClarificationResult or RequirementDocument.

        Args:
            result: ClarificationResult or RequirementDocument with .decisions dict

        Returns:
            extras dict with keys: playbooks, capabilities, extra_components, imakefile_deps
        """
        extras = {
            "playbooks": [],
            "capabilities": [],
            "extra_components": [],
            "imakefile_deps": [],
            "knowledge_refs": [],
            "pattern_refs": [],
        }

        decisions = {}
        domain = "general"

        if hasattr(result, "decisions"):
            decisions = dict(result.decisions)
        if hasattr(result, "resolved"):
            decisions.update(dict(result.resolved))
        if hasattr(result, "domain"):
            domain = result.domain

        # Apply decision-based mappings
        for key, value in decisions.items():
            mapping_key = (key, value)
            if mapping_key in self.DECISION_EXTRAS:
                for extra_key, extra_values in self.DECISION_EXTRAS[mapping_key].items():
                    extras[extra_key].extend(extra_values)

        # Apply domain defaults
        if domain in self.DOMAIN_PLAYBOOKS:
            extras["playbooks"].extend(self.DOMAIN_PLAYBOOKS[domain])
        if domain in self.DOMAIN_CAPABILITIES:
            extras["capabilities"].extend(self.DOMAIN_CAPABILITIES[domain])

        # Deduplicate
        for key in extras:
            extras[key] = list(dict.fromkeys(extras[key]))

        return extras


# ─── Multi-Intent Decomposer (v3.1) ────────────────────────────────


@dataclass
class SubIntent:
    """A single decomposed sub-intent from a compound request"""
    goal: str
    domain: str = "general"
    description: str = ""
    priority: int = 1

    def to_dict(self) -> dict:
        return {
            "goal": self.goal, "domain": self.domain,
            "description": self.description, "priority": self.priority,
        }


class MultiIntentDecomposer:
    """
    Splits compound user requests into independent sub-intents.

    Detects connectors like 并/同时/以及/and also/as well as.
    Each sub-intent goes through the full develop pipeline independently.
    """

    CN_CONNECTORS = ["并", "同时", "以及", "还有", "另外", "并且", "外加", "包含", "和"]
    EN_CONNECTORS = ["and also", "as well as", "plus", "additionally", " and "]

    def decompose(self, request: str, clarification=None) -> List[SubIntent]:
        if not request or not request.strip():
            return []
        domain = clarification.domain if clarification and hasattr(clarification, 'domain') else "general"
        segments = self._split_request(request)
        if len(segments) <= 1:
            return [SubIntent(goal=request.strip()[:80], domain=domain, description=request.strip())]
        sub_intents = []
        for i, seg in enumerate(segments):
            seg = seg.strip()
            if not seg or len(seg) < 3:
                continue
            sub_domain = self._infer_domain(seg)
            sub_intents.append(SubIntent(
                goal=seg[:80], domain=sub_domain or domain,
                description=seg, priority=i + 1,
            ))
        return sub_intents if sub_intents else [SubIntent(
            goal=request.strip()[:80], domain=domain, description=request.strip())]

    def _split_request(self, request: str) -> List[str]:
        for conn in self.CN_CONNECTORS:
            if conn in request:
                parts = request.split(conn)
                result = []
                for p in parts:
                    result.extend(self._split_request(p.strip()))
                return result if len(result) > 1 else [request]
        for conn in self.EN_CONNECTORS:
            if conn in request.lower():
                parts = request.lower().split(conn)
                result = []
                for p in parts:
                    result.extend(self._split_request(p.strip()))
                return result if len(result) > 1 else [request]
        return [request]

    def _infer_domain(self, text: str) -> str:
        """Infer CAA domain using authoritative RequirementsClarifier domain detection."""
        detected = RequirementsClarifier()._detect_domain(text.lower())
        return detected if detected != "general" else ""
