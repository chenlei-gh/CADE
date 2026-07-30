#!/usr/bin/env python3
"""
Phantom Capability Checker
============================
Scan skills/**/*.py for public functions and CLI commands, then verify
each against the five-point capability contract: file / entry / test /
doc / runtime path.  A capability missing BOTH an entry point AND a
runtime path is flagged as PHANTOM.

Pure stdlib.  Run:  python tools/check_capabilities.py
"""

import ast
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
SKILLS_DIR = SKILL_ROOT / "skills"
TESTS_DIR = SKILL_ROOT / "tests"
SKILL_MD = SKILL_ROOT / "SKILL.md"
# Lifecycle declarations (can the capability be used?).  Routing contract
# (which capability handles an intent) lives at SKILL_ROOT/capabilities.yaml.
LIFECYCLE = SKILLS_DIR / "lifecycle.yaml"
CONTRACT = SKILL_ROOT / "capabilities.yaml"


def collect_registry():
    """Parse skills/lifecycle.yaml into {file_path: declared_state}.

    The registry is the DECLARATION layer of the capability contract (the
    'Capability != File' model); this checker is the DETECTION layer.  We map
    each capability's `implementation` files to its declared `status`/`action`
    so a capability whose code lives in a declared-unavailable file is
    reported against intent, not mistaken for an accidental phantom.

    Pure-stdlib line parser — the project deliberately has no PyYAML dep and
    parses SKILL.md frontmatter by hand, so we do the same for this small,
    fixed-structure file.  Only reads status / action / implementation keys."""
    # Map BOTH the capability name and its implementation files to the
    # declared state.  Capability-name matching is precise (a file can host
    # several capabilities — services.py holds both the unavailable
    # expose_service and the active create_component_with_interfaces); file
    # matching is kept as a fallback for whole-file experimental modules.
    declared = {"by_name": {}, "by_file": {}}
    if not LIFECYCLE.exists():
        return declared
    cur_cap = None
    cur_status = None
    cur_action = None
    in_impl = False
    for raw in LIFECYCLE.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        # capability key: 2-space indented 'name:' with no value
        if indent == 2 and stripped.endswith(":") and not stripped.startswith("-"):
            cur_cap = stripped[:-1].strip()
            cur_status = None
            cur_action = None
            in_impl = False
        elif stripped.startswith("status:"):
            cur_status = stripped.split(":", 1)[1].strip()
            in_impl = False
        elif stripped.startswith("action:"):
            cur_action = stripped.split(":", 1)[1].strip()
            in_impl = False
        elif stripped.startswith("implementation:"):
            in_impl = True
        elif in_impl and stripped.startswith("- "):
            f = stripped[2:].strip()
            declared["by_file"][f] = {"status": cur_status, "action": cur_action}
        elif indent == 0:
            in_impl = False
            cur_cap = None
        if cur_cap and cur_status:
            declared["by_name"][cur_cap] = {"status": cur_status,
                                            "action": cur_action}
    return declared


# ────────────────────────────────────────────────────────────────────
# Routing contract checks (SKILL_ROOT/capabilities.yaml)
# ────────────────────────────────────────────────────────────────────
# v0 contract fields.  Anything else is a WARNING (exploration is allowed),
# not an error — the schema must not block v0 iteration.
CONTRACT_FIELDS = {"name", "description", "triggers", "bindings",
                   "forbidden", "note"}
# Binding types the router understands, in agent-priority order.
BINDING_TYPES = ("mcp", "cli", "python")


