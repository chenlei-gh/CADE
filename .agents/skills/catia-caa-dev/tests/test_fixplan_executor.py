#!/usr/bin/env python3
"""FixPlan Executor Tests"""

import shutil
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from actions import ActionContext
from diagnostics import (
    Diagnostic,
    DiagnosticsEngine,
    FixAction,
    FixPlan,
    Severity,
    apply_all_fixplans,
    apply_fixplan,
    diagnose_and_fix,
    diagnose_workspace,
)
from meta_model import Command, Framework, Module, WorkspaceSnapshot

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(
        f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else "")
    )


print("=" * 60)
print("  FixPlan Executor Tests")
print("=" * 60)

# Build mock workspace with known issues
ws = Path(tempfile.mkdtemp(prefix="caa_fix_"))
fw_dir = ws / "TestFW.edu"
mod_dir = fw_dir / "TestMod.m"
ic_dir = fw_dir / "IdentityCard"
dict_dir = fw_dir / "CNext" / "code" / "dictionary"
nls_dir = fw_dir / "CNext" / "resources" / "msgcatalog"

for d in [
    fw_dir,
    mod_dir,
    mod_dir / "src",
    mod_dir / "LocalInterfaces",
    ic_dir,
    dict_dir,
    nls_dir,
]:
    d.mkdir(parents=True, exist_ok=True)

# Write files
(ic_dir / "IdentityCard.h").write_text("// IdentityCard")
(dict_dir / "TestFW.dico").write_text("ExistingCmd  CATCommand  libTestMod\n")
(nls_dir / "TestFW.CATNls").write_text('ExistingCmd.Title = "Test";\n')
(mod_dir / "Imakefile.mk").write_text("SOURCES = \\\n    src/ExistingCmd.cpp\n")
(mod_dir / "src" / "MissingCmd.cpp").write_text("// Missing from dict")
(mod_dir / "src" / "MissingCmdHeader.cpp").write_text("// Header")
(mod_dir / "LocalInterfaces" / "MissingCmd.h").write_text("// Header")

fw = Framework(name="TestFW.edu", path=fw_dir)
mod = Module(name="TestMod.m", path=mod_dir)
mod.framework = fw
fw.modules.append(mod)

cmd = Command(name="MissingCmd", path=mod_dir / "src" / "MissingCmd.cpp")
cmd.module = mod
cmd.is_stateful = True
mod.commands.append(cmd)

ctx = ActionContext(str(ws))

# ═══════════════════════════════════════════════════════════════════
print("\n[1] FixPlan: APPEND_LINE")

fp = FixPlan(
    action=FixAction.APPEND_LINE,
    file=str(dict_dir / "TestFW.dico"),
    line="MissingCmd  CATStateCommand  libTestMod",
    description="Register MissingCmd",
)
result = apply_fixplan(fp, ws)
ck("1.1 status ok", result["status"] == "ok")
ck("1.2 has changeset", "changeset" in result)
ck("1.3 action is append_line", result["action"] == "append_line")

# Apply and verify
from changeset import ChangeSet

cs = ChangeSet.from_dict(result["changeset"])
cs.apply(dry_run=False, workspace_root=ws)
content = (dict_dir / "TestFW.dico").read_text()
ck("1.4 line appended", "MissingCmd" in content, content.strip())

# ═══════════════════════════════════════════════════════════════════
print("\n[2] FixPlan: DELETE_LINE")

fp2 = FixPlan(
    action=FixAction.DELETE_LINE,
    file=str(dict_dir / "TestFW.dico"),
    delete_target="ExistingCmd",
    description="Remove stale entry",
)
r2 = apply_fixplan(fp2, ws)
cs2 = ChangeSet.from_dict(r2["changeset"])
cs2.apply(dry_run=False, workspace_root=ws)
content2 = (dict_dir / "TestFW.dico").read_text()
ck("2.1 line deleted", "ExistingCmd" not in content2, content2.strip())

# ═══════════════════════════════════════════════════════════════════
print("\n[3] FixPlan: CREATE_FILE + INSERT_LINE")

fp3 = FixPlan(
    action=FixAction.CREATE_FILE,
    file=str(ws / "NewFile.txt"),
    line="Hello World",
    description="Create test file",
)
r3 = apply_fixplan(fp3, ws)
cs3 = ChangeSet.from_dict(r3["changeset"])
cs3.apply(dry_run=False, workspace_root=ws)
newf = ws / "NewFile.txt"
ck("3.1 file created", newf.exists())
ck("3.2 content correct", newf.read_text() == "Hello World")

# INSERT_LINE
fp4 = FixPlan(
    action=FixAction.INSERT_LINE,
    file=str(ws / "NewFile.txt"),
    line="Inserted line",
    after_line="Hello World",
    description="Insert after Hello",
)
r4 = apply_fixplan(fp4, ws)
cs4 = ChangeSet.from_dict(r4["changeset"])
cs4.apply(dry_run=False, workspace_root=ws)
content4 = newf.read_text()
ck("3.3 line inserted", "Inserted line" in content4, content4.strip())

# ═══════════════════════════════════════════════════════════════════
print("\n[4] diagnose_and_fix — full cycle")

# Create a genuine auto-fixable diagnostic. Command dictionary entries and
# explicit SOURCES lists are not required by B28 and must not be used merely
# to make this executor test produce a ChangeSet.
(nls_dir / "TestFW.CATNls").unlink()
ctx.refresh()
result = diagnose_and_fix(ctx, auto_only=True, dry_run=True)
ck("4.1 status ok", result["status"] == "ok")
ck("4.2 has diagnostics", "diagnostics" in result)
ck("4.3 has fixes", "fixes" in result)
ck("4.4 dry_run mode", result["fixes"]["dry_run"] == True)
ck("4.5 changeset available", result["fixes"]["changeset_available"] == True)

# ═══════════════════════════════════════════════════════════════════
print("\n[5] apply_all_fixplans")

ctx.refresh()
r = apply_all_fixplans(ctx, auto_only=True)
ck("5.1 status ok", r["status"] == "ok")
ck(
    "5.2 has applied count",
    "applied" in r,
    f"applied={r.get('applied')}, skipped={r.get('skipped')}",
)
ck("5.3 has details", "details" in r)

# ═══════════════════════════════════════════════════════════════════
print("\n[6] Error handling")

# Invalid file path
fp_err = FixPlan(
    action=FixAction.APPEND_LINE,
    file="Z:/nonexistent/file.dico",
    line="test",
    description="Should fail",
)
r_err = apply_fixplan(fp_err, ws)
ck(
    "6.1 handles missing file",
    r_err["status"] == "error",
    r_err.get("message", "")[:60],
)

# Missing required field
fp_err2 = FixPlan(
    action=FixAction.INSERT_LINE,
    file=str(ws / "NewFile.txt"),
    line="x",
    description="Missing after_line",
)
r_err2 = apply_fixplan(fp_err2, ws)
ck("6.2 handles missing after_line", r_err2["status"] == "error")

shutil.rmtree(ws, ignore_errors=True)

print(f"\n{'=' * 60}")
print(f"  FixPlan Executor: {passed}/{total} ({passed / total * 100:.0f}%)")
print(f"{'=' * 60}")
sys.exit(0 if passed == total else 1)
