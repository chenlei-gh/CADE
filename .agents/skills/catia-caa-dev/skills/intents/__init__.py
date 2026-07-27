"""
CATIA CAA Intent Layer Package
===============================
High-level intent-driven interfaces for CAA development.

Sub-modules:
  commands      - create_executable_command
  services      - expose_service, create_component_with_interfaces
  objects       - create_feature, create_extension
  helpers       - shared validation and utility functions
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
