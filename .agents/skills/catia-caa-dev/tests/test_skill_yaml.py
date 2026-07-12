#!/usr/bin/env python3
"""
SKILL.md YAML Frontmatter Validity Test
=========================================
Verify that the YAML frontmatter in SKILL.md is syntactically valid.
Catches issues like unquoted colons that break skill loading.
"""

import re
from pathlib import Path

SKILL = Path(__file__).parent.parent

total = passed = 0


def ck(label, ok, detail=""):
    global total, passed
    total += 1
    passed += 1 if ok else 0
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  SKILL.md YAML Frontmatter Test")
print("=" * 60)

skill_path = SKILL / "SKILL.md"
content = skill_path.read_text(encoding="utf-8")

# [1] Has frontmatter block
print("\n[1] Frontmatter block")
parts = content.split("---", 2)
ck("starts with ---", content.strip().startswith("---"))
ck("has closing ---", len(parts) >= 3, f"sections={len(parts)}")

yaml_str = parts[1] if len(parts) >= 3 else ""
lines = yaml_str.strip().split("\n")
ck("has content", len(lines) > 1, f"lines={len(lines)}")

# [2] Required keys
print("\n[2] Required keys")
required = ["name", "description", "triggers"]
for key in required:
    ck(f"has '{key}'", f"{key}:" in yaml_str,
       "missing" if f"{key}:" not in yaml_str else "present")

# [3] No unquoted colon-space in scalar values
print("\n[3] Colon safety in scalars")
yaml_issues = 0
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("-"):
        continue
    if ":" not in stripped:
        continue
    key, _, val = stripped.partition(": ")
    val = val.strip()
    # If value is quoted, colons inside are safe
    if val.startswith('"') and val.endswith('"'):
        continue
    if val.startswith("'") and val.endswith("'"):
        continue
    # Check for bare colon+space patterns in unquoted values
    # that could be misparsed as nested keys
    depth = 0
    for ch in val:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        elif ch == ":" and depth == 0:
            yaml_issues += 1
            ck(f"line {i}: unquoted colon in value", False,
               stripped[:60])

ck("no YAML colon issues", yaml_issues == 0,
   f"{yaml_issues} issue(s)" if yaml_issues else "clean")

# [4] name field
print("\n[4] name field")
m = re.search(r"^name:\s*(.+)$", yaml_str, re.MULTILINE)
ck("name exists", m is not None)
if m:
    name = m.group(1).strip().strip('"')
    ck("name is catia-caa-dev", name == "catia-caa-dev", name)

# [5] description field
print("\n[5] description field")
m = re.search(r"^description:\s*(.+)$", yaml_str, re.MULTILINE)
ck("description exists", m is not None)
if m:
    desc = m.group(1).strip()
    ck("description is quoted", desc.startswith('"'), "quoted OK" if desc.startswith('"') else "UNQUOTED")
    ck("description not empty", len(desc) > 20)
    ck("description mentions 3 Mode", "develop/analyze/repair" in desc)
    ck("description mentions Kernel", "Kernel" in desc)

# [6] triggers list
print("\n[6] triggers list")
trigger_lines = []
in_triggers = False
for line in lines:
    if line.strip() == "triggers:":
        in_triggers = True
        continue
    if in_triggers:
        if line.strip().startswith("-"):
            trigger_lines.append(line.strip()[1:].strip())
        elif line.strip() and not line.strip().startswith("-"):
            break

ck("triggers list not empty", len(trigger_lines) > 0, f"{len(trigger_lines)} items")
ck("triggers >= 10", len(trigger_lines) >= 10, f"{len(trigger_lines)} items")
ck("has 'CAA command'", any("CAA command" in t for t in trigger_lines))

print(f"\n{'='*60}")
print(f"  Total: {passed}/{total} passed")
print(f"{'='*60}")
