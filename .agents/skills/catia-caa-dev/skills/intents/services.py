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


def expose_service(
    ctx: ActionContext,
    component_name: str,
    module: str,
    framework: str = None,
    *,
    methods: Optional[List[Dict]] = None,
    interface_name: Optional[str] = None,
    use_idl: bool = True,
    generate_tie: bool = True,
) -> Dict:
    """
    Expose a component's service via interface.

    Automatically creates: IDL, C++ header, TIE, Dictionary registration, IID.
    """
    ctx.refresh()

    if not interface_name:
        interface_name = f"I{component_name}"
    if not methods:
        methods = [{"name": "Execute", "params": [], "return": "HRESULT"}]

    master_cs = ChangeSet(
        action="expose_service",
        description=f"Expose service '{component_name}' via interface '{interface_name}'",
    )

    iface_result = create_interface(
        ctx, name=interface_name, module=module, framework=framework, use_idl=use_idl
    )
    if iface_result["status"] == "error":
        return iface_result
    merge_changeset(master_cs, changeset_from_dict(iface_result["changeset"]))

    method_names = [m["name"] for m in methods]
    master_cs.metadata.update(
        {
            "intent": "expose_service",
            "component": component_name,
            "interface": interface_name,
            "methods": method_names,
            "use_idl": use_idl,
            "generate_tie": generate_tie,
        }
    )

    return {
        "status": "pending",
        "intent": "expose_service",
        "message": f"Ready to expose service '{component_name}' via '{interface_name}'",
        "service": {
            "interface": interface_name,
            "component": component_name,
            "methods": method_names,
            "idl_file": f"{interface_name}.idl" if use_idl else None,
            "tie_file": f"TIE_{interface_name}.h" if generate_tie else None,
        },
        "changeset": master_cs.to_dict(),
        "preview": master_cs.preview(),
        "next_steps": [
            f"Implement {interface_name} methods in {component_name}",
            f"Register {component_name} in Dictionary",
            "Build and test the interface",
        ],
    }


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
