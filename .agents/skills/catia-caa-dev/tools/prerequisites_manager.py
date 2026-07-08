#!/usr/bin/env python3
"""
CADE Prerequisites Manager
===========================
Manage framework dependencies (AddPrereqComponent in IdentityCard.h).

This handles framework-level dependencies, NOT workspace environment.
For workspace environment setup, use tools/setup_environment.py

Features:
- Add/remove prerequisites to frameworks
- Validate dependency graph (detect circular dependencies)
- Suggest prerequisites based on code analysis
- Auto-add common prerequisites when creating frameworks
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Optional, Set

SKILL_ROOT = Path(__file__).resolve().parent.parent


# ─── Common Prerequisites Mapping ──────────────────────────────

COMMON_PREREQS = {
    "System": "Core CATIA system framework",
    "ObjectModelerBase": "Base object model (CATISpecObject, etc.)",
    "Visualization": "Visualization framework",
    "Mathematics": "Math utilities",
    "ApplicationFrame": "UI framework (CATCommand, etc.)",
    "Dialog": "UI dialogs",
    "InteractiveInterfaces": "Interactive selection",
    "ProductStructure": "Product/Assembly (CATIProduct)",
    "MechanicalModeler": "Part modeling (CATBody, CATIPart)",
    "CATPLMIntegration": "PLM integration",
    "DraftingInterfaces": "Drawing/drafting",
    "CATAnnotationInterfaces": "3D annotations",
}

# API → Framework mapping
API_TO_FRAMEWORK = {
    "CATIProduct": "ProductStructure",
    "CATProduct": "ProductStructure",
    "CATIPart": "MechanicalModeler",
    "CATPart": "MechanicalModeler",
    "CATBody": "MechanicalModeler",
    "CATFace": "MechanicalModeler",
    "CATEdge": "MechanicalModeler",
    "CATVertex": "MechanicalModeler",
    "CATISpecObject": "ObjectModelerBase",
    "CATCommand": "ApplicationFrame",
    "CATCommandHeader": "ApplicationFrame",
    "CATDialog": "Dialog",
    "CATDlgDialog": "Dialog",
    "CATPathElement": "InteractiveInterfaces",
    "CATISelect": "InteractiveInterfaces",
    "CATIDrawing": "DraftingInterfaces",
    "CATI3DAnnotation": "CATAnnotationInterfaces",
}


# ─── Core Functions ────────────────────────────────────────────


def get_identity_card_path(framework_path: Path) -> Optional[Path]:
    """Get IdentityCard.h path for a framework."""
    ic = framework_path / "IdentityCard" / "IdentityCard.h"
    return ic if ic.exists() else None


def parse_prerequisites(identity_card_path: Path) -> List[dict]:
    """
    Parse existing prerequisites from IdentityCard.h.

    Returns:
        [{"component": "System", "visibility": "Public", "line": 10}, ...]
    """
    content = identity_card_path.read_text(encoding="utf-8")
    prereqs = []

    pattern = r'AddPrereqComponent\s*\(\s*"([^"]+)"\s*,\s*(\w+)\s*\)'

    for i, line in enumerate(content.split("\n"), 1):
        match = re.search(pattern, line)
        if match:
            prereqs.append(
                {"component": match.group(1), "visibility": match.group(2), "line": i}
            )

    return prereqs


def add_prerequisite(
    framework_path: Path, component: str, visibility: str = "Public"
) -> dict:
    """
    Add a prerequisite to framework's IdentityCard.h.

    Args:
        framework_path: Path to framework (e.g., "FSCore.edu")
        component: Component name (e.g., "System")
        visibility: Public | Private | Protected

    Returns:
        {"status": "ok"|"error", "message": str}
    """
    ic_path = get_identity_card_path(framework_path)

    if not ic_path:
        return {
            "status": "error",
            "message": f"IdentityCard.h not found in {framework_path}",
        }

    # Parse existing prerequisites
    existing = parse_prerequisites(ic_path)

    # Check if already exists
    for prereq in existing:
        if prereq["component"] == component:
            if prereq["visibility"] == visibility:
                return {
                    "status": "ok",
                    "message": f"Prerequisite '{component}' already exists",
                }
            else:
                return {
                    "status": "warning",
                    "message": f"Prerequisite '{component}' exists with different visibility: {prereq['visibility']}",
                }

    # Read file content
    content = ic_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Find insertion point (after last AddPrereqComponent or after comment)
    insert_idx = None
    for i, line in enumerate(lines):
        if "AddPrereqComponent" in line:
            insert_idx = i + 1

    if insert_idx is None:
        # No existing prerequisites, find comment section
        for i, line in enumerate(lines):
            if "Prereq Components" in line or "Prerequisites" in line:
                insert_idx = i + 1
                break

    if insert_idx is None:
        return {
            "status": "error",
            "message": "Could not find insertion point in IdentityCard.h",
        }

    # Insert new prerequisite
    new_line = f'AddPrereqComponent("{component}", {visibility});'
    lines.insert(insert_idx, new_line)

    # Write back
    ic_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "status": "ok",
        "message": f"Added prerequisite: {component} ({visibility})",
    }


def remove_prerequisite(framework_path: Path, component: str) -> dict:
    """Remove a prerequisite from framework's IdentityCard.h."""
    ic_path = get_identity_card_path(framework_path)

    if not ic_path:
        return {
            "status": "error",
            "message": f"IdentityCard.h not found in {framework_path}",
        }

    content = ic_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Find and remove the line
    pattern = rf'AddPrereqComponent\s*\(\s*"{component}"\s*,\s*\w+\s*\)'
    new_lines = [line for line in lines if not re.search(pattern, line)]

    if len(new_lines) == len(lines):
        return {"status": "warning", "message": f"Prerequisite '{component}' not found"}

    ic_path.write_text("\n".join(new_lines), encoding="utf-8")

    return {"status": "ok", "message": f"Removed prerequisite: {component}"}


