"""
Unit tests for Change Provenance Guard integration into build_workspace (Step 2-D.1)
===================================================================================
Verifies read-only diagnostic provenance audit hook in build.py:
  1. Default build without baseline -> NOT_EVALUATED (zero disk I/O, zero overhead)
  2. Invalid baseline/inputs -> NOT_EVALUATED with sanitized reason code
  3. Valid inputs + verified delta -> EVALUATED (PROVENANCE_VERIFIED)
  4. Valid inputs + unregistered external change -> EVALUATED (UNTRACKED_EXTERNAL)
  5. Audit exception -> FAILED (non-blocking Fail-Open, build succeeds)
  6. Early errors & timeouts -> consistent provenance_audit schema
"""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "skills"))

from build import build_workspace, incremental_build
from provenance_guard import (
    ExpectedChange,
    ProvenanceAuditState,
    ProvenanceStatus,
    WorkingTreeState,
    compute_file_sha256,
)


class TestBuildProvenanceIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp_dir.name)
        # Create minimal CAA workspace structure
        self.fw_dir = self.workspace / "TestFw.edu"
        self.mod_dir = self.fw_dir / "TestMod.m"
        self.src_dir = self.mod_dir / "src"
        self.src_dir.mkdir(parents=True)
        (self.mod_dir / "Imakefile.mk").write_text("BUILT_OBJECT_TYPE=SHARED LIBRARY\n")
        (self.fw_dir / "IdentityCard" / "IdentityCard.xml").parent.mkdir(parents=True)
        (self.fw_dir / "IdentityCard" / "IdentityCard.xml").write_text("<xml/>\n")
        (self.src_dir / "Main.cpp").write_text("int main() { return 0; }\n")

    def tearDown(self):
        self.tmp_dir.cleanup()

    @patch("build.setup_prerequisite_path", return_value={"status": "success"})
    @patch("build.validate_workspace", return_value={"ok": True, "issues": [], "can_build": True})
    @patch("build.sync_runtime_view", return_value={"synced": []})
    @patch("build.verify_build", return_value={"ok": True, "issues": [], "dlls": []})
    @patch("build.subprocess.run")
    @patch("build.CAAEnvironment")
    def test_default_build_without_baseline_is_not_evaluated(
        self, mock_env_cls, mock_run, mock_verify, mock_sync, mock_val, mock_prereq
    ):
        mock_env = mock_env_cls.return_value
        mock_env.load_config.return_value = True
        mock_env.build_time_command.return_value = (["cmd", "/c"], "cmd /c")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"# make: TestFw.edu\\TestMod.m\nEXIT_CODE=0\n"
        mock_proc.stderr = b""
        mock_run.return_value = mock_proc

        # Execute default build (no baseline passed)
        res = build_workspace(self.workspace, skip_gate=True)
        self.assertEqual(res["status"], "success")

        # Provenance audit must be NOT_EVALUATED with missing inputs reason
        self.assertIn("provenance_audit", res)
        audit = res["provenance_audit"]
        self.assertEqual(audit["audit_state"], ProvenanceAuditState.NOT_EVALUATED)
        self.assertEqual(audit["reason"], "missing_baseline_or_expected_changes")
        self.assertEqual(audit["provenance_status"], "not_applicable")
        self.assertEqual(audit["untracked_changes"], [])
        self.assertEqual(audit["untracked_change_count"], 0)

    @patch("build.setup_prerequisite_path", return_value={"status": "success"})
    @patch("build.validate_workspace", return_value={"ok": True, "issues": [], "can_build": True})
    @patch("build.sync_runtime_view", return_value={"synced": []})
    @patch("build.verify_build", return_value={"ok": True, "issues": [], "dlls": []})
    @patch("build.subprocess.run")
    @patch("build.CAAEnvironment")
    def test_build_with_invalid_baseline_path_is_not_evaluated(
        self, mock_env_cls, mock_run, mock_verify, mock_sync, mock_val, mock_prereq
    ):
        mock_env = mock_env_cls.return_value
        mock_env.load_config.return_value = True
        mock_env.build_time_command.return_value = (["cmd", "/c"], "cmd /c")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"EXIT_CODE=0\n"
        mock_proc.stderr = b""
        mock_run.return_value = mock_proc

        # Pass baseline containing illegal Windows backslash
        bad_baseline = {"TestFw.edu\\TestMod.m/src/Main.cpp": "a" * 64}
        res = build_workspace(
            self.workspace,
            skip_gate=True,
            baseline_snapshot=bad_baseline,
            expected_changes=[],
        )
        self.assertEqual(res["status"], "success")

        audit = res["provenance_audit"]
        self.assertEqual(audit["audit_state"], ProvenanceAuditState.NOT_EVALUATED)
        self.assertEqual(audit["reason"], "invalid_baseline_path")

    @patch("build.setup_prerequisite_path", return_value={"status": "success"})
    @patch("build.validate_workspace", return_value={"ok": True, "issues": [], "can_build": True})
    @patch("build.sync_runtime_view", return_value={"synced": []})
    @patch("build.verify_build", return_value={"ok": True, "issues": [], "dlls": []})
    @patch("build.subprocess.run")
    @patch("build.CAAEnvironment")
    def test_build_with_verified_provenance(
        self, mock_env_cls, mock_run, mock_verify, mock_sync, mock_val, mock_prereq
    ):
        mock_env = mock_env_cls.return_value
        mock_env.load_config.return_value = True
        mock_env.build_time_command.return_value = (["cmd", "/c"], "cmd /c")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"EXIT_CODE=0\n"
        mock_proc.stderr = b""
        mock_run.return_value = mock_proc

        # Simulate baseline prior to change
        main_cpp = self.src_dir / "Main.cpp"
        main_rel = "TestFw.edu/TestMod.m/src/Main.cpp"
        base_sha = "0" * 64
        baseline = {
            main_rel: base_sha,
            "TestFw.edu/TestMod.m/Imakefile.mk": compute_file_sha256(self.mod_dir / "Imakefile.mk"),
            "TestFw.edu/IdentityCard/IdentityCard.xml": compute_file_sha256(self.fw_dir / "IdentityCard" / "IdentityCard.xml"),
        }

        # Modify Main.cpp
        main_cpp.write_text("int main() { return 42; }\n")
        new_sha = compute_file_sha256(main_cpp)

        # Register expected change
        expected = [ExpectedChange(main_rel, "modify", new_sha)]

        res = incremental_build(
            self.workspace,
            baseline_snapshot=baseline,
            expected_changes=expected,
        )
        self.assertEqual(res["status"], "success")

        audit = res["provenance_audit"]
        self.assertEqual(audit["audit_state"], ProvenanceAuditState.EVALUATED)
        self.assertEqual(audit["provenance_status"], ProvenanceStatus.PROVENANCE_VERIFIED)
        self.assertEqual(audit["working_tree_state"], WorkingTreeState.DIRTY)
        self.assertEqual(audit["untracked_changes"], [])
        self.assertEqual(audit["untracked_change_count"], 0)
        self.assertEqual(audit["matched_change_count"], 1)

    @patch("build.setup_prerequisite_path", return_value={"status": "success"})
    @patch("build.validate_workspace", return_value={"ok": True, "issues": [], "can_build": True})
    @patch("build.sync_runtime_view", return_value={"synced": []})
    @patch("build.verify_build", return_value={"ok": True, "issues": [], "dlls": []})
    @patch("build.subprocess.run")
    @patch("build.CAAEnvironment")
    def test_build_detects_untracked_external_source_modification(
        self, mock_env_cls, mock_run, mock_verify, mock_sync, mock_val, mock_prereq
    ):
        mock_env = mock_env_cls.return_value
        mock_env.load_config.return_value = True
        mock_env.build_time_command.return_value = (["cmd", "/c"], "cmd /c")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"EXIT_CODE=0\n"
        mock_proc.stderr = b""
        mock_run.return_value = mock_proc

        main_rel = "TestFw.edu/TestMod.m/src/Main.cpp"
        imake_rel = "TestFw.edu/TestMod.m/Imakefile.mk"
        id_rel = "TestFw.edu/IdentityCard/IdentityCard.xml"

        baseline = {
            main_rel: compute_file_sha256(self.src_dir / "Main.cpp"),
            imake_rel: compute_file_sha256(self.mod_dir / "Imakefile.mk"),
            id_rel: compute_file_sha256(self.fw_dir / "IdentityCard" / "IdentityCard.xml"),
        }

        # Modify Main.cpp and register it
        (self.src_dir / "Main.cpp").write_text("int main() { return 1; }\n")
        expected = [ExpectedChange(main_rel, "modify", compute_file_sha256(self.src_dir / "Main.cpp"))]

        # External side-effect: create an untracked Extra.cpp
        (self.src_dir / "Extra.cpp").write_text("void extra() {}\n")

        res = build_workspace(
            self.workspace,
            skip_gate=True,
            baseline_snapshot=baseline,
            expected_changes=expected,
        )
        self.assertEqual(res["status"], "success")

        audit = res["provenance_audit"]
        self.assertEqual(audit["audit_state"], ProvenanceAuditState.EVALUATED)
        self.assertEqual(audit["provenance_status"], ProvenanceStatus.UNTRACKED_EXTERNAL)
        self.assertIn("TestFw.edu/TestMod.m/src/Extra.cpp", audit["untracked_changes"])
        self.assertEqual(audit["untracked_change_count"], 1)

    @patch("build.setup_prerequisite_path", return_value={"status": "success"})
    @patch("build.validate_workspace", return_value={"ok": True, "issues": [], "can_build": True})
    @patch("build.sync_runtime_view", return_value={"synced": []})
    @patch("build.verify_build", return_value={"ok": True, "issues": [], "dlls": []})
    @patch("build.subprocess.run")
    @patch("build.CAAEnvironment")
    def test_audit_exception_is_non_blocking_fail_open(
        self, mock_env_cls, mock_run, mock_verify, mock_sync, mock_val, mock_prereq
    ):
        mock_env = mock_env_cls.return_value
        mock_env.load_config.return_value = True
        mock_env.build_time_command.return_value = (["cmd", "/c"], "cmd /c")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"EXIT_CODE=0\n"
        mock_proc.stderr = b""
        mock_run.return_value = mock_proc

        # Mock capture_source_snapshot to raise unexpected OS error
        with patch("provenance_guard.capture_source_snapshot", side_effect=PermissionError("Locked directory")):
            res = build_workspace(
                self.workspace,
                skip_gate=True,
                baseline_snapshot={"TestFw.edu/TestMod.m/src/Main.cpp": "a" * 64},
                expected_changes=[],
            )

        # Build must remain successful (Fail-Open)
        self.assertEqual(res["status"], "success")

        # Provenance audit must be marked as FAILED with safe error_type
        audit = res["provenance_audit"]
        self.assertEqual(audit["audit_state"], ProvenanceAuditState.FAILED)
        self.assertEqual(audit["reason"], "internal_audit_exception")
        self.assertEqual(audit["provenance_status"], "audit_failed")
        self.assertEqual(audit["error_type"], "PermissionError")
        self.assertEqual(audit["untracked_changes"], [])

    def test_early_abort_contains_consistent_not_evaluated_audit(self):
        # Non-existent workspace path triggers path_validation abort
        res = build_workspace(self.workspace / "NonExistentPath")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res.get("stage"), "path_validation")

        self.assertIn("provenance_audit", res)
        audit = res["provenance_audit"]
        self.assertEqual(audit["audit_state"], ProvenanceAuditState.NOT_EVALUATED)
        self.assertEqual(audit["reason"], "build_aborted_at_path_validation")
        self.assertEqual(audit["provenance_status"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
