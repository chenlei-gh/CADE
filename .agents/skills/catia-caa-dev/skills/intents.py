"""
CATIA CAA Intent Layer (backward-compat wrapper)
================================================
Re-exports from intents/ package.
See intents/__init__.py for the actual implementation.
"""

from intents.commands import create_executable_command, create_ui_dialog
from intents.objects import create_extension, create_feature
from intents.recommendation import _analyze_workspace_health, suggest_next_action
from intents.services import create_component_with_interfaces, expose_service

__all__ = [
    "create_executable_command",
    "create_ui_dialog",
    "expose_service",
    "create_component_with_interfaces",
    "create_feature",
    "create_extension",
    "suggest_next_action",
    "_analyze_workspace_health",
]
