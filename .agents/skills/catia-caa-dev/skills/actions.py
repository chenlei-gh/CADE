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
import hashlib
import re
import sys
import xml.etree.ElementTree as ET
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


def create_workbench(
    ctx: ActionContext,
    name: str,
    framework: Optional[str] = None,
    *,
    module: Optional[str] = None,
    plan: Optional[Dict[str, Any]] = None,
    cs: Optional[ChangeSet] = None,
    generate_icon: bool = False,
) -> Dict[str, Any]:
    """Create a Workbench with Addin and register to general workshop (W-1-B Phase 2).

    Strictly consumes the WorkbenchCreatePlan (schema 2.0) computed by inspect_create_workbench()
    to maintain transaction integrity, concurrent modification resistance, and rollback symmetry.
    Guarantees:
      - Plan v2.0 schema and identity binding (name, framework, module)
      - Host directory scope and path escape verification (relative_to)
      - Post-plan newly discovered file collisions hard rejection (no blind overwrite)
      - Physical raw byte snapshot SHA-256 hash checks against concurrent tampering
      - Caller-owned ChangeSet conflict detection and atomic staging
    """
    ctx.refresh()

    if plan is None:
        inspect_res = inspect_create_workbench(
            ctx,
            name,
            framework=framework,
            module=module,
            cs=cs,
            generate_icon=generate_icon,
        )
        if inspect_res.get("status") != "ok":
            return _error(inspect_res.get("error") or f"Inspection failed for workbench '{name}'")
        plan = inspect_res["plan"]

    # 1. Plan schema and identity binding validation
    if plan.get("plan_schema_version") != "2.0":
        return _error(f"Incompatible or missing plan_schema_version: expected '2.0', got '{plan.get('plan_schema_version')}'")

    wid = plan.get("workbench_identity")
    if not isinstance(wid, dict):
        return _error("Plan missing or invalid workbench_identity")

    if wid.get("name") != name:
        return _error(f"Plan workbench_identity mismatch: expected name '{name}', got '{wid.get('name')}'")

    fw_name = wid.get("framework")
    mod_name = wid.get("module")

    if framework and fw_name != framework:
        return _error(f"Plan framework mismatch: expected '{framework}', got '{fw_name}'")
    if module and mod_name != module:
        return _error(f"Plan module mismatch: expected '{module}', got '{mod_name}'")

    target_fw = ctx.snapshot.get_framework(fw_name) if fw_name else None
    if not target_fw:
        return _error(f"Target framework '{fw_name}' not found in workspace")

    target_mod = ctx.snapshot.get_module(mod_name, fw_name) if mod_name else None
    if not target_mod:
        return _error(f"Target module '{mod_name}' not found in framework '{fw_name}'")

    fw_root = target_fw.path.resolve()

    # 2. Path boundary & scope verification (no directory escape)
    for fc in plan.get("file_creations", []):
        p = Path(fc["path"]).resolve()
        try:
            p.relative_to(fw_root)
        except ValueError:
            return _error(f"Plan file creation path outside target framework directory: {p}")

    for patch in plan.get("patches", []):
        p = Path(patch["path"]).resolve()
        try:
            p.relative_to(fw_root)
        except ValueError:
            return _error(f"Plan patch path outside target framework directory: {p}")

    # 3. Post-plan newly discovered file collision checks (disk state)
    # Strictly enforce Scheme A: no blind overwrite on ANY creation target, including binary icons.
    for fc in plan.get("file_creations", []):
        p = Path(fc["path"])
        if p.exists():
            return _error(f"Target creation file already exists on disk: {p}")

    # 4. Caller ChangeSet conflict detection
    if cs is not None:
        for fc in plan.get("file_creations", []):
            p_str = str(Path(fc["path"]))
            if p_str in cs.created and cs.created[p_str] != fc["content"]:
                return _error(f"Conflict on {p_str}: already created with different content in caller ChangeSet")
            if p_str in cs.modified:
                return _error(f"Conflict on {p_str}: planned for creation but already marked modified in caller ChangeSet")
            if p_str in (str(d) for d in cs.deleted):
                return _error(f"Conflict on {p_str}: planned for creation but marked deleted in caller ChangeSet")

        for patch in plan.get("patches", []):
            p_str = str(Path(patch["path"]))
            if p_str in (str(d) for d in cs.deleted):
                return _error(f"Conflict on {p_str}: planned for modification but marked deleted in caller ChangeSet")
            if p_str in cs.created:
                return _error(f"Conflict on {p_str}: planned for modification but marked created in caller ChangeSet")

    # 5. Verify source snapshot physical byte hashes against concurrent tampering
    for patch in plan.get("patches", []):
        snap = patch.get("source_snapshot")
        if not snap:
            return _error(f"Plan patch missing source_snapshot: {patch.get('path')}")
        p = Path(patch["path"])
        raw_bytes, current_content, enc = _read_file_bytes_and_text(p, cs=cs)
        if raw_bytes is None:
            return _error(f"Source file not found or unreadable during workbench create: {p}")

        cur_hash = hashlib.sha256(raw_bytes).hexdigest()
        cur_len = len(raw_bytes)
        expected_hash = snap.get("content_hash") or snap.get("sha256")
        expected_len = snap.get("content_length") if "content_length" in snap else snap.get("byte_length")
        if cur_hash != expected_hash or (expected_len is not None and cur_len != expected_len):
            hash_display = expected_hash[:12] if expected_hash else "unknown"
            return _error(
                f"Concurrent modification detected on {p}: expected hash {hash_display} "
                f"({expected_len} bytes), got {cur_hash[:12]} ({cur_len} bytes)"
            )

    # 6. Initialize or reuse ChangeSet and stage operations
    master_cs = cs if cs is not None else ChangeSet(
        action="create_workbench", description=f"Create workbench '{name}' with addin"
    )

    for fc in plan.get("file_creations", []):
        if fc.get("kind") == "icon_binary" and fc.get("binary_b64"):
            import base64
            master_cs.add_create_binary(Path(fc["path"]), base64.b64decode(fc["binary_b64"]))
        else:
            master_cs.add_create(Path(fc["path"]), fc["content"])

    for patch in plan.get("patches", []):
        master_cs.add_modify(Path(patch["path"]), patch["new_content"])

    master_cs.merge_metadata(
        workbench=name,
        addin_class=wid.get("addin_class"),
        framework=fw_name,
        module=mod_name,
        plan=plan,
    )

    return _result(master_cs)


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
    m = re.search(r"void\s+(?:\w+::)?CreateCommands\s*\([^)\n;]*\)", masked)
    if not m:
        return None

    open_brace_idx = masked.find('{', m.end())
    if open_brace_idx == -1:
        return None

    # Between signature end and opening brace, only whitespace is allowed
    if masked[m.end():open_brace_idx].strip():
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
    m = re.search(r"CATCmdContainer\s*\*\s*(?:\w+::)?CreateToolbars\s*\([^)\n;]*\)", masked)
    if not m:
        return None

    open_brace_idx = masked.find('{', m.end())
    if open_brace_idx == -1:
        return None

    # Between signature end and opening brace, only whitespace is allowed
    if masked[m.end():open_brace_idx].strip():
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
    framework: Optional[str] = None,
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
    mod = ctx.snapshot.get_module(module, framework) if module else None
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

        masked_content = _mask_comments_and_strings(content)
        cc_defs = list(re.finditer(r"void\s+(?:\w+::)?CreateCommands\s*\([^)]*\)", masked_content))
        if len(cc_defs) > 1:
            return {
                "status": "error",
                "error": f"Multiple CreateCommands() definitions found in {addin_source}; cannot disambiguate target scope",
                "plan": None,
            }

        scope_cc = _extract_create_commands_scope(content)
        if len(cc_defs) == 1 and not scope_cc:
            return {
                "status": "error",
                "error": f"Cannot reliably extract CreateCommands() scope in {addin_source}: unbalanced braces or malformed function definition",
                "plan": None,
            }
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
    masked_content = _mask_comments_and_strings(content)
    tb_defs = list(re.finditer(r"CATCmdContainer\s*\*\s*(?:\w+::)?CreateToolbars\s*\([^)]*\)", masked_content))
    if len(tb_defs) > 1:
        return {
            "status": "error",
            "error": f"Multiple CreateToolbars() definitions found in {addin_source}; cannot disambiguate target scope",
            "plan": None,
        }

    scope_tb = _extract_create_toolbars_scope(content)
    if len(tb_defs) == 1 and not scope_tb:
        return {
            "status": "error",
            "error": f"Cannot reliably extract CreateToolbars() scope in {addin_source}: unbalanced braces or malformed function definition",
            "plan": None,
        }

    stripped_full = strip_c_comments(content)
    has_header_in_file = bool(re.search(r'\bSetAccessCommand\s*\(\s*\w+\s*,\s*"' + re.escape(matched_hdr_id) + r'"\s*\)', stripped_full))
    if has_header_in_file and not scope_tb:
        return {
            "status": "error",
            "error": f"Header '{matched_hdr_id}' is referenced by toolbar starter, but CreateToolbars() scope cannot be found or extracted in {addin_source}",
            "plan": None,
        }

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


def _remove_statement_line(
    content: str,
    stmt: str,
    replace_with: Optional[str] = None,
    search_start: int = 0,
    search_end: Optional[int] = None,
) -> str:
    """Remove or replace a single C++ statement line in content within optional scope bounds.

    If search_start / search_end are specified, the search for stmt is strictly bounded.
    If the line containing stmt has only whitespace before/after stmt,
    the entire line (including newline) is replaced by indent + replace_with,
    or deleted entirely. Otherwise, inline replacement/deletion is performed.
    """
    if not stmt:
        return content
    end_bound = len(content) if search_end is None else search_end
    idx = content.find(stmt, search_start, end_bound)
    if idx == -1:
        return content

    line_start = content.rfind("\n", 0, idx)
    line_start = 0 if line_start == -1 else line_start + 1
    indent = content[line_start:idx]

    line_end = content.find("\n", idx + len(stmt))
    if line_end == -1:
        line_end = len(content)
        has_newline = False
    else:
        has_newline = True

    trailing = content[idx + len(stmt):line_end]

    if indent.strip() == "" and trailing.strip() == "":
        if replace_with is not None:
            new_line = indent + replace_with + ("\n" if has_newline else "")
            return content[:line_start] + new_line + content[line_end + (1 if has_newline else 0):]
        else:
            return content[:line_start] + content[line_end + (1 if has_newline else 0):]
    else:
        if replace_with is not None:
            return content[:idx] + replace_with + content[idx + len(stmt):]
        else:
            return content[:idx] + content[idx + len(stmt):]


