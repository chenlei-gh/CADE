#!/usr/bin/env python3
"""
Test Brownfield Module Analysis (P1 Verification)
=================================================
Validates that Kernel can target existing CAA modules in:
1. ANALYZE mode: produces rich, read-only aggregated analysis (files, build config,
   entities, diagnostics split into module vs workspace, and related knowledge).
2. DEVELOP mode: recognizes "maintain" requests, returns task_type="maintain_existing_module"
   and guidance, without destructive generation.
"""

import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent / "skills"
sys.path.insert(0, str(SKILL_ROOT))

from kernel import Kernel, KernelMode


class TestBrownfieldAnalysis(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp_dir.name)

        # Create a mock CAA structure: TestFw.edu/TestMod.m
        fw_dir = self.ws / "TestFw.edu"
        fw_dir.mkdir()
        mod_dir = fw_dir / "TestMod.m"
        mod_dir.mkdir()
        src_dir = mod_dir / "src"
        src_dir.mkdir()
        local_int = mod_dir / "LocalInterfaces"
        local_int.mkdir()

        # Files (Valid CAA baseline)
        cmd_h = (
            "#ifndef TestCmd_H\n"
            "#define TestCmd_H\n"
            "#include \"CATCommand.h\"\n"
            "class TestCmd : public CATCommand {\n"
            "    CATDeclareClass;\n"
            "public:\n"
            "    TestCmd();\n"
            "    virtual ~TestCmd();\n"
            "    void BuildGraph();\n"
            "};\n"
            "#endif\n"
        )
        cmd_cpp = (
            "#include \"TestCmd.h\"\n"
            "CATCreateClass(TestCmd);\n"
            "TestCmd::TestCmd() : CATCommand(NULL, \"TestCmd\") {}\n"
            "TestCmd::~TestCmd() {}\n"
            "void TestCmd::BuildGraph() {}\n"
        )
        (src_dir / "TestCmd.cpp").write_text(cmd_cpp, encoding="utf-8")
        (local_int / "TestCmd.h").write_text(cmd_h, encoding="utf-8")
        imakefile_content = (
            "BUILT_OBJECT_TYPE = SHARED LIBRARY\n"
            "LINK_WITH = CATApplicationFrame JS0GROUP \\\n"
            "            CATMathematics\n"
            "SYS_LIBS = USER32.lib GDI32.lib\n"
        )
        (mod_dir / "Imakefile.mk").write_text(imakefile_content, encoding="utf-8")

        self.kernel = Kernel(workspace_root=str(self.ws))

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_analyze_module_by_explicit_dot_m(self):
        """ANALYZE mode correctly resolves TestMod.m and aggregates files & build config"""
        res = self.kernel.execute(KernelMode.ANALYZE, "analyze TestMod.m")
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("target_module"), "TestMod.m")
        self.assertEqual(res.get("framework"), "TestFw.edu")

        # Files inspection
        files = res.get("files", {})
        self.assertTrue(any("TestCmd.cpp" in f for f in files.get("src", [])))
        self.assertTrue(any("TestCmd.h" in f for f in files.get("local_interfaces", [])))
        self.assertIsNotNone(files.get("imakefile"))

        # Build config inspection
        build_config = res.get("build_config", {})
        self.assertEqual(build_config.get("built_object_type"), "SHARED LIBRARY")
        self.assertIn("CATApplicationFrame", build_config.get("link_with", []))
        self.assertIn("CATMathematics", build_config.get("link_with", []))
        self.assertIn("USER32.lib", build_config.get("sys_libs", []))

        # Diagnostics categorization
        diagnostics = res.get("diagnostics", {})
        self.assertIn("module_specific", diagnostics)
        self.assertIn("workspace_scope", diagnostics)

    def test_analyze_module_by_keyword(self):
        """ANALYZE mode resolves 'inspect module TestMod'"""
        res = self.kernel.execute(KernelMode.ANALYZE, "inspect module TestMod")
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("target_module"), "TestMod.m")

    def test_develop_mode_brownfield_routing(self):
        """DEVELOP mode routes maintain request to brownfield maintenance without generation"""
        res = self.kernel.execute(KernelMode.DEVELOP, "maintain TestMod.m")
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("task_type"), "maintain_existing_module")
        self.assertEqual(res.get("target_module"), "TestMod.m")

        # Guidance present
        guidance = res.get("guidance", [])
        self.assertGreaterEqual(len(guidance), 1)

        # Analysis data attached
        analysis = res.get("analysis", {})
        self.assertEqual(analysis.get("target_module"), "TestMod.m")

    def test_chinese_maintenance_request_develop_mode(self):
        """DEVELOP mode routes Chinese maintenance requests, extracts clean problem description, and prevents generator execution"""
        # Add a dialog file to match the problem description
        dlg_cpp = (
            "#include \"TestDialog.h\"\n"
            "void TestDialog::BuildWindow() {\n"
            "    AddCallback(this, GetWindCloseNotification(), NULL);\n"
            "}\n"
        )
        (self.ws / "TestFw.edu" / "TestMod.m" / "src" / "TestDialog.cpp").write_text(dlg_cpp, encoding="utf-8")

        res = self.kernel.execute(KernelMode.DEVELOP, "排查 TestMod.m 对话框关闭崩溃问题")
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("task_type"), "maintain_existing_module")
        self.assertEqual(res.get("target_module"), "TestMod.m")
        self.assertIn("对话框关闭崩溃", res.get("problem_description", ""))

        guidance = res.get("guidance", [])
        self.assertTrue(any("TestMod.m" in g for g in guidance))

        # Check that verification and relevant_locations are present
        self.assertIn("verification", res)
        self.assertIn("relevant_locations", res)
        locations = res.get("relevant_locations", [])
        self.assertGreater(len(locations), 0)

    def test_symbol_and_location_positioning(self):
        """Kernel locates relevant symbols, callbacks and line numbers for the problem description"""
        # Add rich dialog code with lifecycle & callbacks
        dlg_src = (
            "#include \"TestDialog.h\"\n\n"
            "class TestDialog : public CATDlgDialog {\n"
            "public:\n"
            "    void BuildWindow() {\n"
            "        AddCallback(this, GetWindCloseNotification(), (CATSubscriberMethod)&TestDialog::OnClose);\n"
            "    }\n"
            "    void OnClose() {\n"
            "        SetVisibility(CATDlgHide);\n"
            "    }\n"
            "};\n"
        )
        src_file = self.ws / "TestFw.edu" / "TestMod.m" / "src" / "TestDialog.cpp"
        src_file.write_text(dlg_src, encoding="utf-8")

        res = self.kernel.execute(KernelMode.ANALYZE, "analyze TestMod.m: 对话框关闭 close callback")
        self.assertEqual(res.get("status"), "ok")

        locations = res.get("relevant_locations", [])
        self.assertGreater(len(locations), 0)
        # Should have found TestDialog.cpp with callback or BuildWindow
        has_cb = any("GetWindCloseNotification" in loc.get("snippet", "") or "BuildWindow" in loc.get("snippet", "") for loc in locations)
        self.assertTrue(has_cb, f"Expected callback or BuildWindow in locations: {locations}")

    def test_targeted_single_module_verification(self):
        """Kernel runs CodeVerifier and UILinter on target module in verify mode"""
        res = self.kernel.execute(KernelMode.ANALYZE, "verify module TestMod.m")
        self.assertEqual(res.get("status"), "ok")

        v = res.get("verification", {})
        self.assertIn("summary", v)
        self.assertGreaterEqual(v["summary"]["files_checked"], 2)
        self.assertEqual(v["summary"]["code_errors"], 0)
        self.assertEqual(v["status"], "clean")

    def test_ui_lint_detection_in_brownfield(self):
        """Kernel flags CAA UI failure patterns in single module verification"""
        # Inject NULL parent dialog failure pattern
        bad_code = (
            "#include \"CATDlgDialog.h\"\n"
            "void BadCreate() {\n"
            "    CATDlgDialog* p = new TestDlg(NULL);\n"
            "}\n"
        )
        (self.ws / "TestFw.edu" / "TestMod.m" / "src" / "TestBad.cpp").write_text(bad_code, encoding="utf-8")

        res = self.kernel.execute(KernelMode.ANALYZE, "verify module TestMod.m")
        v = res.get("verification", {})
        self.assertEqual(v.get("status"), "has_issues")
        ui_findings = v.get("ui_findings", [])
        self.assertGreaterEqual(len(ui_findings), 1)
        finding = ui_findings[0]
        self.assertEqual(finding.get("rule"), "ui_dialog_null_parent")
        self.assertIn("TestBad.cpp", finding.get("file", ""))

    def test_entity_to_module_resolution(self):
        """Kernel resolves target module when request references an internal source entity"""
        (self.ws / "TestFw.edu" / "TestMod.m" / "src" / "CAABOMPanelDlg.cpp").write_text("// Panel dialog\n", encoding="utf-8")
        res = self.kernel.execute(KernelMode.DEVELOP, "排查 CAABOMPanelDlg 崩溃问题")
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("target_module"), "TestMod.m")
        self.assertEqual(res.get("task_type"), "maintain_existing_module")

    def test_greenfield_creation_not_hijacked(self):
        """Greenfield component creation in existing module is NOT hijacked into read-only maintenance"""
        res = self.kernel.execute(KernelMode.DEVELOP, "create command NewCmd in TestMod.m")
        # Should not be maintain_existing_module task_type
        self.assertNotEqual(res.get("task_type"), "maintain_existing_module")


if __name__ == "__main__":
    unittest.main()
