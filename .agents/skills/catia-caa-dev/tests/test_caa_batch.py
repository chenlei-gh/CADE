#!/usr/bin/env python3
"""
CAA Batch (CATBatch) Suite
===========================
Covers the descriptor-driven batch path, which is a different mechanism from
CNEXT's `-batch -macro` script path:

  1. sync_runtime_view copies resources/batchdesc/ into the Runtime View
     (a descriptor that never reaches the RV is invisible to CATBatch, and
     the miss is silent — it falls back to an official descriptor of the
     same name and reports a misleading "batchmain not found").
  2. _pe_exports reads a real PE export table (stdlib only).
  3. run_caa_batch preflight catches each failure mode BEFORE launching, so
     the AFWIN modal dialog never appears.

No CATBatch process is started: every case either fails preflight or asks
for dry_run, which returns before subprocess.run is reached.

Pure stdlib.
"""

import shutil
import struct
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from build import sync_runtime_view
from run import _pe_exports, run_caa_batch

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    if ok:
        passed += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


WS = Path(tempfile.mkdtemp(prefix="cade_batch_test_"))

DESCRIPTOR = (
    "<?xml version='1.0' encoding='UTF-8' standalone='no' ?>\n"
    '<!DOCTYPE batch SYSTEM "BatchDescriptor.dtd">\n'
    '<batch name="TestBatch" description="t" commandline="CATBatch TestLib" />\n'
)

PARAM_OK = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE root SYSTEM "Parameters.dtd" >\n'
    '<root batch_name="TestBatch" >\n'
    "  <inputParameters>\n"
    '    <file id="part" filePath="{input}" type="bin"/>\n'
    "  </inputParameters>\n"
    "  <outputParameters>\n"
    '    <folder id="out" folderPath="{out}" type="bin" extension="CATPart"/>\n'
    "  </outputParameters>\n"
    "</root>\n"
)


def _minimal_pe(exports):
    """Build a tiny but structurally valid PE32+ image exporting `exports`.

    Hand-assembled so the export walker is tested against real header
    offsets rather than a mock. One section holds headers, export directory
    and name strings; both RVA and raw offset are 0x1000-based.
    """
    base = 0x1000
    EXPORT_DIR, NAMES_TABLE, ORDINALS, STRINGS = 0x000, 0x100, 0x0C0, 0x200

    names_blob = b""
    string_rvas = []
    for name in exports:
        string_rvas.append(base + STRINGS + len(names_blob))
        names_blob += name.encode("ascii") + b"\0"

    # IMAGE_EXPORT_DIRECTORY: my walker reads NumberOfNames (+24) and
    # AddressOfNames (+32); the other fields are filled with plausible values
    # so the image stays well-formed for any other reader.
    export_dir = struct.pack(
        "<IIHHIIIIIII",
        0,                      # Characteristics
        0,                      # TimeDateStamp
        0, 0,                   # Major/MinorVersion
        base + STRINGS,         # Name RVA
        1,                      # Ordinal base
        len(exports),           # NumberOfFunctions
        len(exports),           # NumberOfNames
        base + 0x040,           # AddressOfFunctions
        base + NAMES_TABLE,     # AddressOfNames
        base + ORDINALS,        # AddressOfNameOrdinals
    )
    assert len(export_dir) == 40
    names_table = b"".join(struct.pack("<I", r) for r in string_rvas)
    ordinals = b"".join(struct.pack("<H", i) for i in range(len(exports)))

    section = bytearray(0x1000)
    section[EXPORT_DIR:EXPORT_DIR + 40] = export_dir
    section[NAMES_TABLE:NAMES_TABLE + len(names_table)] = names_table
    section[ORDINALS:ORDINALS + len(ordinals)] = ordinals
    section[STRINGS:STRINGS + len(names_blob)] = names_blob

    # Data directory 0 = export table: RVA then size.
    data_dir = struct.pack("<II", base + EXPORT_DIR, len(export_dir)) + b"\0" * (112 - 8)
    opt = struct.pack("<H", 0x20B) + b"\0" * 110 + data_dir
    opt += b"\0" * (0xF0 - len(opt))          # PE32+ optional header is 240 bytes

    coff = struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, len(opt), 0x2022)
    e_lfanew = 0x80
    section_header = struct.pack(
        "<8sIIIIIIHHI",
        b".rdata\0\0", 0x1000, base, 0x1000, base, 0, 0, 0, 0, 0x40000040,
    )
    headers = b"MZ" + b"\0" * (e_lfanew - 2) + b"PE\0\0" + coff + opt + section_header
    headers = bytearray(headers)
    # e_lfanew at 0x3C must POINT at the PE signature; the signature position
    # above only controls where it is written.
    struct.pack_into("<I", headers, 0x3C, e_lfanew)
    headers = bytes(headers)
    assert len(headers) <= base, f"headers overflow: {len(headers):#x}"
    return headers + b"\0" * (base - len(headers)) + bytes(section)


