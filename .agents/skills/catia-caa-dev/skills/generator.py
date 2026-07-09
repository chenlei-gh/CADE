"""
CATIA CAA Generator
====================
Template-based code generation for CAA components.

The Generator is the backend — it receives a Spec and produces code.
It never knows about AI or user intent.

Usage: python generator.py [type] [name] [options]
Output: JSON with generation result

Supported types (ALL CATIA CAA RADE templates):
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

  Object Modeler:
    objectmodeler    Object Modeler (Feature/SpecObject)
    feature          Feature Component (5+ files)

  Utility:
    class            Plain C++ class
    adapter          3DS Adapter

  Testing:
    testcase         CATTestCase
    xmltestcase      XmlTestCase

  Code Generation:
    codegen          Code Generation Wizard

  Extension:
    eventlistener    CATIA Event Listener
    plugin           CATIA Plugin
    userexit         CATIA User Exit

  Resource:
    resource         Catalog + NLS + Icon + CATRsc (5 files)
    catalog          CATCatalog
    nls              CATNls (English + Chinese)
    icon             Icon resource
    catrsc           CATRsc resource
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from utils import Cache, Logger, output_json


class TemplateGenerator:
    """CAA Template Generator — supports ALL 21+ template types"""

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

        for tf in sorted(src_dir.rglob("*")):
            if tf.is_file() and not tf.name.startswith("."):
                rel = tf.relative_to(src_dir)
                out_file = out / str(rel).replace("FrameworkName", fw)
                out_file.parent.mkdir(parents=True, exist_ok=True)

                content = tf.read_text(encoding="utf-8", errors="replace")
                content = self._replace(content, name, fw, mod)
                for k, v in extra.items():
                    content = content.replace(k, v)

                if iface:
                    content = content.replace("IInterfaceName", iface)

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
                content = self._replace(content, name, fw, mod)
                if extra_repl:
                    for k, v in extra_repl.items():
                        content = content.replace(k, v)
                out_file.write_text(content, encoding="utf-8")
                generated.append(str(out_file))
                self.logger.write(f"Generated: {out_file}")

        if not found:
            return self._error(f"No templates found for prefix: {prefix}")

        return self._success(generated, prefix.lower(), name)

    # ─── Helpers ──────────────────────────────────────────────────

    def _replace(self, content: str, name: str, fw: str, mod: str) -> str:
        year = str(datetime.now().year)
        reps = {
            "YYYY": year,
            "ComponentName": name,
            "COMPONENTNAME": name.upper(),
            "ClassName": name,
            "IInterfaceName": name,
            "IIDLInterfaceName": name,
            "FrameworkName": fw,
            "FRAMEWORKNAME": fw.upper(),
            "FrameworkBareName": fw.replace(".edu", ""),
            "ModuleName": mod,
            "MODULENAME": mod.upper(),
            "TestCaseName": name,
            "XmlTestCaseName": name,
            "AdapterName": name,
            "AddinName": name,
            "PluginName": name,
            "UserExitName": name,
            "EventListenerName": name,
            "ObjectModelerName": name,
            "WorkshopAddinName": name,
            "CommandClassName": name,
            "CommandHeaderName": name,
            "DialogClass": name,
            "WorkbenchClass": name,
            "FeatureClass": name,
        }
        for k, v in reps.items():
            content = content.replace(k, v)
        return content

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
        src = out / f"{name}.cpp"
        src.write_text(
            self._render(
                "adapter", name, ExtensionClass=name, TargetObject=spec.target_object
            ),
            encoding="utf-8",
        )
        files.append(str(src))
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
        description="Generate CATIA CAA components from 21+ template types",
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
  python generate.py objectmodeler CalcObj    -o MyModule.m/src/
  python generate.py class        CalcUtil    -o MyModule.m/src/
  python generate.py testcase     CalcTest    -o MyModule.m/src/
  python generate.py xmltestcase  CalcXMLTest -o MyModule.m/
  python generate.py codegen      CalcCodeGen -o MyModule.m/src/
  python generate.py adapter      CalcAdapter -o MyModule.m/src/
  python generate.py feature      CalcFeature -o MyModule.m/
  python generate.py eventlistener CalcEvt    -o MyModule.m/src/
  python generate.py plugin       CalcPlugin  -o MyModule.m/src/
  python generate.py userexit     CalcExit    -o MyModule.m/src/
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
