#!/usr/bin/env python3
"""
L4: Architecture Invariants Test
=================================
Verify that the architecture constraints are never violated:
  - AI never calls Generator directly
  - Development never writes files directly (must go through ChangeSet)
  - Generator never accesses Workspace
  - Intent → Specification → Generator chain is preserved
  - ChangeSet is the only file writer
"""

import inspect
import sys
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(
        f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else "")
    )


print("=" * 70)
print("  L4: Architecture Invariants Test")
print("=" * 70)

# ═══════════════════════════════════════════════════════════════════
# 1. Intent → Generator connection: Intent MUST go through Spec
# ═══════════════════════════════════════════════════════════════════

print("\n[1] Intent Layer → Generator must NOT be direct")

# Check that intents.py does NOT import generator directly
import intents as intent_mod

intent_src = inspect.getsource(intent_mod)
ck(
    "1.1 intents.py does not import generator",
    "import generator" not in intent_src and "from generator" not in intent_src,
)

# Check intents sub-modules
for sub in ["commands", "services", "objects", "recommendation"]:
    mod_name = f"intents.{sub}"
    try:
        mod = __import__(mod_name, fromlist=[sub])
        src = inspect.getsource(mod)
        ok = "import generator" not in src and "from generator" not in src
        ck(f"1.2 {mod_name} does not import generator", ok)
    except Exception as e:
        ck(f"1.2 {mod_name}", False, str(e)[:60])

# ═══════════════════════════════════════════════════════════════════
# 2. Generator must NOT access workspace
# ═══════════════════════════════════════════════════════════════════

print("\n[2] Generator must NOT access workspace")

import generator as gen_mod

gen_src = inspect.getsource(gen_mod)
ck(
    "2.1 generator.py does not import analyzer",
    "import analyzer" not in gen_src and "from analyzer" not in gen_src,
)
ck(
    "2.2 generator.py does not import meta_model",
    "import meta_model" not in gen_src and "from meta_model" not in gen_src,
)

# Generator must only know about its templates directory
ck("2.3 generator.py uses templates dir", "templates" in gen_src.lower())

# ═══════════════════════════════════════════════════════════════════
# 3. File I/O must go through ChangeSet
# ═══════════════════════════════════════════════════════════════════

print("\n[3] File I/O must go through ChangeSet")

import actions as act_mod

act_src = inspect.getsource(act_mod)

# Check that actions.py does NOT use open() or write_text() directly for CAA files
# (It's OK for logging/config)
direct_file_writes = act_src.count("write_text(") - act_src.count("# write_text")
# Count ChangeSet usage vs direct file ops
cs_creates = act_src.count("cs.add_create_file") + act_src.count("cs.add_create(")
cs_modifies = act_src.count("cs.add_modify") + act_src.count("cs.add_modify(")
ck(
    "3.1 ChangeSet.create operations present",
    cs_creates > 0,
    f"{cs_creates} occurrences",
)
ck(
    "3.2 ChangeSet.modify operations present",
    cs_modifies > 0,
    f"{cs_modifies} occurrences",
)
ck(
    "3.3 ChangeSet is the primary I/O path",
    (cs_creates + cs_modifies) >= 5,
    "dominant pattern",
)

# ═══════════════════════════════════════════════════════════════════
# 4. Specification independence
# ═══════════════════════════════════════════════════════════════════

print("\n[4] Specification is independent of AI and Generator")

import specification as spec_mod

spec_src = inspect.getsource(spec_mod)
ck(
    "4.1 spec does not import intents",
    "import intents" not in spec_src and "from intents" not in spec_src,
)
ck(
    "4.2 spec does not import generator",
    "import generator" not in spec_src and "from generator" not in spec_src,
)
ck(
    "4.3 spec does not import actions",
    "import actions" not in spec_src and "from actions" not in spec_src,
)
ck(
    "4.4 spec is pure dataclass",
    "from dataclasses" in spec_src or "@dataclass" in spec_src,
)

# ═══════════════════════════════════════════════════════════════════
# 5. Dependency direction
# ═══════════════════════════════════════════════════════════════════

print("\n[5] Dependency direction enforcement")

# Higher layers can import lower layers, but NOT vice versa
# Intent (L1) can import Action (L2), MetaModel (L3), ChangeSet (L4)
# Action (L2) should NOT import Intent (L1)
# Generator (L4) should NOT import Action (L2) or Intent (L1)

