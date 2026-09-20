"""
Unit tests for Maintenance Context Manager (P3-A.1)
Covers resilience, association logic, L0 error normalization, and recovery.
"""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent / "skills"))

from maintenance_context import (
    MaintenanceContext,
    StructuredError,
    BuildRecord,
    generate_task_id,
    get_context_path,
    load_context,
    save_context,
    attach_build_result,
    normalize_error,
)


class TestMaintenanceContext(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_task_id_generation_is_stable_and_informative(self):
        tid1 = generate_task_id(str(self.workspace), "CAABOMToolCmd.m", "排查列宽问题")
        tid2 = generate_task_id(str(self.workspace), "CAABOMToolCmd.m", "排查列宽问题")
        self.assertTrue(tid1.startswith("maint_CAABOMToolCmd_"))
        self.assertIn("CAABOMToolCmd", tid1)
        # Note: timestamp component changes, prefix hash is stable
        prefix1 = "_".join(tid1.split("_")[:4])
        prefix2 = "_".join(tid2.split("_")[:4])
        self.assertEqual(prefix1, prefix2)

    def test_normalize_compiler_and_linker_errors(self):
        # MSVC compiler error
        raw_c = {
            "file": "CAABomColModel.cpp",
            "line": 45,
            "code": "C2065",
            "message": "'m_colWidth': undeclared identifier",
            "module": "CAABOMToolCmd.m",
            "raw": "CAABomColModel.cpp(45) : error C2065: 'm_colWidth': undeclared identifier",
        }
        err_c = normalize_error(raw_c, target_module="CAABOMToolCmd.m")
        self.assertEqual(err_c.kind, "compiler_error")
        self.assertEqual(err_c.line, 45)
        self.assertEqual(err_c.code, "C2065")
        self.assertTrue(err_c.associated)
        self.assertEqual(err_c.level, "L0")

        # Linker error without line number
        raw_lnk = {
            "file": None,
            "line": None,
            "code": "LNK2001",
            "message": "unresolved external symbol CAABomColModel::GetColumnWidth",
            "module": "CAABOMToolCmd.m",
        }
        err_lnk = normalize_error(raw_lnk, target_module="CAABOMToolCmd.m")
        self.assertEqual(err_lnk.kind, "linker_error")
        self.assertIsNone(err_lnk.file)
        self.assertIsNone(err_lnk.line)
        self.assertEqual(err_lnk.code, "LNK2001")
        self.assertTrue(err_lnk.associated)

    def test_context_persistence_and_reload(self):
        ctx = MaintenanceContext(
            schema_version=1,
            task_id="test_task_1",
            workspace=str(self.workspace),
            target_module="CAABOMToolCmd.m",
            original_request="排查刷新异常",
            problem_description="刷新异常",
            candidate_locations=[{"file": "CAABomColModel.cpp", "line": 10}],
        )
        saved = save_context(ctx)
        self.assertTrue(saved)

        reloaded = load_context(self.workspace, "CAABOMToolCmd.m")
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.task_id, "test_task_1")
        self.assertEqual(reloaded.target_module, "CAABOMToolCmd.m")
        self.assertEqual(len(reloaded.candidate_locations), 1)

    def test_attach_build_result_and_unresolved_errors_lifecycle(self):
        # 1. Initial maintenance session
        ctx = MaintenanceContext(
            task_id="task_lifecycle",
            workspace=str(self.workspace),
            target_module="CAABOMToolCmd.m",
            original_request="排查刷新异常",
        )
        save_context(ctx)

        # 2. Build fails with an error in CAABOMToolCmd.m
        failed_build = {
            "status": "failed",
            "duration_seconds": 12.5,
            "errors": [
                {
                    "file": "CAABomColModel.cpp",
                    "line": 45,
                    "code": "C2065",
                    "message": "'m_width': undeclared identifier",
                    "module": "CAABOMToolCmd.m",
                }
            ],
        }
        res_ctx = attach_build_result(self.workspace, failed_build, target_module="CAABOMToolCmd.m")
        self.assertIsNotNone(res_ctx)
        self.assertEqual(len(res_ctx.build_results), 1)
        self.assertEqual(res_ctx.last_build["status"], "failed")
        self.assertEqual(res_ctx.last_build["association"], "explicit")
        self.assertEqual(len(res_ctx.unresolved_build_errors), 1)
        self.assertEqual(res_ctx.unresolved_build_errors[0]["code"], "C2065")

        # 3. Code is fixed and build succeeds
        successful_build = {
            "status": "success",
            "duration_seconds": 10.1,
            "errors": [],
        }
        res_ctx2 = attach_build_result(self.workspace, successful_build, target_module="CAABOMToolCmd.m")
        self.assertIsNotNone(res_ctx2)
        self.assertEqual(len(res_ctx2.build_results), 2)
        self.assertEqual(res_ctx2.last_build["status"], "success")
        # Critical verification: previous error is resolved, unresolved list is now empty!
        self.assertEqual(len(res_ctx2.unresolved_build_errors), 0)

    def test_resilience_on_corrupted_json_and_missing_files(self):
        # Missing file
        missing = load_context(self.workspace, "NonExistentModule.m")
        self.assertIsNone(missing)

        # Malformed JSON
        ctx_path = get_context_path(self.workspace, "CorruptedMod.m")
        ctx_path.write_text("{ malformed: json, [ ", encoding="utf-8")
        corrupted = load_context(self.workspace, "CorruptedMod.m")
        self.assertIsNone(corrupted)

        # attach_build_result on missing context is a clean no-op
        res = attach_build_result(self.workspace, {"status": "success"}, "NonExistent.m")
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
