#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CADE Production Readiness Checklist

生产就绪完整检查清单 - 20年专家标准
"""

import os
import subprocess
import sys
from pathlib import Path


class ProductionReadinessCheck:
    def __init__(self):
        self.root = Path(__file__).parent.parent
        self.errors = []
        self.warnings = []
        self.info = []
        self.checks_passed = 0
        self.checks_total = 0

    def check_all(self):
        """执行所有生产就绪检查"""
        print("=" * 70)
        print("  CADE Production Readiness Checklist")
        print("  20年专家标准 - 完整检查")
        print("=" * 70)

        self.check_1_code_quality()
        self.check_2_documentation()
        self.check_3_testing()
        self.check_4_security()
        self.check_5_performance()
        self.check_6_maintainability()
        self.check_7_deployment()
        self.check_8_backwards_compatibility()
        self.check_9_error_handling()
        self.check_10_versioning()

        self.print_summary()

        return len(self.errors) == 0

    def check_item(self, name, condition, error_msg=None, warning_msg=None):
        """检查单项"""
        self.checks_total += 1
        if condition:
            self.checks_passed += 1
            print(f"  [PASS] {name}")
            return True
        else:
            if error_msg:
                self.errors.append(f"{name}: {error_msg}")
                print(f"  [FAIL] {name}")
            elif warning_msg:
                self.warnings.append(f"{name}: {warning_msg}")
                print(f"  [WARN] {name}")
            return False

    def check_1_code_quality(self):
        """1. 代码质量"""
        print("\n[1/10] Code Quality Check...")

        # 检查是否有 TODO/FIXME
        result = subprocess.run(
            ["grep", "-r", "TODO\\|FIXME", "skills/", "--include=*.py"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        todo_count = len(result.stdout.splitlines()) if result.stdout else 0
        self.check_item(
            "No critical TODOs",
            todo_count == 0,
            warning_msg=f"Found {todo_count} TODO/FIXME items",
        )

        # 检查是否有 print() 调试语句
        result = subprocess.run(
            ["grep", "-r", "print(", "skills/", "--include=*.py"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        lines = result.stdout.splitlines() if result.stdout else []
        # 过滤掉合法的 print（如 file=sys.stderr）
        debug_prints = [l for l in lines if "file=" not in l and "def print" not in l]
        self.check_item(
            "No debug print statements",
            len(debug_prints) == 0,
            warning_msg=f"Found {len(debug_prints)} debug print() statements",
        )

        # 检查是否有长行（>120字符）
        long_lines = []
        for py_file in (self.root / "skills").rglob("*.py"):
            with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    if len(line.rstrip()) > 120:
                        long_lines.append(f"{py_file.name}:{i}")
        self.check_item(
            "No excessively long lines (>120 chars)",
            len(long_lines) < 10,
            warning_msg=f"Found {len(long_lines)} long lines",
        )

    def check_2_documentation(self):
        """2. 文档完整性"""
        print("\n[2/10] Documentation Check...")

        # 核心文档（README.md is at CADE root, 3 levels up）
        root_parent = self.root.parent.parent.parent
        core_docs = ["README.md", "SKILL.md", "CHANGELOG.md", "LICENSE"]
        for doc in core_docs:
            doc_path = root_parent if doc == "README.md" else self.root
            self.check_item(
                f"Core doc: {doc}",
                (doc_path / doc).exists(),
                error_msg=f"Missing {doc}",
            )

        # 知识系统文档
        self.check_item(
            "Knowledge system README",
            (self.root / "knowledge" / "README.md").exists(),
            error_msg="Missing knowledge/README.md",
        )

        self.check_item(
            "Patterns README",
            (self.root / "patterns" / "README.md").exists(),
            error_msg="Missing patterns/README.md",
        )

        # Read README from CADE root (3 levels up)
        readme_path = self.root.parent.parent.parent / "README.md"
        with open(readme_path, "r", encoding="utf-8") as f:
            readme = f.read()
        self.check_item(
            "README mentions Knowledge System",
            "Knowledge System" in readme or "知识系统" in readme,
            error_msg="README doesn't mention Knowledge System",
        )

    def check_3_testing(self):
        """3. 测试覆盖"""
        print("\n[3/10] Testing Check...")

        # 检查测试文件数量
        test_files = list((self.root / "tests").glob("test_*.py"))
        self.check_item(
            "Sufficient test files (>= 20)",
            len(test_files) >= 20,
            error_msg=f"Only {len(test_files)} test files",
        )

        # 检查是否有 L7 知识系统测试
        self.check_item(
            "L7 Knowledge system test exists",
            (self.root / "tests" / "test_knowledge_system.py").exists(),
            error_msg="Missing L7 knowledge test",
        )

        # 检查是否有系统健康检查
        self.check_item(
            "System health check exists",
            (self.root / "tests" / "test_system_health.py").exists(),
            warning_msg="Missing system health check",
        )

    def check_4_security(self):
        """4. 安全性"""
        print("\n[4/10] Security Check...")

        # 检查是否有硬编码密码
        result = subprocess.run(
            ["grep", "-ri", "password.*=.*['\"]", "skills/", "--include=*.py"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        self.check_item(
            "No hardcoded passwords",
            not result.stdout,
            error_msg="Found potential hardcoded passwords",
        )

        # 检查 .gitignore 是否保护配置文件
        with open(self.root / ".gitignore", "r") as f:
            gitignore = f.read()
        self.check_item(
            ".gitignore protects config",
            "caa_env_config.txt" in gitignore,
            error_msg="Config file not in .gitignore",
        )

        self.check_item(
            ".gitignore protects cache",
            "__pycache__" in gitignore,
            warning_msg="__pycache__ not in .gitignore",
        )

    def check_5_performance(self):
        """5. 性能考量"""
        print("\n[5/10] Performance Check...")

        # 检查是否有不必要的递归
        result = subprocess.run(
            ["grep", "-r", "def.*recursive", "skills/", "--include=*.py"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        recursive_count = len(result.stdout.splitlines()) if result.stdout else 0
        self.info.append(f"Found {recursive_count} explicit recursive functions")

        # 检查是否有缓存机制
        has_cache = (self.root / "cache").exists()
        self.check_item(
            "Cache directory exists", has_cache, warning_msg="No cache directory"
        )

    def check_6_maintainability(self):
        """6. 可维护性"""
        print("\n[6/10] Maintainability Check...")

        # 检查模块化程度（文件数量）
        py_files = list((self.root / "skills").rglob("*.py"))
        self.check_item(
            "Reasonable module count (10-30)",
            10 <= len(py_files) <= 30,
            warning_msg=f"Unusual file count: {len(py_files)}",
        )

        # 检查是否有巨型文件（>1000行）
        huge_files = []
        for py_file in py_files:
            with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = len(f.readlines())
                if lines > 1000:
                    huge_files.append(f"{py_file.name} ({lines} lines)")
        self.check_item(
            "No huge files (>1000 lines)",
            len(huge_files) == 0,
            warning_msg=f"Large files: {', '.join(huge_files)}",
        )

    def check_7_deployment(self):
        """7. 部署就绪"""
        print("\n[7/10] Deployment Check...")

        # 检查是否有 requirements.txt
        self.check_item(
            "requirements.txt exists",
            (self.root / "config" / "requirements.txt").exists(),
            warning_msg="No requirements.txt",
        )

        # 检查是否有安装说明（README.md is at CADE root）
        readme_path = self.root.parent.parent.parent / "README.md"
        with open(readme_path, "r", encoding="utf-8") as f:
            readme = f.read()
        self.check_item(
            "README has installation instructions",
            "Install" in readme or "安装" in readme,
            error_msg="No installation instructions",
        )

    def check_8_backwards_compatibility(self):
        """8. 向后兼容性"""
        print("\n[8/10] Backwards Compatibility Check...")

        # 检查 CHANGELOG 是否记录了 breaking changes
        with open(self.root / "CHANGELOG.md", "r", encoding="utf-8") as f:
            changelog = f.read()
        has_v2 = "2.2.0" in changelog or "2.0.0" in changelog
        self.check_item(
            "CHANGELOG documents v2.x", has_v2, error_msg="no version 2.x documented"
        )

        # 检查是否保留了旧 API（如果有的话）
        self.info.append("Manual review: Check if old APIs are deprecated gracefully")

    def check_9_error_handling(self):
        """9. 错误处理"""
        print("\n[9/10] Error Handling Check...")

        # 检查是否有裸 except
        result = subprocess.run(
            ["grep", "-rn", "except:$", "skills/", "--include=*.py"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        bare_excepts = len(result.stdout.splitlines()) if result.stdout else 0
        self.check_item(
            "No bare except clauses",
            bare_excepts == 0,
            warning_msg=f"Found {bare_excepts} bare except: clauses",
        )

        # 检查是否有合理的日志
        has_logging = (self.root / "logs").exists()
        self.check_item(
            "Logging directory exists", has_logging, warning_msg="No logging directory"
        )

    def check_10_versioning(self):
        """10. 版本管理"""
        print("\n[10/10] Versioning Check...")

        # 检查版本号一致性（README.md is at CADE root）
        readme_path = self.root.parent.parent.parent / "README.md"
        files_to_check = [
            (readme_path, "2.2.0"),
            (self.root / "SKILL.md", "2.2.0"),
            (self.root / "CHANGELOG.md", "2.2.0"),
        ]

        for file_path, expected_version in files_to_check:
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.check_item(
                    f"Version {expected_version} in {file_path.name}",
                    expected_version in content,
                    error_msg=f"Version mismatch in {file_path.name}",
                )

    def print_summary(self):
        """打印汇总"""
        print("\n" + "=" * 70)
        print("  Summary")
        print("=" * 70)

        print(f"\nChecks:       {self.checks_passed}/{self.checks_total}")
        print(f"Pass Rate:    {self.checks_passed / self.checks_total * 100:.1f}%")
        print(f"Errors:       {len(self.errors)}")
        print(f"Warnings:     {len(self.warnings)}")
        print(f"Info:         {len(self.info)}")

        if self.errors:
            print("\n[ERRORS]:")
            for err in self.errors:
                print(f"  - {err}")

        if self.warnings:
            print("\n[WARNINGS]:")
            for warn in self.warnings:
                print(f"  - {warn}")

        if self.info:
            print("\n[INFO]:")
            for info in self.info:
                print(f"  - {info}")

        if not self.errors and len(self.warnings) <= 3:
            print("\n[PASS] PRODUCTION READY")
        elif not self.errors:
            print("\n[WARN] READY WITH WARNINGS")
        else:
            print("\n[FAIL] NOT PRODUCTION READY")


def main():
    checker = ProductionReadinessCheck()
    success = checker.check_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