def parse_contract():
    """Parse the routing contract into [{name, triggers, bindings, ...}].

    Same pure-stdlib line style as collect_registry (no PyYAML dep).  The
    contract is a fixed-structure list under a top-level `capabilities:` key;
    each entry starts at '- name:' (2-space indent), scalar fields are
    4-space indented, list fields (triggers/forbidden) carry 6-space '- '
    items, and `bindings:` maps type -> command string at 6-space indent.
    Unknown fields are captured in `_unknown` for the schema warning."""
    caps = []
    if not CONTRACT.exists():
        return caps
    cur = None
    list_field = None      # 'triggers' | 'forbidden' | None
    in_bindings = False
    for raw in CONTRACT.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            # top-level key (e.g. 'capabilities:') — close any open entry
            if cur:
                caps.append(cur)
                cur = None
            list_field = None
            in_bindings = False
            continue
        if indent == 2 and stripped.startswith("- "):
            if cur:
                caps.append(cur)
            cur = {"_unknown": [], "triggers": [], "forbidden": [],
                   "bindings": {}, "_dup_list": [], "_dup_bindings": []}
            list_field = None
            in_bindings = False
            body = stripped[2:]
            if ":" in body:
                k, v = body.split(":", 1)
                cur[k.strip()] = v.strip()
            continue
        if cur is None:
            continue
        if indent == 4 and stripped.endswith(":"):
            key = stripped[:-1]
            if key == "bindings":
                in_bindings = True
                list_field = None
            else:
                list_field = key if key in ("triggers", "forbidden") else None
                in_bindings = False
                if key not in CONTRACT_FIELDS:
                    cur["_unknown"].append(key)
            continue
        if indent == 4 and ":" in stripped:
            k, v = stripped.split(":", 1)
            k, v = k.strip(), v.strip()
            if k in CONTRACT_FIELDS:
                cur[k] = v
            else:
                cur["_unknown"].append(k)
            list_field = None
            in_bindings = False
            continue
        if in_bindings and indent >= 6 and ":" in stripped:
            k, v = stripped.split(":", 1)
            k = k.strip()
            if k in cur["bindings"]:
                cur["_dup_bindings"].append(k)
            cur["bindings"][k] = v.strip()
            continue
        if list_field and indent >= 6 and stripped.startswith("- "):
            item = stripped[2:].strip()
            if item in cur[list_field]:
                cur["_dup_list"].append(f"{list_field}:{item}")
            cur[list_field].append(item)
            continue
    if cur:
        caps.append(cur)
    return caps


def parse_binding(raw):
    """Parse one binding command string into a typed target.

    Returns {type, ...} so the checker can validate each kind without
    hard-coding any single executable:
      cli 'cade build'                    -> {exe:'cade',    cmd:'build'}
      cli 'python skills/header_map.py..' -> {exe:'python',  script:Path}
      cli 'sh sync_agents.sh'             -> {exe:'sh',      script:Path}
      python 'build.sync_runtime_view'    -> {module:'build', func:'sync_runtime_view'}
      mcp  'cade.build'                   -> {server:'cade', tool:'build'}
    Unknown shapes return {'raw': ...} and validate as unverifiable."""
    parts = raw.split()
    if not parts:
        return {"raw": raw}
    exe = parts[0]
    if exe == "cade" and len(parts) >= 2:
        return {"exe": "cade", "cmd": parts[1]}
    if exe == "python" and len(parts) >= 2 and parts[1].endswith(".py"):
        return {"exe": "python", "script": parts[1]}
    if exe == "sh" and len(parts) >= 2:
        return {"exe": "sh", "script": parts[1]}
    return {"raw": raw}


def _defined_functions(py_path):
    """Top-level function names defined in one python file (ast, safe)."""
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"),
                         filename=str(py_path))
    except (SyntaxError, OSError):
        return set()
    return {n.name for n in ast.iter_child_nodes(tree)
            if isinstance(n, ast.FunctionDef)}


