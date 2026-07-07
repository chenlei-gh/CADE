"""
Intelligent recommendation system.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from actions import ActionContext


def suggest_next_action(ctx: ActionContext, last_action: Optional[Dict] = None) -> Dict:
    """
    Analyze workspace and last action to suggest intelligent next steps.
    """
    ctx.refresh()
    snapshot = ctx.snapshot
    suggestions = []
    warnings = []

    if last_action:
        intent = last_action.get("intent", "")
        components = last_action.get("components", {})

        if intent == "create_executable_command":
            cmd_name = components.get("command")
            if not components.get("workbench"):
                wbs = snapshot.get_all_workbenches()
                wb_names = [w.name for w in wbs]
                if wb_names:
                    suggestions.append(
                        {
                            "action": "add_command_to_workbench",
                            "reason": f"Command '{cmd_name}' is not in any workbench",
                            "priority": "high",
                            "params": {
                                "command": cmd_name,
                                "available_workbenches": wb_names,
                            },
                            "estimated_time": "2 minutes",
                        }
                    )
                else:
                    suggestions.append(
                        {
                            "action": "create_workbench",
                            "reason": "No workbench exists to hold the command",
                            "priority": "high",
                            "params": {"suggested_name": "MyWorkbench"},
                            "estimated_time": "5 minutes",
                        }
                    )
            if components.get("dialog") and not last_action.get("dialog_configured"):
                suggestions.append(
                    {
                        "action": "configure_dialog",
                        "reason": f"Dialog '{components['dialog']}' needs controls",
                        "priority": "medium",
                        "params": {"dialog": components["dialog"]},
                        "estimated_time": "10 minutes",
                    }
                )
            suggestions.append(
                {
                    "action": "build_module",
                    "reason": "New files created, verify compilation",
                    "priority": "high",
                    "params": {"module": components.get("module")},
                    "estimated_time": "1-3 minutes",
                }
            )

        elif intent == "expose_service":
            suggestions.append(
                {
                    "action": "implement_service_methods",
                    "reason": "Interface created but methods need implementation",
                    "priority": "high",
                    "params": last_action.get("service", {}),
                    "estimated_time": "10-30 minutes",
                }
            )
            suggestions.append(
                {
                    "action": "build_module",
                    "reason": "Verify interface compilation",
                    "priority": "high",
                    "estimated_time": "1-3 minutes",
                }
            )

        elif intent == "create_feature":
            suggestions.append(
                {
                    "action": "define_attributes",
                    "reason": "Feature attributes need implementation",
                    "priority": "high",
                    "params": last_action.get("feature", {}),
                    "estimated_time": "15-30 minutes",
                }
            )
            if last_action.get("feature", {}).get("factory"):
                suggestions.append(
                    {
                        "action": "register_factory",
                        "reason": "Factory needs Startup Catalog registration",
                        "priority": "medium",
                        "estimated_time": "5 minutes",
                    }
                )

    workspace_health = _analyze_workspace_health(snapshot)

    # Empty module detection
    for fw in snapshot.frameworks:
        for mod in fw.modules:
            if not mod.commands and not mod.interfaces and not mod.components:
                warnings.append(f"Empty module: '{mod.name}'")
                suggestions.append(
                    {
                        "action": "create_command_in_module",
                        "reason": f"Module '{mod.name}' is empty, consider adding commands",
                        "priority": "low",
                        "params": {"module": mod.name, "framework": fw.name},
                        "estimated_time": "5 minutes",
                    }
                )
                break

    # Missing headers
    cmds_wo_headers = [
        c.name
        for c in snapshot.get_all_commands()
        if not c.header or not c.header.exists()
    ]
    if cmds_wo_headers:
        warnings.append(f"Commands missing headers: {', '.join(cmds_wo_headers[:3])}")
        suggestions.append(
            {
                "action": "fix_missing_headers",
                "reason": f"{len(cmds_wo_headers)} command(s) missing header files",
                "priority": "medium",
                "params": {"commands": cmds_wo_headers},
                "estimated_time": "10 minutes",
            }
        )

    if snapshot.orphaned_files:
        warnings.append(f"Orphaned files: {len(snapshot.orphaned_files)}")
        suggestions.append(
            {
                "action": "cleanup_orphaned_files",
                "reason": "Found orphaned files that can be cleaned up",
                "priority": "low",
                "params": {"count": len(snapshot.orphaned_files)},
                "estimated_time": "3 minutes",
            }
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda x: priority_order.get(x["priority"], 99))

    return {
        "status": "ok",
        "suggestions": suggestions,
        "total_suggestions": len(suggestions),
        "warnings": warnings,
        "workspace_health": workspace_health,
    }


def _analyze_workspace_health(snapshot) -> Dict:
    total_fw = len(snapshot.frameworks)
    total_mod = sum(len(fw.modules) for fw in snapshot.frameworks)
    total_cmd = len(snapshot.get_all_commands())
    total_if = len(snapshot.get_all_interfaces())
    total_wb = len(snapshot.get_all_workbenches())

    issues = 0
    if total_fw == 0:
        health = "empty"
        issues += 1
    elif total_cmd == 0 and total_mod > 0:
        health = "needs_content"
        issues += 1
    elif total_cmd > 0 and total_wb == 0:
        health = "needs_workbench"
        issues += 1
    elif snapshot.warnings:
        health = "needs_attention"
        issues = len(snapshot.warnings)
    else:
        health = "good"

    ratings = {
        "good": "Excellent",
        "needs_attention": "Good",
        "needs_content": "Needs Work",
        "needs_workbench": "Needs Workbench",
        "empty": "Just Started",
    }

    return {
        "health": health,
        "total_frameworks": total_fw,
        "total_modules": total_mod,
        "total_commands": total_cmd,
        "total_interfaces": total_if,
        "total_workbenches": total_wb,
        "issues_count": issues,
        "rating": ratings.get(health, "Unknown"),
    }
