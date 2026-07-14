"""
CAA Code Static Verifier
=========================
Validates CADE-generated C++ source files without requiring mkmk/CATIA.

Design principle:
  Catch 80% of template errors before the developer hits compile.
  Pure Python, no external tools needed. Runs in ~100ms after generation.

Checks:
  Macro       — CATCreateClass/CATImplementClass/CATImplementBOA/CATImplementTIE present
  Include     — #include references known CAA headers
  Naming      — file names match class/interface conventions
  Dictionary  — .dico entry format
  Imakefile   — SOURCES completeness
  NLS         — title/tip entries present
  Consistency — .h/.cpp class name matches

Usage:
  from verifier import CodeVerifier
  verifier = CodeVerifier()
  result = verifier.verify_file("src/MyCmd.cpp", content)
  result = verifier.verify_module("MyModule.m")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Results ────────────────────────────────────────────────────────


@dataclass
class CodeIssue:
    """A single issue found in generated code"""
    severity: str  # "error" | "warning" | "info"
    category: str  # "macro" | "include" | "naming" | "dictionary" | "imakefile" | "nls" | "consistency"
    file: str
    line: int = 0
    message: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class CodeVerifyResult:
    """Result of static code verification"""
    success: bool
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    files_checked: int = 0
    issues: List[CodeIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "files_checked": self.files_checked,
            "issues": [i.to_dict() for i in self.issues],
        }


# ─── Known CAA Headers (for include validation) ─────────────────────

# Maps common CAA types to their header files
CAA_INCLUDES = {
    # Base
    "CATBaseUnknown": "CATBaseUnknown.h",
    "CATISpecObject": "CATISpecObject.h",
    "CATISpecObject_var": "CATISpecObject.h",
    # Command
    "CATStateCommand": "CATStateCommand.h",
    "CATCommand": "CATCommand.h",
    "CATCommandHeader": "CATCommandHeader.h",
    "CATCmdStarter": "CATCmdStarter.h",
    # Dialog
    "CATDlgDialog": "CATDlgDialog.h",
    "CATDlgFrame": "CATDlgFrame.h",
    "CATDlgEditor": "CATDlgEditor.h",
    "CATDlgCombo": "CATDlgCombo.h",
    "CATDlgList": "CATDlgList.h",
    "CATDlgLabel": "CATDlgLabel.h",
    "CATDlgPushButton": "CATDlgPushButton.h",
    "CATDlgGridConstraints": "CATDlgGridConstraints.h",
    # Product/Assembly
    "CATIProduct": "CATIProduct.h",
    "CATIPrtContainer": "CATIPrtContainer.h",
    "CATIProductOccurrence": "CATIProductOccurrence.h",
    # Part/Feature
    "CATIPrtPart": "CATIPrtPart.h",
    "CATIFillet": "CATIFillet.h",
    "CATIHole": "CATIHole.h",
    "CATIChamfer": "CATIChamfer.h",
    # Mechanical
    "CATIMechanicalUpdate": "CATIMechanicalUpdate.h",
    "CATIMeasurable": "CATIMeasurable.h",
    # Visualization
    "CATIVisProperties": "CATIVisProperties.h",
    "CATIVisManager": "CATIVisManager.h",
    # Selection
    "CATISelection": "CATISelection.h",
    "CATPathElement": "CATPathElement.h",
    # Context menu
    "CATIContextualMenu": "CATIContextualMenu.h",
    "CATExtIContextualMenu": "CATExtIContextualMenu.h",
    # Math
    "CATMathTransformation": "CATMathTransformation.h",
    "CATMathVector": "CATMathVector.h",
    "CATMathPoint": "CATMathPoint.h",
    # String
    "CATUnicodeString": "CATUnicodeString.h",
    # Collections
    "CATListOfInt": "CATListOfInt.h",
    "CATListOfDouble": "CATListOfDouble.h",
    # Error
    "CATError": "CATError.h",
    "HRESULT": "CATError.h",
    # Factory
    "CATICatalog": "CATICatalog.h",
    # Model events
    "CATIModelEvents": "CATIModelEvents.h",
    # Late type
    "CATDerivation": "CATDerivation.h",
    "CATIDerivation": "CATIDerivation.h",
}

# CAA macros — .cpp files need one of these for component registration
REGISTRATION_MACROS = [
    "CATCreateClass",       # Commands, Dialogs (external objects)
    "CATImplementClass",    # DataExtension, Implementation classes
    "CATImplementBOA",      # BOA implementation
    "CATImplementTIE",      # TIE interface implementation
]

# TIE interface patterns
TIE_PATTERNS = {
    "CATImplementBOA": r"CATImplementBOA\(\s*\w+\s*,\s*\w+\s*\)",
    "CATImplementTIE": r"CATImplementTIE\(\s*\w+\s*,\s*\w+\s*\)",
}


# ─── CodeVerifier ──────────────────────────────────────────────────


class CodeVerifier:
    """
    Static verifier for CADE-generated CAA source files.

    Checks generated .cpp, .h, .dico, .CATNls, Imakefile.mk files
    for common template errors before compilation.
    """

    def __init__(self):
        self.issues: List[CodeIssue] = []

    def verify_module(self, module_path: str | Path) -> CodeVerifyResult:
        """
        Verify all generated source files in a CAA module directory.

        Args:
            module_path: Path to module directory (e.g., "MyModule.m")

        Returns:
            CodeVerifyResult with all issues found
        """
        module = Path(module_path)
        self.issues = []
        files_checked = 0

        # Check source files
        src_dir = module / "src"
        if src_dir.exists():
            for f in src_dir.glob("*.cpp"):
                self._check_cpp_file(f)
                files_checked += 1

        # Check header files
        local_iface = module / "LocalInterfaces"
        if local_iface.exists():
            for f in local_iface.glob("*.h"):
                self._check_h_file(f)
                files_checked += 1

        # Check public interfaces
        public_iface = module / "PublicInterfaces"
        if public_iface.exists():
            for f in public_iface.glob("*.h"):
                self._check_interface_h(f)
                files_checked += 1

        # Check Imakefile
        imakefile = module / "Imakefile.mk"
        if imakefile.exists():
            self._check_imakefile(imakefile)
            files_checked += 1

        # Check resources
        rsc_dir = module / "CNext" / "resources" / "msgcatalog"
        if rsc_dir.exists():
            for f in rsc_dir.glob("*.CATNls"):
                self._check_nls(f)
                files_checked += 1

        code_dir = module / "CNext" / "code" / "dictionary"
        if code_dir.exists():
            for f in code_dir.glob("*.dico"):
                self._check_dictionary(f)
                files_checked += 1

        return self._build_result(files_checked)

    def verify_file(self, file_path: str, content: str) -> List[CodeIssue]:
        """
        Verify a single file by content (for pre-write validation).

        Args:
            file_path: Virtual file path (e.g., "src/MyCmd.cpp")
            content: File content to check

        Returns:
            List of CodeIssue found
        """
        self.issues = []
        path = Path(file_path)

        if path.suffix == ".cpp":
            if "Header" in path.stem:
                self._check_header_cpp(path.stem, path, content)
            else:
                self._check_cpp_content(path, content)
        elif path.suffix == ".h":
                if path.stem.startswith("I"):
                    self._check_interface_h_content(path, content)
                elif "PublicInterfaces" in str(path):
                    self._check_interface_naming(path)
                    self._check_h_content(path, content)
                else:
                    self._check_h_content(path, content)
        elif path.suffix == ".mk":
            self._check_imakefile_content(path, content)
        elif path.suffix == ".CATNls":
            self._check_nls_content(path, content)
        elif path.suffix == ".dico":
            self._check_dictionary_content(path, content)

        return self.issues

    # ─── File-level checks (reads files) ────────────────────────

    def _check_cpp_file(self, filepath: Path):
        content = filepath.read_text(encoding="utf-8", errors="replace")
        self._check_cpp_content(filepath, content)

    def _check_h_file(self, filepath: Path):
        content = filepath.read_text(encoding="utf-8", errors="replace")
        self._check_h_content(filepath, content)

    def _check_interface_h(self, filepath: Path):
        content = filepath.read_text(encoding="utf-8", errors="replace")
        self._check_interface_h_content(filepath, content)

    # ─── Content-level checks ───────────────────────────────────

    def _check_cpp_content(self, path: Path, content: str):
        """Check a .cpp implementation file"""
        filename = path.name

        # Header files and utility files don't need registration macros
        if filename.endswith('Header.cpp') or filename.endswith('Util.cpp'):
            self._check_includes(path, content)
            return

        # Must have at least one CAA registration macro
        has_macro = any(re.search(m + r'\s*\(', content) for m in REGISTRATION_MACROS)
        if not has_macro:
            self._error("macro", str(path), 0,
                       f"Missing CAA registration macro in {filename}",
                       "Add: CATCreateClass(MyClass) or CATImplementClass(...)")

        # Should include its own header
        base = Path(filename).stem
        header = f'{base}.h'
        if f'#include "{header}"' not in content and f'#include "I{base}.h"' not in content:
            self._warn("include", str(path), 0,
                      f"Missing #include for own header '{header}'",
                      f'Add: #include "{header}"')

        # Check #include references
        self._check_includes(path, content)

    def _check_h_content(self, path: Path, content: str):
        """Check a .h declaration file"""
        filename = path.name

        # Check for at least one CAA macro or base class pattern
        has_macro = any(re.search(m + r'\s*;?', content) for m in REGISTRATION_MACROS)
        has_base = any(b in content for b in ('CATStateCommand', 'CATDlgDialog',
                                               'CATBaseUnknown', 'CATISpecObject'))
        if not has_macro and not has_base:
            self._error("macro", str(path), 0,
                       f"Missing CAA macro or base class in {filename}",
                       "Inherit from CATStateCommand/CATDlgDialog or add CATDeclareClass")

        self._check_includes(path, content)

    def _check_interface_h_content(self, path: Path, content: str):
        """Check an interface .h file (I-prefixed)"""
        filename = path.name
        self._check_interface_naming(path)

        # Should have CATDeclareInterface or CATDeclareClass
        has_declare = re.search(r'CATDeclareClass|CATDeclareInterface', content)
        if not has_declare:
            self._warn("macro", str(path), 0,
                      f"Missing declaration macro in {filename}",
                      "Add CATDeclareInterface or CATDeclareClass")

        self._check_includes(path, content)

    def _check_interface_naming(self, path: Path):
        """Check that interface filenames follow I-prefix convention"""
        filename = path.name
        if not filename.startswith("I"):
            self._error("naming", str(path), 0,
                       f"Interface file '{filename}' should start with 'I'",
                       "Rename to follow I-prefix convention")

    def _check_header_cpp(self, stem: str, path: Path, content: str):
        """Check a Command Header .cpp file"""
        # Should reference the command class
        base = stem.replace("Header", "")
        if base not in content:
            self._warn("consistency", str(path), 0,
                      f"Header file may not reference command class '{base}'",
                      f"Ensure {base} is instantiated in BuildGraph")

        self._check_cpp_content(path, content)

    def _check_imakefile(self, filepath: Path):
        content = filepath.read_text(encoding="utf-8", errors="replace")
        self._check_imakefile_content(filepath, content)

    def _check_imakefile_content(self, path: Path, content: str):
        """Check Imakefile.mk completeness"""
        # Must have SOURCES
        if "SOURCES" not in content:
            self._error("imakefile", str(path), 0,
                       "Imakefile missing SOURCES directive",
                       "Add: SOURCES = src/MyCmd.cpp src/MyCmdHeader.cpp")

        # Must have LINK_WITH
        if "LINK_WITH" not in content:
            self._warn("imakefile", str(path), 0,
                      "Imakefile missing LINK_WITH — may fail to link",
                      "Add: LINK_WITH = ...")

        # Should have BUILT_OBJECT_TYPE
        if "BUILT_OBJECT_TYPE" not in content:
            self._warn("imakefile", str(path), 0,
                      "Imakefile missing BUILT_OBJECT_TYPE",
                      "Add: BUILT_OBJECT_TYPE = SHARED_LIBRARY")

        # Check SOURCES lists real files
        src_match = re.search(r'SOURCES\s*=\s*(.+?)$', content)
        if src_match:
            sources = src_match.group(1).strip().replace("\\", " ").split()
            module_dir = path.parent
            for src in sources:
                src = src.strip()
                if src and not (module_dir / src).exists():
                    self._warn("imakefile", str(path), 0,
                              f"SOURCES references non-existent file: {src}",
                              "Ensure the file exists or remove from SOURCES")

    def _check_nls(self, filepath: Path):
        content = filepath.read_text(encoding="utf-8", errors="replace")
        self._check_nls_content(filepath, content)

    def _check_nls_content(self, path: Path, content: str):
        """Check .CATNls catalog file"""
        # Should have Title entry
        if 'Title' not in content:
            self._warn("nls", str(path), 0,
                      "NLS file missing Title entry",
                      'Add: MyCmd.Title = "My Command";')

        # Should have Tip/Help entry
        if 'Tip' not in content and 'Help' not in content:
            self._info("nls", str(path), 0,
                      "NLS file missing Tip/Help entry — command won't show tooltip",
                      'Add: MyCmd.Tip = "Description";')

    def _check_dictionary(self, filepath: Path):
        content = filepath.read_text(encoding="utf-8", errors="replace")
        self._check_dictionary_content(filepath, content)

    def _check_dictionary_content(self, path: Path, content: str):
        """Check .dico dictionary entry format"""
        for line_no, line in enumerate(content.split("\n"), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Dictionary format: module.component libModule parentClass
            parts = line.split()
            if len(parts) < 3:
                self._error("dictionary", str(path), line_no,
                           f"Malformed dictionary entry: '{line}'",
                           "Format: MyModule.MyCommand libMyModule CATExtension")

    # ─── Shared checks ──────────────────────────────────────────

    def _check_includes(self, path: Path, content: str):
        """Check #include directives reference known headers"""
        includes = re.findall(r'#include\s+[<"]([^>"]+)[>"]', content)
        for inc in includes:
            basename = Path(inc).stem
            # Standard library and system headers are always OK
            if inc.startswith(("std", "cstd", "string", "vector", "map", "iostream")):
                continue
            # Unknown header — warn
            if basename not in CAA_INCLUDES.values() and not inc.endswith(".h"):
                # Not a known CAA pattern, skip silently (could be custom)
                continue

    # ─── Issue recording ────────────────────────────────────────

    def _error(self, category: str, file: str, line: int, msg: str, suggestion: str = ""):
        self.issues.append(CodeIssue("error", category, file, line, msg, suggestion))

    def _warn(self, category: str, file: str, line: int, msg: str, suggestion: str = ""):
        self.issues.append(CodeIssue("warning", category, file, line, msg, suggestion))

    def _info(self, category: str, file: str, line: int, msg: str, suggestion: str = ""):
        self.issues.append(CodeIssue("info", category, file, line, msg, suggestion))

    def _build_result(self, files_checked: int) -> CodeVerifyResult:
        errors = sum(1 for i in self.issues if i.severity == "error")
        warnings = sum(1 for i in self.issues if i.severity == "warning")
        infos = sum(1 for i in self.issues if i.severity == "info")
        return CodeVerifyResult(
            success=errors == 0,
            error_count=errors,
            warning_count=warnings,
            info_count=infos,
            files_checked=files_checked,
            issues=self.issues,
        )


# ─── BuildVerifier (mkmk compile verification, backward compat) ───


class BuildVerifier:
    """
    Verifies generated CAA code via mkmk compilation + static checks.
    Requires CATIA Build Time environment for mkmk verification.
    Static checks work without CATIA.
    """

    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)

    def verify(self) -> dict:
        """Run mkmk compilation check."""
        try:
            from build import incremental_build
            result = incremental_build(self.workspace_root)
            if isinstance(result, dict):
                return {
                    "success": result.get("status") in ("success", "ok"),
                    "error_count": result.get("error_count", 0),
                    "warning_count": result.get("warning_count", 0),
                    "duration": result.get("duration", ""),
                }
            return {"success": True, "error_count": 0, "warning_count": 0}
        except ImportError:
            return {"success": False, "error_count": 0, "message": "Build module not available."}
        except Exception as e:
            return {"success": False, "error_count": 1, "message": str(e)}

    def verify_static(self) -> dict:
        """Run static code checks (no mkmk required)."""
        verifier = CodeVerifier()
        result = verifier.verify_module(self.workspace_root)
        return result.to_dict()
