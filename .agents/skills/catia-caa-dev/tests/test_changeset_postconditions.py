#!/usr/bin/env python3
"""P5.1: ChangeSet postconditions prove the applied object landed.

Expected bytes come from the writer, not from a second interpretation of the
request. Rejected and failed applies do not scan. Temp workspace only.
"""

import shutil
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from changeset import ChangeSet, Patch

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))


def statuses(result):
    return (
        result.get("execution", {}).get("status"),
        result.get("verification", {}).get("status"),
    )


def main():
    ws = Path(tempfile.mkdtemp(prefix="cade_p51_post_"))
    try:
        created = ws / "New.cpp"
        modified = ws / "Keep.cpp"
        deleted = ws / "Gone.cpp"
        patched = ws / "Patch.cpp"
        binary = ws / "I_New.bmp"
        gbk = ws / "Simplified_Chinese" / "Cmd.CATNls"
        modified.write_bytes(b"int keep = 1;\r\n")
        deleted.write_bytes(b"int gone = 1;\r\n")
        patched.write_bytes(b"void Foo() {\r\n}\r\n")

        cs = ChangeSet(action="p51", description="land these writes")
        cs.add_create(created, "int created = 1;\n")
        cs.add_modify(modified, "int keep = 2;\n")
        cs.add_delete(deleted)
        cs.add_patch(Patch(file=patched, operation="append", target="", content="// patched"))
        cs.add_create_binary(binary, b"\x42\x4d\x00")
        cs.add_create(gbk, "CAACmd.Title = \"\u6807\u9898\";\n")

        ok = cs.apply(workspace_root=ws)
        check("apply stays applied", ok.get("status") == "applied", str(ok.get("status")))
        check("execution success and verification passed", statuses(ok) == ("success", "passed"), str(statuses(ok)))
        names = {c["name"] for c in ok["verification"]["checks"]}
        check("created and modified hashed", {"created_sha256", "modified_sha256"} <= names)
        check("deleted proved absent", any(c["name"] == "deleted_absent" and c["status"] == "passed" for c in ok["verification"]["checks"]))
        check(
            "patch is existence-only",
            any(c["name"] == "patched_exists" and "not_run" in c.get("detail", "") for c in ok["verification"]["checks"]),
        )
        check("gbk writer bytes landed", b"\xb1\xea\xcc\xe2" in gbk.read_bytes())

        # A successful write whose disk image is then disturbed must fail
        # verification without rewriting apply status or rolling back.
        disturbed = ChangeSet(action="p51-disturb", description="detect drift")
        target = ws / "Drift.cpp"
        disturbed.add_create(target, "int drift = 1;\n")
        real_verify = disturbed._verify_postconditions
        def drift_after_write(*args, **kwargs):
            target.write_bytes(b"tampered\r\n")
            return real_verify(*args, **kwargs)
        disturbed._verify_postconditions = drift_after_write
        drifted = disturbed.apply(workspace_root=ws)
        check("disturbed apply status remains applied", drifted.get("status") == "applied")
        check("disturbed execution stays success", drifted["execution"]["status"] == "success")
        check("disturbed verification fails", drifted["verification"]["status"] == "failed")
        check("disturbance is not rolled back", target.read_bytes() == b"tampered\r\n")

        rejected = ChangeSet(action="p51-reject", description="no scan")
        rejected.add_create(created, "int again = 1;\n")
        rejected_result = rejected.apply(workspace_root=ws)
        check("existing create is rejected", rejected_result.get("status") == "rejected")
        check("rejected does not scan", statuses(rejected_result) == ("failed", "not_run"))
        check("rejected has no checks", rejected_result["verification"]["checks"] == [])

        dry = ChangeSet(action="p51-dry", description="no scan")
        dry.add_create(ws / "Dry.cpp", "int dry = 1;\n")
        dry_result = dry.apply(dry_run=True, workspace_root=ws)
        check("dry_run does not scan", statuses(dry_result) == ("not_run", "not_run"))
        check("dry_run writes nothing", not (ws / "Dry.cpp").exists())
    finally:
        shutil.rmtree(ws, ignore_errors=True)

    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
