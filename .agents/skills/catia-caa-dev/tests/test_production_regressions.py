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

from actions import ActionContext, create_framework, add_command_to_workbench
from analyzer import WorkspaceAnalyzer
import backup as backup_module
import build as build_module
import cade as cade_module
from backup import BackupManager
from build import verify_build
from changeset import ChangeSet, Patch, merge_changesets
from diagnostics import DiagnosticsEngine
from generator import TemplateGenerator
from intents.commands import create_executable_command
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

    # (5) R-1-B: Differing binary payloads on same path keep first and warn
    bin_diff_1 = ChangeSet(action="b1", description="b1")
    bin_diff_2 = ChangeSet(action="b2", description="b2")
    diff_bin_file = merge_ws / "conflict_icon.bmp"
    data1 = b"\x42\x4d\x01\x01"
    data2 = b"\x42\x4d\x02\x02"
    bin_diff_1.add_create_binary(diff_bin_file, data1)
    bin_diff_2.add_create_binary(diff_bin_file, data2)
    merged_diff_bin = merge_changesets(bin_diff_1, bin_diff_2)
    check("differing binary payloads keeps first queued bytes",
          merged_diff_bin._binary.get(str(diff_bin_file)) == data1)
    check("differing binary payloads emits conflict warning",
          any("binary conflict" in w for w in merged_diff_bin.warnings),
          str(merged_diff_bin.warnings))

    # (6) R-1-B: Contributor metadata key conflict keeps first and warns
    meta_c1 = ChangeSet(action="m1", description="m1")
    meta_c2 = ChangeSet(action="m2", description="m2")
    meta_c1.merge_metadata(priority="high")
    meta_c2.merge_metadata(priority="low")
    merged_meta_conflict = merge_changesets(meta_c1, meta_c2)
    check("metadata conflict keeps first queued value",
          merged_meta_conflict.metadata.get("priority") == "high",
          str(merged_meta_conflict.metadata))
    check("metadata conflict emits warning",
          any("metadata conflict" in w for w in merged_meta_conflict.warnings),
          str(merged_meta_conflict.warnings))

    # (7) R-1-B: Immutability of input changesets (pure function semantics)
    orig_c1 = ChangeSet(action="orig1", description="orig1")
    orig_c1.add_create(merge_ws / "f1.txt", "content1")
    orig_c1.merge_metadata(k1="v1")
    orig_c2 = ChangeSet(action="orig2", description="orig2")
    orig_c2.add_create(merge_ws / "f2.txt", "content2")
    orig_c2.merge_metadata(k2="v2")

    c1_created_before = dict(orig_c1.created)
    c1_meta_before = dict(orig_c1.metadata)
    c2_created_before = dict(orig_c2.created)

    _ = merge_changesets(orig_c1, orig_c2)

    check("merge_changesets does not mutate input cs1 created",
          orig_c1.created == c1_created_before)
    check("merge_changesets does not mutate input cs1 metadata",
          orig_c1.metadata == c1_meta_before)
    check("merge_changesets does not mutate input cs2 created",
          orig_c2.created == c2_created_before)

    # (8) R-1-B: Cross-ChangeSet created vs modified conflict
    cs_cross_create = ChangeSet(action="cr", description="cr")
    cs_cross_modify = ChangeSet(action="mo", description="mo")
    cross_file = merge_ws / "cross.txt"
    cs_cross_create.add_create(cross_file, "created content")
    cs_cross_modify.add_modify(cross_file, "modified content")
    merged_cross = merge_changesets(cs_cross_create, cs_cross_modify)
    check("cross-changeset created + modified flags conflict",
          any("conflict on" in c.lower() for c in merged_cross.metadata.get("merge_conflicts", [])),
          str(merged_cross.metadata.get("merge_conflicts", [])))

    # (9) R-1-B: Inheritance of existing merge_conflicts from inputs
    cs_with_conflict = ChangeSet(action="conflicted", description="conflicted")
    cs_with_conflict.metadata["merge_conflicts"] = ["prior conflict on file.txt"]
    cs_normal = ChangeSet(action="norm", description="norm")
    merged_inherited = merge_changesets(cs_with_conflict, cs_normal)
    check("existing merge_conflicts carried over without loss",
          "prior conflict on file.txt" in merged_inherited.metadata.get("merge_conflicts", []),
          str(merged_inherited.metadata.get("merge_conflicts", [])))
finally:
    shutil.rmtree(merge_ws, ignore_errors=True)