def _clean_imakefile_content(
    content: str, name: str, class_name: Optional[str] = None
) -> str:
    """Clean references to a command from Imakefile.mk using exact token boundaries (R-4-A).

    Preserves byte-fidelity (CRLF/LF line endings, indentation, tabs, and alignment).
    Protects LINK_WITH, BUILT_OBJECT_TYPE, and comment lines.
    Maintains Makefile continuation chain syntax (trailing backslashes) cleanly.
    """
    targets = set()
    if name:
        targets.add(name)
    if class_name:
        targets.add(class_name)
    if not targets:
        return content

    raw_lines = content.splitlines(keepends=True)
    out_lines = []

    for idx, line in enumerate(raw_lines):
        line_strip = line.strip()
        if line_strip.startswith(("LINK_WITH", "BUILT_OBJECT_TYPE", "#")):
            out_lines.append(line)
            continue

        if line.endswith("\r\n"):
            nl = "\r\n"
            body = line[:-2]
        elif line.endswith("\n"):
            nl = "\n"
            body = line[:-1]
        else:
            nl = ""
            body = line

        has_match = False
        new_body = body

        for t in targets:
            p = re.compile(
                r'(?P<prefix>(?:^|(?<=[\s=:,]))(?:[a-zA-Z0-9_]+[/\\])?)'
                + re.escape(t)
                + r'(?:\.(?:cpp|cxx|c|h|obj|o))?(?P<suffix>(?=[\s/\\=:,#]|$))',
                re.IGNORECASE,
            )
            while True:
                m = p.search(new_body)
                if not m:
                    break
                has_match = True
                s, e = m.start(), m.end()
                before = new_body[:s]
                after = new_body[e:]
                if before.endswith((" ", "\t")) and after.startswith((" ", "\t")):
                    new_body = before + after.lstrip(" \t")
                elif before.endswith(("=", "+=", ":=")):
                    new_body = before + " " + after.lstrip(" \t")
                else:
                    new_body = before + after

        if not has_match:
            out_lines.append(line)
            continue

        is_assign = bool(re.search(r'^[A-Za-z0-9_]+\s*(?:\+=|:=|=)', new_body.strip()))
        rem_core = new_body.strip().rstrip("\\").strip()
        if is_assign:
            if new_body.rstrip().endswith("\\"):
                head = new_body.rstrip()[:-1].rstrip()
                out_lines.append(f"{head} \\{nl}")
            else:
                out_lines.append(new_body + nl)
        else:
            if rem_core:
                out_lines.append(new_body + nl)
            else:
                had_backslash = body.rstrip().endswith("\\")
                if not had_backslash:
                    for p_idx in range(len(out_lines) - 1, -1, -1):
                        prev = out_lines[p_idx]
                        if prev.strip():
                            if prev.endswith("\r\n"):
                                p_nl = "\r\n"
                                p_body = prev[:-2]
                            elif prev.endswith("\n"):
                                p_nl = "\n"
                                p_body = prev[:-1]
                            else:
                                p_nl = ""
                                p_body = prev
                            r_body = p_body.rstrip()
                            if r_body.endswith("\\"):
                                p_body = r_body[:-1].rstrip()
                                out_lines[p_idx] = p_body + p_nl
                            break

    return "".join(out_lines)


def delete_command(
    ctx: ActionContext,
    name: str,
    module: Optional[str] = None,
    framework: Optional[str] = None,
    workbench_name: Optional[str] = None,
    cs: Optional[ChangeSet] = None,
) -> Dict[str, Any]:
    """Delete a Command and cascade remove its Header registration and Toolbar mounts (R-4-A).

    Strictly consumes the CommandDeletePlan computed by inspect_delete_command()
    to maintain transaction integrity and zero-mutation guarantees upon failure.
    Removes:
      - Command implementation (.h, .cpp, owned dialog files)
      - Imakefile.mk references (if any)
      - Header registration from CreateCommands()
      - Starter mounts from CreateToolbars() with single-chain splicing
    Resources (.CATNls, .CATRsc, .bmp) are NOT deleted; orphan resources are recorded
    in metadata for user audit.
    """
    ctx.refresh()

    inspect_res = inspect_delete_command(
        ctx,
        name,
        module=module,
        framework=framework,
        workbench_name=workbench_name,
        cs=cs,
    )
    if inspect_res.get("status") != "ok":
        return _error(inspect_res.get("error") or f"Delete inspection failed for command '{name}'")

    plan = inspect_res["plan"]

    # Locate command entity for breaking dependents / cascade metadata
    cmd = None
    all_cmds = ctx.snapshot.get_all_commands()
    if module:
        mod = ctx.snapshot.get_module(module, framework)
        if mod:
            cmd = next((c for c in mod.commands if c.name.lower() == name.lower()), None)
    if not cmd:
        cmd = next((c for c in all_cmds if c.name.lower() == name.lower()), None)

    master_cs = cs if cs is not None else ChangeSet(
        action="delete_command",
        description=f"Delete command '{name}' and cascade remove Header registration and Toolbar mounts",
    )

    breaking_deps = ctx.snapshot.find_breaking_dependents(cmd) if cmd else []
    if breaking_deps:
        for dep, reason in breaking_deps:
            master_cs.add_warning(reason)
        master_cs.metadata["breaking_dependents"] = [
            {"name": dep.name, "type": dep.__class__.__name__.lower(), "reason": reason}
            for dep, reason in breaking_deps
        ]

    cascade_entities = ctx.snapshot.find_cascade_delete(cmd) if cmd else []

    # Pre-validate Addin source scopes before staging mutations
    addin_source_str = plan["addin_source"]
    addin_source = Path(addin_source_str)
    if addin_source_str in master_cs.modified:
        content = master_cs.modified[addin_source_str]
    elif addin_source_str in master_cs.created:
        content = master_cs.created[addin_source_str]
    else:
        content = addin_source.read_text(encoding="utf-8", errors="replace")

    header_stmt = plan.get("header_statement")
    if header_stmt:
        cc_scope = _extract_create_commands_scope(content)
        if not cc_scope:
            return _error(f"Cannot reliably extract CreateCommands() scope in {addin_source}")

    toolbar_splices = plan.get("toolbar_splices", [])
    if toolbar_splices:
        tb_scope = _extract_create_toolbars_scope(content)
        if not tb_scope:
            return _error(f"Cannot reliably extract CreateToolbars() scope in {addin_source}")

    # 1. Delete implementation files
    for f_str in plan.get("command_files", []):
        f = Path(f_str)
        if f.exists():
            master_cs.add_delete(f)

    # 2. Update Imakefile.mk (remove references to command/class with exact token matching)
    imakefile_path_str = plan.get("imakefile_path")
    if imakefile_path_str:
        imk_p = Path(imakefile_path_str)
        if imk_p.exists():
            if str(imk_p) in master_cs.modified:
                old_imk = master_cs.modified[str(imk_p)]
            elif str(imk_p) in master_cs.created:
                old_imk = master_cs.created[str(imk_p)]
            else:
                old_imk = imk_p.read_text(encoding="utf-8", errors="replace")

            c_name = plan.get("class_name") or name
            new_imk = _clean_imakefile_content(old_imk, name, c_name)
            if new_imk != old_imk:
                if str(imk_p) in master_cs.created:
                    master_cs.created[str(imk_p)] = new_imk
                else:
                    master_cs.add_modify(imk_p, new_imk)

    # 3. Update Addin source (Header registration + Toolbar splices)
    # 3a. Remove Header registration from CreateCommands() scope
    if header_stmt:
        cc_scope = _extract_create_commands_scope(content)
        if not cc_scope:
            return _error(f"Cannot reliably extract CreateCommands() scope in {addin_source}")
        content = _remove_statement_line(
            content, header_stmt, search_start=cc_scope[1], search_end=cc_scope[2]
        )

    # 3b. Execute toolbar splices strictly within CreateToolbars() scope
    for splice in toolbar_splices:
        mode = splice.get("splice_mode")
        stmts_to_remove = splice.get("statements_to_remove", [])
        stmts_to_add = splice.get("statements_to_add", [])

        tb_scope = _extract_create_toolbars_scope(content)
        if not tb_scope:
            return _error(f"CreateToolbars() scope lost while splicing toolbar in {addin_source}")
        tb_start, tb_end = tb_scope[1], tb_scope[2]

        if mode == "remove_only_child" or mode == "remove_tail":
            for stmt in stmts_to_remove:
                content = _remove_statement_line(
                    content, stmt, search_start=tb_start, search_end=tb_end
                )
                tb_scope = _extract_create_toolbars_scope(content)
                if not tb_scope:
                    return _error(f"CreateToolbars() scope lost while splicing toolbar in {addin_source}")
                tb_start, tb_end = tb_scope[1], tb_scope[2]
        elif mode == "new_child":
            child_stmt = next((s for s in stmts_to_remove if s.strip().startswith("SetAccessChild")), None)
            new_child_stmt = stmts_to_add[0] if stmts_to_add else None
            if child_stmt and new_child_stmt:
                content = _remove_statement_line(
                    content, child_stmt, replace_with=new_child_stmt, search_start=tb_start, search_end=tb_end
                )
                tb_scope = _extract_create_toolbars_scope(content)
                if not tb_scope:
                    return _error(f"CreateToolbars() scope lost while splicing toolbar in {addin_source}")
                tb_start, tb_end = tb_scope[1], tb_scope[2]
            for stmt in stmts_to_remove:
                if stmt != child_stmt:
                    content = _remove_statement_line(
                        content, stmt, search_start=tb_start, search_end=tb_end
                    )
                    tb_scope = _extract_create_toolbars_scope(content)
                    if not tb_scope:
                        return _error(f"CreateToolbars() scope lost while splicing toolbar in {addin_source}")
                    tb_start, tb_end = tb_scope[1], tb_scope[2]
        elif mode == "relink_next":
            prev_var = splice.get("prev_starter_var")
            tgt_starter = splice.get("starter_var")
            prev_next_stmt = next(
                (s for s in stmts_to_remove if s.strip().startswith("SetAccessNext") and prev_var in s and tgt_starter in s),
                None,
            )
            new_next_stmt = stmts_to_add[0] if stmts_to_add else None
            if prev_next_stmt and new_next_stmt:
                content = _remove_statement_line(
                    content, prev_next_stmt, replace_with=new_next_stmt, search_start=tb_start, search_end=tb_end
                )
                tb_scope = _extract_create_toolbars_scope(content)
                if not tb_scope:
                    return _error(f"CreateToolbars() scope lost while splicing toolbar in {addin_source}")
                tb_start, tb_end = tb_scope[1], tb_scope[2]
            for stmt in stmts_to_remove:
                if stmt != prev_next_stmt:
                    content = _remove_statement_line(
                        content, stmt, search_start=tb_start, search_end=tb_end
                    )
                    tb_scope = _extract_create_toolbars_scope(content)
                    if not tb_scope:
                        return _error(f"CreateToolbars() scope lost while splicing toolbar in {addin_source}")
                    tb_start, tb_end = tb_scope[1], tb_scope[2]

    if addin_source_str in master_cs.created:
        master_cs.created[addin_source_str] = content
    else:
        master_cs.add_modify(addin_source, content)

    # 4. Record metadata
    master_cs.metadata.update(
        {
            "command": name,
            "class_name": plan.get("class_name"),
            "header_id": plan.get("header_id"),
            "workbench_name": plan.get("workbench_name"),
            "toolbar_splices": plan.get("toolbar_splices", []),
            "orphan_resources": plan.get("orphan_resources", []),
            "deleted_files": [str(d) for d in master_cs.deleted],
            "cascade_count": len(cascade_entities),
            "has_breaking_dependents": len(breaking_deps) > 0,
        }
    )

    return _result(master_cs)


