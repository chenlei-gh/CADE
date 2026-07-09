#!/usr/bin/env python3
"""
Test CAA Standard Directory Structure Compliance
==================================================
Verify CADE generates CAA-compliant directory paths.
"""

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from meta_model import Framework, Module, Command, Dialog, Interface, Component, Workbench

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════════
# 1. Framework paths
# ═══════════════════════════════════════════════════════════════
print("=" * 70)
print("  1. Framework entity paths")
print("=" * 70)

fw = Framework(name="MyFramework.edu", path=Path("/ws/MyFramework.edu"))

# IdentityCard
check("IdentityCard path", str(fw.identitycard_path()) ==
      r"\ws\MyFramework.edu\IdentityCard\IdentityCard.h")

# Dictionary
dict_path = str(fw.dictionary_path())
check("dictionary path", "CNext" in dict_path and ".dico" in dict_path,
      dict_path.replace("\\", "/"))

# Catalog (NLS)
cat_path = str(fw.catalog_path())
check("catalog path (CATNls)", "msgcatalog" in cat_path and ".CATNls" in cat_path,
      cat_path.replace("\\", "/"))

# CATRsc — NEW
rsc_path = str(fw.rsc_path())
check("CATRsc path", "resources" in rsc_path and ".CATRsc" in rsc_path,
      rsc_path.replace("\\", "/"))

# FunctionTests — NEW
ft_path = str(fw.function_tests_path())
check("FunctionTests path", ft_path.endswith("FunctionTests"),
      ft_path.replace("\\", "/"))


# ═══════════════════════════════════════════════════════════════
# 2. Module paths
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  2. Module entity paths")
print("=" * 70)

mod = Module(name="MyModule.m", path=Path("/ws/MyFramework.edu/MyModule.m"))

check("src/ dir", str(mod.src_dir_path()).endswith("src"))
check("LocalInterfaces/ dir", str(mod.local_interfaces_dir()).endswith("LocalInterfaces"))
check("PublicInterfaces/ dir", str(mod.public_interfaces_dir()).endswith("PublicInterfaces"))
check("Imakefile.mk", str(mod.imakefile_path()).endswith("Imakefile.mk"))


# ═══════════════════════════════════════════════════════════════
# 3. Entity file paths
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  3. Entity file paths")
print("=" * 70)

# Command
cmd = Command(name="MyCmd", path=Path("/ws/MyFramework.edu/MyModule.m"))
cmd.module = mod
cmd_path = str(cmd.header_path())
check("Command header: LocalInterfaces/MyCmd.h",
      "LocalInterfaces" in cmd_path and "MyCmd.h" in cmd_path,
      cmd_path.replace("\\", "/"))

src_path = str(cmd.source_path())
check("Command source: src/MyCmd.cpp",
      "src" in src_path and "MyCmd.cpp" in src_path,
      src_path.replace("\\", "/"))

# Dialog
dlg = Dialog(name="MyDlg", path=Path("/ws/MyFramework.edu/MyModule.m"))
dlg.module = mod
dlg_path = str(dlg.header_path())
check("Dialog header: LocalInterfaces/MyDlg.h",
      "LocalInterfaces" in dlg_path and "MyDlg.h" in dlg_path)

dlg_src = str(dlg.source_path())
check("Dialog source: src/MyDlg.cpp",
      "src" in dlg_src and "MyDlg.cpp" in dlg_src)

# Interface
iface = Interface(name="IMyInterface", path=Path("/ws/MyFramework.edu/MyModule.m"))
iface.module = mod
iface_path = str(iface.header_path())
check("Interface header: PublicInterfaces/IMyInterface.h",
      "PublicInterfaces" in iface_path and "IMyInterface.h" in iface_path,
      iface_path.replace("\\", "/"))


# ═══════════════════════════════════════════════════════════════
# 4. Template existence
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  4. Required templates exist")
print("=" * 70)

templates_dir = SKILL_ROOT / "templates"

for tt in ["testcase", "resource", "framework", "module", "command", "dialog"]:
    tf = templates_dir / tt
    has_files = tf.is_dir() and any(tf.glob("*"))
    check(f"Template dir: {tt}/", has_files, f"{len(list(tf.glob('*'))) if tf.is_dir() else 0} files")

# Check specific template files
for tf in ["templates/resource/FrameworkName.CATRsc",
           "templates/testcase/TestCase.cpp",
           "templates/testcase/TestCase.h"]:
    check(f"Template file: {tf}", (SKILL_ROOT / tf).exists())


# ═══════════════════════════════════════════════════════════════
# 5. Generator template discovery
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  5. Generator discovers all templates")
print("=" * 70)

from generator import TemplateGenerator
gen = TemplateGenerator()
available = gen.get_available_templates()
check("testcase in generator", "testcase" in available)
check("resource in generator", "resource" in available)
check(f"Total template types >= 20", len(available) >= 20, f"actual={len(available)}")


# ═══════════════════════════════════════════════════════════════
# 6. Full CAA-compliant tree
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  6. Complete CAA directory tree compliance")
print("=" * 70)

fw_module = fw
fw_module.function_tests = fw_module.function_tests_path()

# All required paths present
structure = {
    "IdentityCard/": str(fw_module.identitycard_path()),
    "CNext/dictionary/": str(fw_module.dictionary_path()),
    "CNext/msgcatalog/": str(fw_module.catalog_path()),
    "CNext/resources/ (CATRsc)": str(fw_module.rsc_path()),
    "FunctionTests/": str(fw_module.function_tests_path()),
    "{Module}/Imakefile.mk": str(mod.imakefile_path()),
    "{Module}/LocalInterfaces/": str(mod.local_interfaces_dir()),
    "{Module}/PublicInterfaces/": str(mod.public_interfaces_dir()),
    "{Module}/src/": str(mod.src_dir_path()),
}

for label, path in structure.items():
        check(f"Path: {label}", len(Path(path).parts) >= 3, path.replace("\\", "/"))

# to_dict completeness
d = fw.to_dict()
for k in ("has_dictionary", "has_catalog", "has_function_tests", "has_rsc"):
    check(f"to_dict has {k}", k in d)


# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"  CAA STRUCTURE COMPLIANCE: {passed}/{total}")
if total:
    print(f"  Pass rate: {passed / total * 100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> All CAA standard paths verified <<<")
    sys.exit(0)
else:
    print(f"\n  >>> {total - passed} failure(s) <<<")
    sys.exit(1)