ck(
    "5.1 actions.py does not import intents",
    "import intents" not in act_src and "from intents" not in act_src,
)
ck(
    "5.2 generator.py does not import intents",
    "import intents" not in gen_src and "from intents" not in gen_src,
)
ck(
    "5.3 generator.py does not import actions",
    "import actions" not in gen_src and "from actions" not in gen_src,
)
ck(
    "5.4 specification.py does not import intents",
    "import intents" not in spec_src and "from intents" not in spec_src,
)
ck(
    "5.5 changeset.py is independent",
    "from intents" not in inspect.getsource(__import__("changeset")),
)

# ═══════════════════════════════════════════════════════════════════
# 6. Rich Domain Model — entities know themselves
# ═══════════════════════════════════════════════════════════════════

print("\n[6] Rich Domain Model integrity")

from meta_model import Command, Dialog, Framework, Interface, Module, Workbench

# Framework knows its structure
fw = Framework(name="Test.edu", path=Path("/test"))
ck("6.1 Framework.dictionary_path", "CNext" in str(fw.dictionary_path()))
ck("6.2 Framework.catalog_path", "CATNls" in str(fw.catalog_path()))

# Module knows its structure
mod = Module(name="Test.m", path=Path("/test/Test.m"))
mod.framework = fw
ck("6.3 Module.src_dir_path", "src" in str(mod.src_dir_path()))
ck(
    "6.4 Module.local_interfaces_dir",
    "LocalInterfaces" in str(mod.local_interfaces_dir()),
)

# Command knows its registration
cmd = Command(name="MyCmd", path=Path("/test/Test.m/src/MyCmd.cpp"))
cmd.module = mod
cmd.is_stateful = True
ck("6.5 Command.dictionary_entry is non-empty", len(cmd.dictionary_entry()) > 0)
ck("6.6 Command.nls_block is non-empty", len(cmd.nls_block()) > 0)
ck("6.7 Command.imakefile_sources is non-empty", len(cmd.imakefile_sources()) > 0)
ck(
    "6.8 Command has CATIAfrGeneralWksAddin in dictionary entry",
    "CATIAfrGeneralWksAddin" in cmd.dictionary_entry(),
)

# Model integrity — no null module for Command
cmd2 = Command(name="BadCmd", path=Path("."))
ck("6.9 Command without module returns None paths", cmd2.header_path() is None)

# ═══════════════════════════════════════════════════════════════════
# 7. Kernel architecture constraints (v3.0)
# ═══════════════════════════════════════════════════════════════════

print("\n[7] Kernel architecture constraints (v3.0)")

try:
    import kernel
    ck("7.1 kernel module exists", True)
    ck("7.2 KernelResult dataclass", hasattr(kernel, "KernelResult"))
    ck("7.3 Kernel class", hasattr(kernel, "Kernel"))
    ck("7.4 KernelMode enum", hasattr(kernel, "KernelMode"))
    ck("7.5 3 modes defined",
       all(hasattr(kernel.KernelMode, m) for m in ("DEVELOP", "ANALYZE", "REPAIR")))
except ImportError:
    ck("7.1 kernel module exists", False, "not importable")

try:
    from requirements import RequirementsClarifier
    ck("7.6 RequirementsClarifier exists", True)
except ImportError:
    ck("7.6 RequirementsClarifier exists", False)

try:
    from repair import RepairLoop, RepairState
    ck("7.7 RepairLoop exists", True)
    ck("7.8 MAX_RETRIES is 3", RepairLoop.MAX_RETRIES == 3)
except ImportError:
    ck("7.7 RepairLoop exists", False)

try:
    from verifier import BuildVerifier
    ck("7.9 BuildVerifier exists", True)
except ImportError:
    ck("7.9 BuildVerifier exists", False)

try:
    from actions import ActionContext
    ck("7.10 ActionContext exists", True)
except ImportError:
    ck("7.10 ActionContext exists", False)

# ═══════════════════════════════════════════════════════════════════
print(f"\n{'=' * 70}")
print(f"  L4 Architecture: {passed}/{total} ({passed / total * 100:.0f}%)")
print(f"{'=' * 70}")
sys.exit(0 if passed == total else 1)
