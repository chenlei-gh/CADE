#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CADE System Health Check — Full System Validation

全面检查 CADE 系统的健康状态：
- 核心模块完整性
- 知识系统完整性
- 测试覆盖率
- 文档完整性
- 配置正确性
"""

import os
import sys
from pathlib import Path


class SystemHealthCheck:
    def __init__(self):
        self.root = Path(__file__).parent.parent
        self.errors = []
        self.warnings = []
        self.stats = {}

    def check_all(self):
        """执行所有健康检查"""
        print("=" * 70)
        print("  CADE System Health Check")
        print("=" * 70)

        self.check_core_modules()
        self.check_knowledge_system()
        self.check_tests()
        self.check_documentation()
        self.check_configuration()

        self.print_summary()

        return len(self.errors) == 0

    def check_core_modules(self):
        """检查核心 Python 模块"""
        print("\n[1/5] Checking Core Modules...")

        required_modules = [
            "skills/actions.py",
            "skills/specification.py",
            "skills/diagnostics.py",
            "skills/refactor.py",
            "skills/generator.py",
            "skills/meta_model.py",
            "skills/analyzer.py",
            "skills/changeset.py",
            "skills/backup.py",
            "skills/env.py",
            "skills/parser.py",
            "skills/utils.py",
            "skills/build.py",
            "skills/run.py",
            "skills/clean.py",
            "skills/workspace.py",
            "skills/runtime_view.py",
        ]

        for module in required_modules:
            path = self.root / module
            if not path.exists():
                self.errors.append(f"Missing core module: {module}")

        self.stats["core_modules"] = len(required_modules)
        print(f"  [OK] {len(required_modules)} core modules verified")

    def check_knowledge_system(self):
        """检查知识系统"""
        print("\n[2/5] Checking Knowledge System...")

        # Catalog
        catalog = self.root / "catalog" / "index.yaml"
        if not catalog.exists():
            self.errors.append("Missing catalog/index.yaml")

        # Knowledge files
        knowledge_dir = self.root / "knowledge"
        knowledge_files = list(knowledge_dir.rglob("*.md"))
        knowledge_files = [f for f in knowledge_files if f.name != "README.md"]

        # Pattern files
        patterns_dir = self.root / "patterns"
        pattern_files = list(patterns_dir.rglob("*.md"))
        pattern_files = [f for f in pattern_files if f.name != "README.md"]

        # Example files
        examples_dir = self.root / "examples"
        example_files = list(examples_dir.rglob("*.md"))
        example_files = [f for f in example_files if f.name != "README.md"]

        total = len(knowledge_files) + len(pattern_files) + len(example_files)

        self.stats["knowledge_files"] = len(knowledge_files)
        self.stats["pattern_files"] = len(pattern_files)
        self.stats["example_files"] = len(example_files)

        print(
            f"  [OK] Knowledge: {len(knowledge_files)}, Patterns: {len(pattern_files)}, Examples: {len(example_files)}"
        )

        if total < 20:
                    self.warnings.append(f"Expected 20+ knowledge files, found {total}")

    def check_tests(self):
        """检查测试文件"""
        print("\n[3/5] Checking Tests...")

        test_files = list((self.root / "tests").glob("test_*.py"))

        required_tests = [
            "test_master.py",
            "test_full_integration.py",
            "test_phase1_enhancements.py",
            "test_phase2_intents.py",
            "test_phase3_rollback.py",
            "test_phase4_enhanced.py",
            "test_specification.py",
            "test_diagnostics.py",
            "test_fixplan_executor.py",
            "test_refactor.py",
            "test_e2e_workflow.py",
            "test_l4_architecture.py",
            "test_l5_semantic.py",
            "test_l6_fault_injection.py",
            "test_knowledge_system.py",
            "test_build_and_run.py",
            "test_skill_ai_coordination.py",
            "test_complete_system.py",
                        "test_cross_reference.py",
                        "test_token_optimizer.py",
                        "test_caa_structure.py",
                                                "test_intent_planner.py",
                                                "test_ai_integration.py",
                                                "test_token_audit.py",
                                            ]

        for test in required_tests:
            if not (self.root / "tests" / test).exists():
                self.errors.append(f"Missing test: {test}")

        self.stats["test_files"] = len(test_files)
        print(f"  [OK] {len(test_files)} test files found")

    def check_documentation(self):
        """检查文档"""
        print("\n[4/5] Checking Documentation...")

        required_docs = [
            "README.md",
            "SKILL.md",
            "CHANGELOG.md",
            "LICENSE",
            "docs/KNOWLEDGE_SYSTEM_ARCHITECTURE.md",
        ]

        # README.md is at CADE root, not catia-caa-dev
        cade_root = self.root.parent.parent.parent
        for doc in required_docs:
            check_path = cade_root if doc == "README.md" else self.root
            if not (check_path / doc).exists():
                self.errors.append(f"Missing documentation: {doc}")

        self.stats["docs"] = len(required_docs)
        print(f"  [OK] {len(required_docs)} core documents verified")

    def check_configuration(self):
        """检查配置文件"""
        print("\n[5/5] Checking Configuration...")

        config_files = [
            ".gitignore",
        ]

        for cfg in config_files:
            if not (self.root / cfg).exists():
                self.warnings.append(f"Missing config: {cfg}")

        # Check templates
        templates_dir = self.root / "templates"
        if not templates_dir.exists():
            self.errors.append("Missing templates directory")
        else:
            template_count = len(list(templates_dir.iterdir()))
            self.stats["templates"] = template_count
            print(f"  [OK] {template_count} template types found")

    def print_summary(self):
        """打印汇总"""
        print("\n" + "=" * 70)
        print("  Summary")
        print("=" * 70)

        print(f"\nCore Modules:     {self.stats.get('core_modules', 0)}")
        print(f"Knowledge Files:  {self.stats.get('knowledge_files', 0)}")
        print(f"Pattern Files:    {self.stats.get('pattern_files', 0)}")
        print(f"Example Files:    {self.stats.get('example_files', 0)}")
        print(f"Test Files:       {self.stats.get('test_files', 0)}")
        print(f"Templates:        {self.stats.get('templates', 0)}")
        print(f"Documentation:    {self.stats.get('docs', 0)}")

        print(f"\nErrors:           {len(self.errors)}")
        print(f"Warnings:         {len(self.warnings)}")

        if self.errors:
            print("\n[ERRORS]:")
            for err in self.errors:
                print(f"  - {err}")

        if self.warnings:
            print("\n[WARNINGS]:")
            for warn in self.warnings:
                print(f"  - {warn}")

        if not self.errors:
            print("\n[PASS] SYSTEM HEALTHY")
        else:
            print("\n[FAIL] SYSTEM CHECK FAILED")


def main():
    checker = SystemHealthCheck()
    success = checker.check_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
