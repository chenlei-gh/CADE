"""CATIA CAA Atomic Development Actions
=====================================
High-level development actions with ChangeSet preview.

Design principle:
  AI calls actions with INTENT, not template names.
  Each action = validate + plan → ChangeSet → review → apply.

Atomic Skills (what AI actually calls):
  Query:      analyze_workspace, list_modules, list_commands, list_workbenches
  Create:     create_framework, create_module, create_command, create_workbench,
              create_dialog, create_interface, create_component, add_command_to_workbench
  Delete:     delete_command, delete_module (removes ALL related files)
  Build:      build_workspace, run_catia

Every Create has a corresponding Delete = reversible.

=====================================
Table of Contents (1123 lines):
=====================================
  [Lines 43-75]    ActionContext class
  [Lines 77-85]    Helper functions (_error, _result, _apply_and_return, _fill)

  QUERY APIs:
  [Lines 126-195]  analyze_workspace()     - Full workspace analysis
  [Lines 198-226]  list_modules()          - List all modules
  [Lines 229-267]  list_commands()         - List all commands
  [Lines 270-301]  list_workbenches()      - List all workbenches
  [Lines 304-335]  list_interfaces()       - List all interfaces

  CREATE APIs:
  [Lines 338-444]  create_framework()      - Create new framework
  [Lines 447-480]  create_module()         - Create new module
  [Lines 483-485]  _module_cs()            - Module changeset helper
  [Lines 591-700]  create_command()        - Create new command
  [Lines 703-800]  create_workbench()      - Create new workbench
  [Lines 803-876]  create_dialog()         - Create new dialog
  [Lines 879-945]  create_interface()      - Create new interface
  [Lines 948-1015] create_component()      - Create new component
  [Lines 1018-1070] add_command_to_workbench() - Add command to workbench

  DELETE APIs:
  [Lines 1073-1100] delete_command()       - Delete command (cascade)
  [Lines 1103-1123] delete_module()        - Delete module (cascade)

Note: This is a Facade module - intentionally consolidated for unified API.
      Splitting would break backward compatibility and increase complexity.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from analyzer import WorkspaceAnalyzer
from changeset import ChangeSet, Patch
from meta_model import (
    Command,
    Dialog,
    Framework,
    Interface,
    Module,
    Visibility,
    Workbench,
    WorkspaceSnapshot,
)
from utils import Logger, output_json, render_template

# ─── ActionContext ───────────────────────────────────────────────


class ActionContext:
    """Shared context: templates, workspace, cached snapshot with invalidation"""

    def __init__(self, workspace_path: str = None):
        self.skill_root = Path(__file__).parent.parent
        self.templates = self.skill_root / "templates"
        self.workspace_root = (
            Path(workspace_path).resolve() if workspace_path else Path.cwd()
        )
        self.logger = Logger("actions.log")
        self.logger.clear()
        self._snapshot = None
        self._snapshot_mtime = 0
        self._cache_ttl = 5
        from meta_model import SnapshotHistory

        self.history = SnapshotHistory()

    @property
    def snapshot(self) -> WorkspaceSnapshot:
        """Get snapshot, with timestamp-based cache invalidation"""
        if self._snapshot is not None and not self._is_stale():
            return self._snapshot
        self._snapshot = WorkspaceAnalyzer(self.workspace_root).analyze()
        self._snapshot_mtime = self._max_file_mtime()
        return self._snapshot

    def refresh(self, force: bool = False, label: str = "") -> WorkspaceSnapshot:
        """Refresh snapshot. Records to history. Use force=True to bypass cache.

        Cache-aware: when the current snapshot is still fresh (no file newer
        than its baseline mtime, within the TTL throttle), it is reused
        instead of re-scanning the whole workspace. This is what makes the
        existing mtime cache actually effective — previously every action
        function unconditionally nulled the snapshot, so one develop request
        re-analyzed the workspace 3-5 times even though nothing changed on
        disk between the sub-steps (ChangeSets only hit disk at apply time).
        """
        if not force and self._snapshot is not None and not self._is_stale():
            # Cache hit: still record to history so audit/telemetry keeps
            # seeing every refresh call (the recorded snapshot is the same
            # object — diff_last_two will report has_changes=False).
            self.history.record(self._snapshot, label or "refresh")
            return self._snapshot
        self._snapshot = None
        snap = self.snapshot
        self.history.record(snap, label or "refresh")
        return snap

    # Build outputs and VCS/backup internals change on every build but are
    # invisible to the analyzer (it only reads src/LocalInterfaces/CNext),
    # so they are pruned from the staleness walk — win_b64 alone can hold
    # tens of thousands of files.
    _PRUNE_DIRS = frozenset(
        {"win_b64", ".caa_backups", ".git", "__pycache__", ".pytest_cache"}
    )

    def _max_file_mtime(self, early_exit_above: float = None) -> float:
        """Get the most recent modification time in the workspace.
        early_exit_above: staleness probe — stop walking once a file newer
        than this value is found. None (the snapshot-baseline mode) computes
        the TRUE max: the old unconditional early-exit compared against the
        still-zero baseline on first build and returned the first file's
        mtime, so nearly every subsequent staleness probe saw "newer" files
        and rebuilt the snapshot for nothing.
        """
        import os

        try:
            max_mtime = 0
            for root, dirs, files in os.walk(str(self.workspace_root)):
                dirs[:] = [d for d in dirs if d not in self._PRUNE_DIRS]
                for f in files:
                    try:
                        mtime = Path(root, f).stat().st_mtime
                        if mtime > max_mtime:
                            max_mtime = mtime
                    except OSError:
                        pass
                if (
                    early_exit_above is not None
                    and max_mtime > early_exit_above
                ):
                    break
            return max_mtime
        except Exception:
            return float("inf")  # Force refresh on error

    def _is_stale(self) -> bool:
        """Check if snapshot is stale (files have changed)"""
        import time

        if time.time() - getattr(self, "_last_check", 0) < self._cache_ttl:
            return False
        self._last_check = time.time()
        current_mtime = self._max_file_mtime(
            early_exit_above=self._snapshot_mtime
        )
        return current_mtime > self._snapshot_mtime

    def tpl(self, *parts) -> Path:
        return self.templates.joinpath(*parts)

    def y(self) -> str:
        return str(datetime.now().year)


# ─── Helpers ─────────────────────────────────────────────────────


def _error(msg: str) -> Dict:
    return {"status": "error", "message": msg, "changeset": None}


def _result(cs: ChangeSet) -> Dict:
    return {"status": "pending", "message": cs.description, "changeset": cs.to_dict()}


# NLS assignment lines look like `Key = "value";` (optionally indented).
# Keys are whole identifiers (letters/digits/underscore/dot) so that a key is
# never matched as a substring of a longer one: 'Foo.Title' and 'Foo.TitleX'
# are two different keys.
_NLS_ASSIGN_RE = re.compile(r"^[ \t]*([A-Za-z_][A-Za-z0-9_.]*)[ \t]*=")


def _nls_assignments(text: str) -> Dict[str, str]:
    """Map exact NLS key -> raw value text for every assignment in `text`."""
    found: Dict[str, str] = {}
    for line in text.splitlines():
        m = _NLS_ASSIGN_RE.match(line)
        if m:
            found.setdefault(
                m.group(1), line[m.end():].strip().rstrip(";").strip()
            )
    return found


def _queue_nls(cs: ChangeSet, path: Path, content: str, source: str):
    """Queue NLS `content` for `path`, merging it into whatever block is
    already scheduled for that file rather than replacing it.

    Two independent loss modes are handled here:

    * `add_create`/`add_modify` are plain dict assignments, so queuing a second
      block for the same catalog used to silently drop the first one (this ate
      the command-header Title/ShortHelp entries whenever the toolbar/addin
      block was queued after them). This helper always merges into the value
      already in the ChangeSet instead of re-reading the file from disk.
    * Deduplication used to be a substring test (`marker not in queued`).
      Because the command block pre-writes `<Dialog>.Title` and
      `<Dialog>Id.Title` (actions.create_command), any block whose marker began
      with the dialog name matched inside the *other* block's text and was
      skipped wholesale — dropping `<Dialog>.LabelId` and every other key the
      dialog template contributes. Deduplication is key-exact now.

    Per key: same value is an idempotent no-op, a different value is reported
    as a warning on the ChangeSet (never silently decided by queue order).
    The contract is the same whether the catalog is already scheduled, already
    on disk, or brand new. `source` names the contributing block and is used
    only to make conflict warnings traceable.
    """
    key = str(path)
    # Existing Simplified_Chinese catalogs are GBK on disk (CATIA locale
    # codepage convention); read with the matching encoding or every key would
    # be compared against mojibake.
    disk_enc = (
        "gbk"
        if any(part.lower() == "simplified_chinese" for part in path.parts)
        else "utf-8"
    )

    if key in cs.created:
        base, write = cs.created[key], cs.add_create
    elif key in cs.modified:
        base, write = cs.modified[key], cs.add_modify
    elif path.exists():
        base = path.read_text(encoding=disk_enc, errors="replace")
        write = cs.add_modify
    else:
        # Brand-new catalog: run the same key-exact contract as the merge
        # paths above, just against an empty baseline. Short-circuiting
        # straight to add_create here would skip in-block duplicate detection
        # and the key-conflict warning for exactly the blocks most likely to
        # be the file's only contributor.
        base, write = "", cs.add_create

    existing = _nls_assignments(base)
    base_lines = set(base.splitlines())
    seen_in_block: Dict[str, str] = {}
    new_lines = []
    for line in content.splitlines():
        m = _NLS_ASSIGN_RE.match(line)
        if m:
            name = m.group(1)
            value = line[m.end():].strip().rstrip(";").strip()
            if name in seen_in_block:
                cs.add_warning(
                    f"NLS key '{name}' appears more than once in the "
                    f"'{source}' block for {path.name}; kept the first value"
                )
                continue
            seen_in_block[name] = value
            if name in existing:
                if existing[name] != value:
                    cs.add_warning(
                        f"NLS key conflict in {path.name}: '{name}' is already "
                        f"scheduled as {existing[name]!r}; kept it and ignored "
                        f"{value!r} from the '{source}' block"
                    )
                continue
            existing[name] = value
        elif line.strip().startswith("//") and line in base_lines:
            continue  # identical comment already present
        new_lines.append(line)

    has_new_data = False
    for line in new_lines:
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        has_new_data = True
        break
    if not has_new_data:
        return
    block = "\n".join(new_lines).strip()
    merged = base.rstrip() + "\n" + block + "\n" if base.strip() else block + "\n"
    write(path, merged)


# RSC assignment lines look like `Key = "value";` or `Key = "I_foo";`.
_RSC_ASSIGN_RE = re.compile(r"^[ \t]*([A-Za-z_][A-Za-z0-9_.]*)[ \t]*=")


def _rsc_assignments(text: str) -> Dict[str, str]:
    """Map exact RSC key -> raw value text for every assignment in `text`."""
    found: Dict[str, str] = {}
    for line in text.splitlines():
        m = _RSC_ASSIGN_RE.match(line)
        if m:
            found.setdefault(
                m.group(1), line[m.end():].strip().rstrip(";").strip()
            )
    return found


def _queue_rsc(cs: ChangeSet, path: Path, content: str, source: str):
    """Queue RSC `content` for `path`, merging key-values into ChangeSet.

    Follows the same key-exact contract as _queue_nls, but strictly for
    textual .CATRsc files (never handles .bmp binaries).
    Per key:
      - Same key + same value: idempotent no-op (skipped)
      - Same key + different value: raises ValueError (hard error, never warning)
    """
    key = str(path)
    if key in cs.created:
        base, write = cs.created[key], cs.add_create
    elif key in cs.modified:
        base, write = cs.modified[key], cs.add_modify
    elif path.exists():
        base = path.read_text(encoding="utf-8", errors="replace")
        write = cs.add_modify
    else:
        base, write = "", cs.add_create

    existing = _rsc_assignments(base)
    base_lines = set(base.splitlines())
    seen_in_block: Dict[str, str] = {}
    new_lines = []
    for line in content.splitlines():
        m = _RSC_ASSIGN_RE.match(line)
        if m:
            name = m.group(1)
            value = line[m.end():].strip().rstrip(";").strip()
            if name in seen_in_block:
                if seen_in_block[name] != value:
                    raise ValueError(
                        f"CATRsc key conflict in '{source}' for {path.name}: "
                        f"'{name}' assigned multiple different values in the same block"
                    )
                continue
            seen_in_block[name] = value
            if name in existing:
                if existing[name] != value:
                    raise ValueError(
                        f"CATRsc key conflict in {path.name}: '{name}' is already assigned as "
                        f"{existing[name]!r}, cannot assign as {value!r} from '{source}'"
                    )
                continue
            existing[name] = value
        elif line.strip().startswith("//") and line in base_lines:
            continue
        new_lines.append(line)

    has_new_data = False
    for line in new_lines:
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        has_new_data = True
        break
    if not has_new_data:
        return
    block = "\n".join(new_lines).strip()
    merged = base.rstrip() + "\n" + block + "\n" if base.strip() else block + "\n"
    write(path, merged)


def _apply_and_return(cs: ChangeSet, dry_run: bool = False) -> Dict:
    result = cs.apply(dry_run=dry_run)
    result["preview"] = cs.preview()
    return result




# ══════════════════════════════════════════════════════════════════
#  QUERY ACTIONS
# ══════════════════════════════════════════════════════════════════


def analyze_workspace(ctx: ActionContext) -> Dict:
    """Complete workspace analysis: all entities and relationships"""
    snap = ctx.refresh()
    return {"status": "ok", "workspace": str(snap.root), "summary": snap.to_dict()}


def list_modules(ctx: ActionContext) -> Dict:
    ctx.refresh()
    items = []
    for fw in ctx.snapshot.frameworks:
        for mod in fw.modules:
            items.append(
                {
                    "name": mod.name,
                    "framework": fw.name,
                    "commands": len(mod.commands),
                    "interfaces": len(mod.interfaces),
                    "has_imakefile": mod.imakefile is not None,
                    "path": str(mod.path),
                }
            )
    return {"status": "ok", "modules": items, "count": len(items)}


def list_commands(ctx: ActionContext) -> Dict:
    ctx.refresh()
    items = [
        c.to_dict()
        for fw in ctx.snapshot.frameworks
        for m in fw.modules
        for c in m.commands
    ]
    return {"status": "ok", "commands": items, "count": len(items)}


def list_workbenches(ctx: ActionContext) -> Dict:
    ctx.refresh()
    items = [wb.to_dict() for wb in ctx.snapshot.get_all_workbenches()]
    return {"status": "ok", "workbenches": items, "count": len(items)}


def list_interfaces(ctx: ActionContext) -> Dict:
    ctx.refresh()
    items = [i.to_dict() for i in ctx.snapshot.get_all_interfaces()]
    return {"status": "ok", "interfaces": items, "count": len(items)}


# ══════════════════════════════════════════════════════════════════
#  CREATE ACTIONS
# ══════════════════════════════════════════════════════════════════


def create_framework(
    ctx: ActionContext,
    name: str,
    modules: List[str] = None,
) -> Dict:
    """Create a new Framework"""
    ctx.refresh()
    fw_name = name if name.endswith(".edu") else f"{name}.edu"
    base = fw_name.replace(".edu", "")
    fw_dir = ctx.workspace_root / fw_name

    if fw_dir.exists():
        return _error(f"Framework already exists: {fw_name}")

    cs = ChangeSet(
        action="create_framework", description=f"Create framework '{fw_name}'"
    )
    cs.add_create_file(
        fw_dir / "IdentityCard" / "IdentityCard.xml",
        ctx.tpl("framework", "IdentityCard.h"),
        {"FrameworkName": base, "YYYY": ctx.y()},
    )
    cs.add_create_file(
        fw_dir / "CNext" / "code" / "dictionary" / f"{base}.dico",
        ctx.tpl("framework", "Framework.edu.dico"),
        {"FrameworkName": base},
    )
    cs.add_create_file(
        fw_dir / "Imakefile.mk",
        ctx.tpl("framework", "FrameworkImakefile.mk"),
        {"FrameworkName": base},
    )
    # Generate CATIAV5Level.lvl at workspace root (required for B28 builds).
    # The file is workspace-scoped, not framework-private. Skip when it already
    # exists: queuing create is rejected by ChangeSet ("Created file already
    # exists") and would block a second framework or any workspace that already
    # ran mkGetPreq / official RADE. Never overwrite — on-disk content may be
    # official or hand-tuned.
    lvl_tpl = ctx.tpl("framework", "CATIAV5Level.lvl")
    lvl_path = ctx.workspace_root / "CATIAV5Level.lvl"
    if lvl_tpl.exists() and not lvl_path.exists():
        cs.add_create_file(
            lvl_path, lvl_tpl,
            {"YYYY": ctx.y()},
        )

    if modules:
        mod_names = []
        for mn in modules:
            mod_base = mn.replace(".m", "") if mn.endswith(".m") else mn
            mod_names.append(mod_base)
            sub = _module_cs(ctx, fw_dir, mn)
            cs.created.update(sub.created)
            cs.modified.update(sub.modified)
        # Update framework Imakefile to register modules
        fw_imk = fw_dir / "Imakefile.mk"
        if fw_imk.exists() or str(fw_imk) in cs.created:
            lines = [f"MODULES += {n}" for n in mod_names]
            cs.add_patch(Patch(
                file=fw_imk,
                operation="append",
                target="",
                content="\n" + "\n".join(lines),
            ))

    # NOTE: Prerequisite path setup (mkGetPreq) is a real side-effecting build
    # command and must NOT run here — this function only returns a preview
    # ChangeSet (status="pending") and callers may discard it without ever
    # calling apply(). Running mkGetPreq eagerly wrote CATIAV5Level.lvl /
    # Install_config_win_b64 to the workspace before apply(), which then
    # collided with this ChangeSet's own CATIAV5Level.lvl create and caused
    # apply() to reject with "Created file already exists" (P0-004 class bug).
    # build_workspace() already calls setup_prerequisite_path() itself before
    # invoking mkmk, so no explicit setup is needed here.
    return _result(cs)


def create_module(ctx: ActionContext, framework_name: str, module_name: str) -> Dict:
    """Create a Module within an existing Framework"""
    ctx.refresh()
    fw = ctx.snapshot.get_framework(framework_name)
    if not fw:
        return _error(f"Framework not found: {framework_name}")
    mod_name = module_name if module_name.endswith(".m") else f"{module_name}.m"
    mod_base = mod_name.replace(".m", "")
    if (fw.path / mod_name).exists():
        return _error(f"Module already exists: {mod_name}")
    cs = _module_cs(ctx, fw.path, mod_name)
    # Update framework Imakefile to register the module
    fw_imk = fw.path / "Imakefile.mk"
    if fw_imk.exists():
        cs.add_patch(Patch(
            file=fw_imk,
            operation="append",
            target="",
            content=f"\nMODULES += {mod_base}",
        ))
    cs.metadata = {"framework": framework_name, "module": mod_name}
    return _result(cs)


def _module_cs(ctx: ActionContext, fw_path: Path, module_name: str) -> ChangeSet:
    base = module_name.replace(".m", "") if module_name.endswith(".m") else module_name
    if not module_name.endswith(".m"):
        module_name = f"{module_name}.m"
    mp = fw_path / module_name
    cs = ChangeSet(action="create_module", description=f"Create module '{module_name}'")
    cs.add_create_file(
        mp / "Imakefile.mk",
        ctx.tpl("module", "Imakefile.mk"),
        {"ModuleName": base, "YYYY": ctx.y()},
    )
    for d in ["src", "LocalInterfaces", "PublicInterfaces", "resources"]:
        cs.add_create(mp / d / ".gitkeep", "")
    return cs


def create_command(
    ctx: ActionContext,
    name: str,
    module: str,
    framework: str = None,
    *,
    workbench: str = None,
    is_stateful: bool = False,
    dialog_name: str = None,
    icon: str = None,
    tooltip: str = None,
    category: str = None,
    visibility: str = Visibility.ALWAYS,
    load_name: Optional[str] = None,
    cs: ChangeSet = None,
) -> Dict:
    """
    Create a Command + Addin for B28 CAA.

    Generates:
      - {Name}.h / {Name}.cpp         (CATStateCommand subclass)
      - {Module}Addin.h / .cpp        (workbench addin, registers command)
      - Framework .dico               (register addin as CATIAfrGeneralWksAddin)
      - Imakefile update              (WIZARD_LINK_MODULES)

    `cs` is an optional caller-owned ChangeSet. Passing one lets an orchestrator
    (see intents.create_executable_command) collect the command, dialog and
    workbench contributions of a single user intent into ONE ChangeSet instead
    of serializing each action to a dict and re-merging them, which loses the
    second contribution to any file two actions both write (notably the shared
    framework .CATNls catalog). The ChangeSet is never applied here — the
    outermost orchestrator owns apply().
    """
    ctx.refresh()
    mod = ctx.snapshot.get_module(module, framework)
    if not mod:
        fw_names = [fw.name for fw in ctx.snapshot.frameworks]
        return _error(f"Module '{module}' not found. Frameworks: {fw_names}")

    cs = cs if cs is not None else ChangeSet(
        action="create_command", description=f"Create command '{name}' in '{module}'"
    )
    fw_name = mod.framework.name if mod.framework else "MyFramework"
    module_base = module.replace(".m", "")
    resolved_load_name = load_name or module_base

    src = mod.src_dir or mod.path / "src"
    li = mod.path / "LocalInterfaces"
    # Directories are created inside ChangeSet.apply() — no premature writes (P0-004 fix)

    # --- 1. Command.h (LocalInterfaces) ---
    cs.add_create_file(
        li / f"{name}.h",
        ctx.tpl("command", "CommandClass.h"),
        _r(name, fw_name, module, CommandClassName=name),
    )

    # --- 2. Command.cpp (src) ---
    cs.add_create_file(
        src / f"{name}.cpp",
        ctx.tpl("command", "CommandClass.cpp"),
        _r(name, fw_name, module, CommandClassName=name),
    )

    # --- 3. Addin.h (LocalInterfaces) — skip if exists (shared across commands) ---
    addin_name = f"{module_base}Addin"
    addin_h = li / f"{addin_name}.h"
    if not addin_h.exists():
        cs.add_create_file(
            addin_h,
            ctx.tpl("module", "AddinClass.h"),
            _r(addin_name, fw_name, module, CommandClassName=name, ModuleName=module_base),
        )

    # --- 4. Addin.cpp (src) — toolbar + command registration ---
    toolbar_pos = "Right"  # default position
    toolbar_pri = "1"       # default priority
    addin_cpp = src / f"{addin_name}.cpp"
    if not addin_cpp.exists():
        cs.add_create_file(
            addin_cpp,
            ctx.tpl("module", "AddinClass.cpp") if (ctx.tpl("module") / "AddinClass.cpp").exists() else ctx.tpl("command", "CommandClass.cpp"),
            _r(addin_name, fw_name, module, CommandClassName=name, ModuleName=module_base,
               ToolbarPriority=toolbar_pri, ToolbarPosition=toolbar_pos),
        )
    else:
        # Addin.cpp already exists — patch to register new command (P3 fix: multi-command support)
        # Idempotency guard: patches whose content is already present must be
        # skipped, otherwise re-generating the same command inserts duplicate
        # MacDeclareHeader/registration lines and breaks compilation (C2011).
        cpp_base = module.replace(".m", "")
        addin_text = addin_cpp.read_text(encoding="utf-8", errors="replace")
        # 4a. Add MacDeclareHeader
        if f"MacDeclareHeader({name}Hdr);" not in addin_text:
            cs.add_patch(Patch(
                file=addin_cpp,
                operation="insert_after",
                target='#include "CATCommandHeader.h"',
                content=f'MacDeclareHeader({name}Hdr);',
            ))
        # 4b. Register in CreateCommands() — insertion point is the first
        # '{' after the signature, not the signature line itself, since
        # the opening brace is conventionally on its own line (see
        # templates/module/AddinClass.cpp). Using plain insert_after here
        # would insert content between the signature and '{', producing
        # invalid C++ (see CADE bug: broke CreateCommands() compilation).
        if f'"{cpp_base}.{name}"' not in addin_text:
            cs.add_patch(Patch(
                file=addin_cpp,
                operation="insert_after_brace",
                target="void " + addin_name + "::CreateCommands()",
                content=f'    new {name}Hdr("{cpp_base}.{name}", "{cpp_base}", "{name}", (void*)NULL);',
            ))

    # --- 5. Ensure Imakefile has WIZARD_LINK_MODULES (append, don't overwrite) ---
    if mod.imakefile_path().exists():
        old = mod.imakefile_path().read_text(encoding="utf-8", errors="replace")
        if "WIZARD_LINK_MODULES" not in old:
            if "LINK_WITH" not in old:
                cs.add_patch(Patch(
                    file=mod.imakefile_path(),
                    operation="append",
                    target="",
                    content="\n#INSERTION ZONE NOT FOUND, MOVE AND APPEND THIS VARIABLE IN YOUR LINK STATEMENT\n"
                            "LINK_WITH = $(WIZARD_LINK_MODULES)\n"
                            "# DO NOT EDIT :: 3DS WIZARDS WILL ADD CODE HERE\n"
                            "WIZARD_LINK_MODULES =  \\\n"
                            "JS0GROUP \\\n"
                            "JS0FM \\\n"
                            "CATApplicationFrame \\\n"
                            "CATDialogEngine \\\n"
                            "DI0PANV2 \n"
                            "# END WIZARD EDITION ZONE\n",
                ))
            else:
                cs.add_patch(Patch(
                    file=mod.imakefile_path(),
                    operation="append",
                    target="",
                    content="\n# DO NOT EDIT :: 3DS WIZARDS WILL ADD CODE HERE\n"
                            "WIZARD_LINK_MODULES =  \\\n"
                            "JS0GROUP \\\n"
                            "JS0FM \\\n"
                            "CATApplicationFrame \\\n"
                            "CATDialogEngine \\\n"
                            "DI0PANV2 \n"
                            "# END WIZARD EDITION ZONE\n",
                ))

    # --- 6. Framework .dico — register addin ---
    fw = mod.framework
    if fw:
        dico_file = fw.path / "CNext" / "code" / "dictionary" / f"{fw.name.replace('.edu', '')}.dico"
        # Directory created in ChangeSet.apply() — no premature writes (P0-004 fix)
        entry = f"{addin_name} CATIAfrGeneralWksAddin lib{module_base}\n"
        if dico_file.exists():
            old = dico_file.read_text(encoding="utf-8", errors="replace")
            if addin_name not in old:
                stripped = old.rstrip()
                cs.add_modify(dico_file, (stripped + "\n" if stripped else "") + entry)
        else:
            cs.add_create(dico_file, entry)
        # Also write to Runtime View location so CATIA finds it after mkCreateRuntimeView
        rv_dico = ctx.workspace_root / "win_b64" / "code" / "dictionary" / dico_file.name
        if rv_dico.exists():
            old_rv = rv_dico.read_text(encoding="utf-8", errors="replace")
            if addin_name not in old_rv:
                cs.add_modify(rv_dico, old_rv.rstrip() + "\n" + entry)
        else:
            cs.add_create(rv_dico, entry)

    # --- 7. Dialog files (when dialog_name is provided) ---
    if dialog_name:
        tpl_dlg = ctx.tpl("dialog")
        dlg_h = tpl_dlg / "DialogClass.h"
        dlg_cpp = tpl_dlg / "DialogClass.cpp"
        if dlg_h.exists() and dlg_cpp.exists():
            cs.add_create_file(
                li / f"{dialog_name}.h", dlg_h,
                _r(dialog_name, fw_name, module, DialogClassName=dialog_name),
            )
            cs.add_create_file(
                src / f"{dialog_name}.cpp", dlg_cpp,
                _r(dialog_name, fw_name, module, DialogClassName=dialog_name),
            )
            # Add dialog include to command header
            cs.add_patch(Patch(
                file=li / f"{name}.h",
                operation="insert_after",
                target='#include "CATStateCommand.h"',
                content=f'#include "{dialog_name}.h"',
            ))
            # Dialog member in command class (created + shown in BuildGraph)
            cs.add_patch(Patch(
                file=li / f"{name}.h",
                operation="insert_after",
                target="CATDialogAgent      *_pDlgAgent;",
                content=f"    {dialog_name}          *_pDialog;",
            ))
            # Framework includes needed to open/show the dialog.
            # CATApplicationFrame.h is required so the dialog can be parented
            # to the app main window (see BuildGraph fix below) — a
            # NULL-parent top-level CATDlgDialog never gets mapped to the
            # window manager in B28's Dialog framework and stays invisible
            # (verified against official CAADoc sample
            # CAADegAnalysisNumericCmd.cpp).
            cs.add_patch(Patch(
                file=src / f"{name}.cpp",
                operation="insert_after",
                target='#include "CATCommandGlobalUndo.h"',
                content='#include "CATDialogAgent.h"\n#include "CATDialogState.h"\n#include "CATApplicationFrame.h"',
            ))
            # Member initializer in constructor
            cs.add_patch(Patch(
                file=src / f"{name}.cpp",
                operation="insert_after",
                target=", _pDlgAgent(NULL)",
                content="    , _pDialog(NULL)",
            ))
            # BuildGraph: create + show dialog, end command when dialog closes
            # (official CATStateCommand + CATDialogAgent pattern; clicking the
            # toolbar button must open the dialog, not silently no-op).
            #
            # IMPORTANT: the dialog MUST be parented to the app main window.
            # `new {dialog_name}(NULL)` builds a top-level CATDlgDialog with
            # a NULL parent, which in B28's Dialog framework never gets
            # mapped to the window manager — the dialog object is created
            # but stays invisible/unmapped, so clicking the toolbar button
            # silently does nothing. Fix verified against official CAADoc
            # sample CAADegAnalysisNumericCmd.cpp, which parents its dialog
            # to CATApplicationFrame::GetFrame()->GetMainWindow(). Also
            # subscribe to both close notifications (Dia CLOSE + window
            # close), matching official samples, so the command ends
            # correctly whichever way the user closes the dialog (OK/Cancel
            # button vs. the window's [x] close box).
            cs.add_patch(Patch(
                file=src / f"{name}.cpp",
                operation="insert_after_brace",
                target=f"void {name}::BuildGraph()",
                content=(
                    "    CATApplicationFrame *pFrame = CATApplicationFrame::GetFrame();\n"
                    "    CATDialog *pDlgParent = (CATDialog *)(pFrame ? pFrame->GetMainWindow() : NULL);\n"
                    f"    _pDialog = new {dialog_name}(pDlgParent);\n"
                    "    _pDialog->Build();\n"
                    "    _pDialog->SetVisibility(CATDlgShow);\n"
                    "\n"
                    '    _pDlgAgent = new CATDialogAgent("DlgAgentId");\n'
                    "    _pDlgAgent->AcceptOnNotify(_pDialog, _pDialog->GetDiaCLOSENotification());\n"
                    "    _pDlgAgent->AcceptOnNotify(_pDialog, _pDialog->GetWindCloseNotification());\n"
                    "\n"
                    '    CATDialogState *pDlgState = GetInitialState("DlgStateId");\n'
                    "    pDlgState->AddDialogAgent(_pDlgAgent);\n"
                    "\n"
                    "    AddTransition(pDlgState, NULL, IsOutputSetCondition(_pDlgAgent));"
                ),
            ))
            # Hide the dialog whenever the command ends.
            #
            # IMPORTANT (confirmed via debug tracing + official CAADoc
            # sample CAADegAnalysisNumericCmd.cpp): when the end-user closes
            # the dialog (Close button OR window [x]), the state machine's
            # `AddTransition(pDlgState, NULL, ...)` reaches the NULL state,
            # and the framework calls **Cancel()**, not Desactivate(), to
            # tear down the command. The official sample therefore hides
            # the dialog in BOTH Cancel() and Desactivate() (they can be
            # reached via different paths — Cancel for user-driven end,
            # Desactivate for programmatic/focus-loss end); relying on only
            # one of them leaves the dialog window stuck on screen even
            # though its Close button was clicked (its click is consumed
            # by the state transition, not by any code that hides the
            # window). The dialog is only actually destroyed in the
            # command destructor via RequestDelayedDestruction() — never a
            # raw `delete`, and never inside Cancel/Desactivate themselves
            # (the command object, and therefore _pDialog, may still be
            # queried afterwards).
            cs.add_patch(Patch(
                file=src / f"{name}.cpp",
                operation="insert_after_brace",
                target=f"CATStatusChangeRC {name}::Desactivate(",
                content=(
                    "    if (_pDialog)\n"
                    "    {\n"
                    "        _pDialog->SetVisibility(CATDlgHide);\n"
                    "    }"
                ),
            ))
            cs.add_patch(Patch(
                file=src / f"{name}.cpp",
                operation="insert_after_brace",
                target=f"CATStatusChangeRC {name}::Cancel(",
                content=(
                    "    if (_pDialog)\n"
                    "    {\n"
                    "        _pDialog->SetVisibility(CATDlgHide);\n"
                    "    }"
                ),
            ))
            # Destructor: safely destroy the dialog (never a raw `delete`).
            cs.add_patch(Patch(
                file=src / f"{name}.cpp",
                operation="insert_after_brace",
                target=f"{name}::~{name}(",
                content=(
                    "    if (_pDialog)\n"
                    "    {\n"
                    "        _pDialog->RequestDelayedDestruction();\n"
                    "        _pDialog = NULL;\n"
                    "    }"
                ),
            ))

    # --- 8. NLS + CATRsc Resources — use templates for UI display ---
    if fw:
        tpl_nls = ctx.tpl("command", "resources", "CommandFramework.CATNls")
        tpl_rsc = ctx.tpl("command", "resources", "CommandFramework.CATRsc")
        fw_base = fw.name.replace(".edu", "")

        # NLS
        nls_file = fw.path / "CNext" / "resources" / "msgcatalog" / f"{fw_base}.CATNls"
        # Directory created in ChangeSet.apply() — no premature writes (P0-004 fix)
        # NLS — use tooltip param if provided
        if tpl_nls.exists():
            nls_title = tooltip if tooltip else name
            nls_content = render_template(tpl_nls.read_text(encoding="utf-8", errors="replace"), {
                "CommandClassName": name,
                "CommandHeaderName": name,
                "CommandTitle": nls_title,
                "FrameworkName": fw_base,
            })
            # Dialog NLS: window title + control labels (used by DeclareResource)
            if dialog_name:
                nls_content += (
                    f'\n// Dialog window titles\n'
                    f'{dialog_name}.Title = "{dialog_name}";\n'
                    f'{dialog_name}Id.Title = "{dialog_name}";\n'
                )
            _queue_nls(cs, nls_file, nls_content, f"command:{name}")

        # 中文 NLS — 放在 Simplified_Chinese/ 子目录（文件名与英文版相同，
        # CATIA 按运行语言自动到语言子目录查找；平铺的 *_Chinese.CATNls 不会被加载）。
        # 标题沿用用户传入的 tooltip（中文用户通常直接传中文）；固定串给中文默认。
        tpl_nls_zh = ctx.tpl("command", "resources", "Simplified_Chinese", "CommandFramework.CATNls")
        nls_file_zh = (
            fw.path / "CNext" / "resources" / "msgcatalog"
            / "Simplified_Chinese" / f"{fw_base}.CATNls"
        )
        if tpl_nls_zh.exists():
            nls_title = tooltip if tooltip else name
            nls_content_zh = render_template(
                tpl_nls_zh.read_text(encoding="utf-8", errors="replace"),
                {
                    "CommandClassName": name,
                    "CommandHeaderName": name,
                    "CommandTitle": nls_title,
                    "FrameworkName": fw_base,
                },
            )
            if dialog_name:
                nls_content_zh += (
                    f'\n// 对话框窗口标题\n'
                    f'{dialog_name}.Title = "{dialog_name}";\n'
                    f'{dialog_name}Id.Title = "{dialog_name}";\n'
                )
            _queue_nls(cs, nls_file_zh, nls_content_zh, f"command:{name}")

        # CATRsc — in msgcatalog/ (where CNEXT reads it via CATMsgCatalogPath)
        # Named after header class, format: HeaderClass.HeaderID.Icon.Normal
        rsc_file = fw.path / "CNext" / "resources" / "msgcatalog" / f"{name}Hdr.CATRsc"
        # Directory created in ChangeSet.apply() — no premature writes (P0-004 fix)
        # Computed unconditionally so the icon-file generation block below
        # (8c) can always see the same name the .CATRsc reference uses,
        # even if tpl_rsc happens to be missing.
        icon_name = icon if icon else name.lower()
        if tpl_rsc.exists():
            rsc_category = category if category else "Commands"
            rsc_content = f'{name}Hdr.{module_base}.{name}.Icon.Normal = "I_{icon_name}";\n'
            if rsc_file.exists():
                old = rsc_file.read_text(encoding="utf-8", errors="replace")
                if name not in old:
                    cs.add_modify(rsc_file, old.rstrip() + "\n" + rsc_content)
            else:
                cs.add_create(rsc_file, rsc_content)

        # --- 8c. Icon file — resolve via icon_provider, add to ChangeSet (P0-004 fix) ---
        # NOTE: the .CATRsc block above always writes an "I_{icon_name}"
        # reference (falling back to the command name in lowercase when no
        # explicit `icon=` is given). This block MUST use the same fallback,
        # otherwise a command created without an explicit icon gets a
        # dangling icon reference — CNEXT shows the toolbar button with no
        # logo because the referenced .bmp was never generated.
        if fw:
            try:
                from icon_provider import get_icon
                # Entity-level hint: the Command's category carries domain
                # semantics the name alone may not (e.g. a 'FooCmd' with
                # category='hole' still gets the hole icon). Name parsing
                # remains the primary source; hint is the entity fallback.
                ico_path = get_icon(icon_name, hint=category)
                if ico_path and ico_path.exists():
                    icons_dir = fw.path / "CNext" / "resources" / "graphic" / "icons" / "normal"
                    ico_name = f"I_{icon_name.replace(' ', '_')}.bmp"
                    target = icons_dir / ico_name
                    # Custom-icon override: a project-drawn bmp placed under
                    # icons/custom/ (e.g. a 24x24 panel icon) shadows the
                    # CADE-rendered default — never overwritten. See
                    # knowledge/failure_patterns/fp_runtime_resource_not_synced.md.
                    custom = icons_dir.parent / "custom" / ico_name
                    if custom.exists():
                        pass
                    else:
                        # Freshness guarantee: overwrite any stale/foreign icon
                        # with the current CADE render (old CADE versions or
                        # other tools may have left an icon with the same name).
                        new_bytes = ico_path.read_bytes()
                        if not target.exists() or target.read_bytes() != new_bytes:
                            cs.add_create_binary(target, new_bytes)
            except Exception:
                pass  # icon failure never blocks generation

        # Toolbar + addin NLS (required for toolbar visibility)
        tip = tooltip if tooltip else f"Execute {name}"
        addin_nls = (
            f"{addin_name}.Title  = \"{name}\";\n"
            f"{addin_name}.Tip    = \"{tip}\";\n"
            f"{module_base}Tlb.Title  = \"{module_base} Commands\";\n"
        )
        _queue_nls(cs, nls_file, addin_nls, f"addin:{addin_name}")

        # Toolbar + addin 中文 NLS（与英文块镜像，固定串用中文）
        addin_nls_zh = (
            f'{addin_name}.Title  = "{name}";\n'
            f'{addin_name}.Tip    = "{tip}";\n'
            f'{module_base}Tlb.Title  = "{module_base} 命令";\n'
        )
        _queue_nls(cs, nls_file_zh, addin_nls_zh, f"addin:{addin_name}")

    cs.merge_metadata(
        command=name,
        class_name=name,
        load_name=resolved_load_name,
        module=module,
        addin=addin_name,
        is_stateful=is_stateful,
        dialog=dialog_name,
    )
    return _result(cs)


def create_workbench(ctx: ActionContext, name: str, framework: str = None) -> Dict:
    """Create a Workbench with Addin"""
    ctx.refresh()
    fw = (
        ctx.snapshot.get_framework(framework)
        if framework
        else (ctx.snapshot.frameworks[0] if ctx.snapshot.frameworks else None)
    )
    if not fw:
        return _error("No framework found")

    # Find a module to place the workbench in
    mod = fw.modules[0] if fw.modules else None
    if not mod:
        return _error("No modules found in framework")

    cs = ChangeSet(action="create_workbench", description=f"Create workbench '{name}'")
    src = mod.src_dir or mod.path / "src"
    li = mod.path / "LocalInterfaces"
    # Directories created in ChangeSet.apply() — no premature writes (P0-004 fix)

    tpl_wb = ctx.tpl("workbench")
    cs.add_create_file(
        li / f"{name}.h", tpl_wb / "WorkbenchClass.h", _r(name, fw.name, mod.name)
    )
    cs.add_create_file(
        src / f"{name}.cpp", tpl_wb / "WorkbenchClass.cpp", _r(name, fw.name, mod.name)
    )
    cs.add_create_file(
        li / f"{name}Addin.h", tpl_wb / "AddinClass.h", _r(name, fw.name, mod.name)
    )
    cs.add_create_file(
        src / f"{name}Addin.cpp", tpl_wb / "AddinClass.cpp", _r(name, fw.name, mod.name)
    )

    cs.metadata = {"workbench": name, "framework": fw.name}
    return _result(cs)


def create_dialog(
    ctx: ActionContext, name: str, module: str, framework: str = None,
    *, cs: ChangeSet = None,
) -> Dict:
    """Create a Dialog

    `cs` is an optional caller-owned ChangeSet — see create_command().
    """
    ctx.refresh()
    mod = ctx.snapshot.get_module(module, framework)
    if not mod:
        return _error(f"Module not found: {module}")

    cs = cs if cs is not None else ChangeSet(
        action="create_dialog", description=f"Create dialog '{name}'"
    )
    src = mod.src_dir or mod.path / "src"
    li = mod.path / "LocalInterfaces"
    # Directories created in ChangeSet.apply() — no premature writes (P0-004 fix)

    tpl = ctx.tpl("dialog")
    cs.add_create_file(
        li / f"{name}.h",
        tpl / "DialogClass.h",
        _r(
            name,
            fw_name=mod.framework.name if mod.framework else "MF",
            mod_name=mod.name,
        ),
    )
    cs.add_create_file(
        src / f"{name}.cpp",
        tpl / "DialogClass.cpp",
        _r(
            name,
            fw_name=mod.framework.name if mod.framework else "MF",
            mod_name=mod.name,
        ),
    )

    # 对话框 NLS 条目合并到 framework 共享 catalog（en + zh）。
    # 与 DialogClass.cpp 的 NLS(key, fallback) 模式对齐：
    #   en -> msgcatalog/<Framework>.CATNls
    #   zh -> msgcatalog/Simplified_Chinese/<Framework>.CATNls（GBK 落盘）
    fw_path = mod.framework.path if mod.framework else None
    if fw_path:
        fw_base = mod.framework.name.replace(".edu", "")
        msg_dir = fw_path / "CNext" / "resources" / "msgcatalog"
        tpl_nls_en = tpl / "resources" / "DialogClass.CATNls"
        tpl_nls_zh = tpl / "resources" / "Simplified_Chinese" / "DialogClass.CATNls"
        replacements = _r(
            name,
            fw_name=mod.framework.name,
            mod_name=mod.name,
            DialogClassName=name,
        )
        if tpl_nls_en.exists():
            content_en = render_template(
                tpl_nls_en.read_text(encoding="utf-8", errors="replace"), replacements
            )
            _queue_nls(cs, msg_dir / f"{fw_base}.CATNls", content_en, f"dialog:{name}")
        if tpl_nls_zh.exists():
            content_zh = render_template(
                tpl_nls_zh.read_text(encoding="utf-8", errors="replace"), replacements
            )
            _queue_nls(
                cs,
                msg_dir / "Simplified_Chinese" / f"{fw_base}.CATNls",
                content_zh,
                f"dialog:{name}",
            )

    cs.merge_metadata(dialog=name, module=module)
    return _result(cs)


def create_interface(
    ctx: ActionContext,
    name: str,
    module: str,
    framework: str = None,
    *,
    use_idl: bool = False,
) -> Dict:
    """Create an Interface (with optional IDL)"""
    ctx.refresh()
    mod = ctx.snapshot.get_module(module, framework)
    if not mod:
        return _error(f"Module not found: {module}")

    cs = ChangeSet(action="create_interface", description=f"Create interface '{name}'")
    li = mod.path / "LocalInterfaces"
    src = mod.src_dir or mod.path / "src"
    # Directories created in ChangeSet.apply() — no premature writes (P0-004 fix)

    cs.add_create_file(li / f"{name}.h", ctx.tpl("IInterface.h"), _r(name))
    cs.add_create_file(src / f"{name}.cpp", ctx.tpl("IInterface.cpp"), _r(name))

    if use_idl:
        cs.add_create_file(
            src / f"{name}.idl",
            ctx.tpl("idl", "InterfaceName.idl"),
            _r(name, IIDLInterfaceName=name),
        )
        pi = mod.path / "PublicInterfaces"
        cs.add_create_file(
            pi / f"{name}IDL.h", ctx.tpl("idl", "IDLInterface.h"), _r(name)
        )

    cs.metadata = {"interface": name, "module": module, "use_idl": use_idl}
    return _result(cs)


def create_component(
    ctx: ActionContext,
    name: str,
    module: str,
    framework: str = None,
    *,
    implements: str = None,
) -> Dict:
    """Create a Component implementing an interface"""
    ctx.refresh()
    mod = ctx.snapshot.get_module(module, framework)
    if not mod:
        return _error(f"Module not found: {module}")

    cs = ChangeSet(action="create_component", description=f"Create component '{name}'")
    li = mod.local_interfaces_dir()
    src = mod.src_dir_path()
    # Directories created in ChangeSet.apply() — no premature writes (P0-004 fix)

    extra = {"IInterfaceName": implements} if implements else {}
    cs.add_create_file(li / f"{name}.h", ctx.tpl("Component.h"), _r(name, **extra))
    cs.add_create_file(src / f"{name}.cpp", ctx.tpl("Component.cpp"), _r(name, **extra))

    cs.metadata = {"component": name, "module": module, "implements": implements}
    return _result(cs)


def strip_c_comments_and_strings(code: str) -> str:
    """Strip C/C++ comments (/* */ and //) and string/char literals from code."""
    pattern = re.compile(
        r'//[^\r\n]*'                       # line comment
        r'|/\*[\s\S]*?\*/'                  # block comment
        r'|"(?:\\.|[^"\\])*"'               # string literal
        r"|'(?:\\.|[^'\\])*'",              # char literal
        re.MULTILINE
    )
    def replacer(match):
        s = match.group(0)
        if s.startswith('//'):
            return ''
        elif s.startswith('/*'):
            return '\n' * s.count('\n')
        else:
            return '""'
    return pattern.sub(replacer, code)


def strip_c_comments(code: str) -> str:
    """Strip C/C++ comments (/* */ and //) from code, preserving string literals."""
    pattern = re.compile(
        r'//[^\r\n]*'                       # line comment
        r'|/\*[\s\S]*?\*/'                  # block comment
        r'|"(?:\\.|[^"\\])*"'               # string literal
        r"|'(?:\\.|[^'\\])*'",              # char literal
        re.MULTILINE
    )
    def replacer(match):
        s = match.group(0)
        if s.startswith('//'):
            return ''
        elif s.startswith('/*'):
            return '\n' * s.count('\n')
        else:
            return s
    return pattern.sub(replacer, code)


def inspect_workbench_registration(
    ctx: ActionContext,
    workbench_name: str,
    command_name: str,
    load_name: Optional[str] = None,
    class_name: Optional[str] = None,
    cs: Optional[ChangeSet] = None,
) -> Dict:
    """Inspect workbench and addin source to validate 4-parameter header registration.

    Read-only inspection: determines target header class, header ID, load name,
    class name, and verifies whether registration is valid, conflicting, or idempotent.
    Used both for pre-validation gates (before mutations) and inside add_command_to_workbench.
    """
    if not load_name:
        return {
            "status": "error",
            "error": (
                f"Cannot resolve load_name for command '{command_name}'. "
                "load_name must be provided explicitly or stored in ChangeSet metadata."
            ),
        }

    wbs = ctx.snapshot.get_all_workbenches()
    wb = next((w for w in wbs if w.name.lower() == workbench_name.lower()), None)
    if not wb:
        return {"status": "error", "error": f"Workbench not found: {workbench_name}"}

    addin_source = wb.addin_source or wb.addin_source_path()
    if not addin_source:
        return {"status": "error", "error": f"Workbench '{workbench_name}' has no Addin source configured"}

    addin_str = str(addin_source)
    old_content = None
    if cs is not None and addin_str in cs.modified:
        old_content = cs.modified[addin_str]
    elif cs is not None and addin_str in cs.created:
        old_content = cs.created[addin_str]
    elif addin_source.exists():
        old_content = addin_source.read_text(encoding="utf-8", errors="replace")

    if old_content is None:
        return {"status": "error", "error": f"Workbench '{workbench_name}' Addin source not found: {addin_source}"}

    target_class_name = class_name or command_name
    target_header_id = f"{command_name}Hdr"

    # Analyze MacDeclareHeader declarations via lexical stripping
    stripped = strip_c_comments_and_strings(old_content)
    declared_headers = re.findall(r"\bMacDeclareHeader\s*\(\s*(\w+)\s*\)", stripped)
    if len(declared_headers) > 1:
        return {
            "status": "error",
            "error": (
                f"Workbench '{workbench_name}' Addin source contains multiple "
                f"MacDeclareHeader declarations ({declared_headers}). Cannot infer HeaderClass."
            ),
        }
    elif len(declared_headers) == 1:
        target_header_class = declared_headers[0]
        needs_declare = False
    else:
        # 0 headers declared: derive from Addin class name
        m_cls = re.search(r"void\s+(\w+)::CreateCommands\s*\(", old_content)
        addin_cls = m_cls.group(1) if m_cls else f"{wb.name}Addin"
        target_header_class = f"{addin_cls}Header"
        needs_declare = True

    # Parse existing 4-parameter Header registrations inside CreateCommands()
    stripped_for_reg = strip_c_comments(old_content)
    m_cc = re.search(r"void\s+\w+::CreateCommands\s*\([^)]*\)\s*\{", stripped_for_reg)
    if not m_cc:
        return {"status": "error", "error": f"Could not locate CreateCommands() in {addin_source}"}

    reg_pattern = re.compile(
        r'new\s+(\w+)\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*\(void\s*\*\)\s*NULL\s*\);?'
    )
    existing_regs = reg_pattern.findall(stripped_for_reg)

    is_idempotent = False
    for hdr_cls, hdr_id, ld_name, cls_name in existing_regs:
        if (hdr_cls, hdr_id) == (target_header_class, target_header_id):
            if (ld_name, cls_name) == (load_name, target_class_name):
                is_idempotent = True
                break
            else:
                return {
                    "status": "error",
                    "error": (
                        f"Header registration conflict: ({target_header_class}, {target_header_id}) "
                        f"is already registered with payload ({ld_name}, {cls_name}), "
                        f"cannot register with ({load_name}, {target_class_name})"
                    ),
                }

    return {
        "status": "ok",
        "error": None,
        "workbench": wb,
        "addin_source": addin_source,
        "addin_content": old_content,
        "header_class": target_header_class,
        "header_id": target_header_id,
        "load_name": load_name,
        "class_name": target_class_name,
        "needs_declare": needs_declare,
        "is_idempotent": is_idempotent,
    }


def resolve_resource_host(workbench: Any) -> Optional[Path]:
    """Resolve the resource host framework directory for a workbench.

    Strict explicit host resolution: only accepts workbench.framework.path.
    If workbench has no framework or no framework path, returns None.
    Never guesses or climbs directory hierarchies looking for .edu/IdentityCard.
    """
    if not workbench:
        return None
    fw = getattr(workbench, "framework", None)
    if not fw:
        return None
    fw_path = getattr(fw, "path", None)
    if not fw_path:
        return None
    return Path(fw_path)


def _resolve_icon_bytes(icon_name: str, hint: Optional[str] = None) -> Optional[bytes]:
    """Try to resolve icon bytes using icon_provider."""
    try:
        from icon_provider import get_icon
        ico_path = get_icon(icon_name, hint=hint)
        if ico_path and ico_path.exists():
            return ico_path.read_bytes()
    except Exception:
        pass
    return None


def _queue_icon_binary(
    cs: ChangeSet,
    fw_path: Path,
    icon_ref: str,
    target_path: Optional[Path] = None,
    icon_bytes: Optional[bytes] = None,
    source: str = "workbench",
) -> None:
    """Queue icon binary into ChangeSet if available and not already identical."""
    if target_path is None:
        target_path = fw_path / "CNext" / "resources" / "graphic" / "icons" / "normal" / f"{icon_ref}.bmp"
    if icon_bytes is None:
        icon_base = icon_ref[2:] if icon_ref.startswith("I_") else icon_ref
        icon_bytes = _resolve_icon_bytes(icon_base)
    if icon_bytes is None:
        return

    key = str(target_path)
    existing_bytes = None
    if key in cs._binary:
        existing_bytes = cs._binary[key]
    elif target_path.exists():
        existing_bytes = target_path.read_bytes()

    if existing_bytes is not None:
        if existing_bytes != icon_bytes:
            raise ValueError(
                f"Icon binary conflict for {target_path.name}: "
                f"target file already exists with different content from '{source}'"
            )
        return  # identical bytes -> idempotent no-op

    cs.add_create_binary(target_path, icon_bytes)


def inspect_header_resources(
    ctx: ActionContext,
    workbench_name: str,
    header_class: str,
    header_id: str,
    command_name: str,
    *,
    title: Optional[str] = None,
    tooltip: Optional[str] = None,
    icon: Optional[str] = None,
    icon_bytes: Optional[bytes] = None,
    cs: Optional[ChangeSet] = None,
) -> Dict:
    """Read-only inspection of workbench header resources (CATNls, CATRsc, Icon).

    Validates that:
      - The workbench has a valid explicit resource host framework (workbench.framework.path)
      - NLS keys do not conflict with existing definitions (same key + different value)
      - RSC keys do not conflict with existing definitions (same key + different value)
      - Icon binary does not conflict with existing file on disk / staged in CS
    Returns {"status": "ok", ...} or {"status": "error", "error": "..."}.
    """
    wbs = ctx.snapshot.get_all_workbenches()
    wb = next((w for w in wbs if w.name.lower() == workbench_name.lower()), None)
    if not wb:
        return {"status": "error", "error": f"Workbench not found: {workbench_name}"}

    fw_path = resolve_resource_host(wb)
    if not fw_path:
        return {
            "status": "error",
            "error": (
                f"Cannot resolve resource host for workbench '{workbench_name}': "
                "workbench has no framework or framework path configured."
            ),
        }

    target_title = (title or tooltip or command_name).replace('"', '\\"')
    target_tooltip = (tooltip or title or command_name).replace('"', '\\"')
    raw_icon = icon or command_name.lower()
    icon_ref = raw_icon if raw_icon.startswith("I_") else f"I_{raw_icon}"
    icon_ref = icon_ref.replace('"', '')
    icon_base_name = icon_ref[2:]

    msg_dir = fw_path / "CNext" / "resources" / "msgcatalog"
    nls_file = msg_dir / f"{header_class}.CATNls"
    nls_file_zh = msg_dir / "Simplified_Chinese" / f"{header_class}.CATNls"
    rsc_file = msg_dir / f"{header_class}.CATRsc"
    icon_dir = fw_path / "CNext" / "resources" / "graphic" / "icons" / "normal"
    icon_file = icon_dir / f"{icon_ref}.bmp"

    nls_entries = {
        f"{header_class}.{header_id}.Title": f'"{target_title}"',
        f"{header_class}.{header_id}.ShortHelp": f'"{target_tooltip}"',
        f"{header_class}.{header_id}.Help": f'"{target_tooltip}"',
        f"{header_class}.{header_id}.LongHelp": f'"{target_tooltip}"',
    }
    rsc_entries = {
        f"{header_class}.{header_id}.Icon.Normal": f'"{icon_ref}"',
    }

    def _inspect_file_keys(file_path: Path, entries: Dict[str, str], is_gbk: bool, is_rsc: bool) -> Optional[str]:
        key = str(file_path)
        base = None
        if cs is not None and key in cs.modified:
            base = cs.modified[key]
        elif cs is not None and key in cs.created:
            base = cs.created[key]
        elif file_path.exists():
            enc = "gbk" if is_gbk else "utf-8"
            base = file_path.read_text(encoding=enc, errors="replace")

        if not base:
            return None

        assignments = _rsc_assignments(base) if is_rsc else _nls_assignments(base)
        for k, v in entries.items():
            if k in assignments:
                if assignments[k] != v:
                    file_type = "CATRsc" if is_rsc else "CATNls"
                    verb = "assigned as" if is_rsc else "defined as"
                    target_verb = "assign as" if is_rsc else "set to"
                    return (
                        f"{file_type} key conflict in {file_path.name}: '{k}' is already "
                        f"{verb} {assignments[k]!r}, cannot {target_verb} {v!r}"
                    )
        return None

    # Check NLS conflict (English)
    err_nls = _inspect_file_keys(nls_file, nls_entries, is_gbk=False, is_rsc=False)
    if err_nls:
        return {"status": "error", "error": err_nls}

    # Check NLS conflict (Simplified_Chinese)
    err_nls_zh = _inspect_file_keys(nls_file_zh, nls_entries, is_gbk=True, is_rsc=False)
    if err_nls_zh:
        return {"status": "error", "error": err_nls_zh}

    # Check RSC conflict
    err_rsc = _inspect_file_keys(rsc_file, rsc_entries, is_gbk=False, is_rsc=True)
    if err_rsc:
        return {"status": "error", "error": err_rsc}

    # Check icon binary conflict
    target_icon_bytes = icon_bytes if icon_bytes is not None else _resolve_icon_bytes(icon_base_name)
    if target_icon_bytes is not None:
        key = str(icon_file)
        existing_bytes = None
        if cs is not None and key in cs._binary:
            existing_bytes = cs._binary[key]
        elif icon_file.exists():
            existing_bytes = icon_file.read_bytes()

        if existing_bytes is not None and existing_bytes != target_icon_bytes:
            return {
                "status": "error",
                "error": (
                    f"Icon binary conflict for {icon_file.name}: "
                    "target file already exists with different content"
                ),
            }

    return {
        "status": "ok",
        "error": None,
        "workbench": wb,
        "resource_host": fw_path,
        "header_class": header_class,
        "header_id": header_id,
        "command_name": command_name,
        "title": target_title,
        "tooltip": target_tooltip,
        "icon_ref": icon_ref,
        "icon_base_name": icon_base_name,
        "icon_bytes": target_icon_bytes,
        "nls_file": nls_file,
        "nls_file_zh": nls_file_zh,
        "rsc_file": rsc_file,
        "icon_file": icon_file,
    }


def queue_header_resources(
    cs: ChangeSet,
    inspection: Dict,
    source: str = "workbench",
) -> None:
    """Queue header resources into ChangeSet based on inspection result."""
    hdr_cls = inspection["header_class"]
    hdr_id = inspection["header_id"]
    title = inspection["title"]
    tooltip = inspection["tooltip"]
    icon_ref = inspection["icon_ref"]

    # 1. English CATNls
    nls_content = (
        f"\n// Command Header: {hdr_cls}.{hdr_id}\n"
        f'{hdr_cls}.{hdr_id}.Title     = "{title}";\n'
        f'{hdr_cls}.{hdr_id}.ShortHelp = "{tooltip}";\n'
        f'{hdr_cls}.{hdr_id}.Help      = "{tooltip}";\n'
        f'{hdr_cls}.{hdr_id}.LongHelp  = "{tooltip}";\n'
    )
    _queue_nls(cs, inspection["nls_file"], nls_content, source)

    # 2. Chinese CATNls (Simplified_Chinese)
    nls_content_zh = (
        f"\n// 命令头: {hdr_cls}.{hdr_id}\n"
        f'{hdr_cls}.{hdr_id}.Title     = "{title}";\n'
        f'{hdr_cls}.{hdr_id}.ShortHelp = "{tooltip}";\n'
        f'{hdr_cls}.{hdr_id}.Help      = "{tooltip}";\n'
        f'{hdr_cls}.{hdr_id}.LongHelp  = "{tooltip}";\n'
    )
    _queue_nls(cs, inspection["nls_file_zh"], nls_content_zh, source)

    # 3. CATRsc
    rsc_content = (
        f"\n// Command Header Icon: {hdr_cls}.{hdr_id}\n"
        f'{hdr_cls}.{hdr_id}.Icon.Normal = "{icon_ref}";\n'
    )
    _queue_rsc(cs, inspection["rsc_file"], rsc_content, source)

    # 4. Icon Binary
    _queue_icon_binary(
        cs,
        fw_path=inspection["resource_host"],
        icon_ref=icon_ref,
        target_path=inspection["icon_file"],
        icon_bytes=inspection.get("icon_bytes"),
        source=source,
    )


def add_command_to_workbench(
    ctx: ActionContext,
    command_name: str,
    workbench_name: str,
    *,
    load_name: Optional[str] = None,
    title: Optional[str] = None,
    tooltip: Optional[str] = None,
    icon: Optional[str] = None,
    icon_bytes: Optional[bytes] = None,
    cs: ChangeSet = None,
) -> Dict:
    """Register a 4-parameter command header in a workbench's Addin source file
    and queue corresponding workbench header resources (.CATNls, .CATRsc, icon).

    Inserts the 4-parameter command header registration in the Addin's
    CreateCommands() method using the decoupled CATCommandHeader architecture.
    Supports both existing commands and commands queued in a caller-owned
    ChangeSet (`cs`).
    """
    ctx.refresh()
    cmds = ctx.snapshot.get_all_commands()

    cmd = next((c for c in cmds if c.name.lower() == command_name.lower()), None)
    cmd_in_cs = False

    if cmd:
        pass
    elif cs is not None:
        meta_cmd = cs.metadata.get("command")
        if meta_cmd and meta_cmd.lower() == command_name.lower():
            cmd_in_cs = True
        else:
            for p_str in cs.created:
                p = Path(p_str)
                if p.stem.lower() == command_name.lower() and p.suffix.lower() in (".cpp", ".h"):
                    cmd_in_cs = True
                    break

    if not cmd and not cmd_in_cs:
        return _error(f"Command not found: {command_name}")

    target_load_name = load_name or (cs.metadata.get("load_name") if cs else None)
    target_class_name = (cs.metadata.get("class_name") if cs else None) or command_name

    inspection = inspect_workbench_registration(
        ctx,
        workbench_name=workbench_name,
        command_name=command_name,
        load_name=target_load_name,
        class_name=target_class_name,
        cs=cs,
    )
    if inspection["status"] == "error":
        return _error(inspection["error"])

    target_header_class = inspection["header_class"]
    target_header_id = inspection["header_id"]

    rsc_inspection = inspect_header_resources(
        ctx,
        workbench_name=workbench_name,
        header_class=target_header_class,
        header_id=target_header_id,
        command_name=command_name,
        title=title,
        tooltip=tooltip,
        icon=icon,
        icon_bytes=icon_bytes,
        cs=cs,
    )
    if rsc_inspection["status"] == "error":
        return _error(rsc_inspection["error"])

    addin_source = inspection["addin_source"]
    addin_str = str(addin_source)
    old_content = inspection["addin_content"]
    content = old_content

    if not inspection["is_idempotent"]:
        if inspection["needs_declare"]:
            header_decl = f"MacDeclareHeader({target_header_class});"
            matches = list(re.finditer(r'^[ \t]*#include\s+[<"][^>"]+[>"].*$', content, re.MULTILINE))
            if matches:
                last_match = matches[-1]
                pos = last_match.end()
                content = content[:pos] + f"\n\n{header_decl}" + content[pos:]
            else:
                content = f"{header_decl}\n\n" + content

        m_real = re.search(r"void\s+\w+::CreateCommands\s*\([^)]*\)\s*\{", content)
        if not m_real:
            return _error(f"Could not locate CreateCommands() in {addin_source}")
        anchor = m_real.group(0)
        reg_statement = f'    new {target_header_class}("{target_header_id}", "{target_load_name}", "{target_class_name}", (void *)NULL);'
        content = content.replace(anchor, anchor + f"\n{reg_statement}", 1)

    cs = cs if cs is not None else ChangeSet(
        action="add_command_to_workbench",
        description=f"Add '{command_name}' to workbench '{workbench_name}'",
    )

    if content != old_content:
        if addin_str in cs.created:
            cs.created[addin_str] = content
        else:
            cs.add_modify(addin_source, content)

    # Queue resources (CATNls, CATRsc, Icon binary)
    queue_header_resources(cs, rsc_inspection, source=f"workbench:{workbench_name}")

    cs.merge_metadata(
        command=command_name,
        workbench=workbench_name,
        header_class=target_header_class,
        header_id=target_header_id,
        load_name=target_load_name,
        class_name=target_class_name,
    )
    return _result(cs)


def _mask_comments_and_strings(code: str) -> str:
    """Mask C/C++ comments and string/char literals with spaces, preserving exact length and newlines."""
    pattern = re.compile(
        r'//[^\r\n]*'
        r'|/\*[\s\S]*?\*/'
        r'|"(?:\\.|[^"\\])*"'
        r"|'(?:\\.|[^'\\])*'",
        re.MULTILINE,
    )

    def replacer(match):
        s = match.group(0)
        return re.sub(r'[^\r\n]', ' ', s)

    return pattern.sub(replacer, code)


def _mask_comments_only(code: str) -> str:
    """Mask C/C++ comments with spaces, preserving string literals, exact length and newlines."""
    pattern = re.compile(
        r'//[^\r\n]*'
        r'|/\*[\s\S]*?\*/',
        re.MULTILINE,
    )

    def replacer(match):
        s = match.group(0)
        return re.sub(r'[^\r\n]', ' ', s)

    return pattern.sub(replacer, code)


def _extract_create_commands_scope(text: str) -> Optional[Tuple[str, int, int]]:
    """Extract body and character boundaries of CreateCommands() method.

    Returns (body, body_start_idx, body_end_idx) where:
      - body_start_idx is the index right after the opening '{'
      - body_end_idx is the index of the closing '}'
      - body is text[body_start_idx:body_end_idx]
    Returns None if CreateCommands() or its balanced braces cannot be found.
    """
    masked = _mask_comments_and_strings(text)
    m = re.search(r"void\s+(?:\w+::)?CreateCommands\s*\([^)]*\)", masked)
    if not m:
        return None

    open_brace_idx = masked.find('{', m.end())
    if open_brace_idx == -1:
        return None

    depth = 0
    end_brace_idx = -1
    for i in range(open_brace_idx, len(masked)):
        ch = masked[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end_brace_idx = i
                break

    if depth != 0 or end_brace_idx == -1:
        return None

    body_start_idx = open_brace_idx + 1
    body_end_idx = end_brace_idx
    body = text[body_start_idx:body_end_idx]
    return body, body_start_idx, body_end_idx


def _extract_create_toolbars_scope(text: str) -> Optional[Tuple[str, int, int]]:
    """Extract body and character boundaries of CreateToolbars() method.

    Returns (body, body_start_idx, body_end_idx) where:
      - body_start_idx is the index right after the opening '{'
      - body_end_idx is the index of the closing '}'
      - body is text[body_start_idx:body_end_idx]
    Returns None if CreateToolbars() or its balanced braces cannot be found.
    """
    masked = _mask_comments_and_strings(text)
    m = re.search(r"CATCmdContainer\s*\*\s*(?:\w+::)?CreateToolbars\s*\([^)]*\)", masked)
    if not m:
        return None

    open_brace_idx = masked.find('{', m.end())
    if open_brace_idx == -1:
        return None

    depth = 0
    end_brace_idx = -1
    for i in range(open_brace_idx, len(masked)):
        ch = masked[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end_brace_idx = i
                break

    if depth != 0 or end_brace_idx == -1:
        return None

    body_start_idx = open_brace_idx + 1
    body_end_idx = end_brace_idx
    body = text[body_start_idx:body_end_idx]
    return body, body_start_idx, body_end_idx


def _sanitize_identifier(name: str) -> str:
    """Sanitize a command or header ID to a valid C++ identifier token."""
    token = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if token.endswith("Hdr") and len(token) > 3:
        token = token[:-3]
    if not token or token == "_":
        token = "Cmd"
    if token[0].isdigit():
        token = f"_{token}"
    return token


def _discover_toolbars(body: str) -> List[Dict[str, str]]:
    """Discover all toolbars in CreateToolbars body.

    A container is recognized as a Toolbar iff it has both:
      1. NewAccess(CATCmdContainer, var, id)
      2. AddToolbarView(var, ...)
    Menubars and other containers lacking AddToolbarView are excluded (C1 / RB13).
    """
    stripped = strip_c_comments(body)
    containers = re.findall(
        r'NewAccess\s*\(\s*CATCmdContainer\s*,\s*(\w+)\s*,\s*(\w+)\s*\)',
        stripped,
    )
    toolbars = []
    seen_vars = set()
    for var, tlb_id in containers:
        if var in seen_vars:
            continue
        if re.search(r'\bAddToolbarView\s*\(\s*' + re.escape(var) + r'\s*,', stripped):
            toolbars.append({"var": var, "id": tlb_id})
            seen_vars.add(var)
    return toolbars


def _trace_starter_chain(
    body: str,
    tlb_var: str,
    target_header_id: str,
) -> Dict[str, Any]:
    """Trace the starter chain for a specific toolbar container.

    Checks:
      - Starter declarations: NewAccess(CATCmdStarter, var, id)
      - Single child entry: SetAccessChild(tlb_var, first_starter)
      - Linked list siblings: SetAccessNext(prev, next)
      - Commands: SetAccessCommand(var, "HeaderID")
      - Anomaly detection (RB15/RB16):
          * Incomplete syntax (missing/extra args)
          * Multiple SetAccessChild on tlb_var
          * Undefined starters in chain
          * Forking / branching (multiple nexts from same starter)
          * Cycles in chain
          * Convergence (multiple predecessors to same starter)
    """
    stripped = strip_c_comments(body)

    # 1. Container-level syntax checks for tlb_var
    if re.search(r'\bSetAccessChild\s*\(\s*' + re.escape(tlb_var) + r'\s*\)', stripped):
        raise ValueError("Incomplete SetAccessChild statement with missing arguments in CreateToolbars()")
    if re.search(r'\bSetAccessChild\s*\(\s*' + re.escape(tlb_var) + r'\s*,\s*[^,)]+,\s*[^)]+\)', stripped):
        raise ValueError("Malformed SetAccessChild statement with too many arguments in CreateToolbars()")

    # 2. Declared starters
    starters = re.findall(r'\bNewAccess\s*\(\s*CATCmdStarter\s*,\s*(\w+)\s*,\s*(\w+)\s*\)', stripped)
    declared_starters = {var: sid for var, sid in starters}

    # 3. Children linked to toolbars
    children = re.findall(r'\bSetAccessChild\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)', stripped)
    tlb_children = [starter for c, starter in children if c == tlb_var]
    if len(tlb_children) > 1:
        raise ValueError(f"Multiple SetAccessChild calls found for toolbar container '{tlb_var}' ({tlb_children})")

    # 4. Command headers
    cmd_links = re.findall(r'\bSetAccessCommand\s*\(\s*(\w+)\s*,\s*"([^"]+)"\s*\)', stripped)
    starter_headers: Dict[str, str] = {}
    for s_var, hdr in cmd_links:
        starter_headers[s_var] = hdr

    if len(tlb_children) == 0:
        return {
            "chain": [],
            "first_starter": None,
            "last_starter": None,
            "is_idempotent": False,
            "starter_headers": starter_headers,
        }

    first_starter = tlb_children[0]
    if first_starter not in declared_starters:
        raise ValueError(f"Starter '{first_starter}' linked to toolbar '{tlb_var}' is not declared via NewAccess(CATCmdStarter, ...)")

    # 5. Next links
    next_links = re.findall(r'\bSetAccessNext\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)', stripped)
    outgoing: Dict[str, List[str]] = {}
    incoming: Dict[str, List[str]] = {}
    for prev_var, next_var in next_links:
        outgoing.setdefault(prev_var, []).append(next_var)
        incoming.setdefault(next_var, []).append(prev_var)

    # Check multiple predecessors on first_starter
    if len(incoming.get(first_starter, [])) > 1:
        raise ValueError(f"Multiple predecessors point to starter '{first_starter}' via SetAccessNext")

    def _check_starter_syntax(s: str) -> None:
        if re.search(r'\bSetAccessNext\s*\(\s*' + re.escape(s) + r'\s*\)', stripped):
            raise ValueError("Incomplete SetAccessNext statement with missing arguments in CreateToolbars()")
        if re.search(r'\bSetAccessNext\s*\(\s*' + re.escape(s) + r'\s*,\s*[^,)]+,\s*[^)]+\)', stripped) or \
           re.search(r'\bSetAccessNext\s*\(\s*[^,)]+,\s*' + re.escape(s) + r'\s*,\s*[^)]+\)', stripped):
            raise ValueError("Malformed SetAccessNext statement with too many arguments in CreateToolbars()")
        if re.search(r'\bSetAccessCommand\s*\(\s*' + re.escape(s) + r'\s*\)', stripped):
            raise ValueError("Incomplete SetAccessCommand statement with missing arguments in CreateToolbars()")
        if re.search(r'\bSetAccessCommand\s*\(\s*' + re.escape(s) + r'\s*,\s*[^,)]+,\s*[^)]+\)', stripped):
            raise ValueError("Malformed SetAccessCommand statement with too many arguments in CreateToolbars()")

    # Check syntax on first_starter
    _check_starter_syntax(first_starter)

    # 6. Trace chain for this specific toolbar starting from first_starter
    chain = [first_starter]
    seen = {first_starter}
    curr = first_starter
    while True:
        next_vars = outgoing.get(curr, [])
        if len(next_vars) > 1:
            raise ValueError(f"Fork/branching detected in toolbar chain: starter '{curr}' has multiple SetAccessNext calls")
        if len(next_vars) == 0:
            break

        nxt = next_vars[0]
        if nxt in seen:
            raise ValueError(f"Cycle detected in toolbar chain involving starter '{nxt}'")
        if len(incoming.get(nxt, [])) > 1:
            raise ValueError(f"Multiple predecessors point to starter '{nxt}' via SetAccessNext")
        if nxt not in declared_starters:
            raise ValueError(f"Starter '{nxt}' in SetAccessNext is not declared via NewAccess(CATCmdStarter, ...)")

        _check_starter_syntax(nxt)

        chain.append(nxt)
        seen.add(nxt)
        curr = nxt

    is_idempotent = any(starter_headers.get(s) == target_header_id for s in chain)

    return {
        "chain": chain,
        "first_starter": first_starter,
        "last_starter": chain[-1],
        "is_idempotent": is_idempotent,
        "starter_headers": starter_headers,
    }


def inspect_toolbar_mount(
    ctx: ActionContext,
    workbench_name: str,
    header_id: str,
    *,
    toolbar_id: Optional[str] = None,
    cs: Optional[ChangeSet] = None,
) -> Dict:
    """Inspect workbench and addin source to compute a deterministic ToolbarMountPlan.

    Pure read-only inspection:
      - Resolves workbench entity and addin source
      - Extracts CreateToolbars() method scope
      - Discovers toolbars via NewAccess(CATCmdContainer, ...) + AddToolbarView(...)
      - Selects target toolbar according to C2 decision matrix (RB1~RB6)
      - Traces starter chain & validates chain topology (RB15, RB16)
      - Detects idempotency (C4 / RB10 / RB11)
      - Generates sanitized, non-colliding starter variable names (RB12)
      - Computes deterministic anchor statement and source offset
    Returns a dict with status "ok" and a decoupled "plan" dict, or status "error".
    """
    if not header_id or not header_id.strip():
        return {"status": "error", "error": "header_id must not be empty", "plan": None}

    wbs = ctx.snapshot.get_all_workbenches()
    wb = next((w for w in wbs if w.name.lower() == workbench_name.lower()), None)
    if not wb:
        return {"status": "error", "error": f"Workbench not found: {workbench_name}", "plan": None}

    addin_source = wb.addin_source or wb.addin_source_path()
    if not addin_source:
        return {"status": "error", "error": f"Workbench '{workbench_name}' has no Addin source configured", "plan": None}

    addin_str = str(addin_source)
    old_content = None
    if cs is not None and addin_str in cs.modified:
        old_content = cs.modified[addin_str]
    elif cs is not None and addin_str in cs.created:
        old_content = cs.created[addin_str]
    elif addin_source.exists():
        old_content = addin_source.read_text(encoding="utf-8", errors="replace")

    if old_content is None:
        return {"status": "error", "error": f"Workbench '{workbench_name}' Addin source not found: {addin_source}", "plan": None}

    scope = _extract_create_toolbars_scope(old_content)
    if not scope:
        return {"status": "error", "error": f"Could not locate CreateToolbars() in {addin_source}", "plan": None}

    body, body_start_idx, body_end_idx = scope
    toolbars = _discover_toolbars(body)

    # C2 Decision Matrix (RB1~RB6)
    if len(toolbars) == 0:
        return {
            "status": "error",
            "error": f"No toolbars found in CreateToolbars() for workbench '{workbench_name}'. Cannot attach command without an existing toolbar.",
            "plan": None,
        }

    target_tlb = None
    if toolbar_id is None:
        if len(toolbars) == 1:
            target_tlb = toolbars[0]
        else:
            avail_ids = [t["id"] for t in toolbars]
            return {
                "status": "error",
                "error": f"Multiple toolbars found in CreateToolbars() for workbench '{workbench_name}' ({avail_ids}). Please specify toolbar_id explicitly.",
                "plan": None,
            }
    else:
        target_tlb = next((t for t in toolbars if t["id"].lower() == toolbar_id.lower()), None)
        if not target_tlb:
            avail_ids = [t["id"] for t in toolbars]
            return {
                "status": "error",
                "error": f"Toolbar '{toolbar_id}' not found in CreateToolbars() for workbench '{workbench_name}'. Available: {avail_ids}",
                "plan": None,
            }

    tlb_var = target_tlb["var"]
    try:
        chain_info = _trace_starter_chain(body, tlb_var, header_id)
    except ValueError as e:
        return {"status": "error", "error": str(e), "plan": None}

    chain = chain_info["chain"]
    is_idempotent = chain_info["is_idempotent"]
    last_starter_var = chain_info["last_starter"]

    # Generate sanitized starter names and resolve variable collision in body (RB12)
    token = _sanitize_identifier(header_id)
    base_var = f"p{token}Str"
    base_id = f"{token}Str"

    new_starter_var = base_var
    new_starter_id = base_id
    suffix = 2
    while re.search(r'\b' + re.escape(new_starter_var) + r'\b', body):
        new_starter_var = f"{base_var}_{suffix}"
        new_starter_id = f"{base_id}_{suffix}"
        suffix += 1

    # Determine insertion mode and anchor statement
    if len(chain) == 0:
        insertion_mode = "child"
        last_starter_var = None
        m_view = re.search(r'AddToolbarView\s*\(\s*' + re.escape(tlb_var) + r'\s*,[^;]*\);', body)
        if m_view:
            anchor_stmt = m_view.group(0)
            anchor_end_in_body = m_view.end()
        else:
            m_new = re.search(r'NewAccess\s*\(\s*CATCmdContainer\s*,\s*' + re.escape(tlb_var) + r'\s*,[^;]*\);', body)
            if not m_new:
                return {"status": "error", "error": f"Could not locate anchor for toolbar '{tlb_var}' in CreateToolbars()", "plan": None}
            anchor_stmt = m_new.group(0)
            anchor_end_in_body = m_new.end()
    else:
        insertion_mode = "next"
        patterns = [
            r'NewAccess\s*\(\s*CATCmdStarter\s*,\s*' + re.escape(last_starter_var) + r'\s*,[^;]*\);',
            r'SetAccessCommand\s*\(\s*' + re.escape(last_starter_var) + r'\s*,[^;]*\);',
            r'SetAccessChild\s*\(\s*' + re.escape(tlb_var) + r'\s*,\s*' + re.escape(last_starter_var) + r'\s*\);',
            r'SetAccessNext\s*\(\s*\w+\s*,\s*' + re.escape(last_starter_var) + r'\s*\);',
        ]
        best_end = -1
        best_stmt = None
        for pat in patterns:
            for m in re.finditer(pat, body):
                if m.end() > best_end:
                    best_end = m.end()
                    best_stmt = m.group(0)

        if not best_stmt:
            return {
                "status": "error",
                "error": f"Could not locate anchor statement for existing starter '{last_starter_var}' in CreateToolbars()",
                "plan": None,
            }
        anchor_stmt = best_stmt
        anchor_end_in_body = best_end

    anchor_offset = body_start_idx + anchor_end_in_body
    anchor_line = old_content[:anchor_offset].count('\n') + 1

    plan = {
        "toolbar_id": target_tlb["id"],
        "toolbar_var": target_tlb["var"],
        "insertion_mode": insertion_mode,
        "anchor_statement": anchor_stmt,
        "anchor_line": anchor_line,
        "anchor_offset": anchor_offset,
        "last_starter_var": last_starter_var,
        "new_starter_var": new_starter_var,
        "new_starter_id": new_starter_id,
        "is_idempotent": is_idempotent,
    }

    return {
        "status": "ok",
        "error": None,
        "workbench": wb,
        "addin_source": addin_source,
        "addin_content": old_content,
        "plan": plan,
    }


def attach_command_to_toolbar(
    ctx: ActionContext,
    workbench_name: str,
    header_id: str,
    *,
    toolbar_id: Optional[str] = None,
    cs: Optional[ChangeSet] = None,
) -> Dict:
    """Attach a command HeaderID to a toolbar in workbench Addin source.

    Inserts Starter creation and linking in CreateToolbars():
      - First starter uses SetAccessChild(pToolbar, pStarter)
      - Subsequent starters use SetAccessNext(pPrevStarter, pNextStarter)
    Guarantees:
      - Toolbar isolation (RB9)
      - Idempotent no-op if (ToolbarID, HeaderID) already mounted (RB10)
      - Multi-toolbar support (RB11)
      - Variable name collision renaming (RB12)
      - Menubar exclusion (RB13)
      - Zero mutation on pre-validation errors (RB14)
    """
    inspection = inspect_toolbar_mount(
        ctx,
        workbench_name=workbench_name,
        header_id=header_id,
        toolbar_id=toolbar_id,
        cs=cs,
    )
    if inspection["status"] == "error":
        return _error(inspection["error"])

    plan = inspection["plan"]
    addin_source = inspection["addin_source"]
    addin_str = str(addin_source)
    old_content = inspection["addin_content"]
    content = old_content

    cs = cs if cs is not None else ChangeSet(
        action="attach_command_to_toolbar",
        description=f"Attach header '{header_id}' to toolbar '{plan['toolbar_id']}' in workbench '{workbench_name}'",
    )

    if not plan["is_idempotent"]:
        scope = _extract_create_toolbars_scope(content)
        if not scope:
            return _error(f"Could not locate CreateToolbars() in {addin_source}")
        _, body_start, body_end = scope

        anchor = plan["anchor_statement"]
        idx = content.find(anchor, body_start)
        if idx == -1 or idx >= body_end:
            return _error(f"Could not locate anchor statement in CreateToolbars(): {anchor}")

        line_start = content.rfind('\n', 0, idx)
        line_start = 0 if line_start == -1 else line_start + 1
        indent = ""
        while line_start < idx and content[line_start] in (' ', '\t'):
            indent += content[line_start]
            line_start += 1
        if not indent:
            indent = "    "

        if plan["insertion_mode"] == "child":
            lines = [
                f"{indent}NewAccess(CATCmdStarter, {plan['new_starter_var']}, {plan['new_starter_id']});",
                f"{indent}SetAccessCommand({plan['new_starter_var']}, \"{header_id}\");",
                f"{indent}SetAccessChild({plan['toolbar_var']}, {plan['new_starter_var']});",
            ]
        else:
            lines = [
                f"{indent}NewAccess(CATCmdStarter, {plan['new_starter_var']}, {plan['new_starter_id']});",
                f"{indent}SetAccessCommand({plan['new_starter_var']}, \"{header_id}\");",
                f"{indent}SetAccessNext({plan['last_starter_var']}, {plan['new_starter_var']});",
            ]
        block = "\n".join(lines)

        end_of_line = content.find('\n', idx + len(anchor))
        if end_of_line != -1:
            content = content[:end_of_line + 1] + block + "\n" + content[end_of_line + 1:]
        else:
            content = content + "\n" + block

        if addin_str in cs.created:
            cs.created[addin_str] = content
        else:
            cs.add_modify(addin_source, content)

    cs.merge_metadata(
        workbench=workbench_name,
        toolbar_id=plan["toolbar_id"],
        header_id=header_id,
        starter_var=plan["new_starter_var"],
        is_idempotent=plan["is_idempotent"],
    )
    return _result(cs)


# ══════════════════════════════════════════════════════════════════
#  DELETE ACTIONS (reversible)
# ══════════════════════════════════════════════════════════════════


def inspect_delete_command(
    ctx: ActionContext,
    name: str,
    *,
    module: Optional[str] = None,
    workbench_name: Optional[str] = None,
    cs: Optional[ChangeSet] = None,
) -> Dict[str, Any]:
    """Inspect workspace to compute a deterministic CommandDeletePlan (R-4-A).

    Pure read-only pre-validation:
      - Validates command entity and identity (DA1)
      - Locates workbench Addin source (explicit or discovered)
      - Validates unique 4-parameter header registration in CreateCommands() (DA1, DA8, DA9)
      - Traces only target toolbars mounting target HeaderID (DA10)
      - Detects duplicate MountKey in target toolbar (DA13)
      - Determines toolbar starter splicing plan & mode (DA2~DA6: remove_only_child, new_child, relink_next, remove_tail)
      - Detects multi-toolbar mounts (DA7)
      - Identifies command files and orphan resources (without deleting)
      - Preserves ChangeSet zero-mutation on any failure (DA11)
    """
    ctx.refresh()
    mod = ctx.snapshot.get_module(module) if module else None
    cmd = None
    if mod:
        cmd = next((c for c in mod.commands if c.name.lower() == name.lower()), None)
    if not cmd:
        all_cmds = ctx.snapshot.get_all_commands()
        cmd = next((c for c in all_cmds if c.name.lower() == name.lower()), None)
    if not cmd:
        return {"status": "error", "error": f"Command not found: {name}", "plan": None}

    wbs = ctx.snapshot.get_all_workbenches()
    if workbench_name:
        wb = next((w for w in wbs if w.name.lower() == workbench_name.lower()), None)
        if not wb:
            return {"status": "error", "error": f"Workbench not found: {workbench_name}", "plan": None}
        target_wbs = [wb]
    else:
        if len(wbs) == 0:
            return {"status": "error", "error": "No workbenches found in workspace", "plan": None}
        target_wbs = wbs

    target_class_name = getattr(cmd, "class_name", None) or cmd.name
    expected_load_name = cmd.module.bare_name if cmd.module else (cmd.module.name if cmd.module else None)

    # 1. Search for 4-param header registration across candidate workbenches
    candidate_matches = []
    reg_pattern = re.compile(
        r'new\s+(\w+)\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*(?:\(void\s*\*\)\s*)?NULL\s*\)\s*;?'
    )

    for candidate_wb in target_wbs:
        addin_source = candidate_wb.addin_source or candidate_wb.addin_source_path()
        if not addin_source:
            continue
        addin_str = str(addin_source)
        content = None
        if cs is not None and addin_str in cs.modified:
            content = cs.modified[addin_str]
        elif cs is not None and addin_str in cs.created:
            content = cs.created[addin_str]
        elif addin_source.exists():
            content = addin_source.read_text(encoding="utf-8", errors="replace")
        if content is None:
            continue

        scope_cc = _extract_create_commands_scope(content)
        if not scope_cc:
            continue
        cc_body, cc_start_idx, cc_end_idx = scope_cc

        masked_cc = _mask_comments_only(cc_body)
        for m in reg_pattern.finditer(masked_cc):
            h_cls, h_id, l_name, c_name = m.groups()
            if c_name == target_class_name:
                candidate_matches.append((
                    candidate_wb,
                    addin_source,
                    content,
                    h_cls,
                    h_id,
                    l_name,
                    c_name,
                    m,
                    cc_start_idx,
                ))

    # DA8: Header registration not found
    if len(candidate_matches) == 0:
        if workbench_name:
            wb_addin = target_wbs[0].addin_source or target_wbs[0].addin_source_path()
            return {
                "status": "error",
                "error": f"Header registration for command '{name}' (class '{target_class_name}') not found in {wb_addin}",
                "plan": None,
            }
        return {
            "status": "error",
            "error": f"Header registration for command '{name}' (class '{target_class_name}') not found in any workbench",
            "plan": None,
        }

    # DA9: Duplicate header registration
    if len(candidate_matches) > 1:
        wbs_in_matches = {m[0].name for m in candidate_matches}
        if len(wbs_in_matches) == 1:
            return {
                "status": "error",
                "error": f"Duplicate header registration found for command '{name}' in {candidate_matches[0][1]}",
                "plan": None,
            }
        return {
            "status": "error",
            "error": f"Multiple workbenches ({list(wbs_in_matches)}) contain registration for command '{name}'. Please specify workbench_name explicitly.",
            "plan": None,
        }

    (
        wb,
        addin_source,
        content,
        matched_hdr_cls,
        matched_hdr_id,
        matched_ld_name,
        matched_cls_name,
        m_reg,
        cc_start_idx,
    ) = candidate_matches[0]

    # DA1 Tightened identity: verify load_name consistency if known
    if expected_load_name and matched_ld_name.lower() != expected_load_name.lower():
        return {
            "status": "error",
            "error": (
                f"Header registration load_name conflict for command '{name}': "
                f"found '{matched_ld_name}', expected '{expected_load_name}'"
            ),
            "plan": None,
        }

    header_statement = content[cc_start_idx + m_reg.start():cc_start_idx + m_reg.end()]

    # 2. Inspect toolbar starter mountings in CreateToolbars()
    toolbar_splices = []
    scope_tb = _extract_create_toolbars_scope(content)
    if scope_tb:
        tb_body, tb_start_idx, tb_end_idx = scope_tb
        toolbars = _discover_toolbars(tb_body)
        stripped_tb = strip_c_comments(tb_body)

        cmd_links = re.findall(r'\bSetAccessCommand\s*\(\s*(\w+)\s*,\s*"([^"]+)"\s*\)', stripped_tb)
        matching_starters = [s for s, hdr in cmd_links if hdr == matched_hdr_id]

        if matching_starters:
            children = re.findall(r'\bSetAccessChild\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)', stripped_tb)
            child_map = {starter: tlb_v for tlb_v, starter in children}

            next_links = re.findall(r'\bSetAccessNext\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)', stripped_tb)
            prev_map = {nxt: prv for prv, nxt in next_links}

            target_tlb_vars = set()
            for s_var in matching_starters:
                curr = s_var
                seen_back = {curr}
                while curr in prev_map and curr not in child_map:
                    curr = prev_map[curr]
                    if curr in seen_back:
                        break
                    seen_back.add(curr)
                if curr in child_map:
                    target_tlb_vars.add(child_map[curr])

            target_toolbars = [t for t in toolbars if t["var"] in target_tlb_vars]

            # DA10: Trace and validate ONLY target toolbars
            for tlb in target_toolbars:
                tlb_var = tlb["var"]
                tlb_id = tlb["id"]
                try:
                    chain_info = _trace_starter_chain(tb_body, tlb_var, matched_hdr_id)
                except ValueError as e:
                    return {"status": "error", "error": str(e), "plan": None}

                chain = chain_info["chain"]
                starter_headers = chain_info["starter_headers"]
                starters_for_hdr = [s for s in chain if starter_headers.get(s) == matched_hdr_id]

                # DA13: Duplicate mount in the same toolbar
                if len(starters_for_hdr) > 1:
                    return {
                        "status": "error",
                        "error": f"Duplicate mount of HeaderID '{matched_hdr_id}' in toolbar '{tlb_id}' ({tlb_var})",
                        "plan": None,
                    }

                if len(starters_for_hdr) == 1:
                    tgt_starter = starters_for_hdr[0]
                    n = len(chain)
                    idx = chain.index(tgt_starter)

                    # Determine splicing mode (DA3)
                    if n == 1:
                        splice_mode = "remove_only_child"
                        prev_var = None
                        next_var = None
                    elif idx == 0:
                        splice_mode = "new_child"
                        prev_var = None
                        next_var = chain[1]
                    elif idx == n - 1:
                        splice_mode = "remove_tail"
                        prev_var = chain[idx - 1]
                        next_var = None
                    else:
                        splice_mode = "relink_next"
                        prev_var = chain[idx - 1]
                        next_var = chain[idx + 1]

                    stmts_to_remove = []
                    stmts_to_add = []

                    m_new = re.search(r'\bNewAccess\s*\(\s*CATCmdStarter\s*,\s*' + re.escape(tgt_starter) + r'\s*,[^;]*\);', tb_body)
                    if m_new:
                        stmts_to_remove.append(m_new.group(0))

                    m_cmd = re.search(r'\bSetAccessCommand\s*\(\s*' + re.escape(tgt_starter) + r'\s*,\s*"[^"]*"\s*\);', tb_body)
                    if m_cmd:
                        stmts_to_remove.append(m_cmd.group(0))

                    if splice_mode == "remove_only_child":
                        m_child = re.search(r'\bSetAccessChild\s*\(\s*' + re.escape(tlb_var) + r'\s*,\s*' + re.escape(tgt_starter) + r'\s*\);', tb_body)
                        if m_child:
                            stmts_to_remove.append(m_child.group(0))
                    elif splice_mode == "new_child":
                        m_child = re.search(r'\bSetAccessChild\s*\(\s*' + re.escape(tlb_var) + r'\s*,\s*' + re.escape(tgt_starter) + r'\s*\);', tb_body)
                        if m_child:
                            stmts_to_remove.append(m_child.group(0))
                        m_next = re.search(r'\bSetAccessNext\s*\(\s*' + re.escape(tgt_starter) + r'\s*,\s*' + re.escape(next_var) + r'\s*\);', tb_body)
                        if m_next:
                            stmts_to_remove.append(m_next.group(0))
                        stmts_to_add.append(f"SetAccessChild({tlb_var}, {next_var});")
                    elif splice_mode == "relink_next":
                        m_prev_next = re.search(r'\bSetAccessNext\s*\(\s*' + re.escape(prev_var) + r'\s*,\s*' + re.escape(tgt_starter) + r'\s*\);', tb_body)
                        if m_prev_next:
                            stmts_to_remove.append(m_prev_next.group(0))
                        m_next = re.search(r'\bSetAccessNext\s*\(\s*' + re.escape(tgt_starter) + r'\s*,\s*' + re.escape(next_var) + r'\s*\);', tb_body)
                        if m_next:
                            stmts_to_remove.append(m_next.group(0))
                        stmts_to_add.append(f"SetAccessNext({prev_var}, {next_var});")
                    elif splice_mode == "remove_tail":
                        m_prev_next = re.search(r'\bSetAccessNext\s*\(\s*' + re.escape(prev_var) + r'\s*,\s*' + re.escape(tgt_starter) + r'\s*\);', tb_body)
                        if m_prev_next:
                            stmts_to_remove.append(m_prev_next.group(0))

                    toolbar_splices.append({
                        "toolbar_id": tlb_id,
                        "toolbar_var": tlb_var,
                        "starter_var": tgt_starter,
                        "splice_mode": splice_mode,
                        "prev_starter_var": prev_var,
                        "next_starter_var": next_var,
                        "statements_to_remove": stmts_to_remove,
                        "statements_to_add": stmts_to_add,
                    })

    # 3. Command files & orphan resources
    cmd_files = [f for f in cmd.all_files if f.exists()]
    if cmd.dialog:
        cmd_files.extend([f for f in cmd.dialog.all_files if f.exists()])
    imakefile_path = cmd.module.imakefile_path() if (cmd.module and cmd.module.imakefile_path().exists()) else None

    orphan_resources = []
    fw = getattr(wb, "framework", None)
    if not fw and hasattr(wb, "framework_name") and wb.framework_name:
        fw = ctx.snapshot.get_framework(wb.framework_name)
    if not fw and cmd.module and hasattr(cmd.module, "framework"):
        fw = cmd.module.framework

    if fw:
        nls_path = fw.cnext_dir() / "resources" / "msgcatalog" / f"{matched_hdr_cls}.CATNls"
        if nls_path.exists():
            nls_text = nls_path.read_text(encoding="utf-8", errors="replace")
            if f"{matched_hdr_cls}.{matched_hdr_id}" in nls_text or matched_hdr_id in nls_text:
                orphan_resources.append({
                    "type": "nls",
                    "path": str(nls_path),
                    "key_prefix": f"{matched_hdr_cls}.{matched_hdr_id}",
                })
        rsc_path = fw.cnext_dir() / "resources" / "msgcatalog" / f"{matched_hdr_cls}.CATRsc"
        if rsc_path.exists():
            rsc_text = rsc_path.read_text(encoding="utf-8", errors="replace")
            if f"{matched_hdr_cls}.{matched_hdr_id}" in rsc_text or matched_hdr_id in rsc_text:
                orphan_resources.append({
                    "type": "rsc",
                    "path": str(rsc_path),
                    "key_prefix": f"{matched_hdr_cls}.{matched_hdr_id}",
                })
        icon_name = getattr(cmd, "icon", None) or name
        icon_path = fw.cnext_dir() / "resources" / "graphic" / "icons" / "normal" / f"I_{icon_name}.bmp"
        if icon_path.exists():
            orphan_resources.append({
                "type": "icon",
                "path": str(icon_path),
            })

    plan = {
        "command_name": name,
        "class_name": matched_cls_name,
        "header_class": matched_hdr_cls,
        "header_id": matched_hdr_id,
        "load_name": matched_ld_name,
        "workbench_name": wb.name,
        "addin_source": str(addin_source),
        "header_statement": header_statement,
        "toolbar_splices": toolbar_splices,
        "command_files": [str(f) for f in cmd_files],
        "imakefile_path": str(imakefile_path) if imakefile_path else None,
        "orphan_resources": orphan_resources,
    }
    return {
        "status": "ok",
        "error": None,
        "plan": plan,
    }


def delete_command(
    ctx: ActionContext, name: str, module: str = None, framework: str = None
) -> Dict:
    """
    Delete a Command AND all related files with cascade detection.
    Removes: .h, .cpp, Header.cpp, Dialog (if owned), Catalog entry, NLS entries, Imakefile references.

    Returns preview with warnings if other entities depend on this command.
    """
    ctx.refresh()
    mod = ctx.snapshot.get_module(module, framework) if module else None
    cmd = None

    if mod:
        cmd = next((c for c in mod.commands if c.name.lower() == name.lower()), None)
    if not cmd:
        all_cmds = ctx.snapshot.get_all_commands()
        cmd = next((c for c in all_cmds if c.name.lower() == name.lower()), None)
    if not cmd:
        return _error(f"Command not found: {name}")

    cs = ChangeSet(
        action="delete_command",
        description=f"Delete command '{name}' and ALL related files",
    )

    # Check for breaking dependents (e.g., workbenches using this command)
    breaking_deps = ctx.snapshot.find_breaking_dependents(cmd)
    if breaking_deps:
        warnings = []
        for dep, reason in breaking_deps:
            warnings.append(reason)
            cs.add_warning(reason)

        # Add to metadata for AI to decide
        cs.metadata["breaking_dependents"] = [
            {"name": dep.name, "type": dep.__class__.__name__.lower(), "reason": reason}
            for dep, reason in breaking_deps
        ]

    # Find all files to delete using cascade
    cascade_entities = ctx.snapshot.find_cascade_delete(cmd)

    # Delete main command files using domain model
    for f in cmd.all_files:
        if f.exists():
            cs.add_delete(f)

    # Delete owned dialog if exists
    if cmd.dialog:
        for f in cmd.dialog.all_files:
            if f.exists():
                cs.add_delete(f)

    # Clean Imakefile reference
    if cmd.module and cmd.module.imakefile_path().exists():
        old = cmd.module.imakefile_path().read_text(encoding="utf-8", errors="replace")
        new = "\n".join([l for l in old.split("\n") if cmd.name not in l])
        if new != old:
            cs.add_modify(cmd.module.imakefile_path(), new)

    # Add metadata
    cs.metadata.update(
        {
            "command": name,
            "deleted_files": [str(d) for d in cs.deleted],
            "cascade_count": len(cascade_entities),
            "has_breaking_dependents": len(breaking_deps) > 0,
        }
    )

    return _result(cs)


def delete_module(ctx: ActionContext, name: str, framework: str = None) -> Dict:
    """Delete a Module and ALL its contents (commands, dialogs, interfaces, components)"""
    ctx.refresh()
    mod = ctx.snapshot.get_module(name, framework)
    if not mod:
        return _error(f"Module not found: {name}")

    cs = ChangeSet(
        action="delete_module", description=f"Delete module '{name}' and ALL children"
    )

    # Collect all files through the module
    for cmd in mod.commands:
        _delete_command_to_cs(cmd, cs)
    for dlg in mod.dialogs:
        if dlg.header:
            cs.add_delete(dlg.header)
        cs.add_delete(dlg.path)

    if mod.imakefile:
        cs.add_delete(mod.imakefile)
    for d in ["src", "LocalInterfaces", "PublicInterfaces", "resources"]:
        dpath = mod.path / d
        if dpath.exists():
            for f in dpath.rglob("*"):
                if f.is_file() and f.name != ".gitkeep":
                    cs.add_delete(f)

    cs.add_warning(f"Module directory '{mod.path}' will be removed recursively")
    cs.metadata = {"module": name, "deleted_files_count": len(cs.deleted)}
    return _result(cs)


def _delete_command_to_cs(cmd: Command, cs: ChangeSet):
    """Add all command-related files to a ChangeSet for deletion"""
    for f in [cmd.header, cmd.source, cmd.header_source]:
        if f and f.exists():
            cs.add_delete(f)


# ══════════════════════════════════════════════════════════════════
#  ENHANCED QUERY ACTIONS (Phase 1)
# ══════════════════════════════════════════════════════════════════


def get_dependencies(
    ctx: ActionContext, entity_name: str, entity_type: str = None
) -> Dict:
    """
    Get all entities that the specified entity depends on.

    Args:
        entity_name: Name of the entity (e.g., "MyCommand")
        entity_type: Type hint ("command", "module", "interface", etc.)

    Returns:
        {
            "status": "ok",
            "entity": {"name": "...", "type": "..."},
            "dependencies": [{"name": "...", "type": "...", "relationship": "..."}],
            "count": 5
        }
    """
    ctx.refresh()
    snapshot = ctx.snapshot

    # Find the entity
    entity = None
    actual_type = None

    if entity_type == "command" or entity_type is None:
        entity = next(
            (c for c in snapshot.get_all_commands() if c.name == entity_name), None
        )
        if entity:
            actual_type = "command"

    if not entity and (entity_type == "module" or entity_type is None):
        entity = snapshot.get_module(entity_name)
        if entity:
            actual_type = "module"

    if not entity and (entity_type == "interface" or entity_type is None):
        entity = next(
            (i for i in snapshot.get_all_interfaces() if i.name == entity_name), None
        )
        if entity:
            actual_type = "interface"

    if not entity:
        return _error(f"Entity '{entity_name}' not found")

    # Get dependencies from dependency graph
    deps = snapshot.get_dependencies(entity)

    dependencies = []
    for dep in deps:
        dependencies.append(
            {
                "name": dep.name,
                "type": dep.__class__.__name__.lower(),
                "path": str(dep.path) if hasattr(dep, "path") else None,
            }
        )

    return {
        "status": "ok",
        "entity": {"name": entity_name, "type": actual_type},
        "dependencies": dependencies,
        "count": len(dependencies),
    }


def get_dependents(
    ctx: ActionContext, entity_name: str, entity_type: str = None
) -> Dict:
    """
    Get all entities that depend on the specified entity.
    Useful to check what will break if this entity is deleted.

    Returns:
        {
            "status": "ok",
            "entity": {"name": "...", "type": "..."},
            "dependents": [{"name": "...", "type": "..."}],
            "warnings": ["MyWorkbench uses this command"],
            "count": 3
        }
    """
    ctx.refresh()
    snapshot = ctx.snapshot

    # Find the entity (similar logic to get_dependencies)
    entity = None
    actual_type = None

    if entity_type == "command" or entity_type is None:
        entity = next(
            (c for c in snapshot.get_all_commands() if c.name == entity_name), None
        )
        if entity:
            actual_type = "command"

    if not entity and (entity_type == "module" or entity_type is None):
        entity = snapshot.get_module(entity_name)
        if entity:
            actual_type = "module"

    if not entity:
        return _error(f"Entity '{entity_name}' not found")

    # Get dependents from dependency graph
    dependents_list = snapshot.get_dependents(entity)

    dependents = []
    warnings = []
    for dep in dependents_list:
        dependents.append(
            {
                "name": dep.name,
                "type": dep.__class__.__name__.lower(),
                "path": str(dep.path) if hasattr(dep, "path") else None,
            }
        )
        warnings.append(
            f"{dep.name} ({dep.__class__.__name__}) depends on {entity_name}"
        )

    return {
        "status": "ok",
        "entity": {"name": entity_name, "type": actual_type},
        "dependents": dependents,
        "warnings": warnings if dependents else [],
        "count": len(dependents),
    }


def visualize_dependencies(ctx: ActionContext, entity_name: str = None) -> Dict:
    """
    Generate a Mermaid diagram showing entity relationships.

    Args:
        entity_name: If provided, focuses on this entity's neighborhood.
                    If None, shows entire workspace dependencies.

    Returns:
        {
            "status": "ok",
            "diagram": "graph TD\n    ...",
            "entity": "MyCommand" or null
        }
    """
    ctx.refresh()
    snapshot = ctx.snapshot

    entity = None
    if entity_name:
        # Find entity
        entity = next(
            (c for c in snapshot.get_all_commands() if c.name == entity_name), None
        )
        if not entity:
            entity = snapshot.get_module(entity_name)
        if not entity:
            return _error(f"Entity '{entity_name}' not found")

    diagram = snapshot.visualize_dependencies(entity)

    return {
        "status": "ok",
        "diagram": diagram,
        "entity": entity_name,
        "message": "Dependency diagram generated successfully",
    }


def validate_workspace(ctx: ActionContext) -> Dict:
    """
    Validate workspace for common issues:
    - Broken references
    - Missing dependencies
    - Orphaned files
    - Inconsistent naming

    Returns:
        {
            "status": "ok" | "warning",
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
    """
    ctx.refresh()
    snapshot = ctx.snapshot

    errors = []
    warnings = list(snapshot.warnings)
    suggestions = []

    # Check for commands without headers
    for cmd in snapshot.get_all_commands():
        if not cmd.header or not cmd.header.exists():
            warnings.append(f"Command '{cmd.name}' missing header file")
        if not cmd.source or not cmd.source.exists():
            errors.append(f"Command '{cmd.name}' missing source file")

    # Check for orphaned files
    if snapshot.orphaned_files:
        warnings.append(f"Found {len(snapshot.orphaned_files)} orphaned files")
        suggestions.append("Run cleanup to remove orphaned files")

    # Check for modules without commands
    for fw in snapshot.frameworks:
        for mod in fw.modules:
            if not mod.commands and not mod.interfaces and not mod.components:
                warnings.append(f"Module '{mod.name}' is empty")
                suggestions.append(f"Consider deleting empty module '{mod.name}'")

    status = "ok" if not errors else "error"
    if warnings and status == "ok":
        status = "warning"

    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "suggestions": suggestions,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def find_orphaned_files(ctx: ActionContext) -> Dict:
    """
    Find files that exist but are not referenced by any entity.

    Returns:
        {
            "status": "ok",
            "orphaned_files": ["path/to/file1.cpp", ...],
            "count": 5
        }
    """
    ctx.refresh()
    snapshot = ctx.snapshot

    orphaned = [str(f) for f in snapshot.orphaned_files]

    return {
        "status": "ok",
        "orphaned_files": orphaned,
        "count": len(orphaned),
        "message": f"Found {len(orphaned)} orphaned files"
        if orphaned
        else "No orphaned files found",
    }


# ══════════════════════════════════════════════════════════════════
#  ROLLBACK SUPPORT (Phase 3)
# ══════════════════════════════════════════════════════════════════


def rollback_operation(ctx: ActionContext, backup_id: str) -> Dict:
    """
    Rollback to a specific backup point.

    Args:
        ctx: Action context
        backup_id: Backup identifier (e.g., "20260707_143022")

    Returns:
        {
            "status": "success",
            "message": "Successfully rolled back to ...",
            "backup_id": "...",
            "action": "create_command",
            "restored": {...}
        }

    Example:
        >>> result = rollback_operation(ctx, "20260707_143022")
        >>> print(result["message"])
    """
    from backup import rollback_operation as rb_op

    return rb_op(ctx.workspace_root, backup_id)


def list_rollback_points(ctx: ActionContext) -> Dict:
    """
    List all available rollback points.

    Args:
        ctx: Action context

    Returns:
        {
            "status": "ok",
            "backups": [
                {
                    "backup_id": "20260707_143022",
                    "timestamp": "2026-07-07T14:30:22",
                    "action": "create_executable_command",
                    "description": "...",
                    "created": [...],
                    "modified": [...]
                }
            ],
            "count": 5
        }

    Example:
        >>> result = list_rollback_points(ctx)
        >>> for backup in result["backups"]:
        ...     print(f"{backup['backup_id']}: {backup['action']}")
    """
    from backup import list_rollback_points as list_rb

    return list_rb(ctx.workspace_root)


def cleanup_old_backups(ctx: ActionContext, keep_count: int = 10) -> Dict:
    """
    Clean up old backups, keeping only recent ones.

    Args:
        ctx: Action context
        keep_count: Number of recent backups to keep

    Returns:
        {
            "status": "success",
            "message": "...",
            "deleted": [...],
            "kept": [...]
        }

    Example:
        >>> result = cleanup_old_backups(ctx, keep_count=5)
        >>> print(f"Deleted {len(result['deleted'])} old backups")
    """
    from backup import cleanup_backups

    return cleanup_backups(ctx.workspace_root, keep_count)


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════


def _r(
    name: str, fw_name: str = "MyFramework", mod_name: str = "MyModule", **extra
) -> Dict[str, str]:
    """Build replacement dict for template filling — single source of truth"""
    fw = fw_name.replace(".edu", "")
    mod = mod_name.replace(".m", "")
    return {
        "YYYY": str(datetime.now().year),
        "PREFIX": name,
        # Entity names
        "ClassName": name,
        "ComponentName": name,
        "COMPONENTNAME": name.upper(),
        "IInterfaceName": name,
        "TestCaseName": name,
        "AddinName": name,
        "EventListenerName": name,
        "WorkshopAddinName": name,
        "XmlTestCaseName": name,
        "FeatureClass": name,
        "WorkbenchClass": name,
        "DialogClass": name,
        "DialogClassName": name,
        "CommandClassName": name,
        "CommandHeaderName": f"{name}Header",
        "IIDLInterfaceName": name,
        # Framework/Module
        "FrameworkName": fw,
        "FRAMEWORKNAME": fw.upper(),
        "ModuleName": mod,
        "MODULENAME": mod.upper(),
        **extra,
    }


# ══════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════

ACTIONS = {
    "analyze": (analyze_workspace, "Analyze workspace structure"),
    "list-modules": (list_modules, "List all modules"),
    "list-commands": (list_commands, "List all commands"),
    "list-workbenches": (list_workbenches, "List all workbenches"),
    "list-interfaces": (list_interfaces, "List all interfaces"),
    "get-dependencies": (get_dependencies, "Get entity dependencies"),
    "get-dependents": (get_dependents, "Get entities that depend on this"),
    "visualize": (visualize_dependencies, "Generate dependency diagram"),
    "validate": (validate_workspace, "Validate workspace for issues"),
    "find-orphaned": (find_orphaned_files, "Find orphaned files"),
    "rollback": (rollback_operation, "Rollback to backup point"),
    "list-backups": (list_rollback_points, "List all rollback points"),
    "cleanup-backups": (cleanup_old_backups, "Clean up old backups"),
}


def main():
    parser = argparse.ArgumentParser(description="CAA Atomic Development Actions")
    parser.add_argument(
        "action", choices=list(ACTIONS.keys()), help="Action to perform"
    )
    parser.add_argument("-w", "--workspace", default=".", help="Workspace path")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    ctx = ActionContext(args.workspace)
    fn, desc = ACTIONS[args.action]
    result = fn(ctx)
    output_json(result)


if __name__ == "__main__":
    main()
