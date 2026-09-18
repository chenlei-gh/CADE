#!/usr/bin/env python3
"""Focused regression tests for production safety contracts."""

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from actions import ActionContext, create_framework
from analyzer import WorkspaceAnalyzer
import backup as backup_module
import build as build_module
import cade as cade_module
from backup import BackupManager
from build import verify_build
from changeset import ChangeSet, Patch, merge_changesets
from diagnostics import DiagnosticsEngine
from generator import TemplateGenerator
from parser import parse_mkmk_output
from repair import RepairLoop, RepairState
import runtime_view as runtime_view_module
from utils import Cache, gc_stale_buckets

workspace = Path(tempfile.mkdtemp(prefix="cade_production_regressions_"))
total = passed = 0
failures = []


def check(label, ok, detail=""):
    global total, passed
    total += 1
    if ok:
        passed += 1
    else:
        failures.append(label)
    trailer = f" — {detail}" if detail else ""
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{trailer}")


try:
    # Rejection must be side-effect free.
    rejected_parent = workspace / "must_not_exist"
    cs = ChangeSet(action="reject", description="reject before writes")
    cs.add_create(rejected_parent / "new.txt", "new")
    cs.add_modify(workspace / "missing.txt", "bad")
    result = cs.apply(workspace_root=workspace)
    check("invalid changeset is rejected", result["status"] == "rejected", str(result.get("errors", [])))
    check("rejected changeset creates no parent", not rejected_parent.exists())

    # insert_after must terminate even when inserted content contains the target.
    target_file = workspace / "patch.txt"
    target_file.write_text("TARGET\n", encoding="utf-8")
    patch_cs = ChangeSet(action="patch", description="safe insert")
    patch_cs.add_patch(Patch(target_file, "insert_after", "TARGET", "TARGET child"))
    patch_result = patch_cs.apply(workspace_root=workspace)
    check("insert_after with recursive-looking content applies", patch_result["status"] == "applied", str(patch_result.get("errors", [])))
    check("insert_after inserts exactly once", target_file.read_text(encoding="utf-8").count("TARGET child") == 1)

    # A ChangeSet may create a file and patch that newly-created content atomically.
    created_file = workspace / "created_then_patched.txt"
    create_patch = ChangeSet(action="create_patch", description="create and patch")
    create_patch.add_create(created_file, "base\n")
    create_patch.add_patch(Patch(created_file, "append", "", "extra"))
    create_patch_result = create_patch.apply(workspace_root=workspace)
    check("create+patch same file applies", create_patch_result["status"] == "applied", str(create_patch_result.get("errors", [])))
    check("create+patch content retained", created_file.exists() and "extra" in created_file.read_text(encoding="utf-8"))

    # Framework + modules is advertised as one operation and must be applicable.
    ctx = ActionContext(workspace)
    framework_result = create_framework(ctx, "CombinedFramework", modules=["CoreModule"])
    check("framework with modules returns pending", framework_result.get("status") == "pending", framework_result.get("message", ""))
    framework_cs = ChangeSet.from_dict(framework_result.get("changeset", {}))
    framework_apply = framework_cs.apply(workspace_root=workspace)
    check("framework with modules applies", framework_apply["status"] == "applied", str(framework_apply.get("errors", [])))
    check("framework module exists", (workspace / "CombinedFramework.edu" / "CoreModule.m" / "Imakefile.mk").exists())

    # CATIAV5Level.lvl is workspace-scoped. A second framework must not queue
    # create against the existing file (ChangeSet create-or-fail).
    existing_lvl = workspace / "CATIAV5Level.lvl"
    check("first framework wrote CATIAV5Level.lvl", existing_lvl.is_file())
    sentinel = (
        existing_lvl.read_text(encoding="utf-8") if existing_lvl.is_file() else ""
    ) + "\n// SENTINEL_DO_NOT_OVERWRITE\n"
    existing_lvl.write_text(sentinel, encoding="utf-8")
    ctx2 = ActionContext(workspace)
    second = create_framework(ctx2, "SecondFramework")
    check(
        "second framework returns pending",
        second.get("status") == "pending",
        second.get("message", ""),
    )
    created_keys = list((second.get("changeset") or {}).get("created") or {})
    check(
        "second framework does not queue existing CATIAV5Level.lvl",
        not any(Path(k).name == "CATIAV5Level.lvl" for k in created_keys),
        str(created_keys),
    )
    second_apply = ChangeSet.from_dict(second.get("changeset", {})).apply(
        workspace_root=workspace
    )
    check(
        "second framework applies with existing .lvl",
        second_apply["status"] == "applied",
        str(second_apply.get("errors", [])),
    )
    check(
        "existing CATIAV5Level.lvl content unchanged",
        existing_lvl.is_file() and existing_lvl.read_text(encoding="utf-8") == sentinel,
    )
    check(
        "second framework .edu exists",
        (workspace / "SecondFramework.edu" / "Imakefile.mk").exists(),
    )

    # Generated tests must use APIs available in B28, not an invented test framework.
    generated_tests = workspace / "generated_tests"
    testcase_result = TemplateGenerator().generate("testcase", "GeneratedTest", generated_tests)
    generated_header = (generated_tests / "GeneratedTest.h").read_text(encoding="utf-8")
    generated_source = (generated_tests / "GeneratedTest.cpp").read_text(encoding="utf-8")
    check("testcase generation succeeds", testcase_result.get("status") == "success", str(testcase_result))
    check("testcase omits unavailable CATTestCase", '#include "CATTestCase.h"' not in generated_header and "public CATTestCase" not in generated_header and ": CATTestCase(" not in generated_source)
    check("testcase uses supported CATAssert", "CATAssert(" in generated_source)
    check("testcase omits unavailable suite macros", "CATBeginTestSuite" not in generated_source and "CATAddTest" not in generated_source)

    # Static diagnostics must reject the legacy patterns found by the real TTEST build.
    legacy_source = workspace / "CombinedFramework.edu" / "CoreModule.m" / "src" / "LegacyTest.h"
    legacy_source.write_text('#include "CATTestCase.h"\n', encoding="utf-8")
    legacy_addin = legacy_source.with_name("LegacyAddin.cpp")
    legacy_addin.write_text("CATImplementHeaderResources(LegacyHdr, CATCommandHeader, LegacyHdr);\n", encoding="utf-8")
    legacy_snapshot = WorkspaceAnalyzer(workspace).analyze()
    legacy_diagnostics = DiagnosticsEngine(legacy_snapshot)
    legacy_diagnostics.run_all()
    compile_problems = [d.problem for d in legacy_diagnostics.diagnostics if d.category == "compile_contract"]
    check("diagnostics detect unavailable CATTestCase", any("CATTestCase" in p for p in compile_problems), str(compile_problems))
    check("diagnostics detect invalid header macro", any("CommandHeader" in p for p in compile_problems), str(compile_problems))

    # The documented direct `build.py <workspace> -a` CLI form must remain valid.
    cli_calls = []
    with patch.object(sys, "argv", ["build.py", str(workspace), "-a"]), \
            patch.object(build_module, "build_workspace", side_effect=lambda ws, opts, timeout, **kw: cli_calls.append((ws, opts, timeout)) or {"status": "success"}), \
            patch.object(build_module, "output_json", return_value=None):
        build_module.main()
    check("build CLI accepts direct -a", bool(cli_calls) and cli_calls[0][1] == "-a", str(cli_calls))

    # CLI JSON must not carry the full raw mkmk log (repair.py keeps it via
    # the Python API; the CLI shows only a tail + the on-disk log path).
    big_output = "x\n" * 5000
    fake_log = str(workspace / "logs" / "build.log")
    fat_result = {
        "status": "failed",
        "error_count": 1,
        "errors": [{"file": "a.cpp", "line": 1, "code": "C2440", "message": "boom"}],
        "output": big_output,
        "output_log": fake_log,
    }
    slim = build_module.slim_result_for_cli(fat_result)
    check(
        "CLI slim drops raw output",
        "output" not in slim,
        str(sorted(slim.keys())),
    )
    check(
        "CLI slim keeps structured errors",
        slim.get("errors") == fat_result["errors"] and slim.get("error_count") == 1,
        str(slim.get("errors")),
    )
    check(
        "CLI slim keeps bounded tail",
        0 < len(slim.get("output_tail", "")) <= 2000,
        str(len(slim.get("output_tail", ""))),
    )
    check(
        "CLI slim points at on-disk log",
        slim.get("output_log") == fake_log,
        str(slim.get("output_log")),
    )
    no_output = {"status": "success"}
    check(
        "CLI slim tolerates missing output",
        "output_tail" not in build_module.slim_result_for_cli(no_output),
        str(build_module.slim_result_for_cli(no_output)),
    )
    # main() applies slimming by default and --full-output opts out.
    captured = []
    with patch.object(sys, "argv", ["build.py", str(workspace)]), \
            patch.object(build_module, "build_workspace", return_value=dict(fat_result)), \
            patch.object(build_module, "output_json", side_effect=lambda r, exit_code=0: captured.append(r)):
        build_module.main()
    check(
        "main slims output by default",
        bool(captured) and "output" not in captured[0] and "output_tail" in captured[0],
        str(sorted(captured[0].keys())) if captured else "no capture",
    )
    captured.clear()
    with patch.object(sys, "argv", ["build.py", str(workspace), "--full-output"]), \
            patch.object(build_module, "build_workspace", return_value=dict(fat_result)), \
            patch.object(build_module, "output_json", side_effect=lambda r, exit_code=0: captured.append(r)):
        build_module.main()
    check(
        "main keeps full output with --full-output",
        bool(captured) and captured[0].get("output") == big_output,
        str(sorted(captured[0].keys())) if captured else "no capture",
    )

    kernel_calls = []
    with patch.object(cade_module, "_kernel", side_effect=lambda mode, text, workspace=None: kernel_calls.append((mode, text, workspace)) or {"status": "ok", "message": "mock"}), \
            patch.object(cade_module, "_print_kernel", return_value=None):
        cade_module.cmd_diagnose([str(workspace)])
    check("diagnose CLI uses positional workspace", bool(kernel_calls) and kernel_calls[0][2] == str(workspace), str(kernel_calls))

    # Conflicting merge must not silently select the last writer.
    conflict_path = workspace / "conflict.txt"
    first = ChangeSet(action="first", description="first")
    second = ChangeSet(action="second", description="second")
    first.add_create(conflict_path, "first")
    second.add_create(conflict_path, "second")
    merged = merge_changesets(first, second)
    conflict_apply = merged.apply(workspace_root=workspace)
    check("merge conflict blocks apply", conflict_apply["status"] == "rejected", str(conflict_apply.get("errors", [])))
    check("merge conflict writes no file", not conflict_path.exists())

    # Wrapper/system errors must count even when mkmk returns zero. B28 uses
    # mkmk-ERROR; make-ERROR remains a compatibility variant.
    wrapper_output = (
        "   # mkmk-ERROR: C:\\Build Output\\Broken Module.m\n"
        "mkmk-ERROR: C:\\Build Output\\Second Module.m\n"
        "# make-ERROR: C:\\Build Output\\Legacy Module.m\n"
        "  # syst-ERROR: C:\\Program Files\\Dassault Systemes\\broken.obj: access denied\n"
    )
    parsed_wrapper = parse_mkmk_output(wrapper_output)
    check("mkmk/make/syst errors are parsed", parsed_wrapper["error_count"] == 4, str(parsed_wrapper))
    wrapper_codes = [e.get("code") for e in parsed_wrapper["errors"]]
    check("mkmk wrapper code is preserved", wrapper_codes.count("mkmk-ERROR") == 2, str(wrapper_codes))
    syst_errors = [e for e in parsed_wrapper["errors"] if e.get("message") == "access denied"]
    check("syst error preserves message", len(syst_errors) == 1 and syst_errors[0].get("code") == "syst-ERROR", str(parsed_wrapper["errors"]))
    check("wrapper Windows path with spaces is parsed", any(e.get("file") == "Broken Module.m" for e in parsed_wrapper["errors"]), str(parsed_wrapper["errors"]))

    prose_output = (
        "Documentation says mkmk-ERROR: this is only an example.\n"
        "prefix # syst-ERROR: C:\\Build\\broken.obj: not a real record\n"
        "mkmk completed successfully\n"
    )
    parsed_prose = parse_mkmk_output(prose_output)
    check("wrapper tokens in prose are ignored", parsed_prose["error_count"] == 0, str(parsed_prose))
    single_wrapper = parse_mkmk_output("# mkmk-ERROR: C:\\Build Output\\OnlyOnce.m")
    check("one wrapper line is counted once", single_wrapper["error_count"] == 1, str(single_wrapper))

    # P0: 1 root-cause compile error followed by artifact-missing wrappers
    # collapses to error_count == 1; wrappers stay visible but flagged.
    # Build paths from a tempfile root to satisfy the no-hardcoded-paths gate.
    mock_root = str(workspace).replace("/", "\\")
    cascade_output = (
        f"{mock_root}\\MyModule.m\\src\\MyFile.cpp(42): error C2440: cannot convert\n"
        f"# make-ERROR: {mock_root}\\win_b64\\code\\bin\\MyModule.dll: No such file or directory\n"
        f"  # syst-ERROR: {mock_root}\\win_b64\\code\\lib\\MyModule.lib: No such file or directory\n"
    )
    parsed_cascade = parse_mkmk_output(cascade_output)
    check("root cause counted once despite artifact fallout",
          parsed_cascade["error_count"] == 1, str(parsed_cascade))
    check("artifact wrappers flagged cascade",
          parsed_cascade["cascade_count"] == 2, str(parsed_cascade))
    check("cascade wrappers stay visible in errors list",
          len(parsed_cascade["errors"]) == 3, str(parsed_cascade["errors"]))
    check("cascade flag survives to_dict",
          sum(1 for e in parsed_cascade["errors"] if e.get("cascade")) == 2,
          str(parsed_cascade["errors"]))
    check("wrapper count kept for build verdict",
          parsed_cascade["wrapper_error_count"] == 2, str(parsed_cascade))

    # A wrapper that is NOT artifact fallout stays counted even when a root
    # cause exists (distinct config/license failure, not a missing artifact).
    mixed_output = (
        "file.cpp(10): error C2143: syntax error\n"
        "# mkmk-ERROR: license checkout failed\n"
    )
    parsed_mixed = parse_mkmk_output(mixed_output)
    check("non-artifact wrapper stays counted alongside root cause",
          parsed_mixed["error_count"] == 2 and parsed_mixed["cascade_count"] == 0,
          str(parsed_mixed))

    # P0: GBK mkmk/MSVC output decodes to readable Chinese, not U+FFFD.
    gbk_line = (b"MyFile.cpp(42): error C2440: \xce\xde\xb7\xa8\xb4\xd3"
                b" 'const char *' \xd7\xaa\xbb\xbb\xce\xaa 'char *'")
    decoded_gbk = build_module._decode_mkmk_output(gbk_line)
    check("gbk mkmk output decodes to readable Chinese",
          "\u65e0\u6cd5\u4ece" in decoded_gbk
          and "\u8f6c\u6362\u4e3a" in decoded_gbk
          and "\ufffd" not in decoded_gbk, decoded_gbk)
    utf8_text = "note: \u65e0\u6cd5\u4ece (utf-8)"
    check("utf-8 output still decodes as utf-8",
          build_module._decode_mkmk_output(utf8_text.encode("utf-8")) == utf8_text)
    check("empty output decodes to empty string",
          build_module._decode_mkmk_output(b"") == "")

    # P2: C4819 codepage warnings are quarantined out of actionable warnings —
    # they fire once per non-ASCII source file on every build and drown real
    # warnings, but they are environment noise, not defects to fix in code.
    c4819_output = (
        f"{mock_root}\\MyModule.m\\src\\Alpha.cpp(1): warning C4819: codepage 936 cannot represent a character\n"
        f"{mock_root}\\MyModule.m\\src\\Beta.cpp(1): warning C4819: codepage 936 cannot represent a character\n"
        f"{mock_root}\\MyModule.m\\src\\Alpha.cpp(9): warning C4819: codepage 936 cannot represent a character\n"
        f"{mock_root}\\MyModule.m\\src\\Alpha.cpp(42): warning C4101: 'unused' : unreferenced local variable\n"
    )
    parsed_cp = parse_mkmk_output(c4819_output)
    check("C4819 quarantined out of actionable warnings",
          parsed_cp["warning_count"] == 1
          and all(w["code"] != "C4819" for w in parsed_cp["warnings"]), str(parsed_cp))
    check("codepage warnings counted separately",
          parsed_cp["codepage_warning_count"] == 3, str(parsed_cp))
    check("codepage warning files deduped and sorted",
          parsed_cp["codepage_warning_files"] == ["src/Alpha.cpp", "src/Beta.cpp"],
          str(parsed_cp["codepage_warning_files"]))
    check("actionable warning still surfaces",
          parsed_cp["warnings"][0]["code"] == "C4101", str(parsed_cp["warnings"]))

    from parser import MkmkParser
    summary_parser = MkmkParser()
    summary_parser.parse(c4819_output)
    summary_text = summary_parser.get_summary()
    # Trailer must stay GBK-encodable: the ✓/✗ glyphs in get_summary crash
    # print() on a zh-CN console, so sanitize before handing it to check().
    check("summary counts codepage apart from warnings",
          "1 warning(s)" in summary_text and "3 codepage C4819" in summary_text,
          summary_text.replace("✓", "ok:").replace("✗", "fail:"))
    clean_summary = MkmkParser()
    clean_summary.parse(f"{mock_root}\\MyModule.m\\src\\Alpha.cpp(1): warning C4819: codepage 936\n")
    clean_text = clean_summary.get_summary()
    check("codepage-only output still summarizes as successful",
          clean_text.startswith("✓ Build successful"),
          clean_text.replace("✓", "ok:").replace("✗", "fail:"))

    # Build verification must reject stale or implausible target DLLs.
    bin_dir = workspace / "win_b64" / "code" / "bin"
    bin_dir.mkdir(parents=True)
    target_dll = bin_dir / "TargetModule.dll"
    target_dll.write_bytes(b"x" * 2048)
    build_start = datetime.now()
    stale_time = (build_start - timedelta(minutes=5)).timestamp()
    os.utime(target_dll, (stale_time, stale_time))
    stale_verify = verify_build(
        workspace,
        expected_modules=["TargetModule"],
        build_start_time=build_start,
    )
    check("stale target DLL fails verification", not stale_verify["ok"], str(stale_verify["issues"]))
    check("stale DLL issue is explicit", any("stale" in issue.lower() for issue in stale_verify["issues"]), str(stale_verify["issues"]))

    fresh_time = (build_start + timedelta(seconds=1)).timestamp()
    os.utime(target_dll, (fresh_time, fresh_time))
    target_dll.write_bytes(b"tiny")
    tiny_verify = verify_build(
        workspace,
        expected_modules=["TargetModule"],
        build_start_time=build_start,
    )
    check("tiny target DLL fails verification", not tiny_verify["ok"], str(tiny_verify["issues"]))

    # Mixed module results must identify only stale/missing targets.
    fresh_dll = bin_dir / "FreshModule.dll"
    stale_dll = bin_dir / "StaleModule.dll"
    fresh_dll.write_bytes(b"f" * 2048)
    stale_dll.write_bytes(b"s" * 2048)
    os.utime(fresh_dll, (fresh_time, fresh_time))
    os.utime(stale_dll, (stale_time, stale_time))
    mixed_verify = verify_build(
        workspace,
        expected_modules=["FreshModule", "StaleModule", "MissingModule"],
        build_start_time=build_start,
    )
    mixed_issues = mixed_verify["issues"]
    check("mixed module verification fails", not mixed_verify["ok"], str(mixed_issues))
    check("mixed verification identifies stale module", any("StaleModule.dll" in issue and "stale" in issue for issue in mixed_issues), str(mixed_issues))
    check("mixed verification accepts fresh module", not any("FreshModule.dll" in issue for issue in mixed_issues), str(mixed_issues))
    check("mixed verification identifies missing module", any("missingmodule.dll" in issue.lower() and "not found" in issue.lower() for issue in mixed_issues), str(mixed_issues))

    # The final cache and log must reflect post-build verification, not pre-verification success.
    build_ws = workspace / "mock_build"
    build_fw = build_ws / "MockFramework.edu"
    build_mod = build_fw / "MockModule.m"
    (build_fw / "IdentityCard").mkdir(parents=True)
    (build_fw / "IdentityCard" / "IdentityCard.h").write_text("// identity", encoding="utf-8")
    (build_fw / "Imakefile.mk").write_text("", encoding="utf-8")
    build_mod.mkdir()
    (build_mod / "Imakefile.mk").write_text("BUILT_OBJECT_TYPE=SHARED LIBRARY", encoding="utf-8")

    class MemoryLogger:
        instances = []

        def __init__(self, *_args, **_kwargs):
            self.lines = []
            self.__class__.instances.append(self)

        def clear(self):
            self.lines.clear()

        def write(self, message):
            self.lines.append(str(message))

    class MemoryCache:
        instances = []

        def __init__(self, *_args, **_kwargs):
            self.data = {}
            self.__class__.instances.append(self)

        def load(self):
            return dict(self.data)

        def save(self, data):
            self.data = dict(data)

    class FakeEnvironment:
        _build_bat = None

        def load_config(self):
            return True

        def build_time_command(self, _workspace, _options):
            return ["fake-build"], "fake-build"

    # Real subprocess.run without text=True yields bytes — the mock must too,
    # otherwise build output decoding is exercised against the wrong type.
    # C4819 lines ride along to prove build_result quarantines them (P2).
    fake_process = SimpleNamespace(
        returncode=0,
        stdout=(
            f"{mock_root}\\MockModule.m\\src\\Noise.cpp(1): warning C4819: codepage 936\n"
            f"{mock_root}\\MockModule.m\\src\\Noise.cpp(5): warning C4819: codepage 936\n"
            "build completed"
        ).encode("utf-8"),
        stderr=b"",
    )
    failed_verification = {"ok": False, "issues": ["MockModule.dll: stale DLL"]}
    with patch.object(build_module, "Logger", MemoryLogger), \
            patch.object(build_module, "Cache", MemoryCache), \
            patch.object(build_module, "CAAEnvironment", FakeEnvironment), \
            patch.object(build_module, "setup_prerequisite_path", return_value={"status": "success"}), \
            patch.object(build_module.subprocess, "run", return_value=fake_process), \
            patch.object(build_module, "verify_build", return_value=failed_verification), \
            patch.object(build_module, "sync_runtime_view", return_value={"synced": [], "errors": [], "ok": True}):
        # skip_gate: this fixture is intentionally minimal (no src/) and
        # targets post-build verification, not the pre-build gate.
        mocked_build = build_module.build_workspace(build_ws, skip_gate=True)

    final_cache = MemoryCache.instances[-1].data
    final_log = MemoryLogger.instances[-1].lines
    check("verification failure changes returned build status", mocked_build["status"] == "failed_verification", str(mocked_build))
    check("final cache stores verification failure", final_cache.get("status") == "failed_verification", str(final_cache))
    check("final cache preserves prerequisite workspace", final_cache.get("prereq_workspace") == str(build_ws), str(final_cache))
    check("final build log stores verification failure", any("Status: failed_verification" in line for line in final_log), str(final_log))

    successful_verification = {"ok": True, "issues": [], "dll_count": 1, "dlls": [{"name": "MockModule.dll"}]}
    MemoryLogger.instances.clear()
    MemoryCache.instances.clear()
    with patch.object(build_module, "Logger", MemoryLogger), \
            patch.object(build_module, "Cache", MemoryCache), \
            patch.object(build_module, "CAAEnvironment", FakeEnvironment), \
            patch.object(build_module, "setup_prerequisite_path", return_value={"status": "success"}), \
            patch.object(build_module.subprocess, "run", return_value=fake_process), \
            patch.object(build_module, "verify_build", return_value=successful_verification), \
            patch.object(build_module, "sync_runtime_view", return_value={"synced": [], "errors": [], "ok": True}):
        # skip_gate: intentionally minimal fixture (see above).
        successful_build = build_module.build_workspace(build_ws, skip_gate=True)
    check("successful build returns verification evidence", successful_build.get("verification") == successful_verification, str(successful_build))
    check("successful cache stores verification evidence", MemoryCache.instances[-1].data.get("verification") == successful_verification, str(MemoryCache.instances[-1].data))
    check("build result quarantines C4819 noise",
          successful_build.get("codepage_warning_count") == 2
          and successful_build.get("codepage_warning_files") == ["src/Noise.cpp"]
          and successful_build.get("warning_count") == 0, str(successful_build))

    # Repair must diagnose the output returned by this build, not stale cache data.
    repair_ws = workspace / "repair"
    repair_ws.mkdir()
    Cache("build.json", workspace_root=repair_ws).save({
        "output": "old.cpp(1): error C2143: stale cached failure"
    })
    current_build = {
        "status": "failed",
        "output": "current.cpp(7): error C1083: Cannot open include file: 'Current.h'",
        "error_count": 1,
    }
    repair_loop = RepairLoop(repair_ws, with_build=True)
    with patch("build.build_workspace", return_value=current_build):
        build_diagnosis = repair_loop._diagnose_build()
    build_files = [d.get("file") for d in build_diagnosis["diagnostics"]]
    check("repair uses current build output", "current.cpp" in build_files, str(build_diagnosis))
    check("repair ignores stale cached output", "old.cpp" not in build_files, str(build_diagnosis))

    failed_without_details = {"status": "error", "message": "tool invocation failed", "output": ""}
    with patch("build.build_workspace", return_value=failed_without_details):
        failed_diagnosis = repair_loop._diagnose_build()
    check("unparsed build failure remains diagnostic", failed_diagnosis["total"] == 1, str(failed_diagnosis))

    # Static-only repair results must never imply that build verification ran.
    static_clean = RepairLoop(repair_ws, with_build=False)
    static_clean._diagnose_static = lambda: {"total": 0, "auto_fixable": 0, "diagnostics": []}
    clean_result = static_clean.run()
    check("static clean message discloses no build", "static analysis only" in clean_result.message.lower(), clean_result.message)

    static_fix = RepairLoop(repair_ws, with_build=False)
    static_fix._diagnose_static = lambda: {
        "total": 1,
        "auto_fixable": 1,
        "diagnostics": [{
            "severity": "error",
            "message": "missing generated file",
            "file": "generated.h",
            "auto_fixable": True,
            "fix_plan": {
                "action": "create_file",
                "file": "generated.h",
                "line": "// generated",
            },
        }],
    }
    fixed_result = static_fix.run()
    check("static fix succeeds", fixed_result.state == RepairState.FIXED, fixed_result.message)
    check("static fix discloses no build", "build verification was not run" in fixed_result.message.lower(), fixed_result.message)
    # A fix that applied must hand back the real rollback id minted by apply()
    # (BackupManager), never a synthetic value.
    check("static fix returns the real rollback id",
          len(fixed_result.backup_ids) == 1 and fixed_result.backup_ids[0],
          str(fixed_result.backup_ids))

    # delete_file: diagnostics._check_orphaned emits FixAction.DELETE_FILE with
    # auto_fixable=True. Without a delete branch the ChangeSet came back empty,
    # so the run burned all retries and escalated while the orphan survived.
    orphan_dir = repair_ws / "TestFW.edu" / "TestMod.m" / "src"
    orphan_dir.mkdir(parents=True)
    orphan = orphan_dir / "Orphan.cpp"
    orphan.write_text("// orphan content\n", encoding="utf-8")

    delete_fix = RepairLoop(repair_ws, with_build=False)
    delete_fix._diagnose_static = lambda: {
        "total": 1,
        "auto_fixable": 1,
        "diagnostics": [{
            "severity": "warning",
            "message": f"orphaned file {orphan.name}",
            "file": str(orphan),
            "auto_fixable": True,
            "fix_plan": {
                "action": "delete_file",
                "file": str(orphan),
                "description": f"Remove orphaned file {orphan.name}",
            },
        }],
    }
    delete_result = delete_fix.run()
    check("delete_file fix reaches FIXED",
          delete_result.state == RepairState.FIXED, delete_result.message)
    check("delete_file actually removes the orphan", not orphan.exists(),
          f"exists={orphan.exists()}")
    check("delete_file records a rollback id",
          len(delete_result.backup_ids) == 1, str(delete_result.backup_ids))

    # Deleting is the one fix with no in-memory fallback, so the persisted
    # BackupManager entry must be able to bring the file back.
    if delete_result.backup_ids:
        with patch.object(build_module, "verify_build", return_value={}):
            restored = backup_module.rollback_operation(
                repair_ws, delete_result.backup_ids[0]
            )
        check("delete_file rollback restores the orphan",
              restored.get("status") == "success" and orphan.exists()
              and orphan.read_text(encoding="utf-8") == "// orphan content\n",
              str(restored.get("status")))
    else:
        check("delete_file rollback restores the orphan", False,
              "no rollback id to restore from")

    # Escalation must not advertise a restore path when nothing was applied.
    noop_fix = RepairLoop(repair_ws, with_build=False)
    noop_fix._diagnose_static = lambda: {
        "total": 1, "auto_fixable": 1,
        "diagnostics": [{
            "severity": "error", "message": "already there", "file": "generated.h",
            "auto_fixable": True,
            # create_file on an existing path yields an empty ChangeSet.
            "fix_plan": {"action": "create_file", "file": "generated.h", "line": "x"},
        }],
    }
    noop_result = noop_fix.run()
    check("empty-ChangeSet run applies nothing so reports no rollback points",
          noop_result.backup_ids == [], str(noop_result.backup_ids))
    check("no-rollback escalation omits the restore hint",
          "backup_id=" not in noop_result.message
          and "nothing to roll back" in noop_result.message.lower(),
          noop_result.message)

    # Addins are neither interfaces nor generic components; workbench names are unique.
    analyzer_fw = workspace / "AnalyzerFramework.edu"
    (analyzer_fw / "IdentityCard").mkdir(parents=True)
    (analyzer_fw / "IdentityCard" / "IdentityCard.h").write_text("", encoding="utf-8")
    analyzer_mod = analyzer_fw / "AnalyzerModule.m"
    local_interfaces = analyzer_mod / "LocalInterfaces"
    src_dir = analyzer_mod / "src"
    local_interfaces.mkdir(parents=True)
    src_dir.mkdir()
    (analyzer_mod / "Imakefile.mk").write_text("BUILT_OBJECT_TYPE=SHARED LIBRARY", encoding="utf-8")
    (local_interfaces / "SampleWorkbenchAddin.h").write_text(
        "class SampleWorkbenchAddin : public CATBaseUnknown { CATDeclareClass; };",
        encoding="utf-8",
    )
    (src_dir / "SampleWorkbench.cpp").write_text(
        "CATCmdWorkbench SampleWorkbench;", encoding="utf-8"
    )
    (src_dir / "SampleWorkbenchAddin.cpp").write_text(
        "CATIAfrGeneralWksAddin CreateCommands CreateToolbars", encoding="utf-8"
    )
    analyzer_snapshot = WorkspaceAnalyzer(workspace).analyze()
    analyzed_fw = next(fw for fw in analyzer_snapshot.frameworks if fw.name == "AnalyzerFramework.edu")
    analyzed_mod = analyzed_fw.modules[0]
    check("addin is not classified as interface", "SampleWorkbenchAddin" not in [i.name for i in analyzed_mod.interfaces])
    check("addin is not classified as component", "SampleWorkbenchAddin" not in [c.name for c in analyzed_mod.components])
    workbench_names = [wb.name for wb in analyzed_fw.workbenches]
    check("workbench names are unique", len(workbench_names) == len(set(workbench_names)), str(workbench_names))
