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
from actions import _result

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

        # Hole 1: _result fail-closed when capture fails.
        class BrokenCS(ChangeSet):
            def capture_preconditions(self, workspace_root):
                raise RuntimeError("simulated capture explosion")

        borked = BrokenCS(action="borked", description="fail to capture")
        borked_res = _result(borked, ws)
        check("capture failure returns error status", borked_res.get("status") == "error")
        check("capture failure omits changeset", borked_res.get("changeset") is None)
        check("capture failure message explains reason", "simulated capture explosion" in borked_res.get("message", ""))

        # Hole 2: Pre-existing binary create target (e.g. .bmp) is baselined,
        # not refused: overwriting a stale render is the intended semantics of a
        # queued binary payload (_pre_validate_files says so explicitly). The
        # recorded baseline is what makes the overwrite safe — drift after
        # authorization still rejects at apply().
        bmp_file = ws / "Conflict.bmp"
        bmp_file.write_bytes(b"original bmp")
        cs_bmp = ChangeSet(action="bmp-create", description="create on top of existing bmp")
        cs_bmp.add_create_binary(bmp_file, b"new bmp bytes")
        bmp_captured = cs_bmp.capture_preconditions(ws)
        check(
            "existing bmp baselined by hash, not refused",
            bmp_captured.get("Conflict.bmp", {}).get("exists") is True
            and bmp_captured["Conflict.bmp"].get("sha256") == compute_file_sha256(bmp_file),
            str(bmp_captured.get("Conflict.bmp")),
        )
        check("existing bmp untouched at capture", bmp_file.read_bytes() == b"original bmp")

        bmp_result = _result(cs_bmp, ws)
        check("existing bmp still authorizes", bmp_result.get("status") == "pending", str(bmp_result.get("status")))

        bmp_applied = ChangeSet.from_dict(bmp_result["changeset"]).apply(workspace_root=ws)
        check("baselined bmp apply succeeds", bmp_applied.get("status") == "applied", str(bmp_applied.get("errors")))
        check("baselined bmp overwritten", bmp_file.read_bytes() == b"new bmp bytes")
        shutil.rmtree(ws / ".caa_backups", ignore_errors=True)

        # Same object, but the file changes between authorization and apply:
        # the recorded hash no longer holds, so the overwrite is refused.
        bmp_file.write_bytes(b"actor bytes")
        bmp_drift = ChangeSet.from_dict(bmp_result["changeset"]).apply(workspace_root=ws)
        check("bmp drift rejected", bmp_drift.get("status") == "rejected", str(bmp_drift.get("errors")))
        check("bmp drift not written", bmp_file.read_bytes() == b"actor bytes")

        # Text create targets keep the fail-closed rule: only binary payloads are
        # exempt, so an existing file cannot be silently overwritten as text.
        text_file = ws / "Conflict.cpp"
        text_file.write_bytes(b"int original = 1;\n")
        cs_text = ChangeSet(action="text-create", description="create over existing text")
        cs_text.add_create(text_file, "int replacement = 2;\n")
        text_raised = False
        try:
            cs_text.capture_preconditions(ws)
        except ValueError as e:
            text_raised = True
            check("text capture raises ValueError on existing file", "already exists" in str(e))
        check("text capture raised", text_raised)
        text_result = _result(cs_text, ws)
        check("_result returns error when text exists", text_result.get("status") == "error")
        check("existing text untouched", text_file.read_bytes() == b"int original = 1;\n")

        # Invariant: Old unbaselined binary apply still overwrites (preserves legacy semantics).
        cs_old_binary = ChangeSet(action="old-bmp", description="unbaselined binary overwrite")
        cs_old_binary.add_create_binary(bmp_file, b"legacy overwritten bytes")
        old_apply_res = cs_old_binary.apply(workspace_root=ws)
        check("unbaselined binary apply succeeds", old_apply_res.get("status") == "applied")
        check("unbaselined binary overwrites file", bmp_file.read_bytes() == b"legacy overwritten bytes")

        # Hole 3: Precondition path outside workspace_root rejected before read.
        outside_file = ws.parent / "outside_probe.txt"
        outside_file.write_bytes(b"sensitive")
        try:
            cs_traversal = ChangeSet(action="traversal", description="traversal in preconditions")
            cs_traversal.preconditions = {
                "../outside_probe.txt": {"exists": True, "sha256": "fakehash"}
            }
            res_traversal = cs_traversal.apply(workspace_root=ws)
            check("traversal precondition rejected", res_traversal.get("status") == "rejected")
            check("mismatch reports invalid path", any("Invalid precondition path" in err for err in res_traversal.get("errors", [])))
            check("outside file untouched", outside_file.read_bytes() == b"sensitive")
        finally:
            if outside_file.exists():
                outside_file.unlink()
    finally:
        shutil.rmtree(ws, ignore_errors=True)

    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
