#!/usr/bin/env python3
"""
Test Suite for P5.4 Boundary Exposure / Result Propagation
===========================================================
Validates the P5.4 contract:

1. Kernel._execute_plan_dict() hoists the P5.3 runtime envelopes
   (execution/verification) to the top level for P5.3-enabled actions
   (start_catia, stop_catia).
2. Kernel maps execution.status -> outer status by ALLOWLIST: only
   "completed" is ok; "timeout" and "error" are NOT reported as ok.
3. Kernel does NOT invent envelopes for other actions, and the runtime_view
   action (create_runtime_view) stays a build action with no P5.3 envelope.
4. MCP _execute_authorized_plan() forwards P5.3 envelopes by explicit action
   gate + status-domain validation, so build.py's differently-shaped top-level
   "execution"/"verification" keys are never carried into the execute result.
5. token_optimizer.optimize() is NOT globally modified for execution/verification
   (two different contracts share the key names), but the MCP layer preserves the
   P5.3 envelopes through optimization.
6. Real chain (only the OS boundary mocked): MCP entry -> Kernel -> run ->
   optimizer preserves envelopes and execution.raw reaches the final output.
"""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

import mcp_server
from kernel import Kernel, compute_plan_digest
from mcp_server import _execute_authorized_plan
from token_optimizer import optimize


def _make_plan(action: str, workspace: Path, parameters: dict) -> dict:
    plan = {
        "type": "execution_plan",
        "version": 1,
        "action": action,
        "workspace_root": str(workspace),
        "parameters": parameters,
        "file_preconditions": {},
    }
    plan["plan_digest"] = compute_plan_digest(plan)
    return plan


