"""
Object-modeling intent functions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from actions import ActionContext
from changeset import ChangeSet

from .helpers import validate_module


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
        "capability": "create_feature",
        "action": "do_not_fix",
        "intent": "create_feature",
        "message": (
            f"暂不支持自动创建特征 '{name}' (capability unavailable, action: do_not_fix)："
            "feature 模版经 B28 全目录核实基于不存在的 API (CATIMmiResultFeature / "
            "SetResult / catalog 调用链)。请手工基于 CATMecModUseItf 开发，证据见 "
            "knowledge/failure_patterns/fp_template_feature_apis.md"
        ),
    }


_CPP_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Only this pair has a verified B28 implementation recipe:
# CATExtIVisu::BuildRep() is pure virtual (Visualization/PublicInterfaces/CATExtIVisu.h).
# Official sample CAAEMmrMeasureSetVisu.cpp binds CATI3DGeoVisu, whose header says
# @CAA2Usage U4 CATExtIVisu. CATIVisu requests use that same adapter path.
# header_map does not list TIE_CATI3DGeoVisu in PublicInterfaces; the official cpp
# still includes <TIE_CATI3DGeoVisu.h>. Do not invent TIE_CATIVisu.
_VERIFIED_VISU_INTERFACES = frozenset({"CATIVisu", "CATI3DGeoVisu"})
_VISU_DICTIONARY_INTERFACE = "CATI3DGeoVisu"
_VISU_ADAPTER = "CATExtIVisu"
_VISU_TIE = "TIE_CATI3DGeoVisu"


def _extension_error(message: str, **extra) -> Dict:
    payload = {
        "status": "error",
        "intent": "create_extension",
        "message": message,
        "changeset": None,
    }
    payload.update(extra)
    return payload


def render_verified_visu_extension(
    name: str,
    target_object: str,
    module: str,
    requested_interfaces: Optional[List[str]] = None,
) -> Dict:
    """Render the verified CATI3DGeoVisu extension skeleton.

    This is a source skeleton taken from the official sample shape. It has not
    been compiled on B28. It does not copy the sample's CATIDescendants or
    CATVisManager calls.
    """
    bare = module[:-2] if module.endswith(".m") else module
    requested = list(requested_interfaces or ["CATIVisu"])
    mapped_from = [item for item in requested if item == "CATIVisu"]
    header = (
        f"#ifndef {name}_H\n"
        f"#define {name}_H\n"
        "\n"
        "// Verified B28 visualization-extension skeleton.\n"
        "// Not compiled by this generator. L4 registration is UNKNOWN.\n"
        "// L5 functional verification is NOT_RUN.\n"
        f"// Requested {', '.join(requested)} is bound as {_VISU_DICTIONARY_INTERFACE}\n"
        f"// through {_VISU_ADAPTER}. Do not treat this as a generated CATIVisu.h.\n"
        "\n"
        "#include \"CATExtIVisu.h\"\n"
        "#include \"CATRep.h\"\n"
        "\n"
        f"class {name} : public {_VISU_ADAPTER}\n"
        "{\n"
        "    CATDeclareClass;\n"
        "\n"
        "public:\n"
        f"    {name}();\n"
        f"    virtual ~{name}();\n"
        "    virtual CATRep *BuildRep();\n"
        "};\n"
        "\n"
        f"#endif\n"
    )
    source = (
        f"#include \"{name}.h\"\n"
        "\n"
        "#include \"CAT3DBagRep.h\"\n"
        "\n"
        f"#include <{_VISU_TIE}.h>\n"
        f"{_VISU_TIE}({name});\n"
        "\n"
        f"CATImplementClass({name}, DataExtension, {_VISU_ADAPTER}, {target_object});\n"
        "\n"
        f"// Dictionary: {target_object} {_VISU_DICTIONARY_INTERFACE} lib{bare}\n"
        "\n"
        f"{name}::{name}()\n"
        "{\n"
        "}\n"
        "\n"
        f"{name}::~{name}()\n"
        "{\n"
        "}\n"
        "\n"
        f"CATRep *{name}::BuildRep()\n"
        "{\n"
        "    // Minimal verified representation. Sample business logic is not copied.\n"
        "    CAT3DBagRep *bag = new CAT3DBagRep();\n"
        "    return bag;\n"
        "}\n"
    )
    dictionary_line = f"{target_object} {_VISU_DICTIONARY_INTERFACE} lib{bare}\n"
    return {
        "header": header,
        "source": source,
        "dictionary_line": dictionary_line,
        "dictionary_interface": _VISU_DICTIONARY_INTERFACE,
        "adapter": _VISU_ADAPTER,
        "tie": _VISU_TIE,
        "requested_interfaces": requested,
        "mapped_from": mapped_from,
        "required_frameworks": ["Visualization", "VisualizationBase"],
        "b28_compiled": False,
        "runtime_registration": "UNKNOWN",
        "functional_verification": "NOT_RUN",
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
    behavior_aspects: Optional[List[str]] = None,
) -> Dict:
    """Create an extension only when a verified B28 recipe exists.

    CATIVisu / CATI3DGeoVisu become a CATExtIVisu data extension with
    TIE_CATI3DGeoVisu and a three-token dictionary line. Any other interface,
    a missing late type, or a data-only request returns error. The generic
    Component template is not used: its Execute() method is not an interface
    implementation.
    """
    ctx.refresh()

    validation = validate_module(ctx, module, framework)
    if validation["status"] == "error":
        validation["intent"] = "create_extension"
        return validation

    if isinstance(implements, str):
        iface_list = [implements] if implements else []
    else:
        iface_list = [str(item) for item in (implements or []) if item]

    if not iface_list:
        return _extension_error(
            "Refusing to generate a data extension without a verified interface recipe. "
            "The generic Component template Execute() method is not a CAA extension implementation.",
            extension={"name": name, "target": target_object, "interfaces": []},
        )

    unverified = [item for item in iface_list if item not in _VERIFIED_VISU_INTERFACES]
    if unverified:
        return _extension_error(
            "No verified B28 implementation recipe for "
            f"{unverified}. Refusing to emit a partial extension or a pending placeholder. "
            "CATIVisu and CATI3DGeoVisu use CATExtIVisu + TIE_CATI3DGeoVisu; other interfaces are not guessed.",
            extension={
                "name": name,
                "target": target_object,
                "interfaces": iface_list,
                "unverified_interfaces": unverified,
            },
        )

    if not target_object or not _CPP_IDENT.match(str(target_object)):
        return _extension_error(
            "target_object must be the late type used as CATImplementClass's fourth argument "
            "and as the dictionary component name. An empty or non-identifier target cannot be emitted.",
            extension={"name": name, "target": target_object, "interfaces": iface_list},
        )
    if not name or not _CPP_IDENT.match(name):
        return _extension_error(
            f"Extension name '{name}' is not a C++ identifier.",
            extension={"name": name, "target": target_object, "interfaces": iface_list},
        )

    bare = module[:-2] if str(module).endswith(".m") else str(module)
    if not _CPP_IDENT.match(bare):
        return _extension_error(
            f"Module '{module}' does not yield a dictionary library name.",
            extension={"name": name, "target": target_object, "interfaces": iface_list},
        )

    mod = ctx.snapshot.get_module(module, framework)
    if not mod or not getattr(mod, "framework", None):
        return _extension_error(
            f"Module '{module}' has no framework dictionary path. "
            "The extension cannot be registered without a .dico line.",
            extension={"name": name, "target": target_object, "interfaces": iface_list},
        )
    fw = mod.framework
    if not callable(getattr(fw, "dictionary_path", None)):
        return _extension_error(
            f"Framework for '{module}' does not expose dictionary_path().",
            extension={"name": name, "target": target_object, "interfaces": iface_list},
        )

    rendered = render_verified_visu_extension(
        name, str(target_object), module, iface_list,
    )
    master_cs = ChangeSet(
        action="create_extension",
        description=f"Create verified visu extension '{name}' for '{target_object}'",
    )
    header_path = mod.local_interfaces_dir() / f"{name}.h"
    source_path = mod.src_dir_path() / f"{name}.cpp"
    master_cs.add_create(header_path, rendered["header"])
    master_cs.add_create(source_path, rendered["source"])

    dico_path = fw.dictionary_path()
    entry = rendered["dictionary_line"]
    if isinstance(dico_path, Path) and dico_path.exists():
        old = dico_path.read_text(encoding="utf-8", errors="replace")
        if entry.strip() not in old.splitlines():
            stripped = old.rstrip()
            master_cs.add_modify(dico_path, (stripped + "\n" if stripped else "") + entry)
    else:
        master_cs.add_create(dico_path, entry)

    extension_info = {
        "name": name,
        "target": target_object,
        "data_members": [d.get("name") for d in (data_members or [])],
        "interfaces": iface_list,
        "implemented_interfaces": [_VISU_DICTIONARY_INTERFACE],
        "bound_interfaces": iface_list,
        "created_interfaces": [],
        "behavior_aspects": list(behavior_aspects or []),
        "interface_binding": {
            "requested": iface_list,
            "dictionary_interface": _VISU_DICTIONARY_INTERFACE,
            "adapter": _VISU_ADAPTER,
            "tie": _VISU_TIE,
            "mapped_from": rendered["mapped_from"],
            "dictionary_line": entry.strip(),
            "note": (
                "CATIVisu is bound through the verified CATI3DGeoVisu adapter path. "
                "This generator does not emit CATIVisu.h or TIE_CATIVisu."
            ),
        },
        "required_frameworks": rendered["required_frameworks"],
        "link_with_injected": False,
        "b28_compiled": False,
        "runtime_registration": "UNKNOWN",
        "functional_verification": "NOT_RUN",
    }
    master_cs.metadata.update(
        {
            "intent": "create_extension",
            "extension": name,
            "target_object": target_object,
            "module": module,
            "implements": iface_list,
            "implemented_interface": _VISU_DICTIONARY_INTERFACE,
            "behavior_aspects": list(behavior_aspects or []),
            "components": extension_info,
            "b28_compiled": False,
        }
    )
    next_steps = [
        "Review the CATExtIVisu skeleton. It has not been compiled on B28.",
        "LINK_WITH for Visualization and VisualizationBase was not injected; "
        "the official sample Imakefile was not retrieved, so library tokens were not guessed.",
        "L4 add-in registration remains UNKNOWN. L5 command verification remains NOT_RUN.",
    ]
    if data_members:
        next_steps.append(
            "Requested data members were recorded but not emitted; there is no verified member recipe."
        )

    return {
        "status": "pending",
        "intent": "create_extension",
        "message": (
            f"Ready to create verified visu extension '{name}' for '{target_object}'. "
            "Skeleton only; not compiled on B28."
        ),
        "extension": extension_info,
        "changeset": master_cs.to_dict(),
        "preview": master_cs.preview(),
        "next_steps": next_steps,
    }
