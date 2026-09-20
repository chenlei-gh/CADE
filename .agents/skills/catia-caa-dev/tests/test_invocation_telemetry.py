#!/usr/bin/env python3
"""
Test Invocation Telemetry (P0-A Verification)
==============================================
Validates that build, gate, and runtime invocations accurately record:
- entrypoint ("python_cli" | "cade_cli" | "kernel")
- orchestrated_by_kernel (bool)
- operation ("build" | "build_gate" | "start_runtime" | "stop_runtime")
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

SKILL_ROOT = Path(__file__).resolve().parent.parent / "skills"
sys.path.insert(0, str(SKILL_ROOT))

from build_gate import run_gate
from build import build_workspace, incremental_build, full_build, clean_build
from run import start_catia_runtime, stop_catia
from repair import RepairLoop
from kernel import Kernel, KernelMode


class TestInvocationTelemetry(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_run_gate_defaults(self):
        """Direct call to run_gate defaults to python_cli, orchestrated_by_kernel=False, operation=gate, stage=build_gate"""
        res = run_gate(self.ws, skip=True)
        self.assertEqual(res.get("entrypoint"), "python_cli")
        self.assertFalse(res.get("orchestrated_by_kernel"))
        self.assertEqual(res.get("operation"), "gate")
        self.assertEqual(res.get("stage"), "build_gate")

    def test_run_gate_explicit_cade_cli(self):
        """CLI call to run_gate preserves cade_cli, False, operation=gate, stage=build_gate"""
        res = run_gate(self.ws, skip=True, entrypoint="cade_cli", orchestrated_by_kernel=False)
        self.assertEqual(res.get("entrypoint"), "cade_cli")
        self.assertFalse(res.get("orchestrated_by_kernel"))
        self.assertEqual(res.get("operation"), "gate")
        self.assertEqual(res.get("stage"), "build_gate")

    def test_run_gate_unverified_kernel_downgraded(self):
        """External call attempting orchestrated_by_kernel=True without Kernel in stack is downgraded"""
        res = run_gate(self.ws, skip=True, entrypoint="kernel", orchestrated_by_kernel=True)
        self.assertEqual(res.get("entrypoint"), "unverified_kernel")
        self.assertFalse(res.get("orchestrated_by_kernel"))
        self.assertEqual(res.get("operation"), "gate")
        self.assertEqual(res.get("stage"), "build_gate")
        self.assertIn("telemetry_audit_warning", res)

    @patch("build.CAAEnvironment")
    def test_build_workspace_error_defaults(self, mock_env):
        """Early return errors in build_workspace still carry telemetry fields with stage"""
        mock_env_instance = MagicMock()
        mock_env_instance.load_config.return_value = False
        mock_env.return_value = mock_env_instance

        res = build_workspace(self.ws)
        self.assertEqual(res.get("entrypoint"), "python_cli")
        self.assertFalse(res.get("orchestrated_by_kernel"))
        self.assertEqual(res.get("operation"), "build")
        self.assertEqual(res.get("stage"), "env_validation")

    @patch("build.CAAEnvironment")
    def test_build_workspace_unverified_kernel_downgraded(self, mock_env):
        """build_workspace downgrades fabricated kernel flag when not in Kernel stack"""
        mock_env_instance = MagicMock()
        mock_env_instance.load_config.return_value = False
        mock_env.return_value = mock_env_instance

        res = build_workspace(self.ws, entrypoint="kernel", orchestrated_by_kernel=True)
        self.assertEqual(res.get("entrypoint"), "unverified_kernel")
        self.assertFalse(res.get("orchestrated_by_kernel"))
        self.assertEqual(res.get("operation"), "build")
        self.assertIn("telemetry_audit_warning", res)

    def test_stop_catia_telemetry(self):
        """stop_catia carries invocation telemetry and validates caller stack"""
        with patch("run.check_process_running", return_value=[]):
            res_default = stop_catia()
            self.assertEqual(res_default.get("entrypoint"), "python_cli")
            self.assertFalse(res_default.get("orchestrated_by_kernel"))
            self.assertEqual(res_default.get("operation"), "stop_runtime")
            self.assertEqual(res_default.get("stage"), "runtime_stop")

            res_unverified = stop_catia(entrypoint="kernel", orchestrated_by_kernel=True)
            self.assertEqual(res_unverified.get("entrypoint"), "unverified_kernel")
            self.assertFalse(res_unverified.get("orchestrated_by_kernel"))
            self.assertEqual(res_unverified.get("operation"), "stop_runtime")
            self.assertEqual(res_unverified.get("stage"), "runtime_stop")
            self.assertIn("telemetry_audit_warning", res_unverified)

    def test_start_catia_runtime_error_telemetry(self):
        """start_catia_runtime with nonexistent path carries invocation telemetry and verifies stack"""
        bad_path = self.ws / "nonexistent"
        res_default = start_catia_runtime(workspace_path=str(bad_path))
        self.assertEqual(res_default.get("entrypoint"), "python_cli")
        self.assertFalse(res_default.get("orchestrated_by_kernel"))
        self.assertEqual(res_default.get("operation"), "start_runtime")
        self.assertEqual(res_default.get("stage"), "runtime_start")

        res_unverified = start_catia_runtime(
            workspace_path=str(bad_path),
            entrypoint="kernel",
            orchestrated_by_kernel=True,
        )
        self.assertEqual(res_unverified.get("entrypoint"), "unverified_kernel")
        self.assertFalse(res_unverified.get("orchestrated_by_kernel"))
        self.assertEqual(res_unverified.get("operation"), "start_runtime")
        self.assertEqual(res_unverified.get("stage"), "runtime_start")
        self.assertIn("telemetry_audit_warning", res_unverified)

    def test_real_kernel_orchestration_stack_verification(self):
        """When invoked from within a real Kernel instance, orchestrated_by_kernel remains True"""
        k = Kernel(workspace_root=str(self.ws))
        # Call build_workspace from a method inside the Kernel class context
        with patch("build.CAAEnvironment") as mock_env:
            mock_env_instance = MagicMock()
            mock_env_instance.load_config.return_value = False
            mock_env.return_value = mock_env_instance
            # Define a Kernel method that invokes build_workspace
            def _kernel_build_caller(kernel_self):
                return build_workspace(self.ws, entrypoint="kernel", orchestrated_by_kernel=True)

            res = _kernel_build_caller(k)
            self.assertEqual(res.get("entrypoint"), "kernel")
            self.assertTrue(res.get("orchestrated_by_kernel"))
            self.assertNotIn("telemetry_audit_warning", res)

    def test_repair_loop_telemetry_propagation(self):
        """RepairLoop passes orchestration flag to build_workspace"""
        loop_standalone = RepairLoop(self.ws, with_build=True)
        self.assertFalse(loop_standalone._orchestrated_by_kernel)
        self.assertEqual(loop_standalone._entrypoint, "repair_cli")

        loop_kernel = RepairLoop(self.ws, with_build=True, entrypoint="kernel", orchestrated_by_kernel=True)
        self.assertTrue(loop_kernel._orchestrated_by_kernel)
        self.assertEqual(loop_kernel._entrypoint, "kernel")

    @patch("build.incremental_build")
    def test_kernel_handle_build_run_passes_telemetry(self, mock_build):
        """Kernel._handle_build_run explicitly passes entrypoint='kernel' and orchestrated_by_kernel=True"""
        mock_build.return_value = {
            "status": "success",
            "message": "mocked",
            "entrypoint": "kernel",
            "orchestrated_by_kernel": True,
            "operation": "build",
        }
        k = Kernel(workspace_root=str(self.ws))
        res = k.execute(KernelMode.DEVELOP, "build the workspace")
        self.assertIn(res.get("status"), ("ok", "success"))
        self.assertTrue(res.get("orchestrated_by_kernel"))
        self.assertEqual(res.get("entrypoint"), "kernel")
        mock_build.assert_called_once_with(self.ws, entrypoint="kernel", orchestrated_by_kernel=True)

    def test_gate_log_file_contains_telemetry(self):
        """build_gate_log.jsonl explicitly records entrypoint, orchestrated_by_kernel, operation, stage"""
        tmp_log = self.ws / "test_gate_log.jsonl"
        with patch("build_gate.LOG_FILE", tmp_log):
            run_gate(self.ws, skip=True, entrypoint="cade_cli", orchestrated_by_kernel=False)
            self.assertTrue(tmp_log.exists())
            with open(tmp_log, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertGreaterEqual(len(lines), 1)
            entry = lines[-1]
            self.assertEqual(entry.get("entrypoint"), "cade_cli")
            self.assertFalse(entry.get("orchestrated_by_kernel"))
            self.assertEqual(entry.get("operation"), "gate")
            self.assertEqual(entry.get("stage"), "build_gate")
            self.assertEqual(entry.get("decision"), "SKIP")


if __name__ == "__main__":
    unittest.main()