finally:
    shutil.rmtree(workspace, ignore_errors=True)

# ── gc_stale_buckets: workspace bucket retention ─────────────────────────
# Buckets accumulate forever otherwise (662 stale ones pruned on 2026-07-31).
gc_root = Path(tempfile.mkdtemp(prefix="cade_gc_test_"))
try:
    stale = gc_root / "deadbeef"
    stale.mkdir()
    (stale / "build.log").write_text("old", encoding="utf-8")
    past = (datetime.now() - timedelta(days=31)).timestamp()
    os.utime(stale / "build.log", (past, past))
    os.utime(stale, (past, past))
    fresh = gc_root / "cafef00d"
    fresh.mkdir()
    (fresh / "build.log").write_text("new", encoding="utf-8")
    (gc_root / "index.json").write_text("{}", encoding="utf-8")  # non-bucket file

    removed = gc_stale_buckets(gc_root)
    check("gc removes bucket idle > 30 days", removed == 1 and not stale.exists())
    check("gc keeps fresh bucket", fresh.exists())
    check("gc never touches non-bucket files", (gc_root / "index.json").exists())
    check("gc throttles rescan within 24h", gc_stale_buckets(gc_root) == 0)
    check("gc never raises on missing root",
          gc_stale_buckets(gc_root / "nonexistent_xyz") == 0)
