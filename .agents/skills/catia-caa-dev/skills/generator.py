"""
CATIA CAA Generator
====================
Template-based code generation for CAA components.

The Generator is the backend — it receives a Spec and produces code.
It never knows about AI or user intent.

Usage: python generator.py [type] [name] [options]
Output: JSON with generation result

Supported types (17 validated B28 templates):
  Fundamental:
    interface        IInterface.h/cpp
    component        Component.h/cpp (requires --interface)
    identitycard     IdentityCard.h
    imakefile        Imakefile.mk
    dictionary       Framework.edu.dico

  Project Structure:
    framework        Framework (IdentityCard + dico + Imakefile)
    module           Module (Imakefile + ModuleInfo)

  Command System:
    command          State Command (7 files)
    commandheader    Command Header (menu binding)

  Workbench System:
    workbench        CATWorkbench
    addin            Workbench Addin (inject commands)
    workshopaddin    Workshop Addin (extend workshop)

  UI System:
    dialog           Dialog

  Component/Interface:
    idl              IDL Interface (.h + .cpp + .idl)

  Feature:
    feature          Feature Component (5+ files)

  Utility:
    class            Plain C++ class

  Testing:
    testcase         CATTestCase
    xmltestcase      XmlTestCase

  Code Generation:
    codegen          Code Generation Wizard

  Extension:
    eventlistener    CATIA Event Listener

  Resource:
    resource         Catalog + NLS + Icon + CATRsc (5 files)
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from utils import Cache, Logger, output_json, render_template


class TemplateGenerator:
    """CAA Template Generator — 17 validated B28 templates"""

    # Template prefix mapping: template directory name → filename prefix in templates
    _TPL_PREFIX = {
        "command": "CommandClass",
        "commandheader": "CommandHeader",
        "eventlistener": "EventListener",
        "workshopaddin": "WorkshopAddin",
        "addin": "WorkbenchAddin",
        "workbench": "Workbench",
        "testcase": "TestCase",
        "xmltestcase": "XmlTestCase",
        "class": "Class",
        "codegen": "CodeGenWizard",
    }

    def __init__(self):
        self.skill_root = Path(__file__).parent.parent
        self.templates_dir = self.skill_root / "templates"
        self.logger = Logger("generate.log")
        self.cache = Cache("generate.json")
        self.logger.clear()

    # ─── Public API ───────────────────────────────────────────────

    def get_available_templates(self) -> List[str]:
        """All available template types"""
        subdirs = sorted(
            d.name
            for d in self.templates_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
        )
        root_types = [
            "interface",
            "component",
            "identitycard",
            "imakefile",
            "dictionary",
        ]
        return sorted(set(root_types + subdirs))

    def generate(
        self,
        template_type: str,
        name: str,
        output_dir: Path,
        *,
        interface: Optional[str] = None,
        framework: str = "MyFramework",
        module: str = "MyModule",
        **kwargs,
    ) -> Dict:
        """Route to the correct generator based on type"""

        output_dir.mkdir(parents=True, exist_ok=True)
        if not self._validate_name(name):
            return self._error(f"Invalid name: {name}")

        type_handlers = {
            "interface": self._gen_interface,
            "component": self._gen_component,
            "identitycard": self._gen_identitycard,
            "imakefile": self._gen_imakefile,
            "dictionary": self._gen_dictionary,
        }

        if template_type in type_handlers:
            return type_handlers[template_type](
                name, output_dir, interface, framework, module, **kwargs
            )

        # All subdirectory-based templates
        return self._gen_from_dir(
            template_type, name, output_dir, interface, framework, module, **kwargs
        )

    # ─── Root-file generators ────────────────────────────────────

    def _gen_interface(self, name, out, _, fw, mod, **kw):
        return self._gen_root_files(
            "IInterface",
            name,
            out,
            fw,
            mod,
            extra_repl={"IInterfaceName": name, "IINTERFACENAME": name.upper()},
        )

    def _gen_component(self, name, out, iface, fw, mod, **kw):
        if not iface:
            return self._error("--interface is required for component")
        return self._gen_root_files(
            "Component",
            name,
            out,
            fw,
            mod,
            extra_repl={
                "ComponentName": name,
                "COMPONENTNAME": name.upper(),
                "IInterfaceName": iface,
            },
        )

    def _gen_identitycard(self, name, out, _, fw, mod, **kw):
        return self._gen_root_files("IdentityCard", name, out, fw, mod)

    def _gen_imakefile(self, name, out, _, fw, mod, **kw):
        return self._gen_root_files("Imakefile", name, out, fw, mod)

    def _gen_dictionary(self, name, out, _, fw, mod, **kw):
        src = self.templates_dir / "Framework.edu.dico"
        if not src.exists():
            return self._error("Template Framework.edu.dico not found")
        dst = out / f"{fw}.dico"
        content = src.read_text(encoding="utf-8", errors="replace")
        content = self._replace(content, name, fw, mod)
        dst.write_text(content, encoding="utf-8")
        self.logger.write(f"Generated: {dst}")
        return self._success([str(dst)], "dictionary", name)

    # ─── Directory-based generator ────────────────────────────────

    def _gen_from_dir(self, ttype, name, out, iface, fw, mod, **kw):
        src_dir = self.templates_dir / ttype
        if not src_dir.exists():
            return self._error(f"Template directory not found: {src_dir}")

        generated = []
        extra = kw.get("extra_repl", {})

        # Map template directory name to the prefix used in template filenames
        tpl_prefix = self._TPL_PREFIX.get(ttype, ttype.capitalize())

        for tf in sorted(src_dir.rglob("*")):
            if tf.is_file() and not tf.name.startswith("."):
                rel = tf.relative_to(src_dir)
                # Replace template prefix in filename with user-provided name
                rel_str = str(rel).replace(tpl_prefix, name)
                rel_str = rel_str.replace("FrameworkName", fw)
                out_file = out / rel_str
                out_file.parent.mkdir(parents=True, exist_ok=True)

                content = tf.read_text(encoding="utf-8", errors="replace")
                # Merge extra replacements + interface override into unified render
                extra_kwargs = dict(extra)
                if iface:
                    extra_kwargs["IInterfaceName"] = iface
                content = self._replace(content, name, fw, mod, **extra_kwargs)

                out_file.write_text(content, encoding="utf-8")
                generated.append(str(out_file))
                self.logger.write(f"Generated: {out_file}")

        return self._success(generated, ttype, name)

    def _gen_root_files(self, prefix, name, out, fw, mod, *, extra_repl=None):
        """Generate from root-level template files matching prefix (e.g. Component.h/.cpp)"""
        generated = []
        patterns = [f"{prefix}.h", f"{prefix}.cpp", f"{prefix}.h", f"{prefix}.mk"]
        found = False

        for pat in patterns:
            src = self.templates_dir / pat
            if src.exists():
                found = True
                ext = src.suffix
                out_file = out / f"{name}{ext}"
                content = src.read_text(encoding="utf-8", errors="replace")
                content = self._replace(content, name, fw, mod, **(extra_repl or {}))
                out_file.write_text(content, encoding="utf-8")
                generated.append(str(out_file))
                self.logger.write(f"Generated: {out_file}")

        if not found:
            return self._error(f"No templates found for prefix: {prefix}")

        return self._success(generated, prefix.lower(), name)

    # ─── Helpers ──────────────────────────────────────────────────

    def _replace(self, content: str, name: str, fw: str, mod: str, **extra) -> str:
        """Render template content by replacing all placeholders.
        
        Builds a comprehensive replacements dict from name/framework/module,
        merges in any extra kwargs (which take priority), then delegates to
        the unified render_template() in utils.py.
        """
        year = str(datetime.now().year)
        fw_base = fw.replace(".edu", "")
        mod_base = mod.replace(".m", "")
        reps = {
            "YYYY": year,
            "PREFIX": name,
            "ClassName": name,
            "ComponentName": name,
            "COMPONENTNAME": name.upper(),
            "IInterfaceName": name,
            "IIDLInterfaceName": name,
            "TestCaseName": name,
            "XmlTestCaseName": name,
            "AddinName": name,
            "EventListenerName": name,
            "WorkshopAddinName": name,
            "CommandClassName": name,
            "CommandHeaderName": name,
            "DialogClass": name,
            "DialogClassName": name,
            "WorkbenchClass": name,
            "WorkbenchAddin": name,
            "FeatureClass": name,
            "FrameworkName": fw_base,
            "FrameworkBareName": fw_base,
            "FRAMEWORKNAME": fw_base.upper(),
            "ModuleName": mod_base,
            "MODULENAME": mod_base.upper(),
        }
        # Merge extra kwargs — they override base dict entries
        reps.update(extra)
        return render_template(content, reps)

    def _render(
        self, template_ref: str, name: str,
        fw: str = "MyFramework", mod: str = "MyModule", **kwargs
    ) -> str:
        """Find a template by name, read it, and render with replacements.

        Supports:
          - Root template files: "Component.h", "Component.cpp", etc.
          - Directory-based templates: "command", "dialog", "feature", etc.
          - Special aliases: "interface" → IInterface.h, "component" → Component.cpp

        Args:
            template_ref: Template file name or directory type
            name: The user-provided name for replacements
            fw: Framework name
            mod: Module name
            **kwargs: Extra replacements (e.g., CommandClassName="MyCmd")

        Returns:
            Rendered template content as a string

        Raises:
            FileNotFoundError: If no matching template found
        """
        # 1. Try as exact root template file
        src = self.templates_dir / template_ref
        if src.is_file():
            content = src.read_text(encoding="utf-8", errors="replace")
            return self._replace(content, name, fw, mod, **kwargs)

        # 2. Try as directory — find the primary source file
        src_dir = self.templates_dir / template_ref
        if src_dir.is_dir():
            tpl_prefix = self._TPL_PREFIX.get(template_ref, template_ref.capitalize())
            # Determine preferred extension: "header" → .h, else → .cpp
            prefer_h = "header" in template_ref.lower()
            pref_suffix = ".h" if prefer_h else ".cpp"
            alt_suffix = ".cpp" if prefer_h else ".h"
            # Score: preferred suffix with matching prefix > alt suffix with matching prefix > any .cpp > any .h > anything
            candidates = sorted(
                [
                    f
                    for f in src_dir.rglob("*")
                    if f.is_file() and not f.name.startswith(".")
                ],
                key=lambda f: (
                    0 if f.suffix == pref_suffix and tpl_prefix in f.stem else
                    1 if f.suffix == alt_suffix and tpl_prefix in f.stem else
                    2 if f.suffix == pref_suffix else
                    3 if f.suffix == alt_suffix else 4,
                    f.name,
                ),
            )
            if candidates:
                content = candidates[0].read_text(encoding="utf-8", errors="replace")
                return self._replace(content, name, fw, mod, **kwargs)

        # 3. Special aliases for root-level single-file templates
        _ALIASES = {"interface": "IInterface.h", "component": "Component.cpp"}
        if template_ref in _ALIASES:
            src = self.templates_dir / _ALIASES[template_ref]
            if src.is_file():
                content = src.read_text(encoding="utf-8", errors="replace")
                return self._replace(content, name, fw, mod, **kwargs)

        raise FileNotFoundError(f"Template not found: {template_ref}")

    def _validate_name(self, name: str) -> bool:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            self.logger.write(f"Invalid name: {name}", "ERROR")
            return False
        return True

    # ─── Spec-based Generation ───────────────────────────────────

    def generate_from_spec(self, spec, output_dir: Path) -> Dict:
        """Generate code from a Specification object.
        This is the canonical Generator entry point — Spec is the contract.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        spec_type = spec.__class__.__name__

        if spec_type == "CommandSpec":
            return self._gen_command_spec(spec, output_dir)
        elif spec_type == "DialogSpec":
            return self._gen_dialog_spec(spec, output_dir)
        elif spec_type == "InterfaceSpec":
            return self._gen_interface_spec(spec, output_dir)
        elif spec_type == "ComponentSpec":
            return self._gen_component_spec(spec, output_dir)
        elif spec_type == "FeatureSpec":
            return self._gen_feature_spec(spec, output_dir)
        elif spec_type == "ExtensionSpec":
            return self._gen_extension_spec(spec, output_dir)
        elif spec_type == "WorkbenchSpec":
            return self._gen_workbench_spec(spec, output_dir)
        else:
            # Fallback to string-based generation
            return self.generate(
                spec_type.lower().replace("spec", ""), spec.name, output_dir
            )

    def _gen_command_spec(self, spec, out: Path) -> Dict:
        """Generate from CommandSpec"""
        files = []
        name = spec.name

        # Command header
        hdr = out / f"{name}.h"
        hdr.write_text(
            self._render("commandheader", name, CommandClassName=name), encoding="utf-8"
        )
        files.append(str(hdr))

        # Command source
        src = out / f"{name}.cpp"
        src.write_text(
            self._render("command", name, CommandClassName=name), encoding="utf-8"
        )
        files.append(str(src))

        # Dialog
        if spec.dialog:
            dlg = out / f"{spec.dialog.name}.cpp"
            dlg.write_text(
                self._render(
                    "dialog", spec.dialog.name, DialogClassName=spec.dialog.name
                ),
                encoding="utf-8",
            )
            files.append(str(dlg))

        return self._success(files, "command", name)

    def _gen_dialog_spec(self, spec, out: Path) -> Dict:
        files = []
        name = spec.name
        src = out / f"{name}.cpp"
        src.write_text(
            self._render("dialog", name, DialogClassName=name), encoding="utf-8"
        )
        files.append(str(src))
        return self._success(files, "dialog", name)

    def _gen_interface_spec(self, spec, out: Path) -> Dict:
        files = []
        name = spec.name
        hdr = out / f"{name}.h"
        hdr.write_text(
            self._render("interface", name, InterfaceClassName=name), encoding="utf-8"
        )
        files.append(str(hdr))
        return self._success(files, "interface", name)

    def _gen_component_spec(self, spec, out: Path) -> Dict:
        files = []
        name = spec.name
        src = out / f"{name}.cpp"
        src.write_text(
            self._render("component", name, ComponentClassName=name), encoding="utf-8"
        )
        files.append(str(src))
        return self._success(files, "component", name)

    def _gen_feature_spec(self, spec, out: Path) -> Dict:
        files = []
        name = spec.name
        src = out / f"{name}.cpp"
        src.write_text(
            self._render("feature", name, FeatureClass=name), encoding="utf-8"
        )
        files.append(str(src))
        if spec.with_factory:
            factory_name = f"{name}Factory"
            fac = out / f"{factory_name}.cpp"
            fac.write_text(
                self._render(
                    "feature",
                    factory_name,
                    FeatureClass=name,
                    FactoryClass=factory_name,
                ),
                encoding="utf-8",
            )
            files.append(str(fac))
        return self._success(files, "feature", name)

    def _gen_extension_spec(self, spec, out: Path) -> Dict:
        files = []
        name = spec.name
        # Use component templates for extensions (adapter template removed in v3.0.3)
        for ext in ['.h', '.cpp']:
            tpl_name = f"Component{ext}"
            dst = out / f"{name}{ext}"
            dst.write_text(
                self._render(tpl_name, name, ExtensionClass=name, TargetObject=spec.target_object),
                encoding="utf-8",
            )
            files.append(str(dst))
        return self._success(files, "extension", name)

    def _gen_workbench_spec(self, spec, out: Path) -> Dict:
        files = []
        name = spec.name
        src = out / f"{name}Addin.cpp"
        src.write_text(
            self._render("workbench", name, WorkbenchClass=name), encoding="utf-8"
        )
        files.append(str(src))
        return self._success(files, "workbench", name)

    def _success(self, files: List[str], ttype: str, name: str) -> Dict:
        return {
            "status": "success",
            "message": f"{ttype} '{name}' generated ({len(files)} files)",
            "generated_files": files,
            "count": len(files),
            "type": ttype,
            "name": name,
        }

    def _error(self, msg: str) -> Dict:
        self.logger.write(msg, "ERROR")
        return {"status": "error", "message": msg, "generated_files": []}


