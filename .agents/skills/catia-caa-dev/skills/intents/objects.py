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
    # Route degradation: feature templates verified fabricated against the
    # full B28 installation (2026-07). See fp_template_feature_apis.md.
    # The original implementation is preserved in git history.
    return {
        "status": "error",
        "intent": "create_feature",
        "message": (
            f"暂不支持自动创建特征 '{name}'：feature 模版经 B28 全目录核实"
            "基于不存在的 API (CATIMmiResultFeature / SetResult / catalog "
            "调用链)。请手工基于 CATMecModUseItf 开发，证据见 "
            "knowledge/failure_patterns/fp_template_feature_apis.md"
        ),
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