finally:
    shutil.rmtree(gc_root, ignore_errors=True)

# ── module / .edu path resolution: Runtime View + validate ─────────
path_ws = Path(tempfile.mkdtemp(prefix="cade_path_resolve_"))
try:
    fw = path_ws / "PathFw.edu"
    mod = fw / "PathMod.m"
    (fw / "IdentityCard").mkdir(parents=True)
    (fw / "IdentityCard" / "IdentityCard.h").write_text("// ic", encoding="utf-8")
    (fw / "Imakefile.mk").write_text("", encoding="utf-8")
    mod.mkdir()
    (mod / "Imakefile.mk").write_text("BUILT_OBJECT_TYPE=SHARED LIBRARY", encoding="utf-8")
    msg = fw / "CNext" / "resources" / "msgcatalog"
    (msg / "Simplified_Chinese").mkdir(parents=True)
    (msg / "PathFw.CATNls").write_text("Title=\"PathFw\";\n", encoding="utf-8")
    (msg / "Simplified_Chinese" / "PathFw.CATNls").write_bytes(
        "Title=\"\xb2\xe2\xca\xd4\";\n".encode("latin-1")
    )
    dico_dir = fw / "CNext" / "code" / "dictionary"
    dico_dir.mkdir(parents=True)
    (dico_dir / "PathFw.dico").write_text("PathMod PathMod\n", encoding="utf-8")

    sync_from_mod = build_module.sync_runtime_view(mod)
    nls_en = path_ws / "win_b64" / "resources" / "msgcatalog" / "PathFw.CATNls"
    nls_zh = (
        path_ws / "win_b64" / "resources" / "msgcatalog"
        / "Simplified_Chinese" / "PathFw.CATNls"
    )
    dico_rv = path_ws / "win_b64" / "code" / "dictionary" / "PathFw.dico"
    leaked = mod / "win_b64"
    check("module-scoped sync writes NLS to workspace root",
          nls_en.is_file(), str(sync_from_mod.get("synced", [])))
    check("module-scoped sync includes Simplified_Chinese",
          nls_zh.is_file(), str(sync_from_mod.get("synced", [])))
    check("module-scoped sync writes dico to workspace root", dico_rv.is_file())
    check("module-scoped sync does not create Module.m/win_b64", not leaked.exists())

    shutil.rmtree(path_ws / "win_b64", ignore_errors=True)
    sync_from_edu = build_module.sync_runtime_view(fw)
    check(".edu-scoped sync still lands on workspace root",
          nls_zh.is_file() and not (fw / "win_b64").exists(),
          str(sync_from_edu.get("synced", [])))

    health_edu = build_module.validate_workspace(fw)
    check("validate_workspace(.edu) can_build",
          health_edu.get("can_build") is True, str(health_edu))
    check("validate_workspace(.edu) does not report missing framework",
          not any("No .edu framework found" in i for i in health_edu.get("issues", [])),
          str(health_edu.get("issues", [])))
    health_mod = build_module.validate_workspace(mod)
    check("validate_workspace(.m) still module mode",
          health_mod.get("mode") == "module" and health_mod.get("can_build") is True,
          str(health_mod))
    resolved = build_module._resolve_workspace_root
    check("_resolve_workspace_root(.m) is workspace root", resolved(mod) == path_ws)
    check("_resolve_workspace_root(.edu) is workspace root", resolved(fw) == path_ws)
    check("_resolve_workspace_root(root) is unchanged", resolved(path_ws) == path_ws)
