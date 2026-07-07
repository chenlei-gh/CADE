"""
CATIA CAA Specification Layer
==============================
Contract between Intent and Generator.

Design principle:
  Intent produces a Spec, Generator consumes a Spec.
  Neither knows about the other.
  Spec is the single source of truth for what to create.

Spec classes:
  CommandSpec, DialogSpec, FeatureSpec, ExtensionSpec,
  InterfaceSpec, ComponentSpec, WorkbenchSpec
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Visibility(Enum):
    ALWAYS = "always"
    CONTEXT = "context"
    HIDDEN = "hidden"


# ─── Base Spec ────────────────────────────────────────────────────


@dataclass
class Spec:
    """Base specification — all specs have a name and optional metadata"""

    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> dict:
        """Validate this spec. Returns {'status': 'ok'} or {'status': 'error', ...}"""
        return {"status": "ok"}

    def to_dict(self) -> dict:
        return {
            "type": self.__class__.__name__,
            "name": self.name,
            **self._fields_dict(),
            "metadata": self.metadata,
        }

    def _fields_dict(self) -> dict:
        """Override in subclasses"""
        return {}


# ─── DialogSpec ───────────────────────────────────────────────────


@dataclass
class DialogSpec(Spec):
    """Specification for a CATIA Dialog"""

    layout: str = "vertical"  # vertical | horizontal | grid
    modal: bool = True
    controls: List[Dict] = field(default_factory=list)
    with_callbacks: bool = True

    def validate(self) -> dict:
        if not self.name:
            return {"status": "error", "message": "Dialog name is required"}
        if self.layout not in ("vertical", "horizontal", "grid"):
            return {"status": "error", "message": f"Invalid layout: {self.layout}"}
        for i, ctrl in enumerate(self.controls):
            if "type" not in ctrl:
                return {"status": "error", "message": f"Control #{i} missing 'type'"}
        return {"status": "ok"}

    def _fields_dict(self) -> dict:
        return {"layout": self.layout, "modal": self.modal, "controls": self.controls}


# ─── CommandSpec ──────────────────────────────────────────────────


@dataclass
class CommandSpec(Spec):
    """Specification for a complete CATIA Command"""

    module: str = ""
    framework: str = ""
    stateful: bool = False
    visibility: str = "always"
    category: str = "General"
    tooltip: Optional[str] = None
    icon: Optional[str] = None
    header_name: Optional[str] = None

    # Nested specs
    dialog: Optional[DialogSpec] = None
    workbench: Optional[str] = None  # workbench name to add to

    def validate(self) -> dict:
        if not self.name:
            return {"status": "error", "message": "Command name is required"}
        if not self.module:
            return {"status": "error", "message": "Module name is required"}
        if self.dialog:
            dlg_err = self.dialog.validate()
            if dlg_err["status"] != "ok":
                return dlg_err
        return {"status": "ok"}

    def _fields_dict(self) -> dict:
        d = {
            "module": self.module,
            "framework": self.framework,
            "stateful": self.stateful,
            "visibility": self.visibility,
            "category": self.category,
        }
        if self.tooltip:
            d["tooltip"] = self.tooltip
        if self.icon:
            d["icon"] = self.icon
        if self.dialog:
            d["dialog"] = self.dialog.to_dict()
        if self.workbench:
            d["workbench"] = self.workbench
        return d


# ─── InterfaceSpec ────────────────────────────────────────────────


@dataclass
class MethodSpec:
    """Specification for a single interface method"""

    name: str
    params: List[str] = field(default_factory=list)
    return_type: str = "HRESULT"


@dataclass
class InterfaceSpec(Spec):
    """Specification for a CAA Interface"""

    module: str = ""
    framework: str = ""
    methods: List[MethodSpec] = field(default_factory=list)
    use_idl: bool = True
    generate_tie: bool = True

    def validate(self) -> dict:
        if not self.name:
            return {"status": "error", "message": "Interface name is required"}
        if not self.name.startswith("I"):
            return {
                "status": "warning",
                "message": "Interface name should start with 'I'",
            }
        return {"status": "ok"}

    @property
    def method_names(self) -> List[str]:
        return [m.name for m in self.methods]

    def _fields_dict(self) -> dict:
        return {
            "module": self.module,
            "framework": self.framework,
            "methods": [
                {"name": m.name, "params": m.params, "return_type": m.return_type}
                for m in self.methods
            ],
            "use_idl": self.use_idl,
        }


# ─── ComponentSpec ────────────────────────────────────────────────


@dataclass
class ComponentSpec(Spec):
    """Specification for a CAA Component"""

    module: str = ""
    framework: str = ""
    implements: List[str] = field(default_factory=list)  # interface names
    use_tie: bool = True
    generate_skeleton: bool = True
    parent_class: str = "CATBaseUnknown"

    def validate(self) -> dict:
        if not self.name:
            return {"status": "error", "message": "Component name is required"}
        return {"status": "ok"}

    def _fields_dict(self) -> dict:
        return {
            "module": self.module,
            "framework": self.framework,
            "implements": self.implements,
            "use_tie": self.use_tie,
            "parent_class": self.parent_class,
        }


# ─── FeatureSpec ──────────────────────────────────────────────────


@dataclass
class AttributeSpec:
    """Specification for a Feature attribute"""

    name: str
    type: str = "CATLength"
    default: str = ""


@dataclass
class FeatureSpec(Spec):
    """Specification for a CATIA Feature"""

    module: str = ""
    framework: str = ""
    attributes: List[AttributeSpec] = field(default_factory=list)
    with_factory: bool = True
    with_catalog: bool = True
    parent_feature: Optional[str] = None

    def validate(self) -> dict:
        if not self.name:
            return {"status": "error", "message": "Feature name is required"}
        return {"status": "ok"}

    @property
    def attribute_names(self) -> List[str]:
        return [a.name for a in self.attributes]

    def _fields_dict(self) -> dict:
        return {
            "module": self.module,
            "framework": self.framework,
            "attributes": [
                {"name": a.name, "type": a.type, "default": a.default}
                for a in self.attributes
            ],
            "with_factory": self.with_factory,
            "with_catalog": self.with_catalog,
        }


# ─── ExtensionSpec ────────────────────────────────────────────────


@dataclass
class DataMemberSpec:
    """Specification for a data member"""

    name: str
    type: str = "double"


@dataclass
class ExtensionSpec(Spec):
    """Specification for a data extension"""

    module: str = ""
    framework: str = ""
    target_object: str = ""  # e.g., "CATPart"
    data_members: List[DataMemberSpec] = field(default_factory=list)
    implements: List[str] = field(default_factory=list)

    def validate(self) -> dict:
        if not self.name:
            return {"status": "error", "message": "Extension name is required"}
        if not self.target_object:
            return {"status": "error", "message": "target_object is required"}
        return {"status": "ok"}

    def _fields_dict(self) -> dict:
        return {
            "module": self.module,
            "framework": self.framework,
            "target_object": self.target_object,
            "data_members": [
                {"name": d.name, "type": d.type} for d in self.data_members
            ],
            "implements": self.implements,
        }


# ─── WorkbenchSpec ────────────────────────────────────────────────


@dataclass
class WorkbenchSpec(Spec):
    """Specification for a CATIA Workbench"""

    module: str = ""
    framework: str = ""
    commands: List[str] = field(default_factory=list)  # command names to include
    icon: Optional[str] = None

    def validate(self) -> dict:
        if not self.name:
            return {"status": "error", "message": "Workbench name is required"}
        return {"status": "ok"}

    def _fields_dict(self) -> dict:
        return {
            "module": self.module,
            "framework": self.framework,
            "commands": self.commands,
        }


# ─── Helpers ─────────────────────────────────────────────────────


def spec_from_dict(d: dict) -> Spec:
    """Reconstruct a Spec from a dict (API deserialization)"""

    # Strip internal fields not used by constructors
    def _clean(dd: dict) -> dict:
        return {k: v for k, v in dd.items() if k not in ("type", "metadata")}

    spec_type = d.get("type", "")
    name = d.get("name", "")

    if spec_type == "CommandSpec":
        dialog = None
        if d.get("dialog"):
            dd = _clean(d["dialog"])
            dialog = DialogSpec(**dd)
        return CommandSpec(
            name=name,
            module=d.get("module", ""),
            framework=d.get("framework", ""),
            stateful=d.get("stateful", False),
            visibility=d.get("visibility", "always"),
            category=d.get("category", "General"),
            tooltip=d.get("tooltip"),
            icon=d.get("icon"),
            dialog=dialog,
            workbench=d.get("workbench"),
            metadata=d.get("metadata", {}),
        )

    if spec_type == "DialogSpec":
        return DialogSpec(**_clean(d))

    if spec_type == "InterfaceSpec":
        methods = [
            MethodSpec(
                name=m["name"],
                params=m.get("params", []),
                return_type=m.get("return_type", "HRESULT"),
            )
            for m in d.get("methods", [])
        ]
        return InterfaceSpec(
            name=name,
            module=d.get("module", ""),
            framework=d.get("framework", ""),
            methods=methods,
            use_idl=d.get("use_idl", True),
            generate_tie=d.get("generate_tie", True),
            metadata=d.get("metadata", {}),
        )

    if spec_type == "FeatureSpec":
        attrs = [
            AttributeSpec(
                name=a["name"], type=a.get("type", ""), default=a.get("default", "")
            )
            for a in d.get("attributes", [])
        ]
        return FeatureSpec(
            name=name,
            module=d.get("module", ""),
            framework=d.get("framework", ""),
            attributes=attrs,
            with_factory=d.get("with_factory", True),
            with_catalog=d.get("with_catalog", True),
            parent_feature=d.get("parent_feature"),
            metadata=d.get("metadata", {}),
        )

    if spec_type == "ExtensionSpec":
        members = [
            DataMemberSpec(
                name=m["name"], type=m.get("data_type", m.get("type", "double"))
            )
            for m in d.get("data_members", [])
        ]
        return ExtensionSpec(
            name=name,
            module=d.get("module", ""),
            framework=d.get("framework", ""),
            target_object=d.get("target_object", ""),
            data_members=members,
            implements=d.get("implements", []),
            metadata=d.get("metadata", {}),
        )

    if spec_type == "ComponentSpec":
        return ComponentSpec(
            name=name,
            module=d.get("module", ""),
            framework=d.get("framework", ""),
            implements=d.get("implements", []),
            use_tie=d.get("use_tie", True),
            generate_skeleton=d.get("generate_skeleton", True),
            parent_class=d.get("parent_class", "CATBaseUnknown"),
            metadata=d.get("metadata", {}),
        )

    if spec_type == "WorkbenchSpec":
        return WorkbenchSpec(
            name=name,
            module=d.get("module", ""),
            framework=d.get("framework", ""),
            commands=d.get("commands", []),
            icon=d.get("icon"),
            metadata=d.get("metadata", {}),
        )

    raise ValueError(f"Unknown spec type: {spec_type}")