def _rename_imakefile_content(content: str, old_name: str, new_name: str) -> str:
    """Rename source file tokens in Imakefile.mk with strict token boundary (R-4-B).

    Replaces 'OldCmd.cpp' -> 'NewCmd.cpp' without touching 'OldCmdHelper.cpp'
    or directives like LINK_WITH, BUILT_OBJECT_TYPE, or comments.
    """
    pattern = re.compile(
        r'(?P<prefix>(?:^|(?<=[\s=:]))(?:[a-zA-Z0-9_]+[/\\])?)'
        + re.escape(old_name)
        + r'(?P<ext>\.(?:cpp|cxx|c|h|obj|o))(?=$|[\s/\\=:#,])'
    )
    new_lines = []
    for line in content.splitlines(keepends=True):
        line_strip = line.strip()
        if line_strip.startswith(("LINK_WITH", "BUILT_OBJECT_TYPE", "#")):
            new_lines.append(line)
            continue
        new_line = pattern.sub(r'\g<prefix>' + new_name + r'\g<ext>', line)
        new_lines.append(new_line)
    return "".join(new_lines)


def _compute_cpp_rename_content(
    old_name: str, new_name: str, content: str, is_header: bool = False
) -> Tuple[str, List[Dict[str, str]]]:
    """Perform bounded, semantic-aware C++ token replacement for command renaming (R-4-B).

    Precise structural targets:
      - Include guards (#ifndef/#define/#endif)
      - #include directives for the header
      - CATCreateClass(OldCmd) macro
      - Class declaration / definition: class ... OldCmd : ...
      - Constructor / destructor declarations and definitions
      - Member function qualifiers: OldCmd::
    Plain string literals (e.g. const char* str = "OldCmd";) and comments are left intact.
    """
    replacements: List[Dict[str, str]] = []
    res = content

    # 1. Include guard (if header)
    if is_header:
        p_guard_if = re.compile(r'(#ifndef\s+[_A-Za-z0-9]*?)' + re.escape(old_name) + r'([_A-Za-z0-9]*)')
        if p_guard_if.search(res):
            res = p_guard_if.sub(r'\g<1>' + new_name + r'\2', res)
            replacements.append({"target": "include_guard_ifndef"})

        p_guard_def = re.compile(r'(#define\s+[_A-Za-z0-9]*?)' + re.escape(old_name) + r'([_A-Za-z0-9]*)')
        if p_guard_def.search(res):
            res = p_guard_def.sub(r'\g<1>' + new_name + r'\2', res)
            replacements.append({"target": "include_guard_define"})

        p_guard_end = re.compile(r'(#endif\s*//\s*[_A-Za-z0-9]*?)' + re.escape(old_name) + r'([_A-Za-z0-9]*)')
        if p_guard_end.search(res):
            res = p_guard_end.sub(r'\g<1>' + new_name + r'\2', res)
            replacements.append({"target": "include_guard_endif"})

    # 2. #include directives
    p_inc = re.compile(r'(#include\s+["<])' + re.escape(old_name) + r'(\.h[">])')
    if p_inc.search(res):
        res = p_inc.sub(r'\g<1>' + new_name + r'\2', res)
        replacements.append({"target": "include_directive"})

    # 3. CATCreateClass macro
    p_ccc = re.compile(r'\bCATCreateClass\s*\(\s*' + re.escape(old_name) + r'\s*\)')
    if p_ccc.search(res):
        res = p_ccc.sub(f'CATCreateClass({new_name})', res)
        replacements.append({"target": "cat_create_class"})

    # 4. Class declaration / definition: class [ExportedBy...] OldCmd [: {]
    p_cls = re.compile(r'\bclass\s+([A-Za-z0-9_]+\s+)?' + re.escape(old_name) + r'(\s*[:{])')
    if p_cls.search(res):
        res = p_cls.sub(r'class \g<1>' + new_name + r'\2', res)
        replacements.append({"target": "class_declaration"})

    # 5. Constructor & destructor declarations (header lines like "OldCmd();" or "virtual ~OldCmd();")
    p_ctor_decl = re.compile(r'^\s*' + re.escape(old_name) + r'(\s*\([^;]*\)\s*;)', re.MULTILINE)
    if p_ctor_decl.search(res):
        res = p_ctor_decl.sub(r'  ' + new_name + r'\1', res)
        replacements.append({"target": "constructor_declaration"})

    p_dtor_decl = re.compile(r'^\s*(virtual\s+)?~' + re.escape(old_name) + r'(\s*\([^;]*\)\s*;)', re.MULTILINE)
    if p_dtor_decl.search(res):
        res = p_dtor_decl.sub(r'  \g<1>~' + new_name + r'\2', res)
        replacements.append({"target": "destructor_declaration"})

    # 6. Constructor & destructor definitions (OldCmd::OldCmd / OldCmd::~OldCmd)
    p_ctor_def = re.compile(r'\b' + re.escape(old_name) + r'::' + re.escape(old_name) + r'\b')
    if p_ctor_def.search(res):
        res = p_ctor_def.sub(f'{new_name}::{new_name}', res)
        replacements.append({"target": "constructor_definition"})

    p_dtor_def = re.compile(r'\b' + re.escape(old_name) + r'::~' + re.escape(old_name) + r'\b')
    if p_dtor_def.search(res):
        res = p_dtor_def.sub(f'{new_name}::~{new_name}', res)
        replacements.append({"target": "destructor_definition"})

    # 7. Member function scope qualifiers: OldCmd::Activate(...)
    p_scope = re.compile(r'\b' + re.escape(old_name) + r'::')
    if p_scope.search(res):
        res = p_scope.sub(f'{new_name}::', res)
        replacements.append({"target": "member_function_scope"})

    return res, replacements


