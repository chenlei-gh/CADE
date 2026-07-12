#!/usr/bin/env python3
"""
Requirements Decomposer Contract Tests (L1-2)
===============================================
Verify that decisions are correctly mapped to cross-domain extras.
"""

import sys, tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from requirements import RequirementsClarifier, RequirementsDecomposer, ClarificationResult, Decision

total = passed = 0

def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  Requirements Decomposer Contract Tests")
print("=" * 60)

decomposer = RequirementsDecomposer()
clarifier = RequirementsClarifier()

# ═══════════════════════════════════════════════════════════════
# [1] Basic data structure
# ═══════════════════════════════════════════════════════════════
print("\n[1] Extras structure")
extras = decomposer.enhance(ClarificationResult(domain="product"))
ck("has playbooks key", "playbooks" in extras)
ck("has capabilities key", "capabilities" in extras)
ck("has extra_components key", "extra_components" in extras)
ck("has imakefile_deps key", "imakefile_deps" in extras)
ck("all keys are lists", all(isinstance(extras[k], list) for k in extras))

# ═══════════════════════════════════════════════════════════════
# [2] Domain defaults
# ═══════════════════════════════════════════════════════════════
print("\n[2] Domain → defaults")
e = decomposer.enhance(ClarificationResult(domain="product"))
ck("product domain → playbooks", "pb.export_bom" in e["playbooks"], str(e["playbooks"]))
ck("product domain → capabilities", "cap.assembly_tree" in e["capabilities"])

e = decomposer.enhance(ClarificationResult(domain="part"))
ck("part domain → playbooks", "pb.batch_feature_check" in e["playbooks"])
ck("part domain → capabilities", "cap.feature_recognition" in e["capabilities"])

e = decomposer.enhance(ClarificationResult(domain="general"))
ck("general domain → no playbooks", e["playbooks"] == [])

# ═══════════════════════════════════════════════════════════════
# [3] Decision → extras mapping
# ═══════════════════════════════════════════════════════════════
print("\n[3] Decision → extras")
cr = ClarificationResult(
    domain="product",
    resolved={"trigger": "context_menu", "output_format": "csv"},
)
e = decomposer.enhance(cr)
ck("context_menu → data_extension",
   "data_extension" in e["extra_components"],
   f"extra_components={e['extra_components']}")
ck("csv → document_export capability",
   "cap.document_export" in e["capabilities"])

cr = ClarificationResult(
    domain="product",
    resolved={"output_format": "excel"},
)
e = decomposer.enhance(cr)
ck("excel → AutomationInterfaces",
   "AutomationInterfaces" in e["imakefile_deps"],
   f"deps={e['imakefile_deps']}")

# ═══════════════════════════════════════════════════════════════
# [4] Deduplication
# ═══════════════════════════════════════════════════════════════
print("\n[4] Deduplication")
cr = ClarificationResult(
    domain="product",
    resolved={"trigger": "context_menu"},
)
# Product domain already adds cap.assembly_tree
e = decomposer.enhance(cr)
cap_count = e["capabilities"].count("cap.assembly_tree")
ck("no duplicate capabilities", cap_count <= 1, f"count={cap_count}")

# ═══════════════════════════════════════════════════════════════
# [5] Full pipeline: clarify → decompose
# ═══════════════════════════════════════════════════════════════
print("\n[5] Full clarify → decompose pipeline")
clarification = clarifier.analyze("BOM export to CSV with right-click trigger")
e = decomposer.enhance(clarification)
ck("domain detected", clarification.domain == "product", f"domain={clarification.domain}")
ck("has extras", any(e[k] for k in e), f"extras={ {k:v for k,v in e.items() if v} }")

# ═══════════════════════════════════════════════════════════════
# [6] Empty / edge cases
# ═══════════════════════════════════════════════════════════════
print("\n[6] Edge cases")
cr = ClarificationResult(domain="", resolved={})
e = decomposer.enhance(cr)
ck("empty → all lists empty", all(v == [] for v in e.values()),
   f"extras={ {k:len(v) for k,v in e.items()} }")

cr = ClarificationResult(domain="product", resolved={"unknown_key": "unknown_value"})
e = decomposer.enhance(cr)
ck("unknown key → no crash", isinstance(e, dict))

# ═══════════════════════════════════════════════════════════════
# [7] Integration: kernel.py extras applied to generated files
# ═══════════════════════════════════════════════════════════════
print("\n[7] Integration: kernel applies extras to files")
from kernel import Kernel, KernelMode

ws = Path(tempfile.mkdtemp(prefix="cade_extras_"))
k = Kernel(workspace_root=str(ws))

# Create a minimal module so _apply_extras can write to it
mod = ws / "MyModule.m"
mod.mkdir(parents=True)
(mod / "src").mkdir(parents=True)
(mod / "LocalInterfaces").mkdir(parents=True)
(mod / "Imakefile.mk").write_text(
    "SOURCES = src/MyCmd.cpp\n"
    "LINK_WITH = CATDialogEngine\n"
    "BUILT_OBJECT_TYPE = SHARED_LIBRARY\n",
    encoding="utf-8"
)
(mod / "src" / "MyCmd.cpp").write_text(
    '#include "MyCmd.h"\n\n'
    'CATImplementClass(MyCmd, DataExtension, CATBaseUnknown, MyCmdStartUp);\n',
    encoding="utf-8"
)

extras_test = {
    "imakefile_deps": ["CATAssemblyInterfaces"],
    "playbooks": ["pb.export_bom"],
    "capabilities": ["cap.assembly_tree"],
}
plan = {"intent": {"name": "MyCmd", "module": "MyModule.m", "framework": "MyFramework"}}
applied = k._apply_extras(plan, extras_test)
ck("imakefile dep applied",
   "CATAssemblyInterfaces" in applied.get("deps_added", []))
ck("playbook ref injected",
   "CADE Playbooks" in applied.get("refs_added", "") or
   len(applied.get("refs_added", [])) > 0)

verify = (mod / "Imakefile.mk").read_text()
ck("Imakefile has new dep",
   "CATAssemblyInterfaces" in verify,
   f"LINK_WITH={verify.split('LINK_WITH')[1][:60] if 'LINK_WITH' in verify else 'missing'}")

import shutil
shutil.rmtree(ws, ignore_errors=True)

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
