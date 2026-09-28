"""
P3a Unit & Integration Tests: Incorporating _apply_extras into ChangeSet
======================================================================
Verifies:
  1. _apply_extras strictly requires a ChangeSet and never writes to disk.
  2. develop(preview=True) generates a complete ChangeSet containing extras
     (Imakefile dependencies and cpp references) with ZERO disk writes.
  3. Preconditions correctly cover all touched files (P2 integration).
  4. Applying the authorization ChangeSet (P1 flow) atomically writes both
     base components and extras to disk.
  5. develop(preview=False) applies atomically with extras via ChangeSet.apply.
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

# Setup import path
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
sys.path.insert(0, str(SKILLS_DIR))

from kernel import Kernel, KernelMode
from changeset import ChangeSet
from actions import ActionContext, create_module


class TestP3aExtrasChangeSet(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cade_p3a_test_")
        self.workspace = Path(self.test_dir)
        self.kernel = Kernel(workspace_root=str(self.workspace))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_apply_extras_requires_changeset(self):
        """_apply_extras must raise TypeError if cs is omitted or not a ChangeSet."""
        plan = {"intent": {"name": "CmdA", "module": "ModA.m", "framework": "FwA"}}
        extras = {"imakefile_deps": ["CATDialogEngine"]}

        # Calling without cs must fail closed
        with self.assertRaises(TypeError):
            self.kernel._apply_extras(plan, extras, cs=None)

        with self.assertRaises(TypeError):
            self.kernel._apply_extras(plan, extras, cs="not_a_changeset")

    def test_apply_extras_pure_in_memory(self):
        """_apply_extras mutates cs in memory and never touches the disk."""
        # Create an existing module on disk
        mod_dir = self.workspace / "MyFW" / "MyMod.m"
        mod_dir.mkdir(parents=True)
        imakefile = mod_dir / "Imakefile.mk"
        imakefile.write_text("LINK_WITH = CATDialogEngine\n", encoding="utf-8")
        src_dir = mod_dir / "src"
        src_dir.mkdir(parents=True)
        cpp_file = src_dir / "MyCmd.cpp"
        cpp_file.write_text("#include \"MyCmd.h\"\n\nvoid run() {}\n", encoding="utf-8")

        initial_imakefile_mtime = imakefile.stat().st_mtime_ns
        initial_cpp_mtime = cpp_file.stat().st_mtime_ns

        cs = ChangeSet(action="test_action", description="test pure memory")
        plan = {"intent": {"name": "MyCmd", "module": "MyMod.m", "framework": "MyFW"}}
        extras = {
            "imakefile_deps": ["CATAssemblyInterfaces"],
            "playbooks": ["pb.export_bom"],
            "capabilities": ["cap.assembly_tree"],
        }

        applied = self.kernel._apply_extras(plan, extras, cs=cs)

        self.assertIn("CATAssemblyInterfaces", applied["deps_added"])
        self.assertGreater(len(applied["refs_added"]), 0)

        # Verify disk files were NOT touched at all
        self.assertEqual(imakefile.stat().st_mtime_ns, initial_imakefile_mtime)
        self.assertEqual(cpp_file.stat().st_mtime_ns, initial_cpp_mtime)
        self.assertNotIn("CATAssemblyInterfaces", imakefile.read_text(encoding="utf-8"))
        self.assertNotIn("pb.export_bom", cpp_file.read_text(encoding="utf-8"))

        # Verify cs.modified contains the enriched contents
        imakefile_str = str(imakefile)
        self.assertIn(imakefile_str, cs.modified)
        self.assertIn("CATAssemblyInterfaces", cs.modified[imakefile_str])

        cpp_str = str(cpp_file)
        self.assertIn(cpp_str, cs.modified)
        self.assertIn("pb.export_bom", cs.modified[cpp_str])

    def _setup_framework_and_module(self, framework: str = "TestFW", module: str = "TestMod.m"):
        """Helper to create a valid CAA framework and module on disk."""
        ctx = ActionContext(str(self.workspace))
        from actions import create_framework
        r1 = create_framework(ctx, framework)
        ChangeSet.from_dict(r1["changeset"]).apply(workspace_root=self.workspace)
        ctx = ActionContext(str(self.workspace))
        r2 = create_module(ctx, framework_name=framework, module_name=module)
        ChangeSet.from_dict(r2["changeset"]).apply(workspace_root=self.workspace)
        imakefile = self.workspace / f"{framework}.edu" / module / "Imakefile.mk"
        return imakefile

    def test_preview_develop_contains_extras_without_disk_write(self):
        """develop(preview=True) with extras produces complete ChangeSet with 0 disk writes."""
        imakefile = self._setup_framework_and_module("TestFW", "TestMod.m")
        imakefile.write_text("LINK_WITH = CATDialogEngine\n", encoding="utf-8")

        plan = {
            "intent": {
                "type": "CreateCommand",
                "name": "ExportCSV",
                "module": "TestMod.m",
                "framework": "TestFW",
            }
        }
        extras = {
            "imakefile_deps": ["CATAssemblyInterfaces", "AutomationInterfaces"],
            "playbooks": ["pb.export_bom"],
            "capabilities": ["cap.document_export"],
        }

        # Execute plan in preview mode
        result = self.kernel._execute_develop_plan(plan, preview=True, extras=extras)

        self.assertEqual(result["status"], "pending")
        self.assertIn("changeset", result)
        cs_dict = result["changeset"]

        # Verify extras are present inside the ChangeSet
        imakefile_key = str(imakefile)
        self.assertIn(imakefile_key, cs_dict["modified"])
        self.assertIn("CATAssemblyInterfaces", cs_dict["modified"][imakefile_key])

        # Find the created or modified cpp file in changeset
        cpp_entries = [
            content for path, content in cs_dict.get("created", {}).items()
            if "ExportCSV.cpp" in path
        ]
        self.assertTrue(len(cpp_entries) > 0, "ExportCSV.cpp must be in created files")
        self.assertIn("pb.export_bom", cpp_entries[0])

        # Preconditions must cover the touched files
        self.assertIn("preconditions", cs_dict)
        self.assertGreater(len(cs_dict["preconditions"]), 0)

        # VERIFY ZERO DISK WRITES: ExportCSV.cpp must not exist on disk yet
        disk_cpp = self.workspace / "TestFW.edu" / "TestMod.m" / "src" / "ExportCSV.cpp"
        self.assertFalse(disk_cpp.exists(), "Preview mode must not write .cpp file to disk")

        # Imakefile on disk must remain unchanged
        self.assertNotIn("CATAssemblyInterfaces", imakefile.read_text(encoding="utf-8"))

        # NOW APPLY the authorized ChangeSet (P1 flow)
        apply_res = self.kernel._apply_changeset_dict(cs_dict)
        self.assertEqual(apply_res["status"], "applied")

        # Now files MUST exist on disk with extras intact
        self.assertTrue(disk_cpp.exists())
        self.assertIn("pb.export_bom", disk_cpp.read_text(encoding="utf-8"))
        self.assertIn("CATAssemblyInterfaces", imakefile.read_text(encoding="utf-8"))

    def test_non_preview_develop_applies_extras_via_changeset(self):
        """develop(preview=False) incorporates extras directly into applied ChangeSet."""
        imakefile = self._setup_framework_and_module("MyFW", "MyMod.m")
        imakefile.write_text("LINK_WITH = CATDialogEngine\n", encoding="utf-8")

        plan = {
            "intent": {
                "type": "CreateCommand",
                "name": "AutoCmd",
                "module": "MyMod.m",
                "framework": "MyFW",
            }
        }
        extras = {
            "imakefile_deps": ["CATAssemblyInterfaces"],
            "playbooks": ["pb.assembly_stats"],
        }

        result = self.kernel._execute_develop_plan(plan, preview=False, extras=extras)

        self.assertEqual(result["status"], "ok")
        self.assertIn("extras_applied", result)
        self.assertIn("CATAssemblyInterfaces", result["extras_applied"]["deps_added"])

        # Check on disk
        cpp_file = self.workspace / "MyFW.edu" / "MyMod.m" / "src" / "AutoCmd.cpp"
        self.assertTrue(cpp_file.exists())
        self.assertIn("pb.assembly_stats", cpp_file.read_text(encoding="utf-8"))
        self.assertIn("CATAssemblyInterfaces", imakefile.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
