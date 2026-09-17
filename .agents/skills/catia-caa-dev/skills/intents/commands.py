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
    generate_next_steps,
    generate_tooltip,
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

    # All three actions write into the SAME ChangeSet. Serializing each result
    # and re-merging (the previous flow) dropped the second writer of any file
    # two actions share: create_command and create_dialog both contribute to
    # the framework .CATNls catalog, so the merged value kept only one of the
    # two blocks and the dialog's own keys (<Dialog>.LabelId) never reached
    # disk. Nothing below applies the ChangeSet — the caller does.
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
        cs=master_cs,
    )
    if cmd_result["status"] == "error":
        return cmd_result

    # Create dialog
    if with_dialog and dialog_name:
        dlg_result = create_dialog(ctx, dialog_name, module, framework, cs=master_cs)
        if dlg_result["status"] != "error":
            components["dialog"] = dialog_name

    # Add to workbench
    if add_to_workbench:
        wb_result = add_cmd_to_wb(ctx, name, add_to_workbench, cs=master_cs)
        if wb_result["status"] != "error":
            components["workbench"] = add_to_workbench

    master_cs.merge_metadata(
        intent="create_executable_command",
        command=name,
        module=module,
        framework=framework,
        has_dialog=with_dialog,
        dialog_name=dialog_name,
        workbench=add_to_workbench,
        components=components,
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



