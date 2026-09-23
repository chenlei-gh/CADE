"""
Unit tests for CADE Change Provenance Guard (P3-B)
===================================================
Covers pure-function comparator, path normalization, asset filtering,
pre-existing dirty isolation, ChangeSet extraction, and serialization.
"""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent / "skills"))

from provenance_guard import (
    AssetCategoryConfig,
    ExpectedChange,
    ProvenanceAuditState,
    ProvenanceResult,
    ProvenanceStatus,
    WorkingTreeState,
    build_audit_summary,
    capture_source_snapshot,
    capture_source_snapshot_detailed,
    compute_change_provenance,
    compute_file_sha256,
    extract_expected_changes_from_changeset,
    is_controlled_source_asset,
    normalize_rel_posix_path,
    validate_provenance_inputs,
)
from changeset import ChangeSet, Patch


class TestProvenanceGuard(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    # ── 1. Path Normalization ────────────────────────────────────────

    def test_normalize_rel_posix_path(self):
        ws = self.workspace
        # Absolute path inside workspace
        abs_p = ws / "MyFramework.edu" / "MyModule.m" / "src" / "Foo.cpp"
        self.assertEqual(
            normalize_rel_posix_path(abs_p, ws),
            "MyFramework.edu/MyModule.m/src/Foo.cpp",
        )

        # Relative path with backslashes
        rel_win = "MyFramework.edu\\MyModule.m\\src\\Bar.cpp"
        self.assertEqual(
            normalize_rel_posix_path(rel_win, ws),
            "MyFramework.edu/MyModule.m/src/Bar.cpp",
        )

        # Relative path with ./
        rel_dot = "./MyFramework.edu/MyModule.m/Imakefile.mk"
        self.assertEqual(
            normalize_rel_posix_path(rel_dot, ws),
            "MyFramework.edu/MyModule.m/Imakefile.mk",
        )

    # ── 2. Asset Categorization & Filtering ──────────────────────────

    def test_asset_categorization_controlled_vs_excluded(self):
        ws = self.workspace

        # Controlled assets
        self.assertTrue(
            is_controlled_source_asset(
                ws / "CAABOM.edu" / "CAABOMCmd.m" / "src" / "Main.cpp", ws
            )
        )
        self.assertTrue(
            is_controlled_source_asset(
                ws / "CAABOM.edu" / "CAABOMCmd.m" / "LocalInterfaces" / "Main.h",
                ws,
            )
        )
        self.assertTrue(
            is_controlled_source_asset(
                ws / "CAABOM.edu" / "CAABOMCmd.m" / "Imakefile.mk", ws
            )
        )
        self.assertTrue(
            is_controlled_source_asset(
                ws / "CAABOM.edu" / "IdentityCard" / "IdentityCard.xml", ws
            )
        )
        self.assertTrue(
            is_controlled_source_asset(
                ws / "CAABOM.edu" / "CNext" / "code" / "dictionary" / "CAABOM.dico",
                ws,
            )
        )
        self.assertTrue(
            is_controlled_source_asset(
                ws / "CAABOM.edu" / "CNext" / "resources" / "msgcatalog" / "CAABOM.CATNls",
                ws,
            )
        )

        # Excluded assets: build outputs in win_b64
        self.assertFalse(
            is_controlled_source_asset(
                ws / "win_b64" / "code" / "bin" / "CAABOMCmd.dll", ws
            )
        )
        self.assertFalse(
            is_controlled_source_asset(
                ws / "win_b64" / "resources" / "msgcatalog" / "CAABOM.CATNls", ws
            )
        )
        self.assertFalse(
            is_controlled_source_asset(
                ws / "CAABOM.edu" / "CAABOMCmd.m" / "win_b64" / "Foo.obj", ws
            )
        )

        # Excluded metadata & temp files
        self.assertFalse(
            is_controlled_source_asset(ws / ".git" / "HEAD", ws)
        )
        self.assertFalse(
            is_controlled_source_asset(
                ws / ".cade" / "maintenance" / "CAABOMCmd.json", ws
            )
        )
        self.assertFalse(
            is_controlled_source_asset(ws / "build.log", ws)
        )
        self.assertFalse(
            is_controlled_source_asset(
                ws / "CAABOM.edu" / "CAABOMCmd.m" / "src" / "Main.cpp.bak", ws
            )
        )

    # ── 3. Snapshot Capture & File Hashing ───────────────────────────

    def test_capture_source_snapshot_on_disk(self):
        ws = self.workspace

        # Create a controlled source file with CRLF
        src_dir = ws / "Fw.edu" / "Mod.m" / "src"
        src_dir.mkdir(parents=True)
        src_file = src_dir / "Test.cpp"
        src_file.write_bytes(b"int main() {\r\n    return 0;\r\n}\r\n")

        # Create an excluded win_b64 file
        bin_dir = ws / "win_b64" / "code" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "output.dll").write_bytes(b"BINARY")

        # Create a build log
        (ws / "build.log").write_text("build completed")

        snapshot = capture_source_snapshot(ws)

        self.assertIn("Fw.edu/Mod.m/src/Test.cpp", snapshot)
        self.assertNotIn("win_b64/code/bin/output.dll", snapshot)
        self.assertNotIn("build.log", snapshot)

        # Verify hash matches compute_file_sha256 directly
        expected_sha = compute_file_sha256(src_file)
        self.assertEqual(snapshot["Fw.edu/Mod.m/src/Test.cpp"], expected_sha)

    # ── 4. Pure Comparator: Clean / No Changes ───────────────────────

    def test_provenance_clean_no_changes(self):
        baseline = {"Fw.edu/Mod.m/src/Foo.cpp": "hash1"}
        current = {"Fw.edu/Mod.m/src/Foo.cpp": "hash1"}
        expected = []

        result = compute_change_provenance(baseline, current, expected)
        self.assertEqual(result.working_tree_state, WorkingTreeState.CLEAN)
        self.assertEqual(result.provenance_status, ProvenanceStatus.CLEAN_NO_CHANGES)
        self.assertEqual(len(result.actual_changes), 0)
        self.assertEqual(len(result.untracked_changes), 0)

    # ── 5. Pure Comparator: Fully Verified Provenance ────────────────

    def test_provenance_verified_create_modify_delete(self):
        baseline = {
            "Fw.edu/Mod.m/src/Keep.cpp": "hash_keep",
            "Fw.edu/Mod.m/src/Old.cpp": "hash_old",
            "Fw.edu/Mod.m/src/Modify.cpp": "hash_mod_v1",
        }
        current = {
            "Fw.edu/Mod.m/src/Keep.cpp": "hash_keep",
            "Fw.edu/Mod.m/src/Modify.cpp": "hash_mod_v2",
            "Fw.edu/Mod.m/src/New.cpp": "hash_new",
        }

        expected = [
            ExpectedChange("Fw.edu/Mod.m/src/New.cpp", "create", "hash_new"),
            ExpectedChange("Fw.edu/Mod.m/src/Modify.cpp", "modify", "hash_mod_v2"),
            ExpectedChange("Fw.edu/Mod.m/src/Old.cpp", "delete"),
        ]

        result = compute_change_provenance(baseline, current, expected)
        self.assertEqual(result.working_tree_state, WorkingTreeState.DIRTY)
        self.assertEqual(result.provenance_status, ProvenanceStatus.PROVENANCE_VERIFIED)
        self.assertEqual(
            set(result.matched_changes),
            {
                "Fw.edu/Mod.m/src/New.cpp",
                "Fw.edu/Mod.m/src/Modify.cpp",
                "Fw.edu/Mod.m/src/Old.cpp",
            },
        )
        self.assertEqual(len(result.untracked_changes), 0)
        self.assertEqual(len(result.missing_expected_changes), 0)

    # ── 6. Pure Comparator: Untracked External Modification ──────────

    def test_provenance_untracked_external_tampering(self):
        # Scenario: CADE expected to modify A.cpp, but external agent also modified B.cpp
        baseline = {
            "Fw.edu/Mod.m/src/A.cpp": "hash_a1",
            "Fw.edu/Mod.m/src/B.cpp": "hash_b1",
        }
        current = {
            "Fw.edu/Mod.m/src/A.cpp": "hash_a2",
            "Fw.edu/Mod.m/src/B.cpp": "hash_b2",  # external modification!
        }
        expected = [
            ExpectedChange("Fw.edu/Mod.m/src/A.cpp", "modify", "hash_a2")
        ]

        result = compute_change_provenance(baseline, current, expected)
        self.assertEqual(result.working_tree_state, WorkingTreeState.DIRTY)
        self.assertEqual(result.provenance_status, ProvenanceStatus.UNTRACKED_EXTERNAL)
        self.assertIn("Fw.edu/Mod.m/src/A.cpp", result.matched_changes)
        self.assertIn("Fw.edu/Mod.m/src/B.cpp", result.untracked_changes)

    # ── 7. Pure Comparator: Conflict / Expected Change Missing ───────

    def test_provenance_conflict_missing_expected(self):
        baseline = {"Fw.edu/Mod.m/src/A.cpp": "hash_a1"}
        current = {"Fw.edu/Mod.m/src/A.cpp": "hash_a1"}  # Did not change
        expected = [
            ExpectedChange("Fw.edu/Mod.m/src/A.cpp", "modify", "hash_a2")
        ]

        result = compute_change_provenance(baseline, current, expected)
        self.assertEqual(result.provenance_status, ProvenanceStatus.CONFLICT)
        self.assertIn("Fw.edu/Mod.m/src/A.cpp", result.missing_expected_changes)

    # ── 8. Pure Comparator: Conflict / Content Hash Mismatch ─────────

    def test_provenance_conflict_content_hash_mismatch(self):
        baseline = {"Fw.edu/Mod.m/src/A.cpp": "hash_a1"}
        current = {"Fw.edu/Mod.m/src/A.cpp": "hash_tampered"}
        expected = [
            ExpectedChange("Fw.edu/Mod.m/src/A.cpp", "modify", "hash_expected")
        ]

        result = compute_change_provenance(baseline, current, expected)
        self.assertEqual(result.provenance_status, ProvenanceStatus.CONFLICT)
        self.assertEqual(len(result.content_mismatches), 1)
        self.assertEqual(
            result.content_mismatches[0]["path"], "Fw.edu/Mod.m/src/A.cpp"
        )
        self.assertEqual(
            result.content_mismatches[0]["expected_sha256"], "hash_expected"
        )
        self.assertEqual(
            result.content_mismatches[0]["actual_sha256"], "hash_tampered"
        )

    # ── 9. Pre-existing Dirty Scenarios ──────────────────────────────

    def test_pre_existing_dirty_unmodified_during_task(self):
        # File was dirty BEFORE task, but was NOT touched during task
        baseline = {
            "Fw.edu/Mod.m/src/PreDirty.cpp": "hash_predirty",
            "Fw.edu/Mod.m/src/Active.cpp": "hash_act1",
        }
        current = {
            "Fw.edu/Mod.m/src/PreDirty.cpp": "hash_predirty",  # Unchanged during task
            "Fw.edu/Mod.m/src/Active.cpp": "hash_act2",
        }
        expected = [
            ExpectedChange("Fw.edu/Mod.m/src/Active.cpp", "modify", "hash_act2")
        ]
        pre_existing = ["Fw.edu/Mod.m/src/PreDirty.cpp"]

        result = compute_change_provenance(
            baseline, current, expected, pre_existing_dirty=pre_existing
        )
        # Provenance is VERIFIED for this task's changes
        self.assertEqual(result.provenance_status, ProvenanceStatus.PROVENANCE_VERIFIED)
        self.assertIn("Fw.edu/Mod.m/src/PreDirty.cpp", result.pre_existing_dirty)
        self.assertEqual(len(result.pre_existing_modified_externally), 0)
        # Warning recorded for traceability
        self.assertTrue(
            any("PreDirty.cpp" in w for w in result.warnings)
        )

    def test_pre_existing_dirty_modified_further_externally(self):
        # File was dirty before task, AND was modified AGAIN without expectation
        baseline = {
            "Fw.edu/Mod.m/src/PreDirty.cpp": "hash_predirty_v1",
            "Fw.edu/Mod.m/src/Active.cpp": "hash_act1",
        }
        current = {
            "Fw.edu/Mod.m/src/PreDirty.cpp": "hash_predirty_v2",  # Changed externally!
            "Fw.edu/Mod.m/src/Active.cpp": "hash_act2",
        }
        expected = [
            ExpectedChange("Fw.edu/Mod.m/src/Active.cpp", "modify", "hash_act2")
        ]
        pre_existing = ["Fw.edu/Mod.m/src/PreDirty.cpp"]

        result = compute_change_provenance(
            baseline, current, expected, pre_existing_dirty=pre_existing
        )
        self.assertEqual(result.provenance_status, ProvenanceStatus.UNTRACKED_EXTERNAL)
        self.assertIn(
            "Fw.edu/Mod.m/src/PreDirty.cpp",
            result.pre_existing_modified_externally,
        )

    def test_pre_existing_dirty_addressed_in_expected_changes(self):
        # File was dirty before task, and CADE's task explicitly expected to fix it
        baseline = {"Fw.edu/Mod.m/src/PreDirty.cpp": "hash_predirty_v1"}
        current = {"Fw.edu/Mod.m/src/PreDirty.cpp": "hash_fixed"}
        expected = [
            ExpectedChange(
                "Fw.edu/Mod.m/src/PreDirty.cpp", "modify", "hash_fixed"
            )
        ]
        pre_existing = ["Fw.edu/Mod.m/src/PreDirty.cpp"]

        result = compute_change_provenance(
            baseline, current, expected, pre_existing_dirty=pre_existing
        )
        self.assertEqual(result.provenance_status, ProvenanceStatus.PROVENANCE_VERIFIED)
        self.assertEqual(len(result.pre_existing_modified_externally), 0)

    # ── 10. Extract Expected Changes from ChangeSet ──────────────────

    def test_extract_expected_changes_from_changeset(self):
        ws = self.workspace
        cs = ChangeSet(action="fix_issue", description="test action")
        cs.add_create(ws / "Fw.edu" / "Mod.m" / "src" / "New.cpp", "content")
        cs.add_modify(ws / "Fw.edu" / "Mod.m" / "src" / "Edit.cpp", "content2")
        cs.add_delete(ws / "Fw.edu" / "Mod.m" / "src" / "Del.cpp")
        cs.add_patch(
            Patch(
                file=ws / "Fw.edu" / "Mod.m" / "src" / "Patch.cpp",
                operation="replace",
                target="foo",
                content="bar",
            )
        )

        post_hashes = {
            "Fw.edu/Mod.m/src/New.cpp": "hash_new",
            "Fw.edu/Mod.m/src/Edit.cpp": "hash_edit",
            "Fw.edu/Mod.m/src/Patch.cpp": "hash_patch",
        }

        expected = extract_expected_changes_from_changeset(
            cs, ws, post_apply_hashes=post_hashes
        )
        self.assertEqual(len(expected), 4)

        by_path = {exp.path: exp for exp in expected}
        self.assertEqual(by_path["Fw.edu/Mod.m/src/New.cpp"].op_type, "create")
        self.assertEqual(
            by_path["Fw.edu/Mod.m/src/New.cpp"].expected_sha256, "hash_new"
        )
        self.assertEqual(by_path["Fw.edu/Mod.m/src/Edit.cpp"].op_type, "modify")
        self.assertEqual(
            by_path["Fw.edu/Mod.m/src/Patch.cpp"].op_type, "patch"
        )
        self.assertEqual(by_path["Fw.edu/Mod.m/src/Del.cpp"].op_type, "delete")
        self.assertIsNone(by_path["Fw.edu/Mod.m/src/Del.cpp"].expected_sha256)

    # ── 11. Serialization & Round-Trip ───────────────────────────────

    def test_provenance_result_json_serialization(self):
        res = ProvenanceResult(
            working_tree_state=WorkingTreeState.DIRTY,
            provenance_status=ProvenanceStatus.PROVENANCE_VERIFIED,
            expected_changes=[{"path": "a.cpp", "op_type": "modify"}],
            actual_changes={"a.cpp": "modified"},
            matched_changes=["a.cpp"],
            warnings=["test warning"],
        )
        d = res.to_dict()
        # Verify JSON serializability
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        # Round-trip reconstruction
        reconstructed = ProvenanceResult.from_dict(parsed)
        self.assertEqual(reconstructed.working_tree_state, res.working_tree_state)
        self.assertEqual(reconstructed.provenance_status, res.provenance_status)
        self.assertEqual(reconstructed.matched_changes, res.matched_changes)
        self.assertEqual(reconstructed.warnings, res.warnings)

    # ── 12. Rename as Delete + Create ────────────────────────────────

    def test_rename_as_delete_and_create(self):
        baseline = {"Fw.edu/Mod.m/src/OldName.cpp": "hash_old"}
        current = {"Fw.edu/Mod.m/src/NewName.cpp": "hash_new"}
        expected = [
            ExpectedChange("Fw.edu/Mod.m/src/OldName.cpp", "delete"),
            ExpectedChange("Fw.edu/Mod.m/src/NewName.cpp", "create", "hash_new"),
        ]

        result = compute_change_provenance(baseline, current, expected)
        self.assertEqual(result.provenance_status, ProvenanceStatus.PROVENANCE_VERIFIED)
        self.assertEqual(
            set(result.matched_changes),
            {"Fw.edu/Mod.m/src/OldName.cpp", "Fw.edu/Mod.m/src/NewName.cpp"},
        )
        self.assertEqual(len(result.untracked_changes), 0)

    # ── 13. Multiple Patches on Same File Consolidate ────────────────

    def test_multiple_patches_same_file_consolidation(self):
        ws = self.workspace
        cs = ChangeSet(action="multi_patch", description="multiple patches")
        cs.add_patch(
            Patch(
                file=ws / "Fw.edu" / "Mod.m" / "src" / "Target.cpp",
                operation="insert_after",
                target="mark1",
                content="line1",
            )
        )
        cs.add_patch(
            Patch(
                file=ws / "Fw.edu" / "Mod.m" / "src" / "Target.cpp",
                operation="replace",
                target="mark2",
                content="line2",
            )
        )

        post_hashes = {"Fw.edu/Mod.m/src/Target.cpp": "final_disk_hash"}
        expected = extract_expected_changes_from_changeset(
            cs, ws, post_apply_hashes=post_hashes
        )
        # Should consolidate to exactly 1 ExpectedChange
        self.assertEqual(len(expected), 1)
        self.assertEqual(expected[0].path, "Fw.edu/Mod.m/src/Target.cpp")
        self.assertEqual(expected[0].op_type, "patch")
        self.assertEqual(expected[0].expected_sha256, "final_disk_hash")

    # ── 14. Create then Modify Same Path Consolidate ─────────────────

    def test_create_then_modify_same_path_consolidation(self):
        ws = self.workspace
        cs = ChangeSet(action="composite", description="create then modify")
        cs.add_create(ws / "Fw.edu" / "Mod.m" / "src" / "Gen.cpp", "initial")
        cs.add_modify(ws / "Fw.edu" / "Mod.m" / "src" / "Gen.cpp", "modified")

        post_hashes = {"Fw.edu/Mod.m/src/Gen.cpp": "final_gen_hash"}
        expected = extract_expected_changes_from_changeset(
            cs, ws, post_apply_hashes=post_hashes
        )
        # Net effect relative to baseline is create
        self.assertEqual(len(expected), 1)
        self.assertEqual(expected[0].path, "Fw.edu/Mod.m/src/Gen.cpp")
        self.assertEqual(expected[0].op_type, "create")
        self.assertEqual(expected[0].expected_sha256, "final_gen_hash")

    # ── 15. Binary and Non-UTF8 Files Safe Hashing ───────────────────

    def test_binary_and_non_utf8_files(self):
        ws = self.workspace
        cat_dir = ws / "Fw.edu" / "CNext" / "resources" / "msgcatalog" / "Simplified_Chinese"
        cat_dir.mkdir(parents=True)
        # Write GBK encoded Simplified Chinese text
        cat_file = cat_dir / "Test.CATNls"
        gbk_bytes = "提示信息=测试成功\r\n".encode("gbk")
        cat_file.write_bytes(gbk_bytes)

        # Write binary file with null and non-ASCII bytes
        bin_file = ws / "Fw.edu" / "CNext" / "resources" / "Test.CATRsc"
        bin_bytes = b"\x00\xff\xfe\x01\x02\x03\r\n"
        bin_file.write_bytes(bin_bytes)

        # Binary sha256 should compute without UnicodeDecodeError
        sha_gbk = compute_file_sha256(cat_file)
        sha_bin = compute_file_sha256(bin_file)
        self.assertEqual(len(sha_gbk), 64)
        self.assertEqual(len(sha_bin), 64)

        snapshot = capture_source_snapshot(ws)
        self.assertIn(
            "Fw.edu/CNext/resources/msgcatalog/Simplified_Chinese/Test.CATNls",
            snapshot,
        )
        self.assertIn("Fw.edu/CNext/resources/Test.CATRsc", snapshot)

    # ── 16. Outside Workspace & Path Traversal Rejection ─────────────

    def test_outside_workspace_and_path_traversal(self):
        ws = self.workspace

        # Attempt path traversal escaping workspace_root
        with self.assertRaises(ValueError):
            normalize_rel_posix_path("../../outside.cpp", ws, strict=True)

        with self.assertRaises(ValueError):
            normalize_rel_posix_path(
                ws / "Fw.edu" / ".." / ".." / "outside.cpp", ws, strict=True
            )

        # Non-strict mode does not raise
        non_strict = normalize_rel_posix_path(
            "../../outside.cpp", ws, strict=False
        )
        self.assertTrue(len(non_strict) > 0)

    # ── 17. Internal Path Traversal Normalization ────────────────────

    def test_path_with_internal_dotdot(self):
        ws = self.workspace
        # Internal .. that remains within workspace_root should resolve cleanly
        rel = normalize_rel_posix_path(
            "Fw.edu/Mod.m/src/../LocalInterfaces/Foo.h", ws, strict=True
        )
        self.assertEqual(rel, "Fw.edu/Mod.m/LocalInterfaces/Foo.h")

    # ── 18. Unknown Extension in Controlled Directory Ignored ────────

    def test_unknown_extension_in_controlled_dir(self):
        ws = self.workspace
        src_dir = ws / "Fw.edu" / "Mod.m" / "src"
        src_dir.mkdir(parents=True)
        # Controlled source file
        (src_dir / "Valid.cpp").write_text("int a = 1;")
        # Non-controlled auxiliary files
        (src_dir / "notes.txt").write_text("my notes")
        (src_dir / "temp_data.dat").write_bytes(b"\x01\x02")
        (src_dir / "debug.log").write_text("log line")

        snapshot = capture_source_snapshot(ws)
        self.assertIn("Fw.edu/Mod.m/src/Valid.cpp", snapshot)
        self.assertNotIn("Fw.edu/Mod.m/src/notes.txt", snapshot)
        self.assertNotIn("Fw.edu/Mod.m/src/temp_data.dat", snapshot)
        self.assertNotIn("Fw.edu/Mod.m/src/debug.log", snapshot)

    # ── 19. Deleted and Recreated File ───────────────────────────────

    def test_deleted_and_recreated_file(self):
        # A file was deleted and recreated with different content between baseline & current
        baseline = {"Fw.edu/Mod.m/src/Lifecycle.cpp": "hash_v1"}
        current = {"Fw.edu/Mod.m/src/Lifecycle.cpp": "hash_v2"}
        expected = [
            ExpectedChange(
                "Fw.edu/Mod.m/src/Lifecycle.cpp", "modify", "hash_v2"
            )
        ]

        result = compute_change_provenance(baseline, current, expected)
        self.assertEqual(result.provenance_status, ProvenanceStatus.PROVENANCE_VERIFIED)
        self.assertEqual(result.actual_changes["Fw.edu/Mod.m/src/Lifecycle.cpp"], "modified")
        self.assertIn("Fw.edu/Mod.m/src/Lifecycle.cpp", result.matched_changes)

    # ── 20. Windows Path Slashes and Case Handling ───────────────────

    def test_windows_path_case_handling(self):
        ws = self.workspace
        mixed_slash = "Fw.edu\\Mod.m/src\\Sub/File.cpp"
        norm = normalize_rel_posix_path(mixed_slash, ws)
        self.assertEqual(norm, "Fw.edu/Mod.m/src/Sub/File.cpp")
        self.assertNotIn("\\", norm)

    # ── 21. Deterministic Duplicate Expected Changes ─────────────────

    def test_deterministic_duplicate_expected_changes(self):
        baseline = {"Fw.edu/Mod.m/src/A.cpp": "hash1"}
        current = {"Fw.edu/Mod.m/src/A.cpp": "hash2"}
        # Caller supplies duplicate ExpectedChange entries for A.cpp
        expected = [
            ExpectedChange("Fw.edu/Mod.m/src/A.cpp", "modify"),
            ExpectedChange("Fw.edu/Mod.m/src/A.cpp", "modify", "hash2"),
        ]

        result = compute_change_provenance(baseline, current, expected)
        self.assertEqual(result.provenance_status, ProvenanceStatus.PROVENANCE_VERIFIED)
        self.assertEqual(len(result.matched_changes), 1)
        self.assertIn("Fw.edu/Mod.m/src/A.cpp", result.matched_changes)
        self.assertEqual(len(result.content_mismatches), 0)


    # ── 22. Detailed Snapshot Audit Stats ────────────────────────────

    def test_capture_source_snapshot_detailed_stats(self):
        ws = self.workspace
        src_dir = ws / "Fw.edu" / "Mod.m" / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "Code.cpp").write_text("void f() {}")
        (src_dir / "notes.txt").write_text("info")
        (ws / "win_b64" / "out.dll").parent.mkdir(parents=True)
        (ws / "win_b64" / "out.dll").write_bytes(b"bin")

        snapshot, stats = capture_source_snapshot_detailed(ws)
        self.assertIn("Fw.edu/Mod.m/src/Code.cpp", snapshot)
        self.assertEqual(stats.controlled_assets_count, 1)
        self.assertGreater(stats.total_files_scanned, 1)
        self.assertIn("win_b64", stats.excluded_directories)
        self.assertIn(".txt", stats.unknown_extensions)
        self.assertGreater(stats.scan_duration_ms, 0.0)

    # ── 23. Extract Expected Changes with Delete + Recreate Baseline ──

    def test_extract_expected_changes_delete_recreate_with_baseline(self):
        ws = self.workspace
        cs = ChangeSet(action="rewrite", description="delete and recreate")
        cs.add_delete(ws / "Fw.edu" / "Mod.m" / "src" / "Old.cpp")
        cs.add_create(ws / "Fw.edu" / "Mod.m" / "src" / "Old.cpp", "new_content")

        # Case A: File was present in baseline -> net modify
        base_snap = {"Fw.edu/Mod.m/src/Old.cpp": "base_hash"}
        post_hashes = {"Fw.edu/Mod.m/src/Old.cpp": "post_hash"}
        exp_mod = extract_expected_changes_from_changeset(
            cs, ws, post_apply_hashes=post_hashes, baseline_snapshot=base_snap
        )
        self.assertEqual(len(exp_mod), 1)
        self.assertEqual(exp_mod[0].path, "Fw.edu/Mod.m/src/Old.cpp")
        self.assertEqual(exp_mod[0].op_type, "modify")
        self.assertEqual(exp_mod[0].expected_sha256, "post_hash")

        # Case B: File was NOT present in baseline -> net create
        exp_create = extract_expected_changes_from_changeset(
            cs, ws, post_apply_hashes=post_hashes, baseline_snapshot={}
        )
        self.assertEqual(len(exp_create), 1)
        self.assertEqual(exp_create[0].op_type, "create")

    # ── 24. Input Validation: Missing and Invalid Types ──────────────

    def test_validate_provenance_inputs_missing_or_invalid_type(self):
        # Missing baseline or expected_changes returns False with exact reason
        ok, reason = validate_provenance_inputs(None, [])
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_baseline_or_expected_changes")

        ok, reason = validate_provenance_inputs({}, None)
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_baseline_or_expected_changes")

        # Invalid baseline type
        ok, reason = validate_provenance_inputs(["not_a_dict"], [])
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_baseline_type_not_dict")

        # Invalid expected_changes type
        ok, reason = validate_provenance_inputs({}, "not_a_list")
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_expected_changes_type_not_list")

    # ── 25. Input Validation: Path Format and SHA-256 Check ──────────

    def test_validate_provenance_inputs_path_and_hash_format(self):
        valid_sha = "a" * 64

        # Invalid baseline path (backslash, traversal, absolute)
        bad_paths = [
            ("Mod.m\\src\\foo.cpp", "invalid_baseline_path: Mod.m\\src\\foo.cpp"),
            ("/Mod.m/src/foo.cpp", "invalid_baseline_path: /Mod.m/src/foo.cpp"),
            ("../outside.cpp", "invalid_baseline_path: ../outside.cpp"),
            ("Mod.m/../outside.cpp", "invalid_baseline_path: Mod.m/../outside.cpp"),
            ("", "invalid_baseline_path: "),
        ]
        for p, _ in bad_paths:
            ok, reason = validate_provenance_inputs({p: valid_sha}, [])
            self.assertFalse(ok)
            self.assertEqual(reason, "invalid_baseline_path")

        # Invalid SHA-256 format (not 64 hex characters)
        bad_hashes = ["short", "g" * 64, "a" * 63, "a" * 65, 12345]
        for h in bad_hashes:
            ok, reason = validate_provenance_inputs({"Mod.m/src/A.cpp": h}, [])
            self.assertFalse(ok)
            self.assertEqual(reason, "invalid_baseline_sha256")

    # ── 26. Input Validation: ExpectedChanges Structure ──────────────

    def test_validate_provenance_inputs_expected_changes_structure(self):
        valid_sha = "f" * 64
        base = {"Mod.m/src/A.cpp": valid_sha}

        # Valid ExpectedChange object and dict
        valid_exp = [
            ExpectedChange("Mod.m/src/A.cpp", "modify", valid_sha),
            {"path": "Mod.m/src/B.cpp", "op_type": "create", "expected_sha256": valid_sha},
        ]
        ok, reason = validate_provenance_inputs(base, valid_exp)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

        # Invalid op_type
        bad_op = [{"path": "Mod.m/src/C.cpp", "op_type": "destroy"}]
        ok, reason = validate_provenance_inputs(base, bad_op)
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_expected_change_op")

        # Invalid path in expected_changes
        bad_path = [{"path": "../C.cpp", "op_type": "create"}]
        ok, reason = validate_provenance_inputs(base, bad_path)
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_expected_change_path")

        # Invalid pre_existing_dirty
        ok, reason = validate_provenance_inputs(base, valid_exp, pre_existing_dirty=["/abs/path"])
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_pre_existing_dirty_path")

        # Empty expected_changes is valid (explicitly declared zero modifications)
        ok_empty, reason_empty = validate_provenance_inputs(base, [])
        self.assertTrue(ok_empty)
        self.assertEqual(reason_empty, "")

    # ── 27. Build Audit Summary: NOT_EVALUATED (Zero I/O) ────────────

    def test_build_audit_summary_not_evaluated(self):
        summary = build_audit_summary(
            audit_state=ProvenanceAuditState.NOT_EVALUATED,
            reason="missing_baseline_or_expected_changes",
            warnings=["No baseline provided."],
        )
        self.assertEqual(summary["audit_state"], "NOT_EVALUATED")
        self.assertEqual(summary["reason"], "missing_baseline_or_expected_changes")
        self.assertEqual(summary["provenance_status"], "not_applicable")
        self.assertEqual(summary["working_tree_state"], "unassessed")
        self.assertEqual(summary["untracked_changes"], [])
        self.assertEqual(summary["untracked_change_count"], 0)
        self.assertEqual(summary["matched_change_count"], 0)
        self.assertIn("No baseline provided.", summary["warnings"])

        # Must be strictly JSON-serializable
        serialized = json.dumps(summary)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized["audit_state"], "NOT_EVALUATED")

    # ── 28. Build Audit Summary: EVALUATED & Serialization ───────────

    def test_build_audit_summary_evaluated(self):
        valid_sha1 = "1" * 64
        valid_sha2 = "2" * 64
        baseline = {"Mod.m/src/A.cpp": valid_sha1}
        current = {"Mod.m/src/A.cpp": valid_sha2, "Mod.m/src/Extra.cpp": valid_sha2}
        expected = [ExpectedChange("Mod.m/src/A.cpp", "modify", valid_sha2)]

        prov_result = compute_change_provenance(baseline, current, expected)
        summary = build_audit_summary(
            audit_state=ProvenanceAuditState.EVALUATED,
            reason="verification_completed",
            prov_result=prov_result,
        )

        self.assertEqual(summary["audit_state"], "EVALUATED")
        self.assertEqual(summary["provenance_status"], ProvenanceStatus.UNTRACKED_EXTERNAL)
        self.assertEqual(summary["working_tree_state"], WorkingTreeState.DIRTY)
        self.assertEqual(summary["untracked_changes"], ["Mod.m/src/Extra.cpp"])
        self.assertEqual(summary["untracked_change_count"], 1)
        self.assertEqual(summary["matched_change_count"], 1)

        # JSON round-trip stability
        round_trip = json.loads(json.dumps(summary))
        self.assertEqual(round_trip["untracked_change_count"], 1)
        self.assertEqual(round_trip["untracked_changes"], ["Mod.m/src/Extra.cpp"])

    # ── 29. Build Audit Summary: FAILED Safe Containment ─────────────

    def test_build_audit_summary_failed_safe_containment(self):
        summary = build_audit_summary(
            audit_state=ProvenanceAuditState.FAILED,
            reason="scan_permission_denied",
            error_type="PermissionError",
        )
        self.assertEqual(summary["audit_state"], "FAILED")
        self.assertEqual(summary["reason"], "scan_permission_denied")
        self.assertEqual(summary["provenance_status"], "audit_failed")
        self.assertEqual(summary["error_type"], "PermissionError")
        self.assertEqual(summary["untracked_changes"], [])
        self.assertEqual(summary["untracked_change_count"], 0)
        # Verify no raw sensitive paths leaked in error_type
        self.assertNotIn("\\", summary["error_type"])
        self.assertNotIn("/", summary["error_type"])


if __name__ == "__main__":
    unittest.main()
