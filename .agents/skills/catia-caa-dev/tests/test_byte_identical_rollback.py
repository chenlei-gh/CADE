#!/usr/bin/env python3
"""
Physical Byte-Identical Rollback & Evidence Deepening Tests
===========================================================
Strictly verifies that ChangeSet and BackupManager preserve 100% byte-for-byte
physical identical state across apply -> rollback lifecycles.

Covers:
  - UTF-8 with CRLF line endings
  - GBK encoded files (e.g. CATNls resource files)
  - UTF-8 with BOM header
  - Mixed CRLF and LF binary preservation
  - Binary assets (BMP icon images / 256-byte binary tables)
  - Create -> Rollback (clean physical deletion)
  - Rename / Move -> Rollback (source restored byte-for-byte, target deleted)
  - Patch -> Rollback (in-place patch restored byte-for-byte)
  - BackupManager disk persistence & rollback (all encodings & binaries)
  - ChangeSet.apply(workspace_root=...) integrated backup rollback
"""

import codecs
import os
import shutil
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from backup import BackupManager
from changeset import ChangeSet, Patch

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    s = "PASS" if ok else "FAIL"
    print(f"  [{s}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 70)
print("  Byte-Identical Physical Rollback Verification")
print("=" * 70)

# Create a temporary workspace for isolated testing
ws = Path(tempfile.mkdtemp(prefix="caa_byte_rb_")).resolve()

try:
    # ═══════════════════════════════════════════════════════════════
    # 1. In-Memory ChangeSet Rollback (Byte-for-Byte)
    # ═══════════════════════════════════════════════════════════════
    print("\n[1] In-Memory ChangeSet: Modify -> Rollback")

    # 1.1 UTF-8 with CRLF
    utf8_file = ws / "test_utf8.cpp"
    orig_utf8 = (
        b"#include <iostream>\r\n"
        b"// \xe4\xb8\xad\xe6\x96\x87\xe6\xb3\xa8\xe9\x87\x8a UTF-8 comment\r\n"
        b"void test() {\r\n"
        b"    std::cout << \"Hello\" << std::endl;\r\n"
        b"}\r\n"
    )
    utf8_file.write_bytes(orig_utf8)

    cs1 = ChangeSet(action="modify_utf8", description="Modify UTF-8 CRLF")
    cs1.add_modify(utf8_file, "void modified() {}\r\n")
    res1 = cs1.apply()
    ck("1.1.1 UTF-8 apply succeeds", res1["status"] == "applied")
    ck("1.1.2 UTF-8 content modified", utf8_file.read_bytes() != orig_utf8)

    rb1 = cs1.rollback()
    ck("1.1.3 UTF-8 rollback succeeds", rb1["status"] == "rolled_back")
    ck(
        "1.1.4 UTF-8 byte-identical restored",
        utf8_file.read_bytes() == orig_utf8,
        f"bytes={len(utf8_file.read_bytes())}",
    )

    # 1.2 GBK (CATNls resource file)
    gbk_file = ws / "test_gbk.CATNls"
    # "测试标题" in GBK: \xb2\xe2\xca\xd4\xb1\xea\xcc\xe2
    orig_gbk = b"CAACmd.Title = \"\xb2\xe2\xca\xd4\xb1\xea\xcc\xe2\";\r\nCAACmd.Help = \"\xcb\xb5\xc3\xf7\";\r\n"
    gbk_file.write_bytes(orig_gbk)

    cs2 = ChangeSet(action="modify_gbk", description="Modify GBK file")
    cs2.add_modify(gbk_file, "CAACmd.Title = \"NewTitle\";\r\n")
    res2 = cs2.apply()
    ck("1.2.1 GBK apply succeeds", res2["status"] == "applied")
    ck("1.2.2 GBK content modified", gbk_file.read_bytes() != orig_gbk)

    rb2 = cs2.rollback()
    ck("1.2.3 GBK rollback succeeds", rb2["status"] == "rolled_back")
    ck(
        "1.2.4 GBK byte-identical restored",
        gbk_file.read_bytes() == orig_gbk,
        f"bytes={len(gbk_file.read_bytes())}",
    )

    # 1.3 UTF-8 with BOM
    bom_file = ws / "test_bom.h"
    orig_bom = codecs.BOM_UTF8 + b"#pragma once\r\n// Header with BOM\r\nclass MyHeader {};\r\n"
    bom_file.write_bytes(orig_bom)

    cs3 = ChangeSet(action="modify_bom", description="Modify UTF-8 BOM file")
    cs3.add_modify(bom_file, "#pragma once\r\nclass Altered {};\r\n")
    res3 = cs3.apply()
    ck("1.3.1 UTF-8 BOM apply succeeds", res3["status"] == "applied")
    ck("1.3.2 UTF-8 BOM modified", bom_file.read_bytes() != orig_bom)

    rb3 = cs3.rollback()
    ck("1.3.3 UTF-8 BOM rollback succeeds", rb3["status"] == "rolled_back")
    ck(
        "1.3.4 UTF-8 BOM byte-identical restored",
        bom_file.read_bytes() == orig_bom,
        f"bytes={len(bom_file.read_bytes())}",
    )

    # 1.4 Mixed CRLF and LF binary preservation
    mixed_file = ws / "test_mixed_eol.txt"
    orig_mixed = b"line1_crlf\r\nline2_lf\nline3_crlf\r\nline4_lf\n"
    mixed_file.write_bytes(orig_mixed)

    cs4 = ChangeSet(action="modify_mixed", description="Modify mixed EOL file")
    cs4.add_modify(mixed_file, "single line content\r\n")
    res4 = cs4.apply()
    ck("1.4.1 Mixed EOL apply succeeds", res4["status"] == "applied")
    ck("1.4.2 Mixed EOL content modified", mixed_file.read_bytes() != orig_mixed)

    rb4 = cs4.rollback()
    ck("1.4.3 Mixed EOL rollback succeeds", rb4["status"] == "rolled_back")
    ck(
        "1.4.4 Mixed EOL byte-identical restored (no normalization)",
        mixed_file.read_bytes() == orig_mixed,
        f"bytes={len(mixed_file.read_bytes())}",
    )

    # ═══════════════════════════════════════════════════════════════
    # 2. Delete, Create, Rename / Move Rollback
    # ═══════════════════════════════════════════════════════════════
    print("\n[2] In-Memory ChangeSet: Delete / Create / Rename Rollback")

    # 2.1 Delete -> Rollback on Binary BMP File
    bmp_file = ws / "I_TestIcon.bmp"
    # Use real BMP asset if available, otherwise high-entropy binary table
    real_bmp_sample = SKILL_ROOT / "assets" / "icons" / "generated" / "I_CADEPartToAsm.bmp"
    if real_bmp_sample.exists():
        orig_bmp = real_bmp_sample.read_bytes()
    else:
        orig_bmp = b"BM" + bytes(range(256)) * 4  # 1026 bytes synthetic binary
    bmp_file.write_bytes(orig_bmp)

    cs5 = ChangeSet(action="delete_bmp", description="Delete binary BMP")
    cs5.add_delete(bmp_file)
    res5 = cs5.apply()
    ck("2.1.1 Binary delete apply succeeds", res5["status"] == "applied")
    ck("2.1.2 Binary file physically unlinked", not bmp_file.exists())

    rb5 = cs5.rollback()
    ck("2.1.3 Binary delete rollback succeeds", rb5["status"] == "rolled_back")
    ck("2.1.4 Binary file physically recreated", bmp_file.exists())
    ck(
        "2.1.5 Binary file byte-identical restored",
        bmp_file.read_bytes() == orig_bmp,
        f"bytes={len(bmp_file.read_bytes())}",
    )

    # 2.2 Create -> Rollback (clean unlinking)
    new_txt = ws / "new_file.txt"
    new_bin = ws / "new_icon.bmp"
    bin_payload = b"\x00\xff\xfe\xfd" + bytes(range(64))

    cs6 = ChangeSet(action="create_files", description="Create new text and binary")
    cs6.add_create(new_txt, "hello newly created world\r\n")
    cs6.add_create_binary(new_bin, bin_payload)
    res6 = cs6.apply()
    ck("2.2.1 Create apply succeeds", res6["status"] == "applied")
    ck("2.2.2 Text file physically created", new_txt.exists())
    ck("2.2.3 Binary file physically created", new_bin.exists() and new_bin.read_bytes() == bin_payload)

    rb6 = cs6.rollback()
    ck("2.2.4 Create rollback succeeds", rb6["status"] == "rolled_back")
    ck("2.2.5 Text file physically removed", not new_txt.exists())
    ck("2.2.6 Binary file physically removed", not new_bin.exists())

    # 2.3 Rename / Move -> Rollback
    # In ChangeSet, rename/move is: add_delete(src) + add_create(dst, content)
    move_src = ws / "SrcCommand.cpp"
    move_dst = ws / "RenamedCommand.cpp"
    orig_move_bytes = b"#include \"SrcCommand.h\"\r\nvoid execute() {}\r\n"
    move_src.write_bytes(orig_move_bytes)

    cs7 = ChangeSet(action="rename_cmd", description="Rename command")
    cs7.add_delete(move_src)
    cs7.add_create(move_dst, orig_move_bytes.decode("utf-8"))
    res7 = cs7.apply()
    ck("2.3.1 Move apply succeeds", res7["status"] == "applied")
    ck("2.3.2 Move source unlinked", not move_src.exists())
    ck("2.3.3 Move destination created", move_dst.exists())

    rb7 = cs7.rollback()
    ck("2.3.4 Move rollback succeeds", rb7["status"] == "rolled_back")
    ck("2.3.5 Move source restored", move_src.exists())
    ck(
        "2.3.6 Move source byte-identical restored",
        move_src.read_bytes() == orig_move_bytes,
    )
    ck("2.3.7 Move destination removed", not move_dst.exists())

    # 2.4 Patch -> Rollback
    patch_file = ws / "patch_target.txt"
    orig_patch_bytes = b"alpha\r\nbeta\r\ngamma\r\n"
    patch_file.write_bytes(orig_patch_bytes)

    cs8 = ChangeSet(action="patch_file", description="Inline patch")
    cs8.patches.append(
        Patch(
            file=patch_file,
            operation="insert_after",
            target="beta",
            content="inserted_item",
        )
    )
    res8 = cs8.apply()
    ck("2.4.1 Patch apply succeeds", res8["status"] == "applied")
    ck("2.4.2 Patch content modified", patch_file.read_bytes() != orig_patch_bytes)

    rb8 = cs8.rollback()
    ck("2.4.3 Patch rollback succeeds", rb8["status"] == "rolled_back")
    ck(
        "2.4.4 Patch target byte-identical restored",
        patch_file.read_bytes() == orig_patch_bytes,
    )

    # ═══════════════════════════════════════════════════════════════
    # 3. Disk-Persistent BackupManager Rollback (Full Matrix)
    # ═══════════════════════════════════════════════════════════════
    print("\n[3] Disk-Persistent BackupManager: Multi-Encoding Physical Verification")

    bm = BackupManager(ws)

    # Prepare files in workspace
    f_utf8 = ws / "bm_utf8.cpp"
    f_utf8.write_bytes(orig_utf8)

    f_gbk = ws / "bm_gbk.CATNls"
    f_gbk.write_bytes(orig_gbk)

    f_bom = ws / "bm_bom.h"
    f_bom.write_bytes(orig_bom)

    f_mixed = ws / "bm_mixed.txt"
    f_mixed.write_bytes(orig_mixed)

    f_bmp = ws / "bm_icon.bmp"
    f_bmp.write_bytes(orig_bmp)

    f_created = ws / "bm_new.txt"
    if f_created.exists():
        f_created.unlink()

    # Build ChangeSet modifying all formats, deleting BMP, creating new file
    cs_disk = ChangeSet(action="disk_test", description="BackupManager full matrix")
    cs_disk.add_modify(f_utf8, "// completely changed utf8\r\n")
    cs_disk.add_modify(f_gbk, "CAACmd.Title = \"Changed\";\r\n")
    cs_disk.add_modify(f_bom, "#pragma once\r\n// modified bom\r\n")
    cs_disk.add_modify(f_mixed, "single line modified\r\n")
    cs_disk.add_delete(f_bmp)
    cs_disk.add_create(f_created, "temporary created file\r\n")

    # Create persistent disk backup
    backup_id = bm.create_backup(cs_disk)
    ck("3.1 Backup created on disk", bool(backup_id))
    ck("3.2 Backup dir exists", (ws / ".caa_backups" / backup_id).is_dir())
    ck("3.3 Manifest exists", (ws / ".caa_backups" / backup_id / "manifest.json").is_file())

    # Apply changes to disk
    res_disk = cs_disk.apply()
    ck("3.4 ChangeSet applied to disk", res_disk["status"] == "applied")
    ck("3.5 BMP physically deleted on disk", not f_bmp.exists())
    ck("3.6 Created file physically present", f_created.exists())

    # Rollback via BackupManager
    rb_disk_res = bm.rollback(backup_id)
    ck("3.7 BackupManager rollback reported success", rb_disk_res["status"] == "success")

    # Assert 100% byte-for-byte fidelity across all files
    ck(
        "3.8 UTF-8 CRLF byte-identical restored from disk",
        f_utf8.read_bytes() == orig_utf8,
        f"bytes={len(f_utf8.read_bytes())}",
    )
    ck(
        "3.9 GBK byte-identical restored from disk",
        f_gbk.read_bytes() == orig_gbk,
        f"bytes={len(f_gbk.read_bytes())}",
    )
    ck(
        "3.10 UTF-8 BOM byte-identical restored from disk",
        f_bom.read_bytes() == orig_bom,
        f"bytes={len(f_bom.read_bytes())}",
    )
    ck(
        "3.11 Mixed EOL byte-identical restored from disk",
        f_mixed.read_bytes() == orig_mixed,
        f"bytes={len(f_mixed.read_bytes())}",
    )
    ck(
        "3.12 Binary BMP physically restored and byte-identical",
        f_bmp.exists() and f_bmp.read_bytes() == orig_bmp,
        f"bytes={len(f_bmp.read_bytes()) if f_bmp.exists() else 0}",
    )
    ck(
        "3.13 Created file physically deleted by rollback",
        not f_created.exists(),
    )

    # ═══════════════════════════════════════════════════════════════
    # 4. ChangeSet.apply(workspace_root=...) Integration
    # ═══════════════════════════════════════════════════════════════
    print("\n[4] ChangeSet.apply(workspace_root=...) Auto-Backup & Rollback")

    target_file = ws / "auto_backup_target.cpp"
    orig_target_bytes = (
        b"// Copyright (c) 2026 Dassault Systemes\r\n"
        b"#include \"CATBaseUnknown.h\"\r\n"
        b"\xc4\xe3\xba\xc3\r\n"
    )
    target_file.write_bytes(orig_target_bytes)

    cs_auto = ChangeSet(action="auto_backup_action", description="Auto backup on apply")
    cs_auto.add_modify(target_file, "// changed during auto backup test\r\n")

    apply_auto_res = cs_auto.apply(workspace_root=ws)
    ck("4.1 apply with workspace_root succeeds", apply_auto_res["status"] == "applied")
    auto_rb_id = apply_auto_res.get("rollback_id")
    ck("4.2 rollback_id returned from apply", bool(auto_rb_id))
    ck("4.3 File changed on disk", target_file.read_bytes() != orig_target_bytes)

    # Roll back via the returned rollback_id
    bm_auto = BackupManager(ws)
    auto_rb_res = bm_auto.rollback(auto_rb_id)
    ck("4.4 Rollback using returned rollback_id succeeds", auto_rb_res["status"] == "success")
    ck(
        "4.5 Auto-backup target restored byte-identical",
        target_file.read_bytes() == orig_target_bytes,
        f"bytes={len(target_file.read_bytes())}",
    )

finally:
    # Cleanup temp workspace
    shutil.rmtree(ws, ignore_errors=True)

print("\n" + "=" * 70)
print(f"  Byte-Identical Rollback: {passed}/{total} ({passed / total * 100:.0f}%)")
print("=" * 70)

if passed == total:
    print("\n  >>> ALL BYTE-IDENTICAL ROLLBACK TESTS PASSED <<<")
    sys.exit(0)
else:
    print(f"\n  >>> FAILED {total - passed} CHECKS <<<")
    sys.exit(1)
