#!/usr/bin/env python3
"""
L5: Semantic Integrity Tests
==============================
Verify that CAA artifacts and Rich Domain Model entities are semantically complete:
  - Framework defines dictionary, catalog, and module structure
  - Module defines compilation paths and container relations
  - Command has header, source, dictionary entry, and NLS blocks
  - Interface adheres to CAA naming conventions and IDL contracts
  - Component implements interfaces and defines parent class
  - Serialization to dict preserves entity identity and semantics
"""

import sys
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from meta_model import (
    Command,
    Component,
    Dialog,
    Framework,
    Interface,
    Module,
    Visibility,
    Workbench,
)

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(
        f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else "")
    )


print("=" * 70)
print("  L5: Semantic Integrity Tests")
print("=" * 70)

# Mock framework and module
fw = Framework(name="MyFW.edu", path=Path("/ws/MyFW.edu"))
mod = Module(name="GeoMod.m", path=Path("/ws/MyFW.edu/GeoMod.m"), framework=fw)
fw.add_module(mod)
wb = Workbench(name="GeometryWB", path=Path("/ws/MyFW.edu/CNext"), framework=fw)
fw.workbenches.append(wb)

# ═══════════════════════════════════════════════════════════════════
# 1. Command semantic completeness
# ═══════════════════════════════════════════════════════════════════

print("\n[1] Command semantic completeness")

dlg = Dialog(name="CalculateVolumeDlg", path=Path("/ws/MyFW.edu/GeoMod.m/src/CalculateVolumeDlg.cpp"), module=mod)
cmd = Command(
    name="CalculateVolume",
    path=Path("/ws/MyFW.edu/GeoMod.m/src/CalculateVolume.cpp"),
    module=mod,
    is_stateful=True,
    tooltip="Calculate Volume of selected geometry",
    dialog=dlg,
    workbench=wb,
    visibility=Visibility.ALWAYS,
)
dlg.parent_command = cmd

# A complete Command entity must have ALL these
ck("1.1 name non-empty", len(cmd.name) > 0)
ck("1.2 module attached", cmd.module is not None and cmd.module.name == "GeoMod.m")
ck("1.3 stateful flag set", cmd.is_stateful)
ck("1.4 dialog attached", cmd.dialog is not None)
ck("1.5 dialog has name", len(cmd.dialog.name) > 0)
ck("1.6 workbench specified", cmd.workbench is not None and len(cmd.workbench.name) > 0)

# Registration generation
dico_entry = cmd.dictionary_entry()
ck("1.7 dictionary entry valid", "CalculateVolume" in dico_entry and "CATIAfrGeneralWksAddin" in dico_entry)
nls_block = cmd.nls_block()
ck("1.8 NLS block has title and tip", "CalculateVolume.Title" in nls_block and "CalculateVolume.Tip" in nls_block)

# ═══════════════════════════════════════════════════════════════════
# 2. Interface semantic completeness
# ═══════════════════════════════════════════════════════════════════

print("\n[2] Interface semantic completeness")

comp = Component(
    name="MyServiceComponent",
    path=Path("/ws/MyFW.edu/GeoMod.m/src/MyServiceComponent.cpp"),
    module=mod,
)

iface = Interface(
    name="IMyService",
    path=Path("/ws/MyFW.edu/GeoMod.m/PublicInterfaces/IMyService.h"),
    module=mod,
    is_idl=True,
    implemented_by=[comp],
)

ck("2.1 has I-prefix", iface.name.startswith("I"))
ck("2.2 module attached", iface.module is not None)
ck("2.3 is_idl flag set", iface.is_idl)
ck("2.4 idl_path computes PublicInterfaces", "PublicInterfaces" in str(iface.idl_path()))
ck("2.5 header_path computes PublicInterfaces", "PublicInterfaces" in str(iface.header_path()))
ck("2.6 implemented_by has component", len(iface.implemented_by) == 1)
d_iface = iface.to_dict()
ck("2.7 to_dict includes module", d_iface.get("module") == "GeoMod.m")
ck("2.8 to_dict includes is_idl", d_iface.get("is_idl") is True)

# ═══════════════════════════════════════════════════════════════════
# 3. Module & Framework container semantics
# ═══════════════════════════════════════════════════════════════════

print("\n[3] Module & Framework container semantics")

ck("3.1 Framework bare_name strips .edu", fw.bare_name == "MyFW")
ck("3.2 Framework dictionary_path computes CNext/code/dictionary", "dictionary" in str(fw.dictionary_path()))
ck("3.3 Framework catalog_path computes msgcatalog", "msgcatalog" in str(fw.catalog_path()))
ck("3.4 Module bare_name strips .m", mod.bare_name == "GeoMod")
ck("3.5 Module src_dir_path computes src", "src" in str(mod.src_dir_path()))
ck("3.6 Module imakefile_path computes Imakefile.mk", "Imakefile.mk" in str(mod.imakefile_path()))

# ═══════════════════════════════════════════════════════════════════
# 4. Component & Dialog semantics
# ═══════════════════════════════════════════════════════════════════

print("\n[4] Component & Dialog semantics")

comp.implements.append(iface)
ck("4.1 Component parent_class default", comp.parent_class == "CATBaseUnknown")
ck("4.2 Component boa_bound flag", comp.boa_bound is True)
d_comp = comp.to_dict()
ck("4.3 Component to_dict includes parent_class", d_comp.get("parent_class") == "CATBaseUnknown")
ck("4.4 Dialog parent_command relation", dlg.parent_command is cmd)
d_dlg = dlg.to_dict()
ck("4.5 Dialog to_dict includes parent_command", d_dlg.get("parent_command") == "CalculateVolume")

# ═══════════════════════════════════════════════════════════════════
# 5. Round-trip serialization & entity integrity
# ═══════════════════════════════════════════════════════════════════

print("\n[5] Round-trip serialization & entity integrity")

for entity in [cmd, iface, comp, dlg]:
    d = entity.to_dict()
    ck(f"5.x {entity.__class__.__name__} to_dict preserves name", d.get("name") == entity.name)
    ck(f"5.x {entity.__class__.__name__} to_dict preserves path", d.get("path") == str(entity.path))

# ═══════════════════════════════════════════════════════════════════
# 6. CAA naming conventions
# ═══════════════════════════════════════════════════════════════════

print("\n[6] CAA naming conventions")

# Interface names must start with I
def validate_interface_name(name: str) -> bool:
    return len(name) >= 2 and name.startswith("I") and name[1].isupper()

ck("6.1 Interface with I-prefix valid", validate_interface_name("IMyInterface"))
ck("6.2 Interface without I-prefix invalid", not validate_interface_name("MyInterface"))

# Component names should NOT start with I
def validate_component_name(name: str) -> bool:
    return not (name.startswith("I") and len(name) >= 2 and name[1].isupper())

ck("6.3 Component name does not start with I", validate_component_name(comp.name))
ck("6.4 Component implements interface list", len(comp.implements) >= 1)
ck("6.5 Module has bare_name consistency", mod.bare_name + ".m" == mod.name)

# ═══════════════════════════════════════════════════════════════════
print(f"\n{'=' * 70}")
print(f"  L5 Semantic: {passed}/{total} ({passed / total * 100:.0f}%)")
print(f"{'=' * 70}")
sys.exit(0 if passed == total else 1)