# ═══ 1. Descriptor sync into the Runtime View ═══
print("\n" + "=" * 70)
print("  1. sync_runtime_view copies resources/batchdesc/")
print("=" * 70)

fw = WS / "TestFW.edu" / "CNext" / "resources" / "batchdesc"
fw.mkdir(parents=True, exist_ok=True)
(fw / "TestBatch.xml").write_text(DESCRIPTOR, encoding="utf-8")
(fw / "BatchDescriptor.dtd").write_text("<!ELEMENT batch ANY>\n", encoding="utf-8")
(fw / "notes.txt").write_text("must not be synced", encoding="utf-8")

sync = sync_runtime_view(WS)
rv_desc = WS / "win_b64" / "resources" / "batchdesc" / "TestBatch.xml"

check("1.1 sync reports ok", sync.get("ok") is True, str(sync.get("errors")))
check("1.2 descriptor reached Runtime View", rv_desc.is_file())
check("1.3 descriptor content identical",
      rv_desc.is_file() and rv_desc.read_text(encoding="utf-8") == DESCRIPTOR)
check("1.4 DTD synced", (WS / "win_b64" / "resources" / "batchdesc" / "BatchDescriptor.dtd").is_file())
check("1.5 non-xml/dtd skipped",
      not (WS / "win_b64" / "resources" / "batchdesc" / "notes.txt").exists())
check("1.6 sync list mentions batchdesc",
      any(s.startswith("batchdesc/") for s in sync.get("synced", [])),
      str([s for s in sync.get("synced", []) if s.startswith("batchdesc/")]))

# A stale descriptor must be overwritten even when mtime says it is newer.
rv_desc.write_text("<batch name='Stale' />\n", encoding="utf-8")
import os
os.utime(rv_desc, (2 ** 31 - 1, 2 ** 31 - 1))
sync_runtime_view(WS)
check("1.7 stale descriptor refreshed (content compare, not mtime)",
      rv_desc.read_text(encoding="utf-8") == DESCRIPTOR)

# ═══ 2. PE export parsing ═══
print("\n" + "=" * 70)
print("  2. _pe_exports")
print("=" * 70)

pe_path = WS / "TestLib.dll"
pe_path.write_bytes(_minimal_pe(["batchmain", "SomeOtherExport"]))
exports = _pe_exports(pe_path)
check("2.1 synthetic PE parsed", exports is not None, str(exports))
check("2.2 batchmain found", exports is not None and "batchmain" in exports)
check("2.3 all names returned",
      exports is not None and sorted(exports) == ["SomeOtherExport", "batchmain"], str(exports))

not_pe = WS / "Plain.dll"
not_pe.write_bytes(b"not a PE file at all")
check("2.4 non-PE returns None (not a crash)", _pe_exports(not_pe) is None)
check("2.5 missing file returns None", _pe_exports(WS / "NoSuch.dll") is None)

