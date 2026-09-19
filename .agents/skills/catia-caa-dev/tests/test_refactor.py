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
from changeset import ChangeSet
from actions import ActionContext
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

# ChangeSet hygiene: created has new, deleted has old, modified does NOT have old
cs_dict = r["changeset"]
old_cpp_path = str(mod_dir / "src" / "OldCmd.cpp")
new_cpp_path = str(mod_dir / "src" / "NewCmd.cpp")
ck(
    "1.4.1 changeset hygiene (created has new)",
    new_cpp_path in cs_dict.get("created", {}),
)
ck(
    "1.4.2 changeset hygiene (deleted has old)",
    old_cpp_path in cs_dict.get("deleted", []),
)
ck(
    "1.4.3 changeset hygiene (modified does not contain old)",
    old_cpp_path not in cs_dict.get("modified", {}),
)
ck(
    "1.4.4 new file content replaced old_name",
    "// NewCmd implementation" in cs_dict.get("created", {}).get(new_cpp_path, ""),
)

# Apply changeset and verify disk consistency
applied_cs = ChangeSet.from_dict(cs_dict)
applied_cs.apply()
ck("1.4.5 applied: old file deleted on disk", not Path(old_cpp_path).exists())
ck("1.4.6 applied: new file exists on disk", Path(new_cpp_path).exists())
ck(
    "1.4.7 applied: new file has expected content",
    "// NewCmd implementation"
    in Path(new_cpp_path).read_text(encoding="utf-8", errors="replace"),
)

# Rollback changeset and verify complete reversibility
rb_res = applied_cs.rollback()
ck("1.4.8 rollback: status ok", rb_res.get("status") == "rolled_back", str(rb_res.get("errors", [])))
ck("1.4.9 rollback: old file restored on disk", Path(old_cpp_path).exists())
ck(
    "1.4.10 rollback: old file content restored",
    "// OldCmd implementation"
    in Path(old_cpp_path).read_text(encoding="utf-8", errors="replace"),
)
ck("1.4.11 rollback: new file cleaned up", not Path(new_cpp_path).exists())

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


def test_refactor_move_outside_source_module_rejected():
    """Verify move_command rejects files located outside source module."""
    outside_file = ws / "OutsideCmd.cpp"
    outside_file.write_text("// Outside command")
    outside_cmd = Command(name="OutsideCmd", path=outside_file, header=outside_file)
    outside_cmd.module = mod
    mod.commands.append(outside_cmd)
    try:
        res = move_command(snapshot, "TestMod.m", "OtherMod.m", "OutsideCmd")
        ok = (
            res["status"] == "error"
            and "outside source module" in res.get("message", "")
        )
        ck("3.4 test_refactor_move_outside_source_module_rejected", ok, res.get("message", ""))
    finally:
        mod.commands.remove(outside_cmd)
        if outside_file.exists():
            outside_file.unlink()


test_refactor_move_outside_source_module_rejected()

# ═══════════════════════════════════════════════════════════════════
print("\n[4] .dico token-aware replacement")


def test_dico_token_aware_replacement():
    """Verify dictionary entries are updated precisely without substring corruption."""
    dico_dir = fw_dir / "CNext" / "code" / "dictionary"
    dico_dir.mkdir(parents=True, exist_ok=True)
    dico_file = dico_dir / "TestFW.dico"
    original_dico = (
        "# Comment referencing OldCmd should remain untouched\n"
        "OtherOldCmd  CATIAfrGeneralWksAddin  libTestMod\n"
        "OldCmd  CATIAfrGeneralWksAddin  libTestMod\n"
        "OldCmdAddin  CATIAfrGeneralWksAddin  libTestMod\n"
        "OldCmdSuffix  CATIAfrGeneralWksAddin  libTestMod\n"
    )
    dico_file.write_text(original_dico, encoding="utf-8")

    res = rename_command(snapshot, "TestMod.m", "OldCmd", "NewCmd")
    ck("4.1 rename_command pending with dico", res["status"] == "pending")

    cs = res["changeset"]
    new_dico = cs.get("modified", {}).get(str(dico_file), "")

    ck(
        "4.2 comment untouched",
        "# Comment referencing OldCmd should remain untouched\n" in new_dico,
    )
    ck(
        "4.3 prefix token untouched",
        "OtherOldCmd  CATIAfrGeneralWksAddin  libTestMod\n" in new_dico,
    )
    ck(
        "4.4 suffix token untouched",
        "OldCmdSuffix  CATIAfrGeneralWksAddin  libTestMod\n" in new_dico,
    )
    ck(
        "4.5 exact token replaced",
        "NewCmd  CATIAfrGeneralWksAddin  libTestMod\n" in new_dico,
    )
    ck(
        "4.6 addin token replaced",
        "NewCmdAddin  CATIAfrGeneralWksAddin  libTestMod\n" in new_dico,
    )


test_dico_token_aware_replacement()

# ═══════════════════════════════════════════════════════════════════
print("\n[5] snapshot cache invalidation on file deletion")


def test_snapshot_invalidation_on_deletion():
    """Verify snapshot signature (file_count, max_mtime) invalidates cache on file deletion."""
    test_ws = Path(tempfile.mkdtemp(prefix="caa_snap_test_"))
    try:
        ctx = ActionContext(str(test_ws))
        file_a = test_ws / "FileA.txt"
        file_b = test_ws / "FileB.txt"
        file_a.write_text("aaa")
        file_b.write_text("bbb")

        # First snapshot access establishes baseline
        snap1 = ctx.snapshot
        count1, mtime1 = ctx._snapshot_file_count, ctx._snapshot_mtime
        ck("5.1 initial snapshot established", snap1 is not None and count1 >= 2)

        # Cache hit check within TTL
        snap1_cached = ctx.snapshot
        ck("5.2 cache hit when unchanged", snap1_cached is snap1)

        # Delete a file
        file_b.unlink()

        # Bypass TTL throttle
        ctx._last_check = 0

        # Snapshot must invalidate and rebuild
        snap2 = ctx.snapshot
        count2, mtime2 = ctx._snapshot_file_count, ctx._snapshot_mtime
        ck("5.3 cache invalidated on deletion", snap2 is not snap1)
        ck("5.4 file count decreased", count2 == count1 - 1)
    finally:
        shutil.rmtree(test_ws, ignore_errors=True)


test_snapshot_invalidation_on_deletion()

shutil.rmtree(ws, ignore_errors=True)

print(f"\n{'=' * 60}")
print(f"  Refactor: {passed}/{total} ({passed / total * 100:.0f}%)")
print(f"{'=' * 60}")

if passed < total:
    sys.exit(1)
