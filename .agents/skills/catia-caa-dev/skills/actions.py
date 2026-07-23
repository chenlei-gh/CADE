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
from typing import Dict, List, Optional

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
        """Refresh snapshot. Records to history. Use force=True to bypass cache."""
        self._snapshot = None
        snap = self.snapshot
        self.history.record(snap, label or "refresh")
        return snap

    def _max_file_mtime(self) -> float:
        """Get the most recent modification time in the workspace"""
        import os

        try:
            max_mtime = 0
            for root, _, files in os.walk(str(self.workspace_root)):
                for f in files:
                    try:
                        mtime = Path(root, f).stat().st_mtime
                        if mtime > max_mtime:
                            max_mtime = mtime
                    except OSError:
                        pass
                if max_mtime > self._snapshot_mtime:
                    break  # Stop early if we found a newer file
            return max_mtime
        except Exception:
            return float("inf")  # Force refresh on error

    def _is_stale(self) -> bool:
        """Check if snapshot is stale (files have changed)"""
        import time

        if time.time() - getattr(self, "_last_check", 0) < self._cache_ttl:
            return False
        self._last_check = time.time()
        current_mtime = self._max_file_mtime()
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


def _queue_nls(cs: ChangeSet, path: Path, content: str, marker: str):
    """Queue NLS content for `path` without losing previously queued blocks.

    ChangeSet.add_create is a plain dict assignment (last write wins), so two
    add_create calls on a not-yet-existing file silently drop the first block
    (this used to eat the command-header Title/ShortHelp entries whenever the
    toolbar/addin NLS was queued after it). This helper appends to whatever is
    already queued, and only skips when `marker` is already present.
    """
    key = str(path)
    # Existing Simplified_Chinese catalogs are GBK on disk (CATIA locale
    # codepage convention); read with the matching encoding or the marker
    # check would run against mojibake.
    disk_enc = (
        "gbk"
        if any(part.lower() == "simplified_chinese" for part in path.parts)
        else "utf-8"
    )
    if path.exists():
        old = path.read_text(encoding=disk_enc, errors="replace")
        if marker not in old:
            cs.add_modify(path, old.rstrip() + "\n" + content)
    elif key in cs.created:
        queued = cs.created[key]
        if marker not in queued:
            cs.add_create(path, queued.rstrip() + "\n" + content)
    else:
        cs.add_create(path, content)


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
    # Generate CATIAV5Level.lvl at workspace root (required for B28 builds)
    lvl_tpl = ctx.tpl("framework", "CATIAV5Level.lvl")
    if lvl_tpl.exists():
        cs.add_create_file(
            ctx.workspace_root / "CATIAV5Level.lvl", lvl_tpl,
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
) -> Dict:
    """
    Create a Command + Addin for B28 CAA.

    Generates:
      - {Name}.h / {Name}.cpp         (CATStateCommand subclass)
      - {Module}Addin.h / .cpp        (workbench addin, registers command)
      - Framework .dico               (register addin as CATIAfrGeneralWksAddin)
      - Imakefile update              (WIZARD_LINK_MODULES)
    """
    ctx.refresh()
    mod = ctx.snapshot.get_module(module, framework)
    if not mod:
        fw_names = [fw.name for fw in ctx.snapshot.frameworks]
        return _error(f"Module '{module}' not found. Frameworks: {fw_names}")

    cs = ChangeSet(
        action="create_command", description=f"Create command '{name}' in '{module}'"
    )
    fw_name = mod.framework.name if mod.framework else "MyFramework"
    module_base = module.replace(".m", "")

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
        # 4c. Add to CreateToolbars()
        #
        # IMPORTANT: SetAccessChild(pToolbar, X) is `pToolbar->SetChild(X)` —
        # it sets the container's SOLE child pointer, it does NOT append.
        # Calling it once per command (as a naive generator would) silently
        # overwrites the previous binding, so only the LAST-registered
        # command ever gets attached to the toolbar; earlier starters are
        # created but never linked in, making their buttons invisible and
        # unclickable (verified against official CAADoc samples, e.g.
        # CAAAfrGeometryWks.cpp, which chain siblings with SetAccessNext).
        #
        # Correct pattern: the FIRST starter in a container uses
        # SetAccessChild(container, first); every subsequent sibling must be
        # linked with SetAccessNext(previous, next) instead.
        if f'p{name}Cmd' not in addin_text:
            existing_starters = re.findall(
                r'NewAccess\(CATCmdStarter,\s*(\w+),', addin_text
            )
            new_var = f'p{name}Cmd'
            if existing_starters:
                prev_var = existing_starters[-1]
                link_line = f'    SetAccessNext({prev_var}, {new_var});'
                # Anchor on whichever statement actually linked prev_var into
                # the toolbar/chain (either the first SetAccessChild call, or
                # a SetAccessNext call if prev_var was itself a later
                # sibling). Using the exact linking statement — rather than
                # the NewAccess declaration line — guarantees the new
                # SetAccessNext is appended immediately after the current
                # end of the linked list, regardless of how many commands
                # already exist.
                link_match = re.search(
                    r'(?:SetAccessChild\(pToolbar,\s*' + re.escape(prev_var) + r'\);'
                    r'|SetAccessNext\(\w+,\s*' + re.escape(prev_var) + r'\);)',
                    addin_text,
                )
                if not link_match:
                    raise ValueError(
                        f"Could not locate linking statement for existing "
                        f"toolbar starter '{prev_var}' in {addin_cpp}"
                    )
                anchor_target = link_match.group(0)
            else:
                link_line = f'    SetAccessChild(pToolbar, {new_var});'
                anchor_target = 'SetAccessChild(pToolbar'
            cs.add_patch(Patch(
                file=addin_cpp,
                operation="insert_after",
                target=anchor_target,
                content=f'    NewAccess(CATCmdStarter, {new_var}, {name});\n    SetAccessCommand({new_var}, "{cpp_base}.{name}");\n{link_line}',
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
            _queue_nls(cs, nls_file, nls_content, name)

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
            _queue_nls(cs, nls_file_zh, nls_content_zh, name)

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
                ico_path = get_icon(icon_name)
                if ico_path and ico_path.exists():
                    icons_dir = fw.path / "CNext" / "resources" / "graphic" / "icons" / "normal"
                    ico_name = f"I_{icon_name.replace(' ', '_')}.bmp"
                    target = icons_dir / ico_name
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
        _queue_nls(cs, nls_file, addin_nls, addin_name)

        # Toolbar + addin 中文 NLS（与英文块镜像，固定串用中文）
        addin_nls_zh = (
            f'{addin_name}.Title  = "{name}";\n'
            f'{addin_name}.Tip    = "{tip}";\n'
            f'{module_base}Tlb.Title  = "{module_base} 命令";\n'
        )
        _queue_nls(cs, nls_file_zh, addin_nls_zh, addin_name)

    cs.metadata = {
        "command": name,
        "module": module,
        "addin": addin_name,
        "is_stateful": is_stateful,
        "dialog": dialog_name,
    }
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
    ctx: ActionContext, name: str, module: str, framework: str = None
) -> Dict:
    """Create a Dialog"""
    ctx.refresh()
    mod = ctx.snapshot.get_module(module, framework)
    if not mod:
        return _error(f"Module not found: {module}")

    cs = ChangeSet(action="create_dialog", description=f"Create dialog '{name}'")
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
            _queue_nls(cs, msg_dir / f"{fw_base}.CATNls", content_en, name)
        if tpl_nls_zh.exists():
            content_zh = render_template(
                tpl_nls_zh.read_text(encoding="utf-8", errors="replace"), replacements
            )
            _queue_nls(
                cs,
                msg_dir / "Simplified_Chinese" / f"{fw_base}.CATNls",
                content_zh,
                name,
            )

    cs.metadata = {"dialog": name, "module": module}
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


def add_command_to_workbench(
    ctx: ActionContext, command_name: str, workbench_name: str
) -> Dict:
    """Register a command with a workbench (update Addin + Catalog)"""
    ctx.refresh()
    cmds = ctx.snapshot.get_all_commands()
    wbs = ctx.snapshot.get_all_workbenches()

    cmd = next((c for c in cmds if c.name.lower() == command_name.lower()), None)
    wb = next((w for w in wbs if w.name.lower() == workbench_name.lower()), None)

    if not cmd:
        return _error(f"Command not found: {command_name}")
    if not wb:
        return _error(f"Workbench not found: {workbench_name}")

    cs = ChangeSet(
        action="add_command_to_workbench",
        description=f"Add '{command_name}' to workbench '{workbench_name}'",
    )

    if wb.addin_source and wb.addin_source.exists():
        old = wb.addin_source.read_text(encoding="utf-8", errors="replace")
        new_cmd = f'    new {command_name}Header("{command_name}", "{cmd.module.name if cmd.module else "Unknown"}");'
        if new_cmd not in old:
            marker = "void AddinName::CreateCommands()"
            if marker in old:
                new = old.replace(
                    marker + "\n",
                    marker + f"\n    // Register {command_name}\n{new_cmd}\n",
                )
                cs.add_modify(wb.addin_source, new)

    cs.metadata = {"command": command_name, "workbench": workbench_name}
    return _result(cs)


# ══════════════════════════════════════════════════════════════════
#  DELETE ACTIONS (reversible)
# ══════════════════════════════════════════════════════════════════


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
