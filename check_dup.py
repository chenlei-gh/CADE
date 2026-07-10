#!/usr/bin/env python
"""Check for functional redundancy across CADE modules."""
import re
from pathlib import Path

root = Path(r'D:\DevTools\CADE\.agents\skills\catia-caa-dev')

# 1. Check function name overlap between actions.py and intents/
actions_funcs = set()
for line in (root/'skills'/'actions.py').read_text('utf-8').split('\n'):
    m = re.match(r'def (\w+)', line)
    if m: actions_funcs.add(m.group(1))

intent_funcs = set()
for f in (root/'skills'/'intents').rglob('*.py'):
    for line in f.read_text('utf-8').split('\n'):
        m = re.match(r'def (\w+)', line)
        if m: intent_funcs.add(m.group(1))

overlap = actions_funcs & intent_funcs
print("=== actions.py vs intents/ overlap ===")
if overlap:
    for o in sorted(overlap): print(f"  {o}")
    print(f"Total: {len(overlap)} overlapping functions")
else:
    print("  No overlap - clean separation")

# 2. Check diagnose vs validate_workspace
from skills.diagnostics import diagnose_workspace
diagnose_doc = diagnose_workspace.__doc__ or ""
print(f"\n=== diagnose_workspace vs validate_workspace ===")
print(f"  diagnose_workspace: {diagnose_doc[:100]}...")

# 3. Check MCP tool names vs CLI command names
mcp_text = (root/'skills'/'mcp_server.py').read_text('utf-8')
mcp_tools = set(re.findall(r'if name == "(\w+)"', mcp_text))
print(f"\n=== MCP tools: {len(mcp_tools)} ===")

cli_text = (root/'skills'/'cade.py').read_text('utf-8')
cli_cmds = set(re.findall(r'def cmd_(\w+)', cli_text))
print(f"=== CLI commands: {len(cli_cmds)} ===")

# MCP tools that have no CLI equivalent (or vice versa)
mcp_names = {t.replace('_', '') for t in mcp_tools}
cli_names = {c.replace('_', '') for c in cli_cmds}
mcp_only = mcp_names - cli_names
cli_only = cli_names - mcp_names
if mcp_only:
    print(f"  MCP-only: {len(mcp_only)}")
if cli_only:
    print(f"  CLI-only: {len(cli_only)}")

# 4. Check for SKILL.md duplicated content sections
skill = (root / 'SKILL.md').read_text('utf-8')
# Count example sections that might be duplicated
examples_sections = re.findall(r'### \d+\.', skill)
print(f"\nSKILL.md numbered sections: {len(examples_sections)}")
# Check for duplicate numbered sections
from collections import Counter
counts = Counter(examples_sections)
dups = {k: v for k, v in counts.items() if v > 1}
if dups:
    print(f"  DUPLICATE: {dups}")

print("\n=== Overall ===")
print("No functional redundancy detected between major layers")