finally:
    shutil.rmtree(path_ws, ignore_errors=True)

# ── backup_id uniqueness: rollback points must never be overwritten ──────
# create_backup() used to slice strftime("%Y%m%d_%H%M%S_%f")[:17], keeping one
# microsecond digit. Every backup made inside the same ~100 ms window got the
# same id, and mkdir(exist_ok=True) silently reused the directory, so an
# earlier rollback point was destroyed while rollback() still reported
# success (restoring an intermediate state).
uniq_ws = Path(tempfile.mkdtemp(prefix="cade_backup_unique_"))
# Hoisted out of the try body so the finally clause can always reach it.
rv_root = Path(tempfile.mkdtemp(prefix="cade_rv_test_"))
try:
    src = uniq_ws / "UniqFW.edu" / "UniqMod.m" / "src"
    src.mkdir(parents=True)
    target = src / "Uniq.CATNls"
    true_original = 'A.Title = "a";\n'
    target.write_text(true_original, encoding="utf-8")

    mgr = BackupManager(uniq_ws)
    burst_ids = [mgr.create_backup(ChangeSet(action=f"burst{i}", description="b"))
                 for i in range(25)]
    check("backup ids are unique across a rapid burst",
          len(set(burst_ids)) == len(burst_ids),
          f"{len(set(burst_ids))} distinct of {len(burst_ids)}")
    check("each burst backup has its own directory",
          len([d for d in mgr.backup_dir.iterdir() if d.is_dir()]) == len(burst_ids),
          f"{len([d for d in mgr.backup_dir.iterdir() if d.is_dir()])} dirs")

    # Two sequential edits to the same file must each keep their own rollback
    # point, and the later one must not hold the earlier one's content.
    snapshots = []
    for content in ['B.Title = "b";', 'C.Title = "c";', 'D.Title = "d";']:
        cs = ChangeSet(action="seq", description="seq")
        cs.add_patch(Patch(file=target, operation="append", target="", content=content))
        snapshots.append(cs.apply(workspace_root=uniq_ws).get("rollback_id"))
    check("sequential backups on one file get distinct ids",
          len(set(snapshots)) == 3, str(snapshots))

    first_saved = (mgr.backup_dir / snapshots[0] / "modified"
                   / "UniqFW.edu" / "UniqMod.m" / "src" / "Uniq.CATNls")
    first_ok = (first_saved.is_file()
                and first_saved.read_text(encoding="utf-8") == true_original)
    check("earliest rollback point still holds the true original", first_ok,
          "" if first_ok else
          ("missing snapshot" if not first_saved.is_file() else "content mismatch"))

    # Roll back the OLDEST id: must restore the original, not an intermediate.
    restored = mgr.rollback(snapshots[0])
    restored_content = target.read_text(encoding="utf-8")
    oldest_ok = restored.get("status") == "success" and restored_content == true_original
    check("rolling back the oldest id restores the true original", oldest_ok,
          "" if oldest_ok else f"status={restored.get('status')} content={restored_content!r}")

    # Deterministic collision: freeze the clock so every call produces the
    # same base id, then verify the suffix loop allocates distinct dirs.
    frozen = datetime(2026, 1, 1, 0, 0, 0, 123456)

    class _FrozenDatetime:
        @staticmethod
        def now():
            return frozen

    with patch.object(backup_module, "datetime", _FrozenDatetime):
        frozen_ids = [
            mgr.create_backup(ChangeSet(action=f"frozen{i}", description="f"))
            for i in range(3)
        ]
    check("same-microsecond backups get suffixes instead of colliding",
          frozen_ids == ["20260101_000000_123456",
                         "20260101_000000_123456_1",
                         "20260101_000000_123456_2"],
          str(frozen_ids))
    check("each suffixed id has its own directory",
          all((mgr.backup_dir / i).is_dir() for i in frozen_ids))
    check("suffixed ids stay valid for _validate_backup_id",
          all(mgr._validate_backup_id(i) is None for i in frozen_ids))
    # ── create_runtime_view() CLI lifecycle ──────────────────────
    # runtime_view.py::create_runtime_view backs `python runtime_view.py
    # --create`. It is a *different* implementation from
    # build.create_runtime_view (which `cade rv` uses and whose finally is
    # already correct). This one writes .mkcreate_output.tmp and
    # .mkcreate_run.bat into the workspace itself, and its cleanup used to sit
    # inside the try body — so the timeout and exception handlers returned
    # straight past it and left both files in the user's workspace.
    # These fixtures live outside `workspace`: its own finally (L626) already
    # removed the root, so anything re-created under it survived the run.
    mk_ws = rv_root / "runtime_view_ws"
    fake_catia = rv_root / "fake_catia"
    mk_cmd_dir = fake_catia / "win_b64" / "code" / "command"
    mk_cmd_dir.mkdir(parents=True, exist_ok=True)
    (mk_cmd_dir / "mkinit.bat").write_text("@echo off\r\n", encoding="ascii")
    (mk_cmd_dir / "mkCreateRuntimeView.bat").write_text(
        "@echo off\r\n", encoding="ascii"
    )

    # Same tool layout minus mkinit.bat, to exercise the early return that
    # fires before the temp paths are assigned.
    noinit_catia = rv_root / "fake_catia_noinit"
    noinit_dir = noinit_catia / "win_b64" / "code" / "command"
    noinit_dir.mkdir(parents=True, exist_ok=True)
    (noinit_dir / "mkCreateRuntimeView.bat").write_text(
        "@echo off\r\n", encoding="ascii"
    )

    class _SilentLogger:
        def __init__(self, *args, **kwargs):
            pass

        def write(self, *args, **kwargs):
            pass

        def clear(self):
            pass

    class _SilentCache:
        def __init__(self, *args, **kwargs):
            pass

        def save(self, *args, **kwargs):
            pass

    def _run_runtime_view(run_patch, install):
        shutil.rmtree(mk_ws, ignore_errors=True)
        mk_ws.mkdir(parents=True, exist_ok=True)

        class _Env:
            config = {"CATIA_INSTALL": install}

            def get_architecture(self):
                return "win_b64"

            def initialize(self):
                return {"ok": True}

        with patch.object(runtime_view_module, "CAAEnvironment", _Env), patch.object(
            runtime_view_module, "Logger", _SilentLogger
        ), patch.object(runtime_view_module, "Cache", _SilentCache), patch.object(
            runtime_view_module.subprocess, "run", **run_patch
        ):
            return runtime_view_module.create_runtime_view(mk_ws)

    def _mkcreate_residue():
        return [
            name
            for name in (".mkcreate_output.tmp", ".mkcreate_run.bat")
            if (mk_ws / name).exists()
        ]

    def _fake_success(*_args, **_kwargs):
        # Stand in for mkCreateRuntimeView actually producing the view.
        # subprocess.run's argv is positional, hence *args.
        (mk_ws / "win_b64").mkdir(exist_ok=True)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    ok_result = _run_runtime_view({"side_effect": _fake_success}, str(fake_catia))
    check("runtime_view success reports success",
          ok_result.get("status") == "success", str(ok_result.get("status")))
    check("runtime_view success leaves no .mkcreate_* files",
          _mkcreate_residue() == [], str(_mkcreate_residue()))

    timeout_result = _run_runtime_view(
        {"side_effect": subprocess.TimeoutExpired("cmd", 300)}, str(fake_catia)
    )
    check("runtime_view timeout keeps its timeout status",
          timeout_result.get("status") == "timeout",
          str(timeout_result.get("status")))
    check("runtime_view timeout leaves no .mkcreate_* files",
          _mkcreate_residue() == [], str(_mkcreate_residue()))

    boom_result = _run_runtime_view(
        {"side_effect": RuntimeError("boom")}, str(fake_catia)
    )
    check("runtime_view exception keeps its error status",
          boom_result.get("status") == "error", str(boom_result.get("status")))
    check("runtime_view exception leaves no .mkcreate_* files",
          _mkcreate_residue() == [], str(_mkcreate_residue()))

    # Early return fires before tmpfile/batfile are assigned; the finally
    # guard must tolerate those still being None instead of raising.
    early_result = _run_runtime_view({"side_effect": _fake_success}, str(noinit_catia))
    check("runtime_view missing mkinit.bat returns error, not a crash",
          early_result.get("status") == "error",
          str(early_result.get("message"))[:70])
    check("runtime_view missing mkinit.bat leaves no .mkcreate_* files",
          _mkcreate_residue() == [], str(_mkcreate_residue()))