# A DLL without batchmain is the exact CATMain-vs-batchmain confusion.
no_main = WS / "NoMain.dll"
no_main.write_bytes(_minimal_pe(["CATMain"]))
check("2.6 CATMain-only DLL has no batchmain",
      "batchmain" not in (_pe_exports(no_main) or []))

# ═══ 3. Preflight failure modes (no process started) ═══
print("\n" + "=" * 70)
print("  3. run_caa_batch preflight")
print("=" * 70)

work = WS / "ws"
(work / "win_b64" / "resources" / "batchdesc").mkdir(parents=True, exist_ok=True)
(work / "win_b64" / "code" / "bin").mkdir(parents=True, exist_ok=True)
(work / "win_b64" / "resources" / "batchdesc" / "TestBatch.xml").write_text(
    DESCRIPTOR, encoding="utf-8")

inp = work / "in.CATPart"
inp.write_text("x", encoding="utf-8")
out_dir = work / "out"
out_dir.mkdir(exist_ok=True)
param_ok = work / "Param.xml"
param_ok.write_text(PARAM_OK.format(input=inp, out=out_dir), encoding="utf-8")

r = run_caa_batch(str(WS / "Missing.xml"), workspace_path=str(work))
check("3.1 missing parameter file rejected",
      r.get("status") == "error" and "not found" in r.get("message", "").lower(),
      r.get("message", "")[:70])

bad_xml = work / "Bad.xml"
bad_xml.write_text("<root batch_name='TestBatch'>", encoding="utf-8")
r = run_caa_batch(str(bad_xml), workspace_path=str(work))
check("3.2 malformed parameter XML rejected",
      r.get("status") == "error" and "well-formed" in r.get("message", ""),
      r.get("message", "")[:70])

no_name = work / "NoName.xml"
no_name.write_text("<root><inputParameters/></root>", encoding="utf-8")
r = run_caa_batch(str(no_name), workspace_path=str(work))
check("3.3 missing batch_name rejected",
      r.get("status") == "error" and "batch_name" in r.get("message", ""),
      r.get("message", "")[:70])

# The S0Probe failure: a batch_name with no workspace descriptor. CATBatch
# would fall through to an official descriptor and report the wrong cause.
wrong_name = work / "Wrong.xml"
wrong_name.write_text(
    PARAM_OK.format(input=inp, out=out_dir).replace("TestBatch", "NoSuchBatch"),
    encoding="utf-8")
r = run_caa_batch(str(wrong_name), workspace_path=str(work))
check("3.4 unknown batch_name rejected BEFORE launch",
      r.get("status") == "error" and "descriptor" in r.get("message", "").lower(),
      r.get("message", "")[:80])
check("3.5 error names the searched paths",
      any("batchdesc" in s for s in r.get("searched", [])), str(r.get("searched", []))[:90])

# Descriptor points at a library that was never built.
(work / "win_b64" / "resources" / "batchdesc" / "TestBatch.xml").write_text(
    DESCRIPTOR, encoding="utf-8")
r = run_caa_batch(str(param_ok), workspace_path=str(work), dry_run=True)
check("3.6 descriptor found, library missing is reported",
      any(c["check"] == "library_found" and c["ok"] is False for c in r.get("checks", [])),
      r.get("message", "")[:70])

# Library exists but has no batchmain (a CATMain-only library).
(work / "win_b64" / "code" / "bin" / "TestLib.dll").write_bytes(_minimal_pe(["CATMain"]))
r = run_caa_batch(str(param_ok), workspace_path=str(work), dry_run=True)
check("3.7 library without batchmain rejected",
      any(c["check"] == "exports_batchmain" and c["ok"] is False for c in r.get("checks", []))
      or r.get("status") == "error",
      r.get("message", "")[:80])

# Fully valid preflight, dry_run must stop before CATBatch is launched.
(work / "win_b64" / "code" / "bin" / "TestLib.dll").write_bytes(_minimal_pe(["batchmain"]))
r = run_caa_batch(str(param_ok), workspace_path=str(work), dry_run=True)
all_checks_ok = all(c["ok"] is not False for c in r.get("checks", []))
check("3.8 valid preflight reports dry_run", r.get("status") == "dry_run", str(r.get("status")))
check("3.9 every preflight check passed", all_checks_ok,
      str([c for c in r.get("checks", []) if c["ok"] is False]))