def list_prerequisites(framework_path: Path) -> dict:
    """List all prerequisites for a framework."""
    ic_path = get_identity_card_path(framework_path)

    if not ic_path:
        return {
            "status": "error",
            "message": f"IdentityCard.h not found in {framework_path}",
        }

    prereqs = parse_prerequisites(ic_path)

    return {
        "status": "ok",
        "framework": framework_path.name,
        "prerequisites": prereqs,
        "count": len(prereqs),
    }


def validate_prerequisites(workspace: Path) -> dict:
    """
    Validate all framework prerequisites in workspace.

    Checks:
    1. Circular dependencies
    2. Missing dependencies (referenced but not found)
    """
    import sys

    sys.path.insert(0, str(SKILL_ROOT / "skills"))
    from analyzer import WorkspaceAnalyzer

    analyzer = WorkspaceAnalyzer(workspace)
    snapshot = analyzer.analyze()

    issues = {"circular_deps": [], "missing_deps": [], "warnings": []}

    # Build dependency graph
    dep_graph = {}
    all_frameworks = set()

    for fw in snapshot.frameworks:
        fw_name = fw.name.replace(".edu", "")
        all_frameworks.add(fw_name)
        dep_graph[fw_name] = [d.replace(".edu", "") for d in fw.dependencies]

    # Check for circular dependencies using DFS
    def detect_cycle(
        node: str, visited: Set[str], rec_stack: Set[str], path: List[str]
    ) -> bool:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in dep_graph.get(node, []):
            if neighbor not in dep_graph:
                # External dependency (CATIA framework), skip
                continue

            if neighbor not in visited:
                if detect_cycle(neighbor, visited, rec_stack, path):
                    return True
            elif neighbor in rec_stack:
                # Found cycle
                cycle_start = path.index(neighbor)
                cycle = " -> ".join(path[cycle_start:] + [neighbor])
                issues["circular_deps"].append(cycle)
                return True

        path.pop()
        rec_stack.remove(node)
        return False

    visited = set()
    for fw in dep_graph:
        if fw not in visited:
            detect_cycle(fw, visited, set(), [])

    # Check for missing internal dependencies
    for fw, deps in dep_graph.items():
        for dep in deps:
            if dep not in COMMON_PREREQS and dep not in all_frameworks:
                issues["missing_deps"].append(f"{fw} requires '{dep}' (not found)")

    # Determine overall status
    if issues["circular_deps"]:
        status = "error"
    elif issues["missing_deps"]:
        status = "warning"
    else:
        status = "ok"

    return {"status": status, "issues": issues, "frameworks_count": len(all_frameworks)}


def suggest_prerequisites(module_path: Path) -> dict:
    """
    Suggest prerequisites based on code analysis.

    Scans source files for API usage and recommends frameworks.
    """
    recommendations = {}
    details = []

    # Scan all .cpp and .h files
    for source_file in module_path.rglob("*.cpp"):
        content = source_file.read_text(encoding="utf-8", errors="ignore")

        for api, framework in API_TO_FRAMEWORK.items():
            if api in content:
                if framework not in recommendations:
                    recommendations[framework] = []
                recommendations[framework].append(
                    {"file": str(source_file.relative_to(module_path)), "api": api}
                )

    for source_file in module_path.rglob("*.h"):
        content = source_file.read_text(encoding="utf-8", errors="ignore")

        for api, framework in API_TO_FRAMEWORK.items():
            if api in content:
                if framework not in recommendations:
                    recommendations[framework] = []
                recommendations[framework].append(
                    {"file": str(source_file.relative_to(module_path)), "api": api}
                )

    return {
        "status": "ok",
        "recommendations": list(recommendations.keys()),
        "details": recommendations,
    }


