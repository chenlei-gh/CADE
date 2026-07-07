# Knowledge Base (CAA 领域知识)

CAA API 参考文档，按 **CAA 域 (Domain)** 组织——而非按几何概念。

每篇文档包含统一的 YAML frontmatter，AI 通过 `catalog/index.yaml` 秒定位。

## 目录

| 域 | 目录 | 内容 |
|------|------|------|
| `mecmod` | `mecmod/` | Feature 模型、拓扑 |
| `part` | `part/` | Part Design: 圆角、孔、倒角 |
| `product` | `product/` | Assembly Design: 装配、约束 |
| `ui` | `ui/` | GUI: Dialog、Toolbar |
| `infrastructure` | `infrastructure/` | CAA 基础设施: Selection |

## Metadata Schema

```yaml
---
id: part.fillet           # 全局唯一 ID
title: Edge Fillet        # 显示名称
category: knowledge       # knowledge | pattern | example
domain: part              # CAA 域
keywords: [...]           # 检索关键词
apis: [...]               # 涉及 API
requires: [...]           # 前置知识 ID
patterns: [...]           # 关联 Pattern ID
examples: [...]           # 关联 Example ID
release: [R19, R28]       # 适用版本
tags: [...]               # 通用标签
---
```

## 加载规则

AI 仅在需要时加载 knowledge 文件。关键词匹配 → Catalog 查 ID → 加载对应文件。SKILL.md 始终保持精简。