check("3.10 resolved descriptor is the workspace one",
      str(r.get("descriptor", "")).startswith(str(work)), str(r.get("descriptor"))[:90])
check("3.11 resolved library is TestLib.dll", r.get("library") == "TestLib")
check("3.12 no process launched (no log_dirs)", "log_dirs" not in r)

# Missing declared input file.
(inp).unlink()
r = run_caa_batch(str(param_ok), workspace_path=str(work), dry_run=True)
check("3.13 missing input file flagged",
      any(c["check"] == "input_files_exist" and c["ok"] is False for c in r.get("checks", [])),
      r.get("message", "")[:70])

# ═══ 4. Mechanism separation ═══
print("\n" + "=" * 70)
print("  4. Mechanism separation (script batch vs CATBatch)")
print("=" * 70)

import run as run_mod

check("4.1 run_catia_batch and run_caa_batch are distinct functions",
      run_mod.run_catia_batch is not run_mod.run_caa_batch)
check("4.2 run_caa_batch requires a param file (no script arg)",
      "param_file" in run_mod.run_caa_batch.__code__.co_varnames
      and "batch_script" not in run_mod.run_caa_batch.__code__.co_varnames)
check("4.3 run_catia_batch has no descriptor logic",
      "batchdesc" not in run_mod.run_catia_batch.__code__.co_consts.__str__())

# ═══ 5. mkrun launcher argument passing ═══
print("\n" + "=" * 70)
print("  5. mkrun launcher: CNEXT switches go through -c")
print("=" * 70)

# mkrun parses its OWN argv: -macro/-batch appended after `mkrun` make it exit
# with "illegal option" and CNEXT never starts, which surfaces as exit_code 0
# with no side effects. The switches must ride inside -c "CNEXT ...".


def _launcher_line(cnext_args):
    """Return the mkrun invocation line _mkrun_cmd would emit."""
    caa_env = run_mod.CAAEnvironment()
    caa_env.load_config()
    _args, batfile = run_mod._mkrun_cmd(
        caa_env, str(WS), cnext_args, detach=False
    )
    try:
        text = Path(batfile).read_text(encoding="ascii", errors="replace")
    finally:
        try:
            Path(batfile).unlink()
        except OSError:
            pass
    for line in text.splitlines():
        if "mkrun" in line:
            return line.strip()
    return ""


line_macro = _launcher_line(["-macro", "C:/tmp/x.CATScript"])
line_plain = _launcher_line(None)

check("5.1 CNEXT switches go through -c",
      '-c "CNEXT' in line_macro, line_macro)
check("5.2 -macro is not appended after bare mkrun",
      not line_macro.rstrip().endswith('mkrun "-macro"'), line_macro)
check("5.3 -macro survives inside the -c payload",
      "-macro" in line_macro, line_macro)

# mkrun splits the -c payload on spaces, so a spaced path can never survive:
# bare, nested quotes and backslash escapes all truncate at the first space on
# B28. The launcher must refuse instead of emitting something that fails.
# Built from the test workspace rather than a literal drive path: only the
# space matters here, and a hardcoded C:\ makes this line trip the
# no-hardcoded-paths scan for no reason.
space_path = str(WS / "Program Files" / "x y.CATScript")
try:
    spaced_line = _launcher_line(["-macro", space_path])
    space_failed_loud = False
except ValueError as e:
    spaced_line = str(e)
    space_failed_loud = "cannot pass an argument containing a space" in str(e)

check("5.4 argument with a space fails fast instead of escaping",
      space_failed_loud and "x y.CATScript" in spaced_line, spaced_line[:100])
check("5.5 fail-fast message names the remedy",
      "without spaces" in spaced_line, spaced_line[:100])
