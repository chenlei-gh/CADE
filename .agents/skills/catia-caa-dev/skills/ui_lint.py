"""
CAA UI Static Linter
=====================
Detects the UI-layer failure patterns documented in
knowledge/failure_patterns/ — the three dialog/toolbar bugs that were
originally diagnosed by hand with debug_tools/ against a live CATIA
(see debug_tools/README.md). Static source analysis catches them
before compile, so repair() can surface them without needing a
running CNEXT process.

Checks (each maps 1:1 to a failure_patterns/fp_*.md entry):
  ui_dialog_null_parent   — new XxxDlg(NULL) → dialog never shows
  ui_dialog_cancel_empty  — Cancel() lacks SetVisibility(CATDlgHide)
                            → dialog close button dead
  ui_toolbar_access_chain — repeated SetAccessChild(pTlb, ...) on the
                            same toolbar → only last button clickable

Design principle:
  Regex-based heuristics over generated source — not a C++ parser.
  False positives are acceptable (severity=warning); false negatives
  are not (these bugs are silent at runtime).

Usage:
  from ui_lint import UILinter
  linter = UILinter()
  findings = linter.lint_module(Path("MyModule.m"))
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# ─── Findings ────────────────────────────────────────────────────


@dataclass
class UIFinding:
    """A single UI failure-pattern match in source code"""
    rule: str            # rule id, e.g. "ui_dialog_null_parent"
    severity: str        # "error" | "warning"
    file: str
    line: int
    problem: str
    reason: str
    fix_hint: str        # concise fix guidance (from failure_patterns)
    knowledge_ref: str   # pointer to the fp_*.md entry

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "problem": self.problem,
            "reason": self.reason,
            "fix_hint": self.fix_hint,
            "knowledge_ref": self.knowledge_ref,
        }


# ─── Rule definitions ────────────────────────────────────────────

# Rule 1: dialog constructed with NULL parent → never mapped by CATIA's
# window manager (silent no-show). fp_dialog_null_parent.md
_NULL_PARENT_RE = re.compile(
    r"new\s+\w*Dlg\w*\s*\(\s*NULL\s*\)"
)

# Rule 2 helpers: find Cancel/Desactivate method bodies (brace-counting
# is overkill; CAA style puts the whole method on a few lines, so we
# capture from signature to the next method signature or end of file).
_METHOD_RE = re.compile(
    r"CATStatusChangeRC\s+\w+::(?P<name>Cancel|Desactivate)\s*\([^)]*\)"
    r"(?P<body>.*?)(?=CATStatusChangeRC\s+\w+::|\Z)",
    re.DOTALL,
)

# Rule 3: SetAccessChild called on the SAME toolbar variable more than
# once in one function → every call but the last detaches its starter.
# fp_toolbar_setaccesschild_overwrite.md
_SET_ACCESS_CHILD_RE = re.compile(
    r"SetAccessChild\s*\(\s*(?P<toolbar>\w+)\s*,"
)

# Rule 4: CATICutAndPastable::Paste with a non-NULL second argument
# (explicit CATPathElement targets). Safe only for same-document paste;
# across documents it crashes CATIA with an UNcatchable runtime
# exception. fp_paste_cross_doc_catpathelement.md
_PASTE_NON_NULL_RE = re.compile(
    r"->\s*Paste\s*\(\s*[^,]+,\s*(?!NULL\b|nullptr\b)(?P<target>\S[^,)]*)"
)


class UILinter:
    """Static linter for the documented CAA UI failure patterns."""

    SOURCE_SUFFIXES = (".cpp", ".h")
    SOURCE_DIRS = ("src", "LocalInterfaces", "PublicInterfaces")

    def lint_module(self, module_path: Path) -> List[UIFinding]:
        """Lint all C++ sources in a CAA module directory."""
        findings: List[UIFinding] = []
        module_path = Path(module_path)
        for sub in self.SOURCE_DIRS:
            src_dir = module_path / sub
            if not src_dir.is_dir():
                continue
            for f in sorted(src_dir.rglob("*")):
                if f.is_file() and f.suffix in self.SOURCE_SUFFIXES:
                    findings.extend(self.lint_file(f))
        return findings

    def lint_file(self, path: Path) -> List[UIFinding]:
        """Lint a single .cpp/.h file. Returns findings (may be empty)."""
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return self.lint_source(str(path), content)

    def lint_source(self, file_label: str, content: str) -> List[UIFinding]:
        """Lint C++ source text (virtual path label for reporting)."""
        findings: List[UIFinding] = []
        findings.extend(self._check_null_parent(file_label, content))
        findings.extend(self._check_cancel_hides_dialog(file_label, content))
        findings.extend(self._check_toolbar_access_chain(file_label, content))
        findings.extend(self._check_paste_explicit_targets(file_label, content))
        return findings

    # ─── Rule 1: NULL-parent dialog ──────────────────────────────

    def _check_null_parent(self, file_label: str, content: str) -> List[UIFinding]:
        out = []
        for m in _NULL_PARENT_RE.finditer(content):
            line = content[:m.start()].count("\n") + 1
            out.append(UIFinding(
                rule="ui_dialog_null_parent",
                severity="error",
                file=file_label,
                line=line,
                problem=f"Dialog constructed with NULL parent: {m.group(0)}",
                reason=(
                    "A top-level CATDlgDialog with a NULL parent is never "
                    "mapped by the CATIA window manager — SetVisibility(CATDlgShow) "
                    "succeeds but nothing appears on screen (silent failure)."
                ),
                fix_hint=(
                    "Pass CATApplicationFrame::GetFrame()->GetMainWindow() "
                    "as the dialog parent instead of NULL."
                ),
                knowledge_ref="knowledge/failure_patterns/fp_dialog_null_parent.md",
            ))
        return out

    # ─── Rule 2: Cancel() must hide the dialog ───────────────────

    def _check_cancel_hides_dialog(self, file_label: str, content: str) -> List[UIFinding]:
        # Only relevant when the command actually manages a dialog
        if "SetVisibility(CATDlgShow)" not in content:
            return []
        bodies = {m.group("name"): m.group("body") for m in _METHOD_RE.finditer(content)}
        cancel_body = bodies.get("Cancel")
        if cancel_body is None:
            return []  # no Cancel override — framework default, not our bug
        if "CATDlgHide" in cancel_body or "RequestDelayedDestruction" in cancel_body:
            return []  # handled
        line = content[:content.find("Cancel")].count("\n") + 1 if "Cancel" in content else 0
        return [UIFinding(
            rule="ui_dialog_cancel_empty",
            severity="error",
            file=file_label,
            line=line,
            problem="Cancel() does not hide the dialog",
            reason=(
                "Clicking the dialog's close/cancel button routes to Cancel(), "
                "NOT Desactivate(). If only Desactivate() hides the dialog, the "
                "close button is dead and the dialog stays on screen."
            ),
            fix_hint=(
                "Add _pDialog->SetVisibility(CATDlgHide) in Cancel() as well; "
                "keep RequestDelayedDestruction() only in the destructor."
            ),
            knowledge_ref="knowledge/failure_patterns/fp_dialog_cancel_not_desactivate.md",
        )]

    # ─── Rule 3: SetAccessChild overwrite chain ──────────────────

    def _check_toolbar_access_chain(self, file_label: str, content: str) -> List[UIFinding]:
        counts: dict = {}
        first_line: dict = {}
        for m in _SET_ACCESS_CHILD_RE.finditer(content):
            tlb = m.group("toolbar")
            counts[tlb] = counts.get(tlb, 0) + 1
            if tlb not in first_line:
                first_line[tlb] = content[:m.start()].count("\n") + 1
        out = []
        for tlb, n in counts.items():
            if n > 1:
                out.append(UIFinding(
                    rule="ui_toolbar_access_chain",
                    severity="error",
                    file=file_label,
                    line=first_line[tlb],
                    problem=(
                        f"SetAccessChild({tlb}, ...) called {n} times — "
                        "each call overwrites the previous starter"
                    ),
                    reason=(
                        "SetAccessChild sets the container's ONLY child; calling it "
                        "again detaches the earlier starter from the toolbar's access "
                        "chain. Icons still render (resources are dictionary-driven) "
                        "but only the last button is clickable."
                    ),
                    fix_hint=(
                        "Call SetAccessChild once for the first starter, then chain "
                        "the rest with SetAccessNext(prevStarter, newStarter)."
                    ),
                    knowledge_ref="knowledge/failure_patterns/fp_toolbar_setaccesschild_overwrite.md",
                ))
        return out

    # ─── Rule 4: Paste with explicit targets ─────────────────────

    def _check_paste_explicit_targets(self, file_label: str, content: str) -> List[UIFinding]:
        # Cross-document indicator: clipboard extract or multiple documents
        cross_doc = ("BoundaryExtract" in content
                     or "CATDocumentServices" in content
                     or "GetDocument" in content)
        out = []
        for m in _PASTE_NON_NULL_RE.finditer(content):
            line = content[:m.start()].count("\n") + 1
            out.append(UIFinding(
                rule="paste_explicit_targets",
                # Cross-document context → crash is certain; same-document
                # usage is legal, so only warn there.
                severity="error" if cross_doc else "warning",
                file=file_label,
                line=line,
                problem=f"Paste() with explicit targets: {m.group(0).strip()}",
                reason=(
                    "Passing explicit CATPathElement targets to "
                    "CATICutAndPastable::Paste is only safe for SAME-document "
                    "paste. Across documents the path references source-context "
                    "objects and CATIA crashes with an UNcatchable runtime "
                    "exception (try/catch and set_terminate do not fire)."
                ),
                fix_hint=(
                    "Pass NULL for iToCurObjects: Paste(iObj, NULL, NULL) and let "
                    "the target container decide (defaults to MainBody). For "
                    "precise cross-document placement use the Automation layer "
                    "(Selection.Copy/PasteSpecial) instead."
                ),
                knowledge_ref="knowledge/failure_patterns/fp_paste_cross_doc_catpathelement.md",
            ))
        return out
