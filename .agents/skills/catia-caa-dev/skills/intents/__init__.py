"""
CATIA CAA Intent Layer Package
===============================
High-level intent-driven interfaces for CAA development.

Sub-modules:
  commands      - create_executable_command
  services      - expose_service, create_component_with_interfaces
  objects       - create_feature, create_extension
  helpers       - shared validation and utility functions

Naming note: `intents/` (plural, this package) is the PUBLIC intent API
built on the actions layer. The sibling `intent/` (singular) is the Intent
ENGINE (models/planner/impact, Intent -> DevelopmentPlan). They differ by
one letter — do not confuse them.
"""

from .commands import create_executable_command
from .objects import create_extension, create_feature
from .services import create_component_with_interfaces, expose_service

__all__ = [
    "create_executable_command",
    "expose_service",
    "create_component_with_interfaces",
    "create_feature",
    "create_extension",
]
