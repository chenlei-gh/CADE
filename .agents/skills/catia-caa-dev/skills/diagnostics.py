"""
CATIA CAA Diagnostics System
==============================
Problem detection + structured FixPlan generation.

Design principle:
  Diagnostics finds what's wrong, WHY it's wrong, and HOW to fix it.
  FixPlan is machine-executable — Development Engine can apply fixes automatically.

Diagnostic categories:
  - Dictionary: missing entries, wrong types, unregistered components
  - Catalog/NLS: missing titles, tips, help entries
  - IdentityCard: missing, malformed
  - Imakefile: missing SOURCES, wrong paths
  - Naming: I-prefix violations, duplicate names
  - Integrity: missing header/source, orphaned files
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from meta_model import (
    Command,
    Framework,
    Module,
    WorkspaceSnapshot,
)

# ─── FixPlan ──────────────────────────────────────────────────────


class FixAction(Enum):
    INSERT_LINE = "insert_line"  # Insert a line into a file
    APPEND_LINE = "append_line"  # Append a line to end of file
    DELETE_LINE = "delete_line"  # Remove a specific line
    REPLACE_LINE = "replace_line"  # Replace a line
    CREATE_FILE = "create_file"  # Create a new file
    DELETE_FILE = "delete_file"  # Remove a file
    RENAME = "rename"  # Rename a file or entity
    REGENERATE = "regenerate"  # Re-run generation
    MANUAL = "manual"  # Requires manual edit (e.g. IdentityCard prerequisite)


@dataclass
class FixPlan:
    """A machine-executable plan to fix a diagnostic issue"""

    action: FixAction
    file: str  # Target file path
    line: Optional[str] = None  # Line content (for insert/append/replace)
    after_line: Optional[str] = None  # Insert after this line (for insert)
    delete_target: Optional[str] = None  # Line to delete/replace
    entity_name: Optional[str] = None  # Related entity name
    description: str = ""  # Human-readable description

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "file": self.file,
            "line": self.line,
            "after_line": self.after_line,
            "delete_target": self.delete_target,
            "entity_name": self.entity_name,
            "description": self.description,
        }


# ─── Diagnostic ───────────────────────────────────────────────────


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Diagnostic:
    """A single diagnostic finding with optional FixPlan"""

    severity: Severity
    problem: str
    reason: str
    fix_plan: Optional[FixPlan] = None
    auto_fixable: bool = False
    entity: Optional[str] = None
    category: str = "general"

    def to_dict(self) -> dict:
        d = {
            "severity": self.severity.value,
            "problem": self.problem,
            "reason": self.reason,
            "auto_fixable": self.auto_fixable,
            "entity": self.entity,
            "category": self.category,
        }
        if self.fix_plan:
            d["fix_plan"] = self.fix_plan.to_dict()
        return d


# ─── Diagnostics Engine ───────────────────────────────────────────


class DiagnosticsEngine:
    """
    Runs all diagnostic checks against a workspace snapshot.
    Returns structured Diagnostic objects with FixPlans.
    """

    def __init__(self, snapshot: WorkspaceSnapshot):
        self.snapshot = snapshot
        self.diagnostics: List[Diagnostic] = []

    def run_all(self) -> List[Diagnostic]:
        """Run all diagnostic checks"""
        self.diagnostics = []
        self._check_dictionary()
        self._check_catalog_nls()
        self._check_imakefile()
        self._check_link_with_coverage()
        self._check_naming()
        self._check_integrity()
        self._check_unsupported_generated_apis()
        self._check_ui_failure_patterns()
        self._check_orphaned()
        return self.diagnostics

    def summary(self) -> dict:
        errors = [d for d in self.diagnostics if d.severity == Severity.ERROR]
        warnings = [d for d in self.diagnostics if d.severity == Severity.WARNING]
        auto_fixable = [d for d in self.diagnostics if d.auto_fixable]

        return {
            "total": len(self.diagnostics),
            "errors": len(errors),
            "warnings": len(warnings),
            "auto_fixable": len(auto_fixable),
            "by_category": self._by_category(),
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }

    def _by_category(self) -> dict:
        cats = {}
        for d in self.diagnostics:
            cats[d.category] = cats.get(d.category, 0) + 1
        return cats

    # ── Checks ──────────────────────────────────────────────────

    def _check_dictionary(self):
        """Check Dictionary (.dico) for missing/incorrect entries"""
        for fw in self.snapshot.frameworks:
            dico = fw.dictionary_path()
            if not dico.exists():
                self.diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        problem=f"Dictionary missing: {dico.name}",
                        reason="Dictionary file does not exist — no components can be registered",
                        category="dictionary",
                        entity=fw.name,
                        fix_plan=FixPlan(
                            action=FixAction.CREATE_FILE,
                            file=str(dico),
                            description="Create empty dictionary file",
                        ),
                        auto_fixable=True,
                    )
                )
                continue

            dico_content = dico.read_text(encoding="utf-8", errors="replace")

            # Command headers are registered by the module addin. Individual
            # commands must not be emitted as CATIAfrGeneralWksAddin entries;
            # doing so creates invalid duplicate registrations.

    def _check_catalog_nls(self):
        """Check NLS catalog for missing entries"""
        for fw in self.snapshot.frameworks:
            nls_file = fw.catalog_path()
            if not nls_file.exists():
                self.diagnostics.append(
                    Diagnostic(
                        severity=Severity.WARNING,
                        problem=f"NLS catalog missing: {nls_file.name}",
                        reason="No NLS catalog — commands will have no display text",
                        category="nls",
                        entity=fw.name,
                        fix_plan=FixPlan(
                            action=FixAction.CREATE_FILE,
                            file=str(nls_file),
                            description="Create NLS catalog file",
                        ),
                        auto_fixable=True,
                    )
                )
                continue

            nls_content = nls_file.read_text(encoding="utf-8", errors="replace")

            for mod in fw.modules:
                for cmd in mod.commands:
                    if f"{cmd.name}.Title" not in nls_content:
                        self.diagnostics.append(
                            Diagnostic(
                                severity=Severity.WARNING,
                                problem=f"NLS title missing for {cmd.name}",
                                reason=f"No display title for {cmd.name} in {nls_file.name}",
                                category="nls",
                                entity=cmd.name,
                                fix_plan=FixPlan(
                                    action=FixAction.APPEND_LINE,
                                    file=str(nls_file),
                                    line=cmd.nls_block(),
                                    entity_name=cmd.name,
                                    description=f"Add NLS entries for {cmd.name}",
                                ),
                                auto_fixable=True,
                            )
                        )

    def _check_imakefile(self):
        """Check Imakefile.mk for completeness and framework/module confusion."""
        try:
            from header_map import HeaderMap
            hm = HeaderMap.load(Path(__file__).resolve().parent.parent)
        except Exception:
            hm = None

        for fw in self.snapshot.frameworks:
            for mod in fw.modules:
                imake = mod.imakefile_path()
                if not imake.exists():
                    self.diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            problem=f"Imakefile missing: {mod.name}",
                            reason=f"No Imakefile.mk in {mod.name} — cannot compile",
                            category="imakefile",
                            entity=mod.name,
                            auto_fixable=False,
                        )
                    )
                    continue

                # CAA mkmk discovers C++ sources in the module src directory.
                # A SOURCES variable is not required and is absent from valid
                # B28 wizard-generated modules.

                # Check LINK_WITH entries: framework name vs module name
                if hm:
                    try:
                        content = imake.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue
                    for m in re.finditer(r'LINK_WITH\s*[=+]?\s*(.+)', content):
                        entries = m.group(1).replace('\\', ' ').split()
                        for entry in entries:
                            entry = entry.strip().strip('$()')
                            if not entry or entry.startswith('#'):
                                continue
                            # Skip variable references
                            if entry.startswith('$'):
                                continue
                            # Flag if a framework name was used where a
                            # module name is expected (error #3 pattern)
                            if hm.is_framework_only(entry):
                                fw_name = entry
                                mods_in_fw = [m for m in hm._frameworks.get(fw_name, [])
                                             if m != fw_name]
                                self.diagnostics.append(
                                    Diagnostic(
                                        severity=Severity.ERROR,
                                        problem=(
                                            f"LINK_WITH has framework name '{entry}' "
                                            f"instead of module name"
                                        ),
                                        reason=(
                                            f"'{entry}' is a framework name, not a "
                                            "module name. mkmk LINK_WITH requires "
                                            "module names. Modules in this framework: "
                                            f"{', '.join(mods_in_fw[:5]) if mods_in_fw else 'see CATIA install}'}."
                                        ),
                                        category="imakefile",
                                        entity=mod.name,
                                        auto_fixable=False,
                                    )
                                )

    def _check_link_with_coverage(self):
        """Check that #include headers have their framework declared as
        prerequisite in IdentityCard.xml and linked in LINK_WITH.

        This catches:
        - Error #2: header included but LINK_WITH missing (LNK2019)
        - Error #4: LINK_WITH module in non-prerequisite framework (ignored)
        """
        try:
            from header_map import HeaderMap
            # Build the header map from the skill root
            skill_root = Path(__file__).resolve().parent.parent
            hm = HeaderMap.load(skill_root)
        except Exception:
            return
        if not hm._loaded or hm.header_count == 0:
            return  # CATIA not installed or scan failed

        # Frameworks always available via CATIAV5Level (don't require prereq)
        try:
            from header_map import _ALWAYS_AVAILABLE as always_available
        except ImportError:
            always_available = {"System", "ObjectModelerBase", "ApplicationFrame",
                               "DialogEngine", "InteractiveInterfaces"}

        for fw in self.snapshot.frameworks:
            # Parse IdentityCard prerequisites
            prereqs = set()
            ic_path = fw.identitycard_path()
            if ic_path.exists():
                try:
                    ic_content = ic_path.read_text(encoding="utf-8", errors="replace")
                    for m in re.finditer(r'<prerequisite\s+name="([^"]+)"', ic_content):
                        prereqs.add(m.group(1))
                    # Also parse AddPrereqComponent (IdentityCard.h style)
                    for m in re.finditer(r'AddPrereqComponent\("([^"]+)"', ic_content):
                        prereqs.add(m.group(1))
                except OSError:
                    pass

            for mod in fw.modules:
                # Collect all #includes from source files
                includes = set()
                source_dirs = [mod.path / "src", mod.path / "LocalInterfaces",
                               mod.path / "PublicInterfaces"]
                for src_dir in source_dirs:
                    if not src_dir.exists():
                        continue
                    for path in src_dir.rglob("*"):
                        if not path.is_file() or path.suffix.lower() not in (".h", ".cpp"):
                            continue
                        try:
                            content = path.read_text(encoding="utf-8", errors="replace")
                        except OSError:
                            continue
                        for m in re.finditer(r'#include\s+[<"]([^>"/]+\.h)[>"]', content):
                            stem = m.group(1).replace(".h", "")
                            if stem.startswith("CAT"):
                                includes.add(stem)

                if not includes:
                    continue

                # Read LINK_WITH from Imakefile
                link_with = set()
                imake_path = mod.imakefile_path()
                if imake_path.exists():
                    try:
                        imake = imake_path.read_text(encoding="utf-8", errors="replace")
                        for m in re.finditer(r'LINK_WITH\s*[=+]?\s*(.+)', imake):
                            for e in m.group(1).replace('\\', ' ').split():
                                e = e.strip().strip('$()')
                                if e and not e.startswith('#') and not e.startswith('$'):
                                    link_with.add(e)
                    except OSError:
                        pass

                # Check each included header's framework
                missing_prereqs = {}  # fw_name → [header stems]
                for stem in sorted(includes):
                    entry = hm.lookup(stem)
                    if not entry:
                        continue  # not a known CAA header
                    module_name, fw_name = entry
                    if fw_name in always_available:
                        continue
                    if fw_name in prereqs:
                        continue  # already declared
                    missing_prereqs.setdefault(fw_name, []).append(stem)

                for fw_name, stems in missing_prereqs.items():
                    self.diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            problem=(
                                f"Missing prerequisite: '{fw_name}' not declared "
                                f"in IdentityCard.xml"
                            ),
                            reason=(
                                f"Source files include headers from framework "
                                f"'{fw_name}' ({', '.join(stems[:3])}"
                                f"{'...' if len(stems) > 3 else ''}) but "
                                f"'{fw_name}' is not declared as a prerequisite "
                                "in IdentityCard.xml. mkmk will IGNORE modules "
                                "from this framework in LINK_WITH (silent ignore, "
                                "not an error), causing LNK2019 unresolved symbols."
                            ),
                            category="imakefile",
                            entity=fw.name,
                            fix_plan=FixPlan(
                                action=FixAction.MANUAL,
                                file=str(ic_path),
                                entity_name=fw_name,
                                description=(
                                    f"Add <prerequisite name=\"{fw_name}\" "
                                    f"access=\"Protected\" /> to IdentityCard.xml"
                                ),
                            ),
                            auto_fixable=False,
                        )
                    )

    def _check_naming(self):
        """Check CAA naming conventions"""
        for fw in self.snapshot.frameworks:
            for mod in fw.modules:
                # Interface naming: must start with I
                for iface in mod.interfaces:
                    if not iface.name.startswith("I"):
                        self.diagnostics.append(
                            Diagnostic(
                                severity=Severity.WARNING,
                                problem=f"Interface naming: {iface.name}",
                                reason=f"Interface '{iface.name}' should start with 'I' (convention)",
                                category="naming",
                                entity=iface.name,
                                fix_plan=FixPlan(
                                    action=FixAction.RENAME,
                                    file="",
                                    entity_name=iface.name,
                                    line=f"I{iface.name}",
                                    description=f"Rename to I{iface.name}",
                                ),
                                auto_fixable=False,  # Rename requires refactor
                            )
                        )

                # Check for duplicate names
                names = [c.name.lower() for c in mod.commands]
                dups = {n for n in names if names.count(n) > 1}
                for dup in dups:
                    self.diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            problem=f"Duplicate command: {dup}",
                            reason=f"Multiple commands named '{dup}' in {mod.name}",
                            category="naming",
                            entity=dup,
                            auto_fixable=False,
                        )
                    )

    def _check_integrity(self):
        """Check entity integrity — missing files, broken references"""
        for fw in self.snapshot.frameworks:
            # IdentityCard
            ic = fw.identitycard_path()
            if not ic.exists():
                self.diagnostics.append(
                    Diagnostic(
                        severity=Severity.WARNING,
                        problem=f"IdentityCard missing for {fw.name}",
                        reason="No IdentityCard.xml (or .h) — Framework identity is not defined",
                        category="integrity",
                        entity=fw.name,
                        fix_plan=FixPlan(
                            action=FixAction.CREATE_FILE,
                            file=str(ic),
                            line=f"<?xml version=\"1.0\"?>\n<eduFramework ...>",
                            description=f"Create IdentityCard for {fw.name}",
                        ),
                        auto_fixable=True,
                    )
                )

            for mod in fw.modules:
                for cmd in mod.commands:
                    # Check header
                    hp = cmd.header_path()
                    if hp and not hp.exists():
                        self.diagnostics.append(
                            Diagnostic(
                                severity=Severity.ERROR,
                                problem=f"Header missing: {cmd.name}.h",
                                reason=f"Command '{cmd.name}' references {hp} which does not exist",
                                category="integrity",
                                entity=cmd.name,
                                fix_plan=FixPlan(
                                    action=FixAction.REGENERATE,
                                    file="",
                                    entity_name=cmd.name,
                                    description=f"Regenerate {cmd.name}",
                                ),
                                auto_fixable=False,
                            )
                        )

                    # Check source
                    sp = cmd.source_path()
                    if sp and not sp.exists():
                        self.diagnostics.append(
                            Diagnostic(
                                severity=Severity.ERROR,
                                problem=f"Source missing: {cmd.name}.cpp",
                                reason=f"Command '{cmd.name}' references {sp} which does not exist",
                                category="integrity",
                                entity=cmd.name,
                                fix_plan=FixPlan(
                                    action=FixAction.REGENERATE,
                                    file="",
                                    entity_name=cmd.name,
                                    description=f"Regenerate {cmd.name}",
                                ),
                                auto_fixable=False,
                            )
                        )

                # Dialog integrity
                for dlg in mod.dialogs:
                    hp = dlg.header_path()
                    if hp and not hp.exists():
                        self.diagnostics.append(
                            Diagnostic(
                                severity=Severity.WARNING,
                                problem=f"Dialog header missing: {dlg.name}.h",
                                reason=f"Dialog '{dlg.name}' header not found",
                                category="integrity",
                                entity=dlg.name,
                                auto_fixable=False,
                            )
                        )

    def _check_unsupported_generated_apis(self):
        """Detect generated C++ patterns known to be invalid for supported CATIA releases."""
        invalid_patterns = (
            (
                "CATTestCase.h",
                "Unsupported CATTestCase API",
                "CATTestCase.h is not available in B28; regenerate the test fixture with the current template",
            ),
            (
                "CATBeginTestSuite(",
                "Unsupported CAT test-suite macros",
                "CATBeginTestSuite/CATAddTest are not available in B28; regenerate the test fixture with the current template",
            ),
            (
                "CATImplementHeaderResources(",
                "CommandHeader class is not declared",
                "CATImplementHeaderResources does not declare the header class; use MacDeclareHeader in the addin .cpp",
            ),
        )
        for fw in self.snapshot.frameworks:
            for mod in fw.modules:
                source_dirs = [mod.path / "src", mod.path / "LocalInterfaces", mod.path / "PublicInterfaces"]
                for source_dir in source_dirs:
                    if not source_dir.exists():
                        continue
                    for path in source_dir.rglob("*"):
                        if not path.is_file() or path.suffix.lower() not in (".h", ".cpp"):
                            continue
                        content = path.read_text(encoding="utf-8", errors="replace")
                        for marker, problem, reason in invalid_patterns:
                            if marker in content:
                                self.diagnostics.append(
                                    Diagnostic(
                                        severity=Severity.ERROR,
                                        problem=f"{problem}: {path.name}",
                                        reason=reason,
                                        category="compile_contract",
                                        entity=path.stem,
                                        fix_plan=FixPlan(
                                            action=FixAction.REGENERATE,
                                            file=str(path),
                                            entity_name=path.stem,
                                            description="Regenerate this file using supported CADE templates",
                                        ),
                                        auto_fixable=False,
                                    )
                                )

    def _check_ui_failure_patterns(self):
        """Detect the documented UI failure patterns (dialog/toolbar).

        These are the three silent-runtime-failure bugs recorded in
        knowledge/failure_patterns/fp_*.md, originally diagnosed by hand
        with debug_tools/ against a live CATIA. Static detection here
        means repair() can surface them before any mkmk/launch cycle.
        Not auto-fixable (rewriting command lifecycle logic needs human
        review), but each diagnostic carries the exact fix guidance.
        """
        try:
            from ui_lint import UILinter
        except ImportError:
            return
        linter = UILinter()
        for fw in self.snapshot.frameworks:
            for mod in fw.modules:
                for finding in linter.lint_module(mod.path):
                    self.diagnostics.append(
                        Diagnostic(
                            severity=(Severity.ERROR if finding.severity == "error"
                                      else Severity.WARNING),
                            problem=f"{finding.problem} ({Path(finding.file).name}:{finding.line})",
                            reason=f"{finding.reason} Fix: {finding.fix_hint} "
                                   f"See {finding.knowledge_ref}.",
                            category="ui_pattern",
                            entity=Path(finding.file).stem,
                            auto_fixable=False,
                        )
                    )

    def _check_orphaned(self):
        """Check for orphaned files"""
        if self.snapshot.orphaned_files:
            for f in self.snapshot.orphaned_files:
                self.diagnostics.append(
                    Diagnostic(
                        severity=Severity.WARNING,
                        problem=f"Orphaned file: {f.name}",
                        reason=f"{f} exists but is not referenced by any entity",
                        category="integrity",
                        fix_plan=FixPlan(
                            action=FixAction.DELETE_FILE,
                            file=str(f),
                            description=f"Remove orphaned file {f.name}",
                        ),
                        auto_fixable=True,
                    )
                )


# ─── Convenience Function ────────────────────────────────────────


def diagnose_workspace(ctx) -> dict:
    """
    Run full diagnostics on a workspace and return structured results.

    Args:
        ctx: ActionContext with valid snapshot

    Returns:
        {
            "status": "ok",
            "summary": {"total": 5, "errors": 2, "warnings": 3, "auto_fixable": 4},
            "diagnostics": [...]
        }
    """
    ctx.refresh()
    engine = DiagnosticsEngine(ctx.snapshot)
    engine.run_all()
    summary = engine.summary()
    summary["status"] = "ok"
    return summary


# ─── FixPlan Executor ────────────────────────────────────────────


def apply_fixplan(fix_plan: FixPlan, workspace_root: Path) -> dict:
    """
    Execute a single FixPlan against the filesystem.

    Returns a ChangeSet for preview; use .apply() to commit.

    Args:
        fix_plan: The FixPlan to execute
        workspace_root: Root of the CAA workspace

    Returns:
        {"status": "success", "changeset": {...}, "message": "..."}
    """
    from changeset import ChangeSet

    cs = ChangeSet(
        action=f"fixplan:{fix_plan.action.value}",
        description=fix_plan.description or f"Apply fix: {fix_plan.action.value}",
    )

    file_path = Path(fix_plan.file)
    if not file_path.is_absolute():
        file_path = workspace_root / file_path

    try:
        if fix_plan.action == FixAction.CREATE_FILE:
            content = fix_plan.line or ""
            cs.add_create(str(file_path), content)

        elif fix_plan.action == FixAction.DELETE_FILE:
            if file_path.exists():
                cs.add_delete(file_path)

        elif fix_plan.action == FixAction.APPEND_LINE:
            if file_path.exists() and fix_plan.line:
                old = file_path.read_text(encoding="utf-8", errors="replace")
                new = old.rstrip("\n") + "\n" + fix_plan.line + "\n"
                cs.add_modify(str(file_path), new)
            else:
                return {
                    "status": "error",
                    "message": f"Cannot append: {file_path} not found",
                }

        elif fix_plan.action == FixAction.INSERT_LINE:
            if file_path.exists() and fix_plan.line and fix_plan.after_line:
                old = file_path.read_text(encoding="utf-8", errors="replace")
                lines = old.split("\n")
                inserted = False
                new_lines = []
                for line in lines:
                    new_lines.append(line)
                    if fix_plan.after_line in line and not inserted:
                        new_lines.append(fix_plan.line)
                        inserted = True
                new = "\n".join(new_lines)
                cs.add_modify(str(file_path), new)
            else:
                return {
                    "status": "error",
                    "message": "INSERT_LINE requires line and after_line",
                }

        elif fix_plan.action == FixAction.DELETE_LINE:
            if file_path.exists() and fix_plan.delete_target:
                old = file_path.read_text(encoding="utf-8", errors="replace")
                new = "\n".join(
                    [l for l in old.split("\n") if fix_plan.delete_target not in l]
                )
                if new != old:
                    cs.add_modify(str(file_path), new)

        elif fix_plan.action == FixAction.REPLACE_LINE:
            if file_path.exists() and fix_plan.delete_target and fix_plan.line:
                old = file_path.read_text(encoding="utf-8", errors="replace")
                new = old.replace(fix_plan.delete_target, fix_plan.line)
                if new != old:
                    cs.add_modify(str(file_path), new)

        elif fix_plan.action == FixAction.RENAME:
            # File rename: delete old, create new with same content
            if file_path.exists() and fix_plan.line:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                new_content = content.replace(
                    fix_plan.entity_name or "", fix_plan.line or ""
                )
                new_path = file_path.parent / (
                    file_path.name.replace(
                        fix_plan.entity_name or "", fix_plan.line or ""
                    )
                )
                cs.add_delete(file_path)
                cs.add_create(str(new_path), new_content)

        elif fix_plan.action == FixAction.REGENERATE:
            # Mark for regeneration — actual regen happens at a higher level
            cs.metadata["needs_regeneration"] = fix_plan.entity_name
            return {
                "status": "pending_regeneration",
                "message": f"Entity '{fix_plan.entity_name}' needs regeneration",
                "changeset": cs.to_dict(),
            }

        else:
            return {"status": "error", "message": f"Unknown action: {fix_plan.action}"}

    except Exception as e:
        return {"status": "error", "message": f"FixPlan execution failed: {e}"}

    return {
        "status": "ok",
        "message": f"FixPlan ready: {fix_plan.description}",
        "changeset": cs.to_dict(),
        "preview": cs.preview(),
        "action": fix_plan.action.value,
        "file": str(file_path),
    }


def apply_all_fixplans(ctx, auto_only: bool = True) -> dict:
    """
    Run diagnostics, then generate a merged ChangeSet for all auto-fixable issues.

    Args:
        ctx: ActionContext with valid snapshot
        auto_only: If True, only apply auto-fixable plans

    Returns:
        {"status": "ok", "diagnostics_summary": {...}, "changeset": {...}}
    """
    from changeset import ChangeSet

    # Run diagnostics
    diag_result = diagnose_workspace(ctx)
    diagnostics = diag_result.get("diagnostics", [])

    # Filter
    if auto_only:
        to_fix = [d for d in diagnostics if d.get("auto_fixable") and "fix_plan" in d]
    else:
        to_fix = [d for d in diagnostics if "fix_plan" in d]

    if not to_fix:
        return {
            "status": "ok",
            "message": "No fixable issues found",
            "applied": 0,
            "skipped": len(diagnostics),
            "changeset": None,
            "details": [],
        }

    # Execute all FixPlans, merging into one ChangeSet
    master_cs = ChangeSet(
        action="apply_all_fixplans",
        description=f"Apply {len(to_fix)} automatic fixes",
    )

    applied = 0
    skipped = 0
    details = []

    for diag in to_fix:
        fp_dict = diag.get("fix_plan", {})
        try:
            fp = FixPlan(
                action=FixAction(fp_dict["action"]),
                file=fp_dict.get("file", ""),
                line=fp_dict.get("line"),
                after_line=fp_dict.get("after_line"),
                delete_target=fp_dict.get("delete_target"),
                entity_name=fp_dict.get("entity_name"),
                description=fp_dict.get("description", ""),
            )
            result = apply_fixplan(fp, ctx.workspace_root)

            if result["status"] == "ok":
                # Merge into master
                sub_cs = ChangeSet.from_dict(result["changeset"])
                for k, v in sub_cs.created.items():
                    master_cs.created[k] = v
                for k, v in sub_cs.modified.items():
                    master_cs.modified[k] = v
                master_cs.deleted.extend(sub_cs.deleted)
                applied += 1
                details.append(
                    {
                        "problem": diag.get("problem", ""),
                        "status": "applied",
                    }
                )
            else:
                skipped += 1
                details.append(
                    {
                        "problem": diag.get("problem", ""),
                        "status": result["status"],
                        "message": result.get("message", ""),
                    }
                )
        except Exception as e:
            skipped += 1
            details.append(
                {
                    "problem": diag.get("problem", ""),
                    "status": "error",
                    "message": str(e),
                }
            )

    return {
        "status": "ok",
        "message": f"Applied {applied} fixes, skipped {skipped}",
        "applied": applied,
        "skipped": skipped,
        "total_diagnostics": len(diagnostics),
        "diagnostics_summary": {
            "total": diag_result.get("total", 0),
            "errors": diag_result.get("errors", 0),
            "warnings": diag_result.get("warnings", 0),
            "auto_fixable": diag_result.get("auto_fixable", 0),
        },
        "changeset": master_cs.to_dict(),
        "preview": master_cs.preview(),
        "details": details,
    }


def diagnose_and_fix(ctx, auto_only: bool = True, dry_run: bool = True) -> dict:
    """
    One-shot: diagnose workspace and apply all auto-fixable fixes.

    Args:
        ctx: ActionContext
        auto_only: Only apply auto-fixable fixes
        dry_run: If True, preview only (don't write files)

    Returns:
        {"status": "ok", "diagnostics": {...}, "fixes": {...}}
    """
    ctx.refresh()

    # Step 1: Diagnose
    diag = diagnose_workspace(ctx)

    # Step 2: Fix
    fixes = apply_all_fixplans(ctx, auto_only=auto_only)

    # Step 3: Optionally apply
    if not dry_run and fixes.get("changeset"):
        from changeset import ChangeSet

        cs = ChangeSet.from_dict(fixes["changeset"])
        apply_result = cs.apply(dry_run=False, workspace_root=ctx.workspace_root)
        fixes["apply_result"] = apply_result

    return {
        "status": "ok",
        "diagnostics": {
            "total": diag.get("total", 0),
            "errors": diag.get("errors", 0),
            "warnings": diag.get("warnings", 0),
        },
        "fixes": {
            "applied": fixes.get("applied", 0),
            "skipped": fixes.get("skipped", 0),
            "changeset_available": fixes.get("changeset") is not None,
            "dry_run": dry_run,
        },
        "changeset": fixes.get("changeset"),
        "details": fixes.get("details", []),
    }
