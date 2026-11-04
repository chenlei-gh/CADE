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

# Libraries the generated skeleton actually needs, established by scanning the
# shipped import libraries for the exact symbols the skeleton references
# (B28/win_b64/code/lib on this machine):
#   CATExtIVisu  -> CATVisualization.lib (331 hits, 0 elsewhere)
#   CAT3DBagRep  -> CATViz.lib (448) and CATVisualization.lib (25)
#   CATRep       -> CATViz.lib (2740), CATVisualization.lib (1025)
#   CATMetaClass (CATDeclareClass/CATImplementClass) -> JS0GROUP.lib (1818)
# The official sample Imakefile additionally links MechanicalModeler,
# ObjectModelerBase, SpecsModeler, KnowledgeItf, etc. Those serve the sample's
# CATIDescendants/CATVisManager business code, which this generator does not
# emit, so they are deliberately not injected.
_VISU_LINK_WITH = ("CATVisualization", "CATViz", "JS0GROUP")


def _inject_link_with(imake_text: str, libs: tuple) -> Optional[str]:
    """Return Imakefile.mk text with missing `libs` added to LINK_WITH.

    Returns None when every library is already present, so callers add no
    patch at all. Only an existing `LINK_WITH` continuation block is extended;
    a file without one is left alone rather than having a second LINK_WITH
    definition appended (mkmk honours the last one, which would silently drop
    the module's own libraries).
    """
    present = _link_line_tokens(imake_text)
    missing = [lib for lib in libs if lib not in present]
    if not missing:
        return None

    nl = "\r\n" if "\r\n" in imake_text else "\n"
    lines = imake_text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if re.match(r"^[ \t]*LINK_WITH[ \t]*=", line):
            start = idx
    if start is None:
        return None

    # Walk to the end of the continuation chain (trailing backslash).
    end = start
    while end < len(lines) and lines[end].rstrip().endswith("\\"):
        end += 1
    if end >= len(lines):
        # Chain runs to EOF; appending a new line is safe there.
        last = len(lines) - 1
    else:
        last = end

    # Append to the chain's final line, keeping whether it continues. Adding a
    # trailing backslash where none existed would make the next statement (e.g.
    # LOCAL_CCFLAGS) part of LINK_WITH, silently dropping it.
    target = lines[last].rstrip()
    if target == "":
        return None
    lines[last] = target + " " + " ".join(missing)
    return nl.join(lines) + (nl if imake_text.endswith(("\r\n", "\n")) else "")


def _strip_comment(line: str) -> str:
    """Drop an mkmk comment, leaving the code part of an Imakefile line."""
    hash_at = line.find("#")
    return line if hash_at < 0 else line[:hash_at]


def _assignments(imake_text: str) -> Dict[str, str]:
    """Map variable name -> value, joining continuation lines and dropping comments.

    `+=` appends, so it is accumulated rather than replacing. mkmk honours the
    last plain `=` definition, which is why only that one is kept.
    """
    values: Dict[str, str] = {}
    lines = imake_text.splitlines()
    idx = 0
    while idx < len(lines):
        code = _strip_comment(lines[idx])
        matched = re.match(
            r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*(\+?=)[ \t]*(.*)$", code
        )
        if not matched:
            idx += 1
            continue
        var, op, rest = matched.group(1), matched.group(2), matched.group(3).strip()
        # Consume the continuation chain belonging to this assignment.
        while lines[idx].rstrip().endswith("\\") and idx + 1 < len(lines):
            idx += 1
            rest = (rest.rstrip("\\").strip() + " " + _strip_comment(lines[idx]).strip()).strip()
        rest = rest.rstrip("\\").strip()
        if op == "+=":
            values[var] = (values.get(var, "") + " " + rest).strip()
        else:
            values[var] = rest
        idx += 1
    return values


def _link_line_tokens(imake_text: str) -> set:
    """Tokens that are actually on LINK_WITH, after expanding `$(VAR)`.

    A library named only in a comment is not linked, and a module can reach
    libraries through an intermediate variable such as
    `WIZARD_LINK_MODULES`. Counting tokens from the whole file gets both
    wrong, in opposite directions.
    """
    values = _assignments(imake_text)
    tokens: set = set()
    seen_vars: set = set()

    def expand(name: str) -> None:
        if name in seen_vars:
            return
        seen_vars.add(name)
        raw = values.get(name)
        if raw is None:
            return
        for ref in re.findall(r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)", raw):
            expand(ref)
        for word in re.split(r"\s+", re.sub(r"\$\([A-Za-z_][A-Za-z0-9_]*\)", " ", raw)):
            if re.fullmatch(r"[A-Za-z0-9_]+", word):
                tokens.add(word)

    expand("LINK_WITH")
    return tokens


