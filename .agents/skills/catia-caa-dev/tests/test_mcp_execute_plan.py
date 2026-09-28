#!/usr/bin/env python3
"""P4: MCP develop(execute_plan=) external execution authorization tests.

Verifies:
  1. Tri-mutual exclusion (request XOR changeset XOR execute_plan).
  2. Preview mode zero subprocess spawn (build/run/repair).
  3. command_preview demotion (immune to malicious command string injection).
  4. plan_digest tampering detection and rejection.
  5. Dynamic lock revalidation (TOCTOU: running CATIA blocks authorized build).
  6. IdentityCard executed strictly on-demand during authorized build, never in preview.
  7. Direct dispatch bypasses Kernel.execute (call count == 0).
  8. End-to-end authorized execution lifecycle and response contract.
  9. Action whitelist enforcement (unauthorized actions fail-closed).
  10. OWASP argument/command injection defense (disallowed options, skip_gate=True rejected).
  11. Macro script drift detection against file preconditions.
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

import mcp_server
from kernel import Kernel, compute_plan_digest

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))


def main():
    ws = Path(tempfile.mkdtemp(prefix="cade_p4_test_"))
    try:
        # ── Test 1: Tri-mutual exclusion ─────────────────────────────────
        plan_sample = {
            "type": "execution_plan",
            "version": 1,
            "action": "build",
            "workspace_root": str(ws),
            "parameters": {"options": "-u -a", "target_module": None, "skip_gate": False},
            "command_preview": "mkmk -u -a",
            "preflight": {},
            "planned_steps": ["mkmk"],
            "file_preconditions": {},
        }
        plan_sample["plan_digest"] = compute_plan_digest(plan_sample)

        res = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "request": "build workspace",
            "execute_plan": plan_sample,
        })
        check("Test 1a: request + execute_plan rejected", res.get("status") == "error")

        res = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "changeset": {"action": "test"},
            "execute_plan": plan_sample,
        })
        check("Test 1b: changeset + execute_plan rejected", res.get("status") == "error")

        res = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "request": "build workspace",
            "changeset": {"action": "test"},
            "execute_plan": plan_sample,
        })
        check("Test 1c: request + changeset + execute_plan rejected", res.get("status") == "error")

        res = mcp_server.handle_tool("develop", {"workspace": str(ws)})
        check("Test 1d: all empty rejected", res.get("status") == "error")

        res = mcp_server.handle_tool("analyze", {
            "workspace": str(ws),
            "request": "list modules",
            "execute_plan": plan_sample,
        })
        check("Test 1e: analyze rejects execute_plan", res.get("status") == "error" and res.get("operation") == "execute")

        res = mcp_server.handle_tool("repair", {
            "workspace": str(ws),
            "request": "fix",
            "execute_plan": plan_sample,
        })
        check("Test 1f: repair rejects execute_plan", res.get("status") == "error" and res.get("operation") == "execute")

        # ── Test 2: Preview Zero Subprocesses ──────────────────────────
        with mock.patch("subprocess.run") as mock_subproc, mock.patch("subprocess.Popen") as mock_popen:
            res_build = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "request": "build workspace",
                "preview": True,
            })
            check("Test 2a: build preview returns pending_execution", res_build.get("status") == "pending_execution")
            check("Test 2b: build preview has execute_plan", "execute_plan" in res_build)
            check("Test 2c: build preview zero subprocess.run", mock_subproc.call_count == 0)
            check("Test 2d: build preview zero subprocess.Popen", mock_popen.call_count == 0)

            res_catia = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "request": "start catia",
                "preview": True,
            })
            check("Test 2e: start catia preview returns pending_execution", res_catia.get("status") == "pending_execution")
            check("Test 2f: start catia preview zero subprocess", mock_subproc.call_count == 0 and mock_popen.call_count == 0)

            res_repair = mcp_server.handle_tool("repair", {
                "workspace": str(ws),
                "request": "fix errors",
            })
            check("Test 2g: repair in preview mode zero build subprocess", mock_subproc.call_count == 0)

        # ── Test 3: Command Preview Demotion ───────────────────────────
        # Client maliciously injects calc.exe into command_preview
        tampered_cmd_plan = dict(plan_sample)
        tampered_cmd_plan["command_preview"] = "cmd.exe /c calc.exe & malicious"
        # Digest only hashes canonical fields, so command_preview does not break digest
        tampered_cmd_plan["plan_digest"] = compute_plan_digest(tampered_cmd_plan)

        with mock.patch("build.build_workspace") as mock_bw:
            mock_bw.return_value = {"status": "ok", "message": "mocked build"}
            res = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": tampered_cmd_plan,
            })
            check("Test 3a: command_preview alteration accepted by digest", res.get("status") == "ok")
            check("Test 3b: build_workspace called with structured options", mock_bw.call_args[1].get("options") == "-u -a")
            check("Test 3c: malicious command_preview never executed", "calc" not in str(mock_bw.call_args))

        # ── Test 4: Plan Digest Tamper Rejection ───────────────────────
        tampered_param_plan = dict(plan_sample)
        tampered_param_plan["parameters"] = {"options": "-a", "target_module": "Injected.m", "skip_gate": False}
        # Keep old digest
        res = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "execute_plan": tampered_param_plan,
        })
        check("Test 4: parameter tampering rejected via digest mismatch", res.get("status") == "error")

        # ── Test 5: Dynamic Lock Revalidation (TOCTOU Defense) ────────
        with mock.patch("run.check_catia_running") as mock_catia:
            mock_catia.return_value = {"running": True, "processes": [{"pid": 1234}]}
            res = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": plan_sample,
            })
            check("Test 5: running CATIA dynamically blocks build execution", res.get("status") == "error")
            check("Test 5 detail: mentions DLL lock or CATIA running", "CATIA is running" in res.get("message", ""))

        # ── Test 6: IdentityCard On-Demand in Build Pipeline ───────────
        fw_dir = ws / "TestFW.edu"
        fw_dir.mkdir(parents=True, exist_ok=True)
        ic_dir = fw_dir / "IdentityCard"
        ic_dir.mkdir(parents=True, exist_ok=True)
        (ic_dir / "IdentityCard.h").write_text("// test IC", encoding="utf-8")

        with mock.patch("build.create_identity_card") as mock_mkic, mock.patch("build._exec_build_cmd") as mock_ebc:
            mock_mkic.return_value = {"status": "success"}
            mock_ebc.return_value = {"status": "success", "output": ""}
            # Preview must NOT trigger create_identity_card
            mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "request": "build workspace",
                "preview": True,
            })
            check("Test 6a: preview never auto-runs mkCreateIC", mock_mkic.call_count == 0)

            # Authorized execution of build triggers create_identity_card
            from build import _ensure_identity_cards_for_build
            _ensure_identity_cards_for_build(ws)
            check("Test 6b: build pipeline auto-runs mkCreateIC for missing IC binary", mock_mkic.call_count == 1)

        # ── Test 7: Direct Dispatch Bypasses Kernel.execute ────────────
        calls = {"execute": 0, "_execute_plan_dict": 0}
        orig_execute = Kernel.execute
        orig_plan_dict = Kernel._execute_plan_dict

        def spy_execute(self, *args, **kwargs):
            calls["execute"] += 1
            return orig_execute(self, *args, **kwargs)

        def spy_plan_dict(self, plan):
            calls["_execute_plan_dict"] += 1
            return {"status": "ok", "message": "spy executed"}

        Kernel.execute = spy_execute
        Kernel._execute_plan_dict = spy_plan_dict
        try:
            res = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": plan_sample,
            })
            check("Test 7a: Kernel.execute call count is 0", calls["execute"] == 0, str(calls))
            check("Test 7b: _execute_plan_dict called exactly once", calls["_execute_plan_dict"] == 1, str(calls))
            check("Test 7c: execution status is ok", res.get("status") == "ok")
            check("Test 7d: operation is execute", res.get("operation") == "execute")
        finally:
            Kernel.execute = orig_execute
            Kernel._execute_plan_dict = orig_plan_dict

        # ── Test 8: End-to-End Execution Contract ──────────────────────
        with mock.patch("build.build_workspace") as mock_bw:
            mock_bw.return_value = {"status": "ok", "message": "build succeeded"}
            res = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": plan_sample,
            })
            check("Test 8a: status is ok", res.get("status") == "ok")
            check("Test 8b: operation is execute", res.get("operation") == "execute")
            check("Test 8c: action matches plan", res.get("action") == "build")
            check("Test 8d: execution_status is ok", res.get("execution_status") == "ok")

        # ── Test 9: Action Whitelist Enforcement ───────────────────────
        tampered_action_plan = dict(plan_sample)
        tampered_action_plan["action"] = "format_drive"
        tampered_action_plan["plan_digest"] = compute_plan_digest(tampered_action_plan)

        res = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "execute_plan": tampered_action_plan,
        })
        check("Test 9: unauthorized action rejected", res.get("status") == "error")
        check("Test 9 detail: message mentions allowed actions", "not in allowed actions" in res.get("message", ""))

        # ── Test 10: OWASP Argument & Command Injection Defense ────────
        # 10a: Shell metacharacters in options
        inj_options_plan = dict(plan_sample)
        inj_options_plan["parameters"] = {"options": "-u -a & calc.exe", "skip_gate": False}
        inj_options_plan["plan_digest"] = compute_plan_digest(inj_options_plan)
        res = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "execute_plan": inj_options_plan,
        })
        check("Test 10a: shell metacharacter injection in options rejected", res.get("status") == "error")

        # 10b: skip_gate=True is strictly forbidden in authorized execution
        skip_gate_plan = dict(plan_sample)
        skip_gate_plan["parameters"] = {"options": "-u -a", "skip_gate": True}
        skip_gate_plan["plan_digest"] = compute_plan_digest(skip_gate_plan)
        res = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "execute_plan": skip_gate_plan,
        })
        check("Test 10b: skip_gate=True rejected in authorized execution", res.get("status") == "error")
        check("Test 10b detail: mentions skip_gate forbidden", "skip_gate=True is forbidden" in res.get("message", ""))

        # ── Test 11: Macro Script Drift Detection ──────────────────────
        macro_file = ws / "MyScript.CATScript"
        macro_file.write_text("' Original Macro Content\nMsgBox \"Hello\"", encoding="utf-8")
        orig_sha = hashlib.sha256(macro_file.read_bytes()).hexdigest()

        macro_plan = {
            "type": "execution_plan",
            "version": 1,
            "action": "macro",
            "workspace_root": str(ws),
            "parameters": {"macro_path": "MyScript.CATScript"},
            "command_preview": "run_catia_macro(MyScript.CATScript)",
            "preflight": {"macro_file_exists": True},
            "planned_steps": ["verify_macro_file", "execute_macro"],
            "file_preconditions": {
                "MyScript.CATScript": {"exists": True, "sha256": orig_sha}
            },
        }
        macro_plan["plan_digest"] = compute_plan_digest(macro_plan)

        with mock.patch("run.run_catia_macro") as mock_macro:
            mock_macro.return_value = {"status": "ok"}
            # Step 1: execution without drift succeeds
            res_macro_ok = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": macro_plan,
            })
            check("Test 11a: pristine macro executes successfully", res_macro_ok.get("status") == "ok")

            # Step 2: external actor modifies macro file (drift)
            macro_file.write_text("' Tampered Content\nMsgBox \"Pwned\"", encoding="utf-8")

            res_macro_drift = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": macro_plan,
            })
            check("Test 11b: drifted macro rejected before execution", res_macro_drift.get("status") == "error")
            check("Test 11c: error message specifies drift", "has drifted since preview" in res_macro_drift.get("message", ""))

    finally:
        shutil.rmtree(ws, ignore_errors=True)

    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
