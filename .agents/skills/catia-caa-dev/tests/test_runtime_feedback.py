#!/usr/bin/env python3
"""
Test Suite for CADE Human Runtime Feedback (P3-B)
=================================================
Validates CLI feedback recording, data contract segregation from L0 build errors,
and Kernel maintenance analysis consumption.
"""

import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "skills"))

from cade import cmd_feedback, _print_kernel
from kernel import Kernel, KernelMode
from maintenance_context import (
    MaintenanceContext,
    load_context,
    save_context,
    attach_build_result,
    record_runtime_feedback,
)


class TestRuntimeFeedback(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp_dir.name)

        # Setup minimal workspace with TestFw.edu/TestMod.m
        self.fw_dir = self.workspace / "TestFw.edu"
        self.mod_dir = self.fw_dir / "TestMod.m"
        self.src_dir = self.mod_dir / "src"
        self.local_int_dir = self.mod_dir / "LocalInterfaces"
        self.fw_int_dir = self.fw_dir / "ProtectedInterfaces"
        self.identity_dir = self.fw_dir / "CNext" / "code" / "dictionary"

        for d in [self.src_dir, self.local_int_dir, self.fw_int_dir, self.identity_dir]:
            d.mkdir(parents=True, exist_ok=True)

        (self.identity_dir / "TestFramework.dico").write_text("# dico\n", encoding="utf-8")

        cmd_h = "#ifndef TestCmd_H\n#define TestCmd_H\nclass TestCmd {};\n#endif\n"
        cmd_cpp = '#include "TestCmd.h"\nvoid TestCmd_Run() {}\n'
        (self.src_dir / "TestCmd.cpp").write_text(cmd_cpp, encoding="utf-8")
        (self.local_int_dir / "TestCmd.h").write_text(cmd_h, encoding="utf-8")

        imakefile_content = "BUILT_OBJECT_TYPE = SHARED LIBRARY\nLINK_WITH = JS0GROUP\n"
        (self.mod_dir / "Imakefile.mk").write_text(imakefile_content, encoding="utf-8")

        self.kernel = Kernel(workspace_root=str(self.workspace))

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_cli_feedback_recording_and_listing(self):
        """Test cade feedback CLI sub-command records and lists human observations."""
        # 1. Record via CLI
        args = [
            "TestMod.m",
            "--symptom", "表格列宽无法自适应文本",
            "--expected", "双击表头根据内容自动撑开",
            "--actual", "双击表头无响应，保持固定100px",
            "--steps", "打开对话框;点击加载数据;双击列分隔线",
            "--build-id", "b_20260920_100000_123456",
            "--workspace", str(self.workspace),
        ]
        rc = cmd_feedback(args)
        self.assertEqual(rc, 0)

        # 2. Verify context persistence
        ctx = load_context(self.workspace, "TestMod.m")
        self.assertIsNotNone(ctx)
        self.assertEqual(len(ctx.runtime_feedback), 1)
        fb = ctx.runtime_feedback[0]
        self.assertEqual(fb["symptom"], "表格列宽无法自适应文本")
        self.assertEqual(fb["expected"], "双击表头根据内容自动撑开")
        self.assertEqual(fb["actual"], "双击表头无响应，保持固定100px")
        self.assertEqual(len(fb["steps"]), 3)
        self.assertEqual(fb["build_id"], "b_20260920_100000_123456")

        # 3. List via CLI
        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output):
            list_rc = cmd_feedback(["TestMod.m", "--list", "--workspace", str(self.workspace)])
        self.assertEqual(list_rc, 0)
        output_str = captured_output.getvalue()
        self.assertIn("Recorded Runtime Feedback for TestMod.m (1 observation(s))", output_str)
        self.assertIn("表格列宽无法自适应文本", output_str)
        self.assertIn("双击表头根据内容自动撑开", output_str)

    def test_cli_feedback_validation_errors(self):
        """Test cade feedback requires target module and symptom."""
        # Missing module
        rc1 = cmd_feedback(["--symptom", "foo", "--workspace", str(self.workspace)])
        self.assertEqual(rc1, 1)

        # Missing symptom
        rc2 = cmd_feedback(["TestMod.m", "--workspace", str(self.workspace)])
        self.assertEqual(rc2, 1)

    def test_kernel_maintenance_analysis_includes_runtime_feedback_and_preserves_l0_errors(self):
        """
        End-to-End P3-B Verification:
        1. Explicit L0 build error attached.
        2. Human runtime feedback recorded.
        3. Kernel maintenance analysis returns both as strictly segregated partitions.
        """
        # Step 0: Initial maintenance analysis creates context
        init_res = self.kernel.execute(KernelMode.DEVELOP, "排查 TestMod.m 中列重绘异常")
        self.assertEqual(init_res["status"], "ok")

        # Step 1: Attach L0 build error
        raw_err = {
            "file": "TestMod.m/src/TestCmd.cpp",
            "line": 2,
            "code": "C2065",
            "message": "'m_pCol': undeclared identifier",
            "module": "TestMod.m",
        }
        attached = attach_build_result(
            self.workspace,
            {"status": "failed", "errors": [raw_err]},
            target_module="TestMod.m",
        )
        self.assertIsNotNone(attached)
        self.assertEqual(len(attached.unresolved_build_errors), 1)

        # Step 2: Record human runtime feedback
        fb_ctx = record_runtime_feedback(
            workspace_root=self.workspace,
            target_module="TestMod.m",
            symptom="CATIA 运行时崩溃在列重绘",
            expected="平滑重绘",
            actual="CATIA 窗口直接闪退",
            build_id="b_test_run",
        )
        self.assertIsNotNone(fb_ctx)

        # Step 3: Run Kernel maintenance analysis
        res = self.kernel.execute(KernelMode.DEVELOP, "排查 TestMod.m 中列重绘异常")
        self.assertEqual(res["status"], "ok")

        # Step 4: Validate strictly segregated partitions
        active_errs = res.get("active_build_errors", [])
        rt_feedback = res.get("runtime_feedback", [])

        # L0 Compiler facts
        self.assertEqual(len(active_errs), 1)
        self.assertEqual(active_errs[0]["code"], "C2065")
        self.assertEqual(active_errs[0]["level"], "L0")

        # Human observations
        self.assertEqual(len(rt_feedback), 1)
        self.assertEqual(rt_feedback[0]["symptom"], "CATIA 运行时崩溃在列重绘")
        self.assertEqual(rt_feedback[0]["actual"], "CATIA 窗口直接闪退")
        self.assertEqual(rt_feedback[0]["build_id"], "b_test_run")

        # Step 5: Test CLI renderer _print_kernel formats both without confusion
        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output):
            _print_kernel(res)
        out = captured_output.getvalue()

        self.assertIn("Active Build Errors (L0 Direct Evidence):", out)
        self.assertIn("C2065", out)
        self.assertIn("Recorded Runtime Feedback (Human Observation - Not Compiler Fact):", out)
        self.assertIn("CATIA 运行时崩溃在列重绘", out)
        self.assertIn("CATIA 窗口直接闪退", out)


if __name__ == "__main__":
    unittest.main()
