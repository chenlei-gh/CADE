"""
CATIA CAA Workspace Analyzer
============================
Scans the workspace and builds a complete Meta Model with dependency graph.

Design principle:
  AI always calls Analyze first, then uses the snapshot for all decisions.
  Never guess Module names — query the snapshot.

Usage:
  python analyzer.py [workspace_path]
  python analyzer.py D:\\test --json
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional

from meta_model import (
    Command,
    Component,
    Dialog,
    Framework,
    Interface,
    Module,
    Resource,
    Visibility,
    Workbench,
    WorkspaceSnapshot,
)
from utils import Cache, Logger, output_json

# ─── Analyzer ────────────────────────────────────────────────────


class WorkspaceAnalyzer:
    """Scans a CAA workspace and builds the meta model"""

    def __init__(self, workspace_path: Path):
        self.root = workspace_path.resolve()
        self.snapshot = WorkspaceSnapshot(root=self.root)
        self.logger = Logger("analyzer.log")
        self.logger.clear()

    def analyze(self) -> WorkspaceSnapshot:
        """Full analysis: discover all entities and relationships"""
        self.logger.write(f"Analyzing workspace: {self.root}")

        # Phase 1: Discover frameworks
        self._discover_frameworks()

        # Phase 2: Discover modules within each framework
        for fw in self.snapshot.frameworks:
            self._discover_modules(fw)

        # Phase 3: Discover entities within each module
        for fw in self.snapshot.frameworks:
            for mod in fw.modules:
                self._discover_interfaces(mod)
                self._discover_components(mod)
                self._discover_commands(mod)
                self._discover_dialogs(mod)

        # Phase 4: Discover workbenches
        for fw in self.snapshot.frameworks:
            self._discover_workbenches(fw)
            self._discover_resources(fw)

        # Phase 5: Resolve cross-references
        self._resolve_references()

        self.logger.write(
            f"Analysis complete: {len(self.snapshot.frameworks)} fw, "
            f"{sum(len(fw.modules) for fw in self.snapshot.frameworks)} mods, "
            f"{len(self.snapshot.get_all_commands())} cmds"
        )
        return self.snapshot

    # ─── Phase 1: Frameworks ─────────────────────────────────

    def _discover_frameworks(self):
        for item in self.root.iterdir():
            if not item.is_dir():
                continue

            # Pattern: *.edu directories
            if item.suffix == ".edu":
                fw = Framework(name=item.name, path=item)
                self._analyze_framework_details(fw, item)
                self.snapshot.frameworks.append(fw)
                self.logger.write(f"  Framework: {fw.name}")

            # Pattern: directories with IdentityCard
            elif (item / "IdentityCard").exists():
                fw = Framework(name=item.name, path=item)
                self._analyze_framework_details(fw, item)
                self.snapshot.frameworks.append(fw)
                self.logger.write(f"  Framework (by IdentityCard): {fw.name}")

    def _analyze_framework_details(self, fw: Framework, path: Path):
        # IdentityCard
        ic = path / "IdentityCard" / "IdentityCard.h"
        if ic.exists():
            fw.identitycard = ic
            # Parse dependencies from IdentityCard
            try:
                content = ic.read_text(encoding="utf-8", errors="replace")
                for line in content.split("\n"):
                    m = re.search(r'AddPrereqComponent\("([^"]+)"', line)
                    if m:
                        fw.dependencies.append(m.group(1))
            except Exception:
                pass

        # Dictionary
        dico = path / "CNext" / "code" / "dictionary"
        if dico.exists():
            dico_files = list(dico.glob("*.dico"))
            if dico_files:
                fw.dictionary = dico_files[0]

        # CATRsc resource files
        rsc_path = path / "CNext" / "resources" / "resources"
        if rsc_path.exists():
            rsc_files = list(rsc_path.glob("*.CATRsc"))
            fw.rsc_files = rsc_files

        # FunctionTests
        ft = path / "FunctionTests"
        if ft.is_dir():
            fw.function_tests = ft

    # ─── Phase 2: Modules ───────────────────────────────────

    def _discover_modules(self, fw: Framework):
        # Pattern: *.m directories (CAA modules)
        for item in fw.path.iterdir():
            if item.is_dir() and item.suffix == ".m":
                mod = Module(name=item.name, path=item)
                self._analyze_module_details(mod, item)
                fw.add_module(mod)
                self.logger.write(f"    Module: {mod.name}")

    def _analyze_module_details(self, mod: Module, path: Path):
        # Imakefile
        imake = path / "Imakefile.mk"
        if imake.exists():
            mod.imakefile = imake

        # LocalInterfaces
        li = path / "LocalInterfaces"
        if li.exists():
            mod.local_interfaces = list(li.glob("*.h"))

        # PublicInterfaces
        pi = path / "PublicInterfaces"
        if pi.exists():
            mod.public_interfaces = list(pi.glob("*.h"))

        # src directory
        src = path / "src"
        if src.exists():
            mod.src_dir = src

        # Resources
        res = path / "resources"
        if res.exists():
            mod.resources_dir = res

    # ─── Phase 3: Entities ──────────────────────────────────

    def _discover_interfaces(self, mod: Module):
        # Public interfaces
        for h in mod.public_interfaces:
            name = h.stem
            iface = Interface(name=name, path=h, header=h, module=mod)
            # Check if IDL
            idl_file = h.with_suffix(".idl")
            if idl_file.exists():
                iface.is_idl = True
                iface.idl_file = idl_file
            mod.interfaces.append(iface)

        # Local interfaces (check for interface patterns)
        for h in mod.local_interfaces:
            name = h.stem
            try:
                content = h.read_text(encoding="utf-8", errors="replace")
                # Check if it derives from CATBaseUnknown (likely an interface or component)
                if "CATBaseUnknown" in content and "CATDeclareInterface" not in content:
                    continue  # Probably a component header, not an interface
            except Exception:
                pass

    def _discover_components(self, mod: Module):
        if not mod.src_dir:
            return

        # Look for Component headers in LocalInterfaces
        for h in mod.local_interfaces:
            name = h.stem
            try:
                content = h.read_text(encoding="utf-8", errors="replace")
                if "CATDeclareClass" in content:
                    comp = Component(name=name, path=h, header=h, module=mod)

                    # Find matching .cpp
                    cpp = mod.src_dir / f"{name}.cpp"
                    if cpp.exists():
                        comp.source = cpp

                        # Parse implements from cpp
                        cpp_content = cpp.read_text(encoding="utf-8", errors="replace")
                        impls = re.findall(r"CATImplementBOA\((\w+)", cpp_content)
                        for impl_name in impls:
                            # Find interface in module
                            for iface in mod.interfaces:
                                if iface.name == impl_name:
                                    comp.implements.append(iface)
                                    iface.implemented_by.append(comp)

                    mod.components.append(comp)
            except Exception:
                pass

    def _discover_commands(self, mod: Module):
        if not mod.src_dir:
            return

        for cpp in mod.src_dir.glob("*.cpp"):
            try:
                content = cpp.read_text(encoding="utf-8", errors="replace")
                # State command detection
                if "CATStateCommand" in content and "BuildGraph" in content:
                    name = cpp.stem
                    # Don't double-count command headers
                    if "Header" in name or "Hdr" in name:
                        hdr = self._find_matching_header(name, mod)
                        # Find the actual command
                        base = name.replace("Header", "").replace("Hdr", "")
                        cmd_cpp = mod.src_dir / f"{base}.cpp"
                        if cmd_cpp.exists():
                            name = base
                        else:
                            continue  # This is just a header file

                    cmd = Command(name=name, path=cpp, is_stateful=True, module=mod)
                    cmd.source = cpp

                    # Find header
                    cmd.header = self._find_matching_header(name, mod)

                    # Parse details from source
                    self._parse_command_details(cmd, content)

                    mod.add_command(cmd)
                    self.logger.write(f"      StateCommand: {name}")

                elif "CATCommandHeader" in content:
                    name = cpp.stem
                    # Find the command this header belongs to
                    for cmd in mod.commands:
                        if cmd.name in name or name in cmd.name:
                            cmd.header_source = cpp
                            break

            except Exception:
                pass

    def _parse_command_details(self, cmd: Command, content: str):
        """Parse command metadata from source comments"""
        # Try to detect visibility hints
        if "hidden" in content.lower() or "internal" in content.lower():
            cmd.visibility = Visibility.HIDDEN

    def _find_matching_header(self, name: str, mod: Module) -> Optional[Path]:
        """Find the .h file that matches a .cpp name"""
        if mod.local_interfaces:
            for h in mod.local_interfaces:
                if h.stem == name:
                    return h
        if mod.src_dir:
            h_path = mod.src_dir / f"{name}.h"
            if h_path.exists():
                return h_path
        return None

    def _discover_dialogs(self, mod: Module):
        if not mod.src_dir:
            return

        for cpp in mod.src_dir.glob("*.cpp"):
            try:
                content = cpp.read_text(encoding="utf-8", errors="replace")
                if "CATDlg" in content or "CATDialog" in content:
                    name = cpp.stem
                    dlg = Dialog(name=name, path=cpp, module=mod)
                    dlg.header = self._find_matching_header(name, mod)
                    mod.dialogs.append(dlg)
                    self.logger.write(f"      Dialog: {name}")
            except Exception:
                pass

    # ─── Phase 4: Workbenches & Resources ────────────────────

    def _discover_workbenches(self, fw: Framework):
        # Look in modules for workbench files
        for mod in fw.modules:
            if not mod.src_dir:
                continue
            for cpp in mod.src_dir.glob("*.cpp"):
                try:
                    content = cpp.read_text(encoding="utf-8", errors="replace")
                    if "CATIWorkbench" in content or "CreateWorkbench" in content:
                        name = cpp.stem
                        wb = Workbench(name=name, path=cpp, framework=fw)
                        wb.header = self._find_matching_header(name, mod)
                        fw.workbenches.append(wb)
                        self.logger.write(f"    Workbench: {name}")

                        # Find Addin
                        addin_cpp = mod.src_dir / f"{name}Addin.cpp"
                        if addin_cpp.exists():
                            wb.addin_source = addin_cpp
                            wb.addin_header = self._find_matching_header(
                                f"{name}Addin", mod
                            )
                except Exception:
                    pass

    def _discover_resources(self, fw: Framework):
        # Catalog
        for pat in ["*.CATCatalog", "*.catalog"]:
            for f in fw.path.glob(pat):
                res = Resource(
                    name=f.stem, path=f, resource_type="catalog", framework=fw
                )
                fw.catalog = f
                self.logger.write(f"    Catalog: {f.name}")
                break

        # NLS files
        for f in fw.path.rglob("*.CATNls"):
            lang = (
                "zh"
                if "chinese" in f.stem.lower() or f.stem.endswith("_Chinese")
                else "en"
            )
            res = Resource(
                name=f.stem, path=f, resource_type="nls", framework=fw, language=lang
            )
            fw.nls_files.append(f)

        # Icon resources
        for f in fw.path.rglob("*.bmp"):
            fw.icon_resources.append(f)
        for f in fw.path.rglob("*.ico"):
            fw.icon_resources.append(f)

        # Rsc files
        for f in fw.path.rglob("*.CATRsc"):
            fw.rsc_files.append(f)

    # ─── Phase 5: Cross-references ───────────────────────────

    def _resolve_references(self):
        """Resolve Command↔Dialog, Command↔Workbench relationships"""
        for fw in self.snapshot.frameworks:
            for mod in fw.modules:
                # Link commands to dialogs (same module, naming convention)
                for cmd in mod.commands:
                    for dlg in mod.dialogs:
                        if (
                            cmd.name.lower() in dlg.name.lower()
                            or dlg.name.lower() in cmd.name.lower()
                        ):
                            cmd.dialog = dlg
                            dlg.parent_command = cmd

                # Link commands to workbenches (via addin files)
                for wb in fw.workbenches:
                    if wb.addin_source and wb.addin_source.exists():
                        try:
                            addin_content = wb.addin_source.read_text(
                                encoding="utf-8", errors="replace"
                            )
                            for cmd in mod.commands:
                                if cmd.name in addin_content:
                                    wb.add_command(cmd)
                        except Exception:
                            pass


# ─── CLI ─────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Analyze CAA workspace")
    parser.add_argument("workspace", nargs="?", default=".", help="Workspace path")
    parser.add_argument("--json", action="store_true", help="Output full JSON")
    parser.add_argument("--summary", action="store_true", help="Output summary only")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    if not workspace.exists():
        output_json(
            {"status": "error", "message": f"Path not found: {workspace}"}, exit_code=1
        )
        return

    analyzer = WorkspaceAnalyzer(workspace)
    snapshot = analyzer.analyze()

    if args.summary:
        output_json({"status": "ok", "summary": snapshot.to_dict()})
    elif args.json:
        print(snapshot.to_json())
    else:
        output_json({"status": "ok", "summary": snapshot.to_dict()})


if __name__ == "__main__":
    main()
