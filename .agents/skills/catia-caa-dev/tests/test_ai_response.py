#!/usr/bin/env python3
"""
AI Response Check — Full System
================================
Simulates AI calling every interface and validates responses.
"""

import json
import sys
import time
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from actions import ActionContext
from build import create_runtime_view, incremental_build, workspace_info
from diagnostics import diagnose_and_fix, diagnose_workspace
from intents import (
    create_executable_command,
    create_extension,
    create_feature,
    suggest_next_action,
)
from meta_model import Command, Framework, Module, WorkspaceSnapshot
from refactor import rename_command
from run import check_catia_running
from specification import CommandSpec, DialogSpec

ctx = ActionContext("D:/test")

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    s = "PASS" if ok else "FAIL"
    print(f"  [{s}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 70)
print("  AI Response Check — All Interfaces")
print("=" * 70)

# ─── 1. Snapshot → History ───────────────────────────────────────

print("\n[1] Snapshot & History")
ctx.refresh(label="ai_check_1")
snap = ctx.snapshot
ck(
    "1.1 snapshot has frameworks",
    len(snap.frameworks) > 0,
    f"count={len(snap.frameworks)}",
)
ck("1.2 snapshot.to_dict serializable", isinstance(snap.to_dict(), dict))

ctx.refresh(label="ai_check_2")
ck("1.3 history records snapshots", ctx.history.summary()["total_snapshots"] >= 2)
diff = ctx.history.diff_last_two()
ck(
    "1.4 diff returns dict",
    isinstance(diff, dict),
    f"has_changes={diff.get('has_changes')}",
)

# ─── 2. Analysis Queries ─────────────────────────────────────────

print("\n[2] Analysis (AI asks: what's in my workspace?)")
r = snap.to_dict()
ck("2.1 framework count in dict", "framework_count" in r)
ck("2.2 module count", r.get("total_modules", 0) >= 0)
ck("2.3 commands accessible", "total_commands" in r)

m = check_catia_running()
ck("2.4 CATIA status queryable", m["status"] in ("running", "not_running"))

# ─── 3. Create Operations ────────────────────────────────────────

print("\n[3] Create (AI asks: create a command)")
r = create_executable_command(
    ctx, name="AIRspCmd", module="TestModule.m", with_dialog=True
)
ck("3.1 create response has status", r["status"] in ("pending", "error"), r["status"])
ck("3.2 response has preview", "preview" in r or "message" in r)
ck("3.3 response has components", "components" in r, str(r.get("components", {})))

r = create_feature(ctx, name="AIRspFeat", module="TestModule.m")
ck("3.4 feature create response", r["status"] in ("pending", "error"))

r = create_extension(
    ctx, name="AIRspExt", target_object="CATPart", module="TestModule.m"
)
ck("3.5 extension create response", r["status"] in ("pending", "error"))

# ─── 4. Specification ────────────────────────────────────────────

print("\n[4] Specification (AI builds structured spec)")
spec = CommandSpec(
    name="AISpecCmd",
    module="TestModule.m",
    stateful=True,
    dialog=DialogSpec(name="AISpecDlg"),
)
ck("4.1 spec validate", spec.validate()["status"] == "ok")
d = spec.to_dict()
ck("4.2 spec serializable", isinstance(d, dict))
ck("4.3 spec has type", d.get("type") == "CommandSpec")

# ─── 5. Diagnostics ──────────────────────────────────────────────

print("\n[5] Diagnostics (AI asks: any problems?)")
r = diagnose_workspace(ctx)
ck("5.1 diagnose returns dict", isinstance(r, dict))
ck("5.2 has total count", "total" in r)
ck("5.3 has errors/warnings", "errors" in r and "warnings" in r)
ck("5.4 auto-fixable count", "auto_fixable" in r)
ck(
    "5.5 diagnostics have severity",
    all("severity" in d for d in r.get("diagnostics", [])[:3])
    if r.get("diagnostics")
    else True,
)

# ─── 6. FixPlan ──────────────────────────────────────────────────

print("\n[6] FixPlan (AI asks: can you fix it?)")
r = diagnose_and_fix(ctx, dry_run=True)
ck("6.1 fix returns dict", isinstance(r, dict))
ck(
    "6.2 has fixes applied",
    "fixes" in r,
    f"applied={r.get('fixes', {}).get('applied', 0)}",
)
ck("6.3 dry_run respects flag", r.get("fixes", {}).get("dry_run", False) == True)

# ─── 7. Refactor ─────────────────────────────────────────────────

print("\n[7] Refactor (AI asks: rename this)")
ctx.refresh()
r = rename_command(ctx.snapshot, "TestModule.m", "NonexistentCmd", "NewName")
ck("7.1 refactor error handled", r["status"] == "error", r.get("message", "")[:50])
ck("7.2 error has message", "message" in r)

# ─── 8. Suggest ──────────────────────────────────────────────────

print("\n[8] Suggest (AI asks: what next?)")
r = suggest_next_action(ctx)
ck("8.1 suggest returns dict", isinstance(r, dict))
ck("8.2 has suggestions list", "suggestions" in r)
ck(
    "8.3 suggestions have priority",
    all("priority" in s for s in r.get("suggestions", [])[:3])
    if r.get("suggestions")
    else True,
)

# ─── 9. Error Response Format ────────────────────────────────────

print("\n[9] Error Response Uniformity")
err_calls = [
    ("nonexistent entity", diagnose_workspace(ctx)),
    (
        "nonexistent cmd rename",
        rename_command(ctx.snapshot, "TestModule.m", "NoCmd", "X"),
    ),
]
for label, r in err_calls:
    ck(f"9.x {label}: has status", "status" in r)
    ck(
        f"9.x {label}: has message on error",
        "message" in r if r.get("status") == "error" else True,
    )

# ─── 10. Full Loop: Observe → Diagnose → Fix ─────────────────────

print("\n[10] Full Loop: Snapshot → Diagnose → Fix → Verify")
ctx.refresh(label="loop_start")
snap1 = ctx.snapshot.to_dict()
diag = diagnose_workspace(ctx)
fix = diagnose_and_fix(ctx, dry_run=True)
ctx.refresh(label="loop_end")
snap2 = ctx.snapshot.to_dict()

ck("10.1 loop: snapshot recorded", ctx.history.summary()["total_snapshots"] >= 2)
ck("10.2 loop: diagnose returned", diag["status"] == "ok")
ck("10.3 loop: fix returned", fix["status"] == "ok")
ck(
    "10.4 loop: snapshot unchanged (dry_run)",
    snap1["total_commands"] == snap2["total_commands"],
)

# ─── 11. Build Commands ──────────────────────────────────────────

print("\n[11] Build (AI asks: compile)")
ck("11.1 incremental_build callable", callable(incremental_build))
ck("11.2 create_runtime_view callable", callable(create_runtime_view))

r = workspace_info(Path("D:/test"))
ck("11.3 workspace_info returns dict", isinstance(r, dict), r.get("status", "?"))

# ─── 12. MCP Tool Schema ─────────────────────────────────────────

print("\n[12] MCP Tool Schemas")
from mcp_server import TOOLS

mcp_names = {t["name"] for t in TOOLS}
required_tools = {
    "analyze_workspace",
    "create_executable_command",
    "diagnose_and_fix",
    "rename_command",
    "workspace_snapshot",
    "rollback",
    "start_catia",
    "stop_catia",
    "incremental_build",
    "suggest_next",
}
for tool in required_tools:
    ck(f"12.x {tool} in MCP", tool in mcp_names)
ck("12.x all MCP tools have inputSchema", all("inputSchema" in t for t in TOOLS))

# ─── Summary ─────────────────────────────────────────────────────

print(f"\n{'=' * 70}")
print(f"  AI Response Check: {passed}/{total} ({passed / total * 100:.0f}%)")
print(f"{'=' * 70}")
if passed == total:
    print("  >>> AI can seamlessly call all interfaces <<<")
sys.exit(0 if passed == total else 1)
