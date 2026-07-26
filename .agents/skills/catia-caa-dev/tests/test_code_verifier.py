#!/usr/bin/env python3
"""
CodeVerifier Contract Tests (L0-5)
===================================
Verify static code checking on CADE-generated output.
"""

import sys, tempfile, json
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
issues = v.verify_file("LocalInterfaces/BadCmd.h",
    'class BadCmd { public: BadCmd(); };\n')
ck("detects missing CATDeclareClass (command class)",
   any("CATDeclareClass" in i.message for i in issues))
# Dialog/helper classes do NOT need CATDeclareClass — must not be flagged
issues2 = v.verify_file("LocalInterfaces/BadDlg.h",
    'class BadDlg { public: BadDlg(); };\n')
ck("dialog class NOT flagged for missing CATDeclareClass",
   not any("CATDeclareClass" in i.message for i in issues2))

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
# [14] build_gate — fabricated module → BLOCK + JSONL telemetry
# ═══════════════════════════════════════════════════════════════
print("\n[14] build_gate BLOCK on fabricated API")
import build_gate
ws2 = Path(tempfile.mkdtemp(prefix="cade_gate_")).resolve()
mod2 = ws2 / "BadFw.edu" / "BadMod.m"
(mod2 / "src").mkdir(parents=True)
(mod2 / "src" / "BadCmd.cpp").write_text(
    '#include "CATDlgStandaloneCommand.h"\n'
    'CATCreateClass(BadCmd);\n'
    'class BadCmd : public CATDlgStandaloneCommand {};\n')
r = build_gate.run_gate(ws2)
ck("decision BLOCK on fabricated header + base class",
   r["decision"] == "BLOCK" and r["errors"] >= 1,
   f"decision={r['decision']} errors={r['errors']}")
log_recs = []
for l in build_gate.LOG_FILE.read_text(encoding="utf-8").splitlines():
    try:
        rec = json.loads(l)
        if rec.get("workspace") == str(ws2):
            log_recs.append(rec)
    except Exception:
        pass
ck("JSONL has finding + run records (facts, incl. evidence/symbol)",
   any(r.get("kind") == "finding" and r.get("evidence") == "header_map"
       and r.get("symbol") for r in log_recs)
   and any(r.get("kind") == "run" and r.get("decision") == "BLOCK" for r in log_recs))

# ═══════════════════════════════════════════════════════════════
# [15] build_gate — clean module has no errors; SKIP is logged
# ═══════════════════════════════════════════════════════════════
print("\n[15] build_gate clean / SKIP")
ws3 = Path(tempfile.mkdtemp(prefix="cade_gate_clean_")).resolve()
mod3 = ws3 / "GoodFw.edu" / "GoodMod.m"
(mod3 / "src").mkdir(parents=True)
(mod3 / "src" / "GoodCmd.cpp").write_text(
    '#include "GoodCmd.h"\n\n'
    'CATImplementClass(GoodCmd, DataExtension, CATBaseUnknown, GoodCmdStartUp);\n'
    'GoodCmd::GoodCmd() {}\n')
r3 = build_gate.run_gate(ws3)
ck("clean module: no errors, decision PASS or WARN (never BLOCK)",
   r3["errors"] == 0 and r3["decision"] in ("PASS", "WARN"),
   f"decision={r3['decision']}")
r4 = build_gate.run_gate(ws3, skip=True)
ck("skip=True → decision SKIP, zero work",
   r4["decision"] == "SKIP" and r4["files_checked"] == 0)
log_recs3 = []
for l in build_gate.LOG_FILE.read_text(encoding="utf-8").splitlines():
    try:
        rec = json.loads(l)
        if rec.get("workspace") == str(ws3):
            log_recs3.append(rec)
    except Exception:
        pass
ck("SKIP recorded in JSONL (bypass visible in monthly stats)",
   any(r.get("kind") == "run" and r.get("decision") == "SKIP" for r in log_recs3))