class TestP54KernelExposure(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_kernel_start_catia_exposure(self):
        """Kernel hoists execution and verification from start_catia_runtime to top level."""
        kernel = Kernel(workspace_root=self.workspace)
        plan = _make_plan("start_catia", self.workspace, {"wait_for_exit": True})

        mock_runtime_res = {
            "status": "exited",
            "exit_code": 0,
            "message": "CATIA launcher exited with code 0",
            "execution": {
                "status": "completed",
                "action_result": "exited",
                "raw": {"status": "exited", "exit_code": 0},
            },
            "verification": {
                "status": "not_run",
                "check": "none",
                "evidence": {"reason": "launcher_exit_code_does_not_prove_cnext_lifecycle"},
            },
        }

        with patch("run.check_catia_running", return_value={"status": "not_running"}), \
             patch("run.start_catia_runtime", return_value=mock_runtime_res):
            res = kernel._execute_plan_dict(plan)

        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["message"], "CATIA launcher exited with code 0")
        self.assertIn("execution", res)
        self.assertEqual(res["execution"]["status"], "completed")
        self.assertEqual(res["execution"]["action_result"], "exited")
        self.assertIn("verification", res)
        self.assertEqual(res["verification"]["status"], "not_run")
        self.assertEqual(res["verification"]["check"], "none")
        # Legacy data compatibility
        self.assertIn("data", res)
        self.assertEqual(res["data"]["status"], "exited")
        self.assertEqual(res["data"]["exit_code"], 0)

    def test_kernel_start_catia_error_not_masked_as_ok(self):
        """Kernel does NOT mask execution.status == 'error' as status == 'ok'."""
        kernel = Kernel(workspace_root=self.workspace)
        plan = _make_plan("start_catia", self.workspace, {"wait_for_exit": True})

        mock_error_res = {
            "status": "error",
            "message": "Launch failed due to missing binary",
            "execution": {"status": "error", "action_result": "error", "raw": {"status": "error"}},
            "verification": {
                "status": "not_run",
                "check": "none",
                "evidence": {"reason": "unhandled_status_error"},
            },
        }

        with patch("run.check_catia_running", return_value={"status": "not_running"}), \
             patch("run.start_catia_runtime", return_value=mock_error_res):
            res = kernel._execute_plan_dict(plan)

        self.assertEqual(res["status"], "error")
        self.assertEqual(res["execution"]["status"], "error")
        self.assertEqual(res["verification"]["status"], "not_run")

    def test_kernel_start_catia_timeout_not_masked_as_ok(self):
        """P0-2 regression: execution.status == 'timeout' MUST NOT map to outer status 'ok'."""
        kernel = Kernel(workspace_root=self.workspace)
        plan = _make_plan("start_catia", self.workspace, {"wait_for_exit": True})

        mock_timeout_res = {
            "status": "timeout",
            "message": "CATIA launch timed out",
            "execution": {"status": "timeout", "action_result": "timeout", "raw": {"status": "timeout"}},
            "verification": {"status": "not_run", "check": "none", "evidence": {"reason": "timeout"}},
        }

        with patch("run.check_catia_running", return_value={"status": "not_running"}), \
             patch("run.start_catia_runtime", return_value=mock_timeout_res):
            res = kernel._execute_plan_dict(plan)

        self.assertNotEqual(res["status"], "ok")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["execution"]["status"], "timeout")

    def test_kernel_stop_catia_exposure(self):
        """Kernel hoists execution and verification from stop_catia to top level."""
        kernel = Kernel(workspace_root=self.workspace)
        plan = _make_plan("stop_catia", self.workspace, {"force": False})

        mock_stop_res = {
            "status": "not_running",
            "message": "CATIA is not running",
            "execution": {"status": "completed", "action_result": "not_running", "raw": {"status": "not_running"}},
            "verification": {
                "status": "observed",
                "check": "cnext_process_scan",
                "evidence": {
                    "target_image": "CNEXT.exe",
                    "match_found": False,
                    "instance_scope": "single_query_snapshot_only",
                },
            },
        }

        with patch("run.stop_catia", return_value=mock_stop_res):
            res = kernel._execute_plan_dict(plan)

        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["execution"]["status"], "completed")
        self.assertEqual(res["execution"]["action_result"], "not_running")
        self.assertEqual(res["verification"]["status"], "observed")
        self.assertEqual(res["verification"]["check"], "cnext_process_scan")
        self.assertEqual(res["data"]["status"], "not_running")

    def test_kernel_non_envelope_action_does_not_invent_envelopes(self):
        """Non-P5.3 actions keep the old protocol (no invented envelopes)."""
        kernel = Kernel(workspace_root=self.workspace)
        macro_file = self.workspace / "test.CATScript"
        macro_file.write_text("Language=\"VBSCRIPT\"\nSub CATMain()\nEnd Sub\n", encoding="utf-8")
        plan = _make_plan("macro", self.workspace, {"macro_path": "test.CATScript"})

        with patch("run.run_catia_macro", return_value={"status": "ok", "message": "Macro executed"}):
            res = kernel._execute_plan_dict(plan)

        self.assertEqual(res["status"], "ok")
        self.assertNotIn("execution", res)
        self.assertNotIn("verification", res)

    def test_kernel_runtime_view_is_build_action_without_p53_envelope(self):
        """P1-3: runtime_view is create_runtime_view (a build action), NOT check_runtime_view.

        create_runtime_view() emits no P5.3 envelope, so the Kernel branch must not
        hoist one. This locks the boundary so a dead hoist is not reintroduced.
        """
        kernel = Kernel(workspace_root=self.workspace)
        plan = _make_plan("runtime_view", self.workspace, {})

        with patch("build.create_runtime_view", return_value={"status": "ok", "message": "Runtime view created."}):
            res = kernel._execute_plan_dict(plan)

        self.assertEqual(res["status"], "ok")
        self.assertNotIn("execution", res)
        self.assertNotIn("verification", res)


