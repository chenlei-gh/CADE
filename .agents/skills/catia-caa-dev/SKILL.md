---
name: catia-caa-dev
description: "CATIA CAA V5 Development Engine (CADE) v3.2.1 — Kernel 架构（3 Mode: develop/analyze/repair）、Generate → Build（tck_init→tck_profile→mkinit→mkGetPreq→mkmk）→ Run（mkrun）闭环。Rich Domain Model（10 实体）、依赖图分析、级联删除、操作回滚、智能推荐、Diagnostics+FixPlan+RepairLoop+AutoSuggest、Refactor、静态代码验证。动态 CATIA 检测（零硬编码）、Prerequisites 管理。CAA 知识系统（29K+14P+13Capability+15Playbook+148Framework+6Philosophy+3Failure+3DecisionTree），107几何图标+RGBA多色、75模板(16类型)、39测试套件、cade dev一键闭环。"
triggers:
  - CAA component
  - CATIA component
  - CAA interface
  - CAA framework
  - CAA module
  - CAA dialog
  - CATIA dialog
  - CATIA UI
  - CAA drawing
  - CATIA drawing
  - engineering drawing
  - 工程图
  - 图纸
  - CAA surface
  - GSD
  - Generative Shape Design
  - surface flatten
  - 曲面
  - 展平
  - FTA
  - 3D annotation
  - PMI
  - 3D 标注
  - tolerance
  - 公差
  - context menu
  - 右键菜单
  - right click
  - CATIContextualMenu
  - CATCmdStarter
  - DataExtension
  - CAA command
  - CATIA command
  - CAA workbench
  - CATIA workbench
  - CAA feature
  - CATIA feature
  - compile CAA
  - build CAA
  - run CATIA
  - start CATIA
  - stop CATIA
  - check workspace
  - analyze workspace
  - list modules
  - list commands
  - create command
  - delete command
  - preview changes
  - 创建CATIA组件
  - 创建对话框
  - 创建命令
  - 创建工作台
  - 编译CAA模块
  - 运行CATIA
  - 分析工作区
  - 列出模块
  - 列出命令
  - create CAA
  - generate CAA
  - mkmk
  - incremental build
  - full build
  - clean build
  - mkmk build
  - compile workspace
  - create runtime view
  - Runtime View
  - workspace info
  - workspace where
  - mkwhereami
  - dependency analysis
  - impact analysis
  - prerequisite
  - mkGetPreq
  - identity card
  - mkCreateIC
  - generate doc
  - mkmancpp
  - export symbols
  - Framework update
  - Framework copy
  - Framework remove
  - build with threads
  - mkmk -j
  - CNEXT
  - CNEXT -macro
  - CNEXT -batch
  - run macro
  - execute macro
  - batch mode
  - 编译
  - 增量编译
  - 全量编译
  - 清理编译
  - 创建RuntimeView
  - 查看工作区
  - 依赖分析
  - 创建IdentityCard
  - 启动CATIA
  - 停止CATIA
  - 运行宏
  - Specification
  - CommandSpec
  - FeatureSpec
  - generate code
  - generator
  - 代码生成
  - 规范
  - 契约
  - diagnose
  - diagnostics
  - FixPlan
  - fix plan
  - auto fix
  - rename command
  - rename interface
  - move command
  - refactor
  - 诊断
  - 修复方案
  - 重命名
  - 重构
  - setup environment
  - setup workspace
  - detect CATIA
  - configure workspace
  - CATIA detection
  - manage prerequisites
  - add prerequisite
  - remove prerequisite
  - validate prerequisites
  - circular dependency
  - prerequisite manager
  - 环境配置
  - 检测CATIA
  - 配置工作区
  - 依赖管理
  - 循环依赖
  - get dependencies
  - check dependencies
  - visualize dependencies
  - dependency graph
  - validate workspace
  - find orphaned
  - cascade delete
  - create feature
  - create extension
  - data extension
  - expose service
  - suggest next
  - recommend
  - rollback
  - undo
  - list backups
  - restore
  - 创建Feature
  - 创建扩展
  - 暴露接口
  - 回滚
  - 撤销
  - 查询依赖
  - 查询依赖
  - 依赖关系
  - 可视化依赖
  - 验证工作区
  - 级联删除
  - CAA knowledge
  - CAA API reference
  - CAA API doc
  - CAA pattern
  - CAA example
  - CAA demo
  - fillet check
  - hole check
  - chamfer check
  - geometry analyzer
  - rule checker
  - result dialog
  - batch process
  - feature traversal
  - feature visitor
  - 圆角检查
  - 孔检查
  - 倒角检查
  - 几何分析
  - CAA知识库
  - CAA范例
  - CAA模式
  - 开发模式
  - 批量处理
  - CAA naming convention
  - CAA lifecycle
  - CAA error handling
  - CAA memory management
  - CAA dialog layout
  - CAA dialog widget
  - CAA event handling
  - CAA workbench pattern
  - CAA state command
  - CAA feature pattern
  - CAA imakefile
  - CAA code style
  - CAA 命名规范
  - CAA 生命周期
  - CAA 错误处理
  - CAA 内存管理
  - CAA 对话框布局
  - CAA 事件处理
  - CAA 工作台
  - CAA Feature 开发
  - CAA 编译链接
---

# CATIA CAA V5 智能开发助手

## 🎯 核心特性

**版本**: 3.2.1
**状态**: ✅ 活跃开发  
**测试**: 39 套件（快速模式执行 38 套，跳过 1 套 CATIA 生命周期测试）

这是一个**智能的 CAA 开发引擎（Development Kernel）**，将模糊的开发需求，经过需求分析、规划、知识推理和验证，稳定地转化为可执行实现。

### 🏗️ Kernel 架构（v3.0）

```text
AI 只知道 3 个 Mode:

  develop()   — 创建/生成 (Command — 可能修改文件)
  analyze()   — 查询/诊断 (Query   — 只读)
  repair()    — 修复/重构 (Command — 带安全网)
         │
         ▼
  ┌──────────────────────────────┐
  │       CADE Kernel             │
  │   (AI 完全不可见的内部)         │
  │                                │
  │  Requirement → Intent → Plan   │
  │       │           │       │    │
  │  Clarify    Intent   Planner   │
  │       │     Models  +Optimize  │
  │  Decompose     │       │       │
  │       │        │       │       │
  │       └────────┼───────┘       │
  │                ↓               │
  │        Capability→Playbook     │
  │                ↓               │
  │        Knowledge→Generator     │
  │                ↓               │
  │        CodeVerifier→Repair     │
  └──────────────────────────────┘
```

### 🤖 给 AI 的提示（最高优先级）

> **你是 CADE 的主要使用者。请遵循以下规则以获得最佳效果：**

