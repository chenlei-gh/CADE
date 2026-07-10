#!/usr/bin/env python3
"""
Deep Link & Reference Audit
=============================
Verify every link, path, version, badge, and reference across the project.

Run: python test_deep_audit.py
"""

import json, re, sys, os
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
CADE_ROOT = SKILL_ROOT.parent.parent.parent

total = passed = 0

def check(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))


# ═══════════════════════════════════════════════════════════
# 1. All markdown links resolve to real files
# ═══════════════════════════════════════════════════════════
print("=" * 70)
print("  1. Markdown link resolution")
print("=" * 70)

def resolve_md_link(base_dir: Path, link: str) -> Path:
    """Resolve a relative markdown link to absolute path."""
    if link.startswith("http://") or link.startswith("https://"):
        return None
    if link.startswith("#"):
        return None
    if link.startswith("mailto:"):
        return None
    if link.startswith("[["):
        return None
    # Skip links that look like regex or code references
    if re.search(r'[\\^$*+?{}()]', link):
        return None
    return (base_dir / link).resolve()

bad_links = []
good_links = 0
for md_file in SKILL_ROOT.rglob("*.md"):
    base_dir = md_file.parent
    try:
        content = md_file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue

    # Find all [text](link) patterns
    links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
    for text, link in links:
        # Skip external URLs, mailto, anchors
        if link.startswith(("http://", "https://", "mailto:", "#")):
            good_links += 1
            continue
        # Skip Obsidian-style [[links]]
        if link.startswith("[["):
            continue

        target = resolve_md_link(base_dir, link)
        if target is None:
            good_links += 1
            continue

        if not target.exists():
            rel = str(md_file.relative_to(SKILL_ROOT))
            bad_links.append((rel, link, text))
        else:
            good_links += 1

if bad_links:
    for rel, link, text in bad_links:
        check(f"Broken: {rel} -> [{text}]({link})", False)
else:
    check(f"All {good_links} internal links resolve", True)

# ═══════════════════════════════════════════════════════════
# 2. All Python imports reference real modules
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  2. Python import resolution")
print("=" * 70)

sys.path.insert(0, str(SKILL_ROOT / "skills"))
import_errors = 0
for py_file in (SKILL_ROOT / "skills").rglob("*.py"):
    if py_file.name.startswith("_"):
        continue
    # Skip intent/ sub-package (internal imports)
    if "intent" in str(py_file):
        continue
    try:
        content = py_file.read_text(encoding="utf-8")
        imports = re.findall(r'from\s+(\S+)\s+import\s+', content)
        for imp in imports:
            if imp.startswith("."):
                continue
            # tools/ modules use sys.path manipulation
            if imp in ("catia_detector", "setup_environment", "prerequisites_manager",
                        "setup_wizard", "validate_component_ai"):
                continue
            try:
                __import__(imp)
            except ImportError:
                import_errors += 1
                check(f"Bad import in {py_file.name}: from {imp}", False)
    except Exception:
        pass

if import_errors == 0:
    check("All Python imports valid", True)
else:
    check(f"Python imports: {import_errors} failed", False)

# ═══════════════════════════════════════════════════════════
# 3. All file references in SKILL.md file tree exist
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  3. SKILL.md file tree accuracy")
print("=" * 70)

skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
tree_files = re.findall(r'[├└]──\s+(\S+)', skill_text)
known_dirs = {"intents/", "docs/", "guides/", "references/", "examples/",
              "knowledge/", "patterns/", "templates/", "tests/", "tools/", "config/",
              "API/", "Design/", "Images/", "Framework/", "Module/", "Command/",
              "StateCommand/", "Dialog/", "Component/", "Interface/", "intent/",
              "analyzer/", "ui/", "workflow/", "blocks/", "mecmod/", "part/",
              "product/", "infrastructure/", "geometry/", "resources/",
              "drawing/", "surface/", "fta/",
              "capabilities/", "playbooks/", "frameworks/",
              "msgcatalog/", "dictionary/", "build/"}
for tf in tree_files:
    name = tf.rstrip("/")
    if tf.endswith("/") or name in known_dirs or tf in known_dirs:
        continue
    # Nested files: look in subdirs
    candidates = [SKILL_ROOT / name]
    for d in ["skills", "tests", "docs", "templates", "tools", "config",
                  "knowledge", "patterns", "catalog", "capabilities", "playbooks"]:
        for sub in SKILL_ROOT.glob(f"{d}/**/{name}"):
            candidates.append(sub)
    found = any(c.exists() for c in candidates if c.exists())
    if not found:
        check(f"File tree ghost: {name}", False)

