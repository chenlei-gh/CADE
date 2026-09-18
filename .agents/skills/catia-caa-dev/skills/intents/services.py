"""
Service-oriented intent functions.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from actions import ActionContext, create_component, create_interface
from changeset import ChangeSet

from .helpers import (
    changeset_from_dict,
    merge_changeset,
    validate_module,
)


def create_component_with_interfaces(
    ctx: ActionContext,
    name: str,
    module: str,
    framework: str = None,
    *,
    implements: Optional[List[str]] = None,
    use_tie: bool = True,
    generate_skeleton: bool = True,
) -> Dict:
    """
    Create a component that implements multiple interfaces.

    Automatically creates: Component class, all interfaces, TIE includes,
    method skeletons, Dictionary registration.
    """
    ctx.refresh()

    validation = validate_module(ctx, module, framework)
    if validation["status"] == "error":
        return validation

    master_cs = ChangeSet(
        action="create_component_with_interfaces",
        description=f"Create component '{name}' with {len(implements or [])} interfaces",
    )

    comp_result = create_component(ctx, name=name, module=module, framework=framework)
    if comp_result["status"] == "error":
        return comp_result
    merge_changeset(master_cs, changeset_from_dict(comp_result["changeset"]))

    created_interfaces = []
    if implements:
        for iface_name in implements:
            iface_result = create_interface(
                ctx, name=iface_name, module=module, framework=framework
            )
            if iface_result["status"] != "error":
                merge_changeset(
                    master_cs, changeset_from_dict(iface_result["changeset"])
                )
                created_interfaces.append(
                    {
                        "name": iface_name,
                        "tie": f"TIE_{iface_name}({name})" if use_tie else None,
                    }
                )

    component_info = {
        "name": name,
        "interfaces": [i["name"] for i in created_interfaces],
        "tie_usage": use_tie,
        "total_interfaces": len(created_interfaces),
    }

    master_cs.metadata.update(
        {
            "intent": "create_component_with_interfaces",
            "component": name,
            "module": module,
            "implements": implements or [],
            "use_tie": use_tie,
            "components": component_info,
        }
    )

    next_steps = [f"Implement {name} class with all interface methods"]
    for iface in created_interfaces:
        next_steps.append(f"Implement {iface['name']} methods in {name}")
    next_steps.extend(
        ["Register all interfaces in Dictionary", "Build and test the component"]
    )

    return {
        "status": "pending",
        "intent": "create_component_with_interfaces",
        "message": f"Ready to create component '{name}' with {len(created_interfaces)} interfaces",
        "component": component_info,
        "changeset": master_cs.to_dict(),
        "preview": master_cs.preview(),
        "next_steps": next_steps,
    }