def _link_with_state(imake_text: str, libs: tuple) -> str:
    """Classify whether `libs` are guaranteed on the module's link line.

    `_inject_link_with` returns None both when nothing has to change and when
    nothing *can* be changed; that is enough for a caller writing a patch, but
    not for a caller reporting on the build contract. This separates the cases:

      ALREADY_SATISFIED   every library is already on the link line
      INJECTED            the patch adds them
      NO_LINK_WITH_BLOCK  there is no LINK_WITH definition to extend
      UNPATCHABLE_LINK_WITH  LINK_WITH exists but its continuation chain ends
                          on a blank line, so there is no line to append to

    Only the first two mean the extension's link contract is met.
    """
    present = _link_line_tokens(imake_text)
    if all(lib in present for lib in libs):
        return "ALREADY_SATISFIED"
    if not re.search(r"^[ \t]*LINK_WITH[ \t]*=", imake_text, re.MULTILINE):
        return "NO_LINK_WITH_BLOCK"
    if _inject_link_with(imake_text, libs) is None:
        return "UNPATCHABLE_LINK_WITH"
    return "INJECTED"


def _add_prerequisites(identity_xml: str, frameworks: tuple) -> Optional[str]:
    """Return IdentityCard.xml text declaring `frameworks` as Public prerequisites.

    mkmk ignores a LINK_WITH library whose framework is not a direct
    prerequisite of the module's framework:

        Module [Visualization\\CATVisualization.m] in 'LINK_WITH' is ignored
        because it is in framework [Visualization] which is not a direct
        prerequisite

    The link then fails with unresolved externals (LNK2001). A link line alone
    is therefore not a build contract; the prerequisite has to be declared.

    Returns None when every framework is already declared (idempotent) or when
    the file is not the XML form (a .h IdentityCard has its own syntax and is
    left untouched rather than corrupted).
    """
    if "<eduFramework" not in identity_xml:
        return None
    missing = [
        fw for fw in frameworks
        if not re.search(
            r"<prerequisite\b[^>]*\bname\s*=\s*[\"']" + re.escape(fw) + r"[\"']",
            identity_xml,
        )
    ]
    if not missing:
        return None

    nl = "\r\n" if "\r\n" in identity_xml else "\n"
    indent = "  "
    block = "".join(
        f'{indent}<prerequisite name="{fw}" access="Public" />{nl}' for fw in missing
    )
    closing = identity_xml.rfind("</eduFramework>")
    if closing < 0:
        return None
    line_start = identity_xml.rfind(nl, 0, closing)
    head = identity_xml if line_start < 0 else identity_xml[: line_start + len(nl)]
    tail = "" if line_start < 0 else identity_xml[line_start + len(nl):]
    return head + block + tail


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
    target_late_type_state: str = None,
    target_late_type_candidates: Optional[List[str]] = None,
) -> Dict:
    """Create an extension only when a verified B28 recipe exists.

    CATIVisu / CATI3DGeoVisu become a CATExtIVisu data extension with
    TIE_CATI3DGeoVisu and a three-token dictionary line. Any other interface,
    a missing late type, or a data-only request returns error. The generic
    Component template is not used: its Execute() method is not an interface
    implementation.

    target_object must be a CATIA component that exists in local evidence
    (shipped .dic or CAADoc samples). A requirement category such as
    ``feature`` is rejected instead of being registered as a late type.
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

    # A requirement category (feature/component/document) is not a CATIA
    # component. Registering it would produce CATImplementClass(..., feature)
    # and a dictionary line no CATIA install can bind.
    try:
        from late_type_resolver import LateTypeResolver
        late_type_info = LateTypeResolver().describe(str(target_object))
    except Exception:  # noqa: BLE001 - resolver absence must not fake a pass
        late_type_info = {"is_late_type": False, "reason": "late_type_resolver_unavailable"}
    if not late_type_info.get("is_late_type"):
        return _extension_error(
            f"'{target_object}' is not a CATIA late type (absent from the shipped .dic "
            "and CAADoc sample dictionaries). An extension target must be a real "
            "component; a requirement category cannot be registered as one.",
            extension={
                "name": name,
                "target": target_object,
                "interfaces": iface_list,
                "target_late_type_state": target_late_type_state or "UNKNOWN",
                "target_late_type_candidates": list(target_late_type_candidates or []),
            },
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

    # Link contract: the skeleton calls CATExtIVisu::BuildRep and new
    # CAT3DBagRep, so the module must link CATVisualization/CATViz/JS0GROUP.
    # Without this the skeleton compiles but fails at link time (LNK2019).
    link_with_injected = False
    link_with_added: List[str] = []
    link_contract_state = "NO_IMAKEFILE"
    imake_path = mod.imakefile_path()
    imake_old = None
    if imake_path.exists():
        raw_imake = imake_path.read_text(encoding="utf-8", errors="replace")
        # Only a real file body can be patched; a non-str here would mean the
        # snapshot handed back a placeholder, and rewriting it would corrupt
        # the Imakefile.
        if isinstance(raw_imake, str):
            imake_old = raw_imake
            link_contract_state = _link_with_state(imake_old, _VISU_LINK_WITH)
            imake_new = _inject_link_with(imake_old, _VISU_LINK_WITH)
            if imake_new is not None:
                master_cs.add_modify(imake_path, imake_new)
                link_with_injected = True
                present = _link_line_tokens(imake_old)
                link_with_added = [lib for lib in _VISU_LINK_WITH if lib not in present]

    dico_path = fw.dictionary_path()
    entry = rendered["dictionary_line"]
    if isinstance(dico_path, Path) and dico_path.exists():
        old = dico_path.read_text(encoding="utf-8", errors="replace")
        if entry.strip() not in old.splitlines():
            stripped = old.rstrip()
            master_cs.add_modify(dico_path, (stripped + "\n" if stripped else "") + entry)
    else:
        master_cs.add_create(dico_path, entry)

    # Framework prerequisites: mkmk drops any LINK_WITH library whose framework
    # is not a direct prerequisite, so the link line injected above is only
    # honoured once these are declared. Verified on B28: without this the build
    # fails with LNK2001 (129 unresolved externals), with it 0 errors.
    prerequisites_added: List[str] = []
    prereq_state = "NO_IDENTITYCARD"
    identity_path = None
    if callable(getattr(fw, "identitycard_path", None)):
        candidate = fw.identitycard_path()
        if isinstance(candidate, Path) and candidate.exists():
            identity_path = candidate
            identity_old = candidate.read_text(encoding="utf-8", errors="replace")
            identity_new = _add_prerequisites(
                identity_old, tuple(rendered["required_frameworks"])
            )
            if identity_new is None:
                prereq_state = (
                    "ALREADY_DECLARED"
                    if "<eduFramework" in identity_old
                    else "NOT_XML_IDENTITYCARD"
                )
            else:
                master_cs.add_modify(candidate, identity_new)
                prerequisites_added = [
                    fw_name for fw_name in rendered["required_frameworks"]
                    if not re.search(
                        r"<prerequisite\b[^>]*\bname\s*=\s*[\"']"
                        + re.escape(fw_name) + r"[\"']",
                        identity_old,
                    )
                ]
                prereq_state = "DECLARED"

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
        "required_libraries": list(_VISU_LINK_WITH),
        "framework_prerequisite_state": prereq_state,
        "framework_prerequisites_added": prerequisites_added,
        "identitycard_path": str(identity_path) if identity_path else None,
        "link_contract_state": link_contract_state,
        "link_contract_satisfied": link_contract_state in (
            "INJECTED",
            "ALREADY_SATISFIED",
        ),
        "link_with_injected": link_with_injected,
        "link_with_added": link_with_added,
        "imakefile_present": imake_old is not None,
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
    ]
    if link_with_injected:
        next_steps.append(
            "LINK_WITH was extended with "
            + ", ".join(link_with_added)
            + " (established by scanning the shipped import libraries for "
            "CATExtIVisu, CAT3DBagRep, CATRep and CATMetaClass)."
        )
    elif imake_old is None:
        next_steps.append(
            "The module has no Imakefile.mk yet, so LINK_WITH was not extended. "
            "The skeleton needs "
            + ", ".join(_VISU_LINK_WITH)
            + " to link."
        )
    elif link_contract_state == "ALREADY_SATISFIED":
        next_steps.append(
            "LINK_WITH already contained "
            + ", ".join(_VISU_LINK_WITH)
            + "; no Imakefile patch was needed."
        )
    elif link_contract_state == "UNPATCHABLE_LINK_WITH":
        next_steps.append(
            "The module's LINK_WITH definition has an empty continuation line, so "
            + ", ".join(_VISU_LINK_WITH)
            + " could not be appended. The link contract is NOT met: add them to "
            "LINK_WITH by hand before building, or the skeleton will fail to link."
        )
    else:
        next_steps.append(
            "The module's Imakefile.mk defines no LINK_WITH, so the extension's link "
            "contract is NOT met. "
            + ", ".join(_VISU_LINK_WITH)
            + " must be added to LINK_WITH by hand before building. The line was not "
            "appended automatically because mkmk honours the last LINK_WITH, so a "
            "second definition would silently drop the module's own libraries."
        )
    next_steps.append(
        "L4 add-in registration remains UNKNOWN. L5 command verification remains NOT_RUN."
    )
    if prereq_state == "DECLARED":
        next_steps.append(
            "IdentityCard.xml now declares "
            + ", ".join(prerequisites_added)
            + " as Public prerequisites. mkmk ignores a LINK_WITH library whose "
            "framework is not a direct prerequisite, so without this the link line "
            "would be dropped and the build would fail with LNK2001."
        )
    elif prereq_state == "NOT_XML_IDENTITYCARD":
        next_steps.append(
            "The framework IdentityCard is not XML, so "
            + ", ".join(rendered["required_frameworks"])
            + " was not declared automatically. mkmk ignores LINK_WITH libraries from "
            "frameworks that are not direct prerequisites: declare them by hand or "
            "the build fails with LNK2001."
        )
    elif prereq_state == "NO_IDENTITYCARD":
        next_steps.append(
            "The framework has no IdentityCard, so "
            + ", ".join(rendered["required_frameworks"])
            + " was not declared. mkmk ignores LINK_WITH libraries from frameworks "
            "that are not direct prerequisites: the build fails with LNK2001."
        )
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