def check_contract_schema(caps):
    """Field whitelist + required-field presence + contract integrity.

    Integrity checks are deliberately limited to structural duplicates
    (duplicate triggers, duplicate binding keys) -- NOT semantic overlap
    between different capabilities' triggers.  Judging whether two trigger
    phrases 'mean the same thing' is an NLP problem, not a contract-
    integrity problem; encoding it here would turn the checker into a
    second router that itself needs maintenance.  (errors, warnings)"""
    errors, warnings = [], []
    for c in caps:
        name = c.get("name", "<unnamed>")
        for k in c.get("_unknown", []):
            warnings.append(f"{name}: unknown field '{k}' "
                            f"(v0 fields: {sorted(CONTRACT_FIELDS)})")
        if not c.get("name"):
            errors.append("contract entry missing 'name'")
        if not c.get("triggers"):
            errors.append(f"{name}: no triggers (router cannot match it)")
        if not c.get("bindings"):
            errors.append(f"{name}: no bindings (router cannot invoke it)")
        for bt in c.get("bindings", {}):
            if bt not in BINDING_TYPES:
                warnings.append(f"{name}: unknown binding type '{bt}' "
                                f"(known: {list(BINDING_TYPES)})")
        for dup in c.get("_dup_list", []):
            errors.append(f"{name}: duplicate list entry '{dup}'")
        for dup in c.get("_dup_bindings", []):
            errors.append(f"{name}: duplicate binding key '{dup}' "
                          f"(second declaration silently overwrote the first)")
    return errors, warnings


def check_contract_bindings(caps):
    """Every declared binding target must actually exist.  (errors,)"""
    errors = []
    cade_src = (SKILLS_DIR / "cade.py").read_text(encoding="utf-8") \
        if (SKILLS_DIR / "cade.py").exists() else ""
    cade_cmds = set(re.findall(r'cmd == "([^"]+)"', cade_src))
    for c in caps:
        name = c.get("name", "<unnamed>")
        for btype, raw in c.get("bindings", {}).items():
            if btype == "cli":
                t = parse_binding(raw)
                if t.get("exe") == "cade":
                    if t["cmd"] not in cade_cmds:
                        errors.append(f"{name}: cli binding 'cade {t['cmd']}' "
                                      f"has no dispatch entry in cade.py")
                elif "script" in t:
                    # script paths are skill-root relative; ../../ escape ok
                    p = (SKILL_ROOT / t["script"]).resolve()
                    if not p.exists():
                        errors.append(f"{name}: cli script '{t['script']}' "
                                      f"not found (resolved: {p})")
                else:
                    errors.append(f"{name}: cli binding '{raw}' has an "
                                  f"unverifiable shape")
            elif btype == "python":
                if "." not in raw:
                    errors.append(f"{name}: python binding '{raw}' is not "
                                  f"module.func")
                    continue
                mod, func = raw.rsplit(".", 1)
                py = SKILLS_DIR / f"{mod}.py"
                if not py.exists():
                    errors.append(f"{name}: python module '{mod}.py' not "
                                  f"found in skills/")
                elif func not in _defined_functions(py):
                    errors.append(f"{name}: '{mod}.py' defines no "
                                  f"function '{func}'")
            elif btype == "mcp":
                # MCP bindings are validated by the MCP server, not here.
                pass
    return (errors,)


def check_cross_reference(caps, registry):
    """Same-named capability should exist in both lifecycle and contract.

    One-sided declarations are a WARNING, not an error: a routing capability
    may have no lifecycle entry (all 7 v0 capabilities are implicitly active)
    and a lifecycle entry may have no route yet (unavailable/experimental).
    The warning exists so the two files cannot silently drift apart."""
    warnings = []
    contract_names = {c.get("name") for c in caps if c.get("name")}
    lifecycle_names = set(registry.get("by_name", {}))
    for n in sorted(contract_names - lifecycle_names):
        warnings.append(f"{n}: in routing contract but not lifecycle.yaml "
                        f"(implicitly active — ok for v0)")
    for n in sorted(lifecycle_names - contract_names):
        warnings.append(f"{n}: in lifecycle.yaml but not routing contract "
                        f"(unroutable by intent — ok if unavailable/"
                        f"experimental)")
    return warnings


