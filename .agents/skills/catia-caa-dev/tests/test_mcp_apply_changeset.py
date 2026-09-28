#!/usr/bin/env python3
"""P1: MCP develop(changeset=) applies that object, and nothing else.

Does not enter Kernel.execute. Does not re-generate. Uses a temp workspace
and deletes it. Does not touch a production workspace.
"""

import shutil
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

import mcp_server
from changeset import ChangeSet
from kernel import Kernel

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))


def main():
    ws = Path(tempfile.mkdtemp(prefix="cade_p1_apply_"))
    target = ws / "Authorized.txt"
    try:
        cs = ChangeSet(action="p1_apply", description="apply this object only")
        cs.add_create(target, "authorized-body\n")
        payload = cs.to_dict()

        both = mcp_server.handle_tool(
            "develop",
            {"workspace": str(ws), "request": "create command X", "changeset": payload},
        )
        check("request + changeset rejected", both.get("status") == "error")
        check("request + changeset writes nothing", not target.exists())

        missing = mcp_server.handle_tool("develop", {"workspace": str(ws)})
        check("neither request nor changeset rejected", missing.get("status") == "error")
        check("empty develop writes nothing", not target.exists())

        analyze = mcp_server.handle_tool(
            "analyze", {"workspace": str(ws), "request": "list modules", "changeset": payload}
        )
        check("analyze rejects changeset", analyze.get("status") == "error" and analyze.get("operation") == "apply")
        repair = mcp_server.handle_tool(
            "repair", {"workspace": str(ws), "request": "fix", "changeset": payload}
        )
        check("repair rejects changeset", repair.get("status") == "error" and repair.get("operation") == "apply")
        check("rejected tools write nothing", not target.exists())

        calls = {"execute": 0, "apply": 0}
        real_execute = Kernel.execute
        real_apply = Kernel._apply_changeset_dict

        def spy_execute(self, *args, **kwargs):
            calls["execute"] += 1
            return real_execute(self, *args, **kwargs)

        def spy_apply(self, changeset_dict):
            calls["apply"] += 1
            return real_apply(self, changeset_dict)

        Kernel.execute = spy_execute
        Kernel._apply_changeset_dict = spy_apply
        try:
            applied = mcp_server.handle_tool(
                "develop", {"workspace": str(ws), "changeset": payload}
            )
        finally:
            Kernel.execute = real_execute
            Kernel._apply_changeset_dict = real_apply

        check("changeset path does not call Kernel.execute", calls["execute"] == 0, str(calls))
        check("changeset path calls _apply_changeset_dict once", calls["apply"] == 1, str(calls))
        check("changeset-only status is ok", applied.get("status") == "ok", str(applied.get("status")))
        check("operation is apply", applied.get("operation") == "apply", str(applied.get("operation")))
        check("apply_status is applied", applied.get("apply_status") == "applied")
        check("rollback_id preserved", bool(applied.get("rollback_id")), str(applied.get("rollback_id")))
        check("body matches authorized object", target.read_text(encoding="utf-8") == "authorized-body\n")
        check("success response does not echo full changeset", "created" not in applied)

        again = mcp_server.handle_tool(
            "develop", {"workspace": str(ws), "changeset": payload}
        )
        check("second apply is not a one-shot grant", again.get("status") == "error")
        check("second apply still reports operation=apply", again.get("operation") == "apply")
        check("failed apply keeps original body", target.read_text(encoding="utf-8") == "authorized-body\n")
    finally:
        shutil.rmtree(ws, ignore_errors=True)

    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
