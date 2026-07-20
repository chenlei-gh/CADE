# Knowledge Base (CAA 领域知识)

CAA API 参考文档，按 **CAA 域 (Domain)** 组织。每篇文档含 YAML frontmatter，AI 通过 `catalog/index.yaml` 秒定位。

## 目录

| 域 | 目录 | 内容 |
|------|------|------|
| `mecmod` | `mecmod/` | Feature 模型、拓扑 |
| `part` | `part/` | Part Design: 圆角、孔、倒角 |
| `product` | `product/` | Assembly Design: 装配、约束 |
| `ui` | `ui/` | GUI: Dialog、布局、右键菜单 |
| `drawing` | `drawing/` | 工程图: 视图、标注、BOM |
| `surface` | `surface/` | GSD 曲面: 拉伸、扫掠、展平 |
| `fta` | `fta/` | FTA: 3D 标注、公差 |
| `infrastructure` | `infrastructure/` | CAA 基础设施: Selection、内存、命名规范 |
| `gaps` | `gaps/` | 知识缺口跟踪 |

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

## 知识文件编写规范

### 必须包含的章节

| 章节 | 要求 | 示例 |
|------|------|------|
| 标题 (H1) | 中文名 + 英文关键词 | `# Dialog (对话框)` |
| 概述 (1-3句) | 一句话说清这个 API 干什么 | `CATDlgDialog 是 CAA 对话框容器...` |
| 核心 API 表 | 至少 3 个关键接口的表格 | 接口名 \| 用途 |
| **代码示例** | ⚠️ 必须含可运行的 C++ 代码 | 创建、调用、清理的完整片段 |
| AI 生成规则 | checklist 格式 (`- [ ]`) | `- [ ] 继承 CATDlgDialog` |

### 代码示例规范

```cpp
// ✅ 正确：完整、可编译、含关键命名
CATDlgDialog *pDlg = new CATDlgDialog(
    "MyDlg",                // Dialog ID
    CATDlgWndModal,         // 模态
    CATDlgGridLayout        // Grid 布局
);

// ❌ 错误：只有函数签名，没有调用方式
HRESULT CreateDialog(CATDlgDialog **oDlg);
```

### 内容红线

| 禁止 | 原因 |
|------|------|
| 只写 API 列表没有代码 | AI 不理解怎么用 |
| 代码只有片段没有命名 | 变量名是 AI 理解意图的关键 |
| 用中文变量名/注释 | CAA 代码是英文环境 |
| 不写清理/析构逻辑 | CAA 内存泄漏是第一大 Bug 源 |

---

## CAADoc → CADE 知识沉淀流程

```
AI 从 CAADoc 学到新知识
    ↓
Step 0: 核实——用 `python tools/build_caadoc_index.py --query <name>` /
        `--search <pattern>` 确认涉及的接口/方法/框架名真实存在于
        CAADoc（cache 命中约 0.3 秒）。查无结果时不要直接当作
        "CAADoc 没收录"沉淀下来，先用 --search 排查是否拼写/别名
        问题；仍确认不存在则说明这是 AI 幻觉，不能沉淀。
        若 `--query` 输出中出现 `*** SDK/refman mismatch ***`，以它交叉
        比对结果里的 SDK 头文件方法列表为准（头文件是 refman 的生成源，
        比 refman htm 页面更权威）；枚举类型要确认具体枚举值真实存在，
        不要只凭接口名存在就假定枚举值存在。
        接口真实存在但不知道怎么获取实例时，改用 `--query <组件名>`
        反查该组件在“shipped .dic, ground truth”板块下实现了哪些接口
        （发布产品构建时生成的组件字典，覆盖全部实际交付框架，比
        CAADoc 自带的教学 `.dico` 权威得多），通常能直接找到真实的
        QueryInterface 入口。
    ↓
Step 1: 在 knowledge/gaps/ 创建 gap 文件（记录：来源URL、涉及API、建议路径）
    ↓
Step 2: 按本规范创建正式 knowledge/ 文件
    ├── YAML frontmatter（id、domain、keywords、apis）
    ├── 代码示例（完整的、可运行的 C++）
    └── AI 生成规则（checklist）
    ↓
Step 3: 更新 catalog/index.yaml 添加索引条目
    ↓
Step 4: 在 CHANGELOG.md 的 "📝 知识沉淀" 下记录：
    `- 新增 knowledge/[domain]/[file.md] — 来源: CAADoc/xxx`
    ↓
Step 5: 删除 knowledge/gaps/ 中的对应 gap 文件
    ↓
Step 6: 运行 `python tests/test_master.py --quick` 验证
```

### 判断是否需要创建 Pattern

仅当满足以下条件时，才同时创建 `patterns/` 文件：

- 涉及跨模块调用（至少 2 个模块）
- 包含完整的类层次结构
- 有清晰的适用场景描述

单个 API 用法 → 只建 knowledge。完整工作流模板 → 加建 pattern。

---

## 加载规则

AI 仅在需要时加载 knowledge 文件。关键词匹配 → Catalog 查 ID → 加载对应文件。SKILL.md 始终保持精简。

---

**最后更新**: 2026-07-10