| 规则 | 说明 |
|------|------|
| 🎯 **只有 3 个工具** | CADE v3.0 只有三个工具：`develop`（创建/生成）、`analyze`（查询/诊断）、`repair`（修复/重构）。永远不需要知道内部实现。 |
| 🔌 **用 MCP 调用** | 所有 CADE 功能通过 MCP 工具调用，不要用 CLI。响应已自动 Token 优化。 |
| 📊 **信 status 不信 output** | API 返回 `{"status": "ok", "error_count": 0}` 就够了，忽略 `output`/`stderr` 字段。 |
| 🆕 **模糊需求用 develop()** | 用户说"我想做一个..."、"能不能..."时直接调用 `develop()`。Kernel 自动做需求澄清 → 分解增强（Playbook/Capability/依赖）→ 规划 → 生成 → **自动写入磁盘（auto-apply）** → 代码验证。如果返回 `needs_clarification`，把问题展示给用户。 |
| ✅ **develop() 一次调用即完成，不要等"确认"** | `develop()` 会自动把生成结果写入磁盘并自带备份（`result.apply_result.rollback_id`），不存在"生成预览 → 再手动 apply"的第二步。返回 `status: "ok"` 就代表文件已经真实存在；只有意图无法解析（如模块不存在）才会停在 `status: "pending"`，此时也没有文件被写入。需要撤销时用 `repair()` 的 rollback，而不是去找一个不存在的 confirm 接口。 |
| 🔍 **只读操作用 analyze()** | 所有查询、诊断、分析用 `analyze()`。它永不会修改文件，无需确认。 |
| 🔧 **修复用 repair()** | 修复诊断问题、重构（重命名/移动）、回滚用 `repair()`。Kernel 内部运行 diagnose → fix → verify 最多重试 3 次。 |
| ⚡ **永远不需要判断"走哪个"** | 用户说"创建/生成/做一个" → `develop`；"检查/分析/诊断" → `analyze`；"修复/改名/回滚" → `repair`。基于自然语言的动词分类，不需要思考。 |
| 📖 **Framework → CAADoc（不是直接搜）** | knowledge/ 没有时，先查 `knowledge/frameworks/` 定位属哪个框架 → 再精准打开 `<CATIA_INSTALL>/CAADoc/` 对应页面。不要跳过 Framework 直接全文搜 CAADoc。 |
| 📝 **CAADoc 洞察沉淀** | 用 CAADoc 学到**踩坑经验/跨 API 组合/非文档化的行为**时，创建 knowledge/ 文件沉淀。纯 API 签名查询不需要沉淀——下次用 Framework 索引秒查。 |
| 🔎 **核实 API 真实性先用索引工具** | 怀疑 playbooks/patterns/knowledge 里某接口、方法、框架名是否真实存在（尤其是“看起来很统一”的 Factory/Manager 名字，经常是虚构）时，先跑 `python tools/build_caadoc_index.py --query <name>` 或 `--search <pattern>`（cache 命中约 0.3 秒，比手动打开 CAADoc 页面或 `grep` 全量扫描快得多；连续核对多个名字用 `--repl` 交互模式，避免反复启动进程）。只有索引覆盖不到的语义性问题（官方样例怎么组合调用、设计意图是什么）才需要再去翻 `Doc/generated/refman/` 页面或 `.cpp` 样例代码。索引没查到不等于 100% 不存在（可能是拼写变体或索引未覆盖的老旧接口），但命中即可作为“确实存在”的强证据。 |
| 📄 **批量核实整份文档用 `--check-file`** | 需要一次性核实某个 playbook/pattern/knowledge 文件里所有 API 时，不要逐个手敲 `--query`：跑 `python tools/build_caadoc_index.py --check-file <path>`，它会自动扫描文件里所有 ```cpp 代码块中的 `CAT*` 类型名和 `->`/`::` 方法调用，一次调用只打印疑点（SUSPECT），比人工逐个核对快一个数量级。`--query`/`--check-file` 都支持 `--quiet` 输出一行式 FOUND/NOT-FOUND/MISMATCH verdict，适合批量核对多个名字时减少输出体积。局限：只扫描代码块，不扫描正文反引号提及的 API 名；枚举成员/类型常量可能被误报，需人工用 `--query` 复核。 |
| 🥇 **冲突时信 SDK 头文件** | `--query` 会自动扫描 CATIA 安装目录下所有 Framework/PublicInterfaces 的 .h 头文件，把 refman 的方法列表与头文件的方法列表交叉比对，不一致时打印 `SDK/refman mismatch` 提示。头文件是 refman 的生成源，比 refman htm 页面更权威（refman 存在生成缺失），看到 mismatch 提示时以头文件为准。同一命令还会展示查询名命中的枚举值列表及其行内注释，用于核实枚举成员是否真实存在（refman 枚举页经常遗漏这些信息）。 |
| 🏆 **查“组件实现了哪些接口”信随产品发布的字典** | `--query <接口名>` 会自动扫描 CATIA 安装目录下 `<arch>/code/dictionary/*.dic`（比 CAADoc 自带的 44 个教学 `.dico` 大得多，约 885 个文件/7.3 万条），列出真正发布产品里哪个组件真实实现了该接口，标记为 "ground truth"。遇到“接口真实存在但不知道怎么获取实例”的情况时，先用它反查实现组件，往往能发现真实获取方式是对该组件做 `QueryInterface`（如 `CATTPSSet` 实现了 `CATITPSFactoryElementary`/`CATITPSCaptureFactory`/`CATITPSViewFactory` 三个工厂接口，都需对 Set 实例 QI 获取）。 |
| 📋 **手写知识文档分可信度，先查审计表** | `capabilities/`、`knowledge/`、`patterns/`、`playbooks/` 里的手写教学文档**不是同等可信**——部分已用上述索引工具逐条核实过虚构 API，部分尚未核实。生成代码前先查 [`KNOWLEDGE_AUDIT_STATUS.md`](KNOWLEDGE_AUDIT_STATUS.md)：命中“已核实清单”可直接参考；命中“未核实清单”（`patterns/` 目录多数文件、部分 `knowledge/mecmod|philosophy|surface|ui|infrastructure|failure_patterns`）必须先用 `--query`/`--check-file` 核实关键 API 再使用，不要直接照抄示例代码。 |
| 🧠 **跨项目记忆库** | 遇到疑难问题（编译、运行时、工具链），先查 `D:/Vault/Memory/BestPractices.md`。症状速查表见下方 **故障排查** 章节。 |

### ✨ 核心优势

1. **Kernel 架构** — develop/analyze/repair 三模式，AI 只需选模式，内核自动调度
2. **意图驱动** — AI 只需表达意图，Planner + Capability/Playbook 自动规划步骤
3. **需求分析** — 模糊需求自动澄清，决策树引导，生成结构化 RequirementDocument
4. **Token 优化** — MCP 响应自动压缩，平均节省 50% token，关键信息不丢
5. **安全操作** — 预览→确认→应用→回滚，全程可控
6. **代码验证** — 生成后自动静态检查（宏/头文件/命名规范），无需 mkmk
7. **自动修复** — Repair Loop：诊断→修复→验证，最多 3 次重试
8. **高性能** — 模板生成约50ms，比 RADE 工具快 100 倍
9. **完整测试** — 39 套件，快速模式执行 38 套
10. **依赖图管理** — 完整的实体关系图和 Mermaid 可视化
11. **知识体系** — Capability→Playbook→Knowledge→Philosophy→Framework→CAADoc + Failure Patterns + Decision Trees

### 📦 支持的功能

**v3.0 核心**
- ✅ **Kernel 三模式** — develop / analyze / repair
- ✅ **需求澄清** — 模糊需求 → 决策树 → 结构化需求文档
- ✅ **需求分解** — 决策映射到 Playbook/Capability/依赖，自动增强生成代码
- ✅ **静态代码验证** — 生成后自动检查宏/头文件/命名/格式
- ✅ **修复闭环** — 诊断 → 修复 → 验证，最多 3 次重试
- ✅ **知识检索** — analyze() 自动搜索 CAA API/Pattern/Playbook
- ✅ **反馈学习** — 失败模式记录 + 模式检测 + 自动建议 Playbook
- ✅ **全工具覆盖** — 41 个旧工具全部通过 3-mode 接口可达

**核心工作流**
- ✅ 工作区分析（Framework、Module、Command 检测）
- ✅ 组件生成（17+ 模板类型）
- ✅ 编译管理（mkmk）
- ✅ 运行时执行（CNEXT）
- ✅ 变更预览和回滚
- ✅ **依赖图管理**（Phase 1 新增）
- ✅ **级联删除检测**（Phase 1 新增）

**智能查询**
- ✅ 列出所有 Framework
- ✅ 列出所有 Module
- ✅ 列出所有 Command
- ✅ 列出所有 Workbench
- ✅ 列出所有 Interface
- ✅ **查询实体依赖关系**（Phase 1 新增）
- ✅ **查询被依赖关系**（Phase 1 新增）
- ✅ **可视化依赖图**（Phase 1 新增）
- ✅ **验证工作区完整性**（Phase 1 新增）
- ✅ **查找孤立文件**（Phase 1 新增）

**创建操作**
- ✅ 创建 Framework
- ✅ 创建 Module
- ✅ 创建 Command（简单/状态）
- ✅ 创建 Workbench
- ✅ 创建 Dialog
- ✅ 创建 Interface
- ✅ 创建 Component（支持 BOA）
- ✅ 创建 Feature（含 Factory）
- ✅ 创建 Extension（数据扩展）
- ✅ 添加命令到工作台
- ✅ **一站式命令创建**（Phase 2 新增）
- ✅ **暴露服务接口**（Phase 2 新增）

**删除操作**
- ✅ 删除 Command（级联删除所有关联文件）
- ✅ 删除 Module
- ✅ 自动清理依赖
- ✅ **破坏性依赖检测**（Phase 1 新增）

**回滚操作**
- ✅ **操作回滚**（Phase 3 新增）
- ✅ **列出回滚点**（Phase 3 新增）
- ✅ **清理旧备份**（Phase 3 新增）

**智能推荐**
- ✅ **下一步操作建议**（Phase 4 新增）
- ✅ **工作区健康分析**（Phase 4 新增）

---

## 🚀 快速开始

### 推荐方式：使用 Intent Layer（一次调用）

```python
from intents import create_executable_command
from actions import ActionContext

ctx = ActionContext("D:/workspace")

# 一次调用创建完整命令（含对话框 + 工作台）
result = create_executable_command(
    ctx,
    name="MyCommand",
    module="MyModule.m",
    with_dialog=True,
    add_to_workbench="MyWorkbench"
)

# 预览将要创建/修改的文件
print(result["preview"])

# 确认后应用
# result["changeset"] 可在审查后 apply
```

### 底层方式：使用 Actions（精细控制）

```python
from actions import ActionContext, analyze_workspace, list_modules

ctx = ActionContext("D:/workspace")
result = analyze_workspace(ctx)

# 返回:
{
  "status": "ok",
  "summary": {
    "frameworks": [
      {
        "name": "TestFramework.edu",
        "modules": [
          {"name": "TestModule.m", "commands": 5}
        ]
      }
    ]
  }
}
```

### 2. 列出所有模块

```python
from actions import list_modules

result = list_modules(ctx)

# 返回:
{
  "status": "ok",
  "modules": [
    {"name": "TestModule.m", "framework": "TestFramework.edu", "commands": 5}
  ],
  "count": 1
}
```

### 3. 创建命令（预览模式，仅适用于直接调用 `actions.py` 底层 API）

> ⚠️ **这是底层 `actions.py` 函数的行为，不是 `develop()` 的行为。**
> 如果你通过 MCP/CLI 的 `develop()`（推荐路径）调用，Kernel 会在返回前自动完成 `ChangeSet.apply()`，最终 `status` 是 `"ok"` 而不是 `"pending"`，文件已经写入磁盘。
> 下面的 `pending`/`changeset` 返回值只会在你绕过 Kernel、直接调用 `actions.create_command()` 本身时出现（如需手动应用，参考本文件后面的 Python API 章节）。

```python
from actions import create_command

result = create_command(
    ctx,
    name="MyCommand",
    module="TestModule.m",
    framework="TestFramework"
)

# 返回:
{
  "status": "pending",
  "preview": {
    "will_create": [
      "TestModule.m/src/MyCommand.cpp",
      "TestModule.m/LocalInterfaces/MyCommand.h",
      "TestModule.m/src/MyCommandHeader.cpp",
      "TestModule.m/CNext/resources/msgcatalog/MyCommandHeader.CATNls"
    ],
    "will_modify": [
      "TestModule.m/Imakefile.mk"
    ]
  },
  "changeset": {...}
}

# 手动应用（仅在直接调用 actions.py 时需要；develop() 已自动完成这一步）：
from changeset import ChangeSet
cs = ChangeSet.from_dict(result["changeset"])
apply_result = cs.apply(workspace_root=ctx.workspace_root)
```

### 4. 删除命令（级联删除）

```python
from actions import delete_command

result = delete_command(
    ctx,
    name="MyCommand",
    module="TestModule.m",
    framework="TestFramework"
)

# 自动删除:
# - MyCommand.cpp
# - MyCommand.h
# - MyCommandHeader.cpp
# - Catalog 条目
# - NLS 资源
# - Icon 文件
# - Imakefile 引用
```

---

## 📚 支持的模板类型 (17+)

### 核心结构
- **Framework** - 项目根结构
- **Module** - 编译单元

### 命令
- **Command** - 普通命令
- **StateCommand** - 多步交互命令
- **CommandHeader** - 命令声明

### 工作台
- **Workbench** - 工作台
- **WorkbenchAddin** - 工作台扩展

### 界面
- **Dialog** - 对话框

### 组件
- **Component** - CAA 组件（支持 BOA/TIE）
- **Interface** - C++ 接口
- **IDLInterface** - IDL 接口
### 对象建模
- **Feature** - 特征
- **Specification** - 规格对象

### 扩展
- **Extension** - 数据扩展
- **BehaviorExtension** - 行为扩展

### 工具类
- **Class** - 普通 C++ 类
- **Utility** - 工具类

### 测试
- **TestCase** - CAA 测试用例
- **XmlTestCase** - XML 数据驱动测试

### 插件
- **EventListener** (CATEventSubscriber) - 事件订阅器

### 资源（自动生成）
- **Catalog** - 命令注册
- **Dictionary** - 组件注册
- **IdentityCard** - Framework 信息
- **NLS** - 国际化资源
- **Icon** - 图标资源
- **Imakefile** - 编译配置

---

## 🔌 三接口协作

CADE 提供三种接口，各有定位，互补不重叠：

| 接口 | 谁用 | 何时用 | Token | 示例 |
|------|------|--------|-------|------|
| **MCP Server** | 🤖 AI Agent | **首选**。每次调用自动优化响应 | 🟢 低 | `analyze_workspace(ws)` |
| **CLI (cade.py)** | 👤 开发者 / CI | 终端操作、脚本、流水线 | 🟡 中 | `cade build --full` |
| **Python API** | 🛠 高级脚本 | 自定义自动化、批量处理 | 🔴 高 | `from build import full_build` |

### 调用优先级

```
AI Agent 有需求
    ↓
① MCP Server — 首选（自动 Token 优化 + 错误格式化）
    ↓ (如果没有 MCP)
② CLI — 使用 --json 输出
    ↓ (如果需要自定义逻辑)
③ Python API — 直接调用
```

### 互补关系

| 场景 | 用这个 | 不用那个 | 原因 |
|------|--------|---------|------|
| AI 创建命令 | MCP | CLI | MCP 响应已优化，CLI 输出冗长 |
| CI/CD 编译 | CLI `--json` | Python API | CLI 一行搞定，不用写脚本 |
| 批量生成 50 个命令 | Python API | MCP | 循环调 MCP 太慢，import 直接循环 |
| 调试一个错误 | CLI | MCP | 开发者需要看完整输出 |
| 重构影响分析 | Python `intent.impact` | MCP | 需要编程式评估结果 |

> ⚠️ **AI Agent 永远优先用 MCP**。CLI 和 Python API 是给人类和脚本用的。

---

### 🏗️ 架构设计

### 五层知识体系

```
用户需求
    │
    ▼
🎯 Capability (能力层)      ← AI 入口：识别"要做什么"
    │
    ▼
📋 Playbook (方案层)         ← 成熟方案："怎么完成这件事"
    │
    ▼
📚 Knowledge (知识层)        ← API 代码："具体怎么写"
    │
    ▼
🗂 Framework (导航层)        ← CAADoc 定位："属于哪个框架"
    │
    ▼
📖 CAADoc (官方文档)         ← 查缺补漏
```

### 架构层次

```
AI / CLI / MCP
     │
     ▼
API Layer (intents.py + actions.py)
     │
     ▼
Development Engine (Intent → Spec → Generator)
     │
     ▼
Validation + Specification
     │
     ▼
Generator (generator.py + templates/)
     │
     ▼
Writer (changeset.py)
     │
     ▼
Workspace Repository (analyzer.py + meta_model.py)
     │
     ▼
Semantic Analyzer + Diagnostics
     │
     ▼
Build Engine (build.py) + Runtime Engine (run.py)
```

### 10 条设计原则

1. **Everything is Object** — 每个 CAA 实体都是 Rich Domain Object，知道自己的一切
2. **Everything is Semantic** — 不解析字符串，理解 CAA 语义
3. **AI Never Touch Files** — AI 只产生 Spec，Generator + Writer 负责文件
4. **Development First** — 面向 CAA 开发生命周期，不是面向代码生成
5. **Generator Is Backend** — Generator 不知道 AI 的存在，只接收 Spec
6. **Validation Before Generation** — Specification.validate() 在生成前校验
7. **Repository Is Single Source** — Workspace 状态统一管理和查询
8. **Specification Is Contract** — Intent 和 Generator 的唯一接口
9. **Diagnostics Before Fix** — 问题诊断输出结构化 FixPlan，不输出字符串
10. **Safe Modification** — 预览→确认→备份→应用→可回滚

---

## 🔧 Python API

### ActionContext

所有操作的入口点：

```python
from actions import ActionContext

ctx = ActionContext("D:/workspace")  # 工作区根目录
ctx.refresh()  # 刷新快照（自动记录版本）
snapshot = ctx.snapshot  # 获取工作区快照
ctx.history.summary()  # 查看快照版本历史
```

### 查询操作

```python
from actions import (
    analyze_workspace,
    list_modules,
    list_commands,
    list_workbenches,
    list_interfaces
)

# 分析工作区
result = analyze_workspace(ctx)

# 列出模块
result = list_modules(ctx)

# 列出命令
result = list_commands(ctx)

# 列出工作台
result = list_workbenches(ctx)

# 列出接口
result = list_interfaces(ctx)
```

### 创建操作

```python
from actions import (
    create_framework,
    create_module,
    create_command,
    create_workbench,
    create_dialog,
    create_interface,
    create_component,
    add_command_to_workbench
)

# 创建 Framework
result = create_framework(ctx, name="MyFramework")

# 创建 Module
result = create_module(ctx, framework_name="MyFramework", module_name="MyModule")

# 创建 Command
result = create_command(
    ctx,
    name="MyCommand",
    module="MyModule.m",
    framework="MyFramework"
)

# 创建状态命令 + 对话框
result = create_command(
    ctx,
    name="MyStatefulCmd",
    module="MyModule.m",
    framework="MyFramework",
    is_stateful=True,
    dialog_name="MyStatefulCmdDlg"
)

# 创建 Workbench
result = create_workbench(ctx, name="MyWorkbench", framework="MyFramework")

# 添加命令到工作台
result = add_command_to_workbench(
    ctx,
    command_name="MyCommand",
    workbench_name="MyWorkbench"
)

# 创建 Dialog
result = create_dialog(ctx, name="MyDialog", module="MyModule.m")

# 创建 Interface
result = create_interface(
    ctx,
    name="IMyInterface",
    module="MyModule.m",
    use_idl=True
)

# 创建 Component
result = create_component(
    ctx,
    name="MyComponent",
    module="MyModule.m",
    implements="IMyInterface"
)
```

### 删除操作

```python
from actions import delete_command, delete_module

# 删除命令（级联删除所有关联文件）
result = delete_command(
    ctx,
    name="MyCommand",
    module="MyModule.m",
    framework="MyFramework"
)

# 删除模块（删除所有内容）
result = delete_module(ctx, name="MyModule.m", framework="MyFramework")
```

### 依赖关系查询 (Phase 1 新增)

```python
from actions import (
    get_dependencies,
    get_dependents,
    visualize_dependencies,
    validate_workspace,
    find_orphaned_files
)

# 查询实体的依赖项
result = get_dependencies(ctx, "MyCommand", "command")
# 返回: {"dependencies": [{"name": "MyDialog", "type": "dialog"}, ...]}

# 查询依赖此实体的其他实体
result = get_dependents(ctx, "MyCommand", "command")
# 返回: {"dependents": [{"name": "MyWorkbench", "type": "workbench"}, ...]}

# 生成依赖关系图（Mermaid 格式）
result = visualize_dependencies(ctx, "MyCommand")
print(result["diagram"])  # Mermaid 图

# 验证工作区完整性
result = validate_workspace(ctx)
# 返回: {"errors": [...], "warnings": [...], "suggestions": [...]}

# 查找孤立文件
result = find_orphaned_files(ctx)
# 返回: {"orphaned_files": ["path/to/file.cpp", ...]}
```

### Intent Layer - 高级意图接口 (Phase 2 新增)

```python
from intents import (
    create_executable_command,
    expose_service,
    create_ui_dialog
)

# 创建完整的可执行命令（一次调用完成所有工作）
result = create_executable_command(
    ctx,
    name="CalculateVolume",
    module="GeometryTools.m",
    framework="MyFramework",
    with_dialog=True,              # 自动创建对话框
    add_to_workbench="GeometryWB"  # 自动添加到工作台
)
# 自动创建：Command、Dialog、Header、Catalog、NLS、Icon、Dictionary

# 暴露组件服务
result = expose_service(
    ctx,
    component_name="DataManager",
    module="CoreModule.m",
    methods=[
        {"name": "LoadData", "params": ["path"], "return": "HRESULT"},
        {"name": "SaveData", "params": ["path"], "return": "HRESULT"}
    ]
)
# 自动创建：Interface、IDL、TIE、Dictionary

# 创建交互式对话框
result = create_ui_dialog(
    ctx,
    name="ConfigDialog",
    module="UIModule.m",
    controls=[
        {"type": "Label", "text": "Enter value:"},
        {"type": "Editor", "name": "ValueEditor"},
        {"type": "PushButton", "name": "OKButton"}
    ],
    layout="vertical"
)
# 自动创建：Dialog、控件、回调骨架、NLS
```

### 回滚支持 (Phase 3 新增)

```python
from actions import (
    rollback_operation,
    list_rollback_points,
    cleanup_old_backups
)

# 列出所有可用的回滚点
result = list_rollback_points(ctx)
for backup in result["backups"]:
    print(f"{backup['backup_id']}: {backup['action']} - {backup['description']}")

# 回滚到指定备份点
result = rollback_operation(ctx, backup_id="20260707_143022")
if result["status"] == "success":
    print(f"已回滚: {result['message']}")
    print(f"恢复的文件: {len(result['restored']['restored_modified_files'])}")

# 清理旧备份（保留最近10个）
result = cleanup_old_backups(ctx, keep_count=10)
print(f"删除了 {len(result['deleted'])} 个旧备份")
```

### 高级意图 (Phase 4 新增)

```python
from intents import create_feature, create_extension, suggest_next_action

# 创建 Feature 对象
result = create_feature(
    ctx,
    name="MyFeature",
    module="TestModule.m",
    attributes=[
        {"name": "Length", "type": "CATLength", "default": "10mm"},
        {"name": "Angle", "type": "CATAngle", "default": "90deg"}
    ],
    with_factory=True
)
# 自动创建：Feature、Factory、StartUp Catalog、属性定义

# 创建数据扩展
result = create_extension(
    ctx,
    name="MyExt",
    target_object="CATPart",
    module="TestModule.m",
    data_members=[{"name": "_length", "type": "double"}],
    implements=["CATIMyExt"]
)
# 自动创建：Extension、DataExtension 声明、TIE、Dictionary

# 智能推荐下一步操作
result = suggest_next_action(ctx)
for sug in result["suggestions"][:3]:
    print(f"[{sug['priority']}] {sug['action']}: {sug['reason']}")
```

### Specification 层 (P1 新增)

Specification 是 Intent 和 Generator 之间的契约层：

```python
from specification import (
    CommandSpec, DialogSpec, InterfaceSpec, ComponentSpec,
    FeatureSpec, ExtensionSpec, WorkbenchSpec,
    MethodSpec, AttributeSpec, DataMemberSpec,
)

# 构建 Spec
spec = CommandSpec(
    name="MyCmd", module="MyModule.m",
    stateful=True, tooltip="My Command",
    dialog=DialogSpec(name="MyCmdDlg", layout="vertical"),
    workbench="MyWorkbench",
)

# 校验
result = spec.validate()
if result["status"] != "ok":
    print(f"Validation failed: {result['message']}")

# 序列化/反序列化
d = spec.to_dict()          # → JSON-safe dict
restored = spec_from_dict(d) # → CommandSpec

# Generator 只接收 Spec，不知道 AI 的存在
```

### Diagnostics + FixPlan（新增）

结构化诊断 + 自动修复方案：

```python
from diagnostics import diagnose_workspace, DiagnosticsEngine, FixPlan
from actions import ActionContext

ctx = ActionContext("D:/workspace")

# 一键诊断
result = diagnose_workspace(ctx)
print(f"发现 {result['total']} 个问题（{result['errors']} 错误, {result['warnings']} 警告）")
print(f"{result['auto_fixable']} 个可自动修复")

for d in result["diagnostics"]:
    print(f"[{d['severity']}] {d['problem']}")
    print(f"       原因: {d['reason']}")
    if d.get("fix_plan"):
        print(f"       修复: {d['fix_plan']['description']}")
```

### Refactor（新增）

安全重构，基于依赖图自动更新所有引用：

```python
from refactor import rename_command, rename_interface, move_command
from actions import ActionContext

ctx = ActionContext("D:/workspace")
ctx.refresh()
snapshot = ctx.snapshot

# 重命名命令（自动更新 Dictionary/Catalog/NLS/Imakefile/Workbench）
result = rename_command(
    snapshot, module_name="TestMod.m",
    old_name="OldCmd", new_name="NewCmd"
)
print(result["preview"])  # 审查所有变更

# 移动命令到另一个模块
result = move_command(
    snapshot,
    source_module="TestMod.m",
    target_module="OtherMod.m",
    command_name="MyCmd"
)
```

---

## 🛠️ 命令行工具

### 1. 编译 (mkmk)

```bash
python skills/build.py [workspace_path] [options]
```

**示例**:
```bash
python skills/build.py                        # 编译当前目录
python skills/build.py D:\workspace\MyFw.edu  # 编译指定 Framework
python skills/build.py . -g                   # 全局编译
python skills/build.py . --timeout 1200       # 自定义超时
```

**输出**:
```json
{
  "status": "success",
  "message": "Build successful",
  "error_count": 0,
  "warning_count": 2,
  "duration": "2m 35s",
  "workspace": "D:\\workspace\\MyFw.edu"
}
```

### 2. Build Time 命名命令（35 个，AI 友好）

```python
from build import (
    # 编译 (7)
    incremental_build,   # mkmk -u   增量编译
    full_build,          # mkmk -a   全量编译
    clean_build,         # mkmk -c   Clean后编译
    debug_build,         # mkmk -g   Debug编译
    dry_run_build,       # mkmk -n   预览模式
    build_with_threads,  # mkmk -j N 多线程编译
    mkmk_version,        # mkmkversion

    # Runtime View (2)
    create_runtime_view,            # mkCreateRuntimeView
    multi_create_runtime_view,      # mkMultiCreateRuntimeView

    # Workspace (5)
    workspace_info,          # mkwhereami + mkreadcpd
    workspace_where,         # mkwhereami
    workspace_config,        # mkreadcpd
    workspace_build_config,  # mkreadbldcfg
    workspace_module_info,   # mkreadms

    # Framework (3)
    update_framework,    # MkUpToDateAFramework
    copy_framework,      # MkCopyFw
    remove_framework,    # MkRemoveAFramework / mkRmFw

    # 依赖 (4)
    dependency_analysis,  # mkmkdepend
    impact_analysis,      # mkmkimpact
    get_prerequisite,     # mkGetPreq
    print_prerequisite,   # mkPrintPreq

    # IdentityCard (1)
    create_identity_card,  # mkCreateIC

    # 文档 (3)
    generate_cpp_doc,    # mkmancpp
    generate_idl_doc,    # mkmanidl
    extract_methods,     # mkGetMethodsProto

    # 导出 (1)
    export_symbols,      # mkexportsymbols

    # 工具 (3)
    run_executable,      # mkrun
    register_vs,         # mkManageDevenvReg
)

# 使用示例
result = incremental_build(Path("D:/workspace"))
result = create_runtime_view(Path("D:/workspace"))
result = workspace_info(Path("D:/workspace"))
result = get_prerequisite(Path("D:/workspace"), target="MyModule.m")

# 通用接口：运行任意 Build Time 命令
from env import CAAEnvironment
env = CAAEnvironment(); env.load_config()
cmd_list, cmd_display = env.run_command("mkwhereami", "D:/workspace")
```

### 3. 运行 CATIA (CNEXT)

```bash
python skills/run.py [options]
```

**示例**:
```bash
python skills/run.py                    # 启动 CATIA
python skills/run.py --workspace D:\ws  # 指定工作区
python skills/run.py --wait             # 等待 CATIA 退出
python skills/run.py --stop             # 停止所有 CATIA 进程
```

**Python API**:
```python
from run import (
    start_catia_runtime,   # CNEXT
    run_catia_macro,       # CNEXT -macro
    run_catia_batch,       # CNEXT -batch
    stop_catia,
    check_catia_running,
)

# 启动 CATIA
result = start_catia_runtime(workspace_path="D:/workspace")

# 运行宏
result = run_catia_macro("D:/scripts/my_macro.CATScript")

# 检查是否运行
result = check_catia_running()

# 停止 CATIA
result = stop_catia()

# 指定环境启动
result = run_catia_with_env("CATIA_P3.V5-6R2018.B28", workspace_path="D:/workspace")

# 运行 CATScript 宏
result = run_catia_macro("D:/scripts/my_macro.CATScript")

# Batch 模式
result = run_catia_batch()
```

### 3. 清理工作区

**输出**:

```bash
python skills/clean.py [workspace_path] [options]
```

**示例**:
```bash
python skills/clean.py                  # 清理当前目录
python skills/clean.py D:\workspace     # 清理指定工作区
python skills/clean.py . --deep         # 深度清理（包括缓存）
```

### 4. 工作区验证

```bash
python skills/workspace.py [workspace_path]
```

**输出**:
```json
{
  "status": "valid",
  "workspace": "D:\\workspace\\MyFw.edu",
  "has_identity_card": true,
  "modules": ["Module1.m", "Module2.m"]
}
```

### 5. Runtime View 管理

```bash
python skills/runtime_view.py [workspace_path]
```

**输出**:
```json
{
  "status": "valid",
  "runtime_view": "D:\\RuntimeView",
  "dll_count": 15,
  "missing_dlls": []
}
```

---

## 📊 测试验证

详细测试文档: [TEST_DOCUMENTATION.md](docs/TEST_DOCUMENTATION.md)

### 当前验证范围

> ✅ 已达到条件性生产就绪（详见本文件「🚧 生产就绪评估」章节）。但快速模式仍只执行安全的静态/模拟回归，不执行真实 Build、CNEXT 或 CATIA 生命周期，因此仍需每次生成代码后在真实工作区跑一次 Build 确认（非阻塞使用规程，不是待修复的缺陷）。

**Full Integration**: 49/49 通过
```bash
python tests/test_full_integration.py
```

**Full Regression quick**: 394/398，剩余 4 项为精确 quarantine
```bash
python tests/test_full_regression.py --quick
```

**Master quick**: 39 套中执行 38 套，跳过 1 套 CATIA 生命周期测试
```bash
python tests/test_master.py --quick
```

**测试分组**:
- ✅ 模块导入测试 (13/13)
- ✅ 元模型测试 (7/7)
- ✅ 变更集测试 (7/7)
- ✅ 模板生成器测试 (6/6)
- ✅ 工作区分析器测试 (4/4)
- ✅ 原子操作测试 (7/7)
- ✅ 环境与构建测试 (5/5)
- ✅ 场景集成测试 (L3-2, 6 scenarios)
- ✅ 需求分解器测试 (L1-2, 21/21)
- ✅ 代码验证器测试 (L0-5, 15/15)
- ✅ Token 状态测试 (L0-6, 29/29)
- ✅ SKILL YAML 测试 (L0-7, 17/17)

### 性能基准

| 操作 | 时间 | 对比 |
|------|------|------|
| 模板生成 | ~50ms | 比 RADE 快 100x |
| 工作区分析 | ~100ms | 即时反馈 |
| 预览变更 | ~20ms | 实时响应 |
| 应用变更 | ~100ms | 高效执行 |

### 测试报告

详细测试报告请查看阶段完成报告：
- 运行 `python tests/test_master.py --quick` 进行快速检查
- 运行 `python tests/test_master.py` 进行全系统检查

---

## 📁 文件结构

```text
.agents/skills/catia-caa-dev/
├── SKILL.md                          # 主技能文档（本文件）
├── CHANGELOG.md                      # 更新日志
├── .gitignore                        # Git 忽略文件
│
├── skills/                           # Python 模块
│   ├── intents/                      # Intent Layer (6 文件)
│   │   ├── commands.py               # 命令意图
│   │   ├── services.py               # 服务意图
│   │   ├── objects.py                # 对象意图
│   │   ├── recommendation.py         # 智能推荐
│   │   └── helpers.py                # 辅助函数
│   ├── actions.py                    # Development Engine
│   ├── specification.py              # Spec 层 (8 种 Spec)
│   ├── diagnostics.py                # Diagnostics + FixPlan
│   ├── refactor.py                   # 安全重构
│   ├── generator.py                  # 代码生成器
│   ├── meta_model.py                 # Rich Domain Model (10 实体)
│   ├── analyzer.py                   # 工作区分析器
│   ├── changeset.py                  # Writer/变更集管理
│   ├── backup.py                     # 回滚系统
│   ├── env.py                        # 环境管理
│   ├── parser.py                     # mkmk 输出解析
│   ├── utils.py                      # 日志和缓存
│   ├── build.py                      # Build Engine (35 命令)
│   ├── run.py                        # Runtime Engine (7 函数)
│   ├── clean.py                      # 清理管理
│   ├── workspace.py                  # 工作区验证
│   ├── runtime_view.py               # Runtime View 管理
│   ├── cade.py                       # CLI 入口 (22 命令)
│   ├── mcp_server.py                 # MCP Server (3 Mode, v3.0)
│   ├── kernel.py                     # Development Kernel (v3.0)
│   ├── catalog.py                    # Knowledge Catalog Index (v3.0)
│   ├── requirements.py               # Requirements Clarifier (v3.0)
│   │   └── decision_trees/          # 决策树 (3 个)
│   ├── verifier.py                   # Code Verifier — static + mkmk (v3.0)
│   ├── icon_provider.py              # 107 geometric icons, 4x SSAA, RGBA multi-color (v3.2)
│   ├── repair.py                     # Repair Loop (v3.0)
│   ├── token_optimizer.py            # AI Token 优化器
│   ├── docgen.py                     # 文档生成器
│   ├── version_strategy.py           # 版本策略
│   ├── intent/                       # Intent Engine (P0 Planner)
│   │   ├── models.py                 # Intent / Plan 数据模型
│   │   ├── planner.py                # 意图→计划转换
│   │   ├── impact.py                 # 影响分析 (P1)
│   │   ├── optimizer.py              # 方案评分排序 (P2)
│   │   └── templates/                # Task Templates
│
├── templates/                        # 模板库（17+ 类型）
│   ├── Framework/
│   ├── Module/
│   ├── Command/
│   ├── StateCommand/
│   ├── Dialog/
│   ├── Component/
│   ├── Interface/
│   └── ...
│
├── catalog/                           # 全局索引
│   └── index.yaml                    # 关键词→ID→文件映射
│
├── capabilities/                     # 能力层: 10 个 CAA 核心能力
│   ├── assembly-tree.md
│   ├── geometry-query.md
│   ├── feature-recognition.md
│   ├── parameter-system.md
│   ├── visualization.md
│   ├── selection.md
│   ├── document-export.md
│   ├── surface-operations.md
│   ├── annotation.md
│   └── powercopy.md
│
├── playbooks/                          # 方案层: 业务目标驱动
│   ├── pb_auto_color.md
│   └── pb_export_bom.md
│
├── knowledge/                         # CAA 知识库 (按 CAA 域组织)
│   ├── mecmod/                       # MecMod: Feature 模型、拓扑
│   ├── part/                         # Part Design: 圆角、孔、倒角
│   ├── product/                      # Assembly: 装配、约束
│   ├── ui/                           # GUI: Dialog、布局、事件、Toolbar
│   │   ├── dialog.md                 # Dialog 基础
│   │   ├── dialog_layout.md          # 布局模式 + GridConstraints
│   │   ├── dialog_patterns.md        # 控件模式 + 决策索引
│   │   ├── dialog_dataflow.md        # 数据流、持久化、NLS
│   │   ├── event_patterns.md         # 事件回调模式
│   │   ├── toolbar.md                # 工具栏/CommandHeader
│   │   ├── workbench_patterns.md     # Workbench/Addin
│   │   ├── layout_advanced.md        # 高级布局（列表-详情/动态/树/向导）
│   │   └── layout_anti_patterns.md   # 布局反模式/常见错误
│   ├── drawing/                    # Drawing: 视图、标注、BOM表
│   │   ├── drawing_basics.md
│   │   └── drawing_annotations.md
│   ├── surface/                    # GSD: 曲面、扫掠、展平
│   │   └── surface_basics.md
│   ├── fta/                        # FTA: 3D标注、公差
│   │   └── fta_basics.md
│   ├── frameworks/                  # Framework 导航 (148 个 CAADoc Framework)
│   │   └── infrastructure/               # 基础设施: Selection、CodeStyle、Memory
│   ├── philosophy/               # CAA 底层哲学 (v3.0, 6 篇)
│   │   ├── updates.md
│   │   ├── late_types.md
│   │   ├── reference_vs_instance.md
│   │   ├── com_lifecycle.md
│   │   ├── caterror.md
│   │   └── undo_redo.md
│   ├── failure_patterns/          # 失败模式 (v3.0, 3 篇)
│   │   ├── fp_imakefile_link.md
│   │   ├── fp_missing_include.md
│   │   └── fp_undeclared_class.md
│   └── infrastructure/               # 基础设施: Selection、CodeStyle、Memory
│
├── patterns/                          # 开发模式库 (Coarse + Block)
│   ├── analyzer/                     # 粗模式: 几何分析、规则检查
│   ├── ui/                           # 粗模式: 结果对话框、Master-Detail、Wizard
│   │   ├── result_dialog.md
│   │   ├── master_detail.md          # 列表-详情模式
│   │   ├── dynamic_form.md           # 动态表单模式
│   │   └── wizard.md                 # 多步骤向导模式
│   ├── drawing/                    # Drawing: 批量工程图
│   │   └── batch_drawing.md
│   ├── surface/                    # Surface: 曲面分析/展平
│   │   └── surface_analysis.md
│   ├── fta/                        # FTA: 自动3D标注
│   │   └── auto_annotate.md
│   ├── workflow/                     # 粗模式: 批量处理
│   └── blocks/                       # 积木: Visitor、Locator
│
├── examples/                          # 真实 CAA 项目示例
│   └── geometry/                     # fillet_checker 完整项目
│
├── docs/                             # 文档目录
│   ├── guides/                       # 使用指南
│   │   ├── AI_GUIDE.md
│   │   ├── GETTING_STARTED.md
│   │   ├── BUILD_RUN_TIME_USAGE_GUIDE.md
│   │   ├── DEPLOYMENT_GUIDE.md
│   │   ├── DICTIONARY_GUIDE.md
│   │   ├── TROUBLESHOOTING_FLOWCHART.md
│   │   └── FAQ.md
│   ├── references/                   # 技术参考
│   │   ├── ARCHITECTURE.md
│   │   ├── CAA_REFERENCE.md
│   │   ├── CGM_REFERENCE.md
│   │   ├── COMMAND_QUICK_REFERENCE.md
│   │   ├── DIALOG_QUICK_REFERENCE.md
│   │   ├── QUICK_REFERENCE.md
│   │   ├── CHEAT_SHEET.md
│   │   └── QUICK_DECISION_TREE.md
│   ├── examples/                     # 示例代码
│   │   ├── EXAMPLE_COMMAND.md
│   │   ├── EXAMPLE_DIALOG.md
│   │   ├── EXAMPLE_EXTENSION.md
│   │   ├── EXAMPLE_MULTI_INTERFACE.md
│   │   ├── EXAMPLE_CALCULATOR.md
│   │   └── AI_WORKFLOW_EXAMPLES.md
│   └── README.md                     # 文档索引
│
├── tests/                            # 测试文件（35 个，35 套件，~600 测试项）
│   ├── test_master.py                # 主运行器
│   ├── test_full_regression.py       # 全系统验证
│   ├── test_cross_reference.py       # 交叉引用审计
│   ├── test_token_optimizer.py       # Token 优化器测试（含 audit）
│   ├── test_system_health.py         # 系统健康检查
│   ├── test_caa_structure.py         # CAA 结构合规
│   ├── test_intent_planner.py        # Intent 引擎测试
│   ├── test_ai_integration.py        # AI 集成测试
│   ├── test_build_and_run.py         # Build/Run 合并测试
│   ├── test_skill_ai_coordination.py # Skill-AI 协同 + 运行时链
│   ├── test_full_integration.py      # 单元测试
│   ├── test_e2e_integration.py       # 端到端集成
│   ├── test_phase1_enhancements.py   # Phase 1: 依赖图
│   ├── test_phase2_intents.py        # Phase 2: Intent
│   ├── test_phase3_rollback.py       # Phase 3: 回滚
│   ├── test_phase4_enhanced.py       # Phase 4: 增强意图
│   ├── test_specification.py         # Spec 层
│   ├── test_diagnostics.py           # 诊断
│   ├── test_fixplan_executor.py      # FixPlan 执行器
│   ├── test_refactor.py              # 重构
│   ├── test_l4_architecture.py       # 架构不变量
│   ├── test_l5_semantic.py           # 语义完整性
│   ├── test_l6_fault_injection.py    # 故障注入
│   ├── test_knowledge_system.py      # 知识系统
│   ├── test_catia_detection.py       # CATIA 检测
│   └── test_system_health.py         # 健康检查
│
├── tools/                            # 辅助工具(与 skills/ 无关,不属于 Kernel 模块)
│   ├── build_caadoc_index.py         (CAADoc API 签名/实现关系索引与核实工具: --query/--search/--repl; 同步扫描 SDK PublicInterfaces/*.h 与 refman 交叉比对)
│   ├── check_code_reuse.py
│   ├── validate_component_ai.bat
│   ├── scan_frameworks.py
│   ├── production_readiness_check.py
│   ├── catia_detector.py             (动态检测本机 CATIA 安装,零硬编码)
│   ├── prerequisites_manager.py      (Prerequisites 依赖管理)
│   └── setup_wizard.bat / setup_environment.* / setup_mcp.* / setup_prerequisites.*
│
└── config/                           # 配置文件
    ├── caa_env_config.txt
    ├── requirements.txt
```

---

## 📁 项目文档规范

每个 CADE 生成的 Framework 自动包含以下文档结构：

| 文件/目录 | 用途 | 规则 |
|----------|------|------|
| `README.md` | 项目入口 | 一句话定位 + 快速开始 + 模块表 |
| `ARCHITECTURE.md` | 架构说明 | 模块依赖图 + 接口/命令清单 |
| `CHANGELOG.md` | 版本记录 | 按 Added/Changed/Fixed 分类 |
| `docs/API/` | API 参考 | 接口文档、类图、调用示例 |
| `docs/Design/` | 设计说明 | 架构图、流程图、技术决策 |
| `docs/Images/` | 图片资源 | PNG 截图，不放源文件 |
| `examples/` | 测试数据 | 示例 CATPart/CATProduct，大文件用 LFS |

**原则**：
- 不放 Obsidian 知识库内容（TODO/Meeting/Knowledge）
- 文档面向开发者（clone 项目的人直接可读）
- 和 CAA 标准目录（IdentityCard/CNext/FunctionTests）互不冲突
- build/run/test 直接用 CADE CLI，不放脚本

---

## 🎓 最佳实践

### 0. 三不原则（最高优先级）

> **不重复造轮，不瞎猜，不跳过帮助**

| 规则 | 说明 |
|------|------|
| 🚫 **不重复造轮** | 有成熟模板直接用，不要手写 CAA 样板代码 |
| 🚫 **不瞎猜** | 遇到未知错误，第一时间查帮助文档，不要凭经验猜测 |
| 🚫 **不跳过帮助** | capabilities/ → playbooks/ → knowledge/ → patterns/ → examples/ → frameworks/ → CAADoc → docs/ 帮助文档 |

```python
# ❌ 错误：遇到编译错误直接猜原因
# "可能是少了某个 include"
# "试一下加个 CATBaseUnknown"

# ✅ 正确：先查帮助系统
# 1. 查 docs/FAQ.md、docs/guides/ 找已知解决方案
# 2. 查 knowledge/part/ 或 knowledge/infrastructure/ 获取正确 API
# 3. 查 patterns/workflow/ 看正确的流程
# 4. 查 examples/ 找真实示例代码
# 5. 用 cade diagnose 让引擎帮你找问题
# 6. 用 cade fix --apply 让引擎自动修复
```

### 1. 始终先查询
```python
# ❌ 错误：直接创建
create_command(ctx, name="MyCmd", module="TestModule.m")

# ✅ 正确：先查询可用的模块、接口、工作台
modules = list_modules(ctx)
interfaces = list_interfaces(ctx, module="TestModule.m")
workbenches = list_workbenches(ctx)
# 然后基于现有结构创建
create_command(ctx, name="MyCmd", module=modules[0]["name"])
```

### 2. 使用预览模式（仅适用于直接调用 `actions.py`；通过 `develop()` 则无需手动 apply）
```python
# 创建命令（自动返回预览）
result = create_command(ctx, name="MyCmd", module="TestModule.m")

# 检查预览
if result["status"] == "pending":
    preview = result["preview"]
    print(f"将创建 {len(preview['will_create'])} 个文件")
    print(f"将修改 {len(preview['will_modify'])} 个文件")

    # 确认后应用
    from changeset import ChangeSet
    cs = ChangeSet.from_dict(result["changeset"])
    cs.apply(workspace_root=ctx.workspace_root)

# 若使用 Kernel 的 develop()（MCP/CLI 推荐路径），上面的 apply 步骤已由
# Kernel 自动完成，无需手动处理：
# result = kernel.execute(KernelMode.DEVELOP, "create command MyCmd in TestModule.m")
# result["status"] == "ok"  # 文件已存在，已自动备份（result["apply_result"]["rollback_id"]）
```

### 3. 处理错误
```python
result = create_command(ctx, name="MyCmd", module="NonExistent.m")

if result["status"] == "error":
    print(f"错误: {result['message']}")
    # 输出: 错误: Module 'NonExistent.m' not found
```

### 4. 批量操作
```python
# 创建多个命令
commands = ["Cmd1", "Cmd2", "Cmd3"]
for cmd in commands:
    result = create_command(ctx, name=cmd, module="TestModule.m")
    if result["status"] == "pending":
        print(f"✓ {cmd} 准备就绪")
```

### 5. 级联删除
```python
# 删除命令会自动删除所有关联文件
result = delete_command(ctx, name="MyCmd", module="TestModule.m")

# 自动删除:
# - MyCmd.cpp, MyCmd.h
# - MyCommandHeader.cpp
# - Catalog 条目
# - NLS 资源
# - Icon 文件
```

---

## 🔍 故障排查

### 🔴 核心法则：遇到未知错误，先查帮助，不猜

```
未知错误发生
    ↓
① 查 capabilities/ → playbooks/     ← 能力入口 + 成熟方案
    ↓
② 查 docs/FAQ.md / docs/guides/     ← 先查帮助文档，找已知方案
    ↓
③ cade diagnose                     ← 让引擎帮你分析
    ↓
④ knowledge/ 查 API 参考             ← 查正确用法
    ↓
⑤ patterns/ 查架构模式               ← 查正确流程
    ↓
⑥ examples/ 查实战代码               ← 查真实案例
    ↓
⑦ knowledge/frameworks/ → CAADoc    ← Framework 导航定位 → 精准查官方文档
    ↓
⑧ cade fix --apply                  ← 让引擎自动修复

> ⚠️ **不要**跳过前两步直接写代码。docs/ 帮助文档和 knowledge/patterns/examples 里 90% 的问题已有答案。

### 🚨 症状速查表

| 症状 | 第一排查点 | 文档 |
|------|-----------|------|
| CNEXT 无工具栏按钮 | `MacDeclareHeader` 在 .cpp 中？ | `knowledge/ui/toolbar.md` |
| 编译成功但 DLL 未生成 | `build.py` false positive？ | `BestPractices.md → 编译输出完整性审计` |
| 输出含 `mkmk-ERROR` / `syst-ERROR` | 即使 mkmk 返回 0，也必须判 Build 失败 | `skills/parser.py` wrapper 解析规则 |
| mkmk 报 License 错误 | TCK 未注册？CATEnv 回退 | `BestPractices.md → TCK 回退策略` |
| 编译无 make 输出 | `mkGetPreq` 缺 `call` 前缀 | `BestPractices.md → mkGetPreq 静默退出` |
| CNEXT 找不到 addin | `CATDictionaryPath` 指向 Runtime View？ | `BestPractices.md → CNEXT 环境变量` |
| Runtime View 缺资源 | 编译后是否同步 dico/NLS/icons？ | `BestPractices.md → Runtime View 同步` |
| Dialog LNK2001 错误 | 误用 `CATImplementClass`？ | `knowledge/ui/dialog.md` |

### Build 结果判定

B28 的正式错误前缀是 `mkmk-ERROR`，构建系统错误使用 `syst-ERROR`；`make-ERROR` 仅作为历史兼容变体保留。parser 支持带或不带 `#`、带前导缩进的行首 wrapper，但不会把普通正文中的同名字符串误判为错误。

不能只依据 mkmk 进程返回码判定成功。Build 成功必须同时满足：

1. parser 的错误数为 0，且输出不含 `mkmk-ERROR`、`make-ERROR` 或 `syst-ERROR`；
2. 预期 DLL 存在且大小大于 0；
3. DLL 修改时间不早于本次 Build 开始时间，不能接受旧缓存产物。

### 常见问题

#### 1. "Module not found"
```python
# 问题：模块名称错误或不存在
result = create_command(ctx, name="MyCmd", module="WrongModule.m")

# 解决：先查询可用模块
modules = list_modules(ctx)
print([m["name"] for m in modules["modules"]])
```

#### 2. "Framework not found"
```python
# 问题：工作区路径错误
ctx = ActionContext("D:/wrong/path")

# 解决：使用正确的工作区根目录（包含 *.edu 目录）
ctx = ActionContext("D:/workspace")  # 包含 MyFramework.edu/
```

#### 3. 分析器返回空结果
```python
# 问题：传入的是 Framework 目录而不是工作区根目录
ctx = ActionContext("D:/workspace/MyFramework.edu")  # ❌ 错误

# 解决：使用工作区根目录
ctx = ActionContext("D:/workspace")  # ✅ 正确
```

---

## 📖 参考文档

### 核心文档
- **SKILL.md** (本文件) - 主技能文档
- **docs/references/ARCHITECTURE.md** - 架构设计
- **docs/references/ARCHITECTURE.md** - 系统架构
- **docs/KNOWLEDGE_SYSTEM_ARCHITECTURE.md** - 知识系统架构
- **docs/guides/AI_GUIDE.md** - AI 使用指南
- **docs/guides/GETTING_STARTED.md** - 快速入门

### 参考指南
- **docs/references/CAA_REFERENCE.md** - CAA V5 API 参考
- **docs/references/COMMAND_QUICK_REFERENCE.md** - 命令快速参考
- **docs/references/DIALOG_QUICK_REFERENCE.md** - 对话框快速参考
- **docs/references/CHEAT_SHEET.md** - 速查表
- **docs/references/QUICK_DECISION_TREE.md** - 快速决策树

### 测试与验证
- 运行 `python tests/test_master.py --quick` 进行快速检查(20s)
- 运行 `python tests/test_master.py` 进行全系统检查(含 CATIA 启停)

### 示例
- **docs/examples/EXAMPLE_COMMAND.md** - 命令开发示例
- **docs/examples/EXAMPLE_DIALOG.md** - 对话框开发示例
- **docs/examples/EXAMPLE_EXTENSION.md** - 扩展开发示例
- **docs/examples/EXAMPLE_MULTI_INTERFACE.md** - 多接口示例
- **docs/examples/EXAMPLE_CALCULATOR.md** - 计算器示例
- **docs/examples/AI_WORKFLOW_EXAMPLES.md** - AI 工作流示例

---

## 🚧 生产就绪评估

### 当前判定：✅ 条件性生产就绪（Conditional GO）

核心 Kernel 缺陷（ChangeSet 失败零副作用、组合创建、merge 冲突阻断、Build 输出解析、Repair 当前输出诊断、DLL 新鲜度验证、Analyzer 去重、develop 模式自动应用、对话框命令 3 处根因）均已修复并通过实机验证（见下方 2026-07-17/07-19 修复记录）。知识库高风险区域（`knowledge/drawing/*`、`patterns/drawing/batch_drawing.md` 曾疑似含虚构 `CATIDrw*`/`CATIAnnBOM` API 体系）已于 2026-07-20 完成核实与重写，不再阻塞生产使用。

**结论**：可以在满足下方「部署前检查清单」的前提下投入生产使用。以下为已知的**非阻塞**残余风险，需在使用规程中显式规避，不需要在使用前修复：

- Full Regression quick 的 4 项 quarantine 均为测试基础设施本身的已知缺口（缺失的辅助模块 `test_skills.py`、`test_build_and_run.py` 在 subprocess 子进程模式下对 MCP 工具列表的间接断言问题），**不代表功能缺陷**，详见下方逐项说明。
- quick 模式不执行真实 Build、CNEXT 或 CATIA 生命周期（`test_build_and_run.py` 整套在 `test_master.py --quick` 下被跳过）；真实 Build 验证需要单独跑 Tier B（见下方「已验证范围」），**每次生成代码后仍需在自己的工作区跑一次真实 Build 确认**，这是使用规程而非工具缺陷。
- 模板全集和 CATIA 运行时验收证据仍只覆盖 `TTEST` 单一工作区的一个模块；新工作区/新模板组合首次使用时应加强人工审查。
- 知识库里 `patterns/` 目录其余9个文件及部分 `knowledge/mecmod|philosophy|surface|ui|infrastructure|failure_patterns` 子文件仍未逐条核实（详见下方「知识库可信度」），AI 引用到这些区域的具体 API 时应主动用 `--query`/`--check-file` 复核，不影响已核实区域（含 `capabilities/`/`playbooks/`/`knowledge/drawing/` 全部）的可信度。

### 部署前检查清单

- [ ] 已阅读并接受上方「非阻塞残余风险」的使用规程（尤其：生成代码后必须在真实工作区跑一次 Build）
- [ ] 已跑通 `python tests/test_master.py --quick`，确认本机环境下 38/38 通过
- [ ] 已确认目标 CATIA 版本 ≥ R19（工具在 B28 上做过实机验证；跨版本首次使用建议先在测试工作区跑一次 `develop()`/`repair()` 全流程）
- [ ] 团队已知晓 `KNOWLEDGE_AUDIT_STATUS.md` 中「未核实清单」范围，涉及这些 API 时纳入代码审查重点
- [ ] 首次在新工作区使用时，先用小范围改动验证 ChangeSet 应用 + Build 闭环，再扩大到完整开发任务

**2026-07-17 修复**：`build.py` 的 `incremental_build()` / `clean_build()` / `debug_build()` / `build_with_threads()` 此前只传递修饰标志（如 `-u`、`-g`、`-j N`），未附带 mkmk 强制要求的目标选择器 `-a`，导致对任意真实工作区调用都会失败，报出误导性的"must be executed in a workspace containing, at least, one framework"错误（实际是缺少 `-a`，与许可证/环境无关）。已修复为始终包含 `-a`；`dry_run_build()` 改用 `-a -nobuild`（mkmk 无 `-n` 选项，会被拒绝为非法参数）。新增 `test_build_and_run.py` Part 4.5（Tier B，opt-in、不启停 CATIA）对 `D:/Vault/FSWorkspaces/TTEST` 执行真实 `incremental_build()`，验证 0 编译错误、DLL 新鲜度校验通过、DLL mtime 确实刷新。

**2026-07-17 修复（develop 模式自动应用）**：`kernel.py` 的 `_execute_develop_plan()` 以前仅把 `actions.py`/`intents/*` 返回的 `status="pending"` + 序列化 `changeset` 原样返回，从未调用 `ChangeSet.from_dict().apply()`。结果：通过文档推荐的 MCP/CLI `develop()` 路径发出的请求永远停在 "pending"，没有任何公开接口可以完成应用；后续的 Phase 2.5（extras）、Phase 3（静态验证）、Phase 3.5（IdentityCard）因文件不存在而静默无操作。已修复：`_execute_develop_plan()` 在拿到 `pending` + `changeset` 后，新方法 `_apply_changeset_dict()` 会立即 `ChangeSet.from_dict(...).apply(workspace_root=...)`，并将最终 `status` 改为 `"ok"`（失败则 `"error"`）。`ModePolicy` 中 `DEVELOP` 的 `auto_apply` 已从 `False` 改为 `True`（与 `REPAIR` 同模式：备份终断应用，可通过 `repair()` 回滚）。同时修复了 `mcp_server.py` 中 `develop` 工具的 `description`，明确说明“一次调用即完成，不要等待确认步骤”。回归：`test_kernel_edge_cases.py`（ModePolicy 断言）、`test_ui_scenario.py`（Section 3 不再手动 apply）已同步更新。

**2026-07-19 修复（对话框命令生成的 3 个根因 —— 生成的“打开对话框”命令实机不可用）**：在 `TTEST` 工作区手动实机验证 `--dialog` 命令时，发现按钮完全无响应或对话框打不开/关不掉。逐一定位到 `actions.py` 的 `create_command()`（`--dialog` 分支）里 3 处独立根因，均已修复并通过官方 CAADoc 样例（`CAADialogEngine.edu\CAADegGeoCommands.m\src\CAADegAnalysisNumericCmd.cpp`、`CAAApplicationFrame.edu\CAAAfrGeometryWshop.m\src\CAAAfrGeometryWks.cpp`）交叉核对，并在真实 CATIA（B28）里逐一点击验证：

1. **对话框父窗口为 NULL → 完全不可见**：`BuildGraph()` 原来用 `new XxxDlg(NULL)` 创建对话框。在 B28 下，无父窗口的顶层 `CATDlgDialog` 永远不会被窗口管理器映射（既不报错也不显示）。已修复为始终传入 `CATApplicationFrame::GetFrame()->GetMainWindow()` 作为父窗口。
2. **多个命令挂同一个工具栏时，只有最后一个按钮可点击**：`CreateToolbars()` 生成代码对每个命令都调用 `SetAccessChild(pToolbar, X)`——这个 API 是“设置唯一子节点”，每次调用都会**覆盖**前一个，不是追加。结果是同一工具栏里先注册的命令按钮全部失效（不可见/不可点）。已修复：第一个 Starter 用 `SetAccessChild`，之后每个新增的 Starter 改用 `SetAccessNext(prev, new)` 链接成单链表（与官方 `CAAAfrGeometryWks.cpp` 的写法一致）。
3. **对话框打开后点击“关闭”没有任何反应**：生成的 `AddTransition(pDlgState, NULL, IsOutputSetCondition(_pDlgAgent))` 这种“回到 NULL 结束态”写法，在对话框被关闭时框架实际调用的是 **`Cancel()`**，不是 `Desactivate()`（通过在 `Activate`/`Desactivate`/`Cancel` 里加日志实机追踪确认）。之前生成的代码只在 `Desactivate()` 里隐藏/销毁对话框，`Cancel()` 是空的，所以点击关闭没有效果。已修复为与官方样例一致的模式：`Desactivate()` 和 `Cancel()` 都只调用 `_pDialog->SetVisibility(CATDlgHide)`（隐藏，不销毁），真正的 `_pDialog->RequestDelayedDestruction()` 只放在析构函数里。**切勿在 `Cancel()`/`Desactivate()` 里直接 `delete _pDialog` 或调用非 delayed 的销毁——对话框可能仍在处理待发的通知，直接销毁会导致崩溃或悬空指针。**

这 3 处修复目前只覆盖生成器对 `--dialog` 分支的代码模板；已存在的旧生成代码（在本次修复之前创建的项目）需要手工按上述模式回填，生成器不会自动迁移历史文件。回归：`test_master.py --quick` 38/38 通过（含修复前后各一次基线对比）。诊断脚本已归档到 `skills/debug_tools/`（`cade_enumwin.ps1`/`cade_findbtn.ps1` 等，用于从进程外部检查 CATIA 窗口/工具栏；详见该目录的 README）。

### 📚 知识库可信度（与上述 Kernel 开发流程无关的另一个维度）

`develop()`/`analyze()`/`repair()` 的代码生成质量还取决于它引用的 `capabilities/`/`knowledge/`/`patterns/`/`playbooks/` 手写文档里的 API 是否真实存在。这些文档历史上曾大量包含 AI 自己“看起来合理”但 CAADoc 里不存在的虚构 API（已修复 40+ 处）。**当前核实状态**：

- ✅ **完全已核实**：`capabilities/` 全部 13 个、`playbooks/` 全部 14 个（除 README）、`knowledge/drawing/` 全部 2 个、`patterns/drawing/batch_drawing.md`，及部分其他 `knowledge/`/`patterns/` 文件。
- ⚠️ **尚未核实**：`patterns/` 目录其余大部分手写代码示例、部分 `knowledge/mecmod|philosophy|surface|ui|infrastructure|failure_patterns` 子文件。
- 完整清单、核实方法论、下一步入口见 **[`KNOWLEDGE_AUDIT_STATUS.md`](KNOWLEDGE_AUDIT_STATUS.md)**。
- **未核实不代表错**，只是尚未人工比对验证。AI 生成代码时引用到未核实区域的具体 API 时，应主动用 `--query`/`--check-file` 复核关键类型与方法名，而不是直接照抄。

### 已验证范围

- **测试套件**: 39 套；快速模式执行 38 套，跳过 1 套 CATIA 生命周期测试。
- **Full Integration**: 49/49 通过。
- **Full Regression quick**: 394/398；4 项 quarantine 不计作通过。
- **真实 mkmk Build（Tier B，非 quick 模式）**: 对 `TTEST` 工作区执行 `incremental_build()`，0 error，DLL 校验通过且已刷新（`Int-1 Build & Run` 套件，约 33s）。
- **适用场景**: 静态分析、预览、受控生成、模拟回归，以及对已知测试工作区的真实增量 Build 验证；新生成的项目仍须人工审查并在自己的真实工作区跑一次 Build 确认。

### 使用限制

- 不应将 quick 测试结果解释为 CAA 项目可编译、可加载或可运行。
- 不应在未审查 ChangeSet 和生成代码的情况下用于生产项目。
- CLI、MCP 和 Python API 各有用途，不能笼统宣称 CLI 可替代所有脚本。

---

## 📞 支持

### 获取帮助

1. **查看文档** - docs/ 目录包含详细指南
2. **运行测试** - 验证环境配置是否正确
3. **查看示例** - EXAMPLE_*.md 文件提供实际用例
4. **故障排查** - TROUBLESHOOTING_FLOWCHART.md 提供诊断流程

### 版本信息

**当前版本**: 3.2.1
- **发布日期**: 2026-07-15
- **状态**: 活跃开发 / ✅ 条件性生产就绪（见上方「部署前检查清单」，2026-07-20）
- **Python 版本**: 3.7+
- **CATIA 版本**: V5 R19+

---

## 📜 许可证

该技能为内部开发工具，遵循项目许可证。

---

**最后更新**: 2026-07-17  
**维护者**: Kiro AI Agent  
**状态**: ✅ 活跃开发（已通过 P0-P2 安全审计）  
**测试**: 39 套件可用
