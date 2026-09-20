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
        ctx_path.parent.mkdir(parents=True, exist_ok=True)
        ctx_path.write_text("{ malformed: json, [ ", encoding="utf-8")
        corrupted = load_context(self.workspace, "CorruptedMod.m")
        self.assertIsNone(corrupted)

        # attach_build_result on missing context is a clean no-op
        res = attach_build_result(self.workspace, {"status": "success"}, "NonExistent.m")
        self.assertIsNone(res)

    def test_pure_read_has_zero_disk_side_effects(self):
        """
        P1 Requirement: Pure read operations (get_context_path, load_context)
        MUST NOT create any directories or files on disk.
        """
        cade_dir = self.workspace / ".cade"
        self.assertFalse(cade_dir.exists())

        path = get_context_path(self.workspace, "AnyModule.m")
        self.assertFalse(cade_dir.exists())
        self.assertFalse(path.exists())

        res = load_context(self.workspace, "AnyModule.m")
        self.assertIsNone(res)
        self.assertFalse(cade_dir.exists())

        # Calling without target module (fallback check) also must not create directory
        res_active = load_context(self.workspace)
        self.assertIsNone(res_active)
        self.assertFalse(cade_dir.exists())

    def test_atomic_save_context(self):
        """
        P1 Requirement: save_context uses atomic file replacement without
        leaving temporary files behind.
        """
        ctx = MaintenanceContext(
            schema_version=1,
            task_id="task_atomic",
            workspace=str(self.workspace),
            target_module="AtomicMod.m",
            original_request="Test atomic replace",
        )
        ok = save_context(ctx)
        self.assertTrue(ok)

        target_file = get_context_path(self.workspace, "AtomicMod.m")
        self.assertTrue(target_file.exists())
        # Verify no .tmp_* leftover files exist in the maintenance directory
        tmp_files = list(target_file.parent.glob(".tmp_*")) + list(target_file.parent.glob("*.tmp_*"))
        self.assertEqual(len(tmp_files), 0)

        # Verify content is valid JSON matching ctx
        reloaded = load_context(self.workspace, "AtomicMod.m")
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.task_id, "task_atomic")

        # Verify active.json singleton was NOT created
        active_file = target_file.parent / "active.json"
        self.assertFalse(active_file.exists())

    def test_workspace_level_success_does_not_clear_explicit_failures(self):
        """
        P0 Requirement: A general workspace-level success (or success from another module)
        MUST NOT wash away an explicit failure record of the module under maintenance.
        """
        ctx = MaintenanceContext(
            task_id="task_modA",
            workspace=str(self.workspace),
            target_module="ModA.m",
            original_request="Fix ModA",
        )
        save_context(ctx)

        # 1. ModA explicitly fails
        failed_build = {
            "status": "failed",
            "duration_seconds": 6.0,
            "errors": [
                {
                    "file": "ModA.m/src/ModA.cpp",
                    "line": 10,
                    "code": "C2065",
                    "message": "undeclared",
                    "module": "ModA.m",
                }
            ],
        }
        res1 = attach_build_result(self.workspace, failed_build, target_module="ModA.m")
        self.assertIsNotNone(res1)
        self.assertEqual(len(res1.unresolved_build_errors), 1)

        # 2. An unrelated build happens: ModB succeeded, or workspace-level build ran
        # with verification only confirming ModB.dll
        unrelated_success = {
            "status": "success",
            "duration_seconds": 15.0,
            "errors": [],
            "verification": {"dlls": [{"name": "ModB.dll", "status": "ok"}]},
        }
        # Manually attach or let system process: association becomes 'workspace_level' for ModA
        res1.build_results.append({
            "build_id": "b_unrelated",
            "status": "success",
            "association": "workspace_level",
            "errors": [],
        })
        save_context(res1)

        # 3. Check unresolved errors: ModA's explicit failure MUST STILL BE ACTIVE!
        reloaded = load_context(self.workspace, "ModA.m")
        self.assertEqual(len(reloaded.unresolved_build_errors), 1)
        self.assertEqual(reloaded.unresolved_build_errors[0]["code"], "C2065")

        # 4. Now an explicit successful build for ModA occurs
        modA_success = {
            "status": "success",
            "duration_seconds": 5.0,
            "errors": [],
            "verification": {"dlls": [{"name": "ModA.dll", "status": "ok"}]},
        }
        res2 = attach_build_result(self.workspace, modA_success, target_module="ModA.m")
        self.assertIsNotNone(res2)
        # Now it is explicitly resolved!
        self.assertEqual(len(res2.unresolved_build_errors), 0)

    def test_attach_build_result_refuses_blind_association_when_ambiguous(self):
        """
        P0 Requirement: If target_module is NOT passed and errors span multiple modules,
        attach_build_result must REFUSE to associate to active.json (Contract: Better unassociated
        than wrongly associated).
        """
        # Create an active context for ModA.m
        ctx_a = MaintenanceContext(
            task_id="task_a",
            workspace=str(self.workspace),
            target_module="ModA.m",
            original_request="Working on ModA",
        )
        save_context(ctx_a)

        # Ambiguous build with errors in both ModX.m and ModY.m, no explicit target_module
        ambiguous_build = {
            "status": "failed",
            "errors": [
                {"file": "ModX.m/src/X.cpp", "line": 1, "code": "C2065", "module": "ModX.m"},
                {"file": "ModY.m/src/Y.cpp", "line": 2, "code": "C2065", "module": "ModY.m"},
            ],
        }
        result = attach_build_result(self.workspace, ambiguous_build, target_module=None)
        # Must be None: refused to associate!
        self.assertIsNone(result)

        # ModA context MUST NOT be polluted
        reloaded_a = load_context(self.workspace, "ModA.m")
        self.assertEqual(len(reloaded_a.build_results), 0)

    def test_readonly_workspace_fails_cleanly_without_fake_success(self):
        """
        Audit Requirement 1: Read-only workspace failure must return False cleanly.
        Must NOT write to temp fallback directory and create fake persistence illusions.
        """
        from unittest.mock import patch
        ctx = MaintenanceContext(
            task_id="task_ro",
            workspace=str(self.workspace),
            target_module="ReadOnlyMod.m",
            original_request="Test RO",
        )
        with patch.object(Path, "mkdir", side_effect=PermissionError("Access denied")):
            ok = save_context(ctx)
            self.assertFalse(ok)

        # Confirm nothing was loaded from any phantom fallback
        reloaded = load_context(self.workspace, "ReadOnlyMod.m")
        self.assertIsNone(reloaded)

    def test_build_id_microsecond_uniqueness(self):
        """
        Audit Requirement 2: Successive rapid builds must generate unique build_ids
        with sub-second microsecond precision.
        """
        ctx = MaintenanceContext(
            task_id="task_rapid",
            workspace=str(self.workspace),
            target_module="RapidMod.m",
            original_request="Test rapid builds",
        )
        save_context(ctx)

        build_ids = set()
        for _ in range(5):
            res = attach_build_result(self.workspace, {"status": "success"}, target_module="RapidMod.m")
            self.assertIsNotNone(res)
            build_ids.add(res.last_build["build_id"])

        # All 5 rapidly generated build_ids must be strictly distinct
        self.assertEqual(len(build_ids), 5)
        for bid in build_ids:
            # Must match microsecond pattern b_YYYYMMDD_HHMMSS_ffffff
            parts = bid.split("_")
            self.assertEqual(len(parts), 4)  # ["b", "YYYYMMDD", "HHMMSS", "ffffff"]
            self.assertEqual(len(parts[3]), 6)


if __name__ == "__main__":
    unittest.main()