def _read_file_bytes_and_text(
    p: Path, cs: Optional[ChangeSet] = None
) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Read raw physical bytes, text content, and detected encoding staged-first.

    Returns (raw_bytes, text_content, encoding) or (None, None, None) if file
    does not exist or cannot be decoded with either UTF-8 or GBK.
    """
    p_str = str(p)
    if cs is not None:
        if p_str in cs.created:
            text = cs.created[p_str]
            enc = "utf-8"
            if p.exists():
                try:
                    p.read_bytes().decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        p.read_bytes().decode("gbk")
                        enc = "gbk"
                    except UnicodeDecodeError:
                        pass
            return text.encode(enc), text, enc
        if p_str in cs.modified:
            text = cs.modified[p_str]
            enc = "utf-8"
            if p.exists():
                try:
                    p.read_bytes().decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        p.read_bytes().decode("gbk")
                        enc = "gbk"
                    except UnicodeDecodeError:
                        pass
            return text.encode(enc), text, enc

    if not p.exists():
        return None, None, None

    try:
        raw = p.read_bytes()
    except Exception:
        return None, None, None

    try:
        text = raw.decode("utf-8")
        return raw, text, "utf-8"
    except UnicodeDecodeError:
        pass

    try:
        text = raw.decode("gbk")
        return raw, text, "gbk"
    except UnicodeDecodeError:
        pass

    return None, None, None


def inspect_rename_command(
    ctx: ActionContext,
    old_name: str,
    new_name: str,
    *,
    module: Optional[str] = None,
    framework: Optional[str] = None,
    workbench_name: Optional[str] = None,
    cs: Optional[ChangeSet] = None,
) -> Dict[str, Any]:
    """Inspect workspace to compute a deterministic CommandRenamePlan (R-4-B Phase 1).

    Pure read-only pre-validation:
      - Validates new_name is a valid C++ identifier (RN3)
      - Validates new_name is not identical to old_name
      - Locates command entity and identity
      - Detects if new_name command already exists in module or workspace (RN2)
      - Detects if target renamed files already exist on disk or staged in cs (RN12)
      - Builds strict source_snapshot with content_hash and content_length
      - Previews bounded C++ semantic token replacements (RN4, RN5, RN6)
      - Previews Imakefile token replacement without touching similar names (RN7)
      - Locates unique 4-parameter header registration in CreateCommands() (RN8, RN10)
      - Previews header registration update with HeaderID strictly stable (RN8, RN9)
      - Audits Toolbar mounts and confirms zero mutation needed (RN9)
      - Audits associated resources without migrating or deleting (RN15)
      - Preserves ChangeSet zero-mutation on any failure (RN11)
    """
    ctx.refresh()

    # 1. Validate new_name C++ identifier
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', new_name):
        return {"status": "error", "error": f"Invalid C++ identifier for new command name: '{new_name}'", "plan": None}

    if old_name.lower() == new_name.lower():
        return {"status": "error", "error": f"New command name cannot be identical to old name: '{new_name}'", "plan": None}

    # 2. Locate target command entity
    mod = ctx.snapshot.get_module(module, framework) if module else None
    cmd = None
    if mod:
        cmd = next((c for c in mod.commands if c.name.lower() == old_name.lower()), None)
    if not cmd:
        all_cmds = ctx.snapshot.get_all_commands()
        cmd = next((c for c in all_cmds if c.name.lower() == old_name.lower()), None)
    if not cmd:
        return {"status": "error", "error": f"Command not found: {old_name}", "plan": None}

    # 3. Check if new_name already exists in module or workspace
    target_mod = cmd.module
    if target_mod:
        if any(c.name.lower() == new_name.lower() for c in target_mod.commands):
            return {"status": "error", "error": f"Command already exists in module '{target_mod.name}': {new_name}", "plan": None}
    all_cmds = ctx.snapshot.get_all_commands()
    if any(c.name.lower() == new_name.lower() for c in all_cmds):
        return {"status": "error", "error": f"Command already exists in workspace: {new_name}", "plan": None}

    # 4. Check for target file collision on disk or in staged cs
    file_renames = []
    cmd_files = [f for f in cmd.all_files if f.exists()]
    if cmd.dialog:
        cmd_files.extend([f for f in cmd.dialog.all_files if f.exists()])

    for old_file in cmd_files:
        new_filename = old_file.name.replace(old_name, new_name, 1)
        new_file = old_file.parent / new_filename
        if new_file.exists():
            return {"status": "error", "error": f"Target file already exists on disk: {new_file}", "plan": None}
        if cs is not None and (str(new_file) in cs.created or str(new_file) in cs.modified):
            return {"status": "error", "error": f"Target file already exists in staged ChangeSet: {new_file}", "plan": None}

        # Read content (staged-first with raw physical bytes)
        raw_bytes, content, detected_enc = _read_file_bytes_and_text(old_file, cs=cs)
        if raw_bytes is None or content is None:
            return {"status": "error", "error": f"Failed to read or decode source file: {old_file}", "plan": None}

        source_snapshot = {
            "path": str(old_file),
            "content_hash": hashlib.sha256(raw_bytes).hexdigest(),
            "content_length": len(raw_bytes),
            "encoding": detected_enc,
        }

        is_header = old_file.suffix.lower() in (".h", ".hpp", ".hxx")
        new_content, repl_details = _compute_cpp_rename_content(old_name, new_name, content, is_header=is_header)

        file_renames.append({
            "old_path": str(old_file),
            "new_path": str(new_file),
            "is_header": is_header,
            "source_snapshot": source_snapshot,
            "replacements": repl_details,
            "new_content": new_content,
        })

    # 5. Imakefile token replacement preview
    imakefile_update = None
    if target_mod:
        imake_path = target_mod.imakefile_path()
        imake_str = str(imake_path)
        if imake_path.exists() or (cs is not None and (imake_str in cs.created or imake_str in cs.modified)):
            raw_bytes, imake_content, detected_enc = _read_file_bytes_and_text(imake_path, cs=cs)
            if imake_content is not None and raw_bytes is not None:
                new_imake_content = _rename_imakefile_content(imake_content, old_name, new_name)
                imakefile_update = {
                    "path": str(imake_path),
                    "old_token": f"{old_name}.cpp",
                    "new_token": f"{new_name}.cpp",
                    "source_snapshot": {
                        "path": str(imake_path),
                        "content_hash": hashlib.sha256(raw_bytes).hexdigest(),
                        "content_length": len(raw_bytes),
                        "encoding": detected_enc,
                    },
                    "new_content": new_imake_content,
                }

    # 6. Locate candidate workbenches and unique 4-param header registration
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

    reg_pattern = re.compile(
        r'new\s+(\w+)\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*(?:\(void\s*\*\)\s*)?NULL\s*\)\s*;?'
    )

    candidate_matches = []
    for candidate_wb in target_wbs:
        addin_source = (
            candidate_wb.addin_source
            or (candidate_wb.path if candidate_wb.path and candidate_wb.path.suffix.lower() == ".cpp" and candidate_wb.path.exists() else None)
            or candidate_wb.addin_source_path()
        )
        if not addin_source:
            continue
        raw_bytes, content, detected_enc = _read_file_bytes_and_text(addin_source, cs=cs)
        if content is None or raw_bytes is None:
            continue

        scope_cc = _extract_create_commands_scope(content)
        if not scope_cc:
            if workbench_name:
                return {
                    "status": "error",
                    "error": f"Failed to extract CreateCommands() scope from specified workbench '{workbench_name}': {addin_source}",
                    "plan": None,
                }
            has_clue = (target_class_name in content) or (f'"{old_name}"' in content) or (old_name in content)
            if has_clue:
                return {
                    "status": "error",
                    "error": f"Workbench '{candidate_wb.name}' references command '{old_name}' but CreateCommands() scope extraction failed: {addin_source}",
                    "plan": None,
                }
            continue
        cc_body, cc_start_idx, cc_end_idx = scope_cc

        for match in reg_pattern.finditer(cc_body):
            hdr_cls, hdr_id, ld_name, cls_name = match.groups()
            if cls_name != target_class_name:
                continue
            if expected_load_name and ld_name != expected_load_name:
                continue
            candidate_matches.append({
                "workbench": candidate_wb,
                "addin_source": addin_source,
                "header_class": hdr_cls,
                "header_id": hdr_id,
                "load_name": ld_name,
                "class_name": cls_name,
                "statement": match.group(0).strip(),
                "scope_start": cc_start_idx,
                "scope_end": cc_end_idx,
                "addin_content": content,
                "raw_bytes": raw_bytes,
                "encoding": detected_enc,
            })

    if len(candidate_matches) == 0:
        return {
            "status": "error",
            "error": f"No 4-parameter header registration found for command '{old_name}' (class_name='{target_class_name}')",
            "plan": None,
        }
    if len(candidate_matches) > 1:
        return {
            "status": "error",
            "error": f"Ambiguous header registration for command '{old_name}': found {len(candidate_matches)} matches across workbenches",
            "plan": None,
        }

    match_info = candidate_matches[0]
    matched_hdr_cls = match_info["header_class"]
    matched_hdr_id = match_info["header_id"]
    matched_ld_name = match_info["load_name"]
    matched_cls_name = match_info["class_name"]
    old_stmt = match_info["statement"]
    wb = match_info["workbench"]
    addin_source = match_info["addin_source"]
    addin_content = match_info["addin_content"]
    addin_raw_bytes = match_info["raw_bytes"]
    addin_enc = match_info["encoding"]

    # Construct new header statement: HeaderID, LoadName, NULL strictly preserved, only ClassName replaced
    new_stmt = f'new {matched_hdr_cls}("{matched_hdr_id}", "{matched_ld_name}", "{new_name}", (void *)NULL);'

    header_update = {
        "workbench_name": wb.name,
        "addin_source": str(addin_source),
        "header_class": matched_hdr_cls,
        "header_id": matched_hdr_id,  # Stable
        "load_name": matched_ld_name,  # Stable
        "old_class_name": matched_cls_name,
        "new_class_name": new_name,
        "old_statement": old_stmt,
        "new_statement": new_stmt,
        "source_snapshot": {
            "path": str(addin_source),
            "content_hash": hashlib.sha256(addin_raw_bytes).hexdigest(),
            "content_length": len(addin_raw_bytes),
            "encoding": addin_enc,
        },
    }

    # 7. Toolbar read-only audit: confirm HeaderID is mounted and remains stable (zero mutation)
    toolbar_references = []
    scope_tb = _extract_create_toolbars_scope(addin_content)
    if scope_tb:
        tb_body, _, _ = scope_tb
        # Look for SetAccessCommand referencing matched_hdr_id
        cmd_re = re.compile(r'SetAccessCommand\s*\(\s*(\w+)\s*,\s*"([^"]+)"\s*\)\s*;')
        for m in cmd_re.finditer(tb_body):
            s_var, h_id = m.groups()
            if h_id == matched_hdr_id:
                toolbar_references.append({
                    "starter_var": s_var,
                    "header_id": h_id,
                    "needs_update": False,
                    "reason": "HeaderID remains stable; no toolbar mutation in phase 1",
                })

    # 8. Resource read-only audit: report resources associated with matched_hdr_id
    fw = getattr(wb, "framework", None)
    if not fw and hasattr(wb, "framework_name") and wb.framework_name:
        fw = ctx.snapshot.get_framework(wb.framework_name)
    if not fw and cmd.module and hasattr(cmd.module, "framework"):
        fw = cmd.module.framework

    affected_resources = []
    if fw:
        nls_path = fw.cnext_dir() / "resources" / "msgcatalog" / f"{matched_hdr_cls}.CATNls"
        if nls_path.exists():
            nls_text = nls_path.read_text(encoding="utf-8", errors="replace")
            if f"{matched_hdr_cls}.{matched_hdr_id}" in nls_text or matched_hdr_id in nls_text:
                affected_resources.append({
                    "type": "nls",
                    "path": str(nls_path),
                    "key_prefix": f"{matched_hdr_cls}.{matched_hdr_id}",
                })
        rsc_path = fw.cnext_dir() / "resources" / "msgcatalog" / f"{matched_hdr_cls}.CATRsc"
        if rsc_path.exists():
            rsc_text = rsc_path.read_text(encoding="utf-8", errors="replace")
            if f"{matched_hdr_cls}.{matched_hdr_id}" in rsc_text or matched_hdr_id in rsc_text:
                affected_resources.append({
                    "type": "rsc",
                    "path": str(rsc_path),
                    "key_prefix": f"{matched_hdr_cls}.{matched_hdr_id}",
                })
        icon_name = getattr(cmd, "icon", None) or old_name
        icon_path = fw.cnext_dir() / "resources" / "graphic" / "icons" / "normal" / f"I_{icon_name}.bmp"
        if icon_path.exists():
            affected_resources.append({
                "type": "icon",
                "path": str(icon_path),
            })

    resource_impact_report = {
        "status": "preserved",
        "reason": "HeaderID remains stable; no resource migration required in phase 1",
        "affected_resources": affected_resources,
    }

    plan = {
        "plan_schema_version": "2.0",
        "command_identity": {
            "old_name": old_name,
            "new_name": new_name,
            "module": target_mod.name if target_mod else None,
            "framework": target_mod.framework.name if (target_mod and target_mod.framework) else None,
            "workbench_name": wb.name if wb else workbench_name,
        },
        "file_renames": file_renames,
        "imakefile_updates": imakefile_update,
        "header_update": header_update,
        "toolbar_references": toolbar_references,
        "resource_impact_report": resource_impact_report,
    }

    return {
        "status": "ok",
        "error": None,
        "plan": plan,
    }


def rename_command(
    ctx: ActionContext,
    old_name: str,
    new_name: str,
    *,
    module: Optional[str] = None,
    framework: Optional[str] = None,
    workbench_name: Optional[str] = None,
    cs: Optional[ChangeSet] = None,
    plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Rename a command entity and cascade update C++ source, Imakefile, and Header registration (R-4-B Phase 2).

    Strictly consumes the CommandRenamePlan computed by inspect_rename_command()
    to maintain transaction integrity and zero-mutation guarantees upon failure.
    Performs:
      - Snapshot hash integrity verification against concurrent tampering
      - Atomic file renames (add_create(new) + add_delete(old))
      - Imakefile.mk token boundary migration
      - 4-parameter Header registration ClassName update with HeaderID strictly preserved
      - ChangeSet staging with full rollback symmetry
    """
    ctx.refresh()

    if plan is None:
        inspect_res = inspect_rename_command(
            ctx,
            old_name,
            new_name,
            module=module,
            framework=framework,
            workbench_name=workbench_name,
            cs=cs,
        )
        if inspect_res.get("status") != "ok":
            return _error(inspect_res.get("error") or f"Rename inspection failed for command '{old_name}'")
        plan = inspect_res["plan"]

    # 1. Plan schema and identity binding validation
    if plan.get("plan_schema_version") != "2.0":
        return _error(f"Incompatible or missing plan_schema_version: expected '2.0', got '{plan.get('plan_schema_version')}'")

    cid = plan.get("command_identity")
    if not isinstance(cid, dict):
        return _error("Plan missing or invalid command_identity")
    if cid.get("old_name") != old_name or cid.get("new_name") != new_name:
        return _error(
            f"Plan command_identity mismatch: expected '{old_name}' -> '{new_name}', "
            f"got '{cid.get('old_name')}' -> '{cid.get('new_name')}'"
        )
    if module and cid.get("module") != module:
        return _error(f"Plan module mismatch: expected '{module}', got '{cid.get('module')}'")
    if framework and cid.get("framework") != framework:
        return _error(f"Plan framework mismatch: expected '{framework}', got '{cid.get('framework')}'")
    if workbench_name and cid.get("workbench_name") and cid.get("workbench_name").lower() != workbench_name.lower():
        return _error(f"Plan workbench_name mismatch: expected '{workbench_name}', got '{cid.get('workbench_name')}'")

    # Path traversal and module scope boundary verification
    mod_name = cid.get("module")
    fw_name = cid.get("framework")
    target_mod = ctx.snapshot.get_module(mod_name, fw_name) if mod_name else None
    if target_mod and target_mod.path:
        mod_root = target_mod.path.resolve()
        for f_item in plan.get("file_renames", []):
            old_p = Path(f_item["old_path"]).resolve()
            new_p = Path(f_item["new_path"]).resolve()
            try:
                old_p.relative_to(mod_root)
                new_p.relative_to(mod_root)
            except ValueError:
                return _error(f"Plan file path is outside target module directory: {old_p}")
            expected_new_filename = old_p.name.replace(old_name, new_name, 1)
            if new_p.name != expected_new_filename:
                return _error(
                    f"Plan file rename '{old_p.name}' -> '{new_p.name}' does not match expected '{expected_new_filename}'"
                )

    hdr_update = plan.get("header_update")
    if hdr_update:
        if hdr_update.get("new_class_name") != new_name:
            return _error(f"Plan header_update new_class_name mismatch: expected '{new_name}', got '{hdr_update.get('new_class_name')}'")

    # 2. Verify source snapshot physical byte hashes to prevent concurrent modification / tampering
    for f_item in plan.get("file_renames", []):
        old_f = Path(f_item["old_path"])
        raw_bytes, current_content, enc = _read_file_bytes_and_text(old_f, cs=cs)
        if raw_bytes is None:
            return _error(f"Source file not found during rename execution: {old_f}")

        cur_hash = hashlib.sha256(raw_bytes).hexdigest()
        cur_len = len(raw_bytes)
        expected_hash = f_item["source_snapshot"]["content_hash"]
        expected_len = f_item["source_snapshot"].get("content_length")
        if cur_hash != expected_hash or (expected_len is not None and cur_len != expected_len):
            return _error(f"Source file has been modified concurrently: {old_f}")

    imk_update = plan.get("imakefile_updates")
    if imk_update:
        imk_f = Path(imk_update["path"])
        raw_bytes, cur_imk, enc = _read_file_bytes_and_text(imk_f, cs=cs)
        if raw_bytes is None:
            return _error(f"Imakefile not found during rename execution: {imk_f}")

        cur_hash = hashlib.sha256(raw_bytes).hexdigest()
        cur_len = len(raw_bytes)
        expected_hash = imk_update["source_snapshot"]["content_hash"]
        expected_len = imk_update["source_snapshot"].get("content_length")
        if cur_hash != expected_hash or (expected_len is not None and cur_len != expected_len):
            return _error(f"Imakefile has been modified concurrently: {imk_f}")

    cur_addin = None
    cc_scope = None
    if hdr_update:
        addin_f = Path(hdr_update["addin_source"])
        raw_bytes, cur_addin, enc = _read_file_bytes_and_text(addin_f, cs=cs)
        if raw_bytes is None or cur_addin is None:
            return _error(f"Addin source file not found during rename execution: {addin_f}")

        cur_hash = hashlib.sha256(raw_bytes).hexdigest()
        cur_len = len(raw_bytes)
        expected_hash = hdr_update["source_snapshot"]["content_hash"]
        expected_len = hdr_update["source_snapshot"].get("content_length")
        if cur_hash != expected_hash or (expected_len is not None and cur_len != expected_len):
            return _error(f"Addin source file has been modified concurrently: {addin_f}")

        cc_scope = _extract_create_commands_scope(cur_addin)
        if not cc_scope:
            return _error(f"Cannot reliably extract CreateCommands() scope in {addin_f}")

    # 2. Initialize or connect master ChangeSet
    master_cs = cs if cs is not None else ChangeSet(
        action="rename_command",
        description=f"Rename command '{old_name}' to '{new_name}'",
    )

    # 3. Stage atomic file renames
    for f_item in plan.get("file_renames", []):
        old_p = Path(f_item["old_path"])
        new_p = Path(f_item["new_path"])
        new_c = f_item["new_content"]
        master_cs.add_create(new_p, new_c)
        master_cs.add_delete(old_p)

    # 4. Stage Imakefile token replacement
    if imk_update:
        imk_p = Path(imk_update["path"])
        new_imk = imk_update["new_content"]
        if str(imk_p) in master_cs.created:
            master_cs.created[str(imk_p)] = new_imk
        else:
            master_cs.add_modify(imk_p, new_imk)

    # 5. Stage Addin Header registration update
    if hdr_update:
        addin_p = Path(hdr_update["addin_source"])
        old_stmt = hdr_update["old_statement"]
        new_stmt = hdr_update["new_statement"]
        new_addin = _remove_statement_line(
            cur_addin,
            old_stmt,
            replace_with=new_stmt,
            search_start=cc_scope[1],
            search_end=cc_scope[2],
        )
        if new_stmt != old_stmt and new_addin == cur_addin:
            return _error(f"Failed to replace header registration statement in {addin_p}")

        if str(addin_p) in master_cs.created:
            master_cs.created[str(addin_p)] = new_addin
        else:
            master_cs.add_modify(addin_p, new_addin)

    # 6. Record metadata and return structured result
    master_cs.metadata.update(
        {
            "command": new_name,
            "old_name": old_name,
            "new_name": new_name,
            "class_name": new_name,
            "header_id": hdr_update.get("header_id") if hdr_update else None,
            "workbench_name": hdr_update.get("workbench_name") if hdr_update else None,
            "file_renames": [
                {"old_path": r["old_path"], "new_path": r["new_path"]}
                for r in plan.get("file_renames", [])
            ],
            "resource_impact_report": plan.get("resource_impact_report"),
            "plan": plan,
        }
    )

    res = _result(master_cs)
    res["plan"] = plan
    return res


