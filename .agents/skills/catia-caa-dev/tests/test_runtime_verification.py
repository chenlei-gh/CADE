#!/usr/bin/env python3
"""
Test Suite for P5.3 Runtime Verification Envelope
==================================================
Strictly validates P5.3 Minimal Contract Specification v1.0 (Freeze Candidate v0.2.6):
- Dual-envelope isolation: execution (completed/error/timeout) vs verification (passed/failed/observed/not_run)
- Never use "success" for execution.status
- Strict branch-driven verification semantics
- Predicate scope lock on runtime_candidate_path_exists
- Full backward compatibility for legacy top-level callers
"""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from run import start_catia_runtime, stop_catia
from runtime_view import check_runtime_view


class TestRuntimeVerification(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    # =========================================================================
    # 1. start_catia_runtime tests
    # =========================================================================

    def test_start_catia_wait_for_exit_completed_and_verification_not_run(self):
        """wait_for_exit=True: launcher subprocess terminates, raw exit_code preserved, verification not_run."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0

        with patch("subprocess.run", return_value=mock_proc):
            res = start_catia_runtime(
                workspace_path=self.workspace,
                wait_for_exit=True,
                entrypoint="python_cli",
                orchestrated_by_kernel=False,
            )

        # Legacy top-level compatibility
        self.assertEqual(res["status"], "exited")
        self.assertEqual(res["exit_code"], 0)
        self.assertIn("message", res)

        # Execution envelope
        self.assertIn("execution", res)
        self.assertEqual(res["execution"]["status"], "completed")
        self.assertNotEqual(res["execution"]["status"], "success")  # Strict rule: NEVER "success"
        self.assertEqual(res["execution"]["action_result"], "exited")
        self.assertEqual(res["execution"]["raw"]["status"], "exited")
        self.assertEqual(res["execution"]["raw"]["exit_code"], 0)

        # Verification envelope
        self.assertIn("verification", res)
        self.assertEqual(res["verification"]["status"], "not_run")
        self.assertEqual(res["verification"]["check"], "none")
        self.assertEqual(
            res["verification"]["evidence"]["reason"],
            "launcher_exit_code_does_not_prove_cnext_lifecycle",
        )
        # Negative constraint: exit_code=0 MUST NOT be interpreted as passed
        self.assertNotEqual(res["verification"]["status"], "passed")

    def test_start_catia_wait_for_exit_non_zero_exit_code(self):
        """wait_for_exit=True with non-zero returncode preserves code without mapping to verification failure."""
        mock_proc = MagicMock()
        mock_proc.returncode = 42

        with patch("subprocess.run", return_value=mock_proc):
            res = start_catia_runtime(
                workspace_path=self.workspace,
                wait_for_exit=True,
            )

        self.assertEqual(res["status"], "exited")
        self.assertEqual(res["exit_code"], 42)
        self.assertEqual(res["execution"]["status"], "completed")
        self.assertEqual(res["execution"]["action_result"], "exited")
        self.assertEqual(res["execution"]["raw"]["exit_code"], 42)
        self.assertEqual(res["verification"]["status"], "not_run")
        self.assertNotEqual(res["verification"]["status"], "failed")

    def test_start_catia_process_detected_started(self):
        """wait_for_exit=False when CNEXT.exe detected: observed status with pid evidence."""
        mock_popen = MagicMock()
        mock_running = [{"pid": 8888, "name": "CNEXT.exe"}]

        with patch("subprocess.Popen", return_value=mock_popen), \
             patch("run.check_process_running", return_value=mock_running):
            res = start_catia_runtime(
                workspace_path=self.workspace,
                wait_for_exit=False,
            )

        self.assertEqual(res["status"], "started")
        self.assertEqual(res["pid"], 8888)
        self.assertEqual(res["execution"]["status"], "completed")
        self.assertEqual(res["execution"]["action_result"], "started")
        self.assertEqual(res["execution"]["raw"]["status"], "started")

        self.assertEqual(res["verification"]["status"], "observed")
        self.assertEqual(res["verification"]["check"], "cnext_process_scan")
        self.assertTrue(res["verification"]["evidence"]["match_found"])
        self.assertEqual(res["verification"]["evidence"]["observed_process"], "CNEXT.exe")
        self.assertEqual(res["verification"]["evidence"]["pid"], 8888)
        # Negative constraint: observed is neither passed nor failed
        self.assertNotIn(res["verification"]["status"], ["passed", "failed"])

    def test_start_catia_polling_exhausted_launching(self):
        """wait_for_exit=False when polling exhausted: status launching, v1_classification not_specified_in_v1."""
        mock_popen = MagicMock()

        with patch("subprocess.Popen", return_value=mock_popen), \
             patch("run.check_process_running", return_value=[]), \
             patch("time.sleep", return_value=None):
            res = start_catia_runtime(
                workspace_path=self.workspace,
                wait_for_exit=False,
            )

        self.assertEqual(res["status"], "launching")
        self.assertEqual(res["execution"]["status"], "completed")
        self.assertEqual(res["execution"]["action_result"], "launching")
        self.assertEqual(res["execution"]["raw"]["status"], "launching")

        self.assertEqual(res["verification"]["status"], "not_run")
        self.assertEqual(res["verification"]["check"], "catia_start_pending")
        self.assertEqual(
            res["verification"]["evidence"]["v1_classification"],
            "not_specified_in_v1",
        )
        # Negative constraint: launching is NOT mapped to passed or failed
        self.assertNotIn(res["verification"]["status"], ["passed", "failed"])

    def test_start_catia_timeout_and_error_envelopes(self):
        """TimeoutExpired and generic exceptions produce timeout/error execution status with verification not_run."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="start", timeout=10)):
            res_timeout = start_catia_runtime(
                workspace_path=self.workspace,
                wait_for_exit=True,
                timeout=10,
            )
        self.assertEqual(res_timeout["status"], "timeout")
        self.assertEqual(res_timeout["execution"]["status"], "timeout")
        self.assertEqual(res_timeout["execution"]["action_result"], "timeout")
        self.assertEqual(res_timeout["verification"]["status"], "not_run")

        with patch("subprocess.run", side_effect=RuntimeError("Subprocess failed to launch")):
            res_error = start_catia_runtime(
                workspace_path=self.workspace,
                wait_for_exit=True,
            )
        self.assertEqual(res_error["status"], "error")
        self.assertEqual(res_error["execution"]["status"], "error")
        self.assertEqual(res_error["execution"]["action_result"], "error")
        self.assertEqual(res_error["verification"]["status"], "not_run")

    # =========================================================================
    # 2. stop_catia tests
    # =========================================================================

    def test_stop_catia_precheck_not_running(self):
        """stop_catia when no processes detected: verification observed with single_query_snapshot_only."""
        with patch("run.check_process_running", return_value=[]):
            res = stop_catia()

        self.assertEqual(res["status"], "not_running")
        self.assertEqual(res["execution"]["status"], "completed")
        self.assertEqual(res["execution"]["action_result"], "not_running")
        self.assertEqual(res["execution"]["raw"]["status"], "not_running")

        self.assertEqual(res["verification"]["status"], "observed")
        self.assertEqual(res["verification"]["check"], "cnext_process_scan")
        self.assertFalse(res["verification"]["evidence"]["match_found"])
        self.assertEqual(
            res["verification"]["evidence"]["instance_scope"],
            "single_query_snapshot_only",
        )
        # Negative constraint: does not claim global absence or taskkill execution
        self.assertNotIn(res["verification"]["status"], ["passed", "failed"])

    def test_stop_catia_stopped_processes(self):
        """stop_catia when process stopped: verification observed with post_stop_process_scan scope."""
        with patch("run.check_process_running", return_value=[{"pid": 4321, "name": "CNEXT.exe"}]), \
             patch("run._wait_pid_exit", return_value=True), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)), \
             patch("time.sleep", return_value=None):
            res = stop_catia(force=True)

        self.assertEqual(res["status"], "stopped")
        self.assertEqual(res["stopped"], [4321])
        self.assertEqual(res["execution"]["status"], "completed")
        self.assertEqual(res["execution"]["action_result"], "stopped")

        self.assertEqual(res["verification"]["status"], "observed")
        self.assertEqual(res["verification"]["check"], "cnext_process_scan")
        self.assertEqual(
            res["verification"]["evidence"]["instance_scope"],
            "post_stop_process_scan",
        )
        self.assertEqual(res["verification"]["evidence"]["stopped_pids"], [4321])

    # =========================================================================
    # 3. check_runtime_view tests
    # =========================================================================

    def test_runtime_view_found_architecture_matched(self):
        """Matching architecture: verification passed, architecture_matched=True, scope path_existence_predicate_only."""
        win_b64 = self.workspace / "win_b64"
        win_b64.mkdir(parents=True)

        with patch("runtime_view.CAAEnvironment.get_architecture", return_value="win_b64"):
            res = check_runtime_view(self.workspace)

        self.assertEqual(res["status"], "found")
        self.assertEqual(len(res["runtime_views"]), 1)
        self.assertEqual(res["execution"]["status"], "completed")
        self.assertEqual(res["execution"]["action_result"], "found")
        self.assertEqual(res["execution"]["raw"]["status"], "found")

        self.assertEqual(res["verification"]["status"], "passed")
        self.assertEqual(res["verification"]["check"], "runtime_candidate_path_exists")
        self.assertTrue(res["verification"]["evidence"]["exists"])
        self.assertTrue(res["verification"]["evidence"]["architecture_matched"])
        self.assertEqual(res["verification"]["evidence"]["configured_architecture"], "win_b64")
        self.assertEqual(res["verification"]["evidence"]["target_architecture"], "win_b64")
        self.assertEqual(
            res["verification"]["evidence"]["instance_scope"],
            "path_existence_predicate_only",
        )

    def test_runtime_view_found_architecture_mismatched_counterexample(self):
        """Counterexample test: intel_a candidate exists, configured is win_b64.
        Passed applies ONLY to path node existence; architecture_matched MUST be False."""
        intel_a = self.workspace / "intel_a"
        intel_a.mkdir(parents=True)

        with patch("runtime_view.CAAEnvironment.get_architecture", return_value="win_b64"):
            res = check_runtime_view(self.workspace)

        self.assertEqual(res["status"], "found")
        self.assertEqual(len(res["runtime_views"]), 1)
        self.assertEqual(res["runtime_views"][0]["architecture"], "intel_a")

        self.assertEqual(res["execution"]["status"], "completed")
        self.assertEqual(res["execution"]["action_result"], "found")

        # Crucial predicate scope lock test
        self.assertEqual(res["verification"]["status"], "passed")
        self.assertEqual(res["verification"]["check"], "runtime_candidate_path_exists")
        self.assertEqual(res["verification"]["evidence"]["target_architecture"], "intel_a")
        self.assertEqual(res["verification"]["evidence"]["configured_architecture"], "win_b64")
        # Negative boundary enforcement: MUST be False
        self.assertFalse(res["verification"]["evidence"]["architecture_matched"])

    def test_runtime_view_regular_file_path_existence_predicate(self):
        """Path.exists() returns True on regular files: proves predicate is path node existence, not directory validation."""
        fake_file = self.workspace / "win_b64"
        fake_file.write_text("regular file node, not a directory", encoding="utf-8")

        self.assertTrue(fake_file.exists())
        self.assertFalse(fake_file.is_dir())

        with patch("runtime_view.CAAEnvironment.get_architecture", return_value="win_b64"):
            res = check_runtime_view(self.workspace)

        self.assertEqual(res["status"], "found")
        self.assertEqual(res["verification"]["status"], "passed")
        self.assertEqual(res["verification"]["check"], "runtime_candidate_path_exists")
        self.assertTrue(res["verification"]["evidence"]["exists"])
        # Node exists, but is not asserted to be a valid directory or usable runtime view
        self.assertEqual(
            res["verification"]["evidence"]["instance_scope"],
            "path_existence_predicate_only",
        )

    def test_runtime_view_not_found(self):
        """Empty workspace: verification failed, exists=False, architecture_matched=False."""
        with patch("runtime_view.CAAEnvironment.get_architecture", return_value="win_b64"):
            res = check_runtime_view(self.workspace)

        self.assertEqual(res["status"], "not_found")
        self.assertEqual(res["runtime_views"], [])
        self.assertEqual(res["execution"]["status"], "completed")
        self.assertEqual(res["execution"]["action_result"], "not_found")
        self.assertEqual(res["execution"]["raw"]["status"], "not_found")

        self.assertEqual(res["verification"]["status"], "failed")
        self.assertEqual(res["verification"]["check"], "runtime_candidate_path_exists")
        self.assertFalse(res["verification"]["evidence"]["exists"])
        self.assertFalse(res["verification"]["evidence"]["architecture_matched"])
        self.assertEqual(res["verification"]["evidence"]["reason"], "no_candidate_path_exists")

    # =========================================================================
    # 4. Backward Compatibility tests
    # =========================================================================

    def test_backward_compatibility_preserves_all_legacy_fields(self):
        """Legacy callers reading top-level status, message, etc. continue to work unchanged."""
        empty_res = check_runtime_view(self.workspace)
        self.assertIn("status", empty_res)
        self.assertIn("message", empty_res)
        self.assertIn("runtime_views", empty_res)
        self.assertIsInstance(empty_res["status"], str)
        self.assertIsInstance(empty_res["runtime_views"], list)

        # raw matches top-level legacy shape
        raw = empty_res["execution"]["raw"]
        self.assertEqual(raw["status"], empty_res["status"])
        self.assertEqual(raw["message"], empty_res["message"])
        self.assertEqual(raw["runtime_views"], empty_res["runtime_views"])


if __name__ == "__main__":
    unittest.main()
