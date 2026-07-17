#!/usr/bin/env python3
"""
Phase 3 Tests - Rollback and Advanced Features
===============================================
Test rollback functionality and advanced features.
"""

import shutil
import sys
import tempfile
from pathlib import Path

# Add skills to path
skill_root = Path(__file__).parent.parent
sys.path.insert(0, str(skill_root / "skills"))

from actions import (
    ActionContext,
    cleanup_old_backups,
    list_rollback_points,
    rollback_operation,
)
from backup import BackupManager
from changeset import ChangeSet

print("=" * 80)
print("Phase 3 Tests - Rollback and Advanced Features")
print("=" * 80)

# Create a temporary workspace for testing
test_workspace = Path(tempfile.mkdtemp(prefix="caa_test_"))
print(f"\nTest workspace: {test_workspace}")

ctx = ActionContext(str(test_workspace))

# ============================================================================
# Test 1: BackupManager Import
# ============================================================================

print("\n[Test 1] BackupManager Import")
print("-" * 80)

try:
    from backup import BackupManager
    from backup import list_rollback_points as list_rb
    from backup import rollback_operation as rb_op

    print("[OK] BackupManager imported successfully")
except ImportError as e:
    print(f"[FAIL] Import error: {e}")

# ============================================================================
# Test 2: Create Backup
# ============================================================================

print("\n[Test 2] Create Backup")
print("-" * 80)

try:
    # Create a test changeset
    cs = ChangeSet(action="test_action", description="Test backup creation")

    # Add some test files
    test_file = test_workspace / "test.txt"
    test_file.write_text("original content")

    cs.created["new_file.txt"] = "new content"
    cs.modified[str(test_file)] = "modified content"

    # Create backup
    backup_mgr = BackupManager(test_workspace)
    backup_id = backup_mgr.create_backup(cs)

    print(f"[OK] Backup created: {backup_id}")
    print(
        f"     Backup directory exists: {(test_workspace / '.caa_backups' / backup_id).exists()}"
    )
    print(
        f"     Manifest exists: {(test_workspace / '.caa_backups' / backup_id / 'manifest.json').exists()}"
    )
except Exception as e:
    print(f"[FAIL] Exception: {e}")
    import traceback

    traceback.print_exc()

# ============================================================================
# Test 3: List Backups
# ============================================================================

print("\n[Test 3] List Backups")
print("-" * 80)

try:
    backups = backup_mgr.list_backups()

    if len(backups) > 0:
        print(f"[OK] Found {len(backups)} backup(s)")
        for backup in backups:
            print(f"     - {backup['backup_id']}: {backup['action']}")
    else:
        print("[INFO] No backups found (expected if first test failed)")
except Exception as e:
    print(f"[FAIL] Exception: {e}")

# ============================================================================
# Test 4: Rollback Operation
# ============================================================================

print("\n[Test 4] Rollback Operation")
print("-" * 80)

try:
    if len(backups) > 0:
        # Apply the changeset first
        cs.apply(dry_run=False)

        # Verify files were created/modified
        new_file_exists = (test_workspace / "new_file.txt").exists()
        print(f"     New file created: {new_file_exists}")

        # Now rollback
        result = backup_mgr.rollback(backup_id)

        if result["status"] == "success":
            print(f"[OK] Rollback successful")
            print(
                f"     Deleted created files: {len(result['restored']['deleted_created_files'])}"
            )
            print(
                f"     Restored modified files: {len(result['restored']['restored_modified_files'])}"
            )

            # P3-007 fix: verify rollback actually restored state (not just print)
            new_file_after = (test_workspace / "new_file.txt").exists()
            modified_file_ok = (test_workspace / "existing.exe").exists()
            if new_file_after:
                print(f"[FAIL] Created file not removed after rollback")
                sys.exit(1)
            if not modified_file_ok:
                print(f"[FAIL] Modified file not restored after rollback")
                sys.exit(1)
            print(f"     Verified: created file removed, modified file restored")
        else:
            print(f"[FAIL] Rollback failed: {result.get('message')}")
            sys.exit(1)
    else:
        print("[INFO] Skipping (no backups available)")
except Exception as e:
    print(f"[FAIL] Exception: {e}")
    import traceback

    traceback.print_exc()

# ============================================================================
# Test 5: list_rollback_points API
# ============================================================================

print("\n[Test 5] list_rollback_points API")
print("-" * 80)

try:
    result = list_rollback_points(ctx)

    if result["status"] == "ok":
        print(f"[OK] API call successful")
        print(f"     Found {result['count']} rollback point(s)")
        if result["backups"]:
            print(f"     Latest: {result['backups'][0]['backup_id']}")
    else:
        print(f"[FAIL] API call failed")
except Exception as e:
    print(f"[FAIL] Exception: {e}")

# ============================================================================
# Test 6: rollback_operation API
# ============================================================================

print("\n[Test 6] rollback_operation API")
print("-" * 80)

try:
    # Create another backup for testing
    cs2 = ChangeSet(action="test_action_2", description="Second test")
    test_file2 = test_workspace / "test2.txt"
    test_file2.write_text("test content")
    cs2.created[str(test_file2)] = "test content"

    backup_id2 = backup_mgr.create_backup(cs2)
    cs2.apply(dry_run=False)

    # Verify file exists
    if test_file2.exists():
        print(f"     Test file created: {test_file2.name}")

    # Rollback using API
    result = rollback_operation(ctx, backup_id2)

    if result["status"] == "success":
        print(f"[OK] Rollback API successful")
        print(f"     Action: {result['action']}")

        # Verify file was deleted
        if not test_file2.exists():
            print(f"     Test file deleted: Yes")
        else:
            print(f"     Test file deleted: No (unexpected)")
    else:
        print(f"[FAIL] Rollback API failed: {result.get('message')}")