def inspect_create_workbench(
    ctx: ActionContext,
    workbench_name: str,
    *,
    framework: Optional[str] = None,
    module: Optional[str] = None,
    cs: Optional[ChangeSet] = None,
    generate_icon: bool = False,
) -> Dict[str, Any]:
    """Inspect workspace to compute a deterministic WorkbenchCreatePlan (W-1-A Phase 1).

    Pure read-only pre-validation across 7 strict security gates:
      Gate 1: Identifier validity and workspace-wide identity collision check
      Gate 2: Target host module existence and BUILT_OBJECT_TYPE == 'SHARED LIBRARY'
      Gate 3: IdentityCard.xml existence, strict XML parsing, and prerequisite audit
      Gate 4: Imakefile.mk token-bounded LINK_WITH audit and library injection plan
      Gate 5: Dictionary (*.dico) conflict check and mapping entry plan
      Gate 6: Resources, NLS, and RSC localization planning
      Gate 7: Deterministic WorkbenchCreatePlan (schema 2.0) with byte snapshots

    Guarantees zero physical disk mutation, zero directory creation, and zero
    mutation to caller-owned ChangeSet upon any gate failure or success.
    """
    ctx.refresh()

    # ── Gate 1: Identifier validity & collision check ──
    if not workbench_name or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', workbench_name):
        return {
            "status": "error",
            "error": f"Invalid C++ identifier for workbench name: '{workbench_name}'",
            "plan": None,
        }

    fw = (
        ctx.snapshot.get_framework(framework)
        if framework
        else (ctx.snapshot.frameworks[0] if ctx.snapshot.frameworks else None)
    )
    if not fw:
        return {
            "status": "error",
            "error": f"Framework not found: '{framework}'" if framework else "No framework found in workspace",
            "plan": None,
        }

    # Check for existing workbench collision in workspace
    for f in ctx.snapshot.frameworks:
        for wb in f.workbenches:
            if wb.name.lower() == workbench_name.lower():
                return {
                    "status": "error",
                    "error": f"Workbench already exists in workspace: '{wb.name}'",
                    "plan": None,
                }

    addin_name = f"{workbench_name}Addin"

    # Check for class/command/module name collision
    for f in ctx.snapshot.frameworks:
        for m in f.modules:
            for c in m.commands:
                if c.name.lower() in (workbench_name.lower(), addin_name.lower()):
                    return {
                        "status": "error",
                        "error": f"Command already exists with matching name in module '{m.name}': '{c.name}'",
                        "plan": None,
                    }

    # ── Gate 2: Target host module existence and BUILT_OBJECT_TYPE ──
    mod = None
    if module:
        mod = fw.find_module(module)
        if not mod:
            return {
                "status": "error",
                "error": f"Module not found in framework '{fw.name}': '{module}'",
                "plan": None,
            }
    else:
        # Discover first shared library module in framework
        for candidate in fw.modules:
            c_imake = candidate.imakefile_path()
            _, c_text, _ = _read_file_bytes_and_text(c_imake, cs=cs)
            if c_text:
                m_type = re.search(r'^\s*BUILT_OBJECT_TYPE\s*=\s*(.+?)\s*$', c_text, re.MULTILINE)
                if m_type and m_type.group(1).strip().strip('"\'').upper().replace("_", " ") == "SHARED LIBRARY":
                    mod = candidate
                    break
        if not mod:
            if fw.modules:
                mod = fw.modules[0]
            else:
                return {
                    "status": "error",
                    "error": f"No modules found in framework '{fw.name}'",
                    "plan": None,
                }

    imake_path = mod.imakefile_path()
    imake_raw, imake_text, imake_enc = _read_file_bytes_and_text(imake_path, cs=cs)
    if imake_raw is None or imake_text is None:
        return {
            "status": "error",
            "error": f"Imakefile.mk not found or unreadable in module '{mod.name}': {imake_path}",
            "plan": None,
        }

    m_type = re.search(r'^\s*BUILT_OBJECT_TYPE\s*=\s*(.+?)\s*$', imake_text, re.MULTILINE)
    if not m_type:
        return {
            "status": "error",
            "error": f"Missing BUILT_OBJECT_TYPE in Imakefile.mk: {imake_path}",
            "plan": None,
        }
    obj_type = m_type.group(1).strip().strip('"\'')
    if obj_type.upper().replace("_", " ") != "SHARED LIBRARY":
        return {
            "status": "error",
            "error": f"Module '{mod.name}' BUILT_OBJECT_TYPE is '{obj_type}', expected 'SHARED LIBRARY'",
            "plan": None,
        }

    # Check file collision on disk and in staged ChangeSet
    src_dir = mod.src_dir_path()
    li_dir = mod.local_interfaces_dir()
    addin_h = li_dir / f"{addin_name}.h"
    addin_cpp = src_dir / f"{addin_name}.cpp"

    for target_file in (addin_h, addin_cpp):
        if target_file.exists():
            return {
                "status": "error",
                "error": f"Target file already exists on disk: {target_file}",
                "plan": None,
            }
        if cs is not None and (str(target_file) in cs.created or str(target_file) in cs.modified):
            return {
                "status": "error",
                "error": f"Target file already exists in staged ChangeSet: {target_file}",
                "plan": None,
            }

    if generate_icon:
        target_icon = fw.path / "CNext" / "resources" / "graphic" / "icons" / "normal" / f"I_{workbench_name}.bmp"
        if target_icon.exists():
            return {
                "status": "error",
                "error": f"Target icon already exists on disk: {target_icon}",
                "plan": None,
            }
        if cs is not None and (str(target_icon) in cs.created or str(target_icon) in cs.modified):
            return {
                "status": "error",
                "error": f"Target icon already exists in staged ChangeSet: {target_icon}",
                "plan": None,
            }

    # ── Gate 3: IdentityCard.xml existence, strict XML parsing, & prereq audit ──
    ic_path = fw.path / "IdentityCard" / "IdentityCard.xml"
    if not ic_path.exists() and (cs is None or str(ic_path) not in cs.created):
        return {
            "status": "error",
            "error": f"IdentityCard.xml not found in framework '{fw.name}': {ic_path}",
            "plan": None,
        }

    ic_raw, ic_text, ic_enc = _read_file_bytes_and_text(ic_path, cs=cs)
    if ic_raw is None or ic_text is None:
        return {
            "status": "error",
            "error": f"Failed to read IdentityCard.xml: {ic_path}",
            "plan": None,
        }

    try:
        ic_root = ET.fromstring(ic_text)
    except ET.ParseError as e:
        return {
            "status": "error",
            "error": f"IdentityCard.xml is malformed or corrupted: {e}",
            "plan": None,
        }

    existing_prereqs = {
        elem.attrib.get("name")
        for elem in ic_root.iter()
        if elem.tag.split("}")[-1] == "prerequisite" and "name" in elem.attrib
    }
    required_prereqs = ["System", "ApplicationFrame"]
    missing_prereqs = [p for p in required_prereqs if p not in existing_prereqs]

    ic_patch = None
    if missing_prereqs:
        nl = "\r\n" if "\r\n" in ic_text else "\n"
        ic_lines = ic_text.splitlines()
        close_idx = -1
        for idx, line in enumerate(ic_lines):
            if re.search(r'</([a-zA-Z0-9_:-]+)>', line):
                close_idx = idx

        indent = "  "
        for line in ic_lines:
            m_ind = re.match(r'^([ \t]+)<prerequisite', line)
            if m_ind:
                indent = m_ind.group(1)
                break

        injections = [f'{indent}<prerequisite name="{p}" access="Protected" />' for p in missing_prereqs]
        if close_idx >= 0:
            for inj in reversed(injections):
                ic_lines.insert(close_idx, inj)
            new_ic_text = nl.join(ic_lines) + (nl if ic_text.endswith(("\r\n", "\n")) else "")
        else:
            new_ic_text = ic_text.rstrip() + nl + nl.join(injections) + nl

        try:
            ET.fromstring(new_ic_text)
        except ET.ParseError as e:
            return {
                "status": "error",
                "error": f"Generated IdentityCard.xml patch would be invalid: {e}",
                "plan": None,
            }

        ic_snapshot = {
            "path": str(ic_path),
            "content_hash": hashlib.sha256(ic_raw).hexdigest(),
            "content_length": len(ic_raw),
            "encoding": ic_enc,
        }
        ic_patch = {
            "path": str(ic_path),
            "kind": "identitycard",
            "source_snapshot": ic_snapshot,
            "new_content": new_ic_text,
            "missing_prereqs": missing_prereqs,
        }

    # ── Gate 4: Imakefile.mk token-bounded LINK_WITH audit ──
    required_libs = ["JS0GROUP", "CATApplicationFrame"]
    missing_libs = [
        lib for lib in required_libs
        if not re.search(r'\b' + re.escape(lib) + r'\b', imake_text)
    ]
    imake_patch = None
    if missing_libs:
        nl = "\r\n" if "\r\n" in imake_text else "\n"
        imake_lines = imake_text.splitlines()
        last_lw_idx = -1
        for idx, line in enumerate(imake_lines):
            if re.match(r'^[ \t]*LINK_WITH[ \t]*=', line):
                last_lw_idx = idx

        injection_line = f"LINK_WITH = $(LINK_WITH) {' '.join(missing_libs)}"
        if last_lw_idx >= 0:
            imake_lines.insert(last_lw_idx + 1, injection_line)
            new_imake_text = nl.join(imake_lines) + (nl if imake_text.endswith(("\r\n", "\n")) else "")
        else:
            new_imake_text = imake_text.rstrip() + nl + injection_line + nl

        imake_snapshot = {
            "path": str(imake_path),
            "content_hash": hashlib.sha256(imake_raw).hexdigest(),
            "content_length": len(imake_raw),
            "encoding": imake_enc,
        }
        imake_patch = {
            "path": str(imake_path),
            "kind": "imakefile",
            "source_snapshot": imake_snapshot,
            "new_content": new_imake_text,
            "missing_libs": missing_libs,
        }

    # ── Gate 5: Dictionary (*.dico) conflict check & mapping entry plan ──
    dico_dir = fw.path / "CNext" / "code" / "dictionary"
    dico_files = list(dico_dir.glob("*.dico")) if dico_dir.exists() else []
    for df in dico_files:
        _, d_text, _ = _read_file_bytes_and_text(df, cs=cs)
        if d_text:
            for line in d_text.splitlines():
                parts = line.strip().split()
                if parts and parts[0].lower() == addin_name.lower():
                    return {
                        "status": "error",
                        "error": f"Dictionary mapping already exists for '{addin_name}' in {df}",
                        "plan": None,
                    }

    target_dico = fw.dictionary_path()
    dico_entry = f"{addin_name}  CATIAfrGeneralWksAddin  lib{mod.bare_name}\n"
    dico_patch = None
    dico_creation = None
    if target_dico.exists() or (cs is not None and str(target_dico) in (cs.created or cs.modified)):
        d_raw, d_text, d_enc = _read_file_bytes_and_text(target_dico, cs=cs)
        stripped = (d_text or "").rstrip()
        nl = "\r\n" if (d_text and "\r\n" in d_text) else "\n"
        new_dico_text = (stripped + nl if stripped else "") + dico_entry
        dico_snapshot = {
            "path": str(target_dico),
            "content_hash": hashlib.sha256(d_raw).hexdigest() if d_raw else "",
            "content_length": len(d_raw) if d_raw else 0,
            "encoding": d_enc or "utf-8",
        }
        dico_patch = {
            "path": str(target_dico),
            "kind": "dictionary",
            "source_snapshot": dico_snapshot,
            "new_content": new_dico_text,
            "entry": dico_entry.strip(),
        }
    else:
        dico_creation = {
            "path": str(target_dico),
            "kind": "dictionary",
            "content": dico_entry,
        }

    # ── Gate 6: Resource & C++ code generation planning ──
    year_str = str(datetime.now().year)

    addin_h_content = f"""// COPYRIGHT DASSAULT SYSTEMES {year_str}
//===================================================================
// {addin_name}.h
// Addin class for integrating into existing workbenches
//===================================================================
#ifndef {addin_name}_H
#define {addin_name}_H

#include "CATBaseUnknown.h"
#include "CATIAfrGeneralWksAddin.h"

class {addin_name} : public CATBaseUnknown
{{
    CATDeclareClass;

public:
    {addin_name}();
    virtual ~{addin_name}();

    void CreateCommands();
    virtual CATCmdContainer* CreateToolbars();
    virtual CATCmdContainer* CreateMenus();

private:
    {addin_name}(const {addin_name}&);
    {addin_name}& operator=(const {addin_name}&);
}};

#endif // {addin_name}_H
"""

    addin_cpp_content = f"""// COPYRIGHT DASSAULT SYSTEMES {year_str}
//===================================================================
// {addin_name}.cpp
// Addin implementation
//===================================================================
#include "{addin_name}.h"

#include "CATCommandHeader.h"
#include "CATCmdContainer.h"
#include "CATCmdStarter.h"
#include "CATCreateWorkshop.h"

#include "TIE_CATIAfrGeneralWksAddin.h"

TIE_CATIAfrGeneralWksAddin({addin_name});

CATImplementClass({addin_name},
                  DataExtension,
                  CATBaseUnknown,
                  {addin_name});

{addin_name}::{addin_name}()
    : CATBaseUnknown()
{{
}}

{addin_name}::~{addin_name}()
{{
}}

void {addin_name}::CreateCommands()
{{
}}

CATCmdContainer* {addin_name}::CreateToolbars()
{{
    NewAccess(CATCmdContainer, pToolbarStarter, {workbench_name}TlbStarter);
    if (pToolbarStarter)
    {{
        NewAccess(CATCmdContainer, pToolbar, {workbench_name}Tlb);
        if (pToolbar)
        {{
            SetAccessChild(pToolbarStarter, pToolbar);
        }}
    }}
    return pToolbarStarter;
}}

CATCmdContainer* {addin_name}::CreateMenus()
{{
    return NULL;
}}
"""

    nls_en_path = fw.path / "CNext" / "resources" / "msgcatalog" / f"{addin_name}.CATNls"
    rsc_path = fw.path / "CNext" / "resources" / "msgcatalog" / f"{addin_name}.CATRsc"
    nls_zh_path = fw.path / "CNext" / "resources" / "msgcatalog" / "Simplified_Chinese" / f"{addin_name}.CATNls"

    file_creations = [
        {"path": str(addin_h), "kind": "header", "content": addin_h_content},
        {"path": str(addin_cpp), "kind": "source", "content": addin_cpp_content},
    ]
    if dico_creation:
        file_creations.append(dico_creation)

    file_creations.extend([
        {
            "path": str(nls_en_path),
            "kind": "nls",
            "content": f'{addin_name}.Title = "{workbench_name}";\n{addin_name}.Help = "{workbench_name} Workbench";\n{addin_name}.ShortHelp = "{workbench_name}";\n{addin_name}.LongHelp = "{workbench_name} Workbench Addin";\n',
        },
        {
            "path": str(nls_zh_path),
            "kind": "nls_zh",
            "content": f'{addin_name}.Title = "{workbench_name}";\n{addin_name}.Help = "{workbench_name} 工作台";\n{addin_name}.ShortHelp = "{workbench_name}";\n{addin_name}.LongHelp = "{workbench_name} 工作台插件";\n',
        },
        {
            "path": str(rsc_path),
            "kind": "rsc",
            "content": f'{addin_name}.Icon.Normal = "I_{workbench_name}";\n',
        },
    ])

    if generate_icon:
        icon_path = fw.path / "CNext" / "resources" / "graphic" / "icons" / "normal" / f"I_{workbench_name}.bmp"
        icon_bytes = None
        try:
            from icon_provider import get_icon
            ico_file = get_icon(workbench_name, format="bmp")
            if ico_file and ico_file.exists():
                icon_bytes = ico_file.read_bytes()
        except Exception:
            pass
        if not icon_bytes:
            icon_bytes = _resolve_icon_bytes("I_" + workbench_name, hint=workbench_name)
        if icon_bytes:
            import base64
            file_creations.append({
                "path": str(icon_path),
                "kind": "icon_binary",
                "content": "[BINARY]",
                "binary_b64": base64.b64encode(icon_bytes).decode("ascii"),
            })

    patches = []
    source_snapshots = []
    if ic_patch:
        patches.append(ic_patch)
        source_snapshots.append(ic_patch["source_snapshot"])
    if imake_patch:
        patches.append(imake_patch)
        source_snapshots.append(imake_patch["source_snapshot"])
    if dico_patch:
        patches.append(dico_patch)
        source_snapshots.append(dico_patch["source_snapshot"])

    # ── Gate 7: Deterministic WorkbenchCreatePlan (schema 2.0) ──
    plan = {
        "plan_schema_version": "2.0",
        "workbench_identity": {
            "name": workbench_name,
            "addin_class": addin_name,
            "framework": fw.name,
            "module": mod.name,
            "module_bare_name": mod.bare_name,
        },
        "file_creations": file_creations,
        "patches": patches,
        "source_snapshots": source_snapshots,
        "dependencies_audit": {
            "required_prereqs": required_prereqs,
            "missing_prereqs": missing_prereqs,
            "required_libs": required_libs,
            "missing_libs": missing_libs,
        },
    }

    return {"status": "ok", "error": None, "plan": plan}


