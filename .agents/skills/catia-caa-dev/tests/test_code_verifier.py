#!/usr/bin/env python3
"""
CodeVerifier Contract Tests (L0-5)
===================================
Verify static code checking on CADE-generated output.
"""

import sys, tempfile
from pathlib import Path

SKILL = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL / "skills"))

from verifier import CodeVerifier, CodeIssue, CodeVerifyResult

total = passed = 0

def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  CodeVerifier Contract Tests (L0-5)")
print("=" * 60)

# ═══════════════════════════════════════════════════════════════
# [1] Empty module — no errors
# ═══════════════════════════════════════════════════════════════
print("\n[1] Empty module")
ws = Path(tempfile.mkdtemp(prefix="cade_verify_"))
mod = ws / "EmptyMod.m"
mod.mkdir()
v = CodeVerifier()
r = v.verify_module(mod)
ck("returns CodeVerifyResult", isinstance(r, CodeVerifyResult))
ck("success (no files = no errors)", r.success)
ck("files_checked is 0", r.files_checked == 0)

# ═══════════════════════════════════════════════════════════════
# [2] verify_file — .cpp missing CATImplementClass
# ═══════════════════════════════════════════════════════════════
print("\n[2] verify_file — missing macro")
issues = v.verify_file("src/BadCmd.cpp",
    '#include "BadCmd.h"\n\nBadCmd::BadCmd() {}\n')
ck("detects missing CATImplementClass",
   any("CATImplementClass" in i.message for i in issues),
   f"found {len(issues)} issues")

# ═══════════════════════════════════════════════════════════════
# [3] verify_file — valid .cpp
# ═══════════════════════════════════════════════════════════════
print("\n[3] verify_file — valid cpp")
issues = v.verify_file("src/GoodCmd.cpp",
    '#include "GoodCmd.h"\n\n'
    'CATImplementClass(GoodCmd, DataExtension, CATBaseUnknown, GoodCmdStartUp);\n'
    'GoodCmd::GoodCmd() {}\n')
ck("no errors for valid file",
   not any(i.severity == "error" for i in issues),
   f"errors={sum(1 for i in issues if i.severity=='error')}")

# ═══════════════════════════════════════════════════════════════
# [4] verify_file — .h missing CATDeclareClass
# ═══════════════════════════════════════════════════════════════
print("\n[4] verify_file — .h missing macro")
issues = v.verify_file("LocalInterfaces/BadDlg.h",
    'class BadDlg { public: BadDlg(); };\n')
ck("detects missing CATDeclareClass",
   any("CATDeclareClass" in i.message for i in issues))

# ═══════════════════════════════════════════════════════════════
# [5] verify_file — valid .h
# ═══════════════════════════════════════════════════════════════
print("\n[5] verify_file — valid .h")
issues = v.verify_file("LocalInterfaces/GoodDlg.h",
    'class GoodDlg { CATDeclareClass; public: GoodDlg(); };\n')
ck("no errors for valid header",
   not any(i.severity == "error" for i in issues))

# ═══════════════════════════════════════════════════════════════
# [6] verify_file — interface naming
# ═══════════════════════════════════════════════════════════════
print("\n[6] verify_file — interface naming")
issues = v.verify_file("PublicInterfaces/MyInterface.h",
    'class MyInterface { public: MyInterface(); };\n')
ck("detects non-I-prefixed interface",
   any("start with 'I'" in i.message for i in issues))

# ═══════════════════════════════════════════════════════════════
# [7] verify_file — valid interface
# ═══════════════════════════════════════════════════════════════
print("\n[7] verify_file — valid interface")
issues = v.verify_file("PublicInterfaces/IMyInterface.h",
    'class IMyInterface { CATDeclareClass; public: virtual ~IMyInterface(){} };\n')
ck("no naming error for I-prefixed",
   not any("start with 'I'" in i.message for i in issues))

# ═══════════════════════════════════════════════════════════════
# [8] verify_file — Imakefile
# ═══════════════════════════════════════════════════════════════
print("\n[8] verify_file — Imakefile")
issues = v.verify_file("Imakefile.mk",
    'SOURCES = src/MyCmd.cpp src/MyCmdHeader.cpp\n'
    'LINK_WITH = CATDialogEngine\n'
    'BUILT_OBJECT_TYPE = SHARED_LIBRARY\n')
ck("no errors for complete Imakefile",
   not any(i.severity == "error" for i in issues))

# Missing LINK_WITH
issues = v.verify_file("Imakefile.mk", 'SOURCES = src/MyCmd.cpp\n')
ck("warns on missing LINK_WITH",
   any("LINK_WITH" in i.message for i in issues))

# ═══════════════════════════════════════════════════════════════
# [9] verify_file — NLS
# ═══════════════════════════════════════════════════════════════
print("\n[9] verify_file — NLS")
issues = v.verify_file("msgcatalog/Test.CATNls",
    'MyCmd.Title = "My Command";\nMyCmd.Tip = "Does something";\n')
ck("no warnings for complete NLS",
   not any(i.severity == "warning" and "Title" in i.message for i in issues))

issues = v.verify_file("msgcatalog/Bare.CATNls", '')
ck("warns on missing Title in NLS",
   any("Title" in i.message for i in issues))

