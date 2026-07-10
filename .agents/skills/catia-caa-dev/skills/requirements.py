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


# ─── ClarificationResult ──────────────────────────────────────────


@dataclass
class ClarificationResult:
    """Result of requirements clarification — may have unresolved decisions"""
    status: str = "needs_clarification"
    domain: str = ""
    goal: str = ""
    resolved: Dict[str, str] = field(default_factory=dict)
    unresolved: List[Decision] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
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
        "product": ["assembly", "product", "bom", "part", "component", "装配", "零件",
                     "bom", "物料", "统计", "export"],
        "part": ["part", "feature", "fillet", "hole", "chamfer", "pad", "pocket",
                 "圆角", "孔", "倒角", "特征"],
        "drawing": ["drawing", "sheet", "view", "annotation", "dimension", "工程图",
                     "图纸", "标注", "视图"],
        "surface": ["surface", "gsd", "extrude", "sweep", "flatten", "offset",
                     "曲面", "拉伸", "扫掠", "展平"],
        "ui": ["dialog", "command", "toolbar", "menu", "workbench", "对话框",
                "命令", "菜单", "工作台", "工具栏"],
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

        # Step 1: Detect domain
        domain = self._detect_domain(request_lower)

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

        # If the request is already clear enough
        if self._is_clear_command(request_lower):
            return ClarificationResult(
                status="ok",
                domain=domain,
                goal=goal,
                resolved=resolved,
                unresolved=[],
            )

        # Limit unresolved questions
        unresolved = unresolved[:self.MAX_QUESTIONS]

        if unresolved:
            return ClarificationResult(
                domain=domain,
                goal=goal,
                resolved=resolved,
                unresolved=unresolved,
            )
        else:
            return ClarificationResult(
                status="ok",
                domain=domain,
                goal=goal,
                resolved=resolved,
                unresolved=[],
            )

    # ─── Domain Detection ──────────────────────────────────────

    def _detect_domain(self, request: str) -> str:
        """Detect CAA domain from request keywords"""
        scores = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in request)
            if score > 0:
                scores[domain] = score

        if not scores:
            return "general"

        return max(scores, key=scores.get)

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
            "visualize": "visualiz" in request or "color" in request or "着色" in request,
        }
        for goal, found in goals.items():
            if found:
                return goal
        return request[:50]  # truncate

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