def verify_workbench_delete_plan(plan: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate a WorkbenchDeletePlan against current on-disk state (DW9).

    Verifies:
      - plan_schema_version is '2.0' and plan_type is 'delete_workbench'
      - All source_snapshots match current physical byte hashes and lengths
      - All patches match target line exactly without divergence
    """
    if not isinstance(plan, dict):
        return False, "Plan is not a dictionary"
    if plan.get("plan_schema_version") != "2.0":
        return False, f"Incompatible plan schema version: {plan.get('plan_schema_version')}"
    if plan.get("plan_type") != "delete_workbench":
        return False, f"Invalid plan type: {plan.get('plan_type')}"

    snapshots = plan.get("source_snapshots", {})
    for path_str, snap in snapshots.items():
        p = Path(path_str)
        if not p.exists():
            return False, f"Target file in plan snapshot does not exist on disk: {p}"
        raw_bytes = p.read_bytes()
        cur_hash = hashlib.sha256(raw_bytes).hexdigest()
        if cur_hash != snap.get("sha256"):
            return False, f"File content modified since plan generation: {p} (expected {snap.get('sha256')[:8]}, got {cur_hash[:8]})"
        if len(raw_bytes) != snap.get("byte_length"):
            return False, f"File length modified since plan generation: {p}"

    patches = plan.get("patches", [])
    for patch in patches:
        p = Path(patch["path"])
        if not p.exists():
            return False, f"Patch target file does not exist: {p}"
        text = p.read_text(encoding=patch.get("encoding", "utf-8"), errors="replace")
        target_line = patch.get("target_line", "")
        if target_line and target_line not in text:
            return False, f"Target line to patch no longer exists in {p}: {target_line}"

    return True, None


def inspect_delete_workbench(
    ctx: ActionContext,
    workbench_name: str,
    *,
    framework: Optional[str] = None,
    module: Optional[str] = None,
    cascade_commands: bool = False,
    cs: Optional[ChangeSet] = None,
) -> Dict[str, Any]:
    """Inspect workspace to compute a deterministic WorkbenchDeletePlan (W-2-A).

    Pure read-only pre-validation across 7 strict security gates:
      Gate 1: Target workbench discovery and single identity resolution (DW1, DW2)
      Gate 2: Host module boundary and addin file path confinement (DW3)
      Gate 3: Dictionary (*.dico) mapping entry exact location and uniqueness (DW4, DW5)
      Gate 4: Exclusive UI resources (NLS/RSC) and shared icon conflict detection (DW6)
      Gate 5: Mounted commands extraction and ownership isolation (DETACH_ONLY) (DW7, DW8)
      Gate 6: Module dependencies conservatism policy (preserves Imakefile/IdentityCard)
      Gate 7: Deterministic WorkbenchDeletePlan (schema 2.0) with raw byte snapshots (DW9, DW10)

    Guarantees zero physical disk mutation, zero deletion, and zero mutation to
    caller-owned ChangeSet.
    """
    ctx.refresh()

    # ── Gate 1: Target workbench discovery and identity resolution ──
    if not workbench_name:
        return {"status": "error", "error": "Workbench name must not be empty", "plan": None}

    target_wb = None
    target_fw = None
    for f in ctx.snapshot.frameworks:
        if framework and f.name != framework and f.name != f"{framework}.edu":
            continue
        for wb in f.workbenches:
            if wb.name.lower() == workbench_name.lower():
                target_wb = wb
                target_fw = f
                break
        if target_wb:
            break

    if not target_wb:
        return {
            "status": "error",
            "error": f"Workbench not found in workspace: '{workbench_name}'",
            "plan": None,
        }

    target_mod = getattr(target_wb, "module", None)
    if not target_mod and target_fw:
        if target_wb.addin_source and target_wb.addin_source.exists():
            for m in target_fw.modules:
                if str(target_wb.addin_source).startswith(str(m.path)):
                    target_mod = m
                    break
        if not target_mod and target_fw.modules:
            target_mod = target_fw.modules[0]

    if module:
        expected_mod = module if module.endswith(".m") else f"{module}.m"
        if not target_mod or target_mod.name != expected_mod:
            return {
                "status": "error",
                "error": f"Workbench '{workbench_name}' belongs to module '{target_mod.name if target_mod else 'none'}', not '{expected_mod}'",
                "plan": None,
            }

    if not target_mod:
        return {
            "status": "error",
            "error": f"Cannot determine host module for workbench '{workbench_name}'",
            "plan": None,
        }

    addin_class = f"{target_wb.name}Addin"
    if target_wb.addin_source and target_wb.addin_source.exists():
        src_text = target_wb.addin_source.read_text(encoding="utf-8", errors="replace")
        m_cls = re.search(r'CATImplementClass\s*\(\s*(\w+)', src_text)
        if m_cls:
            addin_class = m_cls.group(1)

    # ── Gate 2: Host module boundary and file path confinement ──
    addin_h = target_mod.path / "LocalInterfaces" / f"{addin_class}.h"
    addin_cpp = target_mod.path / "src" / f"{addin_class}.cpp"
    if target_wb.addin_source:
        addin_cpp = target_wb.addin_source

    for cand_path in [addin_h, addin_cpp]:
        try:
            cand_path.resolve().relative_to(target_mod.path.resolve())
        except ValueError:
            return {
                "status": "error",
                "error": f"Path traversal or out-of-boundary file detected: {cand_path}",
                "plan": None,
            }

    # ── Gate 3: Dictionary (*.dico) mapping exact location and uniqueness ──
    dico_dir = target_fw.path / "CNext" / "code" / "dictionary"
    matched_dicos = []
    total_matches = 0
    target_dico_path = None
    target_dico_line = None
    estimated_dico_new_content = None

    if dico_dir.exists():
        dico_pattern = re.compile(
            r'^\s*' + re.escape(addin_class) + r'\s+CATIAfrGeneralWksAddin\s+lib' + re.escape(target_mod.bare_name) + r'\s*$',
            re.MULTILINE
        )
        for dico_file in dico_dir.glob("*.dico"):
            if any(part.startswith(".") for part in dico_file.parts):
                continue
            dico_text = dico_file.read_text(encoding="utf-8", errors="replace")
            matches = list(dico_pattern.finditer(dico_text))
            if matches:
                total_matches += len(matches)
                matched_dicos.append(dico_file)
                if len(matches) == 1 and target_dico_path is None:
                    target_dico_path = dico_file
                    target_dico_line = matches[0].group(0).strip()
                    new_lines = []
                    for line in dico_text.splitlines(keepends=True):
                        if dico_pattern.match(line):
                            continue
                        new_lines.append(line)
                    estimated_dico_new_content = "".join(new_lines)

    if total_matches == 0:
        return {
            "status": "error",
            "error": f"Dictionary entry for '{addin_class}' not found in framework '{target_fw.name}'",
            "plan": None,
        }
    if total_matches > 1:
        return {
            "status": "error",
            "error": f"Multiple ambiguous dictionary entries found for '{addin_class}' ({total_matches} entries)",
            "plan": None,
        }

    # ── Gate 4: Exclusive UI resources (NLS/RSC) and shared icon conflict detection ──
    file_deletions = []
    preserved_resources = []
    warnings = []
    scanned_files_set = set()

    if addin_h.exists():
        file_deletions.append({
            "path": str(addin_h),
            "kind": "addin_header",
            "action": "delete",
            "reason_code": "WORKBENCH_OWNED_RESOURCE"
        })
    if addin_cpp.exists():
        file_deletions.append({
            "path": str(addin_cpp),
            "kind": "addin_source",
            "action": "delete",
            "reason_code": "WORKBENCH_OWNED_RESOURCE"
        })

    nls_en = target_fw.path / "CNext" / "resources" / "msgcatalog" / f"{addin_class}.CATNls"
    nls_zh = target_fw.path / "CNext" / "resources" / "msgcatalog" / "Simplified_Chinese" / f"{addin_class}.CATNls"
    rsc_file = target_fw.path / "CNext" / "resources" / "msgcatalog" / f"{addin_class}.CATRsc"
    icon_file = target_fw.path / "CNext" / "resources" / "graphic" / "icons" / "normal" / f"I_{workbench_name}.bmp"

    for res_p, res_kind in [(nls_en, "nls"), (nls_zh, "nls"), (rsc_file, "rsc")]:
        if res_p.exists():
            file_deletions.append({
                "path": str(res_p),
                "kind": res_kind,
                "action": "delete",
                "reason_code": "WORKBENCH_OWNED_RESOURCE"
            })

    if icon_file.exists():
        icon_name = f"I_{workbench_name}"
        is_icon_shared = False
        sharing_referrers = []

        for f in ctx.snapshot.frameworks:
            msg_dir = f.path / "CNext" / "resources" / "msgcatalog"
            if msg_dir.exists():
                for other_rsc in msg_dir.rglob("*.CATRsc"):
                    if any(part.startswith(".") for part in other_rsc.parts):
                        continue
                    if other_rsc.resolve() == rsc_file.resolve():
                        continue
                    scanned_files_set.add(str(other_rsc))
                    rsc_content = other_rsc.read_text(encoding="utf-8", errors="replace")
                    if icon_name in rsc_content:
                        is_icon_shared = True
                        sharing_referrers.append(str(other_rsc))

        if is_icon_shared:
            preserved_resources.append({
                "path": str(icon_file),
                "kind": "icon_binary",
                "action": "preserve",
                "reason_code": "SHARED_RESOURCE",
                "referrers": sharing_referrers
            })
            warnings.append(
                f"Icon file '{icon_file.name}' is referenced by other components ({', '.join(Path(r).name for r in sharing_referrers)}); preserved."
            )
        else:
            file_deletions.append({
                "path": str(icon_file),
                "kind": "icon_binary",
                "action": "delete",
                "reason_code": "WORKBENCH_OWNED_RESOURCE"
            })

    # ── Gate 5: Mounted commands extraction and ownership isolation (DETACH_ONLY) ──
    command_relations = []
    if addin_cpp.exists():
        cpp_text = addin_cpp.read_text(encoding="utf-8", errors="replace")
        cc_scope = _extract_create_commands_scope(cpp_text)
        if cc_scope:
            cc_body = cc_scope[0]
            for m_hdr in re.finditer(
                r'new\s+(\w+)\s*\(\s*"([^"]+)"\s*,\s*(?:"([^"]+)"|NULL)\s*,\s*(?:"([^"]+)"|NULL)',
                cc_body
            ):
                hdr_cls, hdr_id, load_name, cmd_cls = m_hdr.group(1), m_hdr.group(2), m_hdr.group(3), m_hdr.group(4)
                
                is_shared_cmd = False
                ext_referrers = []
                for f in ctx.snapshot.frameworks:
                    for other_wb in f.workbenches:
                        if other_wb == target_wb:
                            continue
                        wb_src = other_wb.addin_source or other_wb.path
                        if wb_src and wb_src.exists():
                            scanned_files_set.add(str(wb_src))
                            other_code = wb_src.read_text(encoding="utf-8", errors="replace")
                            if f'"{hdr_id}"' in other_code:
                                is_shared_cmd = True
                                if other_wb.name not in ext_referrers:
                                    ext_referrers.append(other_wb.name)

                cmd_rel = {
                    "header_id": hdr_id,
                    "header_class": hdr_cls,
                    "command_class": cmd_cls or "",
                    "workbench_relation": "mounted",
                    "ownership": "UNKNOWN",
                    "external_references": "PROVEN_SHARED" if is_shared_cmd else "NOT_FULLY_PROVEN",
                    "sharing_workbenches": ext_referrers,
                    "recommended_action": "DETACH_ONLY"
                }
                command_relations.append(cmd_rel)

    if cascade_commands and command_relations:
        return {
            "status": "blocked",
            "error": "Cascade delete commands blocked: external command ownership cannot be proven; commands must be detached only",
            "plan": None,
            "command_relations": command_relations
        }

    # ── Gate 6: Module dependencies conservatism policy ──
    dependencies_policy = {
        "framework_identity_card": "preserved",
        "module_imakefile": "preserved",
        "reason": "Preserved to protect potentially coexisting commands, dialogs, or future components in host module."
    }

    # ── Gate 7: Deterministic WorkbenchDeletePlan (schema 2.0) with byte snapshots ──
    patches = [
        {
            "path": str(target_dico_path),
            "kind": "dico_entry_removal",
            "target_line": target_dico_line,
            "match_mode": "exact_normalized_entry",
            "expected_occurrences": 1,
            "estimated_new_content": estimated_dico_new_content,
        }
    ]

    source_snapshots = {}
    for fd in file_deletions:
        p = Path(fd["path"])
        if p.exists():
            b = p.read_bytes()
            source_snapshots[str(p)] = {
                "sha256": hashlib.sha256(b).hexdigest(),
                "byte_length": len(b),
                "encoding": "utf-8" if fd.get("kind") != "icon_binary" else "binary"
            }

    for pt in patches:
        p = Path(pt["path"])
        if p.exists():
            b = p.read_bytes()
            source_snapshots[str(p)] = {
                "sha256": hashlib.sha256(b).hexdigest(),
                "byte_length": len(b),
                "encoding": "utf-8"
            }

    plan = {
        "plan_schema_version": "2.0",
        "plan_type": "delete_workbench",
        "workbench_identity": {
            "name": target_wb.name,
            "addin_class": addin_class,
            "framework": target_fw.name,
            "module": target_mod.name,
            "module_bare_name": target_mod.bare_name,
        },
        "action": "delete_workbench",
        "reason_code": "WORKBENCH_OWNED_RESOURCE",
        "file_deletions": file_deletions,
        "patches": patches,
        "preserved_resources": preserved_resources,
        "source_snapshots": source_snapshots,
        "command_relations": command_relations,
        "module_dependencies_policy": dependencies_policy,
        "dependency_evidence": {
            "scan_scope": "workspace",
            "scanned_files": len(scanned_files_set),
            "unresolved_references": [],
            "confidence": "bounded_static_scan"
        },
        "warnings": warnings,
    }

    return {
        "status": "ok",
        "error": None,
        "plan": plan
    }


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