check("5.6 no switch means a plain mkrun call",
      line_plain.startswith("call mkrun") and "-c" not in line_plain,
      line_plain)

# The same guard must be reachable through the public entry point, not only
# through _mkrun_cmd: a caller gets a structured error, never a silent run.
spaced_macro = WS / "spaced macro.CATScript"
spaced_macro.write_text("Language=\"VBScript\"\n", encoding="ascii")
macro_result = run_mod.run_catia_macro(
    str(spaced_macro), workspace_path=str(WS), timeout=1
)
check("5.7 a spaced macro path reports an error, not a silent no-op",
      macro_result.get("status") == "error" and
      "space" in macro_result.get("message", ""),
      macro_result.get("message", "")[:100])

# ═══ 6. Known-limitation hint on a 0x80004005 failure ═══
print("\n" + "=" * 70)
print("  6. CATBatch session failure is self-explaining")
print("=" * 70)

# CATBatch's managed session never comes up on B28, so Documents.Add/Open
# return 0x80004005. The same calls succeed under CNEXT script mode, so this
# is a launcher limitation, not a fault in the batch. The failure message must
# say so rather than leaving the caller to re-diagnose it. The fixture has to
# clear preflight on its own: section 3 deletes the shared input file.


def _annotate(stdout, stderr, rc=2):
    """Drive only the post-run annotation; subprocess is stubbed out."""
    ann_ws = Path(tempfile.mkdtemp(prefix="cade_batch_ann_"))
    try:
        ann_desc = ann_ws / "win_b64" / "resources" / "batchdesc"
        ann_bin = ann_ws / "win_b64" / "code" / "bin"
        ann_desc.mkdir(parents=True)
        ann_bin.mkdir(parents=True)
        (ann_desc / "TestBatch.xml").write_text(DESCRIPTOR, encoding="utf-8")
        (ann_bin / "TestLib.dll").write_bytes(_minimal_pe(["batchmain"]))
        ann_in = ann_ws / "in.CATPart"
        ann_in.write_bytes(b"x")
        ann_param = ann_ws / "Param.xml"
        ann_param.write_text(
            PARAM_OK.format(input=str(ann_in), out=str(ann_ws / "out")),
            encoding="utf-8")

        def fake_run(cmd, **kwargs):
            return type("P", (), {"returncode": rc,
                                  "stdout": stdout, "stderr": stderr})()

        real_run = run_mod.subprocess.run
        run_mod.subprocess.run = fake_run
        try:
            return run_mod.run_caa_batch(str(ann_param), workspace_path=str(ann_ws))
        finally:
            run_mod.subprocess.run = real_run
    finally:
        shutil.rmtree(ann_ws, ignore_errors=True)


session_fail = _annotate("", "Create_Session : 0x80004005\nlocated in <C:\\temp\\abc>")
check("6.1 0x80004005 is flagged as the known session limitation",
      session_fail.get("known_limitation") == "catbatch_session" and
      "run_catia_batch" in session_fail.get("message", ""),
      session_fail.get("message", "")[:110])

other_fail = _annotate("", "Entry point <batchmain> not found")
check("6.2 an unrelated failure is not mislabelled as the session limitation",
      "known_limitation" not in other_fail and
      "0x80004005" not in other_fail.get("message", ""),
      other_fail.get("message", "")[:110])

ok_run = _annotate("batch done", "", rc=0)
check("6.3 a clean run carries no limitation flag",
      ok_run.get("status") == "success" and "known_limitation" not in ok_run,
      ok_run.get("status"))

# ═══ Summary ═══
print("\n" + "=" * 70)
print(f"  CAA Batch: {passed}/{total}")
if total:
    print(f"  Pass rate: {passed / total * 100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> ALL CAA BATCH TESTS PASSED <<<")
else:
    print(f"\n  >>> {total - passed} CHECK(S) FAILED <<<")

shutil.rmtree(WS, ignore_errors=True)
sys.exit(0 if passed == total else 1)
