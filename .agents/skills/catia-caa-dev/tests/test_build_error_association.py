"""
Integration tests for Build Error Association and Recovery Lifecycle (P3-A.1)
Verifies the end-to-end feedback loop:
  1. Maintenance analysis creates context.
  2. Build fails -> L0 compiler errors are attached to maintenance context.
  3. Subsequent maintenance analysis automatically prioritizes L0 build errors.
  4. Fix applied -> Build succeeds -> Unresolved build errors are automatically cleared.
"""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent / "skills"))

from maintenance_context import (
    MaintenanceContext,
    load_context,
    save_context,
    attach_build_result,
)
from kernel import Kernel, KernelMode


class TestBuildErrorAssociation(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp_dir.name)
        
        # Create a mock CAA structure: TestFw.edu/TestMod.m
        self.fw_dir = self.workspace / "TestFw.edu"
        self.fw_dir.mkdir()
        self.mod_dir = self.fw_dir / "TestMod.m"
        self.mod_dir.mkdir()
        self.src_dir = self.mod_dir / "src"
        self.src_dir.mkdir()
        self.local_int_dir = self.mod_dir / "LocalInterfaces"
        self.local_int_dir.mkdir()

        cmd_h = (
            "#ifndef TestCmd_H\n"
            "#define TestCmd_H\n"
            "#include \"CATCommand.h\"\n"
            "class TestCmd : public CATCommand {\n"
            "    CATDeclareClass;\n"
            "public:\n"
            "    TestCmd();\n"
            "    virtual ~TestCmd();\n"
            "    void BuildGraph();\n"
            "};\n"
            "#endif\n"
        )
        cmd_cpp = (
            "#include \"TestCmd.h\"\n"
            "CATCreateClass(TestCmd);\n"
            "TestCmd::TestCmd() : CATCommand(NULL, \"TestCmd\") {}\n"
            "TestCmd::~TestCmd() {}\n"
            "void TestCmd::BuildGraph() {}\n"
        )
        (self.src_dir / "TestCmd.cpp").write_text(cmd_cpp, encoding="utf-8")
        (self.local_int_dir / "TestCmd.h").write_text(cmd_h, encoding="utf-8")

        imakefile_content = (
            "BUILT_OBJECT_TYPE = SHARED LIBRARY\n"
            "LINK_WITH = CATApplicationFrame JS0GROUP\n"
        )
        (self.mod_dir / "Imakefile.mk").write_text(imakefile_content, encoding="utf-8")

        self.cpp_file = self.src_dir / "TestModPanelDlg.cpp"
        self.cpp_file.write_text(
            """#include <CATDlgDialog.h>
void TestModPanelDlg::BuildWindow() {
    int colWidth = 100;
}
""",
            encoding="utf-8",
        )
        self.kernel = Kernel(workspace_root=str(self.workspace))

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_full_build_failure_and_recovery_feedback_loop(self):
        # Step 1: Initial maintenance request
        res1 = self.kernel.execute(KernelMode.DEVELOP, "排查 TestMod.m 中列宽刷新问题")
        self.assertEqual(res1["status"], "ok")
        self.assertEqual(res1.get("target_module"), "TestMod.m")
        self.assertEqual(len(res1.get("active_build_errors", [])), 0)

        # Verify context file was saved on disk
        ctx = load_context(self.workspace, "TestMod.m")
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.target_module, "TestMod.m")

        # Step 2: Build fails (e.g. Developer introduced undeclared identifier in TestModPanelDlg.cpp)
        mock_build_failure = {
            "status": "failed",
            "duration_seconds": 5.2,
            "errors": [
                {
                    "file": str(self.cpp_file),
                    "line": 3,
                    "code": "C2065",
                    "message": "'undeclared_var': undeclared identifier",
                    "module": "TestMod.m",
                    "raw": f"{self.cpp_file}(3) : error C2065: 'undeclared_var': undeclared identifier",
                }
            ],
        }
        attached_ctx = attach_build_result(self.workspace, mock_build_failure, target_module="TestMod.m")
        self.assertIsNotNone(attached_ctx)
        self.assertEqual(len(attached_ctx.unresolved_build_errors), 1)

        # Step 3: Developer re-runs develop/maintenance analysis
        # System MUST automatically prioritize the L0 build error
        res2 = self.kernel.execute(KernelMode.DEVELOP, "排查 TestMod.m 中列宽刷新问题")
        active_errs = res2.get("active_build_errors", [])
        self.assertEqual(len(active_errs), 1)
        self.assertEqual(active_errs[0]["code"], "C2065")
        self.assertEqual(active_errs[0]["line"], 3)

        # Verify L0 error is prepended to relevant_locations
        rel_locs = res2.get("relevant_locations", [])
        self.assertGreater(len(rel_locs), 0)
        self.assertEqual(rel_locs[0].get("level"), "L0")
        self.assertEqual(rel_locs[0].get("symbol"), "[C2065]")

        # Step 4: Fix is applied and build succeeds
        mock_build_success = {
            "status": "success",
            "duration_seconds": 4.8,
            "errors": [],
        }
        attached_ctx2 = attach_build_result(self.workspace, mock_build_success, target_module="TestMod.m")
        self.assertIsNotNone(attached_ctx2)
        self.assertEqual(len(attached_ctx2.unresolved_build_errors), 0)

        # Step 5: Subsequent maintenance run -> No active build errors!
        res3 = self.kernel.execute(KernelMode.DEVELOP, "排查 TestMod.m 中列宽刷新问题")
        self.assertEqual(len(res3.get("active_build_errors", [])), 0)

    def test_unassociated_module_errors_do_not_pollute_current_context(self):
        # Initial maintenance on TestMod.m
        res = self.kernel.execute(KernelMode.DEVELOP, "排查 TestMod.m 中列宽刷新问题")
        self.assertEqual(res["status"], "ok")

        # Build fails in an unrelated module "OtherMod.m"
        mock_unrelated_failure = {
            "status": "failed",
            "duration_seconds": 3.0,
            "errors": [
                {
                    "file": "OtherMod.m/src/Other.cpp",
                    "line": 99,
                    "code": "C2143",
                    "message": "syntax error: missing ';'",
                    "module": "OtherMod.m",
                    "raw": "OtherMod.m/src/Other.cpp(99) : error C2143",
                }
            ],
        }
        attached_ctx = attach_build_result(self.workspace, mock_unrelated_failure, target_module="TestMod.m")
        self.assertIsNotNone(attached_ctx)
        # Association must be workspace_level, and NOT unresolved for TestMod.m
        self.assertEqual(attached_ctx.last_build["association"], "workspace_level")
        self.assertEqual(len(attached_ctx.unresolved_build_errors), 0)

    def test_build_hook_resilience_on_corrupted_context(self):
        # Pre-seed a corrupted context file
        from maintenance_context import get_context_path
        ctx_file = get_context_path(self.workspace, "TestMod.m")
        ctx_file.parent.mkdir(parents=True, exist_ok=True)
        ctx_file.write_text("{{corrupted json", encoding="utf-8")

        mock_failure = {
            "status": "failed",
            "errors": [{"file": "TestMod.m/src/TestCmd.cpp", "line": 1, "code": "C2065", "module": "TestMod.m"}],
        }
        # Hook must handle corrupted file gracefully and return None without throwing
        result = attach_build_result(self.workspace, mock_failure, target_module="TestMod.m")
        self.assertIsNone(result)

    def test_build_workspace_timeout_attaches_error_result(self):
        """
        P2 Requirement: When build_workspace hits TimeoutExpired, the error result
        is still attached to maintenance context without breaking the caller.
        """
        from unittest.mock import patch
        import subprocess
        from build import build_workspace

        # Pre-create maintenance context for TestMod.m
        ctx = MaintenanceContext(
            task_id="task_timeout",
            workspace=str(self.workspace),
            target_module="TestMod.m",
            original_request="Test timeout",
        )
        save_context(ctx)

        # Mock CAA environment, validation, and subprocess.run to raise TimeoutExpired
        with patch("build.CAAEnvironment") as mock_env_cls, \
             patch("build.validate_workspace", return_value={"ok": True, "issues": [], "can_build": True}), \
             patch("build.setup_prerequisite_path", return_value={"status": "success"}), \
             patch("build.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="mkmk", timeout=10)):
            mock_env = mock_env_cls.return_value
            mock_env.load_config.return_value = True
            mock_env.build_time_command.return_value = (["cmd", "/c"], "cmd /c")

            res = build_workspace(self.workspace, timeout=10, target_module="TestMod.m")
            self.assertEqual(res["status"], "error")
            self.assertIn("timeout", res["message"].lower())

            # Verify context recorded the timeout attempt
            reloaded = load_context(self.workspace, "TestMod.m")
            self.assertIsNotNone(reloaded)
            self.assertEqual(len(reloaded.build_results), 1)
            self.assertEqual(reloaded.last_build["status"], "error")

    def test_build_workspace_exception_attaches_error_result(self):
        """
        P2 Requirement: When build_workspace encounters an unexpected Exception during execution,
        it also attempts context attachment and returns structured error.
        """
        from unittest.mock import patch
        from build import build_workspace

        ctx = MaintenanceContext(
            task_id="task_exc",
            workspace=str(self.workspace),
            target_module="TestMod.m",
            original_request="Test exception",
        )
        save_context(ctx)

        with patch("build.CAAEnvironment") as mock_env_cls, \
             patch("build.validate_workspace", return_value={"ok": True, "issues": [], "can_build": True}), \
             patch("build.setup_prerequisite_path", return_value={"status": "success"}), \
             patch("build.subprocess.run", side_effect=RuntimeError("Simulated build crash")):
            mock_env = mock_env_cls.return_value
            mock_env.load_config.return_value = True
            mock_env.build_time_command.return_value = (["cmd", "/c"], "cmd /c")

            res = build_workspace(self.workspace, target_module="TestMod.m")
            self.assertEqual(res["status"], "error")
            self.assertIn("Simulated build crash", res["message"])

            # Verify context recorded the error attempt
            reloaded = load_context(self.workspace, "TestMod.m")
            self.assertIsNotNone(reloaded)
            self.assertEqual(len(reloaded.build_results), 1)
            self.assertEqual(reloaded.last_build["status"], "error")

    def test_multi_module_failure_without_target_refuses_active_pollution(self):
        """
        P0 Requirement: When active.json points to Mod1.m, an untargeted build
        with ambiguous multi-module errors must NOT write into Mod1.m's context.
        """
        # Active context for Mod1.m
        ctx1 = MaintenanceContext(
            task_id="task_mod1",
            workspace=str(self.workspace),
            target_module="Mod1.m",
            original_request="Fix Mod1",
        )
        save_context(ctx1)

        # Ambiguous build errors spanning both Mod2 and Mod3
        ambiguous_errors = {
            "status": "failed",
            "errors": [
                {"file": "Mod2.m/src/Mod2.cpp", "line": 10, "code": "C2065", "module": "Mod2.m"},
                {"file": "Mod3.m/src/Mod3.cpp", "line": 20, "code": "C2065", "module": "Mod3.m"},
            ],
        }
        res = attach_build_result(self.workspace, ambiguous_errors, target_module=None)
        self.assertIsNone(res)

        # Confirm Mod1.m context remains pristine (0 build results)
        reloaded1 = load_context(self.workspace, "Mod1.m")
        self.assertEqual(len(reloaded1.build_results), 0)


if __name__ == "__main__":
    unittest.main()
