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
            # 5a: Real structure returned by check_catia_running()
            mock_catia.return_value = {"status": "running", "message": "Found 1 CATIA process(es)", "processes": [{"pid": 1234}]}
            res = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": plan_sample,
            })
            check("Test 5a: real status=running dynamically blocks build execution", res.get("status") == "error")
            check("Test 5a detail: mentions DLL lock or CATIA running", "CATIA is running" in res.get("message", ""))

            # 5b: Lock check exception fails-closed (no bypass on error)
            mock_catia.side_effect = RuntimeError("Process query failed")
            res_fail_closed = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": plan_sample,
            })
            check("Test 5b: lock check exception fails-closed", res_fail_closed.get("status") == "error")
            check("Test 5b detail: mentions unable to verify", "Unable to verify" in res_fail_closed.get("message", ""))

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

        # 10c: Non-whitelisted build options (arbitrary flags) rejected
        bad_options_plan = dict(plan_sample)
        bad_options_plan["parameters"] = {"options": "-foobar", "skip_gate": False}
        bad_options_plan["plan_digest"] = compute_plan_digest(bad_options_plan)
        res = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "execute_plan": bad_options_plan,
        })
        check("Test 10c: non-whitelisted options rejected by strict allowlist", res.get("status") == "error")
        check("Test 10c detail: mentions allowed build options", "not in allowed build options" in res.get("message", ""))

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

        # ── Test 12: Action Parity - setup_prerequisites ──────────────
        res_sp_prev = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "request": "setup prereq",
            "preview": True,
        })
        check("Test 12a: setup prereq preview status pending_execution", res_sp_prev.get("status") == "pending_execution")
        sp_plan = res_sp_prev.get("execute_plan", {})
        check("Test 12b: setup prereq preview action is setup_prerequisites", sp_plan.get("action") == "setup_prerequisites")

        with mock.patch("build.setup_prerequisite_path") as mock_spp, mock.patch("build.build_workspace") as mock_bw:
            mock_spp.return_value = {"status": "ok", "message": "prereq linked"}
            res_sp_exec = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": sp_plan,
            })
            check("Test 12c: setup prereq execution status ok", res_sp_exec.get("status") == "ok")
            check("Test 12d: setup_prerequisite_path called", mock_spp.call_count == 1)
            check("Test 12e: build_workspace NOT called", mock_bw.call_count == 0)

        # ── Test 13: Action Parity - runtime_view ─────────────────────
        res_rv_prev = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "request": "create runtime view",
            "preview": True,
        })
        check("Test 13a: runtime view preview status pending_execution", res_rv_prev.get("status") == "pending_execution")
        rv_plan = res_rv_prev.get("execute_plan", {})
        check("Test 13b: runtime view preview action is runtime_view", rv_plan.get("action") == "runtime_view")

        with mock.patch("build.create_runtime_view") as mock_crv, mock.patch("build.build_workspace") as mock_bw:
            mock_crv.return_value = {"status": "ok", "message": "runtime view created"}
            res_rv_exec = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": rv_plan,
            })
            check("Test 13c: runtime view execution status ok", res_rv_exec.get("status") == "ok")
            check("Test 13d: create_runtime_view called", mock_crv.call_count == 1)
            check("Test 13e: build_workspace NOT called", mock_bw.call_count == 0)

        # ── Test 14: Action Parity - dev (composite build + run) ──────
        res_dev_prev = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "request": "dev",
            "preview": True,
        })
        check("Test 14a: dev preview status pending_execution", res_dev_prev.get("status") == "pending_execution")
        dev_plan = res_dev_prev.get("execute_plan", {})
        check("Test 14b: dev preview action is dev", dev_plan.get("action") == "dev")

        with mock.patch("build.incremental_build") as mock_inc, mock.patch("run.start_catia_runtime") as mock_start, mock.patch("build.build_workspace") as mock_bw:
            mock_inc.return_value = {"status": "success", "message": "mkmk ok"}
            mock_start.return_value = {"status": "ok", "message": "cnext ok"}
            res_dev_exec = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": dev_plan,
            })
            check("Test 14c: dev execution status ok", res_dev_exec.get("status") == "ok")
            check("Test 14d: incremental_build called", mock_inc.call_count == 1)
            check("Test 14e: start_catia_runtime called on build success", mock_start.call_count == 1)
            check("Test 14f: build_workspace NOT called directly", mock_bw.call_count == 0)

            # Test short-circuit on build failure
            mock_inc.return_value = {"status": "error", "message": "compilation failed"}
            mock_start.reset_mock()
            res_dev_fail = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": dev_plan,
            })
            check("Test 14g: dev execution fails on build failure", res_dev_fail.get("status") == "error")
            check("Test 14h: start_catia_runtime not called on build failure", mock_start.call_count == 0)

            # Test 14i: dev rejects extra parameters even if digest matches
            tampered_dev_plan = dict(dev_plan)
            tampered_dev_plan["parameters"] = {"options": "-a"}
            tampered_dev_plan["plan_digest"] = compute_plan_digest(tampered_dev_plan)
            res_dev_extra = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": tampered_dev_plan,
            })
            check("Test 14i: dev rejects extra parameters fail-closed", res_dev_extra.get("status") == "error")
            check("Test 14i detail: mentions no extra parameters", "no extra parameters" in res_dev_extra.get("message", ""))

        # ── Test 15: Build Mode Preview Options Parity ────────────────
        clean_prev = mcp_server.handle_tool("develop", {"workspace": str(ws), "request": "clean build", "preview": True})
        check("Test 15a: clean build options is -a -u", clean_prev.get("execute_plan", {}).get("parameters", {}).get("options") == "-a -u")

        full_prev = mcp_server.handle_tool("develop", {"workspace": str(ws), "request": "full build", "preview": True})
        check("Test 15b: full build options is -a", full_prev.get("execute_plan", {}).get("parameters", {}).get("options") == "-a")

        debug_prev = mcp_server.handle_tool("develop", {"workspace": str(ws), "request": "debug build", "preview": True})
        check("Test 15c: debug build options is -a -g", debug_prev.get("execute_plan", {}).get("parameters", {}).get("options") == "-a -g")

        inc_prev = mcp_server.handle_tool("develop", {"workspace": str(ws), "request": "incremental build", "preview": True})
        check("Test 15d: incremental build options is -u -a", inc_prev.get("execute_plan", {}).get("parameters", {}).get("options") == "-u -a")

        # ── Test 16: Parameter Parity - start_catia ───────────────────
        catia_plan_custom = {
            "type": "execution_plan",
            "version": 1,
            "action": "start_catia",
            "workspace_root": str(ws),
            "parameters": {"env_name": "MyCustomEnv", "wait_for_exit": True},
            "command_preview": "start_catia_runtime",
            "preflight": {},
            "planned_steps": ["launch_cnext"],
            "file_preconditions": {},
        }
        catia_plan_custom["plan_digest"] = compute_plan_digest(catia_plan_custom)

        with mock.patch("run.start_catia_runtime") as mock_start_custom:
            mock_start_custom.return_value = {"status": "ok"}
            res_sc = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": catia_plan_custom,
            })
            check("Test 16a: start_catia executes successfully with custom params", res_sc.get("status") == "ok")
            check("Test 16b: env_name passed through to start_catia_runtime", mock_start_custom.call_args[1].get("env_name") == "MyCustomEnv")
            check("Test 16c: wait_for_exit passed through to start_catia_runtime", mock_start_custom.call_args[1].get("wait_for_exit") is True)

        # 16d: Invalid param type (wait_for_exit not bool) rejected
        catia_plan_bad = dict(catia_plan_custom)
        catia_plan_bad["parameters"] = {"env_name": None, "wait_for_exit": "not_a_bool"}
        catia_plan_bad["plan_digest"] = compute_plan_digest(catia_plan_bad)
        res_sc_bad = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "execute_plan": catia_plan_bad,
        })
        check("Test 16d: non-boolean wait_for_exit rejected", res_sc_bad.get("status") == "error")

        # ── Test 17: Parameter Parity - batch ─────────────────────────
        # 17a: default batch with batch_script=None
        batch_plan_none = {
            "type": "execution_plan",
            "version": 1,
            "action": "batch",
            "workspace_root": str(ws),
            "parameters": {"batch_script": None},
            "command_preview": "run_catia_batch",
            "preflight": {},
            "planned_steps": ["execute_batch"],
            "file_preconditions": {},
        }
        batch_plan_none["plan_digest"] = compute_plan_digest(batch_plan_none)

        with mock.patch("run.run_catia_batch") as mock_batch:
            mock_batch.return_value = {"status": "ok"}
            res_b_none = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": batch_plan_none,
            })
            check("Test 17a: batch with batch_script=None executes", res_b_none.get("status") == "ok")
            check("Test 17b: run_catia_batch received batch_script=None", mock_batch.call_args[1].get("batch_script") is None)

        # 17c: valid batch script inside workspace
        batch_file = ws / "test_job.bat"
        batch_file.write_text("@echo off\nexit /b 0", encoding="utf-8")
        batch_plan_valid = dict(batch_plan_none)
        batch_plan_valid["parameters"] = {"batch_script": "test_job.bat"}
        batch_plan_valid["plan_digest"] = compute_plan_digest(batch_plan_valid)

        with mock.patch("run.run_catia_batch") as mock_batch:
            mock_batch.return_value = {"status": "ok"}
            res_b_valid = mcp_server.handle_tool("develop", {
                "workspace": str(ws),
                "execute_plan": batch_plan_valid,
            })
            check("Test 17c: batch with valid script executes", res_b_valid.get("status") == "ok")
            check("Test 17d: run_catia_batch received batch_script path", mock_batch.call_args[1].get("batch_script") == "test_job.bat")

        # 17e: path traversal in batch_script rejected
        batch_plan_trav = dict(batch_plan_none)
        batch_plan_trav["parameters"] = {"batch_script": "../../outside.bat"}
        batch_plan_trav["plan_digest"] = compute_plan_digest(batch_plan_trav)
        res_b_trav = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "execute_plan": batch_plan_trav,
        })
        check("Test 17e: batch script path traversal rejected", res_b_trav.get("status") == "error")

        # 17f: non-existent script in batch_script rejected
        batch_plan_missing = dict(batch_plan_none)
        batch_plan_missing["parameters"] = {"batch_script": "missing_script.bat"}
        batch_plan_missing["plan_digest"] = compute_plan_digest(batch_plan_missing)
        res_b_missing = mcp_server.handle_tool("develop", {
            "workspace": str(ws),
            "execute_plan": batch_plan_missing,
        })
        check("Test 17f: non-existent batch script rejected", res_b_missing.get("status") == "error")

    finally:
        shutil.rmtree(ws, ignore_errors=True)

    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
