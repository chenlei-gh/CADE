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

        # Files
        (src_dir / "TestCmd.cpp").write_text("// TestCmd implementation\n", encoding="utf-8")
        (local_int / "TestCmd.h").write_text("// TestCmd header\n", encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
