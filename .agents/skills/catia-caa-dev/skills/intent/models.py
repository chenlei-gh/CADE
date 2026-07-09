"""
Intent Engine — Core Data Models
=================================
Intent, Context, DevelopmentPlan, ActionSpec, ImpactReport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class IntentType(Enum):
    CREATE_COMMAND = "CreateCommand"
    CREATE_COMMAND_WITH_DIALOG = "CreateCommandWithDialog"
    CREATE_FEATURE = "CreateFeature"
    CREATE_FEATURE_WITH_FACTORY = "CreateFeatureWithFactory"
    CREATE_INTERFACE = "CreateInterface"
    CREATE_COMPONENT = "CreateComponent"
    CREATE_WORKBENCH = "CreateWorkbench"
    CREATE_EXTENSION = "CreateExtension"
    CREATE_DIALOG = "CreateDialog"
    CREATE_MODULE = "CreateModule"
    CREATE_FRAMEWORK = "CreateFramework"
    MODIFY_INTERFACE = "ModifyInterface"
    RENAME_COMMAND = "RenameCommand"
    MOVE_COMMAND = "MoveCommand"
    BATCH_CREATE = "BatchCreate"


class Severity(Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Intent:
    """Structured development intent — what the user wants to create/modify."""
    type: IntentType
    name: str
    module: str = ""
    framework: str = "MyFramework"
    params: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)

    # For batch intents
    sub_intents: List[Intent] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> Intent:
        itype = IntentType(d["type"])
        return cls(
            type=itype,
            name=d.get("name", ""),
            module=d.get("module", ""),
            framework=d.get("framework", "MyFramework"),
            params=d.get("params", {}),
            constraints=d.get("constraints", []),
        )

    def to_dict(self) -> dict:
        d = {
            "type": self.type.value,
            "name": self.name,
            "module": self.module,
            "framework": self.framework,
        }
        if self.params:
            d["params"] = self.params
        if self.constraints:
            d["constraints"] = self.constraints
        return d


@dataclass
class ActionStep:
    """Single executable step in a DevelopmentPlan."""
    action: str  # e.g., "create_command", "register_catalog"
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # step IDs this depends on
    rollback_action: Optional[str] = None
    step_id: str = ""

    def __post_init__(self):
        if not self.step_id:
            self.step_id = f"{self.action}_{self.params.get('name', '?')}"

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "params": self.params,
            "dependencies": self.dependencies,
            "rollback_action": self.rollback_action,
        }


@dataclass
class DevelopmentPlan:
    """Ordered, executable plan with metadata."""
    intent: Intent
    steps: List[ActionStep] = field(default_factory=list)
    estimated_time: str = ""
    risk_level: Severity = Severity.NONE
    alternatives: List[DevelopmentPlan] = field(default_factory=list)

    def step_count(self) -> int:
        return len(self.steps)

    def add_step(self, action: str, params: dict = None,
                 deps: list = None, rollback: str = None) -> ActionStep:
        step = ActionStep(
            action=action,
            params=params or {},
            dependencies=deps or [],
            rollback_action=rollback,
        )
        self.steps.append(step)
        return step

    def to_dict(self) -> dict:
        return {
            "intent": self.intent.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
            "estimated_time": self.estimated_time,
            "risk_level": self.risk_level.value,
            "step_count": self.step_count(),
            "alternatives": len(self.alternatives),
        }


@dataclass
class ImpactReport:
    """Result of impact analysis for a proposed change."""
    entity: str  # What's being changed
    severity: Severity = Severity.NONE
    affected_files: List[str] = field(default_factory=list)
    affected_modules: List[str] = field(default_factory=list)
    affected_interfaces: List[str] = field(default_factory=list)
    breaking_changes: bool = False
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entity": self.entity,
            "severity": self.severity.value,
            "affected_files_count": len(self.affected_files),
            "affected_modules": self.affected_modules,
            "affected_interfaces": self.affected_interfaces,
            "breaking_changes": self.breaking_changes,
            "recommendations": self.recommendations,
        }