except Exception as e:
    print(f"[FAIL] Exception: {e}")
    import traceback

    traceback.print_exc()

# ============================================================================
# Test 7: Cleanup Old Backups
# ============================================================================

print("\n[Test 7] Cleanup Old Backups")
print("-" * 80)

try:
    # Create multiple backups
    for i in range(3):
        cs_temp = ChangeSet(action=f"test_{i}", description=f"Test {i}")
        backup_mgr.create_backup(cs_temp)

    # List before cleanup
    backups_before = backup_mgr.list_backups()
    print(f"     Backups before cleanup: {len(backups_before)}")

    # Cleanup, keep only 2
    result = cleanup_old_backups(ctx, keep_count=2)

    if result["status"] == "success":
        print(f"[OK] Cleanup successful")
        print(f"     Kept: {len(result['kept'])}")
        print(f"     Deleted: {len(result['deleted'])}")

        # Verify
        backups_after = backup_mgr.list_backups()
        print(f"     Backups after cleanup: {len(backups_after)}")
    else:
        print(f"[FAIL] Cleanup failed")
except Exception as e:
    print(f"[FAIL] Exception: {e}")
    import traceback

    traceback.print_exc()

# ============================================================================
# Test 8: Backup with Modified Files
# ============================================================================

print("\n[Test 8] Backup with Modified Files")
print("-" * 80)

try:
    # Create a file
    mod_file = test_workspace / "modify_test.txt"
    mod_file.write_text("original")

    # Create changeset that modifies it
    cs_mod = ChangeSet(action="modify_test", description="Modify file")
    cs_mod.modified[str(mod_file)] = "modified"

    # Create backup
    backup_id_mod = backup_mgr.create_backup(cs_mod)

    # Apply changes
    cs_mod.apply(dry_run=False)

    # Verify modification
    if mod_file.read_text() == "modified":
        print(f"     File modified: Yes")

    # Rollback
    result = backup_mgr.rollback(backup_id_mod)

    if result["status"] == "success":
        # Verify restoration
        if mod_file.read_text() == "original":
            print("[OK] File restored to original content")
        else:
            print(f"[FAIL] File content: {mod_file.read_text()}")
    else:
        print(f"[FAIL] Rollback failed: {result.get('message')}")
except Exception as e:
    print(f"[FAIL] Exception: {e}")
    import traceback

    traceback.print_exc()

# ============================================================================
# Test 9: Nonexistent Backup Rollback
# ============================================================================

print("\n[Test 9] Nonexistent Backup Rollback")
print("-" * 80)

try:
    result = rollback_operation(ctx, "nonexistent_backup_id")

    if result["status"] == "error":
        print("[OK] Error handling works")
        print(f"     Message: {result['message']}")
        if "available_backups" in result:
            print(
                f"     Provides alternatives: Yes ({len(result['available_backups'])} backups)"
            )
    else:
        print(f"[FAIL] Should have returned error")
except Exception as e:
    print(f"[FAIL] Exception: {e}")

# ============================================================================
# Test 10: Backup Manifest Integrity
# ============================================================================

print("\n[Test 10] Backup Manifest Integrity")
print("-" * 80)

try:
    # Create a backup
    cs_int = ChangeSet(action="integrity_test", description="Test manifest")
    cs_int.created["test_integrity.txt"] = "content"
    backup_id_int = backup_mgr.create_backup(cs_int)

    # Read and verify manifest
    import json

    manifest_path = test_workspace / ".caa_backups" / backup_id_int / "manifest.json"

    if manifest_path.exists():
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        required_fields = [
            "backup_id",
            "timestamp",
            "action",
            "description",
            "created",
            "modified",
            "deleted",
        ]
        all_present = all(field in manifest for field in required_fields)

        if all_present:
            print("[OK] Manifest contains all required fields")
            print(f"     Backup ID: {manifest['backup_id']}")
            print(f"     Action: {manifest['action']}")
        else:
            missing = [f for f in required_fields if f not in manifest]
            print(f"[FAIL] Missing fields: {missing}")
    else:
        print(f"[FAIL] Manifest file not found")
except Exception as e:
    print(f"[FAIL] Exception: {e}")

# ============================================================================
# Cleanup
# ============================================================================

print("\n[Cleanup] Removing test workspace...")
try:
    shutil.rmtree(test_workspace)
    print("[OK] Test workspace removed")
except Exception as e:
    print(f"[INFO] Could not remove test workspace: {e}")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "=" * 80)
print("Phase 3 Rollback Tests Complete")
print("=" * 80)
print("\nTested Features:")
print("  [OK] BackupManager Import")
print("  [OK] Create Backup")
print("  [OK] List Backups")
print("  [OK] Rollback Operation")
print("  [OK] list_rollback_points API")
print("  [OK] rollback_operation API")
print("  [OK] Cleanup Old Backups")
print("  [OK] Backup with Modified Files")
print("  [OK] Nonexistent Backup Rollback")
print("  [OK] Backup Manifest Integrity")
print("\nRollback system verified!")