def collect_public_functions():
    """Return {name: file} for every top-level public def in skills/."""
    caps = {}
    for py in sorted(SKILLS_DIR.rglob("*.py")):
        if py.name.startswith("_"):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError:
            continue
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                rel = py.relative_to(SKILL_ROOT)
                caps.setdefault(node.name, str(rel))
    return caps


def collect_guarded_api():
    """Names protected by the test_full_regression public-API contract.

    Three guarded forms, all deliberate API-surface protection, not dead code:
      1. every string in the MODULES dict  ("env": ["CAAEnvironment", ...])
         — the test iterates it and asserts each name exists in its module
      2. every attribute in callable(mod.name) checks
         — the test asserts the symbol is present AND callable
      3. every string passed to getattr(mod, "name") where the result feeds a
         callable() check — the for-loop form of (2), e.g.
             for fn_name in ["run_catia_with_env", ...]:
                 check(..., callable(getattr(run_mod, fn_name)))
    A name on this list is a CONTRACT-GUARDED public API: removing it breaks
    the suite, so it is reported as GUARDED, never PHANTOM."""
    guarded = set()
    tfr = TESTS_DIR / "test_full_regression.py"
    if not tfr.exists():
        return guarded
    try:
        tree = ast.parse(tfr.read_text(encoding="utf-8"), filename=str(tfr))
    except SyntaxError:
        return guarded
    for node in ast.walk(tree):
        # MODULES = { "mod": ["a", "b"], ... } — collect every string member
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "MODULES"
                   for t in node.targets):
                for sub in ast.walk(node.value):
                    if isinstance(sub, ast.Constant) \
                            and isinstance(sub.value, str):
                        if re.fullmatch(r"[A-Za-z_]\w*", sub.value):
                            guarded.add(sub.value)
        # callable(ref_mod.extract_interface) — collect the attribute name
        if isinstance(node, ast.Call) \
                and isinstance(node.func, ast.Name) \
                and node.func.id == "callable" and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Attribute):
                guarded.add(arg.attr)
            elif isinstance(arg, ast.Name):
                guarded.add(arg.id)
        # getattr(run_mod, "run_catia_with_env") — string form of the contract
        if isinstance(node, ast.Call) \
                and isinstance(node.func, ast.Name) \
                and node.func.id == "getattr" and len(node.args) >= 2:
            s = node.args[1]
            if isinstance(s, ast.Constant) and isinstance(s.value, str) \
                    and re.fullmatch(r"[A-Za-z_]\w*", s.value):
                guarded.add(s.value)
        # for fn_name in ["run_catia_with_env", ...]: ... getattr(mod, fn_name)
        # The contract list is the for-loop's iterable; the names are verified
        # via getattr(mod, loop_var) inside the body.
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            loop_var = node.target.id
            uses_getattr = any(
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Name)
                and sub.func.id == "getattr"
                and len(sub.args) >= 2
                and isinstance(sub.args[1], ast.Name)
                and sub.args[1].id == loop_var
                for sub in ast.walk(node)
            )
            if uses_getattr:
                for sub in ast.walk(node.iter):
                    if isinstance(sub, ast.Constant) \
                            and isinstance(sub.value, str) \
                            and re.fullmatch(r"[A-Za-z_]\w*", sub.value):
                        guarded.add(sub.value)
    return guarded


def collect_defined_symbols():
    """All top-level public names defined in skills/ — functions AND classes.
    Used only for the stale-doc check: a documented export that resolves to a
    class (CommandSpec, FixPlan, ActionContext...) is present in code even
    though collect_public_functions() (functions only) doesn't track it."""
    names = set()
    for py in sorted(SKILLS_DIR.rglob("*.py")):
        if py.name.startswith("_"):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError:
            continue
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) \
                    and not node.name.startswith("_"):
                names.add(node.name)
    return names


