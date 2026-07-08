# CADE v2.0.0

<div align="center">

<h1>🔧 CADE</h1>

**CATIA CAA Development Engine**

AI-powered CAA development lifecycle engine

<br>

[![Tests](https://img.shields.io/badge/tests-150%2B-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.7%2B-blue)]()
[![CATIA](https://img.shields.io/badge/CATIA-V5%20%7C%20V6-orange)]()
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

<br>

🌐 [English](#english) | [中文](#chinese)

</div>

---

<a name="english"></a>

## 🇬🇧 English

> AI-powered CATIA V5 CAA development lifecycle engine with rich domain model, knowledge system, and intelligent automation.

---

### ⚡ Quick Start

**1. Clone repository**
```bash
git clone https://github.com/chenlei-gh/CADE.git
```

**2. Copy `.agents` to your CAA project**
```bash
cp -r CADE/.agents /path/to/your/caa/project/
```

**3. Open in Zed. Done.**
```
your_project/
├── .agents/skills/catia-caa-dev/   ← CADE
├── MyFramework.edu/
├── MyModule.m/
└── ...
```

First use auto-detects CATIA. Zero manual configuration.

---

### 🎯 Core Features

**🚀 One-Shot Operations**
- Create command → .cpp, .h, Header, Catalog, NLS, Icon, Dictionary, Imakefile in one call
- AI intent layer handles complex workflows automatically

**🔍 Diagnose & Auto-Fix**
- Detects missing entries, broken references
- Generates executable FixPlan
- One-click apply fixes

**♻️ Safe Refactoring**
- Rename/move commands, interfaces, modules
- Auto-updates all references across workspace
- Full rollback support

**📊 Dependency Analysis**
- 9 relation types tracked
- Mermaid visualization
- Cascade delete with safety checks

**💾 Snapshot & Rollback**
- Versioned workspace snapshots
- Diff between states
- Rollback to any point

**🧠 Knowledge System**
- 9 Knowledge modules (mecmod, part, product, ui, infrastructure)
- 6 Development patterns (analyzers, workflows, UI patterns)
- Real CAA code examples
- Catalog-based indexing for AI

---

### 🛠️ Interfaces

<details>
<summary><b>CLI</b> — 19 commands</summary>

```bash
# Create
cade create command <name> <module> --dialog --wb <wb>
cade create feature <name> <module>
cade create extension <name> <target> <module>

# Build
cade build                  # Incremental (mkmk -u)
cade build --full           # Full rebuild (mkmk -a)
cade build --clean          # Clean + build (mkmk -c)
cade build --threads 8      # Multi-threaded

# Run
cade run                    # Start CATIA
cade run --stop             # Stop CATIA
cade run --macro script     # Run macro
cade run --status           # Check status

# Analyze
cade analyze                # Full workspace analysis
cade analyze --modules      # List modules
cade analyze --deps MyCmd   # Entity dependencies
cade analyze --graph        # Mermaid diagram

# Fix
cade diagnose               # Find issues
cade fix                    # Diagnose + generate plan
cade fix --apply            # Auto-apply fixes

# Refactor
cade refactor rename <old> <new> --module <m>
cade refactor move <cmd> --from <m1> --to <m2>

# Snapshot
cade snapshot               # Take snapshot
cade snapshot --diff        # Diff from previous
cade rollback --list        # List restore points
cade rollback --id <id>     # Rollback

# Utils
cade validate               # Integrity check
cade suggest                # AI suggestions
cade prereq <target>        # View dependencies
cade rv                     # Create Runtime View
cade docs                   # Generate docs
cade version                # Version info
```
</details>

<details>
<summary><b>MCP Server</b> — 32 tools for Claude/Cursor</summary>

**Config:**
```json
{
  "mcpServers": {
    "cade": {
      "command": "python",
      "args": ["skills/mcp_server.py"],
      "cwd": ".agents/skills/catia-caa-dev"
    }
  }
}
```

**Tools:** `analyze_workspace`, `create_executable_command`, `diagnose_and_fix`, `rename_command`, `incremental_build`, `start_catia`, `stop_catia`, `rollback`, `workspace_snapshot`, and 23 more.
</details>

<details>
<summary><b>Python API</b> — ~80 functions</summary>

```python
from intents import create_executable_command, create_feature
from diagnostics import diagnose_workspace, diagnose_and_fix
from refactor import rename_command, move_command
from build import incremental_build, full_build
from run import start_catia_runtime, stop_catia
from actions import ActionContext, analyze_workspace

ctx = ActionContext()  # Auto-detects workspace
```
</details>

---

### 🏗️ Architecture

```
AI / CLI / MCP
     ↓
Specification → Validation → Generator → ChangeSet → File System
     ↓
CodeModel (10 entities) + DependencyGraph + Diagnostics + FixPlan
     ↓
Build Engine (35 cmds) + Runtime Engine (7 cmds) + Rollback
     ↓
Knowledge System (on-demand loading via Catalog)
```

**Philosophy:** Capability grows by accumulating knowledge assets, not modifying code.

---

### 📦 Standout Features

| Feature | Value |
|---------|-------|
| **Intent Layer** | "Create command with dialog" → 8 file operations handled |
| **Specification Layer** | Contract between AI and Generator |
| **Rich Domain Model** | 10 entities: Command, Module, Feature, Dialog, Interface... |
| **Architecture Tests** | Verified layer boundaries, single writer pattern |
| **Knowledge System** | CAA API docs + patterns + real examples |

---

### 🧪 Quick Test

```bash
python tests/test_master.py --quick   # 20s, all suites
```

---

> [🌐 中文](#chinese)

---

<a name="chinese"></a>

## 🇨🇳 中文

> AI 驱动的 CATIA V5 CAA 开发生命周期引擎，具有丰富的领域模型、知识系统和智能自动化。

---

### ⚡ 快速开始

**1. 克隆仓库**
```bash
git clone https://github.com/chenlei-gh/CADE.git
```

**2. 复制 `.agents` 到 CAA 项目**
```bash
cp -r CADE/.agents /你的/CAA/项目/路径/
```

**3. 用 Zed 打开项目。完成。**
```
你的项目/
├── .agents/skills/catia-caa-dev/   ← CADE
├── MyFramework.edu/
├── MyModule.m/
└── ...
```

首次使用自动检测 CATIA。零手动配置。

---

### 🎯 核心功能

**🚀 一键操作**
- 创建命令 → 一次调用生成 .cpp/.h/Header/Catalog/NLS/Icon/Dictionary/Imakefile
- AI 意图层自动处理复杂工作流

**🔍 诊断与自动修复**
- 检测缺失条目、破损引用
- 生成可执行 FixPlan
- 一键应用修复

**♻️ 安全重构**
- 重命名/移动命令、接口、模块
- 自动更新工作区所有引用
- 完整回滚支持

**📊 依赖分析**
- 追踪 9 种关系类型
- Mermaid 可视化
- 级联删除（带安全检查）

**💾 快照与回滚**
- 版本化工作区快照
- 状态差异对比
- 回滚到任意节点

**🧠 知识系统**
- 9 个知识模块（mecmod、part、product、ui、infrastructure）
- 6 个开发模式（分析器、工作流、UI 模式）
- 真实 CAA 代码示例
- 基于 Catalog 的 AI 索引

---

### 🛠️ 接口

<details>
<summary><b>CLI</b> — 19 个命令</summary>

```bash
# 创建
cade create command <名称> <模块> --dialog --wb <工作台>
cade create feature <名称> <模块>
cade create extension <名称> <目标> <模块>

# 编译
cade build                  # 增量编译 (mkmk -u)
cade build --full           # 全量编译 (mkmk -a)
cade build --clean          # 清理编译 (mkmk -c)
cade build --threads 8      # 多线程编译

# 运行
cade run                    # 启动 CATIA
cade run --stop             # 停止 CATIA
cade run --macro 脚本       # 运行宏
cade run --status           # 检查状态

# 分析
cade analyze                # 完整工作区分析
cade analyze --modules      # 列出模块
cade analyze --deps MyCmd   # 实体依赖
cade analyze --graph        # Mermaid 图表

# 修复
cade diagnose               # 发现问题
cade fix                    # 诊断 + 生成计划
cade fix --apply            # 自动应用修复

# 重构
cade refactor rename <旧名> <新名> --module <m>
cade refactor move <命令> --from <m1> --to <m2>

# 快照
cade snapshot               # 拍摄快照
cade snapshot --diff        # 与上次对比
cade rollback --list        # 列出恢复点
cade rollback --id <id>     # 回滚

# 工具
cade validate               # 完整性检查
cade suggest                # AI 建议
cade prereq <目标>          # 查看依赖
cade rv                     # 创建 Runtime View
cade docs                   # 生成文档
cade version                # 版本信息
```
</details>

<details>
<summary><b>MCP Server</b> — 32 个工具（Claude/Cursor）</summary>

**配置:**
```json
{
  "mcpServers": {
    "cade": {
      "command": "python",
      "args": ["skills/mcp_server.py"],
      "cwd": ".agents/skills/catia-caa-dev"
    }
  }
}
```

**工具:** `analyze_workspace`、`create_executable_command`、`diagnose_and_fix`、`rename_command`、`incremental_build`、`start_catia`、`stop_catia`、`rollback`、`workspace_snapshot` 等 23 个。
</details>

<details>
<summary><b>Python API</b> — ~80 个函数</summary>

```python
from intents import create_executable_command, create_feature
from diagnostics import diagnose_workspace, diagnose_and_fix
from refactor import rename_command, move_command
from build import incremental_build, full_build
from run import start_catia_runtime, stop_catia
from actions import ActionContext, analyze_workspace

ctx = ActionContext()  # 自动检测工作区
```
</details>

---

### 🏗️ 架构

```
AI / CLI / MCP
     ↓
Specification → Validation → Generator → ChangeSet → File System
     ↓
CodeModel (10 实体) + DependencyGraph + Diagnostics + FixPlan
     ↓
Build Engine (35 命令) + Runtime Engine (7 命令) + Rollback
     ↓
Knowledge System (按需加载 — Catalog 索引)
```

**理念：**系统能力增长通过沉淀知识资产实现，而非修改代码。

---

### 📦 突出能力

| 能力 | 价值 |
|------|------|
| **意图层** | "创建带对话框的命令" → 处理 8 个文件操作 |
| **Specification 层** | AI 和 Generator 之间的契约 |
| **Rich Domain Model** | 10 个实体：Command、Module、Feature、Dialog、Interface... |
| **架构测试** | 验证层边界、单一写入者模式 |
| **知识系统** | CAA API 文档 + 模式 + 真实示例 |

---

### 🧪 快速测试

```bash
python tests/test_master.py --quick   # 20 秒，全部套件
```

---

> [🇬🇧 English](#english)

---

<div align="center">

## 📜 License

MIT — see [LICENSE](.agents/skills/catia-caa-dev/LICENSE)

<br>

**[文档](docs/) · [架构](docs/references/ARCHITECTURE.md) · [更新日志](CHANGELOG.md)**

</div>
