#!/usr/bin/env python3
"""P2: an authorized ChangeSet carries touched-path preconditions.

Ordinary to_dict() stays pure. apply() rejects when the baseline no longer
holds, and writes nothing. Temp workspace only.
"""

import shutil
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from changeset import ChangeSet, Patch
from provenance_guard import compute_file_sha256

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))


def main():
    ws = Path(tempfile.mkdtemp(prefix="cade_p2_pre_"))
    try:
        existing = ws / "Keep.cpp"
        existing.write_bytes(b"int keep = 1;\r\n")
        doomed = ws / "Gone.cpp"
        doomed.write_bytes(b"int gone = 1;\r\n")
        icon = ws / "I_New.bmp"

        cs = ChangeSet(action="p2", description="baseline this object")
        cs.add_create(ws / "New.cpp", "int created = 1;\n")
        cs.add_modify(existing, "int keep = 2;\n")
        cs.add_delete(doomed)
        cs.add_patch(Patch(file=existing, operation="append", target="", content="\n"))
        cs.add_create_binary(icon, b"\x42\x4d")

        plain = cs.to_dict()
        check("plain to_dict has no preconditions", "preconditions" not in plain)
        check("plain to_dict does not mutate the object", cs.preconditions == {})

        captured = cs.capture_preconditions(ws)
        check("created recorded as absent", captured["New.cpp"] == {"exists": False, "sha256": None})
        check("bmp recorded as absent", captured["I_New.bmp"] == {"exists": False, "sha256": None})
        check("modified records sha256", captured["Keep.cpp"]["exists"] is True and captured["Keep.cpp"]["sha256"])
        check("deleted records sha256", captured["Gone.cpp"]["sha256"] == compute_file_sha256(doomed))
        check("patch does not duplicate modified path", list(captured).count("Keep.cpp") == 1)

        authorized = cs.to_dict()
        check("authorized dict carries preconditions", "preconditions" in authorized)
        restored = ChangeSet.from_dict(authorized)
        check("from_dict keeps preconditions", restored.preconditions["Keep.cpp"]["sha256"] == captured["Keep.cpp"]["sha256"])

        ok = restored.apply(workspace_root=ws)
        check("matching baseline applies", ok.get("status") == "applied", str(ok.get("status")))
        check("created file written", (ws / "New.cpp").is_file())
        shutil.rmtree(ws / ".caa_backups", ignore_errors=True)

        # Fresh object: content drift on a modified path must reject before write.
        ws2_new = ws / "Other.cpp"
        cs2 = ChangeSet(action="p2-drift", description="reject drift")
        cs2.add_create(ws / "Fresh.cpp", "fresh\n")
        cs2.add_modify(existing, "int keep = 9;\n")
        cs2.capture_preconditions(ws)
        existing.write_bytes(b"int keep = 3;\r\n")
        before = existing.read_bytes()
        rejected = ChangeSet.from_dict(cs2.to_dict()).apply(workspace_root=ws)
        check("content drift rejected", rejected.get("status") == "rejected", str(rejected.get("errors")))
        check("drift writes nothing", existing.read_bytes() == before and not (ws / "Fresh.cpp").exists())
        check("mismatch names the path", any("Keep.cpp" in m for m in rejected.get("precondition_mismatches", [])))

        # A create path that appears between authorization and apply is also a mismatch.
        cs3 = ChangeSet(action="p2-create", description="reject late create")
        cs3.add_create(ws2_new, "late\n")
        cs3.capture_preconditions(ws)
        ws2_new.write_bytes(b"someone else\n")
        rejected_create = ChangeSet.from_dict(cs3.to_dict()).apply(workspace_root=ws)
        check("late create rejected", rejected_create.get("status") == "rejected")
        check("late create leaves the intruder", ws2_new.read_bytes() == b"someone else\n")

        # No preconditions: old apply path still writes.
        bare = ChangeSet(action="p2-bare", description="no baseline")
        bare.add_create(ws / "Bare.cpp", "bare\n")
        bare_result = bare.apply(workspace_root=ws)
        check("absent preconditions still apply", bare_result.get("status") == "applied")
        check("bare file written", (ws / "Bare.cpp").is_file())
    finally:
        shutil.rmtree(ws, ignore_errors=True)

    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