def add_default_prerequisites(framework_path: Path) -> dict:
    """Add default prerequisites to a new framework."""
    defaults = ["System", "ObjectModelerBase", "Visualization"]
    results = []

    for component in defaults:
        result = add_prerequisite(framework_path, component, "Public")
        results.append(result)

    return {
        "status": "ok",
        "added": [r for r in results if r["status"] == "ok"],
        "count": len([r for r in results if r["status"] == "ok"]),
    }


# ─── CLI ───────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="CADE Prerequisites Manager - Manage framework dependencies"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # cade prereq add
    add_parser = subparsers.add_parser("add", help="Add prerequisite to framework")
    add_parser.add_argument("framework", help="Framework path (e.g., FSCore.edu)")
    add_parser.add_argument("component", help="Component name (e.g., System)")
    add_parser.add_argument(
        "--visibility", default="Public", choices=["Public", "Private", "Protected"]
    )

    # cade prereq remove
    remove_parser = subparsers.add_parser("remove", help="Remove prerequisite")
    remove_parser.add_argument("framework", help="Framework path")
    remove_parser.add_argument("component", help="Component name")

    # cade prereq list
    list_parser = subparsers.add_parser("list", help="List prerequisites")
    list_parser.add_argument("framework", help="Framework path")

    # cade prereq validate
    validate_parser = subparsers.add_parser("validate", help="Validate dependencies")
    validate_parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Workspace path (default: current directory)",
    )

    # cade prereq suggest
    suggest_parser = subparsers.add_parser("suggest", help="Suggest prerequisites")
    suggest_parser.add_argument("module", help="Module path")

    # cade prereq init
    init_parser = subparsers.add_parser("init", help="Add default prerequisites")
    init_parser.add_argument("framework", help="Framework path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Execute command
    if args.command == "add":
        result = add_prerequisite(Path(args.framework), args.component, args.visibility)
        print(f"{'✅' if result['status'] == 'ok' else '⚠️'} {result['message']}")

    elif args.command == "remove":
        result = remove_prerequisite(Path(args.framework), args.component)
        print(f"{'✅' if result['status'] == 'ok' else '⚠️'} {result['message']}")

    elif args.command == "list":
        result = list_prerequisites(Path(args.framework))
        if result["status"] == "ok":
            print(f"\n📋 Prerequisites for {result['framework']}:\n")
            for prereq in result["prerequisites"]:
                print(f"  • {prereq['component']} ({prereq['visibility']})")
            print(f"\nTotal: {result['count']}")
        else:
            print(f"❌ {result['message']}")

    elif args.command == "validate":
        result = validate_prerequisites(Path(args.workspace))
        print(f"\n🔍 Validation Results:\n")

        if result["status"] == "ok":
            print("  ✅ All prerequisites are valid")
        else:
            if result["issues"]["circular_deps"]:
                print("  ❌ Circular dependencies detected:")
                for cycle in result["issues"]["circular_deps"]:
                    print(f"     {cycle}")

            if result["issues"]["missing_deps"]:
                print("  ⚠️  Missing dependencies:")
                for missing in result["issues"]["missing_deps"]:
                    print(f"     {missing}")

        print(f"\nScanned {result['frameworks_count']} frameworks")

    elif args.command == "suggest":
        result = suggest_prerequisites(Path(args.module))
        print(f"\n💡 Suggested Prerequisites:\n")

        if result["recommendations"]:
            for fw in result["recommendations"]:
                print(f"  • {fw}")
                desc = COMMON_PREREQS.get(fw, "")
                if desc:
                    print(f"    {desc}")
                # Show which files use this framework
                files = set(d["file"] for d in result["details"][fw])
                if len(files) <= 3:
                    for f in files:
                        print(f"      Used in: {f}")
                else:
                    print(f"      Used in {len(files)} files")
        else:
            print("  No suggestions (no recognized APIs found)")

    elif args.command == "init":
        result = add_default_prerequisites(Path(args.framework))
        print(f"✅ Added {result['count']} default prerequisites")


if __name__ == "__main__":
    main()
