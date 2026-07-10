"""
Impact Analyzer — Assess change impact before execution.
==========================================================
Uses DependencyGraph to determine blast radius of modifications.

P1: Layer on top of existing DependencyGraph + get_dependents().
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from intent.models import ImpactReport, Severity

# File patterns affected by each entity type
_AFFECTED_PATTERNS = {
    "command": [
        "src/{name}.cpp", "LocalInterfaces/{name}.h",
        "src/{name}Header.cpp",
        "CNext/resources/msgcatalog/*.CATNls",
        "CNext/code/dictionary/*.dico",
    ],
    "interface": [
        "PublicInterfaces/{name}.h",
        "src/{name}.cpp",
        "*.idl",
        "src/*.cpp",  # All components implementing this interface
    ],
    "module": [
        "{name}/**",
        "Imakefile.mk",
    ],
    "dialog": [
        "LocalInterfaces/{name}.h",
        "src/{name}.cpp",
    ],
    "feature": [
        "LocalInterfaces/{name}*.h",
        "src/{name}*.cpp",
    ],
}

# Severity by operation type
_OPERATION_SEVERITY = {
    "rename": Severity.LOW,
    "move": Severity.MEDIUM,
    "modify_interface": Severity.HIGH,
    "delete": Severity.CRITICAL if None else Severity.HIGH,
    "create": Severity.NONE,
}


def analyze(entity_name: str, entity_type: str = None,
            ctx: Any = None, operation: str = "rename") -> ImpactReport:
    """
    Analyze the impact of changing/deleting/moving an entity.

    Args:
        entity_name: e.g., "MyCmd", "IMyInterface"
        entity_type: "command" | "interface" | "module" | "dialog" | "feature"
        ctx: ActionContext (optional, for dependency lookup)
        operation: "rename" | "move" | "modify_interface" | "delete" | "create"

    Returns:
        ImpactReport with severity, affected files, breaking changes
    """
    report = ImpactReport(
        entity=entity_name,
        severity=_analyze_severity(entity_type, operation),
    )

    # Files directly affected by entity type
    if entity_type in _AFFECTED_PATTERNS:
        for pattern in _AFFECTED_PATTERNS[entity_type]:
            report.affected_files.append(
                pattern.replace("{name}", entity_name)
            )

    # Dependency analysis via ActionContext
    if ctx and hasattr(ctx, "snapshot"):
        try:
            deps = _get_dependents_light(ctx, entity_name, entity_type)
            if deps:
                report.affected_modules = list(set(deps.get("modules", [])))
                report.affected_interfaces = list(set(deps.get("interfaces", [])))
                report.breaking_changes = len(report.affected_interfaces) > 0
        except Exception:
            pass

    # Always generate recommendations (empty context = no deps, still useful)
    report.recommendations = _generate_recommendations(
        entity_type, operation, report
    )

    return report


def analyze_batch(changes: List[Dict], ctx: Any = None) -> List[ImpactReport]:
    """Analyze impact for multiple changes."""
    reports = []
    for change in changes:
        reports.append(analyze(
            entity_name=change.get("name", ""),
            entity_type=change.get("type"),
            ctx=ctx,
            operation=change.get("operation", "rename"),
        ))
    return reports


# ─── Helpers ────────────────────────────────────────────────────

def _analyze_severity(entity_type: str, operation: str) -> Severity:
    """Determine severity from entity type and operation."""
    base = _OPERATION_SEVERITY.get(operation, Severity.LOW)

    # Entity-specific escalations
    if entity_type == "interface":
        # Modifying public interfaces is always more severe
        if operation in ("modify_interface", "delete", "move", "rename"):
            return Severity.CRITICAL
    if entity_type == "module":
        if operation in ("delete", "rename"):
            return Severity.CRITICAL

    return base


def _get_dependents_light(ctx: Any, entity_name: str, entity_type: str) -> dict:
    """Lightweight dependency lookup without full entity serialization."""
    result = {"modules": [], "interfaces": [], "commands": []}

    if not hasattr(ctx.snapshot, "dependency_graph") or not ctx.snapshot.dependency_graph:
        return result

    dg = ctx.snapshot.dependency_graph
    entity_id = f"{entity_type}:{entity_name}" if entity_type else entity_name

    for rel in dg.relationships:
        if rel.target.name == entity_name or str(rel.target) == entity_id:
            source = rel.source
            if hasattr(source, "module") and source.module:
                result["modules"].append(source.module.name)
            if hasattr(source, "name"):
                t = type(source).__name__.lower()
                if "interface" in t:
                    result["interfaces"].append(source.name)
                elif "command" in t:
                    result["commands"].append(source.name)

    return result


def _generate_recommendations(entity_type: str, operation: str,
                               report: ImpactReport) -> List[str]:
    """Generate actionable recommendations based on impact analysis."""
    recs = []

    if report.breaking_changes:
        recs.append("!! BREAKING: interfaces affected - update all implementations")

    if report.severity in (Severity.HIGH, Severity.CRITICAL):
        recs.append("[!] Create snapshot before proceeding (cade snapshot)")

    if entity_type == "interface" and operation in ("modify_interface", "delete"):
        recs.append("[>] Run cade diagnose after changes to catch broken refs")

    if entity_type == "module" and operation == "delete":
        recs.append("!! Deleting module - verify no other frameworks depend on it")

    if not recs:
        recs.append("OK Low risk - proceed normally")

    return recs
