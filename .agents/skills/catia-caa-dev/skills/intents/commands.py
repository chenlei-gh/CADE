"""
Command-related intent functions.
"""

from __future__ import annotations

from typing import Dict, Optional

from actions import ActionContext, create_command, create_dialog
from actions import add_command_to_workbench as add_cmd_to_wb
from changeset import ChangeSet
from meta_model import Visibility

from .helpers import (
    changeset_from_dict,
    generate_next_steps,
    generate_tooltip,
    merge_changeset,
    validate_command_params,
)


def create_executable_command(
    ctx: ActionContext,
    name: str,
    module: str,
    framework: str = None,
    *,
    with_dialog: bool = False,
    dialog_name: Optional[str] = None,
    add_to_workbench: Optional[str] = None,
    stateful: bool = False,
    icon_style: str = "simple",
    tooltip: Optional[str] = None,
    category: str = "General",
    visibility: str = Visibility.ALWAYS,
) -> Dict:
    """
    Create a complete executable command with all necessary files.

    Automatically creates: Command, Header, Dialog (optional), Catalog, NLS,
    Icon, Dictionary, Imakefile updates, and Workbench integration (optional).
    """
    ctx.refresh()

    validation = validate_command_params(ctx, name, module, framework)
    if validation["status"] == "error":
        return validation

    if not dialog_name and with_dialog:
        dialog_name = f"{name}Dlg"
    if not tooltip:
        tooltip = generate_tooltip(name)

    master_cs = ChangeSet(
        action="create_executable_command",
        description=f"Create complete executable command '{name}'",
    )
    components = {"command": name, "dialog": None, "workbench": None}

    # Create command
    cmd_result = create_command(
        ctx,
        name=name,
        module=module,
        framework=framework,
        is_stateful=stateful or with_dialog,
        dialog_name=dialog_name if with_dialog else None,
        icon=icon_style,
        tooltip=tooltip,
        category=category,
        visibility=visibility,
    )
    if cmd_result["status"] == "error":
        return cmd_result
    merge_changeset(master_cs, changeset_from_dict(cmd_result["changeset"]))

    # Create dialog
    if with_dialog and dialog_name:
        dlg_result = create_dialog(ctx, dialog_name, module, framework)
        if dlg_result["status"] != "error":
            merge_changeset(master_cs, changeset_from_dict(dlg_result["changeset"]))
            components["dialog"] = dialog_name

    # Add to workbench
    if add_to_workbench:
        wb_result = add_cmd_to_wb(ctx, name, add_to_workbench)
        if wb_result["status"] != "error":
            merge_changeset(master_cs, changeset_from_dict(wb_result["changeset"]))
            components["workbench"] = add_to_workbench

    master_cs.metadata.update(
        {
            "intent": "create_executable_command",
            "command": name,
            "module": module,
            "framework": framework,
            "has_dialog": with_dialog,
            "dialog_name": dialog_name,
            "workbench": add_to_workbench,
            "components": components,
        }
    )

    return {
        "status": "pending",
        "intent": "create_executable_command",
        "message": f"Ready to create complete executable command '{name}'",
        "changeset": master_cs.to_dict(),
        "preview": master_cs.preview(),
        "components": components,
        "suggestions": generate_next_steps(components),
    }


def create_ui_dialog(
    ctx: ActionContext,
    name: str,
    module: str,
    framework: str = None,
    *,
    controls=None,
    layout: str = "vertical",
    with_callbacks: bool = True,
    modal: bool = True,
) -> Dict:
    """Create an interactive UI dialog with controls."""
    ctx.refresh()
    result = create_dialog(ctx, name, module, framework)
    if result["status"] == "error":
        return result

    result["intent"] = "create_ui_dialog"
    result["dialog"] = {
        "name": name,
        "controls": [c.get("name") for c in (controls or [])],
        "layout": layout,
        "modal": modal,
        "with_callbacks": with_callbacks,
    }
    if controls:
        result["next_steps"] = [
            "Add control declarations to dialog header",
            "Implement Build() method with layout",
            "Add callback functions for buttons",
            "Add NLS resources for labels",
        ]
    return result