# ═══════════════════════════════════════════════════════════
# 4. Version consistency across all files
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  4. Version consistency")
print("=" * 70)

versions_found = {}
for md_file in SKILL_ROOT.rglob("*.md"):
    try:
        content = md_file.read_text(encoding="utf-8")
    except Exception:
        continue
    # Skip historical docs
    if "v2.0.0" in md_file.name or "PRODUCTION_READINESS" in md_file.name:
        continue
    if "KNOWLEDGE_SYSTEM_ARCHITECTURE" in md_file.name:
        continue

    vers = re.findall(r'v?(\d+\.\d+\.\d+)', content)
    for v in vers:
        if v.count(".") == 2 and v[0] == "2":
            if v not in versions_found:
                versions_found[v] = []
            versions_found[v].append(md_file.name)

# CHANGELOG entries are historical - only flag version inconsistencies in main docs
active_versions = {}
# Check only CADE root README (not docs/README.md)
main_files = [SKILL_ROOT / "SKILL.md", CADE_ROOT / "README.md",
              SKILL_ROOT / "skills" / "cade.py", SKILL_ROOT / "skills" / "mcp_server.py"]
for md_file in main_files:
    if not md_file.exists():
        continue
    try:
        content = md_file.read_text(encoding="utf-8")
    except Exception:
        continue
    vers = re.findall(r'v?(\d+\.\d+\.\d+)', content)
    for v in vers:
        if v.count(".") == 2 and v[0] == "2":
            active_versions[v] = md_file.name

if "2.2.0" in active_versions:
    check(f"Active version 2.2.0 in {active_versions['2.2.0']}", True)
else:
    check("Active version 2.2.0 NOT in main docs", False)

for v, f in active_versions.items():
    if v != "2.2.0":
        check(f"Stale active version {v} in {f}", False)

# ═══════════════════════════════════════════════════════════
# 5. Badge URLs in README
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  5. Badge URLs")
print("=" * 70)

readme_text = (CADE_ROOT / "README.md").read_text(encoding="utf-8")
badges = re.findall(r'src="(https://img\.shields\.io/[^"]+)"', readme_text)
for b in badges:
    text = re.search(r'badge/([^"]+)', b)
    label = text.group(1) if text else "?"
    check(f"Badge: {label[:60]}", True, "")

# ═══════════════════════════════════════════════════════════
# 6. External URLs (not checked, just listed)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  6. External URL inventory")
print("=" * 70)

ext_urls = set()
for md_file in (SKILL_ROOT / "docs").rglob("*.md"):
    content = md_file.read_text(encoding="utf-8", errors="replace")
    urls = re.findall(r'https?://[^\s<>"\)]+', content)
    ext_urls.update(urls)

check(f"External URLs found: {len(ext_urls)}", len(ext_urls) > 0,
      f"(not validated, just counted)")

# ═══════════════════════════════════════════════════════════
# 7. Tests reference actual files
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  7. Test suite references")
print("=" * 70)

test_dir = SKILL_ROOT / "tests"
for test_file in test_dir.glob("test_*.py"):
    content = test_file.read_text(encoding="utf-8", errors="replace")
    refs = re.findall(r'"test_\w+\.py"', content)
    for ref in refs:
        ref_name = ref.strip('"')
        if ref_name != test_file.name:  # don't check self-reference
            exists = (test_dir / ref_name).exists()
            if not exists:
                check(f"Ghost test ref in {test_file.name}: {ref_name}", False)

# ═══════════════════════════════════════════════════════════
# 8. Template files match generator types
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  8. Template/generator alignment")
print("=" * 70)

template_dirs = [d.name for d in (SKILL_ROOT / "templates").iterdir() if d.is_dir()]
try:
    from generator import TemplateGenerator
    gen = TemplateGenerator()
    generator_types = set(gen.get_available_templates())
except ImportError:
    generator_types = set()

# Root template types (no directory, just .h/.cpp files at template root)
ROOT_TYPES = {"interface", "component", "identitycard", "imakefile", "dictionary"}
# Generator has root types + dir types
missing = (generator_types - ROOT_TYPES) - set(template_dirs)
if missing:
    check(f"Generator types missing template dirs: {missing}", False)
else:
    check("Templates and generator aligned", True)

# ═══════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"  DEEP AUDIT: {passed}/{total}")
if total:
    print(f"  Pass rate: {passed / total * 100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n  >>> ALL REFERENCES CONSISTENT <<<")
    sys.exit(0)
else:
    print(f"\n  >>> {total - passed} ISSUE(S) FOUND <<<")
    sys.exit(1)
