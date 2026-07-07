"""
CATIA CAA Refactor Engine
==========================
Safe, atomic refactoring operations for CAA entities.

Leverages the DependencyGraph to find all impacted files and
produces a ChangeSet for preview → confirm → apply.

Operations:
  rename_command  — Rename a command and update ALL references
  rename_interface — Rename an interface and update all implementors
  move_command     — Move a command to a different module
  rename_module    — Rename a module (updates Imakefile, dictionaries)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from changeset import ChangeSet
from meta_model import (
    Command,
    DependencyGraph,
    Module,
    RelationType,
    WorkspaceSnapshot,
)

# ─── Refactor Operations ─────────────────────────────────────────


def rename_command(
    snapshot: WorkspaceSnapshot,
    module_name: str,
    old_name: str,
    new_name: str,
) -> dict:
    """
    Rename a command and update ALL references across the workspace.

    Updates:
      - Command.h / Command.cpp / CommandHeader.cpp files
      - Imakefile.mk SOURCES
      - Dictionary (.dico) entries
      - NLS catalog entries
      - Workbench references (Addin code + Catalog)
      - Icon files

    Returns:
        {"status": "pending", "changeset": {...}, "preview": {...}}
    """
    mod = snapshot.get_module(module_name)
    if not mod:
        return {"status": "error", "message": f"Module '{module_name}' not found"}

    cmd = next((c for c in mod.commands if c.name.lower() == old_name.lower()), None)
    if not cmd:
        return {
            "status": "error",
            "message": f"Command '{old_name}' not found in '{module_name}'",
        }

    # Check new name doesn't conflict
    existing = next(
        (c for c in mod.commands if c.name.lower() == new_name.lower()), None
    )
    if existing:
        return {"status": "error", "message": f"Command '{new_name}' already exists"}

    cs = ChangeSet(
        action="rename_command",
        description=f"Rename command '{old_name}' → '{new_name}' in '{module_name}'",
    )

    impact = _find_rename_impact(snapshot, cmd, old_name, new_name)

    # 1. Rename source files
    for f in cmd.all_files:
        if f.exists():
            new_path = f.parent / f.name.replace(old_name, new_name, 1)
            cs.add_modify(str(f), "")  # Will be handled as rename
            cs.add_create(
                str(new_path), f.read_text(encoding="utf-8", errors="replace")
            )
            cs.add_delete(f)

    # 2. Update Imakefile
    imake = mod.imakefile_path()
    if imake.exists():
        content = imake.read_text(encoding="utf-8", errors="replace")
        new_content = content.replace(old_name, new_name)
        if new_content != content:
            cs.add_modify(str(imake), new_content)

    # 3. Update Dictionary
    fw = mod.framework
    if fw:
        dico = fw.dictionary_path()
        if dico.exists():
            content = dico.read_text(encoding="utf-8", errors="replace")
            new_content = content.replace(old_name, new_name)
            if new_content != content:
                cs.add_modify(str(dico), new_content)

        # 4. Update NLS
        nls_file = fw.catalog_path()
        if nls_file.exists():
            content = nls_file.read_text(encoding="utf-8", errors="replace")
            new_content = content.replace(old_name, new_name)
            if new_content != content:
                cs.add_modify(str(nls_file), new_content)

    # 5. Update workbench files
    for wb in snapshot.get_all_workbenches():
        for wb_file in [wb.addin_header, wb.addin_source]:
            if wb_file and wb_file.exists():
                content = wb_file.read_text(encoding="utf-8", errors="replace")
                new_content = content.replace(old_name, new_name)
                if new_content != content:
                    cs.add_modify(str(wb_file), new_content)

    cs.metadata["refactor"] = {
        "operation": "rename_command",
        "old_name": old_name,
        "new_name": new_name,
        "module": module_name,
        "impact": impact,
    }

    return {
        "status": "pending",
        "message": f"Rename '{old_name}' → '{new_name}' — preview changes before applying",
        "changeset": cs.to_dict(),
        "preview": cs.preview(),
        "impact": impact,
    }


def rename_interface(
    snapshot: WorkspaceSnapshot,
    module_name: str,
    old_name: str,
    new_name: str,
) -> dict:
    """
    Rename an interface and update all implementing components.

    Updates:
      - Interface.h / Interface.idl files
      - All Component .cpp/.h files that implement it
      - Dictionary entries
      - TIE files
    """
    mod = snapshot.get_module(module_name)
    if not mod:
        return {"status": "error", "message": f"Module '{module_name}' not found"}

    iface = next(
        (i for i in mod.interfaces if i.name.lower() == old_name.lower()), None
    )
    if not iface:
        return {"status": "error", "message": f"Interface '{old_name}' not found"}

    existing = next(
        (i for i in mod.interfaces if i.name.lower() == new_name.lower()), None
    )
    if existing:
        return {"status": "error", "message": f"Interface '{new_name}' already exists"}

    cs = ChangeSet(
        action="rename_interface",
        description=f"Rename interface '{old_name}' → '{new_name}'",
    )

    # Find all components implementing this interface
    impact = {}
    for fw in snapshot.frameworks:
        for m in fw.modules:
            for comp in m.components:
                for imp in comp.implements:
                    if imp.name.lower() == old_name.lower():
                        impact[comp.name] = str(m.path)
                        # Update component files
                        for comp_file in [comp.header, comp.source, comp.tie_header]:
                            if comp_file and comp_file.exists():
                                content = comp_file.read_text(
                                    encoding="utf-8", errors="replace"
                                )
                                new_content = content.replace(old_name, new_name)
                                if new_content != content:
                                    cs.add_modify(str(comp_file), new_content)

    # Rename interface files
    if iface.header and iface.header.exists():
        new_path = iface.header.parent / iface.header.name.replace(old_name, new_name)
        cs.add_delete(iface.header)
        cs.add_create(
            str(new_path),
            iface.header.read_text(encoding="utf-8", errors="replace").replace(
                old_name, new_name
            ),
        )

    if iface.idl_file and iface.idl_file.exists():
        new_path = iface.idl_file.parent / iface.idl_file.name.replace(
            old_name, new_name
        )
        cs.add_delete(iface.idl_file)
        cs.add_create(
            str(new_path),
            iface.idl_file.read_text(encoding="utf-8", errors="replace").replace(
                old_name, new_name
            ),
        )

    # Update Dictionary
    fw = mod.framework
    if fw:
        dico = fw.dictionary_path()
        if dico.exists():
            content = dico.read_text(encoding="utf-8", errors="replace")
            cs.add_modify(str(dico), content.replace(old_name, new_name))

    cs.metadata["refactor"] = {
        "operation": "rename_interface",
        "old_name": old_name,
        "new_name": new_name,
        "impact": impact,
    }

    return {
        "status": "pending",
        "message": f"Rename interface '{old_name}' → '{new_name}' — {len(impact)} component(s) affected",
        "changeset": cs.to_dict(),
        "preview": cs.preview(),
        "impact": impact,
    }


def move_command(
    snapshot: WorkspaceSnapshot,
    source_module: str,
    target_module: str,
    command_name: str,
) -> dict:
    """
    Move a command from one module to another.

    Updates:
      - File locations (src/, LocalInterfaces/)
      - Imakefile of both source and target modules
      - Dictionary entries (lib reference changes)
      - Workbench references
    """
    src_mod = snapshot.get_module(source_module)
    tgt_mod = snapshot.get_module(target_module)

    if not src_mod:
        return {
            "status": "error",
            "message": f"Source module '{source_module}' not found",
        }
    if not tgt_mod:
        return {
            "status": "error",
            "message": f"Target module '{target_module}' not found",
        }

    cmd = next(
        (c for c in src_mod.commands if c.name.lower() == command_name.lower()), None
    )
    if not cmd:
        return {
            "status": "error",
            "message": f"Command '{command_name}' not found in '{source_module}'",
        }

    existing = next(
        (c for c in tgt_mod.commands if c.name.lower() == command_name.lower()), None
    )
    if existing:
        return {
            "status": "error",
            "message": f"Command '{command_name}' already exists in '{target_module}'",
        }

    cs = ChangeSet(
        action="move_command",
        description=f"Move command '{command_name}' from '{source_module}' to '{target_module}'",
    )

    old_lib = src_mod.bare_name
    new_lib = tgt_mod.bare_name

    # 1. Move all files
    for f in cmd.all_files:
        if f.exists():
            # Compute new path in target module
            rel = (
                f.relative_to(src_mod.path)
                if f.is_relative_to(src_mod.path)
                else Path(f.name)
            )
            new_path = tgt_mod.path / rel
            cs.add_delete(f)
            cs.add_create(
                str(new_path), f.read_text(encoding="utf-8", errors="replace")
            )

    # 2. Remove from source Imakefile
    src_imake = src_mod.imakefile_path()
    if src_imake.exists():
        content = src_imake.read_text(encoding="utf-8", errors="replace")
        new_content = "\n".join(
            [l for l in content.split("\n") if command_name not in l]
        )
        cs.add_modify(str(src_imake), new_content)

    # 3. Add to target Imakefile
    tgt_imake = tgt_mod.imakefile_path()
    if tgt_imake.exists():
        content = tgt_imake.read_text(encoding="utf-8", errors="replace")
        new_sources = cmd.imakefile_sources()
        if new_sources not in content:
            new_content = content.replace(
                "SOURCES = \\", f"SOURCES = \\\n{new_sources}"
            )
            cs.add_modify(str(tgt_imake), new_content)

    # 4. Update Dictionary (lib reference changes)
    fw = src_mod.framework
    if fw:
        dico = fw.dictionary_path()
        if dico.exists():
            content = dico.read_text(encoding="utf-8", errors="replace")
            cs.add_modify(str(dico), content.replace(f"lib{old_lib}", f"lib{new_lib}"))

    cs.metadata["refactor"] = {
        "operation": "move_command",
        "command": command_name,
        "from": source_module,
        "to": target_module,
    }

    return {
        "status": "pending",
        "message": f"Move '{command_name}' from '{source_module}' to '{target_module}'",
        "changeset": cs.to_dict(),
        "preview": cs.preview(),
    }


# ─── rename_module ───────────────────────────────────────────────


def rename_module(
    snapshot: WorkspaceSnapshot,
    framework_name: str,
    old_name: str,
    new_name: str,
) -> dict:
    """
    Rename a module and update ALL references.

    Updates:
      - Module directory name
      - Imakefile internal references
      - Dictionary entries (lib name changes)
      - All commands' module references
      - Workbench addin references
    """
    fw = snapshot.get_framework(framework_name)
    if not fw:
        return {"status": "error", "message": f"Framework '{framework_name}' not found"}

    old_mod = next(
        (
            m
            for m in fw.modules
            if m.name.replace(".m", "") == old_name.replace(".m", "")
        ),
        None,
    )
    if not old_mod:
        return {
            "status": "error",
            "message": f"Module '{old_name}' not found in '{framework_name}'",
        }

    new_mod_name = new_name if new_name.endswith(".m") else f"{new_name}.m"
    existing = next((m for m in fw.modules if m.name == new_mod_name), None)
    if existing:
        return {"status": "error", "message": f"Module '{new_mod_name}' already exists"}

    cs = ChangeSet(
        action="rename_module",
        description=f"Rename module '{old_mod.name}' → '{new_mod_name}'",
    )

    old_lib = old_mod.bare_name
    new_lib = new_mod_name.replace(".m", "")

    # 1. Rename directory (via create new + delete old for all files)
    for f in old_mod.path.rglob("*"):
        if f.is_file():
            rel = f.relative_to(old_mod.path)
            new_path = old_mod.path.parent / new_mod_name / rel
            content = f.read_text(encoding="utf-8", errors="replace")
            # Replace old module name references inside files
            content = content.replace(old_lib, new_lib)
            cs.add_create(str(new_path), content)
            cs.add_delete(f)

    # 2. Update Dictionary (lib reference)
    dico = fw.dictionary_path()
    if dico.exists():
        content = dico.read_text(encoding="utf-8", errors="replace")
        cs.add_modify(str(dico), content.replace(f"lib{old_lib}", f"lib{new_lib}"))

    cs.metadata["refactor"] = {
        "operation": "rename_module",
        "old_name": old_mod.name,
        "new_name": new_mod_name,
        "framework": framework_name,
    }

    return {
        "status": "pending",
        "message": f"Rename module '{old_mod.name}' → '{new_mod_name}'",
        "changeset": cs.to_dict(),
        "preview": cs.preview(),
    }


# ─── extract_interface ───────────────────────────────────────────


def extract_interface(
    snapshot: WorkspaceSnapshot,
    module_name: str,
    component_name: str,
    new_interface_name: str,
    methods: Optional[List[str]] = None,
) -> dict:
    """
    Extract a new interface from an existing component.

    Use case: A component has grown and you want to split out an interface.

    Creates:
      - New Interface files (header + IDL)
      - Updates Component to implement the new interface
      - Dictionary registration for the new interface
      - TIE include
    """
    mod = snapshot.get_module(module_name)
    if not mod:
        return {"status": "error", "message": f"Module '{module_name}' not found"}

    comp = next(
        (c for c in mod.components if c.name.lower() == component_name.lower()), None
    )
    if not comp:
        return {"status": "error", "message": f"Component '{component_name}' not found"}

    # Check interface doesn't already exist
    existing_iface = next(
        (i for i in mod.interfaces if i.name.lower() == new_interface_name.lower()),
        None,
    )
    if existing_iface:
        return {
            "status": "error",
            "message": f"Interface '{new_interface_name}' already exists",
        }

    if not new_interface_name.startswith("I"):
        return {
            "status": "error",
            "message": f"Interface name must start with 'I': {new_interface_name}",
        }

    methods = methods or ["Execute"]

    cs = ChangeSet(
        action="extract_interface",
        description=f"Extract '{new_interface_name}' from '{component_name}'",
    )

    fw_name = mod.framework.name if mod.framework else ""

    # 1. Create interface header
    iface_dir = mod.local_interfaces_dir()
    iface_header_content = f"""#ifndef {new_interface_name}_h
