"""
CATIA CAA mkmk Output Parser
============================
Purpose: Parse mkmk compilation output and extract errors/warnings
Called by: build.py
Output: Structured error list
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CompilationError:
    """Represents a single compilation error or warning"""

    framework: str = ""
    module: str = ""
    file: str = ""
    line: int = 0
    code: str = ""
    message: str = ""
    severity: str = "error"  # "error" or "warning"
    # True when this entry is a downstream consequence of an earlier root
    # cause (e.g. the missing .obj/.dll reported after a compile error already
    # aborted the step). Cascaded entries stay in `errors` and still fail the
    # build -- they are only excluded from the root-cause `error_count`.
    cascade: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "framework": self.framework,
            "module": self.module,
            "file": self.file,
            "line": self.line,
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "cascade": self.cascade,
        }


# Wrapper-layer error codes emitted by mkmk itself rather than by the
# compiler/linker. They are the "did the build fail at all" signal (see
# SKILL.md > Build 结果判定), not necessarily independent root causes.
WRAPPER_ERROR_CODES = frozenset({"mkmk-ERROR", "make-ERROR", "syst-ERROR"})

# Text that marks a wrapper error as a consequence of an earlier failure: the
# artifact was never produced because the compile/link step already died.
_CASCADE_MESSAGE_RE = re.compile(
    r"no such file or directory|cannot find|cannot open",
    re.IGNORECASE,
)
_CASCADE_ARTIFACT_RE = re.compile(r"\.(obj|lib|dll|exp|ilk|pdb)$", re.IGNORECASE)


class MkmkParser:
    """Parser for mkmk compilation output"""

    # Regex patterns for different error formats
    PATTERNS = {
        # Microsoft Visual C++ error format
        # Example: C:\path\MyFile.cpp(126): error C2143: syntax error: missing ';' before '}'
        "msvc": re.compile(
            r"(?P<file>[^(]+)\((?P<line>\d+)\)\s*:\s*(?P<severity>error|warning)\s+(?P<code>\w+)\s*:\s*(?P<message>.+)"
        ),
        # Alternative MSVC format
        # Example: MyFile.cpp(126) : error C2143: missing ';'
        "msvc_alt": re.compile(
            r"(?P<file>[^(]+)\((?P<line>\d+)\)\s*:\s*(?P<severity>error|warning)\s+(?P<code>\w+)\s*:\s*(?P<message>.+)"
        ),
        # Link errors
        # Example: MyFile.obj : error LNK2001: unresolved external symbol
        "linker": re.compile(
            r"(?P<file>\S+\.obj)\s*:\s*(?P<severity>error|warning)\s+(?P<code>LNK\d+)\s*:\s*(?P<message>.+)"
        ),
        # Fatal errors
        # Example: fatal error C1083: Cannot open include file
        "fatal": re.compile(
            r"fatal\s+(?P<severity>error)\s+(?P<code>\w+)\s*:\s*(?P<message>.+)"
        ),
        # mkmk wrapper errors. B28 emits mkmk-ERROR; make-ERROR is retained
        # for compatibility with output observed from other toolchain layers.
        "mkmk_error": re.compile(
            r"^\s*#?\s*(?P<code>(?:mkmk|make)-(?P<severity>ERROR))\s*:\s*(?P<file>.+?)\s*$"
        ),
        # Require whitespace after the separator so a Windows drive colon is
        # not mistaken for the file/message boundary.
        "syst_error": re.compile(
            r"^\s*#?\s*(?P<code>syst-(?P<severity>ERROR))\s*:\s*(?P<file>.+?)(?::\s+|\s+-\s+)(?P<message>.+?)\s*$"
        ),
        # Generic error/warning
        "generic": re.compile(
            r"(?P<severity>error|warning)\s+(?P<code>\w+)\s*:\s*(?P<message>.+)"
        ),
    }

    def __init__(self):
        self.errors: List[CompilationError] = []
        self.warnings: List[CompilationError] = []
        self.current_framework = ""
        self.current_module = ""

    def parse_line(self, line: str) -> Optional[CompilationError]:
        """
        Parse a single line of mkmk output

        Args:
            line: One line from mkmk output

        Returns:
            CompilationError if error/warning found, None otherwise
        """
        line = line.strip()
        if not line:
            return None

        # Detect framework context
        if "Framework:" in line or "Building framework" in line:
            match = re.search(r"(\w+\.edu)", line)
            if match:
                self.current_framework = match.group(1)

        # Detect module context
        if "Module:" in line or "Building module" in line:
            match = re.search(r"(\w+\.m)", line)
            if match:
                self.current_module = match.group(1)

        # Try each pattern
        for pattern_name, pattern in self.PATTERNS.items():
            match = pattern.search(line)
            if match:
                error = CompilationError()
                error.framework = self.current_framework
                error.module = self.current_module

                groups = match.groupdict()
                error.file = groups.get("file", "").strip()
                error.message = groups.get("message", "").strip()
                error.code = groups.get("code", "").strip()
                error.severity = groups.get("severity", "error").lower()

                # Parse line number
                if "line" in groups and groups["line"]:
                    try:
                        error.line = int(groups["line"])
                    except ValueError:
                        error.line = 0

                # Clean up file path (keep relative path when possible)
                if error.file:
                    # Remove common prefixes but keep relative structure
                    file_path = error.file.replace("\\", "/")
                    # If it contains a framework-like structure, trim to meaningful part
                    for sep in ["/src/", "/LocalInterfaces/", "/PublicInterfaces/"]:
                        if sep in file_path:
                            idx = file_path.index(sep)
                            file_path = file_path[idx + 1 :]  # src/Foo.cpp
                            break
                    else:
                        file_path = file_path.split("/")[-1]
                    error.file = file_path

                return error

        return None

    def parse(self, output: str) -> Dict:
        """
        Parse complete mkmk output

        Args:
            output: Full mkmk stdout/stderr output

        Returns:
            Dictionary with errors, warnings, and counts
        """
        self.errors = []
        self.warnings = []
        self.current_framework = ""
        self.current_module = ""

        lines = output.split("\n")
        for line in lines:
            error = self.parse_line(line)
            if error:
                if error.severity == "error":
                    self.errors.append(error)
                else:
                    self.warnings.append(error)

        self._mark_cascade_errors()

        root_causes = [e for e in self.errors if not e.cascade]
        cascaded = [e for e in self.errors if e.cascade]
        wrappers = [e for e in self.errors if e.code in WRAPPER_ERROR_CODES]

        return {
            # Root causes only: one C2440 is one error, not seven.
            "error_count": len(root_causes),
            "cascade_count": len(cascaded),
            # All wrapper-layer errors, cascaded or not. build.py fails the
            # build on this too, so cascade marking can never turn a real
            # failure into a false "success".
            "wrapper_error_count": len(wrappers),
            "warning_count": len(self.warnings),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }

    def _mark_cascade_errors(self) -> None:
        """Flag wrapper errors that are consequences of an earlier root cause.

        A single compile error aborts the step, after which mkmk reports the
        failed step and every artifact that was never produced as separate
        wrapper errors. Those are reclassified as cascade -- but only when a
        compiler/linker root cause actually precedes them. With no root cause
        in the output, every wrapper error stays countable: mkmk can return 0
        while the build genuinely failed, and that verdict must survive.
        """
        seen_root_cause = False
        for error in self.errors:
            if error.severity != "error":
                continue
            if error.code not in WRAPPER_ERROR_CODES:
                seen_root_cause = True
                continue
            if seen_root_cause and _is_cascade_consequence(error):
                error.cascade = True

    def get_summary(self) -> str:
        """Get human-readable summary"""
        if not self.errors and not self.warnings:
            return "✓ Build successful (0 errors, 0 warnings)"

        root_causes = [e for e in self.errors if not e.cascade]
        cascaded = [e for e in self.errors if e.cascade]

        parts = []
        if root_causes:
            parts.append(f"{len(root_causes)} error(s)")
        if cascaded:
            parts.append(f"{len(cascaded)} cascaded")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")

        return "✗ Build failed: " + ", ".join(parts)


def _is_cascade_consequence(error: CompilationError) -> bool:
    """Does this wrapper error look like fallout from an earlier failure?"""
    text = f"{error.file} {error.message}".strip()
    if _CASCADE_MESSAGE_RE.search(text):
        return True
    if _CASCADE_ARTIFACT_RE.search(error.file):
        return True
    # mkmk/make-ERROR naming a module or framework target reports the build
    # step that failed, never an independent cause of its own.
    if error.code in ("mkmk-ERROR", "make-ERROR") and error.file.lower().endswith(
        (".m", ".edu")
    ):
        return True
    return False


def parse_mkmk_output(output: str) -> Dict:
    """
    Quick helper to parse mkmk output

    Args:
        output: mkmk stdout/stderr text

    Returns:
        Dictionary with parsed errors and warnings
    """
    parser = MkmkParser()
    return parser.parse(output)


# ─── Error Diagnosis ──────────────────────────────────────────

_ERROR_ADVICE = {
    "C2027": "使用了未定义类型 — 需要 #include 完整的类头文件（不只是前向声明）",
    "C2039": "不是类的成员 — 检查方法名是否正确（B28: Undo→ExecuteUndo, Redo→ExecuteRedo）",
    "C2143": "语法错误 — 检查缺少分号或花括号",
    "C1083": "找不到头文件 — 检查 #include 路径或是否缺少 AddPrereqComponent",
    "LNK2001": "未解析的外部符号 — 检查 Imakefile.mk 的 LINK_WITH 是否缺少依赖模块",
    "LNK2019": "未解析的外部符号 — 同上，检查模块链接配置",
    "mkmk-ERROR": "mkmk 配置错误 — 检查 workspace 是否有 .edu 框架目录",
    "make-ERROR": "mkmk 构建步骤错误 — 检查对应文件和前序编译输出",
    "syst-ERROR": "构建系统错误 — 检查文件访问、路径和工具链环境",
}


def diagnose_errors(parse_result: dict) -> list:
    """Generate actionable fix suggestions for compilation errors.

    Cascaded wrapper errors are skipped: advising on a missing .obj that never
    existed because of a syntax error sends the fixer to the wrong file. They
    are still used when nothing else is available (wrapper-only failures).
    """
    suggestions = []
    seen = set()
    errors = parse_result.get("errors", [])
    root_causes = [e for e in errors if not e.get("cascade")]
    for err in root_causes or errors:
        code = err.get("code", "")
        if code in _ERROR_ADVICE and code not in seen:
            seen.add(code)
            suggestions.append(f"[{code}] {_ERROR_ADVICE[code]}")
            if err.get("file"):
                suggestions[-1] += f" (文件: {err['file']})"
    return suggestions


if __name__ == "__main__":
    # Test with sample output
    test_output = """
Building framework MyFramework.edu
Building module MyModule.m
C:\\workspace\\MyModule\\src\\MyFile.cpp(126): error C2143: syntax error: missing ';' before '}'
C:\\workspace\\MyModule\\src\\MyFile.cpp(130): warning C4101: 'unused' : unreferenced local variable
MyFile.obj : error LNK2001: unresolved external symbol "public: virtual void Test(void)"
fatal error C1083: Cannot open include file: 'missing.h'
"""

    result = parse_mkmk_output(test_output)

    import json

    print(json.dumps(result, indent=2))
