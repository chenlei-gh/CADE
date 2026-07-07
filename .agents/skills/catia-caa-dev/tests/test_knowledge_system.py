#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Knowledge System Validation Test

验证知识系统的完整性：
1. Catalog 索引正确性
2. 所有 knowledge/pattern/example 文件的 metadata 一致性
3. ID 引用完整性（requires/patterns/examples）
4. 文件路径与 catalog 对应
5. YAML frontmatter 格式正确
"""

import os
import re
import sys
from pathlib import Path

# 添加父目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class KnowledgeSystemValidator:
    def __init__(self, root_path):
        self.root = Path(root_path)
        self.catalog_file = self.root / "catalog" / "index.yaml"
        self.knowledge_dir = self.root / "knowledge"
        self.patterns_dir = self.root / "patterns"
        self.examples_dir = self.root / "examples"

        self.all_ids = {}  # id -> file_path
        self.errors = []
        self.warnings = []

    def validate_all(self):
        """执行所有验证"""
        print("=" * 70)
        print("  Knowledge System Validation")
        print("=" * 70)

        # 1. 验证 Catalog 存在
        if not self.catalog_file.exists():
            self.errors.append(f"Catalog not found: {self.catalog_file}")
            return False

        print(f"\n[OK] Catalog found: {self.catalog_file}")

        # 2. 收集所有文件的 metadata
        self.collect_all_metadata()

        # 3. 验证 metadata 一致性
        self.validate_metadata_schema()

        # 4. 验证 ID 引用完整性
        self.validate_id_references()

        # 5. 验证文件路径规范
        self.validate_file_paths()

        # 6. 统计
        self.print_summary()

        return len(self.errors) == 0

    def collect_all_metadata(self):
        """收集所有 .md 文件的 metadata"""
        print("\n" + "=" * 70)
        print("  Collecting Metadata")
        print("=" * 70)

        count = 0
        for category_dir in [self.knowledge_dir, self.patterns_dir, self.examples_dir]:
            if not category_dir.exists():
                continue

            for md_file in category_dir.rglob("*.md"):
                if md_file.name == "README.md":
                    continue

                metadata = self.extract_metadata(md_file)
                if metadata:
                    file_id = metadata.get("id")
                    if file_id:
                        if file_id in self.all_ids:
                            self.errors.append(
                                f"Duplicate ID '{file_id}': {md_file} and {self.all_ids[file_id]}"
                            )
                        else:
                            self.all_ids[file_id] = {
                                "path": md_file,
                                "metadata": metadata,
                            }
                            count += 1
                    else:
                        self.errors.append(f"Missing 'id' in {md_file}")

        print(f"\n[OK] Collected {count} files with metadata")
        print(
            f"  Knowledge: {len(list(self.knowledge_dir.rglob('*.md'))) - 1}"
        )  # -1 for README
        print(f"  Patterns:  {len(list(self.patterns_dir.rglob('*.md'))) - 1}")
        print(f"  Examples:  {len(list(self.examples_dir.rglob('*.md'))) - 1}")

    def extract_metadata(self, file_path):
        """提取 YAML frontmatter (使用简单解析，不依赖 yaml 库)"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 匹配 YAML frontmatter
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            if not match:
                self.warnings.append(f"No frontmatter in {file_path}")
                return None

            yaml_text = match.group(1)
            metadata = {}

            # 简单解析 YAML (key: value 或 key: [list])
            for line in yaml_text.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if ":" not in line:
                    continue

                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                # 解析列表 [a, b, c]
                if value.startswith("[") and value.endswith("]"):
                    items = value[1:-1].split(",")
                    metadata[key] = [item.strip() for item in items if item.strip()]
                else:
                    metadata[key] = value

            return metadata
        except Exception as e:
            self.errors.append(f"Failed to parse {file_path}: {e}")
            return None

    def validate_metadata_schema(self):
        """验证 metadata schema 一致性"""
        print("\n" + "=" * 70)
        print("  Validating Metadata Schema")
        print("=" * 70)

        required_fields = [
            "id",
            "title",
            "category",
            "domain",
            "keywords",
            "apis",
            "release",
            "tags",
        ]

        for file_id, data in self.all_ids.items():
            metadata = data["metadata"]
            file_path = data["path"]

            # 检查必填字段
            for field in required_fields:
                if field not in metadata:
                    self.errors.append(
                        f"Missing field '{field}' in {file_id} ({file_path.name})"
                    )

            # 检查 category 是否合法
            category = metadata.get("category")
            if category not in ["knowledge", "pattern", "example"]:
                self.errors.append(f"Invalid category '{category}' in {file_id}")

            # 检查 keywords 是否是列表
            if "keywords" in metadata and not isinstance(metadata["keywords"], list):
                self.errors.append(f"'keywords' should be list in {file_id}")

            # 检查 apis 是否是列表
            if "apis" in metadata and not isinstance(metadata["apis"], list):
                self.errors.append(f"'apis' should be list in {file_id}")

            # 检查 release 是否是列表
            if "release" in metadata and not isinstance(metadata["release"], list):
                self.errors.append(f"'release' should be list in {file_id}")

        if not self.errors:
            print(f"\n[OK] All {len(self.all_ids)} files have valid metadata schema")

    def validate_id_references(self):
        """验证 ID 引用完整性"""
        print("\n" + "=" * 70)
        print("  Validating ID References")
        print("=" * 70)

        ref_count = 0
        for file_id, data in self.all_ids.items():
            metadata = data["metadata"]
            file_path = data["path"]

            # 检查 requires
            requires = metadata.get("requires", [])
            if requires and not isinstance(requires, list):
                requires = [requires]

            for req_id in requires:
                if req_id not in self.all_ids:
                    self.errors.append(f"Unknown 'requires' ID '{req_id}' in {file_id}")
                ref_count += 1

            # 检查 patterns
            patterns = metadata.get("patterns", [])
            if patterns and not isinstance(patterns, list):
                patterns = [patterns]

            for pat_id in patterns:
                if pat_id and pat_id not in self.all_ids:
                    self.warnings.append(
                        f"Unknown 'patterns' ID '{pat_id}' in {file_id}"
                    )
                ref_count += 1

            # 检查 examples
            examples = metadata.get("examples", [])
            if examples and not isinstance(examples, list):
                examples = [examples]

            for ex_id in examples:
                if ex_id and ex_id not in self.all_ids:
                    self.warnings.append(
                        f"Unknown 'examples' ID '{ex_id}' in {file_id}"
                    )
                ref_count += 1

        print(f"\n[OK] Validated {ref_count} ID references")

    def validate_file_paths(self):
        """验证文件路径规范"""
        print("\n" + "=" * 70)
        print("  Validating File Paths")
        print("=" * 70)

        for file_id, data in self.all_ids.items():
            metadata = data["metadata"]
            file_path = data["path"]
            category = metadata.get("category")
            domain = metadata.get("domain")

            # 验证 category 和实际路径匹配
            if category == "knowledge" and "knowledge" not in str(file_path):
                self.errors.append(f"Category 'knowledge' but path is {file_path}")
            elif category == "pattern" and "patterns" not in str(file_path):
                self.errors.append(f"Category 'pattern' but path is {file_path}")
            elif category == "example" and "examples" not in str(file_path):
                self.errors.append(f"Category 'example' but path is {file_path}")

            # 验证 domain 和父目录匹配
            if domain and category != "example":
                if domain not in str(file_path.parent):
                    self.warnings.append(
                        f"Domain '{domain}' but parent is {file_path.parent.name} in {file_id}"
                    )

        print(f"\n[OK] File paths validated")

    def print_summary(self):
        """打印汇总"""
        print("\n" + "=" * 70)
        print("  Summary")
        print("=" * 70)

        print(f"\nTotal files:  {len(self.all_ids)}")
        print(f"Errors:       {len(self.errors)}")
        print(f"Warnings:     {len(self.warnings)}")

        if self.errors:
            print("\n[ERRORS]:")
            for err in self.errors:
                print(f"  - {err}")

        if self.warnings:
            print("\n[WARNINGS]:")
            for warn in self.warnings[:10]:  # 只显示前 10 个
                print(f"  - {warn}")
            if len(self.warnings) > 10:
                print(f"  ... and {len(self.warnings) - 10} more")

        if not self.errors:
            print("\n[PASS] ALL CHECKS PASSED")
        else:
            print("\n[FAIL] VALIDATION FAILED")


def main():
    # 获取项目根目录
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent

    validator = KnowledgeSystemValidator(root_dir)
    success = validator.validate_all()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