def collect_cli_commands():
    """Return {cmd_string: line_no} from cade.py main() elif branches."""
    cade = SKILLS_DIR / "cade.py"
    cmds = {}
    if not cade.exists():
        return cmds
    for i, line in enumerate(cade.read_text(encoding="utf-8").splitlines(), 1):
        m = re.search(r'elif cmd == "(\w+)"', line)
        if m:
            cmds[m.group(1)] = i
    return cmds


def collect_references():
    """Build lookup sets for entry / test / doc references."""
    entry_files = [SKILLS_DIR / f for f in ("cade.py", "kernel.py", "mcp_server.py")]
    entry_src = " ".join(
        f.read_text(encoding="utf-8") for f in entry_files if f.exists()
    )
    test_src = " ".join(
        f.read_text(encoding="utf-8")
        for f in TESTS_DIR.rglob("*.py")
        if f.is_file()
    )
    doc_src = SKILL_MD.read_text(encoding="utf-8") if SKILL_MD.exists() else ""
    return entry_src, test_src, doc_src


def collect_import_graph():
    """Map each skills module to the set of names it imports from OTHER
    skills modules.  A function imported by any sibling module has a runtime
    path (it's a library API used by the codebase), even if no CLI/kernel
    calls it directly.  This is the single biggest source of false positives
    — build.py's mk* wrappers, actions.py's create_* APIs, utils.py helpers
    are all imported by other modules, not invoked from cade/kernel."""
    imported_names = set()
    module_stems = {p.stem for p in SKILLS_DIR.rglob("*.py") if p.name != "__init__.py"}
    for py in SKILLS_DIR.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = (node.module or "").lstrip(".")
                root = mod.split(".")[0] if mod else ""
                if root in module_stems or mod.startswith(("intents", "intent")):
                    for alias in node.names:
                        imported_names.add(alias.name)
    return imported_names


def collect_intra_module_calls():
    """Map each skills file to the set of top-level function names that are
    CALLED by other functions defined in the SAME file.  Catches the false
    positive where a helper like run.py's check_process_running is invoked by
    start_catia_runtime/stop_catia in the same module — a module never imports
    itself, so the import graph can't see this runtime path."""
    # file_path -> set of names called within that file
    intra = {}
    for py in sorted(SKILLS_DIR.rglob("*.py")):
        if py.name.startswith("_"):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError:
            continue
        rel = str(py.relative_to(SKILL_ROOT))
        called = set()
        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            # Names referenced anywhere inside this function's body
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    called.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    called.add(sub.attr)
        intra[rel] = called
    return intra


def collect_doc_exports():
    """Set of names exposed via SKILL.md `from <module> import (...)` blocks.

    These are the *documented library API surface* — CADE deliberately teaches
    the AI to call them via direct import (e.g. build.py's 35 mk* wrappers,
    actions.py's create_* APIs), BYPASSING kernel/cade routing.  For this class
    of capability the doc import block IS the entry point and the documented
    call IS the runtime path, so the cade/kernel/import-graph standard does not
    apply.  Returns {name: module} so we can also detect the reverse phantom:
    a name documented but no longer present in code (e.g. workspace_build_config)."""
    exports = {}
    if not SKILL_MD.exists():
        return exports
    lines = SKILL_MD.read_text(encoding="utf-8").splitlines()
    i = 0
    open_re = re.compile(
        r"from\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s+import\s+(.*)$")
    while i < len(lines):
        m = open_re.search(lines[i])
        if not m:
            i += 1
            continue
        module, rest = m.group(1), m.group(2)
        if rest.startswith("("):
            # multi-line block.  A comment line like `# 编译 (7)` contains a
            # ')' that must NOT close the block, so strip each line's comment
            # BEFORE testing for the closing paren.  Accumulate only the
            # code portion (text before '#') of every line until a line whose
            # comment-stripped content contains ')'.
            body_lines = []
            first = rest[1:].split("#")[0]
            body_lines.append(first)
            while ")" not in "".join(body_lines) and i + 1 < len(lines):
                i += 1
                body_lines.append(lines[i].split("#")[0])
            body = ",".join(body_lines).replace(")", "")
            for name in body.split(","):
                name = name.strip()
                if re.fullmatch(r"[A-Za-z_]\w*", name):
                    exports[name] = module
        else:
            # single-line:  from run import start_catia_runtime, stop_catia
            for name in rest.split(","):
                name = name.split("#")[0].strip()
                if re.fullmatch(r"[A-Za-z_]\w*", name):
                    exports.setdefault(name, module)
        i += 1
    return exports


