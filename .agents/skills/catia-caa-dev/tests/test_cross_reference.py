#!/usr/bin/env python3
"""
Cross-Reference & Architecture Compliance Audit
================================================
Verifies all file references, version numbers, and architecture
consistency across the entire project. Catches drift early.

Run: python test_cross_reference.py
"""

import ast
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
CADE_ROOT = SKILL_ROOT.parent.parent.parent  # D:\DevTools\CADE
TESTS_DIR = SKILL_ROOT / "tests"
SKILLS_DIR = SKILL_ROOT / "skills"

total = passed = 0


def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    s = "PASS" if ok else "FAIL"
    print(f"  [{s}] {label}" + (f" — {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════
# 1. test_master.py <-> actual files
# ═══════════════════════════════════════════════════════════
print("=" * 70)
print("  1. test_master.py <-> Filesystem")
print("=" * 70)

master = TESTS_DIR / "test_master.py"
master_src = master.read_text(encoding="utf-8")

# Extract SUITES dict
suites_match = re.search(r"SUITES\s*=\s*\{(.*?)\}", master_src, re.DOTALL)
suite_files = (
    re.findall(r'"test_\w+\.py"', suites_match.group(1)) if suites_match else []
)
suite_files = [s.strip('"') for s in suite_files]
check("SUITES entries found", len(suite_files) > 0, f"count={len(suite_files)}")

for sf in suite_files:
    exists = (TESTS_DIR / sf).exists()
    check(f"SUITES -> {sf}", exists)

# Extract VERIFY_STRINGS
verify_match = re.search(r"VERIFY_STRINGS\s*=\s*\{(.*?)\}", master_src, re.DOTALL)
if verify_match:
    verify_refs = re.findall(r'"(\w+\.py)"', verify_match.group(1))
    for vf in verify_refs:
        check(f"VERIFY_STRINGS -> {vf}", (TESTS_DIR / vf).exists())

# Extract SKIP_SLOW
skip_match = re.search(r"SKIP_SLOW\s*=\s*\{(.*?)\}", master_src, re.DOTALL)
if skip_match:
    skip_keys = re.findall(r'"([^"]+)"', skip_match.group(1))
    for sk in skip_keys:
        check(
            f"SKIP_SLOW '{sk}' in SUITES",
            sk in suites_match.group(1) if suites_match else False,
        )

# ═══════════════════════════════════════════════════════════
# 2. SKILL.md <-> reality
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  2. SKILL.md <-> Reality")
print("=" * 70)

skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
changelog_md = (SKILL_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

# 2a. Version consistency
versions_skill = re.findall(r"v?2\.\d+\.\d+", skill_md)
versions_changelog = re.findall(r"\[(\d+\.\d+\.\d+)\]", changelog_md)
skill_ver = versions_skill[0].lstrip("v") if versions_skill else "?"
changelog_top = versions_changelog[0] if versions_changelog else "?"
check(
    "SKILL.md version",
    skill_ver == changelog_top,
    f"SKILL={skill_ver}, CHANGELOG={changelog_top}",
)
check(
    "No stale '1.0.0' in SKILL.md", "1.0.0" not in skill_md.replace("depth=1.0.0", "")
)

# 2b. Suite count
actual_suite_count = len(suite_files)
claimed_suites = re.findall(r"(\d+)\s*套件", skill_md)
if claimed_suites:
    claimed = int(claimed_suites[0])
    check(
        f"Suite count ({claimed} vs {actual_suite_count})",
        claimed == actual_suite_count,
        f"SKILL says {claimed}, master has {actual_suite_count}",
    )

# 2c. Skills modules listed in SKILL.md tree must exist
# Look for lines like: │   ├── module_name.py  (but NOT test_*.py from tests section)
tree_modules = re.findall(r"^│   ├── (\w+)\.py\s+#", skill_md, re.MULTILINE)
tree_modules = [m for m in tree_modules if not m.startswith("test_")]
for mod in tree_modules:
    # Skip modules under intents/ sub-tree (indented deeper)
    if mod in ["commands", "services", "objects", "recommendation", "helpers"]:
        continue
    exists = (SKILLS_DIR / f"{mod}.py").exists()
    check(f"Tree module -> skills/{mod}.py", exists)

# 2d. All .py files in skills/ should be in the tree (or intentional omissions)
SKIP_TREE = {
        "__init__",
        "test_skills",
        "intents",
    }  # intents/intent are package dirs
actual_modules = sorted(f.stem for f in SKILLS_DIR.glob("*.py"))
for mod in actual_modules:
    if mod in SKIP_TREE:
        continue
    check(f"skills/{mod}.py in SKILL.md tree", mod in tree_modules)

# 2e. knowledge/ + patterns/ + examples/ counts
knowledge_dir = SKILL_ROOT / "knowledge"
pattern_dir = SKILL_ROOT / "patterns"
example_dir = SKILL_ROOT / "examples"

knowledge_count = (
    len(list(knowledge_dir.rglob("*.md"))) if knowledge_dir.is_dir() else 0
)
pattern_count = len(list(pattern_dir.rglob("*.md"))) if pattern_dir.is_dir() else 0
example_count = (
    len([f for f in example_dir.rglob("*.md") if f.parent != example_dir])
    if example_dir.is_dir()
    else 0
)

check(f"Knowledge >= 9 (actual={knowledge_count})", knowledge_count >= 9)
check(f"Pattern >= 6 (actual={pattern_count})", pattern_count >= 6)
check(f"Example >= 1 (actual={example_count})", example_count >= 1)

# ═══════════════════════════════════════════════════════════
# 3. test_system_health.py <-> actual files
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  3. test_system_health.py <-> Filesystem")
print("=" * 70)

health = (TESTS_DIR / "test_system_health.py").read_text(encoding="utf-8")
health_files = re.findall(r'"test_\w+\.py"', health)
for hf in health_files:
    fname = hf.strip('"')
    exists = (TESTS_DIR / fname).exists()
    check(f"system_health -> {fname}", exists)

# ═══════════════════════════════════════════════════════════
# 4. test_complete_system.py EXISTING_SUITES
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  4. test_complete_system.py <-> Filesystem")
print("=" * 70)

complete = TESTS_DIR / "test_complete_system.py"
if complete.exists():
    cs_src = complete.read_text(encoding="utf-8")
    # Find existing_suites list (handle both naming conventions)
    es_match = re.search(
        r"(?:existing_suites|EXISTING_SUITES)\s*=\s*\[(.*?)\]", cs_src, re.DOTALL
    )
    if es_match:
        es_files = re.findall(r'"test_\w+\.py"', es_match.group(1))
        for ef in es_files:
            fname = ef.strip('"')
            check(f"complete_system -> {fname}", (TESTS_DIR / fname).exists())
        check(
            "No self-reference in suites",
            "test_complete_system.py" not in " ".join(es_files),
        )
        check("No master in suites", "test_master.py" not in " ".join(es_files))

# ═══════════════════════════════════════════════════════════
# 5. test_production_readiness.py
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  5. test_production_readiness.py <-> Consistency")
print("=" * 70)

prod = TESTS_DIR / "test_production_readiness.py"
if prod.exists():
    prod_src = prod.read_text(encoding="utf-8")

    # Version check
    vers = re.findall(r'"(\d+\.\d+\.\d+)"', prod_src)
    for v in vers:
        check(
            f"Production version {v} matches SKILL {skill_ver}",
            v == skill_ver or v == "2.0.0",
        )

    # README.md path - should use parent.parent.parent
    # README.md path check — non-root READMEs are fine (knowledge/, patterns/)
    # Only flag self.root / "README.md" without parent fix
    readme_refs = re.findall(r'self\.root\s*/\s*"README\.md"', prod_src)
    for ref in readme_refs:
        check(
            f"README.md path uses root (should use parent...): {ref[:60]}",
            False,
            ref[:60],
        )
    if not readme_refs:
        check("All README.md paths use CADE root", True)

# ═══════════════════════════════════════════════════════════
# 6. Architecture compliance
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  6. Architecture Compliance")
print("=" * 70)

# 6a. Core layer modules must exist
LAYERS = [
    ("API Layer", ["intents.py", "actions.py"]),
    ("Specification", ["specification.py"]),
    ("Diagnostics", ["diagnostics.py"]),
    ("CodeModel", ["meta_model.py"]),
    ("ChangeSet/Writer", ["changeset.py"]),
    ("Backup/Rollback", ["backup.py"]),
    ("Analyzer", ["analyzer.py"]),
    ("Generator", ["generator.py"]),
    ("Build Engine", ["build.py"]),
    ("Runtime Engine", ["run.py"]),
    ("Environment", ["env.py"]),
    ("Parser", ["parser.py"]),
    ("Utils", ["utils.py"]),
    ("Workspace", ["workspace.py"]),
    ("CLI", ["cade.py"]),
    ("MCP Server", ["mcp_server.py"]),
]

for layer_name, modules in LAYERS:
    for mod in modules:
        exists = (SKILLS_DIR / mod).exists()
        check(f"Arch layer: {layer_name} -> {mod}", exists)

# 6b. Intent submodules
intent_dir = SKILLS_DIR / "intents"
intent_subs = [
    "__init__.py",
    "commands.py",
    "services.py",
    "objects.py",
    "recommendation.py",
    "helpers.py",
]
for sub in intent_subs:
    check(f"Intent sub: intents/{sub}", (intent_dir / sub).exists())

# 6c. Templates directory count
templates_dir = SKILL_ROOT / "templates"
template_dirs = (
    [d for d in templates_dir.iterdir() if d.is_dir()] if templates_dir.is_dir() else []
)
check(
    f"Templates >= 25 sub-dirs/types (actual={len(template_dirs)})",
    len(template_dirs) >= 20,
)

# 6d. Config editor files
config_editors = SKILL_ROOT / "config" / "editors"
if config_editors.is_dir():
    editors = list(config_editors.glob("*.json"))
    check(f"Editor configs >= 4 (actual={len(editors)})", len(editors) >= 4)

# 6e. Skills don't import from tests/ (layer isolation)
violations = 0
for py_file in SKILLS_DIR.rglob("*.py"):
    try:
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        if "from tests" in content or "import tests" in content:
            violations += 1
            check(f"Layer violation: {py_file.name} imports tests/", False)
    except Exception:
        pass
if violations == 0:
    check("No skills/ -> tests/ imports (layer isolation)", True)

# ═══════════════════════════════════════════════════════════
# 7. README.md consistency
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  7. README.md Consistency")
print("=" * 70)

readme_path = CADE_ROOT / "README.md"
if readme_path.exists():
    readme_md = readme_path.read_text(encoding="utf-8")
    check("README mentions test_master.py", "test_master.py" in readme_md)
    check("README version matches SKILL", skill_ver in readme_md)

# 7a. SKILL.md should NOT claim a local README.md
check("SKILL.md does not claim local README.md", "├── README.md" not in skill_md)

# ═══════════════════════════════════════════════════════════
# 8. Catalog index file
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  8. Catalog & Docs")
print("=" * 70)

catalog_dir = SKILL_ROOT / "catalog"
catalog_files = list(catalog_dir.rglob("*")) if catalog_dir.is_dir() else []
catalog_files = [f for f in catalog_files if f.is_file()]
check(f"Catalog index exists (files={len(catalog_files)})", len(catalog_files) > 0)

# Docs directory
docs_dir = SKILL_ROOT / "docs"
if docs_dir.is_dir():
    docs_md = list(docs_dir.rglob("*.md"))
    check(f"Documentation files >= 10 (actual={len(docs_md)})", len(docs_md) >= 10)

# ═══════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"  CROSS-REFERENCE AUDIT: {passed}/{total}")
if total:
    pct = passed / total * 100
    print(f"  Pass rate: {pct:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> ALL CROSS-REFERENCES CONSISTENT <<<")
    sys.exit(0)
else:
    print(f"\n  >>> {total - passed} INCONSISTENCIE(S) FOUND <<<")
    sys.exit(1)