# ─── CLI ─────────────────────────────────────────────────────────


def main():
    gen = TemplateGenerator()
    available = gen.get_available_templates()

    parser = argparse.ArgumentParser(
        description="Generate CATIA CAA components from 17 template types",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Template types: {", ".join(available)}

Examples:
  python generate.py interface    ICalculator -o PublicInterfaces/
  python generate.py component    Calculator  --interface ICalculator -o src/
  python generate.py framework    MyFramework.edu -o D:\\\\workspace
  python generate.py module       MyModule    -o MyFramework.edu/
  python generate.py command      CalcCmd     -o MyModule.m/src/
  python generate.py commandheader CalcCmdHdr -o MyModule.m/src/
  python generate.py workbench    MyWb        -o MyModule.m/src/
  python generate.py addin        MyAddin     -o MyModule.m/src/
  python generate.py dialog       CalcDlg     -o MyModule.m/src/
  python generate.py idl          ICalc       -o MyModule.m/
  python generate.py class        CalcUtil    -o MyModule.m/src/
  python generate.py testcase     CalcTest    -o MyModule.m/src/
  python generate.py xmltestcase  CalcXMLTest -o MyModule.m/
  python generate.py codegen      CalcCodeGen -o MyModule.m/src/
  python generate.py feature      CalcFeature -o MyModule.m/
  python generate.py eventlistener CalcEvt    -o MyModule.m/src/
  python generate.py resource     MyResources -o MyFramework.edu/
  python generate.py identitycard MyFwCard    -o IdentityCard/
  python generate.py imakefile    MyModule    -o MyModule.m/
  python generate.py dictionary   MyFw        -o MyFramework.edu/
        """,
    )

    parser.add_argument("type", choices=available, help="Template type")
    parser.add_argument("name", help="Component/class name")
    parser.add_argument("-o", "--output", default=".", help="Output directory")
    parser.add_argument("--interface", help="Interface name (required for component)")
    parser.add_argument("--framework", default="MyFramework", help="Framework name")
    parser.add_argument("--module", default="MyModule", help="Module name")

    args = parser.parse_args()
    out_dir = Path(args.output).resolve()

    result = gen.generate(
        args.type,
        args.name,
        out_dir,
        interface=args.interface,
        framework=args.framework,
        module=args.module,
    )

    gen.cache.save(result)
    exit_code = 0 if result["status"] == "success" else 1
    output_json(result, exit_code=exit_code)


if __name__ == "__main__":
    main()
