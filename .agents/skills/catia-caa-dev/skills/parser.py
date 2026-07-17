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
        }


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

        return {
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }

    def get_summary(self) -> str:
        """Get human-readable summary"""
        if not self.errors and not self.warnings:
            return "✓ Build successful (0 errors, 0 warnings)"

        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} error(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")

        return "✗ Build failed: " + ", ".join(parts)


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
    """Generate actionable fix suggestions for compilation errors."""
    suggestions = []
    seen = set()
    for err in parse_result.get("errors", []):
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