# ═══════════════════════════════════════════════════════════════
# [16] build_gate CLI + build.py CLI compatibility
# ═══════════════════════════════════════════════════════════════
print("\n[16] CLI contracts")
out = subprocess.run(
    [sys.executable, str(SKILL / "skills" / "build_gate.py"), str(ws2), "--json"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    timeout=120)
ck("build_gate CLI: BLOCK → exit 1 + JSON payload",
   out.returncode == 1 and out.stdout.startswith("{")
   and '"decision": "BLOCK"' in out.stdout,
   f"exit={out.returncode} err={(out.stderr or '').strip()[:120]}")
out2 = subprocess.run(
    [sys.executable, str(SKILL / "skills" / "build_gate.py"), str(ws2), "--skip"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    timeout=120)
ck("build_gate CLI: --skip → exit 0 + SKIP",
   out2.returncode == 0 and "SKIP" in out2.stdout)
out3 = subprocess.run(
    [sys.executable, str(SKILL / "skills" / "build.py"), "--help"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    timeout=60)
ck("build.py --help works and lists --skip-gate (argparse intact)",
   out3.returncode == 0 and "--skip-gate" in out3.stdout
   and "--timeout" in out3.stdout)
out4 = subprocess.run(
    [sys.executable, str(SKILL / "skills" / "build_gate.py"), "--stats"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    timeout=60)
ck("build_gate --stats prints monthly summary with SKIP ratio",
   out4.returncode == 0 and "Build Gate stats" in out4.stdout
   and "SKIP" in out4.stdout,
   out4.stdout.strip().splitlines()[0] if out4.stdout else "no output")
import shutil as _shutil
_shutil.rmtree(ws2, ignore_errors=True)
_shutil.rmtree(ws3, ignore_errors=True)

# ═══════════════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════════════
import shutil
shutil.rmtree(ws, ignore_errors=True)

# ═══════════════════════════════════════════════════════════════
# [17] Regression set — real fabrication cases caught in templates/
#      and playbooks/ dogfooding (2026-07). Each entry is a real
#      case that was actually generated/reviewed and found fabricated;
#      pinning them here measures verifier recall over time.
#      See knowledge/failure_patterns/fp_template_feature_apis.md.
# ═══════════════════════════════════════════════════════════════
print("\n[17] Regression — historical fabrication cases (recall)")

_hm = None
_mi = None
try:
    from header_map import HeaderMap
    _hm = HeaderMap.load(SKILL)
except Exception:
    pass
try:
    from method_index import MethodIndex
    _mi = MethodIndex.load(SKILL)
    if _mi is not None and _mi.type_count == 0:
        _mi = None
except Exception:
    pass

# (header, should_exist) — fabricated headers from the feature/catalog
# template purge (fp_template_feature_apis.md) plus the CATLISTP.h case
# found in pb_batch_update_save.md.
_FABRICATED_HEADERS = [
    "CATIMmiResultFeature", "CATIMmiUseMechFeat", "CATMmrInterfaces",
    "CATFeatCont", "CATICatalog", "CATAfrCommandHeader",
    "CATFrmIdentityCard", "CATTopBooleanOperator", "CATTopRevolve",
    "CATLISTP",
]
if _hm is not None:
    for h in _FABRICATED_HEADERS:
        ck(f"header_map rejects fabricated '{h}'", _hm.lookup(h) is None)
else:
    ck("header_map available for regression set", False, "could not load")

_REAL_HEADERS = ["CATTopRevol", "CATAfrDialogCommandHeader", "CATICatalogChapter"]
if _hm is not None:
    for h in _REAL_HEADERS:
        ck(f"header_map accepts real '{h}'", _hm.lookup(h) is not None)

# (type, method, expected) — fabricated method attribution caught by
# grepping real B28 headers during the 2026-07 purge.
# expected=False means: type is known to the index AND method is absent
# (method_exists returns False). Some fabricated types are entirely
# unknown to the index (None) — those are covered by the header_map
# block above instead and listed here only when the type is real.
_FABRICATED_METHODS_KNOWN_TYPE = [
    ("CATICatalogChapter", "CreateStartUp"),
    ("CATICatalogChapter", "GetStartUp"),
    ("CATISpecAttrAccess", "AddAttribute"),
    ("CATICatalogDescription", "SetDescription"),
    ("CATIContainer", "GetAllChildren"),  # pre-existing case, kept for recall
]
if _mi is not None:
    for typ, meth in _FABRICATED_METHODS_KNOWN_TYPE:
        ck(f"method_index rejects '{typ}::{meth}' (known type, wrong attribution)",
           _mi.method_exists(typ, meth) is False)
else:
    ck("method_index available for regression set", False, "could not load")

# Types that are themselves fabricated (no header in B28) — the index
# must not claim the method exists on them (None = unknown type is fine,
# False is fine, True would be a regression).
_FABRICATED_TYPES_METHODS = [
    ("CATIMmiMechanicalFeature", "GetBodyResult"),
    ("CATIMmiResultFeature", "SetResult"),
]
if _mi is not None:
    for typ, meth in _FABRICATED_TYPES_METHODS:
        res = _mi.method_exists(typ, meth)
        ck(f"method_index never confirms '{typ}::{meth}' (fabricated type)",
           res is not True)

# The one true replacement fact from the purge: GetBodyResult really
# lives on CATIGeometricalElement.
if _mi is not None:
    ck("method_index confirms real owner CATIGeometricalElement::GetBodyResult",
       _mi.method_exists("CATIGeometricalElement", "GetBodyResult") is True)

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