#define {new_interface_name}_h

#include "CATBaseUnknown.h"

class {new_interface_name} : public CATBaseUnknown {{
public:
"""
    for m in methods:
        iface_header_content += f"    virtual HRESULT {m}() = 0;\n"
    iface_header_content += f"""}};

#endif
"""
    cs.add_create(str(iface_dir / f"{new_interface_name}.h"), iface_header_content)

    # 2. Create IDL if needed
    iface_dir_pub = mod.public_interfaces_dir()
    idl_content = f"""#include "CATBaseUnknown.idl"

interface {new_interface_name} : CATBaseUnknown {{
"""
    for m in methods:
        idl_content += f"    HRESULT {m}();\n"
    idl_content += "};\n"
    cs.add_create(str(iface_dir_pub / f"{new_interface_name}.idl"), idl_content)

    # 3. Update component header to include new interface
    if comp.header and comp.header.exists():
        content = comp.header.read_text(encoding="utf-8", errors="replace")
        # Add TIE include
        tie_include = f'#include "TIE_{new_interface_name}.h"'
        if tie_include not in content:
            content = content.replace("#include", f"{tie_include}\n#include", 1)
            cs.add_modify(str(comp.header), content)

    # 4. Add to Dictionary
    fw = mod.framework
    if fw:
        dico = fw.dictionary_path()
        if dico.exists():
            content = dico.read_text(encoding="utf-8", errors="replace")
            entry = f"{component_name}  {new_interface_name}  lib{mod.bare_name}"
            if entry not in content:
                cs.add_modify(str(dico), content + f"\n{entry}\n")

    cs.metadata["refactor"] = {
        "operation": "extract_interface",
        "component": component_name,
        "interface": new_interface_name,
        "methods": methods,
    }

    return {
        "status": "pending",
        "message": f"Extract '{new_interface_name}' from '{component_name}' with {len(methods)} method(s)",
        "changeset": cs.to_dict(),
        "preview": cs.preview(),
        "interface": {
            "name": new_interface_name,
            "component": component_name,
            "methods": methods,
        },
    }


# ─── Helpers ─────────────────────────────────────────────────────


def _find_rename_impact(
    snapshot: WorkspaceSnapshot,
    cmd: Command,
    old_name: str,
    new_name: str,
) -> dict:
    """Find all files and entities affected by a rename"""
    impact = {
        "files_to_rename": [],
        "files_to_update": [],
        "entities_affected": [],
    }

    # Command's own files
    for f in cmd.all_files:
        if f.exists():
            impact["files_to_rename"].append(str(f))

    # Imakefile
    if cmd.module:
        impact["files_to_update"].append(str(cmd.module.imakefile_path()))

    # Dictionary and NLS
    if cmd.module and cmd.module.framework:
        fw = cmd.module.framework
        impact["files_to_update"].append(str(fw.dictionary_path()))
        impact["files_to_update"].append(str(fw.catalog_path()))

    # Workbench files
    for wb in snapshot.get_all_workbenches():
        if cmd in wb.commands:
            impact["entities_affected"].append(f"Workbench: {wb.name}")
            if wb.addin_header:
                impact["files_to_update"].append(str(wb.addin_header))
            if wb.addin_source:
                impact["files_to_update"].append(str(wb.addin_source))

    impact["files_to_rename"] = [
        f for f in impact["files_to_rename"] if Path(f).exists()
    ]
    impact["files_to_update"] = [
        f for f in impact["files_to_update"] if Path(f).exists()
    ]

    return impact