finally:
    shutil.rmtree(uniq_ws, ignore_errors=True)
    shutil.rmtree(rv_root, ignore_errors=True)

# ── merge_changesets: contract alignment & data integrity (R-1) ───────────
# 1. Binary payloads were dropped by merge_changesets(), leading to apply() rejection.
# 2. created + patch was falsely flagged as conflict.
# 3. Contributor metadata was lost.
# 4. Same-content created across ChangeSets is idempotent.
merge_ws = Path(tempfile.mkdtemp(prefix="cade_merge_cs_"))
try:
    # (1) Binary payload preservation through merge_changesets & disk write
    bin_cs1 = ChangeSet(action="cmd", description="create command")
    bin_file = merge_ws / "icon.bmp"
    bin_data = b"\x42\x4d\x1e\x00\x00\x00\x00\x00\x00\x00\x1a\x00\x00\x00"
    bin_cs1.add_create_binary(bin_file, bin_data)
    bin_cs2 = ChangeSet(action="doc", description="docs")
    bin_cs2.add_create(merge_ws / "doc.txt", "doc text")

    merged_bin = merge_changesets(bin_cs1, bin_cs2)
    check("merge_changesets carries over _binary payload",
          str(bin_file) in merged_bin._binary and merged_bin._binary[str(bin_file)] == bin_data)
    bin_apply = merged_bin.apply(workspace_root=merge_ws)
    check("merged binary changeset applies successfully",
          bin_apply["status"] == "applied", str(bin_apply.get("errors", [])))
    check("merged binary file written to disk",
          bin_file.is_file() and bin_file.read_bytes() == bin_data)

    # (2) created + patch is valid and does not raise conflict
    patch_file = merge_ws / "patched.txt"
    cs_create = ChangeSet(action="create", description="create file")
    cs_create.add_create(patch_file, "line1\nline2\n")
    cs_patch = ChangeSet(action="patch", description="patch file")
    cs_patch.add_patch(Patch(file=patch_file, operation="append", target="", content="line3\n"))

    merged_patch = merge_changesets(cs_create, cs_patch)
    check("merge_changesets allows created + patch without conflict",
          "merge_conflicts" not in merged_patch.metadata,
          str(merged_patch.metadata.get("merge_conflicts", [])))
    patch_apply = merged_patch.apply(workspace_root=merge_ws)
    check("merged created + patch applies cleanly",
          patch_apply["status"] == "applied", str(patch_apply.get("errors", [])))
    check("patched file contains both original and appended content",
          patch_file.is_file()
          and "line1" in patch_file.read_text(encoding="utf-8")
          and "line3" in patch_file.read_text(encoding="utf-8"))

    # (3) Contributor metadata preservation
    cs_meta1 = ChangeSet(action="c1", description="c1")
    cs_meta1.merge_metadata(author="Alice", generator="v1")
    cs_meta2 = ChangeSet(action="c2", description="c2")
    cs_meta2.merge_metadata(tool="CADETool", generator="v1")

    merged_meta = merge_changesets(cs_meta1, cs_meta2)
    check("merge_changesets preserves contributor metadata keys",
          merged_meta.metadata.get("author") == "Alice" and
          merged_meta.metadata.get("tool") == "CADETool" and
          merged_meta.metadata.get("generator") == "v1",
          str(merged_meta.metadata))

    # (4) Idempotent on same-content created vs conflict on differing content
    cs_idem1 = ChangeSet(action="i1", description="i1")
    cs_idem2 = ChangeSet(action="i2", description="i2")
    idem_path = merge_ws / "same.txt"
    cs_idem1.add_create(idem_path, "identical")
    cs_idem2.add_create(idem_path, "identical")
    merged_idem = merge_changesets(cs_idem1, cs_idem2)
    check("same-content created across changesets is idempotent",
          "merge_conflicts" not in merged_idem.metadata and
          merged_idem.created.get(str(idem_path)) == "identical",
          str(merged_idem.metadata.get("merge_conflicts", [])))
finally:
    shutil.rmtree(merge_ws, ignore_errors=True)

print(f"\nProduction regressions: {passed}/{total}")
if failures:
    print("Failures:")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)
print("All production regression tests passed")
sys.exit(0)