def collect_test_calls():
    """Set of names that tests invoke as a real call — `name(...)` or
    `mod.name(...)`.  A test that directly calls a function IS a runtime path
    (it's how apply_fixplan / run_catia_with_env are exercised), distinct from
    a test that merely mentions the name in a string list like LAYERS.  We
    parse each test file's AST and collect both bare calls and attribute calls."""
    called = set()
    for py in TESTS_DIR.rglob("*.py"):
        if not py.is_file():
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
    return called


def check(name, file_path, entry_src, test_src, doc_src,
          imported_names, intra_calls, test_calls, doc_exports, guarded,
          registry):
    """Check one capability against the five-point contract."""
    has_entry = name in entry_src
    has_test = name in test_src
    has_doc = name in doc_src
    # Runtime path has four forms, any one is sufficient:
    #  1. reachable from kernel/cade (direct dispatch)
    #  2. imported by another skills module (library API used by the codebase)
    #  3. called by another function in the SAME module (intra-module helper)
    #  4. directly called by a test (test-driven execution path)
    kernel_src = (SKILLS_DIR / "kernel.py").read_text(encoding="utf-8")
    cade_src = (SKILLS_DIR / "cade.py").read_text(encoding="utf-8")
    has_runtime = (
        name in kernel_src
        or name in cade_src
        or name in imported_names
        or name in intra_calls.get(file_path, set())
        or name in test_calls
    )
    # A documented library API (exposed via SKILL.md import block) satisfies
    # BOTH entry and runtime by design — the AI is taught to import it directly.
    doc_exported = name in doc_exports
    if doc_exported:
        has_entry = True
        has_runtime = True
    status = "OK" if (has_entry or has_runtime) else "PHANTOM"
    # Contract-guarded public API: no live entry/runtime path, but the
    # regression suite asserts it exists and stays callable.  Report it
    # distinctly so it is never mistaken for a deletable phantom.
    if status == "PHANTOM" and name in guarded:
        status = "GUARDED"
    # Declaration layer: if this capability's file is declared in the registry
    # as unavailable/experimental, surface that intent.  An OK capability in a
    # declared-unavailable file is NOT an ordinary production capability — it
    # is a deliberate design state, so say so instead of leaving it ambiguous.
    rel = file_path.replace("\\", "/")
    if rel.startswith("skills/"):
        rel = rel[len("skills/"):]
    # Capability-name match is precise and applies to any declared status.
    # File fallback is ONLY safe for 'experimental' (a whole-file research
    # module like specification.py); it must NOT be used for 'unavailable',
    # which is a single-capability property — services.py hosts both the
    # unavailable expose_service and the active create_component_with_interfaces,
    # so a file-level unavailable tag would smear the active capability.
    declared = registry.get("by_name", {}).get(name)
    if not declared:
        by_file = registry.get("by_file", {}).get(rel)
        if by_file and by_file.get("status") == "experimental":
            declared = by_file
    if declared and declared.get("status") in ("unavailable", "experimental"):
        status = f"DECL-{declared['status']}"
    return {
        "name": name,
        "file": file_path,
        "entry": ("doc" if doc_exported and name not in entry_src
                  else ("Y" if has_entry else "-")),
        "test": "Y" if has_test else "-",
        "doc": "Y" if has_doc else "-",
        "runtime": ("doc" if doc_exported and not (
            name in kernel_src or name in cade_src or name in imported_names)
            else ("Y" if has_runtime else "-")),
        "status": status,
    }


