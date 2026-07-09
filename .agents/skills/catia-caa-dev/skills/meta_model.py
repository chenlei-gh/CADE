"""
CATIA CAA Meta Model
=====================
Defines the object model for CAA workspace entities and their relationships.

Design principle:
  AI reasons about "Commands that belong to a Module in a Framework"
  NOT about "26 individual template wizards".

Entity relationships:
  Framework ──owns──→ Module ──owns──→ Command
                     Module ──owns──→ Component
                     Module ──owns──→ Interface
                     Module ──owns──→ Dialog
                     Framework ──has──→ Workbench
                     Command  ──may_have──→ Dialog
                     Command  ──has──→ CommandHeader
                     Command  ──registered_in──→ Catalog

============================
Table of Contents (1165 lines):
============================
  ENUMS:
  [Lines 30-50]    Enum: Visibility
  [Lines 53-80]    Enum: FeatureStartupType

  CORE ENTITIES (10 classes):
  [Lines 83-250]   class Framework         - Framework root (.edu)
  [Lines 253-380]  class Module            - Module container (.m)
  [Lines 383-550]  class Command           - Interactive command
  [Lines 553-650]  class Dialog            - UI dialog
  [Lines 653-750]  class Interface         - Interface definition
  [Lines 753-850]  class Component         - Component implementation
  [Lines 853-950]  class Workbench         - Workbench with toolbar
  [Lines 953-1050] class Feature           - Feature object
  [Lines 1053-1120] class Factory          - Feature factory
  [Lines 1123-1150] class Extension        - Data extension

  WORKSPACE:
  [Lines 1153-1165] class WorkspaceSnapshot - Complete workspace state

Note: This is a Rich Domain Model - entities are intentionally co-located
      for cohesion. Splitting would create circular dependencies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ─── Enums ──────────────────────────────────────────────────────


class Visibility:
    ALWAYS = "always"
    CONTEXT = "context"
    HIDDEN = "hidden"


class RelationType(Enum):
    """Types of relationships between entities"""

    BELONGS_TO = "belongs_to"  # Command -> Module
    OWNS = "owns"  # Module -> Command
    HAS = "has"  # Command -> Dialog
    IMPLEMENTS = "implements"  # Component -> Interface
    EXTENDS = "extends"  # Interface -> Interface
    USES = "uses"  # Workbench -> Command
    REGISTERED_IN = "registered_in"  # Command -> Catalog
    DEPENDS_ON = "depends_on"  # Generic dependency
    PROVIDES = "provides"  # Module -> Interface


# ─── Entity Base ─────────────────────────────────────────────────


@dataclass
class Entity:
    """Base entity with common metadata"""

    name: str
    path: Path
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {"name": self.name, "path": str(self.path), **self.metadata}

    def __hash__(self):
        return hash((self.name, str(self.path)))


# ─── Core Entities ───────────────────────────────────────────────


@dataclass
class Framework(Entity):
    """Top-level CAA project container — knows its own structure"""

    modules: List[Module] = field(default_factory=list)
    workbenches: List[Workbench] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    identitycard: Optional[Path] = None
    dictionary: Optional[Path] = None
    catalog: Optional[Path] = None
    nls_files: List[Path] = field(default_factory=list)
    icon_resources: List[Path] = field(default_factory=list)
    rsc_files: List[Path] = field(default_factory=list)
    function_tests: Optional[Path] = None

    # ── Domain Methods ──────────────────────────────────────────

    @property
    def bare_name(self) -> str:
        """Framework name without .edu suffix"""
        return self.name.replace(".edu", "")

    def dictionary_path(self) -> Path:
        """CNext/code/dictionary/{bare_name}.dico"""
        return self.path / "CNext" / "code" / "dictionary" / f"{self.bare_name}.dico"

    def catalog_path(self) -> Path:
        """CNext/resources/msgcatalog/{bare_name}.CATNls"""
        return (
            self.path
            / "CNext"
            / "resources"
            / "msgcatalog"
            / f"{self.bare_name}.CATNls"
        )

    def identitycard_path(self) -> Path:
        """IdentityCard/IdentityCard.h"""
        return self.path / "IdentityCard" / "IdentityCard.h"

    def rsc_path(self) -> Path:
        """CNext/resources/resources/{bare_name}.CATRsc"""
        return (
            self.path
            / "CNext"
            / "resources"
            / "resources"
            / f"{self.bare_name}.CATRsc"
        )

    def function_tests_path(self) -> Path:
        """FunctionTests/ directory"""
        return self.path / "FunctionTests"

    def cnext_dir(self) -> Path:
        return self.path / "CNext"

    def find_module(self, name: str) -> Optional[Module]:
        """Find a module by name (with or without .m suffix)"""
        target = name if name.endswith(".m") else f"{name}.m"
        for m in self.modules:
            if m.name == name or m.name == target:
                return m
        return None

    def add_module(self, m: Module):
        m.framework = self
        self.modules.append(m)

    def remove_module(self, name: str) -> bool:
        for m in self.modules:
            if m.name == name:
                self.modules.remove(m)
                return True
        return False

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update(
            {
                "modules": [m.name for m in self.modules],
                "workbenches": [w.name for w in self.workbenches],
                "dependencies": self.dependencies,
                "module_count": len(self.modules),
                "has_dictionary": self.dictionary is not None,
                "has_catalog": self.catalog is not None,
                "has_function_tests": self.function_tests is not None,
                "has_rsc": len(self.rsc_files) > 0,
            }
        )
        return d


@dataclass
class Module(Entity):
    """Compilation unit within a Framework — knows its own structure"""

    framework: Optional[Framework] = None
    components: List[Component] = field(default_factory=list)
    interfaces: List[Interface] = field(default_factory=list)
    commands: List[Command] = field(default_factory=list)
    dialogs: List[Dialog] = field(default_factory=list)
    imakefile: Optional[Path] = None
    local_interfaces: List[Path] = field(default_factory=list)
    public_interfaces: List[Path] = field(default_factory=list)
    src_dir: Optional[Path] = None
    resources_dir: Optional[Path] = None

    # ── Domain Methods ──────────────────────────────────────────

    @property
    def bare_name(self) -> str:
        """Module name without .m suffix"""
        return self.name.replace(".m", "")

    def src_dir_path(self) -> Path:
        """{module}/src/"""
        return self.src_dir or self.path / "src"

    def local_interfaces_dir(self) -> Path:
        """{module}/LocalInterfaces/"""
        return self.path / "LocalInterfaces"

    def public_interfaces_dir(self) -> Path:
        """{module}/PublicInterfaces/"""
        return self.path / "PublicInterfaces"

    def imakefile_path(self) -> Path:
        """{module}/Imakefile.mk"""
        return self.imakefile or self.path / "Imakefile.mk"

    def find_command(self, name: str) -> Optional[Command]:
        for c in self.commands:
            if c.name.lower() == name.lower():
                return c
        return None

    def find_interface(self, name: str) -> Optional[Interface]:
        for i in self.interfaces:
            if i.name.lower() == name.lower():
                return i
        return None

    @property
    def command_count(self) -> int:
        return len(self.commands)

    @property
    def interface_count(self) -> int:
        return len(self.interfaces)

    @property
    def component_count(self) -> int:
        return len(self.components)

    def add_command(self, c: Command):
        c.module = self
        self.commands.append(c)

    def remove_command(self, name: str) -> bool:
        for c in self.commands:
            if c.name == name:
                self.commands.remove(c)
                return True
        return False

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update(
            {
                "framework": self.framework.name if self.framework else None,
                "components": [c.name for c in self.components],
                "interfaces": [i.name for i in self.interfaces],
                "commands": [c.name for c in self.commands],
                "dialogs": [d.name for d in self.dialogs],
                "has_imakefile": self.imakefile is not None,
            }
        )
        return d


@dataclass
class Interface(Entity):
    """CAA Interface — knows its own files"""

    module: Optional[Module] = None
    is_idl: bool = False
    idl_file: Optional[Path] = None
    implemented_by: List[Component] = field(default_factory=list)
    header: Optional[Path] = None
    source: Optional[Path] = None
    iid: Optional[str] = None

    def header_path(self) -> Optional[Path]:
        if self.header and self.header.exists():
            return self.header
        if self.module:
            return self.module.public_interfaces_dir() / f"{self.name}.h"
        return None

    def idl_path(self) -> Optional[Path]:
        if self.idl_file:
            return self.idl_file
        if self.module and self.is_idl:
            return self.module.public_interfaces_dir() / f"{self.name}.idl"
        return None

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update(
            {
                "module": self.module.name if self.module else None,
                "is_idl": self.is_idl,
                "implemented_by": [c.name for c in self.implemented_by],
            }
        )
        return d


@dataclass
class Component(Entity):
    """CAA Component (implementation class)"""

    module: Optional[Module] = None
    implements: List[Interface] = field(default_factory=list)
    parent_class: str = "CATBaseUnknown"
    boa_bound: bool = True
    header: Optional[Path] = None
    source: Optional[Path] = None
    tie_header: Optional[Path] = None

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update(
            {
                "module": self.module.name if self.module else None,
                "implements": [i.name for i in self.implements],
                "parent_class": self.parent_class,
            }
        )
        return d


@dataclass
class Command(Entity):
    """CATIA Command — knows its own files, registration and resources"""

    module: Optional[Module] = None
    is_stateful: bool = False
    dialog: Optional[Dialog] = None
    workbench: Optional[Workbench] = None
    header: Optional[Path] = None
    header_source: Optional[Path] = None
    icon: Optional[str] = None
    tooltip: Optional[str] = None
    category: Optional[str] = None
    visibility: str = Visibility.ALWAYS
    nls_keys: List[str] = field(default_factory=list)

    # ── Domain Methods: paths ───────────────────────────────────

    def header_path(self) -> Optional[Path]:
        """{module}/LocalInterfaces/{name}.h"""
        if self.header and self.header.exists():
            return self.header
        if self.module:
            return self.module.local_interfaces_dir() / f"{self.name}.h"
        return None

    def source_path(self) -> Optional[Path]:
        """{module}/src/{name}.cpp"""
        if self.module:
            return self.module.src_dir_path() / f"{self.name}.cpp"
        return None

    def header_source_path(self) -> Optional[Path]:
        """{module}/src/{name}Header.cpp — registration file"""
        if self.header_source and self.header_source.exists():
            return self.header_source
        if self.module:
            return self.module.src_dir_path() / f"{self.name}Header.cpp"
        return None

    # ── Domain Methods: registration ────────────────────────────

    def dictionary_entry(self) -> str:
        """Catalog entry line: MyCmd CATStateCommand libMyModule"""
        cmd_type = (
            "CATStateCommand" if self.is_stateful or self.dialog else "CATCommand"
        )
        module_lib = self.module.bare_name if self.module else ""
        return f"{self.name}  {cmd_type}  lib{module_lib}"

    def nls_title(self) -> str:
        """NLS title entry: MyCmd.Title"""
        return self.tooltip or self.name

    def nls_tip(self) -> str:
        """NLS tip entry: MyCmd.Tip"""
        return self.tooltip or f"Execute {self.name}"

    def nls_block(self) -> str:
        """Full NLS entry block"""
        return (
            f'{self.name}.Title = "{self.nls_title()}";\n'
            f'{self.name}.Tip   = "{self.nls_tip()}";\n'
            f'{self.name}.Help  = "Help for {self.name}";\n'
        )

    def icon_name(self) -> str:
        """Icon file name: MyCmd.png"""
        return f"{self.name}.png"

    def imakefile_sources(self) -> str:
        """Sources to append to Imakefile.mk SOURCES list"""
        return f"    src/{self.name}.cpp \\\n    src/{self.name}Header.cpp"

    # ── Domain Methods: validation ──────────────────────────────

    def has_header(self) -> bool:
        return self.header_path() is not None and self.header_path().exists()

    def has_source(self) -> bool:
        return self.source_path() is not None and self.source_path().exists()

    def has_dialog(self) -> bool:
        return self.dialog is not None

    @property
    def all_files(self) -> List[Path]:
        """All file paths related to this command"""
        files = []
        for f in [self.header_path(), self.source_path(), self.header_source_path()]:
            if f:
                files.append(f)
        if self.dialog:
            files.extend(self.dialog.all_files)
        return [f for f in files if f is not None]

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update(
            {
                "module": self.module.name if self.module else None,
                "is_stateful": self.is_stateful,
                "dialog": self.dialog.name if self.dialog else None,
                "workbench": self.workbench.name if self.workbench else None,
                "visibility": self.visibility,
            }
        )
        return d


@dataclass
class Dialog(Entity):
    """CATIA Dialog — knows its own files"""

    module: Optional[Module] = None
    parent_command: Optional[Command] = None
    nls_keys: List[str] = field(default_factory=list)

    # ── Domain Methods ──────────────────────────────────────────

    def header_path(self) -> Optional[Path]:
        if self.module:
            return self.module.local_interfaces_dir() / f"{self.name}.h"
        return None

    def source_path(self) -> Optional[Path]:
        if self.module:
            return self.module.src_dir_path() / f"{self.name}.cpp"
        return None

    @property
    def all_files(self) -> List[Path]:
        files = []
        for f in [self.header_path(), self.source_path()]:
            if f:
                files.append(f)
        return files

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update(
            {
                "module": self.module.name if self.module else None,
                "parent_command": self.parent_command.name
                if self.parent_command
                else None,
            }
        )
        return d


@dataclass
class Workbench(Entity):
    """CATIA Workbench — knows its own structure"""

    framework: Optional[Framework] = None
    commands: List[Command] = field(default_factory=list)
    addin_header: Optional[Path] = None
    addin_source: Optional[Path] = None
    icon: Optional[str] = None

    # ── Domain Methods ──────────────────────────────────────────

    def addin_header_path(self) -> Optional[Path]:
        if self.addin_header:
            return self.addin_header
        if self.framework and self.framework.modules:
            mod = self.framework.modules[0]
            return mod.local_interfaces_dir() / f"{self.name}.h"
        return None

    def addin_source_path(self) -> Optional[Path]:
        if self.addin_source:
            return self.addin_source
        if self.framework and self.framework.modules:
            mod = self.framework.modules[0]
            return mod.src_dir_path() / f"{self.name}Addin.cpp"
        return None

    def get_command(self, name: str) -> Optional[Command]:
        for c in self.commands:
            if c.name.lower() == name.lower():
                return c
        return None

    def add_command(self, c: Command):
        c.workbench = self
        self.commands.append(c)

    def remove_command(self, name: str) -> bool:
        for c in self.commands:
            if c.name == name:
                c.workbench = None
                self.commands.remove(c)
                return True
        return False

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update(
            {
                "framework": self.framework.name if self.framework else None,
                "commands": [c.name for c in self.commands],
            }
        )
        return d


# ─── Feature Model ───────────────────────────────────────────────


@dataclass
class FeatureModel(Entity):
    """CATIA Feature — knows its structure, attributes, and factory"""

    module: Optional[Module] = None
    framework: Optional[Framework] = None
    attributes: List[Dict] = field(default_factory=list)
    parent_feature: Optional[str] = None
    factory: Optional["FactoryModel"] = None
    interfaces: List[str] = field(default_factory=list)
    _default_interfaces: List[str] = field(
        default_factory=lambda: ["CATIBuild", "CATIContextualSubMenu"]
    )

    def header_path(self) -> Optional[Path]:
        if self.module:
            return self.module.local_interfaces_dir() / f"{self.name}.h"

    def source_path(self) -> Optional[Path]:
        if self.module:
            return self.module.src_dir_path() / f"{self.name}.cpp"

    def all_interfaces(self) -> List[str]:
        return self._default_interfaces + self.interfaces

    def dictionary_entry(self) -> str:
        lib = self.module.bare_name if self.module else ""
        return f"{self.name}  CATBaseUnknown  lib{lib}"

    @property
    def all_files(self) -> List[Path]:
        files = [f for f in [self.header_path(), self.source_path()] if f]
        if self.factory:
            files.extend(self.factory.all_files)
        return files

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update(
            {
                "module": self.module.name if self.module else None,
                "attributes": self.attributes,
                "factory": self.factory.name if self.factory else None,
                "interfaces": self.all_interfaces(),
            }
        )
        return d


@dataclass
class FactoryModel(Entity):
    """Feature Factory — creates instances of a Feature"""

    module: Optional[Module] = None
    feature: Optional[FeatureModel] = None
    catalog_file: Optional[Path] = None

    def header_path(self) -> Optional[Path]:
        if self.module:
            return self.module.local_interfaces_dir() / f"{self.name}.h"

    def source_path(self) -> Optional[Path]:
        if self.module:
            return self.module.src_dir_path() / f"{self.name}.cpp"

    def catalog_path(self) -> Optional[Path]:
        if self.catalog_file:
            return self.catalog_file
        if self.feature and self.feature.framework:
            return (
                self.feature.framework.cnext_dir()
                / "resources"
                / "graphic"
                / f"{self.feature.name}Catalog.CATfct"
            )

    @property
    def all_files(self) -> List[Path]:
        return [
            f
            for f in [self.header_path(), self.source_path(), self.catalog_path()]
            if f
        ]

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update(
            {
                "module": self.module.name if self.module else None,
                "feature": self.feature.name if self.feature else None,
            }
        )
        return d


# ─── Extension Model ─────────────────────────────────────────────


@dataclass
class ExtensionModel(Entity):
    """Data Extension — extends existing CATIA object with data members"""

    module: Optional[Module] = None
    target_object: str = ""
    data_members: List[Dict] = field(default_factory=list)
    implements: List[str] = field(default_factory=list)

    def header_path(self) -> Optional[Path]:
        if self.module:
            return self.module.local_interfaces_dir() / f"{self.name}.h"

    def source_path(self) -> Optional[Path]:
        if self.module:
            return self.module.src_dir_path() / f"{self.name}.cpp"

    def tie_header_path(self) -> Optional[Path]:
        if self.module and self.implements:
            return self.module.local_interfaces_dir() / f"TIE_{self.implements[0]}.h"

    def dictionary_entry(self) -> str:
        lib = self.module.bare_name if self.module else ""
        target = self.target_object or "CATBaseUnknown"
        return f"{self.name}  {target}  lib{lib}"

    @property
    def all_files(self) -> List[Path]:
        return [
            f
            for f in [self.header_path(), self.source_path(), self.tie_header_path()]
            if f
        ]

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update(
            {
                "module": self.module.name if self.module else None,
                "target_object": self.target_object,
                "data_members": self.data_members,
                "implements": self.implements,
            }
        )
        return d


@dataclass
class Resource(Entity):
    """Resource file (Catalog, NLS, Icon, Rsc)"""

    resource_type: str = ""  # "catalog" | "nls" | "icon" | "rsc"
    framework: Optional[Framework] = None
    language: str = "en"  # for NLS files

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update(
            {
                "resource_type": self.resource_type,
                "framework": self.framework.name if self.framework else None,
                "language": self.language,
            }
        )
        return d


# ─── Workspace Snapshot ──────────────────────────────────────────


@dataclass
class WorkspaceSnapshot:
    """Complete snapshot of the workspace meta model"""

    root: Path
    frameworks: List[Framework] = field(default_factory=list)
    orphaned_files: List[Path] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    dependency_graph: Optional[DependencyGraph] = None

    def __post_init__(self):
        """Initialize dependency graph if not provided"""
        if self.dependency_graph is None:
            self.dependency_graph = DependencyGraph()
            self._build_dependency_graph()

    def _build_dependency_graph(self):
        """Build dependency graph from workspace entities"""
        graph = self.dependency_graph

        # Add all entities
        for fw in self.frameworks:
            graph.add_entity(fw)

            for mod in fw.modules:
                graph.add_entity(mod)
                graph.add_relationship(mod, fw, RelationType.BELONGS_TO)
                graph.add_relationship(fw, mod, RelationType.OWNS)

                for cmd in mod.commands:
                    graph.add_entity(cmd)
                    graph.add_relationship(cmd, mod, RelationType.BELONGS_TO)
                    graph.add_relationship(mod, cmd, RelationType.OWNS)

                    # Command -> Dialog
                    if cmd.dialog:
                        graph.add_entity(cmd.dialog)
                        graph.add_relationship(cmd, cmd.dialog, RelationType.HAS)

                    # Command -> Workbench
                    if cmd.workbench:
                        graph.add_relationship(cmd.workbench, cmd, RelationType.USES)

                for iface in mod.interfaces:
                    graph.add_entity(iface)
                    graph.add_relationship(iface, mod, RelationType.BELONGS_TO)
                    graph.add_relationship(mod, iface, RelationType.PROVIDES)

                for comp in mod.components:
                    graph.add_entity(comp)
                    graph.add_relationship(comp, mod, RelationType.BELONGS_TO)

                    # Component -> Interface
                    for iface in comp.implements:
                        graph.add_relationship(comp, iface, RelationType.IMPLEMENTS)

                for dlg in mod.dialogs:
                    graph.add_entity(dlg)
                    graph.add_relationship(dlg, mod, RelationType.BELONGS_TO)

            for wb in fw.workbenches:
                graph.add_entity(wb)
                graph.add_relationship(wb, fw, RelationType.BELONGS_TO)

                for cmd in wb.commands:
                    graph.add_relationship(wb, cmd, RelationType.USES)

    def get_framework(self, name: str) -> Optional[Framework]:
        for f in self.frameworks:
            if f.name == name or f.name.startswith(name):
                return f
        return None

    def get_module(
        self, name: str, framework_name: Optional[str] = None
    ) -> Optional[Module]:
        if framework_name:
            fw = self.get_framework(framework_name)
            if fw:
                for m in fw.modules:
                    if m.name == name:
                        return m
        else:
            for fw in self.frameworks:
                for m in fw.modules:
                    if m.name == name:
                        return m
        return None

    def get_all_commands(self) -> List[Command]:
        cmds = []
        for fw in self.frameworks:
            for mod in fw.modules:
                cmds.extend(mod.commands)
        return cmds

    def get_all_interfaces(self) -> List[Interface]:
        ifaces = []
        for fw in self.frameworks:
            for mod in fw.modules:
                ifaces.extend(mod.interfaces)
        return ifaces

    def get_all_workbenches(self) -> List[Workbench]:
        wbs = []
        for fw in self.frameworks:
            wbs.extend(fw.workbenches)
        return wbs

    def get_dependencies(self, entity: Entity) -> List[Entity]:
        """Get all entities that this entity depends on"""
        if self.dependency_graph:
            return self.dependency_graph.get_dependencies(entity)
        return []

    def get_dependents(self, entity: Entity) -> List[Entity]:
        """Get all entities that depend on this entity"""
        if self.dependency_graph:
            return self.dependency_graph.get_dependents(entity)
        return []

    def find_cascade_delete(self, entity: Entity) -> List[Entity]:
        """Find all entities that should be deleted with this entity"""
        if self.dependency_graph:
            return self.dependency_graph.find_cascade_delete(entity)
        return [entity]

    def find_breaking_dependents(self, entity: Entity) -> List[Tuple[Entity, str]]:
        """Find entities that will break if this entity is deleted"""
        if self.dependency_graph:
            return self.dependency_graph.find_breaking_dependents(entity)
        return []

    def visualize_dependencies(self, entity: Optional[Entity] = None) -> str:
        """Generate Mermaid diagram of dependencies"""
        if self.dependency_graph:
            return self.dependency_graph.visualize_mermaid(entity)
        return "graph TD\n    No dependencies"

    def to_dict(self) -> Dict:
        result = {
            "root": str(self.root),
            "frameworks": [fw.to_dict() for fw in self.frameworks],
            "framework_count": len(self.frameworks),
            "total_modules": sum(len(fw.modules) for fw in self.frameworks),
            "total_commands": len(self.get_all_commands()),
            "total_interfaces": len(self.get_all_interfaces()),
            "total_workbenches": len(self.get_all_workbenches()),
            "warnings": self.warnings,
        }

        # Add dependency graph if available
        if self.dependency_graph:
            result["dependency_graph"] = self.dependency_graph.to_dict()

        return result

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def diff(self, previous: "WorkspaceSnapshot") -> dict:
        """Compare with a previous snapshot, return what changed"""
        changes = {
            "added_commands": [],
            "removed_commands": [],
            "added_modules": [],
            "removed_modules": [],
            "framework_count_change": len(self.frameworks) - len(previous.frameworks),
            "command_count_change": len(self.get_all_commands())
            - len(previous.get_all_commands()),
            "warning_count_change": len(self.warnings) - len(previous.warnings),
        }

        prev_cmds = {c.name for c in previous.get_all_commands()}
        curr_cmds = {c.name for c in self.get_all_commands()}
        changes["added_commands"] = list(curr_cmds - prev_cmds)
        changes["removed_commands"] = list(prev_cmds - curr_cmds)

        prev_mods = {m.name for fw in previous.frameworks for m in fw.modules}
        curr_mods = {m.name for fw in self.frameworks for m in fw.modules}
        changes["added_modules"] = list(curr_mods - prev_mods)
        changes["removed_modules"] = list(prev_mods - curr_mods)

        total_change = (
            len(changes["added_commands"])
            + len(changes["removed_commands"])
            + len(changes["added_modules"])
            + len(changes["removed_modules"])
        )
        changes["has_changes"] = (
            total_change > 0 or changes["warning_count_change"] != 0
        )
        changes["total_changes"] = total_change

        return changes


# ─── Snapshot History (Versioned) ────────────────────────────────


@dataclass
class SnapshotHistory:
    """Versioned history of workspace snapshots for diff and rollback"""

    snapshots: List[dict] = field(default_factory=list)
    _max_history: int = 50

    def record(self, snapshot: WorkspaceSnapshot, label: str = "") -> dict:
        """Record a snapshot with timestamp. Returns the snapshot record."""
        from datetime import datetime

        record = {
            "version": len(self.snapshots) + 1,
            "timestamp": datetime.now().isoformat(),
            "label": label,
            "data": snapshot.to_dict(),
        }

        # Compute diff from previous
        if self.snapshots:
            prev_data = self.snapshots[-1]["data"]
            prev = WorkspaceSnapshot(
                root=Path(prev_data["root"]),
                warnings=prev_data.get("warnings", []),
            )
            record["diff"] = snapshot.diff(prev)
        else:
            record["diff"] = {"has_changes": True, "message": "Initial snapshot"}

        self.snapshots.append(record)
        if len(self.snapshots) > self._max_history:
            self.snapshots.pop(0)

        return record

    def latest(self) -> Optional[dict]:
        return self.snapshots[-1] if self.snapshots else None

    def diff_last_two(self) -> dict:
        """Diff between the last two snapshots"""
        if len(self.snapshots) >= 2:
            return self.snapshots[-1].get("diff", {})
        return {"has_changes": False, "message": "Need at least 2 snapshots"}

    def summary(self) -> dict:
        return {
            "total_snapshots": len(self.snapshots),
            "latest_version": self.snapshots[-1]["version"] if self.snapshots else 0,
            "latest_time": self.snapshots[-1]["timestamp"] if self.snapshots else "",
        }


# ─── Helpers ─────────────────────────────────────────────────────


def create_entity_id(
    entity_type: str, name: str, parent_name: Optional[str] = None
) -> str:
    """Create a unique entity identifier"""
    if parent_name:
        return f"{parent_name}::{entity_type}::{name}"
    return f"{entity_type}::{name}"


# ─── Dependency Graph ────────────────────────────────────────────


@dataclass
class Relationship:
    """Represents a relationship between two entities"""

    source: Entity
    target: Entity
    rel_type: RelationType
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "source": self.source.name,
            "target": self.target.name,
            "type": self.rel_type.value,
            "metadata": self.metadata,
        }


class DependencyGraph:
    """Manages relationships between all workspace entities"""

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.relationships: List[Relationship] = []

    def add_entity(self, entity: Entity) -> None:
        """Register an entity in the graph"""
        entity_id = self._get_entity_id(entity)
        self.entities[entity_id] = entity

    def add_relationship(
        self,
        source: Entity,
        target: Entity,
        rel_type: RelationType,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Add a relationship between two entities"""
        rel = Relationship(
            source=source, target=target, rel_type=rel_type, metadata=metadata or {}
        )
        self.relationships.append(rel)

    def get_dependencies(
        self, entity: Entity, rel_type: Optional[RelationType] = None
    ) -> List[Entity]:
        """Get all entities that this entity depends on"""
        deps = []
        for rel in self.relationships:
            if rel.source == entity:
                if rel_type is None or rel.rel_type == rel_type:
                    deps.append(rel.target)
        return deps

    def get_dependents(
        self, entity: Entity, rel_type: Optional[RelationType] = None
    ) -> List[Entity]:
        """Get all entities that depend on this entity"""
        dependents = []
        for rel in self.relationships:
            if rel.target == entity:
                if rel_type is None or rel.rel_type == rel_type:
                    dependents.append(rel.source)
        return dependents

    def find_cascade_delete(
        self, entity: Entity, visited: Optional[Set[str]] = None
    ) -> List[Entity]:
        """
        Find all entities that should be deleted when this entity is deleted.
        Uses recursive traversal to find all dependent entities.
        """
        if visited is None:
            visited = set()

        entity_id = self._get_entity_id(entity)
        if entity_id in visited:
            return []

        visited.add(entity_id)
        cascade = [entity]

        # Find direct dependencies (things this entity owns/has)
        for rel in self.relationships:
            if rel.source == entity:
                # Only cascade delete for ownership relationships
                if rel.rel_type in [
                    RelationType.HAS,
                    RelationType.OWNS,
                    RelationType.REGISTERED_IN,
                ]:
                    # Recursively find what the target owns
                    cascade.extend(self.find_cascade_delete(rel.target, visited))

        return cascade

    def find_breaking_dependents(self, entity: Entity) -> List[Tuple[Entity, str]]:
        """
        Find entities that will break if this entity is deleted.
        Returns list of (entity, reason) tuples.
        """
        breaking = []
        dependents = self.get_dependents(entity)

        for dep in dependents:
            # Check if dependent is using (not owning) this entity
            for rel in self.relationships:
                if rel.source == dep and rel.target == entity:
                    if rel.rel_type in [RelationType.USES, RelationType.DEPENDS_ON]:
                        reason = (
                            f"{dep.name} uses {entity.name} via {rel.rel_type.value}"
                        )
                        breaking.append((dep, reason))

        return breaking

    def get_all_files(self, entity: Entity) -> List[Path]:
        """
        Get all file paths associated with an entity and its dependencies.
        Useful for deletion operations.
        """
        files = []

        # Add entity's own files
        if hasattr(entity, "path") and entity.path:
            files.append(entity.path)
        if hasattr(entity, "header") and entity.header:
            files.append(entity.header)
        if hasattr(entity, "source") and entity.source:
            files.append(entity.source)
        if hasattr(entity, "header_source") and entity.header_source:
            files.append(entity.header_source)

        # Add dependency files
        deps = self.get_dependencies(entity)
        for dep in deps:
            if hasattr(dep, "path") and dep.path:
                files.append(dep.path)

        return [f for f in files if f is not None]

    def visualize_mermaid(
        self, entity: Optional[Entity] = None, max_depth: int = 2
    ) -> str:
        """
        Generate a Mermaid diagram showing relationships.
        If entity is provided, focuses on that entity's neighborhood.
        """
        lines = ["graph TD"]

        if entity:
            # Focus on specific entity
            visited = set()
            self._add_entity_to_diagram(entity, lines, visited, 0, max_depth)
        else:
            # Show all relationships
            for rel in self.relationships:
                source_id = self._sanitize_id(rel.source.name)
                target_id = self._sanitize_id(rel.target.name)
                edge_label = rel.rel_type.value
                lines.append(
                    f"    {source_id}[{rel.source.name}] -->|{edge_label}| {target_id}[{rel.target.name}]"
                )

        return "\n".join(lines)

    def _add_entity_to_diagram(
        self,
        entity: Entity,
        lines: List[str],
        visited: Set[str],
        depth: int,
        max_depth: int,
    ):
        """Recursively add entity and its relationships to diagram"""
        entity_id = self._get_entity_id(entity)
        if entity_id in visited or depth > max_depth:
            return

        visited.add(entity_id)

        # Add outgoing relationships
        for rel in self.relationships:
            if rel.source == entity:
                source_id = self._sanitize_id(rel.source.name)
                target_id = self._sanitize_id(rel.target.name)
                edge_label = rel.rel_type.value
                lines.append(
                    f"    {source_id}[{rel.source.name}] -->|{edge_label}| {target_id}[{rel.target.name}]"
                )
                # Recurse into target
                self._add_entity_to_diagram(
                    rel.target, lines, visited, depth + 1, max_depth
                )

        # Add incoming relationships
        for rel in self.relationships:
            if rel.target == entity:
                source_id = self._sanitize_id(rel.source.name)
                target_id = self._sanitize_id(rel.target.name)
                edge_label = rel.rel_type.value
                lines.append(
                    f"    {source_id}[{rel.source.name}] -->|{edge_label}| {target_id}[{rel.target.name}]"
                )

    def to_dict(self) -> Dict:
        """Export graph as JSON-serializable dict"""
        return {
            "entities": {eid: e.to_dict() for eid, e in self.entities.items()},
            "relationships": [r.to_dict() for r in self.relationships],
            "entity_count": len(self.entities),
            "relationship_count": len(self.relationships),
        }

    def _get_entity_id(self, entity: Entity) -> str:
        """Generate unique ID for an entity"""
        return f"{entity.__class__.__name__}::{entity.name}"

    def _sanitize_id(self, name: str) -> str:
        """Sanitize name for use in Mermaid diagram"""
        return name.replace(".", "_").replace(" ", "_").replace("-", "_")
