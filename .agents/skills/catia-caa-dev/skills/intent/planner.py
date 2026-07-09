"""
Planner — Converts Intent objects into executable DevelopmentPlans.

Uses Task Templates (pre-defined step sequences) + Context
to produce ordered, validated development plans.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from intent.models import (
    ActionStep, DevelopmentPlan, ImpactReport, Intent,
    IntentType, Severity,
)

_HERE = Path(__file__).parent
_TEMPLATES_FILE = _HERE / "templates" / "task_templates.json"


class Planner:
    """Converts structured Intents into DevelopmentPlans."""

    def __init__(self):
        self.templates: Dict[str, dict] = {}
        self._load_templates()

    def _load_templates(self):
        if _TEMPLATES_FILE.exists():
            self.templates = json.loads(_TEMPLATES_FILE.read_text(encoding="utf-8"))

    # ─── Public API ────────────────────────────────────────────

    def plan(self, intent: Intent, context: dict = None) -> DevelopmentPlan:
        """Convert a single Intent to a DevelopmentPlan."""
        template_key = intent.type.value
        template = self.templates.get(template_key, {})

        if not template:
            # Fallback: return a simple plan with one step
            return DevelopmentPlan(
                intent=intent,
                steps=[ActionStep(
                    action=intent.type.value.lower(),
                    params=self._resolve_params(intent),
                )],
                risk_level=Severity.LOW,
            )

        plan = DevelopmentPlan(
            intent=intent,
            risk_level=Severity(template.get("risk", "low")),
        )

        for step_def in template.get("steps", []):
            params = self._resolve_params(intent, step_def.get("params", {}))
            deps = step_def.get("dependencies", [])
            rollback = step_def.get("rollback_action")
            plan.add_step(step_def["action"], params, deps, rollback)

        return plan

    def plan_batch(self, intents: List[Intent], context: dict = None) -> List[DevelopmentPlan]:
        """Plan multiple intents with dependency ordering and dedup."""
        plans = [self.plan(i, context) for i in intents]

        # Merge: deduplicate framework/module ensure steps
        seen_modules = set()
        for plan in plans:
            deduped = []
            for step in plan.steps:
                if step.action in ("ensure_module", "ensure_framework"):
                    key = f"{step.params.get('name')}_{step.params.get('framework')}"
                    if key in seen_modules:
                        continue
                    seen_modules.add(key)
                deduped.append(step)
            plan.steps = deduped

        # Sort: frameworks first, then modules, then features, then commands
        priorities = {
            "ensure_framework": 0,
            "create_framework": 0,
            "ensure_module": 1,
            "create_module": 1,
            "create_interface": 2,
            "create_feature": 3,
            "create_factory": 3,
            "create_extension": 3,
            "create_command": 4,
            "create_command_header": 5,
            "create_dialog": 5,
            "create_workbench": 5,
            "create_addin": 5,
            "register_catalog": 6,
            "register_nls": 6,
            "update_imakefile": 7,
            "create_readme": 8,
            "create_architecture_doc": 8,
            "create_changelog": 8,
            "create_docs_structure": 8,
            "create_examples_dir": 8,
        }

        all_steps = []
        for plan in plans:
            for step in plan.steps:
                all_steps.append((priorities.get(step.action, 99), step, plan))

        all_steps.sort(key=lambda x: (x[0], x[1].params.get("module", "")))

        # Reassign steps to plans (keeping original plan identity)
        for i, plan in enumerate(plans):
            plan.steps = [s for _, s, p in all_steps if p is plan]

        return plans

    # ─── Helpers ────────────────────────────────────────────────

    def _resolve_params(self, intent: Intent, template_params: dict = None) -> dict:
        """Fill template placeholders with intent values."""
        if not template_params:
            return {"name": intent.name, "module": intent.module,
                    "framework": intent.framework}

        result = {}
        for k, v in template_params.items():
            if isinstance(v, str) and v.startswith("$"):
                key = v[1:]  # Strip $
                if key == "name":
                    result[k] = intent.name
                elif key == "module":
                    result[k] = intent.module
                elif key == "framework":
                    result[k] = intent.framework
                elif key == "interface_name":
                    result[k] = intent.params.get("interface", f"I{intent.name}")
                elif key == "target":
                    result[k] = intent.params.get("target", "")
                else:
                    result[k] = intent.params.get(key, v)
            else:
                result[k] = v
        return result

    def available_templates(self) -> List[str]:
        return list(self.templates.keys())


# ─── Convenience API ──────────────────────────────────────────

_planner = Planner()


def plan(intent: Intent, context: dict = None) -> DevelopmentPlan:
    """Quick API: single intent → plan."""
    return _planner.plan(intent, context)


def plan_batch(intents: List[Intent], context: dict = None) -> List[DevelopmentPlan]:
    """Quick API: multiple intents → ordered plans with dedup."""
    return _planner.plan_batch(intents, context)


SEVERITY_ORDER = {Severity.NONE: 0, Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3, Severity.CRITICAL: 4}
PRIORITY_MAP = {
    "ensure_framework": 0, "create_framework": 0,
    "ensure_module": 1, "create_module": 1,
    "create_interface": 2,
    "create_feature": 3, "create_factory": 3, "create_extension": 3,
    "create_command": 4, "create_command_header": 5, "create_dialog": 5,
    "create_workbench": 5, "create_addin": 5,
    "register_catalog": 6, "register_nls": 6,
    "update_imakefile": 7,
    "create_readme": 8, "create_architecture_doc": 8,
    "create_changelog": 8, "create_docs_structure": 8, "create_examples_dir": 8,
    "create_identity_card": 8, "create_dictionary": 8, "create_nls_catalog": 8,
    "batch_create_commands": 4, "batch_register_catalog": 6,
}


def merge_plans(plans: List[DevelopmentPlan]) -> DevelopmentPlan:
    """Merge multiple plans into one unified plan."""
    if not plans:
        return DevelopmentPlan(intent=Intent(type=IntentType.BATCH_CREATE, name="empty"))
    if len(plans) == 1:
        return plans[0]

    unified = DevelopmentPlan(
        intent=Intent(type=IntentType.BATCH_CREATE, name="merged"),
        risk_level=max(plans, key=lambda p: SEVERITY_ORDER.get(p.risk_level, 0)).risk_level,
    )

    seen = set()
    for p in plans:
        for step in p.steps:
            if step.step_id not in seen:
                seen.add(step.step_id)
                unified.steps.append(step)
        unified.alternatives.extend(p.alternatives)

    unified.steps.sort(key=lambda s: PRIORITY_MAP.get(s.action, 99))
    return unified