class TestP54McpForwarding(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_mcp_forwards_start_catia_envelopes(self):
        plan = _make_plan("start_catia", self.workspace, {"wait_for_exit": False})
        mock_kernel_exec = {
            "status": "ok",
            "message": "CATIA started",
            "data": {"status": "started", "pid": 9999},
            "execution": {"status": "completed", "action_result": "started", "raw": {"status": "started", "pid": 9999}},
            "verification": {
                "status": "observed",
                "check": "cnext_process_scan",
                "evidence": {
                    "target_image": "CNEXT.exe",
                    "observed_process": "CNEXT.exe",
                    "pid": 9999,
                    "match_found": True,
                    "instance_scope": "global_image_name_snapshot_only",
                },
            },
        }

        with patch("kernel.Kernel._execute_plan_dict", return_value=mock_kernel_exec):
            mcp_res = _execute_authorized_plan(str(self.workspace), plan)

        self.assertEqual(mcp_res["status"], "ok")
        self.assertEqual(mcp_res["operation"], "execute")
        self.assertEqual(mcp_res["action"], "start_catia")
        self.assertEqual(mcp_res["execution"]["status"], "completed")
        self.assertEqual(mcp_res["execution"]["action_result"], "started")
        self.assertEqual(mcp_res["verification"]["status"], "observed")
        self.assertEqual(
            mcp_res["verification"]["evidence"]["instance_scope"],
            "global_image_name_snapshot_only",
        )

    def test_mcp_error_path_forwards_envelopes(self):
        plan = _make_plan("start_catia", self.workspace, {"wait_for_exit": True})
        mock_kernel_error = {
            "status": "error",
            "message": "Start failed",
            "errors": ["Subprocess failed to launch"],
            "execution": {"status": "error", "action_result": "error", "raw": {"status": "error"}},
            "verification": {"status": "not_run", "check": "none", "evidence": {"reason": "launch_error"}},
        }

        with patch("kernel.Kernel._execute_plan_dict", return_value=mock_kernel_error):
            mcp_res = _execute_authorized_plan(str(self.workspace), plan)

        self.assertEqual(mcp_res["status"], "error")
        self.assertEqual(mcp_res["execution"]["status"], "error")
        self.assertEqual(mcp_res["verification"]["status"], "not_run")

    def test_mcp_does_not_forward_build_shaped_envelopes(self):
        """P0-1 guard: a build-shaped envelope (execution.status='success') is NOT forwarded.

        Even if the top-level keys are present with the same names, the status-domain
        validation rejects them, so the AI never sees P5.3-forbidden statuses.
        """
        plan = _make_plan("start_catia", self.workspace, {"wait_for_exit": True})
        build_shaped = {
            "status": "ok",
            "message": "Build successful",
            "data": {},
            "execution": {"status": "success"},          # build.py domain, NOT P5.3
            "verification": {"ok": True, "envelope_status": "passed", "dlls": []},
        }

        with patch("kernel.Kernel._execute_plan_dict", return_value=build_shaped):
            mcp_res = _execute_authorized_plan(str(self.workspace), plan)

        self.assertNotIn("execution", mcp_res)
        self.assertNotIn("verification", mcp_res)

    def test_mcp_does_not_forward_for_non_p53_action(self):
        """Action gate: even a valid P5.3-shaped envelope is not forwarded for a non-P5.3 action."""
        plan = _make_plan("build", self.workspace, {"options": "-u -a"})
        weird = {
            "status": "ok",
            "message": "Build complete",
            "data": {},
            "execution": {"status": "completed"},
            "verification": {"status": "passed", "check": "x"},
        }

        with patch("kernel.Kernel._execute_plan_dict", return_value=weird):
            mcp_res = _execute_authorized_plan(str(self.workspace), plan)

        self.assertNotIn("execution", mcp_res)
        self.assertNotIn("verification", mcp_res)


class TestP54OptimizerIsolation(unittest.TestCase):
    """P0-1: the global optimizer must not be a conduit for either envelope contract."""

    def test_optimizer_strips_build_envelopes(self):
        build_result = {
            "status": "success",
            "message": "Build successful",
            "error_count": 0,
            "warning_count": 0,
            "execution": {"status": "success"},
            "verification": {"ok": True, "dlls": [{"name": "M.dll", "status": "ok"}], "envelope_status": "passed"},
        }
        for mode in ("auto", "brief"):
            out = optimize(dict(build_result), mode=mode)
            self.assertNotIn("execution", out, f"mode={mode} leaked build execution envelope")
            self.assertNotIn("verification", out, f"mode={mode} leaked build verification envelope")

    def test_optimizer_does_not_globally_passthrough_envelope_keys(self):
        from token_optimizer import _PASSTHROUGH_KEYS
        self.assertNotIn("execution", _PASSTHROUGH_KEYS)
        self.assertNotIn("verification", _PASSTHROUGH_KEYS)


class TestP54RealChain(unittest.TestCase):
    """Real chain: MCP entry -> real Kernel -> real run -> optimizer.

    Only the OS boundary (subprocess / process scan) is mocked. This is the path
    the layer-mocked tests could not cover, and where P0-1/P0-2 actually surfaced.
    """

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_real_chain_completed_preserves_envelopes_and_raw(self):
        plan = _make_plan("start_catia", self.workspace, {"wait_for_exit": True})
        mock_proc = MagicMock()
        mock_proc.returncode = 0

        with patch("subprocess.run", return_value=mock_proc), \
             patch("run.check_catia_running", return_value={"status": "not_running"}):
            res = mcp_server._execute_authorized_plan(str(self.workspace), plan)

        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["operation"], "execute")
        self.assertEqual(res["action"], "start_catia")
        # P5.3 envelope reaches the final (AI-facing) output
        self.assertEqual(res["execution"]["status"], "completed")
        self.assertEqual(res["execution"]["action_result"], "exited")
        self.assertEqual(res["verification"]["status"], "not_run")
        self.assertEqual(res["verification"]["check"], "none")
        # execution.raw carries the legacy fields to the AI
        raw = res["execution"]["raw"]
        self.assertEqual(raw["status"], "exited")
        self.assertEqual(raw["exit_code"], 0)
        self.assertIn("message", raw)

    def test_real_chain_exception_maps_to_error_with_envelope(self):
        plan = _make_plan("start_catia", self.workspace, {"wait_for_exit": True})

        with patch("subprocess.run", side_effect=RuntimeError("boom")), \
             patch("run.check_catia_running", return_value={"status": "not_running"}):
            res = mcp_server._execute_authorized_plan(str(self.workspace), plan)

        self.assertEqual(res["status"], "error")
        self.assertEqual(res["execution"]["status"], "error")
        self.assertEqual(res["verification"]["status"], "not_run")
        self.assertIn("raw", res["execution"])

    def test_real_chain_timeout_not_ok_and_envelope_preserved(self):
        # NOTE: "timeout" is deliberately NOT a plan parameter. Kernel's
        # allowed_params["start_catia"] == {"env_name", "wait_for_exit"}, so passing
        # it would be rejected before start_catia_runtime is ever reached. The
        # timeout is injected at the OS boundary instead (the only mocked edge).
        plan = _make_plan("start_catia", self.workspace, {"wait_for_exit": True})

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="start", timeout=300)), \
             patch("run.check_catia_running", return_value={"status": "not_running"}):
            res = mcp_server._execute_authorized_plan(str(self.workspace), plan)

        # Outer status MUST reflect failure; the timeout fact stays visible.
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["execution"]["status"], "timeout")
        self.assertEqual(res["verification"]["status"], "not_run")

    def test_real_chain_build_request_does_not_leak_envelope_contract(self):
        """The develop-with-build path must not surface execution/verification to the AI."""
        fake_build = {
            "status": "success",
            "message": "Build successful",
            "error_count": 0,
            "warning_count": 0,
            "execution": {"status": "success"},
            "verification": {"ok": True, "envelope_status": "passed", "dlls": []},
        }

        with patch("build.incremental_build", return_value=fake_build), \
             patch("run.check_catia_running", return_value={"status": "not_running"}):
            res = mcp_server.handle_tool("develop", {"workspace": str(self.workspace), "request": "build the workspace"})

        self.assertNotIn("execution", res)
        self.assertNotIn("verification", res)


if __name__ == "__main__":
    unittest.main()