# ── add_command_to_workbench: decoupled 4-param Header & Pre-validation (R-2-C) ──
# S1 (0 HeaderClass): Derives AddinClassHeader + injects MacDeclareHeader + 4-param registration
# S2 (1 HeaderClass): Reuses existing HeaderClass, does not duplicate MacDeclareHeader
# S3 (>1 HeaderClass): Multiple MacDeclareHeader declarations -> refuses to guess, zero mutations
# S4 (完全重复注册): Same (HeaderClass, HeaderID, LoadName, ClassName) -> idempotent, no modifications
# S5 (同 identity 异 payload): Same (HeaderClass, HeaderID) with different LoadName/ClassName -> conflict error
# S6 (Metadata E2E): create_executable_command full flow carries load_name/class_name/module/command
# S7 (Orchestrator Pre-validation): Pre-validation Gate fails before any mutation; ChangeSet is None / empty
# S8 (External Header 隔离): Addin source contains NO #include "{Command}Header.h"
# S9 (Lexical false-positive): Comments & string literals do not trigger false declarations or conflicts
# S10 (created/modified/disk 三来源): Correctly reads from and writes to disk, cs.modified, and cs.created
wb_ws = Path(tempfile.mkdtemp(prefix="cade_wb_test_"))
try:
    fw_dir = wb_ws / "TestFW.edu"
    (fw_dir / "IdentityCard").mkdir(parents=True)
    (fw_dir / "IdentityCard" / "IdentityCard.h").write_text("// ic", encoding="utf-8")
    (fw_dir / "Imakefile.mk").write_text("", encoding="utf-8")

    mod_dir = fw_dir / "TestMod.m"
    src_dir = mod_dir / "src"
    src_dir.mkdir(parents=True)
    (mod_dir / "Imakefile.mk").write_text("BUILT_OBJECT_TYPE=SHARED LIBRARY", encoding="utf-8")

    # (1) Existing disk command
    (src_dir / "DiskCmd.cpp").write_text(
        "CATStateCommand BuildGraph\n", encoding="utf-8"
    )

    # Workbench with Addin source (0 headers declared)
    addin_cpp = src_dir / "SampleWorkbenchAddin.cpp"
    addin_initial = (
        '#include "SampleWorkbenchAddin.h"\n'
        '#include <iostream>\n\n'
        'CATIAfrGeneralWksAddin\n\n'
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {\n'
        '}\n'
    )
    addin_cpp.write_text(addin_initial, encoding="utf-8")

    ctx = ActionContext(wb_ws)

    # ── S1: 0 HeaderClass ──
    r1 = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", load_name="TestMod")
    check("S1: add_command_to_workbench status is success/pending",
          r1.get("status") in ("success", "pending"), str(r1))
    cs1_mod = r1.get("changeset", {}).get("modified", {})
    new_addin_1 = cs1_mod.get(str(addin_cpp), "")
    check("S1: derives and injects MacDeclareHeader(SampleWorkbenchAddinHeader)",
          "MacDeclareHeader(SampleWorkbenchAddinHeader);" in new_addin_1, new_addin_1)
    check("S1: registers 4-param header in CreateCommands()",
          'new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);' in new_addin_1, new_addin_1)
    check("S1: declaration inserted below includes",
          '#include <iostream>\n\nMacDeclareHeader(SampleWorkbenchAddinHeader);' in new_addin_1, new_addin_1)

    # ── S2: 1 HeaderClass ──
    addin_single_hdr = (
        '#include "SampleWorkbenchAddin.h"\n'
        '#include "CATCommandHeader.h"\n\n'
        'CATIAfrGeneralWksAddin\n\n'
        'MacDeclareHeader(CustomWksHeader);\n\n'
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {\n'
        '}\n'
    )
    addin_cpp.write_text(addin_single_hdr, encoding="utf-8")
    ctx.refresh(force=True)
    r2 = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", load_name="TestMod")
    check("S2: status is success/pending", r2.get("status") in ("success", "pending"), str(r2))
    new_addin_2 = r2.get("changeset", {}).get("modified", {}).get(str(addin_cpp), "")
    check("S2: reuses existing CustomWksHeader in registration",
          'new CustomWksHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);' in new_addin_2, new_addin_2)
    check("S2: does not inject duplicate MacDeclareHeader",
          new_addin_2.count("MacDeclareHeader") == 1, new_addin_2)

    # ── S3: >1 HeaderClass ──
    addin_multi_hdr = (
        '#include "SampleWorkbenchAddin.h"\n'
        '#include "CATCommandHeader.h"\n\n'
        'CATIAfrGeneralWksAddin\n\n'
        'MacDeclareHeader(HeaderOne);\n'
        'MacDeclareHeader(HeaderTwo);\n\n'
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {\n'
        '}\n'
    )
    addin_cpp.write_text(addin_multi_hdr, encoding="utf-8")
    ctx.refresh(force=True)
    r3 = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", load_name="TestMod")
    check("S3: multiple declarations return error", r3.get("status") == "error", str(r3))
    check("S3: error message explains multiple declarations",
          "multiple MacDeclareHeader" in r3.get("message", ""), r3.get("message", ""))
    check("S3: no changeset modifications returned",
          r3.get("changeset") is None, str(r3))

    # ── S4: 完全重复注册 (Idempotency) ──
    addin_with_reg = (
        '#include "SampleWorkbenchAddin.h"\n'
        '#include "CATCommandHeader.h"\n\n'
        'CATIAfrGeneralWksAddin\n\n'
        'MacDeclareHeader(SampleWorkbenchAddinHeader);\n\n'
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {\n'
        '}\n'
    )
    addin_cpp.write_text(addin_with_reg, encoding="utf-8")
    ctx.refresh(force=True)
    r4 = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", load_name="TestMod")
    check("S4: idempotent call succeeds/pending", r4.get("status") in ("success", "pending"), str(r4))
    r4_mod = r4.get("changeset", {}).get("modified", {})
    check("S4: identical registration produces no modifications",
          str(addin_cpp) not in r4_mod, str(r4_mod))

    # ── S5: 同 identity 异 payload (Conflict) ──
    # Case A: Different LoadName
    r5a = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", load_name="DifferentMod")
    check("S5a: different LoadName returns error", r5a.get("status") == "error", str(r5a))
    check("S5a: error reports conflict", "conflict" in r5a.get("message", "").lower(), r5a.get("message", ""))

    # Case B: Different ClassName
    cs_diff_cls = ChangeSet(action="diff", description="diff")
    cs_diff_cls.merge_metadata(class_name="DifferentClass", load_name="TestMod", command="DiskCmd")
    r5b = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", cs=cs_diff_cls)
    check("S5b: different ClassName returns error", r5b.get("status") == "error", str(r5b))
    check("S5b: error reports conflict", "conflict" in r5b.get("message", "").lower(), r5b.get("message", ""))

    # ── S6: Metadata E2E (create_executable_command) ──
    addin_cpp.write_text(addin_single_hdr, encoding="utf-8")
    ctx.refresh(force=True)
    r6 = create_executable_command(
        ctx,
        name="E2ECmd",
        module="TestMod.m",
        framework="TestFW.edu",
        add_to_workbench="SampleWorkbench",
        load_name="CustomLoadName",
    )
    check("S6: create_executable_command returns pending", r6.get("status") == "pending", str(r6))
    cs6 = r6.get("changeset", {})
    meta6 = cs6.get("metadata", {})
    check("S6: metadata contains command", meta6.get("command") == "E2ECmd", str(meta6))
    check("S6: metadata contains class_name", meta6.get("class_name") == "E2ECmd", str(meta6))
    check("S6: metadata contains load_name", meta6.get("load_name") == "CustomLoadName", str(meta6))
    check("S6: metadata contains module", meta6.get("module") == "TestMod.m", str(meta6))
    addin_6 = cs6.get("modified", {}).get(str(addin_cpp), "")
    check("S6: 4-param header registration in Addin source",
          'new CustomWksHeader("E2ECmdHdr", "CustomLoadName", "E2ECmd", (void *)NULL);' in addin_6, addin_6)

    # ── S7: Orchestrator Pre-validation Gate (A-3 Closure) ──
    # Case A: Missing workbench
    r7a = create_executable_command(
        ctx,
        name="GateFailCmdA",
        module="TestMod.m",
        framework="TestFW.edu",
        add_to_workbench="NonExistentWorkbench",
    )
    check("S7a: pre-validation fails for missing workbench", r7a.get("status") == "error", str(r7a))
    check("S7a: changeset is None (zero mutation)", r7a.get("changeset") is None, str(r7a))

    # Case B: Multi-header workbench fails at pre-validation gate
    addin_cpp.write_text(addin_multi_hdr, encoding="utf-8")
    ctx.refresh(force=True)
    r7b = create_executable_command(
        ctx,
        name="GateFailCmdB",
        module="TestMod.m",
        framework="TestFW.edu",
        add_to_workbench="SampleWorkbench",
    )
    check("S7b: pre-validation fails for multi-header workbench", r7b.get("status") == "error", str(r7b))
    check("S7b: changeset is None (zero mutation)", r7b.get("changeset") is None, str(r7b))
    check("S7b: no command files created on disk", not (src_dir / "GateFailCmdB.cpp").exists())

    # Case C: Missing CreateCommands() method in Addin source
    addin_missing_cc = (
        '#include "SampleWorkbenchAddin.h"\n'
        '#include "CATCommandHeader.h"\n\n'
        '// CATCmdWorkbench\n'
        'CATIAfrGeneralWksAddin\n\n'
        'MacDeclareHeader(CustomWksHeader);\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {\n'
        '}\n'
    )
    addin_cpp.write_text(addin_missing_cc, encoding="utf-8")
    ctx.refresh(force=True)
    r7c = create_executable_command(
        ctx,
        name="GateFailCmdC",
        module="TestMod.m",
        framework="TestFW.edu",
        add_to_workbench="SampleWorkbench",
    )
    check("S7c: pre-validation fails for missing CreateCommands()", r7c.get("status") == "error", str(r7c))
    check("S7c: error explains CreateCommands missing", "CreateCommands" in r7c.get("message", ""), r7c.get("message", ""))
    check("S7c: changeset is None (zero mutation)", r7c.get("changeset") is None, str(r7c))
    check("S7c: no command files created on disk", not (src_dir / "GateFailCmdC.cpp").exists())

    # Case D: Registration payload conflict at pre-validation gate
    addin_conflict = (
        '#include "SampleWorkbenchAddin.h"\n'
        '#include "CATCommandHeader.h"\n\n'
        'CATIAfrGeneralWksAddin\n\n'
        'MacDeclareHeader(CustomWksHeader);\n\n'
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new CustomWksHeader("GateFailCmdDHdr", "ExistingMod", "OtherClass", (void *)NULL);\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {\n'
        '}\n'
    )
    addin_cpp.write_text(addin_conflict, encoding="utf-8")
    ctx.refresh(force=True)
    r7d = create_executable_command(
        ctx,
        name="GateFailCmdD",
        module="TestMod.m",
        framework="TestFW.edu",
        add_to_workbench="SampleWorkbench",
        load_name="TestMod",
    )
    check("S7d: pre-validation fails for payload conflict", r7d.get("status") == "error", str(r7d))
    check("S7d: error mentions conflict", "conflict" in r7d.get("message", "").lower(), r7d.get("message", ""))
    check("S7d: changeset is None (zero mutation)", r7d.get("changeset") is None, str(r7d))
    check("S7d: no command files created on disk", not (src_dir / "GateFailCmdD.cpp").exists())

    # Case E: Completely identical registration (idempotent) passes pre-validation gate
    addin_idempotent = (
        '#include "SampleWorkbenchAddin.h"\n'
        '#include "CATCommandHeader.h"\n\n'
        'CATIAfrGeneralWksAddin\n\n'
        'MacDeclareHeader(CustomWksHeader);\n\n'
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new CustomWksHeader("GatePassCmdEHdr", "CustomLoadName", "GatePassCmdE", (void *)NULL);\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {\n'
        '}\n'
    )
    addin_cpp.write_text(addin_idempotent, encoding="utf-8")
    ctx.refresh(force=True)
    r7e = create_executable_command(
        ctx,
        name="GatePassCmdE",
        module="TestMod.m",
        framework="TestFW.edu",
        add_to_workbench="SampleWorkbench",
        load_name="CustomLoadName",
    )
    check("S7e: pre-validation passes for idempotent registration", r7e.get("status") == "pending", str(r7e))
    cs7e = r7e.get("changeset", {})
    check("S7e: idempotent addin has no modification queued",
          str(addin_cpp) not in cs7e.get("modified", {}), str(cs7e.get("modified", {})))

    # ── S8: External Header 隔离 ──
    check("S8: new_addin_1 has no DiskCmdHeader.h include",
          '#include "DiskCmdHeader.h"' not in new_addin_1, new_addin_1)
    check("S8: new_addin_2 has no DiskCmdHeader.h include",
          '#include "DiskCmdHeader.h"' not in new_addin_2, new_addin_2)
    check("S8: addin_6 has no E2ECmdHeader.h include",
          '#include "E2ECmdHeader.h"' not in addin_6, addin_6)

    # ── S9: Lexical false-positive ──
    addin_lexical = (
        '#include "SampleWorkbenchAddin.h"\n'
        '#include <iostream>\n\n'
        '// MacDeclareHeader(FakeCommentHeader);\n'
        '/* MacDeclareHeader(FakeBlockCommentHeader);\n'
        '   new SampleWorkbenchAddinHeader("DiskCmdHdr", "ConflictMod", "ConflictClass", (void *)NULL);\n'
        '*/\n'
        'const char* dummy = "MacDeclareHeader(FakeStringHeader)";\n\n'
        'CATIAfrGeneralWksAddin\n\n'
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    // new SampleWorkbenchAddinHeader("DiskCmdHdr", "CommentMod", "CommentClass", (void *)NULL);\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {\n'
        '}\n'
    )
    addin_cpp.write_text(addin_lexical, encoding="utf-8")
    ctx.refresh(force=True)
    r9 = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", load_name="TestMod")
    check("S9: status is success/pending despite comment traps",
          r9.get("status") in ("success", "pending"), str(r9))
    new_addin_9 = r9.get("changeset", {}).get("modified", {}).get(str(addin_cpp), "")
    check("S9: ignores fake headers in comments and derives AddinClassHeader",
          "MacDeclareHeader(SampleWorkbenchAddinHeader);" in new_addin_9, new_addin_9)
    check("S9: injects 4-param registration without false conflict",
          'new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);' in new_addin_9, new_addin_9)

    # ── S10: created / modified / disk 三来源 ──
    # 10a. cs.modified: Addin source in cs.modified is preserved and extended
    cs_mod = ChangeSet(action="mod", description="mod")
    cs_mod.add_modify(addin_cpp, addin_initial + "\n// pre-existing change in cs.modified\n")
    r10a = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", load_name="TestMod", cs=cs_mod)
    new_addin_10a = r10a.get("changeset", {}).get("modified", {}).get(str(addin_cpp), "")
    check("S10a: preserves pre-existing change in cs.modified",
          "// pre-existing change in cs.modified" in new_addin_10a, new_addin_10a)
    check("S10a: registers command in cs.modified content",
          'new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);' in new_addin_10a, new_addin_10a)

    # 10b. cs.created: Addin source in cs.created is updated in cs.created, not moved to cs.modified
    cs_created = ChangeSet(action="create", description="create")
    fake_created_addin = src_dir / "NewWorkbenchAddin.cpp"
    fake_created_content = (
        '#include "NewWorkbenchAddin.h"\n\n'
        'void NewWorkbenchAddin::CreateCommands() {\n'
        '}\n'
    )
    cs_created.add_create(fake_created_addin, fake_created_content)
    wb_obj = next((w for w in ctx.snapshot.get_all_workbenches() if w.name.lower() == "sampleworkbench"), None)
    orig_addin_source = wb_obj.addin_source
    wb_obj.addin_source = fake_created_addin
    try:
        r10b = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", load_name="TestMod", cs=cs_created)
        check("S10b: updates cs.created[str(addin)]",
              str(fake_created_addin) in cs_created.created, str(cs_created.created.keys()))
        check("S10b: does not put created addin into cs.modified",
              str(fake_created_addin) not in cs_created.modified, str(cs_created.modified.keys()))
        check("S10b: created content has 4-param header registration",
              'new NewWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);' in cs_created.created[str(fake_created_addin)],
              cs_created.created[str(fake_created_addin)])
    finally:
        wb_obj.addin_source = orig_addin_source
finally:
    shutil.rmtree(wb_ws, ignore_errors=True)

# ── R-3-A: Resource Binding (.CATNls, .CATRsc, Icon Binary, Pre-validation Gate) ──
# RA1 (无既有 CATNls/CATRsc): Creates {HeaderClass}.CATNls & {HeaderClass}.CATRsc & Simplified_Chinese
# RA2 (磁盘已有相同配置): Disk-state idempotency: ChangeSet does not re-add or modify identical resources
# RA3 (CATNls 同 key 异值冲突): Gate & add_command_to_workbench return conflict error
# RA4 (CATRsc 同 key 异值冲突): Gate & add_command_to_workbench return conflict error
# RA5 (已有其他 Header 资源): Appends new header resources while preserving existing entries
# RA6 (中文 NLS 编码与目录): Simplified_Chinese/{HeaderClass}.CATNls generated and readable as GBK
# RA7 (Resource Host 不存在): Pre-validation Gate catches missing host before CS creation (A-3 zero mutation)
# RA8 (端到端编排调用): create_executable_command full flow produces C++, Header reg, NLS, RSC
# RA9 (同一 ChangeSet 连续两次 queue): Staged-state idempotency: duplicate queueing produces no extra lines
# RA10 (图标文件内容冲突): Target icon exists with different bytes -> hard conflict error
ra_ws = Path(tempfile.mkdtemp(prefix="cade_ra_test_"))
try:
    fw_dir = ra_ws / "TestFW.edu"
    (fw_dir / "IdentityCard").mkdir(parents=True)
    (fw_dir / "IdentityCard" / "IdentityCard.h").write_text("// ic", encoding="utf-8")
    (fw_dir / "Imakefile.mk").write_text("", encoding="utf-8")

    mod_dir = fw_dir / "TestMod.m"
    src_dir = mod_dir / "src"
    src_dir.mkdir(parents=True)
    (mod_dir / "Imakefile.mk").write_text("BUILT_OBJECT_TYPE=SHARED LIBRARY", encoding="utf-8")

    (src_dir / "DiskCmd.cpp").write_text("CATStateCommand BuildGraph\n", encoding="utf-8")

    addin_cpp = src_dir / "SampleWorkbenchAddin.cpp"
    addin_initial = (
        '#include "SampleWorkbenchAddin.h"\n'
        '#include <iostream>\n\n'
        'CATIAfrGeneralWksAddin\n\n'
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {\n'
        '}\n'
    )
    addin_cpp.write_text(addin_initial, encoding="utf-8")

    ctx = ActionContext(ra_ws)

    # ── RA1: 无既有 CATNls / CATRsc ──
    r_ra1 = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", load_name="TestMod")
    check("RA1: add_command_to_workbench status is success/pending",
          r_ra1.get("status") in ("success", "pending"), str(r_ra1))
    cs_ra1 = r_ra1.get("changeset", {})
    created_ra1 = cs_ra1.get("created", {})

    nls_path_ra1 = fw_dir / "CNext" / "resources" / "msgcatalog" / "SampleWorkbenchAddinHeader.CATNls"
    rsc_path_ra1 = fw_dir / "CNext" / "resources" / "msgcatalog" / "SampleWorkbenchAddinHeader.CATRsc"
    zh_nls_path_ra1 = fw_dir / "CNext" / "resources" / "msgcatalog" / "Simplified_Chinese" / "SampleWorkbenchAddinHeader.CATNls"

    check("RA1: creates English CATNls in ChangeSet", str(nls_path_ra1) in created_ra1, str(created_ra1.keys()))
    check("RA1: creates CATRsc in ChangeSet", str(rsc_path_ra1) in created_ra1, str(created_ra1.keys()))
    check("RA1: creates Simplified_Chinese CATNls in ChangeSet", str(zh_nls_path_ra1) in created_ra1, str(created_ra1.keys()))

    nls_content_ra1 = created_ra1.get(str(nls_path_ra1), "")
    check("RA1: English CATNls has HeaderClass.HeaderID.Title",
          'SampleWorkbenchAddinHeader.DiskCmdHdr.Title     = "DiskCmd";' in nls_content_ra1, nls_content_ra1)
    check("RA1: English CATNls has HeaderClass.HeaderID.ShortHelp",
          'SampleWorkbenchAddinHeader.DiskCmdHdr.ShortHelp = "DiskCmd";' in nls_content_ra1, nls_content_ra1)

    rsc_content_ra1 = created_ra1.get(str(rsc_path_ra1), "")
    check("RA1: CATRsc has HeaderClass.HeaderID.Icon.Normal",
          'SampleWorkbenchAddinHeader.DiskCmdHdr.Icon.Normal = "I_diskcmd";' in rsc_content_ra1, rsc_content_ra1)

    # ── RA2: 磁盘已有完全相同资源 (磁盘态幂等) ──
    ChangeSet.from_dict(cs_ra1).apply(workspace_root=ra_ws)
    ctx.refresh(force=True)

    r_ra2 = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", load_name="TestMod")
    check("RA2: status is success/pending", r_ra2.get("status") in ("success", "pending"), str(r_ra2))
    cs_ra2 = r_ra2.get("changeset", {})
    created_ra2 = cs_ra2.get("created", {})
    modified_ra2 = cs_ra2.get("modified", {})

    check("RA2: NLS not re-created", str(nls_path_ra1) not in created_ra2, str(created_ra2.keys()))
    check("RA2: RSC not re-created", str(rsc_path_ra1) not in created_ra2, str(created_ra2.keys()))
    check("RA2: NLS not modified on disk-state match", str(nls_path_ra1) not in modified_ra2, str(modified_ra2.keys()))
    check("RA2: RSC not modified on disk-state match", str(rsc_path_ra1) not in modified_ra2, str(modified_ra2.keys()))

    # ── RA3: CATNls 同 key 异值冲突 ──
    r_ra3 = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", load_name="TestMod", title="ConflictingTitle")
    check("RA3: returns error on NLS value conflict", r_ra3.get("status") == "error", str(r_ra3))
    check("RA3: error reports conflict", "conflict" in r_ra3.get("message", "").lower(), r_ra3.get("message", ""))

    # ── RA4: CATRsc 同 key 异值冲突 ──
    r_ra4 = add_command_to_workbench(ctx, "DiskCmd", "SampleWorkbench", load_name="TestMod", icon="ConflictingIcon")
    check("RA4: returns error on RSC value conflict", r_ra4.get("status") == "error", str(r_ra4))
    check("RA4: error reports conflict", "conflict" in r_ra4.get("message", "").lower(), r_ra4.get("message", ""))

    # ── RA5: 工作台已有其他 Header 资源 ──
    existing_nls_with_other = (
        nls_path_ra1.read_text(encoding="utf-8")
        + '\nSampleWorkbenchAddinHeader.OtherCmdHdr.Title     = "Other Title";\n'
    )
    nls_path_ra1.write_text(existing_nls_with_other, encoding="utf-8")

    (src_dir / "NewCmd.cpp").write_text("CATStateCommand BuildGraph\n", encoding="utf-8")
    ctx.refresh(force=True)
    r_ra5 = add_command_to_workbench(ctx, "NewCmd", "SampleWorkbench", load_name="TestMod")
    check("RA5: status is success/pending", r_ra5.get("status") in ("success", "pending"), str(r_ra5))
    cs_ra5 = r_ra5.get("changeset", {})
    mod_ra5 = cs_ra5.get("modified", {})
    check("RA5: NLS is in modified", str(nls_path_ra1) in mod_ra5, str(mod_ra5.keys()))
    new_nls_content_5 = mod_ra5.get(str(nls_path_ra1), "")
    check("RA5: preserves existing OtherCmdHdr", "OtherCmdHdr" in new_nls_content_5, new_nls_content_5)
    check("RA5: appends NewCmdHdr", "NewCmdHdr" in new_nls_content_5, new_nls_content_5)

    # ── RA6: 中文 NLS 编码与目录 ──
    check("RA6: Simplified_Chinese directory exists", zh_nls_path_ra1.parent.exists(), str(zh_nls_path_ra1.parent))
    check("RA6: Simplified_Chinese file exists on disk", zh_nls_path_ra1.exists(), str(zh_nls_path_ra1))
    zh_bytes = zh_nls_path_ra1.read_bytes()
    zh_text = zh_bytes.decode("gbk")
    check("RA6: file is valid GBK and contains Chinese comments/entries", "命令头" in zh_text, zh_text)

    # ── RA7: Resource Host 不存在 (Pre-validation Gate & 零污染) ──
    from meta_model import Workbench
    wb_nohost = Workbench(path=addin_cpp, name="NoHostWorkbench", framework=None, addin_source=addin_cpp)
    ctx.snapshot.frameworks[0].workbenches.append(wb_nohost)
    try:
        r_ra7 = create_executable_command(
            ctx,
            name="NoHostCmd",
            module="TestMod.m",
            framework="TestFW.edu",
            add_to_workbench="NoHostWorkbench",
        )
        check("RA7: pre-validation gate fails when workbench has no framework",
              r_ra7.get("status") == "error", str(r_ra7))
        check("RA7: error explains missing framework",
              "framework" in r_ra7.get("message", "").lower(), r_ra7.get("message", ""))
        check("RA7: changeset is None (zero mutation)", r_ra7.get("changeset") is None, str(r_ra7))
        check("RA7: no command source created on disk", not (src_dir / "NoHostCmd.cpp").exists())
    finally:
        ctx.snapshot.frameworks[0].workbenches.remove(wb_nohost)

    # ── RA8: 端到端编排调用 (create_executable_command) ──
    r_ra8 = create_executable_command(
        ctx,
        name="E2EResCmd",
        module="TestMod.m",
        framework="TestFW.edu",
        add_to_workbench="SampleWorkbench",
        tooltip="Execute E2E Command",
        icon_style="geo",
    )
    check("RA8: create_executable_command returns pending", r_ra8.get("status") == "pending", str(r_ra8))
    cs_ra8 = r_ra8.get("changeset", {})
    created_ra8 = cs_ra8.get("created", {})
    mod_ra8 = cs_ra8.get("modified", {})

    cmd_cpp_ra8 = src_dir / "E2EResCmd.cpp"
    check("RA8: creates command source file", str(cmd_cpp_ra8) in created_ra8, str(created_ra8.keys()))

    addin_ra8 = mod_ra8.get(str(addin_cpp), "")
    check("RA8: registers 4-param header in Addin source",
          'new SampleWorkbenchAddinHeader("E2EResCmdHdr", "TestMod", "E2EResCmd", (void *)NULL);' in addin_ra8, addin_ra8)

    nls_ra8 = mod_ra8.get(str(nls_path_ra1), created_ra8.get(str(nls_path_ra1), ""))
    check("RA8: workbench NLS has E2EResCmd entries", "E2EResCmdHdr.Title" in nls_ra8, nls_ra8)
    rsc_ra8 = mod_ra8.get(str(rsc_path_ra1), created_ra8.get(str(rsc_path_ra1), ""))
    check("RA8: workbench RSC has E2EResCmd icon entry", "E2EResCmdHdr.Icon.Normal" in rsc_ra8, rsc_ra8)

    # ── RA9: 同一 ChangeSet 连续两次 queue (内存态幂等) ──
    from actions import inspect_header_resources, queue_header_resources
    cs_ra9 = ChangeSet(action="ra9", description="ra9")
    insp_ra9 = inspect_header_resources(
        ctx,
        workbench_name="SampleWorkbench",
        header_class="SampleWorkbenchAddinHeader",
        header_id="StagedIdempotentCmdHdr",
        command_name="StagedCmd",
        title="Staged Title",
        tooltip="Staged Tooltip",
        icon="staged_icon",
        cs=cs_ra9,
    )
    check("RA9: inspection status ok", insp_ra9.get("status") == "ok", str(insp_ra9))
    queue_header_resources(cs_ra9, insp_ra9, source="test_ra9")
    nls_key_ra9 = str(insp_ra9["nls_file"])
    rsc_key_ra9 = str(insp_ra9["rsc_file"])

    first_nls = cs_ra9.created.get(nls_key_ra9, cs_ra9.modified.get(nls_key_ra9, ""))
    first_rsc = cs_ra9.created.get(rsc_key_ra9, cs_ra9.modified.get(rsc_key_ra9, ""))

    # Second queue call on the exact same ChangeSet
    queue_header_resources(cs_ra9, insp_ra9, source="test_ra9")
    second_nls = cs_ra9.created.get(nls_key_ra9, cs_ra9.modified.get(nls_key_ra9, ""))
    second_rsc = cs_ra9.created.get(rsc_key_ra9, cs_ra9.modified.get(rsc_key_ra9, ""))

    check("RA9: NLS staged content identical after second queue (no duplicated lines)",
          first_nls == second_nls, f"First:\n{first_nls}\nSecond:\n{second_nls}")
    check("RA9: RSC staged content identical after second queue (no duplicated lines)",
          first_rsc == second_rsc, f"First:\n{first_rsc}\nSecond:\n{second_rsc}")

    # ── RA10: 图标文件内容冲突 ──
    (src_dir / "IconConflictCmd.cpp").write_text("CATStateCommand BuildGraph\n", encoding="utf-8")
    ctx.refresh(force=True)
    icon_dir_ra = fw_dir / "CNext" / "resources" / "graphic" / "icons" / "normal"
    icon_dir_ra.mkdir(parents=True, exist_ok=True)
    conflict_icon_file = icon_dir_ra / "I_conflict_icon.bmp"
    conflict_icon_file.write_bytes(b"BYTE_ORIGINAL_ON_DISK")

    r_ra10 = add_command_to_workbench(
        ctx,
        "IconConflictCmd",
        "SampleWorkbench",
        load_name="TestMod",
        icon="conflict_icon",
        icon_bytes=b"BYTE_DIFFERENT_INCOMING",
    )
    check("RA10: returns error on icon binary conflict", r_ra10.get("status") == "error", str(r_ra10))
    check("RA10: error message reports binary conflict",
          "Icon binary conflict" in r_ra10.get("message", ""), r_ra10.get("message", ""))
finally:
    shutil.rmtree(ra_ws, ignore_errors=True)

# ── R-3-B: Explicit Toolbar Mounting (attach_command_to_toolbar & inspect_toolbar_mount) ──
# RB1  (0 Toolbar): Returns error when CreateToolbars() contains no toolbars
# RB2  (1 Toolbar 隐式选择): Auto-selects the only toolbar when toolbar_id is omitted
# RB3  (1 Toolbar 显式选择): Selects the toolbar when toolbar_id matches
# RB4  (>1 Toolbar 无 ID): Rejects ambiguity with error listing available toolbars
# RB5  (>1 Toolbar 显式选择): Selects the specified toolbar among multiple
# RB6  (无效 toolbar_id): Returns error when requested toolbar_id does not exist
# RB7  (空 Toolbar 挂载): Uses SetAccessChild on empty toolbar container
# RB8  (非空 Toolbar 挂载): Uses SetAccessNext on existing starter chain
# RB9  (多 Toolbar 链表隔离): Mutating one toolbar does not affect or cross-link another toolbar
# RB10 (MountKey 幂等零变更): (ToolbarID, HeaderID) already mounted -> ChangeSet zero mutation
# RB11 (跨 Toolbar 复用同一 Header): Same HeaderID mounted to different toolbar creates independent starter
# RB12 (Starter 变量名冲突去重): Colliding starter variable name gets deterministic numeric suffix
# RB13 (Menubar 容器排除): Container without AddToolbarView is ignored, not recognized as toolbar
# RB14 (事务门禁零变更): Inspection error results in changeset=None, leaves caller CS untouched
# RB15 (异常链表拓扑拦截): Forking / cycle / multiple SetAccessChild detected and rejected as hard error
# RB16 (语句残缺 / 缺失方法拦截): Incomplete C++ statement or missing CreateToolbars() rejected as hard error
rb_ws = Path(tempfile.mkdtemp(prefix="cade_rb_test_"))
try:
    from actions import attach_command_to_toolbar, inspect_toolbar_mount

    fw_dir = rb_ws / "TestFW.edu"
    (fw_dir / "IdentityCard").mkdir(parents=True)
    (fw_dir / "IdentityCard" / "IdentityCard.h").write_text("// ic", encoding="utf-8")
    (fw_dir / "Imakefile.mk").write_text("", encoding="utf-8")

    mod_dir = fw_dir / "TestMod.m"
    src_dir = mod_dir / "src"
    src_dir.mkdir(parents=True)
    (mod_dir / "Imakefile.mk").write_text("BUILT_OBJECT_TYPE=SHARED LIBRARY", encoding="utf-8")

    addin_cpp = src_dir / "SampleWorkbenchAddin.cpp"
    addin_header = (
        '#include "SampleWorkbenchAddin.h"\n'
        '#include <iostream>\n\n'
        'CATIAfrGeneralWksAddin\n\n'
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '}\n\n'
    )

    ctx = ActionContext(rb_ws)

    # ── RB1: 0 Toolbar ──
    addin_cpp.write_text(
        addin_header +
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    return NULL;\n'
        '}\n',
        encoding="utf-8",
    )
    r_rb1 = attach_command_to_toolbar(ctx, "SampleWorkbench", "DiskCmdHdr")
    check("RB1: 0 toolbar returns error", r_rb1.get("status") == "error", str(r_rb1))
    check("RB1: error message explains no toolbars found",
          "no toolbars found" in r_rb1.get("message", "").lower(), r_rb1.get("message", ""))
    check("RB1: changeset is None (zero mutation)", r_rb1.get("changeset") is None, str(r_rb1))

    # ── RB13: Menubar 容器排除 (仅含 Menubar 仍报 0 toolbar) ──
    addin_cpp.write_text(
        addin_header +
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pMenuBar, MenuBar);\n'
        '    SetAddinMenu(pMenuBar, 1);\n'
        '    return pMenuBar;\n'
        '}\n',
        encoding="utf-8",
    )
    r_rb13 = attach_command_to_toolbar(ctx, "SampleWorkbench", "DiskCmdHdr")
    check("RB13: Menubar lacking AddToolbarView is excluded (0 toolbar error)",
          r_rb13.get("status") == "error" and "no toolbars found" in r_rb13.get("message", "").lower(),
          str(r_rb13))

    # ── RB2 & RB7: 1 Toolbar 隐式选择 & 空 Toolbar 挂载 (SetAccessChild) ──
    addin_cpp.write_text(
        addin_header +
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pSingleTlb, SingleTlb);\n'
        '    AddToolbarView(pSingleTlb, 1, Right);\n'
        '    return pSingleTlb;\n'
        '}\n',
        encoding="utf-8",
    )
    r_rb2 = attach_command_to_toolbar(ctx, "SampleWorkbench", "FirstCmdHdr")
    check("RB2: 1 toolbar implicit selection succeeds", r_rb2.get("status") in ("success", "pending"), str(r_rb2))
    cs_rb2 = r_rb2.get("changeset", {})
    check("RB2: metadata has selected toolbar_id", cs_rb2.get("metadata", {}).get("toolbar_id") == "SingleTlb", str(cs_rb2))
    ChangeSet.from_dict(cs_rb2).apply(workspace_root=rb_ws)

    content_rb2 = addin_cpp.read_text(encoding="utf-8")
    check("RB7: empty toolbar uses SetAccessChild",
          "SetAccessChild(pSingleTlb, pFirstCmdStr);" in content_rb2, content_rb2)
    check("RB7: creates Starter with correct NewAccess",
          "NewAccess(CATCmdStarter, pFirstCmdStr, FirstCmdStr);" in content_rb2, content_rb2)
    check("RB7: binds HeaderID via SetAccessCommand",
          'SetAccessCommand(pFirstCmdStr, "FirstCmdHdr");' in content_rb2, content_rb2)

    # ── RB8: 非空 Toolbar 挂载 (SetAccessNext) ──
    r_rb8 = attach_command_to_toolbar(ctx, "SampleWorkbench", "SecondCmdHdr")
    check("RB8: appending to non-empty toolbar succeeds", r_rb8.get("status") in ("success", "pending"), str(r_rb8))
    cs_rb8 = r_rb8.get("changeset", {})
    ChangeSet.from_dict(cs_rb8).apply(workspace_root=rb_ws)

    content_rb8 = addin_cpp.read_text(encoding="utf-8")
    check("RB8: non-empty toolbar uses SetAccessNext linking to predecessor",
          "SetAccessNext(pFirstCmdStr, pSecondCmdStr);" in content_rb8, content_rb8)
    check("RB8: original SetAccessChild is preserved intact",
          "SetAccessChild(pSingleTlb, pFirstCmdStr);" in content_rb8, content_rb8)

    # ── RB3: 1 Toolbar 显式选择 ──
    r_rb3 = attach_command_to_toolbar(ctx, "SampleWorkbench", "ThirdCmdHdr", toolbar_id="SingleTlb")
    check("RB3: explicit toolbar_id matching the 1 toolbar succeeds",
          r_rb3.get("status") in ("success", "pending"), str(r_rb3))
    cs_rb3 = r_rb3.get("changeset", {})
    ChangeSet.from_dict(cs_rb3).apply(workspace_root=rb_ws)

    content_rb3 = addin_cpp.read_text(encoding="utf-8")
    check("RB3: third command linked via SetAccessNext",
          "SetAccessNext(pSecondCmdStr, pThirdCmdStr);" in content_rb3, content_rb3)

    # ── RB6: 无效 toolbar_id ──
    r_rb6 = attach_command_to_toolbar(ctx, "SampleWorkbench", "InvalidTlbCmdHdr", toolbar_id="NonExistentTlb")
    check("RB6: returns error when toolbar_id does not exist", r_rb6.get("status") == "error", str(r_rb6))
    check("RB6: error message indicates missing toolbar and lists available",
          "NonExistentTlb" in r_rb6.get("message", "") and "SingleTlb" in r_rb6.get("message", ""),
          r_rb6.get("message", ""))
    check("RB6: changeset is None on invalid toolbar_id", r_rb6.get("changeset") is None, str(r_rb6))

    # ── RB10: MountKey 幂等零变更 ──
    r_rb10 = attach_command_to_toolbar(ctx, "SampleWorkbench", "SecondCmdHdr", toolbar_id="SingleTlb")
    check("RB10: already mounted command returns pending", r_rb10.get("status") in ("success", "pending"), str(r_rb10))
    cs_rb10 = r_rb10.get("changeset", {})
    check("RB10: created dict is empty on idempotent mount", cs_rb10.get("created") == {}, str(cs_rb10))
    check("RB10: modified dict is empty on idempotent mount", cs_rb10.get("modified") == {}, str(cs_rb10))
    check("RB10: metadata flags is_idempotent=True",
          cs_rb10.get("metadata", {}).get("is_idempotent") is True, str(cs_rb10))

    # ── RB4 & RB5: 多 Toolbar 场景 (无 ID 拒绝猜测 & 显式选择) ──
    addin_multi = (
        addin_header +
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlb1, FirstTlb);\n'
        '    AddToolbarView(pTlb1, 1, Right);\n'
        '    NewAccess(CATCmdStarter, pS1, S1);\n'
        '    SetAccessCommand(pS1, "Cmd1Hdr");\n'
        '    SetAccessChild(pTlb1, pS1);\n\n'
        '    NewAccess(CATCmdContainer, pTlb2, SecondTlb);\n'
        '    AddToolbarView(pTlb2, 1, Bottom);\n'
        '    NewAccess(CATCmdStarter, pS2, S2);\n'
        '    SetAccessCommand(pS2, "OtherCmdHdr");\n'
        '    SetAccessChild(pTlb2, pS2);\n\n'
        '    return pTlb1;\n'
        '}\n'
    )
    addin_cpp.write_text(addin_multi, encoding="utf-8")

    r_rb4 = attach_command_to_toolbar(ctx, "SampleWorkbench", "MultiTestCmdHdr")
    check("RB4: >1 toolbar without toolbar_id returns error", r_rb4.get("status") == "error", str(r_rb4))
    check("RB4: error message lists both available toolbars",
          "FirstTlb" in r_rb4.get("message", "") and "SecondTlb" in r_rb4.get("message", ""),
          r_rb4.get("message", ""))
    check("RB4: changeset is None on ambiguity error", r_rb4.get("changeset") is None, str(r_rb4))

    r_rb5 = attach_command_to_toolbar(ctx, "SampleWorkbench", "MultiTestCmdHdr", toolbar_id="SecondTlb")
    check("RB5: explicit selection among multiple toolbars succeeds",
          r_rb5.get("status") in ("success", "pending"), str(r_rb5))
    cs_rb5 = r_rb5.get("changeset", {})
    ChangeSet.from_dict(cs_rb5).apply(workspace_root=rb_ws)

    content_rb5 = addin_cpp.read_text(encoding="utf-8")
    check("RB5: attaches to specified SecondTlb",
          "SetAccessNext(pS2, pMultiTestCmdStr);" in content_rb5, content_rb5)

    # ── RB9: 多 Toolbar 链表隔离性 ──
    check("RB9: FirstTlb starter pS1 has no SetAccessNext",
          "SetAccessNext(pS1," not in content_rb5, content_rb5)
    check("RB9: FirstTlb remains isolated and unchanged",
          "SetAccessChild(pTlb1, pS1);" in content_rb5, content_rb5)

    # ── RB11: 跨 Toolbar 复用同一 Header (在不同 Toolbar 独立挂载) ──
    # Cmd1Hdr is in FirstTlb; attach it now to SecondTlb
    r_rb11 = attach_command_to_toolbar(ctx, "SampleWorkbench", "Cmd1Hdr", toolbar_id="SecondTlb")
    check("RB11: mounting same HeaderID to different toolbar succeeds",
          r_rb11.get("status") in ("success", "pending"), str(r_rb11))
    cs_rb11 = r_rb11.get("changeset", {})
    check("RB11: not idempotent across different toolbars (produces mutation)",
          cs_rb11.get("modified") != {}, str(cs_rb11))
    ChangeSet.from_dict(cs_rb11).apply(workspace_root=rb_ws)

    content_rb11 = addin_cpp.read_text(encoding="utf-8")
    check("RB11: SecondTlb now links Cmd1 starter at the end of its chain",
          'SetAccessCommand(pCmd1Str, "Cmd1Hdr");' in content_rb11 and
          "SetAccessNext(pMultiTestCmdStr, pCmd1Str);" in content_rb11,
          content_rb11)
    check("RB11: FirstTlb original mount of Cmd1Hdr untouched",
          'SetAccessCommand(pS1, "Cmd1Hdr");' in content_rb11 and
          "SetAccessChild(pTlb1, pS1);" in content_rb11,
          content_rb11)

    # ── RB12: Starter 变量名冲突去重 ──
    # pS1 is already in the file. S1Hdr sanitizes to token S1, base_var pS1Str.
    # But let's check with an existing token: add NewAccess(CATCmdStarter, pDedupStr, ...)
    addin_dedup = (
        addin_header +
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlb1, FirstTlb);\n'
        '    AddToolbarView(pTlb1, 1, Right);\n'
        '    NewAccess(CATCmdStarter, pDedupStr, DedupStr);\n'
        '    SetAccessCommand(pDedupStr, "OldHdr");\n'
        '    SetAccessChild(pTlb1, pDedupStr);\n'
        '    return pTlb1;\n'
        '}\n'
    )
    addin_cpp.write_text(addin_dedup, encoding="utf-8")
    r_rb12 = attach_command_to_toolbar(ctx, "SampleWorkbench", "DedupHdr", toolbar_id="FirstTlb")
    check("RB12: mounting header with colliding var name succeeds",
          r_rb12.get("status") in ("success", "pending"), str(r_rb12))
    cs_rb12 = r_rb12.get("changeset", {})
    mod_rb12 = cs_rb12.get("modified", {})
    content_rb12 = list(mod_rb12.values())[0]
    check("RB12: colliding starter var renamed with suffix _2",
          "pDedupStr_2" in content_rb12 and "DedupStr_2" in content_rb12,
          content_rb12)
    check("RB12: renamed starter linked via SetAccessNext",
          "SetAccessNext(pDedupStr, pDedupStr_2);" in content_rb12,
          content_rb12)

    # ── RB14: 事务门禁零变更 (Pre-validation Gate) ──
    caller_cs = ChangeSet(action="caller_test", description="caller owned CS")
    r_rb14 = attach_command_to_toolbar(ctx, "SampleWorkbench", "GateCmdHdr", toolbar_id="BadTlb", cs=caller_cs)
    check("RB14: gate failure returns error", r_rb14.get("status") == "error", str(r_rb14))
    check("RB14: changeset is None in result", r_rb14.get("changeset") is None, str(r_rb14))
    check("RB14: caller ChangeSet created is completely empty", caller_cs.created == {}, str(caller_cs.created))
    check("RB14: caller ChangeSet modified is completely empty", caller_cs.modified == {}, str(caller_cs.modified))

    # ── RB15: 异常链表拓扑拦截 (Fork, Cycle, Multiple SetAccessChild) ──
    # 15a: Multiple SetAccessChild
    addin_cpp.write_text(
        addin_header +
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlb, BadTlb);\n'
        '    AddToolbarView(pTlb, 1, Right);\n'
        '    NewAccess(CATCmdStarter, pS1, S1);\n'
        '    NewAccess(CATCmdStarter, pS2, S2);\n'
        '    SetAccessChild(pTlb, pS1);\n'
        '    SetAccessChild(pTlb, pS2);\n'
        '    return pTlb;\n'
        '}\n',
        encoding="utf-8",
    )
    r_rb15a = attach_command_to_toolbar(ctx, "SampleWorkbench", "CmdHdr")
    check("RB15a: multiple SetAccessChild rejected as error", r_rb15a.get("status") == "error", str(r_rb15a))
    check("RB15a: error reports multiple SetAccessChild", "multiple setaccesschild" in r_rb15a.get("message", "").lower(), r_rb15a.get("message", ""))
    check("RB15a: changeset is None", r_rb15a.get("changeset") is None, str(r_rb15a))

    # 15b: Fork/branching in chain
    addin_cpp.write_text(
        addin_header +
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlb, BadTlb);\n'
        '    AddToolbarView(pTlb, 1, Right);\n'
        '    NewAccess(CATCmdStarter, pS1, S1);\n'
        '    NewAccess(CATCmdStarter, pS2, S2);\n'
        '    NewAccess(CATCmdStarter, pS3, S3);\n'
        '    SetAccessChild(pTlb, pS1);\n'
        '    SetAccessNext(pS1, pS2);\n'
        '    SetAccessNext(pS1, pS3);\n'
        '    return pTlb;\n'
        '}\n',
        encoding="utf-8",
    )
    r_rb15b = attach_command_to_toolbar(ctx, "SampleWorkbench", "CmdHdr")
    check("RB15b: forking/branching chain rejected as error", r_rb15b.get("status") == "error", str(r_rb15b))
    check("RB15b: error reports branching/fork", "fork" in r_rb15b.get("message", "").lower() or "branching" in r_rb15b.get("message", "").lower(), r_rb15b.get("message", ""))
    check("RB15b: changeset is None", r_rb15b.get("changeset") is None, str(r_rb15b))

    # 15c: Cycle in chain
    addin_cpp.write_text(
        addin_header +
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlb, BadTlb);\n'
        '    AddToolbarView(pTlb, 1, Right);\n'
        '    NewAccess(CATCmdStarter, pS1, S1);\n'
        '    NewAccess(CATCmdStarter, pS2, S2);\n'
        '    SetAccessChild(pTlb, pS1);\n'
        '    SetAccessNext(pS1, pS2);\n'
        '    SetAccessNext(pS2, pS1);\n'
        '    return pTlb;\n'
        '}\n',
        encoding="utf-8",
    )
    r_rb15c = attach_command_to_toolbar(ctx, "SampleWorkbench", "CmdHdr")
    check("RB15c: cycle in chain rejected as error", r_rb15c.get("status") == "error", str(r_rb15c))
    check("RB15c: error reports cycle", "cycle" in r_rb15c.get("message", "").lower(), r_rb15c.get("message", ""))
    check("RB15c: changeset is None", r_rb15c.get("changeset") is None, str(r_rb15c))

    # ── RB16: 语句残缺 / 缺失 CreateToolbars() ──
    # 16a: Incomplete statement
    addin_cpp.write_text(
        addin_header +
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlb, BadTlb);\n'
        '    AddToolbarView(pTlb, 1, Right);\n'
        '    NewAccess(CATCmdStarter, pS1, S1);\n'
        '    SetAccessChild(pTlb, pS1);\n'
        '    SetAccessNext(pS1);\n'
        '    return pTlb;\n'
        '}\n',
        encoding="utf-8",
    )
    r_rb16a = attach_command_to_toolbar(ctx, "SampleWorkbench", "CmdHdr")
    check("RB16a: incomplete statement rejected as error", r_rb16a.get("status") == "error", str(r_rb16a))
    check("RB16a: error reports incomplete statement", "incomplete" in r_rb16a.get("message", "").lower(), r_rb16a.get("message", ""))
    check("RB16a: changeset is None", r_rb16a.get("changeset") is None, str(r_rb16a))

    # 16b: Missing CreateToolbars()
    addin_cpp.write_text(
        addin_header +
        '// CreateToolbars() omitted\n',
        encoding="utf-8",
    )
    r_rb16b = attach_command_to_toolbar(ctx, "SampleWorkbench", "CmdHdr")
    check("RB16b: missing CreateToolbars rejected as error", r_rb16b.get("status") == "error", str(r_rb16b))
    check("RB16b: error indicates CreateToolbars not located", "createtoolbars" in r_rb16b.get("message", "").lower(), r_rb16b.get("message", ""))
    check("RB16b: changeset is None", r_rb16b.get("changeset") is None, str(r_rb16b))

