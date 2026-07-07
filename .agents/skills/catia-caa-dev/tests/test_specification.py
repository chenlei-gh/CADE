#!/usr/bin/env python3
"""P1: Specification Layer Tests"""

import sys
from pathlib import Path

skill_root = Path(__file__).parent.parent
sys.path.insert(0, str(skill_root / "skills"))

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
    spec_from_dict,
)

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(
        f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else "")
    )


print("=" * 60)
print("  P1: Specification Layer Tests")
print("=" * 60)

# ── CommandSpec ──
print("\n[CommandSpec]")
cs = CommandSpec(
    name="MyCmd",
    module="TestMod.m",
    framework="TestFW",
    stateful=True,
    tooltip="My Command",
    dialog=DialogSpec(name="MyCmdDlg"),
    workbench="MyWB",
)
ck("create", cs.name == "MyCmd")
ck("validate", cs.validate()["status"] == "ok")
ck("to_dict type", cs.to_dict()["type"] == "CommandSpec")
ck("has dialog", cs.dialog.name == "MyCmdDlg")
ck("has workbench", cs.workbench == "MyWB")
ck("nested validate", cs.dialog.validate()["status"] == "ok")

# invalid command
cs2 = CommandSpec(name="", module="", framework="")
r = cs2.validate()
ck("invalid validate", r["status"] == "error", r.get("message", ""))

# invalid dialog in command
cs3 = CommandSpec(name="X", module="M", dialog=DialogSpec(name="", layout="bad"))
r = cs3.validate()
ck("invalid dialog detect", r["status"] != "ok", r.get("message", ""))

# ── DialogSpec ──
print("\n[DialogSpec]")
ds = DialogSpec(
    name="MyDlg", layout="grid", controls=[{"type": "Editor", "name": "val"}]
)
ck("create", ds.name == "MyDlg")
ck("validate", ds.validate()["status"] == "ok")
ck("controls", len(ds.controls) == 1)

ds2 = DialogSpec(name="Bad", layout="invalid")
ck("invalid layout detect", ds2.validate()["status"] == "error")

ds3 = DialogSpec(name="Bad2", controls=[{"no_type": "x"}])
ck("missing type detect", ds3.validate()["status"] == "error")

# ── InterfaceSpec ──
print("\n[InterfaceSpec]")
ispec = InterfaceSpec(
    name="IMyInterface",
    module="M.m",
    methods=[
        MethodSpec(name="DoSomething", params=["x"], return_type="HRESULT"),
        MethodSpec(name="GetData", return_type="CATUnicodeString"),
    ],
    use_idl=True,
)
ck("create", ispec.name == "IMyInterface")
ck("validate", ispec.validate()["status"] == "ok")
ck("method_names", ispec.method_names == ["DoSomething", "GetData"])
ck("to_dict methods", len(ispec.to_dict()["methods"]) == 2)

ispec2 = InterfaceSpec(name="BadName", module="M.m")  # no I prefix
r = ispec2.validate()
ck("no I-prefix warning", r["status"] == "warning", r.get("message", ""))

# ── ComponentSpec ──
print("\n[ComponentSpec]")
cps = ComponentSpec(
    name="MyComp",
    module="M.m",
    implements=["IMyInterface1", "IMyInterface2"],
    use_tie=True,
    generate_skeleton=True,
)
ck("create", cps.name == "MyComp")
ck("validate", cps.validate()["status"] == "ok")
ck("implements", cps.implements == ["IMyInterface1", "IMyInterface2"])

# ── FeatureSpec ──
print("\n[FeatureSpec]")
fs = FeatureSpec(
    name="MyFeature",
    module="M.m",
    attributes=[
        AttributeSpec(name="Length", type="CATLength", default="10mm"),
        AttributeSpec(name="Angle", type="CATAngle", default="90deg"),
    ],
    with_factory=True,
    with_catalog=True,
)
ck("create", fs.name == "MyFeature")
ck("validate", fs.validate()["status"] == "ok")
ck("attribute_names", fs.attribute_names == ["Length", "Angle"])
ck("factory", fs.with_factory == True)

# ── ExtensionSpec ──
print("\n[ExtensionSpec]")
es = ExtensionSpec(
    name="MyExt",
    module="M.m",
    target_object="CATPart",
    data_members=[
        DataMemberSpec(name="_length", type="double"),
        DataMemberSpec(name="_name", type="CATUnicodeString"),
    ],
    implements=["CATIMyExt"],
)
ck("create", es.name == "MyExt")
ck("validate", es.validate()["status"] == "ok")
ck("target", es.target_object == "CATPart")

es2 = ExtensionSpec(name="MyExt", module="M.m", target_object="")
r = es2.validate()
ck("no target detect", r["status"] == "error")

# ── WorkbenchSpec ──
print("\n[WorkbenchSpec]")
ws = WorkbenchSpec(name="MyWB", module="M.m", framework="FW", commands=["Cmd1", "Cmd2"])
ck("create", ws.name == "MyWB")
ck("validate", ws.validate()["status"] == "ok")

# ── spec_from_dict round-trip ──
print("\n[Round-trip]")
original = CommandSpec(
    name="RoundTrip",
    module="M.m",
    framework="FW",
    stateful=True,
    dialog=DialogSpec(name="RTDlg"),
)
d = original.to_dict()
restored = spec_from_dict(d)
ck("from_dict type", isinstance(restored, CommandSpec))
ck("from_dict name", restored.name == "RoundTrip")
ck("from_dict dialog", restored.dialog.name == "RTDlg")
ck("from_dict module", restored.module == "M.m")

# ── Multiple spec types round-trip ──
for spec in [
    DialogSpec(name="D", layout="grid"),
    InterfaceSpec(name="II", module="MM", methods=[MethodSpec(name="Run")]),
    FeatureSpec(name="FF", module="MM", attributes=[AttributeSpec(name="A")]),
    ExtensionSpec(name="EE", module="MM", target_object="CATPart"),
    ComponentSpec(name="CC", module="MM", implements=["II"]),
    WorkbenchSpec(name="WW", module="MM", commands=["A", "B"]),
]:
    d2 = spec.to_dict()
    r2 = spec_from_dict(d2)
    ck(f"round-trip {spec.__class__.__name__}", r2.name == spec.name)

print(f"\n{'=' * 60}")
print(f"  Specification: {passed}/{total} ({passed / total * 100:.0f}%)")
print(f"{'=' * 60}")
sys.exit(0 if passed == total else 1)