def main():
    caps = collect_public_functions()
    cli_cmds = collect_cli_commands()
    entry_src, test_src, doc_src = collect_references()
    imported_names = collect_import_graph()
    intra_calls = collect_intra_module_calls()
    test_calls = collect_test_calls()
    doc_exports = collect_doc_exports()
    guarded = collect_guarded_api()
    registry = collect_registry()

    rows = []
    for name, fpath in sorted(caps.items()):
        rows.append(check(name, fpath, entry_src, test_src, doc_src,
                          imported_names, intra_calls, test_calls,
                          doc_exports, guarded, registry))

    # CLI commands are capabilities too
    for cmd, lineno in sorted(cli_cmds.items()):
        rows.append(check(cmd, f"cade.py:L{lineno}", entry_src, test_src,
                        doc_src, imported_names, intra_calls, test_calls,
                        doc_exports, guarded, registry))

    # Reverse phantom: documented in SKILL.md but absent from code.
    # Presence = a function, a CLI command, OR a class (classes aren't in caps).
    code_names = set(caps) | set(cli_cmds) | collect_defined_symbols()
    stale_docs = sorted(n for n in doc_exports if n not in code_names)

    # ── Routing contract checks (capabilities.yaml ↔ reality) ──
    contract = parse_contract()
    schema_errors, schema_warnings = check_contract_schema(contract)
    (binding_errors,) = check_contract_bindings(contract)
    xref_warnings = check_cross_reference(contract, registry)
    contract_errors = schema_errors + binding_errors
    contract_warnings = schema_warnings + xref_warnings

    # Print matrix
    hdr = f"{'Name':<40s} {'File':<40s} {'Entry':<6s} {'Test':<6s} {'Doc':<6s} {'Runtime':<8s} {'Status'}"
    print("=" * len(hdr))
    print("  CADE Phantom Capability Matrix")
    print("=" * len(hdr))
    print(hdr)
    print("-" * len(hdr))
    phantom_count = 0
    guarded_count = 0
    for r in rows:
        print(
            f"{r['name']:<40s} {r['file']:<40s} {r['entry']:<6s} "
            f"{r['test']:<6s} {r['doc']:<6s} {r['runtime']:<8s} {r['status']}"
        )
        if r["status"] == "PHANTOM":
            phantom_count += 1
        elif r["status"] == "GUARDED":
            guarded_count += 1
    print("-" * len(hdr))
    print(f"  Total: {len(rows)} capabilities, "
          f"{phantom_count} PHANTOM, {guarded_count} GUARDED")
    if stale_docs:
        print(f"  STALE DOC (documented but missing from code): "
              f"{len(stale_docs)}")
        for n in stale_docs:
            print(f"    - {n}  (from {doc_exports[n]} import ...)")
    print("=" * len(hdr))

    # ── Routing contract section ──
    print(f"\n  Routing Contract ({CONTRACT.name}): "
          f"{len(contract)} capabilities")
    if contract_errors:
        print(f"  CONTRACT ERRORS (binding promises a non-existent path):")
        for e in contract_errors:
            print(f"    ✗ {e}")
    if contract_warnings:
        print(f"  contract warnings (non-blocking):")
        for w in contract_warnings:
            print(f"    ! {w}")
    if not contract_errors and not contract_warnings:
        print("  contract clean")
    print("=" * len(hdr))

    # Stable success marker for the master-test verify string.  Printed only
    # when the contract is fully clean so the suite does not depend on the
    # (changing) capability/GUARDED counts.
    has_error = phantom_count or stale_docs or contract_errors
    if not has_error:
        print("CAPABILITY CONTRACT OK")

    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())
