#!/usr/bin/env python3
"""Refactor Tests"""

import shutil
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from meta_model import (
    Command,
    Component,
    DependencyGraph,
    Framework,
    Interface,
    Module,
    RelationType,
    Workbench,
    WorkspaceSnapshot,
)
from refactor import (
    move_command,
    rename_command,
    rename_interface,
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
print("  Refactor Tests")
print("=" * 60)

# Build mock workspace
ws = Path(tempfile.mkdtemp(prefix="caa_refactor_"))
fw_dir = ws / "TestFW.edu"
mod_dir = fw_dir / "TestMod.m"
mod2_dir = fw_dir / "OtherMod.m"

for d in [fw_dir, mod_dir, mod2_dir]:
    d.mkdir(parents=True)
    (d / "src").mkdir(parents=True, exist_ok=True)
    (d / "LocalInterfaces").mkdir(parents=True, exist_ok=True)

# Create files
(mod_dir / "Imakefile.mk").write_text(
    "SOURCES = \\\n    src/OldCmd.cpp \\\n    src/OldCmdHeader.cpp\n"
)
(mod_dir / "src" / "OldCmd.cpp").write_text("// OldCmd implementation")
(mod_dir / "src" / "OldCmdHeader.cpp").write_text("// OldCmdHeader")
(mod_dir / "LocalInterfaces" / "OldCmd.h").write_text("// OldCmd header")

(mod2_dir / "Imakefile.mk").write_text("SOURCES = \\\n")

fw = Framework(name="TestFW.edu", path=fw_dir)
mod = Module(name="TestMod.m", path=mod_dir)
mod2 = Module(name="OtherMod.m", path=mod2_dir)
mod.framework = fw
mod2.framework = fw
fw.modules = [mod, mod2]

cmd = Command(name="OldCmd", path=mod_dir / "src" / "OldCmd.cpp")
cmd.module = mod
cmd.is_stateful = True
mod.commands.append(cmd)

snapshot = WorkspaceSnapshot(root=ws, frameworks=[fw])

# ═══════════════════════════════════════════════════════════════════
print("\n[1] rename_command")
r = rename_command(snapshot, "TestMod.m", "OldCmd", "NewCmd")
ck("1.1 status", r["status"] == "pending")
ck("1.2 has changeset", "changeset" in r)
ck("1.3 has preview", "preview" in r)
ck("1.4 has impact", "impact" in r, str(r.get("impact", {}).keys())[:60])

# Error: same name
r2 = rename_command(snapshot, "TestMod.m", "NewCmd", "NewCmd")
ck("1.5 reject same name rename", r2["status"] == "error", r2.get("message", ""))

# Error: nonexistent command
r3 = rename_command(snapshot, "TestMod.m", "NoSuchCmd", "X")
ck("1.6 reject nonexistent", r3["status"] == "error")

# ═══════════════════════════════════════════════════════════════════
print("\n[2] rename_interface")
# Add interface to module
iface = Interface(
    name="IOldInterface", path=mod_dir / "PublicInterfaces" / "IOldInterface.h"
)
iface.module = mod
mod.interfaces.append(iface)

r = rename_interface(snapshot, "TestMod.m", "IOldInterface", "INewInterface")
ck("2.1 status", r["status"] == "pending")
ck("2.2 impact shows 0 components", isinstance(r.get("impact", {}), dict))

# ═══════════════════════════════════════════════════════════════════
print("\n[3] move_command")
r = move_command(snapshot, "TestMod.m", "OtherMod.m", "OldCmd")
ck("3.1 status", r["status"] == "pending")
ck("3.2 has changeset", "changeset" in r)

# Error: same module
r2 = move_command(snapshot, "TestMod.m", "TestMod.m", "OldCmd")
ck("3.3 reject same module move", r2["status"] == "error", r2.get("message", ""))

shutil.rmtree(ws, ignore_errors=True)

print(f"\n{'=' * 60}")
print(f"  Refactor: {passed}/{total} ({passed / total * 100:.0f}%)")
print(f"{'=' * 60}")
