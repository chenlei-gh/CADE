"""
CATIA CAA Intent Layer Package
===============================
High-level intent-driven interfaces for CAA development.

Sub-modules:
  commands      - create_executable_command, create_ui_dialog
  services      - expose_service, create_component_with_interfaces
  objects       - create_feature, create_extension
  recommendation - suggest_next_action
  helpers       - shared validation and utility functions
"""

from .commands import create_executable_command, create_ui_dialog
from .objects import create_extension, create_feature
from .recommendation import _analyze_workspace_health, suggest_next_action
from .services import create_component_with_interfaces, expose_service

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