finally:
    shutil.rmtree(rb_ws, ignore_errors=True)

# ── R-4-A: Command Cascade Delete & Toolbar Chain Splicing (inspect_delete_command) ──
# DA1  (Command 唯一身份识别与无挂载检测): Resolves 4-param header registration; 0 toolbar splices
# DA2  (单 Toolbar 单 Starter): splice_mode == "remove_only_child"
# DA3  (首节点拆除拓扑缝合): splice_mode == "new_child", SetAccessChild re-targeted to successor
# DA4  (中间节点拆除拓扑缝合): splice_mode == "relink_next", predecessor SetAccessNext linked to successor
# DA5  (尾节点拆除拓扑缝合): splice_mode == "remove_tail", predecessor SetAccessNext removed
# DA6  (空 Toolbar 容器与视图保留): Container NewAccess and AddToolbarView preserved in plan
# DA7  (跨 Toolbar 多重挂载独立缝合): Same HeaderID mounted in two toolbars yields two independent splices
# DA8  (Header 注册缺失硬拦截): Missing header registration returns error, plan is None
# DA9  (Header 重复注册冲突拦截): Duplicate header registration returns error, plan is None
# DA10 (目标 Toolbar 异常链拦截与非目标隔离): Malformed non-target toolbar ignored; malformed target toolbar rejected
# DA11 (事务门禁零变更): inspect_delete_command leaves caller ChangeSet untouched under error
# DA12 (非目标指令与资源隔离): Header and starter of unrelated commands untouched in plan
# DA13 (同一 Toolbar 重复 MountKey 拦截): Duplicate mount of same Header in same toolbar rejected as error
da_ws = Path(tempfile.mkdtemp(prefix="cade_da_test_"))
try:
    from actions import inspect_delete_command, delete_command, inspect_rename_command

    fw_dir = da_ws / "TestFW.edu"
    (fw_dir / "IdentityCard").mkdir(parents=True)
    (fw_dir / "IdentityCard" / "IdentityCard.h").write_text("// ic", encoding="utf-8")
    (fw_dir / "Imakefile.mk").write_text("", encoding="utf-8")

    mod_dir = fw_dir / "TestMod.m"
    src_dir = mod_dir / "src"
    src_dir.mkdir(parents=True)
    (mod_dir / "LocalInterfaces").mkdir(parents=True)
    (mod_dir / "Imakefile.mk").write_text("BUILT_OBJECT_TYPE=SHARED LIBRARY\nLINK_WITH=TestMod", encoding="utf-8")

    # Command implementation files
    (src_dir / "DiskCmd.cpp").write_text("CATStateCommand BuildGraph DiskCmd\n", encoding="utf-8")
    (mod_dir / "LocalInterfaces" / "DiskCmd.h").write_text("// DiskCmd header\n", encoding="utf-8")
    (src_dir / "OtherCmd.cpp").write_text("CATStateCommand BuildGraph OtherCmd\n", encoding="utf-8")
    (mod_dir / "LocalInterfaces" / "OtherCmd.h").write_text("// OtherCmd header\n", encoding="utf-8")

    addin_cpp = src_dir / "SampleWorkbenchAddin.cpp"
    ctx = ActionContext(da_ws)
    ctx.refresh(force=True)

    addin_base_header = (
        '#include "SampleWorkbenchAddin.h"\n'
        '#include <iostream>\n\n'
        'CATIAfrGeneralWksAddin\n\n'
        'MacDeclareHeader(SampleWorkbenchAddinHeader);\n\n'
    )

    # ── DA1: Command 唯一身份识别与无挂载检测 ──
    addin_da1 = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {\n'
        '}\n'
    )
    addin_cpp.write_text(addin_da1, encoding="utf-8")
    r_da1 = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA1: inspection succeeds for single unmounted command", r_da1.get("status") == "ok", str(r_da1))
    p_da1 = r_da1.get("plan", {})
    check("DA1: plan command_name matches", p_da1.get("command_name") == "DiskCmd", str(p_da1))
    check("DA1: plan class_name matches", p_da1.get("class_name") == "DiskCmd", str(p_da1))
    check("DA1: plan header_class matches", p_da1.get("header_class") == "SampleWorkbenchAddinHeader", str(p_da1))
    check("DA1: plan header_id matches", p_da1.get("header_id") == "DiskCmdHdr", str(p_da1))
    check("DA1: plan load_name matches", p_da1.get("load_name") == "TestMod", str(p_da1))
    check("DA1: plan toolbar_splices is empty", p_da1.get("toolbar_splices") == [], str(p_da1))
    check("DA1: plan command_files contains DiskCmd.cpp and DiskCmd.h",
          any("DiskCmd.cpp" in f for f in p_da1.get("command_files", [])) and
          any("DiskCmd.h" in f for f in p_da1.get("command_files", [])),
          str(p_da1.get("command_files")))

    # ── DA2: 单 Toolbar 单 Starter (Mode 1: remove_only_child) ──
    addin_da2 = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pSingleTlb, SingleTlb);\n'
        '    AddToolbarView(pSingleTlb, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pDiskCmdStr, DiskCmdStr);\n'
        '    SetAccessCommand(pDiskCmdStr, "DiskCmdHdr");\n'
        '    SetAccessChild(pSingleTlb, pDiskCmdStr);\n'
        '    return pSingleTlb;\n'
        '}\n'
    )
    addin_cpp.write_text(addin_da2, encoding="utf-8")
    r_da2 = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA2: inspection succeeds for single starter toolbar", r_da2.get("status") == "ok", str(r_da2))
    p_da2 = r_da2.get("plan", {})
    splices_da2 = p_da2.get("toolbar_splices", [])
    check("DA2: exactly one toolbar splice", len(splices_da2) == 1, str(splices_da2))
    s_da2 = splices_da2[0] if splices_da2 else {}
    check("DA2: splice_mode is remove_only_child", s_da2.get("splice_mode") == "remove_only_child", str(s_da2))
    check("DA2: starter_var is pDiskCmdStr", s_da2.get("starter_var") == "pDiskCmdStr", str(s_da2))
    check("DA2: prev_starter_var is None", s_da2.get("prev_starter_var") is None, str(s_da2))
    check("DA2: next_starter_var is None", s_da2.get("next_starter_var") is None, str(s_da2))
    check("DA2: statements_to_add is empty", s_da2.get("statements_to_add") == [], str(s_da2))

    # ── DA6: 空 Toolbar 容器与视图保留 ──
    stmts_rem_da2 = s_da2.get("statements_to_remove", [])
    check("DA6: CATCmdContainer not in statements_to_remove",
          not any("CATCmdContainer" in stmt for stmt in stmts_rem_da2), str(stmts_rem_da2))
    check("DA6: AddToolbarView not in statements_to_remove",
          not any("AddToolbarView" in stmt for stmt in stmts_rem_da2), str(stmts_rem_da2))
    check("DA6: SetAccessChild included in statements_to_remove",
          any("SetAccessChild" in stmt for stmt in stmts_rem_da2), str(stmts_rem_da2))

    # Multi-starter chain fixture: pS1 (DiskCmdHdr) -> pS2 (SecondCmdHdr) -> pS3 (ThirdCmdHdr)
    multi_chain_toolbars = (
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlb, MultiTlb);\n'
        '    AddToolbarView(pTlb, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pS1, S1Str);\n'
        '    SetAccessCommand(pS1, "DiskCmdHdr");\n'
        '    NewAccess(CATCmdStarter, pS2, S2Str);\n'
        '    SetAccessCommand(pS2, "SecondCmdHdr");\n'
        '    NewAccess(CATCmdStarter, pS3, S3Str);\n'
        '    SetAccessCommand(pS3, "ThirdCmdHdr");\n'
        '    SetAccessChild(pTlb, pS1);\n'
        '    SetAccessNext(pS1, pS2);\n'
        '    SetAccessNext(pS2, pS3);\n'
        '    return pTlb;\n'
        '}\n'
    )

    # ── DA3: 首节点拆除拓扑缝合 (Mode 2: new_child) ──
    addin_da3 = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '    new SampleWorkbenchAddinHeader("SecondCmdHdr", "TestMod", "OtherCmd", (void *)NULL);\n'
        '}\n\n' +
        multi_chain_toolbars
    )
    addin_cpp.write_text(addin_da3, encoding="utf-8")
    r_da3 = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA3: inspection succeeds for head starter", r_da3.get("status") == "ok", str(r_da3))
    s_da3 = r_da3.get("plan", {}).get("toolbar_splices", [{}])[0]
    check("DA3: splice_mode is new_child", s_da3.get("splice_mode") == "new_child", str(s_da3))
    check("DA3: starter_var is pS1", s_da3.get("starter_var") == "pS1", str(s_da3))
    check("DA3: prev_starter_var is None", s_da3.get("prev_starter_var") is None, str(s_da3))
    check("DA3: next_starter_var is pS2", s_da3.get("next_starter_var") == "pS2", str(s_da3))
    check("DA3: statements_to_add links pS2 as new child",
          "SetAccessChild(pTlb, pS2);" in s_da3.get("statements_to_add", []), str(s_da3))

    # ── DA4: 中间节点拆除拓扑缝合 (Mode 3: relink_next) ──
    multi_chain_middle = multi_chain_toolbars.replace(
        'SetAccessCommand(pS1, "DiskCmdHdr");\n    NewAccess(CATCmdStarter, pS2, S2Str);\n    SetAccessCommand(pS2, "SecondCmdHdr");',
        'SetAccessCommand(pS1, "FirstCmdHdr");\n    NewAccess(CATCmdStarter, pS2, S2Str);\n    SetAccessCommand(pS2, "DiskCmdHdr");'
    )
    addin_da4 = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("FirstCmdHdr", "TestMod", "OtherCmd", (void *)NULL);\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n' +
        multi_chain_middle
    )
    addin_cpp.write_text(addin_da4, encoding="utf-8")
    r_da4 = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA4: inspection succeeds for middle starter", r_da4.get("status") == "ok", str(r_da4))
    s_da4 = r_da4.get("plan", {}).get("toolbar_splices", [{}])[0]
    check("DA4: splice_mode is relink_next", s_da4.get("splice_mode") == "relink_next", str(s_da4))
    check("DA4: starter_var is pS2", s_da4.get("starter_var") == "pS2", str(s_da4))
    check("DA4: prev_starter_var is pS1", s_da4.get("prev_starter_var") == "pS1", str(s_da4))
    check("DA4: next_starter_var is pS3", s_da4.get("next_starter_var") == "pS3", str(s_da4))
    check("DA4: statements_to_add links pS1 directly to pS3",
          "SetAccessNext(pS1, pS3);" in s_da4.get("statements_to_add", []), str(s_da4))

    # ── DA5: 尾节点拆除拓扑缝合 (Mode 4: remove_tail) ──
    multi_chain_tail = multi_chain_toolbars.replace(
        'SetAccessCommand(pS3, "ThirdCmdHdr");',
        'SetAccessCommand(pS3, "DiskCmdHdr");'
    ).replace(
        'SetAccessCommand(pS1, "DiskCmdHdr");',
        'SetAccessCommand(pS1, "FirstCmdHdr");'
    )
    addin_da5 = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("FirstCmdHdr", "TestMod", "OtherCmd", (void *)NULL);\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n' +
        multi_chain_tail
    )
    addin_cpp.write_text(addin_da5, encoding="utf-8")
    r_da5 = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA5: inspection succeeds for tail starter", r_da5.get("status") == "ok", str(r_da5))
    s_da5 = r_da5.get("plan", {}).get("toolbar_splices", [{}])[0]
    check("DA5: splice_mode is remove_tail", s_da5.get("splice_mode") == "remove_tail", str(s_da5))
    check("DA5: starter_var is pS3", s_da5.get("starter_var") == "pS3", str(s_da5))
    check("DA5: prev_starter_var is pS2", s_da5.get("prev_starter_var") == "pS2", str(s_da5))
    check("DA5: next_starter_var is None", s_da5.get("next_starter_var") is None, str(s_da5))
    check("DA5: statements_to_add is empty", s_da5.get("statements_to_add") == [], str(s_da5))

    # ── DA7: 跨 Toolbar 多重挂载独立缝合 ──
    two_toolbars_content = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlbA, ToolbarA);\n'
        '    AddToolbarView(pTlbA, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pA1, A1Str);\n'
        '    SetAccessCommand(pA1, "OtherHdrA");\n'
        '    NewAccess(CATCmdStarter, pA2, A2Str);\n'
        '    SetAccessCommand(pA2, "DiskCmdHdr");\n'
        '    SetAccessChild(pTlbA, pA1);\n'
        '    SetAccessNext(pA1, pA2);\n\n'
        '    NewAccess(CATCmdContainer, pTlbB, ToolbarB);\n'
        '    AddToolbarView(pTlbB, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pB1, B1Str);\n'
        '    SetAccessCommand(pB1, "DiskCmdHdr");\n'
        '    NewAccess(CATCmdStarter, pB2, B2Str);\n'
        '    SetAccessCommand(pB2, "OtherHdrB");\n'
        '    SetAccessChild(pTlbB, pB1);\n'
        '    SetAccessNext(pB1, pB2);\n'
        '    return pTlbA;\n'
        '}\n'
    )
    addin_cpp.write_text(two_toolbars_content, encoding="utf-8")
    r_da7 = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA7: inspection succeeds for multi-toolbar mounts", r_da7.get("status") == "ok", str(r_da7))
    splices_da7 = r_da7.get("plan", {}).get("toolbar_splices", [])
    check("DA7: exactly 2 splices generated", len(splices_da7) == 2, str(splices_da7))
    s_a = next((s for s in splices_da7 if s.get("toolbar_id") == "ToolbarA"), {})
    s_b = next((s for s in splices_da7 if s.get("toolbar_id") == "ToolbarB"), {})
    check("DA7: ToolbarA splice is remove_tail", s_a.get("splice_mode") == "remove_tail" and s_a.get("starter_var") == "pA2", str(s_a))
    check("DA7: ToolbarB splice is new_child", s_b.get("splice_mode") == "new_child" and s_b.get("starter_var") == "pB1", str(s_b))

    # ── DA8: Header 注册缺失硬拦截 ──
    addin_da8 = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    // DiskCmd registration missing entirely\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {\n'
        '}\n'
    )
    addin_cpp.write_text(addin_da8, encoding="utf-8")
    r_da8 = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA8: missing header registration rejected as error", r_da8.get("status") == "error", str(r_da8))
    check("DA8: error indicates not found", "not found" in r_da8.get("error", "").lower(), r_da8.get("error", ""))
    check("DA8: plan is None", r_da8.get("plan") is None, str(r_da8))

    # ── DA9: Header 重复注册冲突拦截 ──
    addin_da9 = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr2", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {\n'
        '}\n'
    )
    addin_cpp.write_text(addin_da9, encoding="utf-8")
    r_da9 = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA9: duplicate header registration rejected as error", r_da9.get("status") == "error", str(r_da9))
    check("DA9: error indicates duplicate", "duplicate" in r_da9.get("error", "").lower(), r_da9.get("error", ""))
    check("DA9: plan is None", r_da9.get("plan") is None, str(r_da9))

    # ── DA10: 目标 Toolbar 异常链拦截与非目标隔离 ──
    addin_da10_isolated = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlbA, ToolbarA);\n'
        '    AddToolbarView(pTlbA, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pA1, A1Str);\n'
        '    SetAccessCommand(pA1, "DiskCmdHdr");\n'
        '    SetAccessChild(pTlbA, pA1);\n\n'
        '    NewAccess(CATCmdContainer, pTlbC, ToolbarC);\n'
        '    AddToolbarView(pTlbC, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pC1, C1Str);\n'
        '    NewAccess(CATCmdStarter, pC2, C2Str);\n'
        '    NewAccess(CATCmdStarter, pC3, C3Str);\n'
        '    SetAccessChild(pTlbC, pC1);\n'
        '    SetAccessNext(pC1, pC2);\n'
        '    SetAccessNext(pC1, pC3);\n'
        '    return pTlbA;\n'
        '}\n'
    )
    addin_cpp.write_text(addin_da10_isolated, encoding="utf-8")
    r_da10_iso = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA10: non-target toolbar with malformed fork is ignored (inspection succeeds)",
          r_da10_iso.get("status") == "ok", str(r_da10_iso))
    check("DA10: plan contains only ToolbarA splice",
          len(r_da10_iso.get("plan", {}).get("toolbar_splices", [])) == 1, str(r_da10_iso))

    addin_da10_target_fail = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlbA, ToolbarA);\n'
        '    AddToolbarView(pTlbA, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pA1, A1Str);\n'
        '    NewAccess(CATCmdStarter, pA2, A2Str);\n'
        '    NewAccess(CATCmdStarter, pA3, A3Str);\n'
        '    SetAccessCommand(pA1, "DiskCmdHdr");\n'
        '    SetAccessChild(pTlbA, pA1);\n'
        '    SetAccessNext(pA1, pA2);\n'
        '    SetAccessNext(pA1, pA3);\n'
        '    return pTlbA;\n'
        '}\n'
    )
    addin_cpp.write_text(addin_da10_target_fail, encoding="utf-8")
    r_da10_fail = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA10: malformed chain on target toolbar rejected as error",
          r_da10_fail.get("status") == "error", str(r_da10_fail))
    check("DA10: error message identifies fork/branching",
          "fork" in r_da10_fail.get("error", "").lower() or "branching" in r_da10_fail.get("error", "").lower(),
          r_da10_fail.get("error", ""))

    # 10b: 非目标 Toolbar 包含残缺语法语句不污染目标 Toolbar
    addin_da10b_syntax_iso = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlbA, ToolbarA);\n'
        '    AddToolbarView(pTlbA, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pA1, A1Str);\n'
        '    SetAccessCommand(pA1, "DiskCmdHdr");\n'
        '    SetAccessChild(pTlbA, pA1);\n\n'
        '    NewAccess(CATCmdContainer, pTlbC, ToolbarC);\n'
        '    AddToolbarView(pTlbC, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pC1, C1Str);\n'
        '    SetAccessChild(pTlbC, pC1);\n'
        '    SetAccessNext(pC1);\n'  # Incomplete statement in non-target ToolbarC
        '    return pTlbA;\n'
        '}\n'
    )
    addin_cpp.write_text(addin_da10b_syntax_iso, encoding="utf-8")
    r_da10b = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA10b: non-target toolbar incomplete syntax does not pollute target toolbar",
          r_da10b.get("status") == "ok", str(r_da10b))

    # 10c: 目标 Toolbar 的 first_starter 存在多前驱汇聚必须被拦截
    addin_da10c_first_starter_pred = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlbA, ToolbarA);\n'
        '    AddToolbarView(pTlbA, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pA1, A1Str);\n'
        '    NewAccess(CATCmdStarter, pX, XStr);\n'
        '    NewAccess(CATCmdStarter, pY, YStr);\n'
        '    SetAccessCommand(pA1, "DiskCmdHdr");\n'
        '    SetAccessChild(pTlbA, pA1);\n'
        '    SetAccessNext(pX, pA1);\n'
        '    SetAccessNext(pY, pA1);\n'
        '    return pTlbA;\n'
        '}\n'
    )
    addin_cpp.write_text(addin_da10c_first_starter_pred, encoding="utf-8")
    r_da10c = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA10c: multiple predecessors to first_starter rejected as error",
          r_da10c.get("status") == "error", str(r_da10c))
    check("DA10c: error message identifies multiple predecessors to first_starter",
          "multiple predecessors" in r_da10c.get("error", "").lower() and "pa1" in r_da10c.get("error", "").lower(),
          r_da10c.get("error", ""))

    # ── DA11: 事务门禁零变更 ──
    caller_cs = ChangeSet(action="caller_audit", description="caller audit CS")
    r_da11 = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench", cs=caller_cs)
    check("DA11: inspect returns error on malformed target", r_da11.get("status") == "error", str(r_da11))
    check("DA11: caller CS created is empty", caller_cs.created == {}, str(caller_cs.created))
    check("DA11: caller CS modified is empty", caller_cs.modified == {}, str(caller_cs.modified))
    check("DA11: caller CS deleted is empty", caller_cs.deleted == [], str(caller_cs.deleted))
    check("DA11: caller CS warnings is empty", caller_cs.warnings == [], str(caller_cs.warnings))

    # ── DA12: 非目标指令与资源隔离 ──
    addin_da12 = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("OtherCmdHdr", "TestMod", "OtherCmd", (void *)NULL);\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlb, SingleTlb);\n'
        '    AddToolbarView(pTlb, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pOtherStr, OtherStr);\n'
        '    SetAccessCommand(pOtherStr, "OtherCmdHdr");\n'
        '    NewAccess(CATCmdStarter, pDiskCmdStr, DiskCmdStr);\n'
        '    SetAccessCommand(pDiskCmdStr, "DiskCmdHdr");\n'
        '    SetAccessChild(pTlb, pOtherStr);\n'
        '    SetAccessNext(pOtherStr, pDiskCmdStr);\n'
        '    return pTlb;\n'
        '}\n'
    )
    addin_cpp.write_text(addin_da12, encoding="utf-8")
    r_da12 = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA12: inspection succeeds alongside other commands", r_da12.get("status") == "ok", str(r_da12))
    p_da12 = r_da12.get("plan", {})
    check("DA12: plan header_statement contains DiskCmdHdr only",
          "DiskCmdHdr" in p_da12.get("header_statement", "") and "OtherCmdHdr" not in p_da12.get("header_statement", ""),
          p_da12.get("header_statement", ""))
    s_da12 = p_da12.get("toolbar_splices", [{}])[0]
    check("DA12: toolbar splice affects pDiskCmdStr only",
          s_da12.get("starter_var") == "pDiskCmdStr" and s_da12.get("splice_mode") == "remove_tail",
          str(s_da12))
    check("DA12: statements_to_remove does not remove declaration or command of OtherCmd",
          not any("NewAccess(CATCmdStarter, pOtherStr" in stmt or "OtherCmdHdr" in stmt for stmt in s_da12.get("statements_to_remove", [])),
          str(s_da12.get("statements_to_remove")))

    # ── DA13: 同一 Toolbar 重复 MountKey 拦截 ──
    addin_da13 = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pTlb, SingleTlb);\n'
        '    AddToolbarView(pTlb, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pS1, S1Str);\n'
        '    SetAccessCommand(pS1, "DiskCmdHdr");\n'
        '    NewAccess(CATCmdStarter, pS2, S2Str);\n'
        '    SetAccessCommand(pS2, "DiskCmdHdr");\n'
        '    SetAccessChild(pTlb, pS1);\n'
        '    SetAccessNext(pS1, pS2);\n'
        '    return pTlb;\n'
        '}\n'
    )
    addin_cpp.write_text(addin_da13, encoding="utf-8")
    r_da13 = inspect_delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA13: duplicate MountKey in same toolbar rejected as error", r_da13.get("status") == "error", str(r_da13))
    check("DA13: error identifies duplicate mount", "duplicate mount" in r_da13.get("error", "").lower(), r_da13.get("error", ""))
    check("DA13: plan is None", r_da13.get("plan") is None, str(r_da13))

    # ══════════════════════════════════════════════════════════════════
    # R-4-A Phase 2: Command Cascade Delete Execution Tests (DA14~DA20)
    # ══════════════════════════════════════════════════════════════════

    res_dir = fw_dir / "CNext" / "resources" / "msgcatalog"
    res_dir.mkdir(parents=True, exist_ok=True)
    nls_file = res_dir / "SampleWorkbenchAddinHeader.CATNls"
    nls_file.write_text('SampleWorkbenchAddinHeader.DiskCmdHdr.Title = "Disk Command";\n', encoding="utf-8")
    rsc_file = res_dir / "SampleWorkbenchAddinHeader.CATRsc"
    rsc_file.write_text('SampleWorkbenchAddinHeader.DiskCmdHdr.Icon.Normal = "I_DiskCmd";\n', encoding="utf-8")
    icon_dir = fw_dir / "CNext" / "resources" / "graphic" / "icons" / "normal"
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon_file = icon_dir / "I_DiskCmd.bmp"
    icon_file.write_bytes(b"BMfakebmpheader")

    # ── DA14: 真实级联删除执行 (Mode 1: remove_only_child) ──
    addin_cpp.write_text(addin_da2, encoding="utf-8")
    (src_dir / "DiskCmd.cpp").write_text("CATStateCommand BuildGraph DiskCmd\n", encoding="utf-8")
    (mod_dir / "LocalInterfaces" / "DiskCmd.h").write_text("// DiskCmd header\n", encoding="utf-8")
    r_da14 = delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA14: delete_command returns pending status", r_da14.get("status") == "pending", str(r_da14))
    cs_dict_da14 = r_da14.get("changeset", {})
    check("DA14: changeset dict contains deleted files", len(cs_dict_da14.get("deleted", [])) >= 2, str(cs_dict_da14.get("deleted")))
    cs_da14 = ChangeSet.from_dict(cs_dict_da14)
    apply_da14 = cs_da14.apply(workspace_root=da_ws)
    check("DA14: changeset apply succeeds", apply_da14.get("status") == "applied", str(apply_da14))
    check("DA14: DiskCmd.cpp physically deleted", not (src_dir / "DiskCmd.cpp").exists())
    check("DA14: DiskCmd.h physically deleted", not (mod_dir / "LocalInterfaces" / "DiskCmd.h").exists())
    addin_post_da14 = addin_cpp.read_text(encoding="utf-8")
    check("DA14: DiskCmd registration removed from CreateCommands", "DiskCmd" not in addin_post_da14, addin_post_da14)
    check("DA14: Toolbar container preserved in CreateToolbars", "NewAccess(CATCmdContainer, pSingleTlb, SingleTlb);" in addin_post_da14)
    check("DA14: AddToolbarView preserved", "AddToolbarView(pSingleTlb, 1, Top);" in addin_post_da14)
    check("DA14: Starter pDiskCmdStr removed from CreateToolbars", "pDiskCmdStr" not in addin_post_da14)
    check("DA14: CATNls file preserved on disk", nls_file.exists())
    check("DA14: CATRsc file preserved on disk", rsc_file.exists())
    check("DA14: icon file preserved on disk", icon_file.exists())
    check("DA14: orphan resources reported in metadata", len(cs_da14.metadata.get("orphan_resources", [])) >= 2, str(cs_da14.metadata))

    # ── DA15: 首节点物理删除与拓扑缝合 (Mode 2: new_child) ──
    addin_cpp.write_text(addin_da3, encoding="utf-8")
    (src_dir / "DiskCmd.cpp").write_text("CATStateCommand BuildGraph DiskCmd\n", encoding="utf-8")
    (mod_dir / "LocalInterfaces" / "DiskCmd.h").write_text("// DiskCmd header\n", encoding="utf-8")
    r_da15 = delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA15: delete_command returns pending status", r_da15.get("status") == "pending", str(r_da15))
    cs_da15 = ChangeSet.from_dict(r_da15.get("changeset", {}))
    apply_da15 = cs_da15.apply(workspace_root=da_ws)
    check("DA15: changeset apply succeeds", apply_da15.get("status") == "applied", str(apply_da15))
    addin_post_da15 = addin_cpp.read_text(encoding="utf-8")
    check("DA15: SetAccessChild now points to pS2", "SetAccessChild(pTlb, pS2);" in addin_post_da15, addin_post_da15)
    check("DA15: pS1 starter removed", "pS1" not in addin_post_da15, addin_post_da15)
    check("DA15: pS2 and pS3 remain intact", "pS2" in addin_post_da15 and "pS3" in addin_post_da15, addin_post_da15)
    check("DA15: SetAccessNext(pS2, pS3) remains intact", "SetAccessNext(pS2, pS3);" in addin_post_da15, addin_post_da15)
    check("DA15: SecondCmdHdr remains in CreateCommands", "SecondCmdHdr" in addin_post_da15, addin_post_da15)

    # ── DA16: 中间节点物理删除与拓扑缝合 (Mode 3: relink_next) ──
    addin_cpp.write_text(addin_da4, encoding="utf-8")
    (src_dir / "DiskCmd.cpp").write_text("CATStateCommand BuildGraph DiskCmd\n", encoding="utf-8")
    (mod_dir / "LocalInterfaces" / "DiskCmd.h").write_text("// DiskCmd header\n", encoding="utf-8")
    r_da16 = delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA16: delete_command returns pending status", r_da16.get("status") == "pending", str(r_da16))
    cs_da16 = ChangeSet.from_dict(r_da16.get("changeset", {}))
    apply_da16 = cs_da16.apply(workspace_root=da_ws)
    check("DA16: changeset apply succeeds", apply_da16.get("status") == "applied", str(apply_da16))
    addin_post_da16 = addin_cpp.read_text(encoding="utf-8")
    check("DA16: SetAccessNext seamlessly bridges pS1 to pS3", "SetAccessNext(pS1, pS3);" in addin_post_da16, addin_post_da16)
    check("DA16: pS2 starter removed", "pS2" not in addin_post_da16, addin_post_da16)
    check("DA16: SetAccessChild(pTlb, pS1) remains intact", "SetAccessChild(pTlb, pS1);" in addin_post_da16, addin_post_da16)
    check("DA16: FirstCmdHdr remains in CreateCommands", "FirstCmdHdr" in addin_post_da16, addin_post_da16)

    # ── DA17: 尾节点物理删除与拓扑截断 (Mode 4: remove_tail) ──
    addin_cpp.write_text(addin_da5, encoding="utf-8")
    (src_dir / "DiskCmd.cpp").write_text("CATStateCommand BuildGraph DiskCmd\n", encoding="utf-8")
    (mod_dir / "LocalInterfaces" / "DiskCmd.h").write_text("// DiskCmd header\n", encoding="utf-8")
    r_da17 = delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA17: delete_command returns pending status", r_da17.get("status") == "pending", str(r_da17))
    cs_da17 = ChangeSet.from_dict(r_da17.get("changeset", {}))
    apply_da17 = cs_da17.apply(workspace_root=da_ws)
    check("DA17: changeset apply succeeds", apply_da17.get("status") == "applied", str(apply_da17))
    addin_post_da17 = addin_cpp.read_text(encoding="utf-8")
    check("DA17: pS3 removed from CreateToolbars", "pS3" not in addin_post_da17, addin_post_da17)
    check("DA17: SetAccessChild(pTlb, pS1) remains", "SetAccessChild(pTlb, pS1);" in addin_post_da17, addin_post_da17)
    check("DA17: SetAccessNext(pS1, pS2) remains", "SetAccessNext(pS1, pS2);" in addin_post_da17, addin_post_da17)

    # ── DA18: 多工具栏物理删除原子缝合 ──
    addin_cpp.write_text(two_toolbars_content, encoding="utf-8")
    (src_dir / "DiskCmd.cpp").write_text("CATStateCommand BuildGraph DiskCmd\n", encoding="utf-8")
    (mod_dir / "LocalInterfaces" / "DiskCmd.h").write_text("// DiskCmd header\n", encoding="utf-8")
    r_da18 = delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    check("DA18: delete_command returns pending status", r_da18.get("status") == "pending", str(r_da18))
    cs_da18 = ChangeSet.from_dict(r_da18.get("changeset", {}))
    apply_da18 = cs_da18.apply(workspace_root=da_ws)
    check("DA18: changeset apply succeeds", apply_da18.get("status") == "applied", str(apply_da18))
    addin_post_da18 = addin_cpp.read_text(encoding="utf-8")
    check("DA18: pA2 removed from ToolbarA", "pA2" not in addin_post_da18, addin_post_da18)
    check("DA18: pA1 remains in ToolbarA", "pA1" in addin_post_da18, addin_post_da18)
    check("DA18: pB1 removed from ToolbarB", "pB1" not in addin_post_da18, addin_post_da18)
    check("DA18: pB2 remains in ToolbarB", "pB2" in addin_post_da18, addin_post_da18)
    check("DA18: ToolbarB SetAccessChild points to pB2", "SetAccessChild(pTlbB, pB2);" in addin_post_da18, addin_post_da18)
    check("DA18: ToolbarA container intact", "NewAccess(CATCmdContainer, pTlbA, ToolbarA);" in addin_post_da18)
    check("DA18: ToolbarB container intact", "NewAccess(CATCmdContainer, pTlbB, ToolbarB);" in addin_post_da18)

    # ── DA19: 预检失败的事务门禁零变更 ──
    addin_cpp.write_text(addin_da10_target_fail, encoding="utf-8")
    (src_dir / "DiskCmd.cpp").write_text("CATStateCommand BuildGraph DiskCmd\n", encoding="utf-8")
    (mod_dir / "LocalInterfaces" / "DiskCmd.h").write_text("// DiskCmd header\n", encoding="utf-8")
    caller_cs_da19 = ChangeSet(action="caller_audit", description="caller audit")
    r_da19 = delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench", cs=caller_cs_da19)
    check("DA19: delete_command returns error on malformed target", r_da19.get("status") == "error", str(r_da19))
    check("DA19: caller CS created is empty", caller_cs_da19.created == {})
    check("DA19: caller CS modified is empty", caller_cs_da19.modified == {})
    check("DA19: caller CS deleted is empty", caller_cs_da19.deleted == [])
    check("DA19: DiskCmd.cpp still exists on disk", (src_dir / "DiskCmd.cpp").exists())
    check("DA19: DiskCmd.h still exists on disk", (mod_dir / "LocalInterfaces" / "DiskCmd.h").exists())

    # ── DA20: 回滚安全性验证 ──
    addin_cpp.write_text(addin_da2, encoding="utf-8")
    (src_dir / "DiskCmd.cpp").write_text("CATStateCommand BuildGraph DiskCmd\n", encoding="utf-8")
    (mod_dir / "LocalInterfaces" / "DiskCmd.h").write_text("// DiskCmd header\n", encoding="utf-8")
    cs_da20 = ChangeSet(action="delete_command", description="delete with rollback test")
    r_da20 = delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench", cs=cs_da20)
    check("DA20: delete_command returns pending status", r_da20.get("status") == "pending", str(r_da20))
    apply_da20 = cs_da20.apply(workspace_root=da_ws)
    check("DA20: apply succeeds", apply_da20.get("status") == "applied", str(apply_da20))
    check("DA20: files deleted after apply", not (src_dir / "DiskCmd.cpp").exists())
    # Rollback
    rb_res = cs_da20.rollback()
    check("DA20: rollback succeeds", rb_res.get("status") == "rolled_back", str(rb_res))
    check("DA20: DiskCmd.cpp restored after rollback", (src_dir / "DiskCmd.cpp").exists())
    check("DA20: DiskCmd.h restored after rollback", (mod_dir / "LocalInterfaces" / "DiskCmd.h").exists())
    check("DA20: Addin content restored after rollback", "DiskCmdHdr" in addin_cpp.read_text(encoding="utf-8"))

    # ── DA21: 语句移除严格限定在函数作用域内 (P1 Scope Bound) ──
    addin_da21 = (
        addin_base_header +
        'void SampleWorkbenchAddin::HelperBefore() {\n'
        '    // Identical statement appearing before CreateCommands\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pSingleTlb, SingleTlb);\n'
        '    AddToolbarView(pSingleTlb, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pDiskCmdStr, DiskCmdStr);\n'
        '    SetAccessCommand(pDiskCmdStr, "DiskCmdHdr");\n'
        '    SetAccessChild(pSingleTlb, pDiskCmdStr);\n'
        '    return pSingleTlb;\n'
        '}\n\n'
        'void SampleWorkbenchAddin::HelperAfter() {\n'
        '    // Identical statement appearing after CreateToolbars\n'
        '    SetAccessCommand(pDiskCmdStr, "DiskCmdHdr");\n'
        '}\n'
    )
    addin_cpp.write_text(addin_da21, encoding="utf-8")
    (src_dir / "DiskCmd.cpp").write_text("CATStateCommand BuildGraph DiskCmd\n", encoding="utf-8")
    (mod_dir / "LocalInterfaces" / "DiskCmd.h").write_text("// DiskCmd header\n", encoding="utf-8")
    r_da21 = delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    cs_da21 = ChangeSet.from_dict(r_da21.get("changeset", {}))
    apply_da21 = cs_da21.apply(workspace_root=da_ws)
    check("DA21: changeset apply succeeds", apply_da21.get("status") == "applied", str(apply_da21))
    addin_post_da21 = addin_cpp.read_text(encoding="utf-8")
    cc_post_da21 = addin_post_da21.split("CreateCommands()")[1].split("CreateToolbars()")[0]
    check("DA21: CreateCommands scope statement removed", "DiskCmdHdr" not in cc_post_da21, cc_post_da21)
    check("DA21: HelperBefore scope statement intact",
          'HelperBefore() {\n    // Identical statement appearing before CreateCommands\n    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);' in addin_post_da21,
          addin_post_da21)
    check("DA21: HelperAfter scope statement intact",
          'HelperAfter() {\n    // Identical statement appearing after CreateToolbars\n    SetAccessCommand(pDiskCmdStr, "DiskCmdHdr");' in addin_post_da21,
          addin_post_da21)

    # ── DA22: Imakefile 词元边界精确清理，防止子串误伤 (P1 Token Match) ──
    imk_da22 = (
        'BUILT_OBJECT_TYPE=SHARED LIBRARY\n'
        'LINK_WITH=JS0GROUP JS0CORBA\n\n'
        'SOURCES = \\\n'
        '    DiskCmd.cpp \\\n'
        '    DiskCmdHelper.cpp \\\n'
        '    DiskCmdExtra.cpp\n'
    )
    (mod_dir / "Imakefile.mk").write_text(imk_da22, encoding="utf-8")
    addin_cpp.write_text(addin_da2, encoding="utf-8")
    (src_dir / "DiskCmd.cpp").write_text("CATStateCommand BuildGraph DiskCmd\n", encoding="utf-8")
    (mod_dir / "LocalInterfaces" / "DiskCmd.h").write_text("// DiskCmd header\n", encoding="utf-8")
    r_da22 = delete_command(ctx, "DiskCmd", workbench_name="SampleWorkbench")
    cs_da22 = ChangeSet.from_dict(r_da22.get("changeset", {}))
    apply_da22 = cs_da22.apply(workspace_root=da_ws)
    check("DA22: changeset apply succeeds", apply_da22.get("status") == "applied", str(apply_da22))
    imk_post_da22 = (mod_dir / "Imakefile.mk").read_text(encoding="utf-8")
    check("DA22: DiskCmd.cpp cleanly removed from Imakefile", "DiskCmd.cpp" not in imk_post_da22, imk_post_da22)
    check("DA22: DiskCmdHelper.cpp preserved in Imakefile", "DiskCmdHelper.cpp" in imk_post_da22, imk_post_da22)
    check("DA22: DiskCmdExtra.cpp preserved in Imakefile", "DiskCmdExtra.cpp" in imk_post_da22, imk_post_da22)
    check("DA22: LINK_WITH directives intact", "LINK_WITH=JS0GROUP JS0CORBA" in imk_post_da22, imk_post_da22)
    check("DA22: BUILT_OBJECT_TYPE intact", "BUILT_OBJECT_TYPE=SHARED LIBRARY" in imk_post_da22, imk_post_da22)

    # ══════════════════════════════════════════════════════════════════
    # R-4-B Phase 1: Command Rename Pre-validation & Semantic Contract (inspect_rename_command)
    # RN1  (标准合法命令重命名): Plan structure complete; HeaderID stable; source_snapshot hashes present
    # RN2  (新名称已存在): Collision with existing command in module/workspace rejected
    # RN3  (非法 C++ 标识符): Invalid characters/digits rejected
    # RN4  (类声明/定义/构造/析构精准替换): Bounded replacements; comments & string literals untouched
    # RN5  (CATCreateClass 宏精确更新): CATCreateClass(DiskCmd) -> CATCreateClass(NewDiskCmd)
    # RN6  (相似前缀命令隔离): DiskCmdHelper / DiskCmdExtra untouched
    # RN7  (Imakefile 相似文件名隔离): DiskCmd.cpp renamed, DiskCmdHelper.cpp intact
    # RN8  (4 参数 Header 第三参数精确更新): ClassName updated, HeaderID/LoadName/NULL strictly preserved
    # RN9  (HeaderID 稳定与 Toolbar 引用零变动): Toolbar audited, needs_update is False
    # RN10 (歧义 Header 注册硬拦截): Ambiguous header matches rejected as error
    # RN11 (预检失败 ChangeSet 零变更): Pre-validation failure leaves caller ChangeSet untouched
    # RN12 (目标重命名文件冲突拦截): Pre-existing target file on disk or staged rejected
    # RN13 (staged ChangeSet 内容优先): Reads staged changes before disk
    # RN14 (ChangeSet 语义与故障恢复验证):
    #       RN14a: Normal apply
    #       RN14b: Normal rollback
    #       RN14c: Target conflict hard rejection before any write
    #       RN14d: Mid-flight failure recovery preserves old files & cleans new files
    #       RN14e: Multi-file batch atomicity
    # RN15 (资源保护与只读审计): NLS/RSC/Icon audited, status preserved, no mutation tasks
    # ══════════════════════════════════════════════════════════════════

    # ── 准备环境：重新部署 DiskCmd 源码与工作台 ──
    diskcmd_h_code = (
        '#ifndef DiskCmd_H\n'
        '#define DiskCmd_H\n\n'
        '#include "CATCommand.h"\n\n'
        'class ExportedByTestMod DiskCmd : public CATCommand {\n'
        '    CATDeclareClass;\n'
        'public:\n'
        '    DiskCmd();\n'
        '    virtual ~DiskCmd();\n'
        '    virtual CATStatusChangeRC Activate(CATCommand *iFromClient, CATNotification *iEvtDat);\n'
        '};\n\n'
        '#endif\n'
    )
    diskcmd_cpp_code = (
        '#include "DiskCmd.h"\n'
        '#include "CATCreateExternalObject.h"\n\n'
        'CATCreateClass(DiskCmd);\n\n'
        'DiskCmd::DiskCmd() : CATCommand(NULL, "DiskCmd") {\n'
        '    const char* keep_literal = "DiskCmd";\n'
        '    DiskCmdHelper* pHelper = NULL;\n'
        '}\n\n'
        'DiskCmd::~DiskCmd() {\n'
        '}\n\n'
        'CATStatusChangeRC DiskCmd::Activate(CATCommand *iFromClient, CATNotification *iEvtDat) {\n'
        '    return CATStatusChangeRCCompleted;\n'
        '}\n'
    )
    (mod_dir / "LocalInterfaces" / "DiskCmd.h").write_text(diskcmd_h_code, encoding="utf-8")
    (src_dir / "DiskCmd.cpp").write_text(diskcmd_cpp_code, encoding="utf-8")
    imk_rn = (
        'BUILT_OBJECT_TYPE=SHARED LIBRARY\n'
        'LINK_WITH=JS0GROUP JS0CORBA\n\n'
        'SOURCES = \\\n'
        '    DiskCmd.cpp \\\n'
        '    DiskCmdHelper.cpp\n'
    )
    (mod_dir / "Imakefile.mk").write_text(imk_rn, encoding="utf-8")
    addin_rn = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'CATCmdContainer* SampleWorkbenchAddin::CreateToolbars() {\n'
        '    NewAccess(CATCmdContainer, pSingleTlb, SingleTlb);\n'
        '    AddToolbarView(pSingleTlb, 1, Top);\n'
        '    NewAccess(CATCmdStarter, pDiskCmdStr, DiskCmdStr);\n'
        '    SetAccessCommand(pDiskCmdStr, "DiskCmdHdr");\n'
        '    SetAccessChild(pSingleTlb, pDiskCmdStr);\n'
        '    return pSingleTlb;\n'
        '}\n'
    )
    addin_cpp.write_text(addin_rn, encoding="utf-8")
    ctx.refresh()

    # ── RN1: 标准合法命令重命名 Plan 检查 ──
    r_rn1 = inspect_rename_command(ctx, "DiskCmd", "NewDiskCmd", workbench_name="SampleWorkbench")
    check("RN1: inspect_rename_command succeeds", r_rn1.get("status") == "ok", str(r_rn1))
    p_rn1 = r_rn1.get("plan", {})
    check("RN1: plan old_name matches", p_rn1.get("command_identity", {}).get("old_name") == "DiskCmd")
    check("RN1: plan new_name matches", p_rn1.get("command_identity", {}).get("new_name") == "NewDiskCmd")
    check("RN1: plan module matches", p_rn1.get("command_identity", {}).get("module") == "TestMod.m")
    check("RN1: plan file_renames count == 2", len(p_rn1.get("file_renames", [])) == 2)
    for fr in p_rn1.get("file_renames", []):
        check("RN1: file_rename has source_snapshot with hash",
              "content_hash" in fr.get("source_snapshot", {}) and "content_length" in fr.get("source_snapshot", {}))

    # ── RN2: 新名称已存在硬拦截 ──
    (src_dir / "ExistingCmd.cpp").write_text("// ExistingCmd\n", encoding="utf-8")
    ctx.refresh()
    r_rn2 = inspect_rename_command(ctx, "DiskCmd", "ExistingCmd", workbench_name="SampleWorkbench")
    check("RN2: existing command name rejected as error", r_rn2.get("status") == "error", str(r_rn2))
    check("RN2: error message indicates already exists", "already exists" in r_rn2.get("error", "").lower(), r_rn2.get("error", ""))
    (src_dir / "ExistingCmd.cpp").unlink()
    ctx.refresh()

    # ── RN3: 非法 C++ 标识符硬拦截 ──
    r_rn3a = inspect_rename_command(ctx, "DiskCmd", "123BadCmd")
    check("RN3a: digit prefix rejected", r_rn3a.get("status") == "error" and "identifier" in r_rn3a.get("error", "").lower())
    r_rn3b = inspect_rename_command(ctx, "DiskCmd", "Bad-Cmd")
    check("RN3b: hyphen rejected", r_rn3b.get("status") == "error" and "identifier" in r_rn3b.get("error", "").lower())
    r_rn3c = inspect_rename_command(ctx, "DiskCmd", "Bad Cmd")
    check("RN3c: whitespace rejected", r_rn3c.get("status") == "error" and "identifier" in r_rn3c.get("error", "").lower())
    r_rn3d = inspect_rename_command(ctx, "DiskCmd", "DiskCmd")
    check("RN3d: identical name rejected", r_rn3d.get("status") == "error" and "identical" in r_rn3d.get("error", "").lower())

    # ── RN4: 类声明、定义、构造函数、析构函数精准语义替换 ──
    h_fr = next((fr for fr in p_rn1.get("file_renames", []) if fr.get("is_header")), {})
    h_new = h_fr.get("new_content", "")
    check("RN4: include guard ifndef updated", "#ifndef NewDiskCmd_H" in h_new, h_new)
    check("RN4: include guard define updated", "#define NewDiskCmd_H" in h_new, h_new)
    check("RN4: class declaration updated", "class ExportedByTestMod NewDiskCmd : public CATCommand" in h_new, h_new)
    check("RN4: ctor declaration updated", "NewDiskCmd();" in h_new, h_new)
    check("RN4: dtor declaration updated", "~NewDiskCmd();" in h_new, h_new)

    cpp_fr = next((fr for fr in p_rn1.get("file_renames", []) if not fr.get("is_header")), {})
    cpp_new = cpp_fr.get("new_content", "")
    check("RN4: ctor definition updated", "NewDiskCmd::NewDiskCmd()" in cpp_new, cpp_new)
    check("RN4: dtor definition updated", "NewDiskCmd::~NewDiskCmd()" in cpp_new, cpp_new)
    check("RN4: member function scope updated", "NewDiskCmd::Activate(" in cpp_new, cpp_new)
    check("RN4: string literal untouched", '"DiskCmd"' in cpp_new, cpp_new)

    # ── RN5: CATCreateClass 宏精确更新 ──
    check("RN5: CATCreateClass macro updated", "CATCreateClass(NewDiskCmd);" in cpp_new, cpp_new)

    # ── RN6: 相似前缀命令隔离 ──
    check("RN6: DiskCmdHelper untouched in cpp", "DiskCmdHelper* pHelper = NULL;" in cpp_new, cpp_new)

    # ── RN7: Imakefile 相似文件名隔离 ──
    imk_upd = p_rn1.get("imakefile_updates", {})
    imk_new = imk_upd.get("new_content", "")
    check("RN7: DiskCmd.cpp renamed in Imakefile", "NewDiskCmd.cpp" in imk_new, imk_new)
    check("RN7: DiskCmdHelper.cpp preserved in Imakefile", "DiskCmdHelper.cpp" in imk_new, imk_new)
    check("RN7: LINK_WITH intact in Imakefile", "LINK_WITH=JS0GROUP JS0CORBA" in imk_new, imk_new)

    # ── RN8: 4 参数 Header 第三参数精确更新 ──
    hdr_upd = p_rn1.get("header_update", {})
    check("RN8: header_class stable", hdr_upd.get("header_class") == "SampleWorkbenchAddinHeader")
    check("RN8: header_id strictly stable", hdr_upd.get("header_id") == "DiskCmdHdr")
    check("RN8: load_name strictly stable", hdr_upd.get("load_name") == "TestMod")
    check("RN8: old_class_name matches", hdr_upd.get("old_class_name") == "DiskCmd")
    check("RN8: new_class_name matches", hdr_upd.get("new_class_name") == "NewDiskCmd")
    expected_new_stmt = 'new SampleWorkbenchAddinHeader("DiskCmdHdr", "TestMod", "NewDiskCmd", (void *)NULL);'
    check("RN8: new_statement replaces third parameter only", hdr_upd.get("new_statement") == expected_new_stmt, hdr_upd.get("new_statement"))

    # ── RN9: HeaderID 稳定与 Toolbar 引用零变动 ──
    tb_refs = p_rn1.get("toolbar_references", [])
    check("RN9: toolbar_references found", len(tb_refs) == 1, str(tb_refs))
    check("RN9: starter_var is pDiskCmdStr", tb_refs[0].get("starter_var") == "pDiskCmdStr")
    check("RN9: header_id is DiskCmdHdr", tb_refs[0].get("header_id") == "DiskCmdHdr")
    check("RN9: needs_update is False", tb_refs[0].get("needs_update") is False)

    # ── RN10: 歧义 Header 注册硬拦截 ──
    addin_rn10 = (
        addin_base_header +
        'void SampleWorkbenchAddin::CreateCommands() {\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr1", "TestMod", "DiskCmd", (void *)NULL);\n'
        '    new SampleWorkbenchAddinHeader("DiskCmdHdr2", "TestMod", "DiskCmd", (void *)NULL);\n'
        '}\n\n'
        'void SampleWorkbenchAddin::CreateToolbars() {}\n'
    )
    addin_cpp.write_text(addin_rn10, encoding="utf-8")
    r_rn10 = inspect_rename_command(ctx, "DiskCmd", "NewDiskCmd", workbench_name="SampleWorkbench")
    check("RN10: ambiguous header registration rejected as error", r_rn10.get("status") == "error", str(r_rn10))
    check("RN10: error indicates ambiguous", "ambiguous" in r_rn10.get("error", "").lower(), r_rn10.get("error", ""))
    addin_cpp.write_text(addin_rn, encoding="utf-8")

    # ── RN11: 预检失败 ChangeSet 零变更 ──
    caller_cs_rn11 = ChangeSet(action="caller_audit", description="caller audit")
    r_rn11 = inspect_rename_command(ctx, "DiskCmd", "123BadCmd", cs=caller_cs_rn11)
    check("RN11: inspect returns error on bad name", r_rn11.get("status") == "error", str(r_rn11))
    check("RN11: caller CS created is empty", caller_cs_rn11.created == {})
    check("RN11: caller CS modified is empty", caller_cs_rn11.modified == {})
    check("RN11: caller CS deleted is empty", caller_cs_rn11.deleted == [])

    # ── RN12: 目标重命名文件冲突拦截 ──
    (src_dir / "NewDiskCmd.cpp").write_text("// collision\n", encoding="utf-8")
    r_rn12 = inspect_rename_command(ctx, "DiskCmd", "NewDiskCmd", workbench_name="SampleWorkbench")
    check("RN12: existing target file rejected as error", r_rn12.get("status") == "error", str(r_rn12))
    check("RN12: error indicates target file already exists", "already exists" in r_rn12.get("error", "").lower(), r_rn12.get("error", ""))
    (src_dir / "NewDiskCmd.cpp").unlink()

    # ── RN13: staged ChangeSet 内容优先 ──
    staged_cs = ChangeSet(action="staged_preview", description="staged preview")
    staged_addin_content = addin_rn.replace("DiskCmdStr", "StagedDiskCmdStr")
    staged_cs.add_modify(addin_cpp, staged_addin_content)
    r_rn13 = inspect_rename_command(ctx, "DiskCmd", "NewDiskCmd", workbench_name="SampleWorkbench", cs=staged_cs)
    check("RN13: inspect succeeds with staged ChangeSet", r_rn13.get("status") == "ok", str(r_rn13))

    # ── RN14a: ChangeSet 文件重命名正常 apply ──
    test_old = mod_dir / "test_old.txt"
    test_new = mod_dir / "test_new.txt"
    test_old.write_text("old original content", encoding="utf-8")
    cs_rn14a = ChangeSet(action="rename_file", description="rn14a test")
    cs_rn14a.add_create(test_new, "new updated content")
    cs_rn14a.add_delete(test_old)
    res_14a = cs_rn14a.apply(workspace_root=da_ws)
    check("RN14a: apply succeeds", res_14a.get("status") == "applied", str(res_14a))
    check("RN14a: new file created", test_new.exists() and test_new.read_text(encoding="utf-8") == "new updated content")
    check("RN14a: old file deleted", not test_old.exists())

    # ── RN14b: ChangeSet 文件重命名正常 rollback ──
    rb_14b = cs_rn14a.rollback()
    check("RN14b: rollback succeeds", rb_14b.get("status") == "rolled_back", str(rb_14b))
    check("RN14b: old file restored", test_old.exists() and test_old.read_text(encoding="utf-8") == "old original content")
    check("RN14b: new file deleted", not test_new.exists())
    test_old.unlink(missing_ok=True)

    # ── RN14c: 目标已存在冲突预检硬拦截，旧文件不受影响 ──
    test_old_c = mod_dir / "test_old_c.txt"
    test_new_c = mod_dir / "test_new_c.txt"
    test_old_c.write_text("old content", encoding="utf-8")
    test_new_c.write_text("pre-existing target", encoding="utf-8")
    cs_rn14c = ChangeSet(action="rename_file", description="rn14c collision")
    cs_rn14c.add_create(test_new_c, "new content")
    cs_rn14c.add_delete(test_old_c)
    res_14c = cs_rn14c.apply(workspace_root=da_ws)
    check("RN14c: apply rejected on collision", res_14c.get("status") == "rejected", str(res_14c))
    check("RN14c: old file untouched", test_old_c.exists() and test_old_c.read_text(encoding="utf-8") == "old content")
    check("RN14c: pre-existing target untouched", test_new_c.exists() and test_new_c.read_text(encoding="utf-8") == "pre-existing target")
    test_old_c.unlink(missing_ok=True)
    test_new_c.unlink(missing_ok=True)

    # ── RN14d: 中途失败故障恢复，清除新文件恢复旧文件 ──
    test_old_d = mod_dir / "test_old_d.txt"
    test_new_d = mod_dir / "test_new_d.txt"
    test_old_d.write_text("old original d", encoding="utf-8")
    cs_rn14d = ChangeSet(action="rename_file", description="rn14d failure recovery")
    cs_rn14d.add_create(test_new_d, "new content d")
    cs_rn14d.add_delete(test_old_d)
    cs_rn14d._deleted_backups[str(test_old_d)] = ("old original d", None)
    test_new_d.write_text("new content d", encoding="utf-8")
    test_old_d.unlink()
    cs_rn14d._rollback_operations(
        created_paths=[str(test_new_d)],
        modified_paths=[],
        deleted_paths=[str(test_old_d)],
        patched_paths=[],
    )
    check("RN14d: old file restored via recovery", test_old_d.exists() and test_old_d.read_text(encoding="utf-8") == "old original d")
    check("RN14d: partially created new file removed via recovery", not test_new_d.exists())
    test_old_d.unlink(missing_ok=True)

    # ── RN14e: 多文件批次原子重命名 ──
    f1_old = mod_dir / "f1_old.txt"
    f1_new = mod_dir / "f1_new.txt"
    f2_old = mod_dir / "f2_old.txt"
    f2_new = mod_dir / "f2_new.txt"
    f1_old.write_text("f1 old", encoding="utf-8")
    f2_old.write_text("f2 old", encoding="utf-8")
    cs_rn14e = ChangeSet(action="rename_batch", description="rn14e batch")
    cs_rn14e.add_create(f1_new, "f1 new")
    cs_rn14e.add_delete(f1_old)
    cs_rn14e.add_create(f2_new, "f2 new")
    cs_rn14e.add_delete(f2_old)
    res_14e = cs_rn14e.apply(workspace_root=da_ws)
    check("RN14e: batch apply succeeds", res_14e.get("status") == "applied", str(res_14e))
    check("RN14e: all new files exist", f1_new.exists() and f2_new.exists())
    check("RN14e: all old files deleted", (not f1_old.exists()) and (not f2_old.exists()))
    rb_14e = cs_rn14e.rollback()
    check("RN14e: batch rollback succeeds", rb_14e.get("status") == "rolled_back", str(rb_14e))
    check("RN14e: all old files restored", f1_old.exists() and f2_old.exists())
    check("RN14e: all new files removed", (not f1_new.exists()) and (not f2_new.exists()))
    f1_old.unlink(missing_ok=True)
    f2_old.unlink(missing_ok=True)

    # ── RN15: 资源保护与只读审计 ──
    res_report = p_rn1.get("resource_impact_report", {})
    check("RN15: resource status is preserved", res_report.get("status") == "preserved")
    check("RN15: reason confirms stable HeaderID", "stable" in res_report.get("reason", "").lower())
    aff_res = res_report.get("affected_resources", [])
    check("RN15: affected resources found", len(aff_res) > 0, str(aff_res))
    check("RN15: plan has no resource mutation tasks", "resource_updates" not in p_rn1)

finally:
    shutil.rmtree(da_ws, ignore_errors=True)

print(f"\nProduction regressions: {passed}/{total}")
if failures:
    print("Failures:")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)
print("All production regression tests passed")
sys.exit(0)
