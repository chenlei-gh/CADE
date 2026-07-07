"""
Shared helpers for intent functions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from actions import ActionContext, list_modules
from changeset import ChangeSet


def validate_module(ctx: ActionContext, module: str, framework: str = None) -> Dict:
    """Validate that a module exists in the workspace"""
    mod = ctx.snapshot.get_module(module, framework)
    if not mod:
        available = list_modules(ctx)
        return {
            "status": "error",
            "message": f"Module '{module}' not found",
            "available_modules": available.get("modules", []),
            "suggestion": "Choose an existing module or create a new one",
        }
    return {"status": "ok"}


def validate_command_params(
    ctx: ActionContext, name: str, module: str, framework: str
) -> Dict:
    """Validate command creation parameters"""
    validation = validate_module(ctx, module, framework)
    if validation["status"] == "error":
        return validation

    mod = ctx.snapshot.get_module(module, framework)
    for cmd in mod.commands:
        if cmd.name.lower() == name.lower():
            return {
                "status": "error",
                "message": f"Command '{name}' already exists in '{module}'",
                "existing_command": cmd.to_dict(),
            }
    return {"status": "ok"}


def generate_tooltip(name: str) -> str:
    """Generate a readable tooltip from CamelCase name"""
    import re

    words = re.findall(r"[A-Z](?:[a-z]+|[A-Z]*(?=[A-Z]|$))", name)
    return " ".join(words) if words else name


def changeset_from_dict(cs_dict: Dict) -> ChangeSet:
    """Reconstruct ChangeSet from dict"""
    return ChangeSet.from_dict(cs_dict)


def merge_changeset(target: ChangeSet, source: ChangeSet):
    """Merge source changeset into target"""
    target.created.update(source.created)
    target.modified.update(source.modified)
    target.deleted.extend(source.deleted)
    target.patches.extend(source.patches)
    target.warnings.extend(source.warnings)


def generate_next_steps(components: Dict) -> List[str]:
    """Generate suggested next steps based on created components"""
    steps = []
    if components.get("command"):
        steps.append(f"Implement {components['command']} business logic")
    if components.get("dialog"):
        steps.append(f"Design {components['dialog']} user interface")
    if components.get("workbench"):
        steps.append(f"Test command in {components['workbench']}")
    else:
        steps.append("Add command to a workbench")
    steps.append("Build and test the module")
    return steps