# ═══════════════════════════════════════════════════════════════
# [10] verify_file — Dictionary
# ═══════════════════════════════════════════════════════════════
print("\n[10] verify_file — Dictionary")
issues = v.verify_file("dictionary/MyFW.edu.dico",
    'MyModule.MyCmd libMyModule CATCommand\n')
ck("no errors for valid dictionary entry",
   not any(i.severity == "error" for i in issues))

issues = v.verify_file("dictionary/MyFW.edu.dico", 'bad\n')
ck("detects malformed dictionary entry",
   any("Malformed" in i.message for i in issues))

# ═══════════════════════════════════════════════════════════════
# [11] header_map CLI — fabricated/real header lookup
# ═══════════════════════════════════════════════════════════════
print("\n[11] header_map CLI")
import subprocess
_hm_cli = [sys.executable, str(SKILL / "skills" / "header_map.py")]
try:
    out = subprocess.run(_hm_cli + ["CATDlgEditor", "CATIProduct"],
                         capture_output=True, text=True, timeout=60)
    ck("real header resolves with fw + path",
       out.returncode == 0
       and "fw=Dialog" in out.stdout
       and "path=" in out.stdout,
       out.stdout.strip().splitlines()[0] if out.stdout else "no output")

    out2 = subprocess.run(_hm_cli + ["CATListValCATBaseUnknown"],
                          capture_output=True, text=True, timeout=60)
    ck("fabricated header NOT-FOUND with suggestion",
       out2.returncode == 1
       and "NOT-FOUND" in out2.stdout
       and "CATLISTV_CATBaseUnknown" in out2.stdout,
       out2.stdout.strip() if out2.stdout else "no output")

    # Multiple headers in one call — all-found must exit 0
    out3 = subprocess.run(_hm_cli + ["CATDlgEditor", "CATDlgFile", "CATPathElement"],
                          capture_output=True, text=True, timeout=60)
    ck("multi-query all-found exits 0",
       out3.returncode == 0 and out3.stdout.count("fw=") == 3)
except FileNotFoundError:
    ck("header_map CLI runnable", False, "skills/header_map.py not found")

# ═══════════════════════════════════════════════════════════════
# [12] method_index CLI — type::method existence
# ═══════════════════════════════════════════════════════════════
print("\n[12] method_index CLI")
_mi_cli = [sys.executable, str(SKILL / "skills" / "method_index.py")]
try:
    out = subprocess.run(_mi_cli + ["CATIProduct", "GetChildren", "GetAllChildren"],
                         capture_output=True, text=True, timeout=60)
    ck("real methods on correct type → OK + exit 0",
       out.returncode == 0 and out.stdout.count("OK") == 2,
       out.stdout.strip().replace("\n", " | "))

    out2 = subprocess.run(_mi_cli + ["CATIContainer", "GetAllChildren"],
                          capture_output=True, text=True, timeout=60)
    ck("wrong receiver → NOT-FOUND with owners list",
       out2.returncode == 1
       and "NOT-FOUND" in out2.stdout
       and "CATIProduct" in out2.stdout,
       out2.stdout.strip())

    out3 = subprocess.run(_mi_cli + ["CATIContainer", "ListMembersHere"],
                          capture_output=True, text=True, timeout=60)
    ck("real container method → OK",
       out3.returncode == 0 and "OK" in out3.stdout,
       out3.stdout.strip())
except FileNotFoundError:
    ck("method_index CLI runnable", False, "skills/method_index.py not found")

# ═══════════════════════════════════════════════════════════════
# [13] verifier — fabricated base class + wrong-receiver method
# ═══════════════════════════════════════════════════════════════
print("\n[13] verifier fabricated base class / method call")
issues = v.verify_file("src/BadDlgCmd.cpp",
    '#include "BadDlgCmd.h"\n'
    '#include "CATDlgStandaloneCommand.h"\n'
    'CATCreateClass(BadDlgCmd);\n'
    'class BadDlgCmd : public CATDlgStandaloneCommand {};\n')
ck("fabricated base class flagged as error",
   any(i.severity == "error" and "CATDlgStandaloneCommand" in i.message
       and "base class" in i.message for i in issues),
   f"{len(issues)} issues")

issues2 = v.verify_file("src/FindSetCmd.cpp",
    '#include "FindSetCmd.h"\n'
    '#include "CATIContainer.h"\n'
    'CATCreateClass(FindSetCmd);\n'
    'void Find(CATIContainer_var spCont, CATIProduct_var spProd) {\n'
    '    CATListValCATBaseUnknown_var* p = spCont->GetAllChildren();\n'
    '    CATListValCATBaseUnknown_var* c = spProd->GetAllChildren();\n'
    '}\n')
wrong = [i for i in issues2 if "has no method" in i.message]
ck("wrong-receiver method flagged (CATIContainer::GetAllChildren)",
   len(wrong) == 1 and "receiver: spCont" in wrong[0].message,
   f"{len(wrong)} flagged")
ck("correct receiver NOT flagged (CATIProduct::GetAllChildren)",
   not any("receiver: spProd" in i.message for i in wrong))

# ═══════════════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════════════
import shutil
shutil.rmtree(ws, ignore_errors=True)

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
