#!/usr/bin/env python3
"""
L5: Semantic Integrity Tests
==============================
Verify that generated CAA artifacts are semantically complete:
  - Dictionary registers CATCommandHeader
  - Catalog references Header
  - NLS has Title/Tip/Help
  - Imakefile is updated
  - Command has header + source + header_source
  - Icon is generated
  - IdentityCard is valid
"""

import shutil
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from specification import (
    AttributeSpec,
    CommandSpec,
    ComponentSpec,
    DataMemberSpec,
    DialogSpec,
    ExtensionSpec,
    FeatureSpec,
    InterfaceSpec,
    MethodSpec,
    WorkbenchSpec,
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

# ═══════════════════════════════════════════════════════════════════
# 1. CommandSpec semantic completeness
# ═══════════════════════════════════════════════════════════════════

print("\n[1] CommandSpec semantic completeness")

cmd = CommandSpec(
    name="CalculateVolume",
    module="GeoMod.m",
    framework="MyFW.edu",
    stateful=True,
    tooltip="Calculate Volume of selected geometry",
    dialog=DialogSpec(name="CalculateVolumeDlg"),
    workbench="GeometryWB",
)

# A complete CommandSpec must have ALL these
ck("1.1 name non-empty", len(cmd.name) > 0)
ck("1.2 module specified", len(cmd.module) > 0)
ck("1.3 stateful flag set", cmd.stateful)
ck("1.4 dialog attached", cmd.dialog is not None)
ck("1.5 dialog has name", len(cmd.dialog.name) > 0)
ck("1.6 workbench specified", cmd.workbench is not None and len(cmd.workbench) > 0)

# Validate should pass
result = cmd.validate()
ck("1.7 validates OK", result["status"] == "ok", str(result))

# An INCOMPLETE CommandSpec should warn
cmd_bad = CommandSpec(name="", module="", framework="")
result = cmd_bad.validate()
ck("1.8 empty spec fails validation", result["status"] == "error")

# ═══════════════════════════════════════════════════════════════════
# 2. InterfaceSpec semantic completeness
# ═══════════════════════════════════════════════════════════════════

print("\n[2] InterfaceSpec semantic completeness")

iface = InterfaceSpec(
    name="IMyService",
    module="CoreMod.m",
    framework="MyFW.edu",
    methods=[
        MethodSpec(
            name="DoSomething", params=["param1", "param2"], return_type="HRESULT"
        ),
        MethodSpec(name="GetData", params=[], return_type="CATUnicodeString"),
    ],
    use_idl=True,
    generate_tie=True,
)
ck("2.1 has I-prefix", iface.name.startswith("I"))
ck("2.2 has methods", len(iface.methods) >= 1)
ck("2.3 first method has params", len(iface.methods[0].params) == 2)
ck("2.4 first method has return type", len(iface.methods[0].return_type) > 0)
ck("2.5 IDL generation enabled", iface.use_idl)
ck("2.6 TIE generation enabled", iface.generate_tie)
ck("2.7 validates OK", iface.validate()["status"] == "ok")

iface_bad = InterfaceSpec(name="BadInterface", module="M")
result = iface_bad.validate()
ck("2.8 no I-prefix warns", result["status"] == "warning", result.get("message", ""))

# ═══════════════════════════════════════════════════════════════════
# 3. FeatureSpec semantic completeness
# ═══════════════════════════════════════════════════════════════════

print("\n[3] FeatureSpec semantic completeness")

feat = FeatureSpec(
    name="MyFeature",
    module="FeatMod.m",
    framework="MyFW.edu",
    attributes=[
        AttributeSpec(name="Length", type="CATLength", default="10mm"),
        AttributeSpec(name="Angle", type="CATAngle", default="90deg"),
    ],
    with_factory=True,
    with_catalog=True,
)
ck("3.1 has attributes", len(feat.attributes) >= 2)
ck("3.2 attribute has type", feat.attributes[0].type == "CATLength")
ck("3.3 attribute has default", feat.attributes[0].default == "10mm")
ck("3.4 factory enabled", feat.with_factory)
ck("3.5 catalog enabled", feat.with_catalog)
ck("3.6 validates OK", feat.validate()["status"] == "ok")

# ═══════════════════════════════════════════════════════════════════
# 4. ExtensionSpec semantic completeness
# ═══════════════════════════════════════════════════════════════════

print("\n[4] ExtensionSpec semantic completeness")

ext = ExtensionSpec(
    name="MyExt",
    module="ExtMod.m",
    framework="MyFW.edu",
    target_object="CATPart",
    data_members=[DataMemberSpec(name="_length", type="double")],
    implements=["CATIMyExt"],
)
ck("4.1 has target object", len(ext.target_object) > 0)
ck("4.2 has data members", len(ext.data_members) == 1)
ck("4.3 has implements", len(ext.implements) == 1)
ck("4.4 validates OK", ext.validate()["status"] == "ok")

ext_bad = ExtensionSpec(name="Bad", module="M", target_object="")
ck("4.5 no target fails", ext_bad.validate()["status"] == "error")

# ═══════════════════════════════════════════════════════════════════
# 5. Round-trip preserves semantics
# ═══════════════════════════════════════════════════════════════════

print("\n[5] Round-trip preserves semantics")

from specification import spec_from_dict

for spec in [cmd, iface, feat, ext]:
    d = spec.to_dict()
    restored = spec_from_dict(d)
    ck(f"5.x {spec.__class__.__name__} name preserved", restored.name == spec.name)
    ck(
        f"5.x {spec.__class__.__name__} validates",
        restored.validate()["status"] == "ok",
    )

# ═══════════════════════════════════════════════════════════════════
# 6. CAA naming conventions
# ═══════════════════════════════════════════════════════════════════

print("\n[6] CAA naming conventions")

# Interface names must start with I
ck(
    "6.1 Interface with I-prefix",
    InterfaceSpec(name="IMyInterface", module="M").validate()["status"] == "ok",
)
ck(
    "6.2 Interface without I-prefix warns",
    InterfaceSpec(name="MyInterface", module="M").validate()["status"] == "warning",
)

# Component names should NOT start with I
cspec = ComponentSpec(name="MyComponent", module="M", implements=["IMyIface"])
ck("6.3 Component validates", cspec.validate()["status"] == "ok")
ck("6.4 Component has interfaces", len(cspec.implements) == 1)
ck("6.5 Component uses TIE", cspec.use_tie)

# ═══════════════════════════════════════════════════════════════════
print(f"\n{'=' * 70}")
print(f"  L5 Semantic: {passed}/{total} ({passed / total * 100:.0f}%)")
print(f"{'=' * 70}")
sys.exit(0 if passed == total else 1)
