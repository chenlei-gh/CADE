#!/usr/bin/env python3
"""
Intent Planner — Test Suite
=============================
Verify: Task Template loading, single intent planning,
batch merging, dedup, sort order.

Run: python test_intent_planner.py
"""

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "skills"))

from intent import (
    Intent, IntentType, ImpactReport, Severity, DevelopmentPlan, ActionStep,
    Planner, plan, plan_batch, merge_plans, analyze, analyze_batch,
)

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" +
          (f" - {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════
# 1. Data Models
# ═══════════════════════════════════════════════════════════
print("=" * 70)
print("  1. Data Models")
print("=" * 70)

i = Intent(type=IntentType.CREATE_COMMAND_WITH_DIALOG,
           name="MyCmd", module="MyModule.m", framework="MyFw.edu")
check("Intent created", i.name == "MyCmd")
check("to_dict roundtrip", i.to_dict()["type"] == "CreateCommandWithDialog")
check("from_dict", Intent.from_dict(i.to_dict()).name == "MyCmd")

step = ActionStep(action="create_command", params={"name": "MyCmd"})
check("ActionStep auto-id", step.step_id == "create_command_MyCmd")

plan_obj = DevelopmentPlan(intent=i)
plan_obj.add_step("ensure_module", {"name": "MyModule.m"})
plan_obj.add_step("create_command", {"name": "MyCmd"}, deps=["ensure_module_MyModule.m"])
check("Plan step count", plan_obj.step_count() == 2)
check("to_dict has keys", all(k in plan_obj.to_dict() for k in
      ["intent", "steps", "risk_level", "step_count"]))


# ═══════════════════════════════════════════════════════════
# 2. Planner — Single Intent
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  2. Planner — Single Intent")
print("=" * 70)

planner = Planner()
check("Templates loaded", len(planner.available_templates()) >= 6)

# Command with dialog
i = Intent(type=IntentType.CREATE_COMMAND_WITH_DIALOG,
           name="ATAutoRename", module="AT_UI.m", framework="AutoTools.edu")
p = planner.plan(i)
check("Command w/ dialog plan", p.step_count() >= 7, f"{p.step_count()} steps")
check("ensure_module first", p.steps[0].action == "ensure_module")
check("module resolved", p.steps[0].params["name"] == "AT_UI.m")
check("risk low", p.risk_level == Severity.LOW)

# Feature
i2 = Intent(type=IntentType.CREATE_FEATURE_WITH_FACTORY,
            name="ATTimeTable", module="AT_Feature.m", framework="AutoTools.edu")
p2 = planner.plan(i2)
check("Feature plan steps", p2.step_count() >= 5, f"{p2.step_count()} steps")
check("create_interface in plan", any(s.action == "create_interface" for s in p2.steps))

# Framework
i3 = Intent(type=IntentType.CREATE_FRAMEWORK, name="AutoTools", framework="AutoTools.edu")
p3 = planner.plan(i3)
check("Framework plan steps", p3.step_count() >= 8, f"{p3.step_count()} steps")
check("create_readme in plan", any(s.action == "create_readme" for s in p3.steps))


# ═══════════════════════════════════════════════════════════
# 3. Batch Plan — 15-item development table
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  3. Batch Plan — 15 items")
print("=" * 70)

development_table = [
    ("ATAutoRename",     "AT_UI",      "CreateCommandWithDialog"),
    ("ATBOMExport",      "AT_Data",    "CreateCommand"),
    ("ATBOMImport",      "AT_Data",    "CreateCommand"),
    ("ATAutoColor",      "AT_Data",    "CreateCommand"),
    ("ATTimeTable",      "AT_Feature", "CreateFeatureWithFactory"),
    ("ATExplode",        "AT_Geom",    "CreateCommandWithDialog"),
    ("ATSurfaceFlatten", "AT_Geom",    "CreateCommandWithDialog"),
    ("ATWrapPredict",    "AT_Geom",    "CreateCommandWithDialog"),
    ("AT3DAnnot",        "AT_Annot",   "CreateCommand"),
    ("ATDrawingGen",     "AT_Annot",   "CreateCommand"),
    ("ATDataCheck",      "AT_Core",    "CreateCommandWithDialog"),
]

intents = []
for name, mod, itype in development_table:
    intents.append(Intent(
        type=IntentType(itype),
        name=name, module=mod + ".m",
        framework="AutoTools.edu",
    ))

plans = plan_batch(intents)
check("11 plans generated", len(plans) == 11)

# Verify dedup — ensure_module should only appear once per module
all_steps = []
for p in plans:
    all_steps.extend(p.steps)

ensure_module_steps = [s for s in all_steps if s.action == "ensure_module"]
unique_modules = set(s.params.get("name", "") for s in ensure_module_steps)
check(f"Dedup: {len(unique_modules)} unique modules (not {len(ensure_module_steps)})",
      len(unique_modules) == len(ensure_module_steps),
      f"unique={len(unique_modules)} vs total={len(ensure_module_steps)}")


# ═══════════════════════════════════════════════════════════
# 4. Sort order — framework → module → features → commands
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  4. Sort order")
print("=" * 70)

merged = merge_plans(plans)
check("Merged plan has steps", merged.step_count() > 0)

# Check priority ordering
priority_order = {
    "ensure_framework": 0, "create_framework": 0,
    "ensure_module": 1, "create_module": 1,
    "create_interface": 2,
    "create_feature": 3, "create_factory": 3, "create_extension": 3,
    "create_command": 4, "create_command_header": 5, "create_dialog": 5,
    "register_catalog": 6, "register_nls": 6,
    "update_imakefile": 7,
}

in_order = True
last_priority = -1
for step in merged.steps:
    p = priority_order.get(step.action, 99)
    if p < last_priority:
        in_order = False
        break
    last_priority = p
check("Steps sorted by priority", in_order)

# ═══════════════════════════════════════════════════════════
# 5. Plan round-trip (dict)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  5. Plan serialization")
print("=" * 70)

d = merged.to_dict()
check("to_dict has intent", "intent" in d)
check("to_dict has steps", "steps" in d)
check("to_dict has risk_level", "risk_level" in d)
check("to_dict has step_count", "step_count" in d)

import json as _json
j = _json.dumps(d, ensure_ascii=False)
check("JSON serializable", isinstance(j, str) and len(j) > 100)


# ═══════════════════════════════════════════════════════════
# 6. Impact Analysis (P1)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  6. Impact Analysis")
print("=" * 70)

# Standalone analysis (no context)
r = analyze("MyCmd", entity_type="command", operation="rename")
check("Impact report created", isinstance(r, ImpactReport))
check("Entity name", r.entity == "MyCmd")
check("Severity LOW for rename", r.severity == Severity.LOW)
check("Affected files not empty", len(r.affected_files) > 0)
check("Recommendations present", len(r.recommendations) >= 1, r.recommendations[0][:40])

# Interface deletion → CRITICAL
r2 = analyze("IMyInterface", entity_type="interface", operation="delete")
check("Interface delete → CRITICAL", r2.severity == Severity.CRITICAL)
check("Snapshot recommendation", any("snapshot" in rec.lower() for rec in r2.recommendations))

# Module deletion → CRITICAL
r3 = analyze("MyModule", entity_type="module", operation="delete")
check("Module delete → CRITICAL", r3.severity == Severity.CRITICAL)

# Create → NONE
r4 = analyze("NewCmd", entity_type="command", operation="create")
check("Create → NONE", r4.severity == Severity.NONE)
check("Create has recommendations", len(r4.recommendations) > 0)

# Batch analysis
changes = [
    {"name": "OldCmd", "type": "command", "operation": "rename"},
    {"name": "IOldInterface", "type": "interface", "operation": "delete"},
    {"name": "OldModule", "type": "module", "operation": "delete"},
]
reports = analyze_batch(changes)
check("Batch: 3 reports", len(reports) == 3)
check("Batch: severities differ", len(set(r.severity for r in reports)) > 1)

# to_dict round-trip
rd = r.to_dict()
check("ImpactReport to_dict has severity", rd["severity"] == "low")
check("ImpactReport to_dict has entity", rd["entity"] == "MyCmd")
check("ImpactReport to_dict has affected_files_count", "affected_files_count" in rd)


# ═══════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"  INTENT PLANNER: {passed}/{total}")
if total:
    print(f"  Pass rate: {passed / total * 100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> All Planner tests passed <<<")
    sys.exit(0)
else:
    print(f"\n  >>> {total - passed} failure(s) <<<")
    sys.exit(1)
