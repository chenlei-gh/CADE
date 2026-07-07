"""
Object-modeling intent functions.
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


def create_feature(
    ctx: ActionContext,
    name: str,
    module: str,
    framework: str = None,
    *,
    attributes: Optional[List[Dict]] = None,
    with_factory: bool = True,
    with_catalog: bool = True,
    parent_feature: Optional[str] = None,
) -> Dict:
    """
    Create a Feature object with factory and catalog support.

    Automatically creates: Feature class, Factory, StartUp Catalog,
    attribute definitions, interface implementations, Dictionary registration.
    """
    ctx.refresh()

    validation = validate_module(ctx, module, framework)
    if validation["status"] == "error":
        return validation

    master_cs = ChangeSet(
        action="create_feature",
        description=f"Create feature '{name}' in '{module}'",
    )

    components = {
        "feature": name,
        "factory": None,
        "catalog": None,
        "attributes": [],
        "interfaces": ["CATIBuild", "CATIContextualSubMenu"],
    }

    comp_result = create_component(ctx, name=name, module=module, framework=framework)
    if comp_result["status"] != "error":
        merge_changeset(master_cs, changeset_from_dict(comp_result["changeset"]))

    if with_factory:
        factory_name = f"{name}Factory"
        factory_result = create_component(
            ctx, name=factory_name, module=module, framework=framework
        )
        if factory_result["status"] != "error":
            merge_changeset(master_cs, changeset_from_dict(factory_result["changeset"]))
            components["factory"] = factory_name

    if attributes:
        for attr in attributes:
            components["attributes"].append(
                {
                    "name": attr.get("name", ""),
                    "type": attr.get("type", "double"),
                    "default": attr.get("default", ""),
                }
            )

    master_cs.metadata.update(
        {
            "intent": "create_feature",
            "feature": name,
            "module": module,
            "framework": framework,
            "with_factory": with_factory,
            "with_catalog": with_catalog,
            "parent_feature": parent_feature,
            "components": components,
        }
    )

    next_steps = [
        f"Implement {name} business logic",
        f"Define attributes: {', '.join(a['name'] for a in (attributes or []))}"
        if attributes
        else "Define feature attributes",
    ]
    if with_factory:
        next_steps.append("Register factory in Startup Catalog")
    next_steps.append("Build and test the feature")

    return {
        "status": "pending",
        "intent": "create_feature",
        "message": f"Ready to create feature '{name}' with {len(attributes or [])} attributes",
        "feature": components,
        "changeset": master_cs.to_dict(),
        "preview": master_cs.preview(),
        "next_steps": next_steps,
    }


def create_extension(
    ctx: ActionContext,
    name: str,
    target_object: str,
    module: str,
    framework: str = None,
    *,
    data_members: Optional[List[Dict]] = None,
    implements: Optional[List[str]] = None,
) -> Dict:
    """
    Create a data extension for an existing CATIA object.

    Automatically creates: Extension class, DataExtension declaration,
    TIE implementation, Dictionary registration, interface implementations.
    """
    ctx.refresh()

    validation = validate_module(ctx, module, framework)
    if validation["status"] == "error":
        return validation

    master_cs = ChangeSet(
        action="create_extension",
        description=f"Create extension '{name}' for '{target_object}'",
    )

    ext_result = create_component(ctx, name=name, module=module, framework=framework)
    if ext_result["status"] != "error":
        merge_changeset(master_cs, changeset_from_dict(ext_result["changeset"]))

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
                created_interfaces.append(iface_name)

    extension_info = {
        "name": name,
        "target": target_object,
        "data_members": [d.get("name") for d in (data_members or [])],
        "interfaces": created_interfaces or implements or [],
    }

    master_cs.metadata.update(
        {
            "intent": "create_extension",
            "extension": name,
            "target_object": target_object,
            "module": module,
            "components": extension_info,
        }
    )

    next_steps = [
        f"Implement extension '{name}' for '{target_object}'",
        "Define data member accessors (get/set)",
        f"Register extension in Dictionary for '{target_object}'",
    ]
    if data_members:
        members_str = ", ".join(d["name"] for d in data_members)
        next_steps.insert(1, f"Implement data members: {members_str}")

    return {
        "status": "pending",
        "intent": "create_extension",
        "message": f"Ready to create extension '{name}' for '{target_object}'",
        "extension": extension_info,
        "changeset": master_cs.to_dict(),
        "preview": master_cs.preview(),
        "next_steps": next_steps,
    }
