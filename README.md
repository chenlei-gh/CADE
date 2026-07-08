# CADE v2.1.0

<div align="center">

```
   ██████╗  █████╗ ██████╗ ███████╗
  ██╔════╝ ██╔══██╗██╔══██╗██╔════╝
  ██║      ███████║██║  ██║█████╗  
  ██║      ██╔══██║██║  ██║██╔══╝  
  ╚██████╗ ██║  ██║██████╔╝███████╗
   ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝
                                       
  CATIA CAA Development Engine
```

[![Tests](https://img.shields.io/badge/tests-147%2B-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.7%2B-blue)]()
[![CATIA](https://img.shields.io/badge/CATIA-V5%20%7C%20V6-orange)]()

🌐 [English](#english) | [中文](#chinese)

</div>

---

<a name="english"></a>

## 🇬🇧 English

### What You Need

- Python 3.7+
- CATIA V5 or V6 installed

### Install

1. Clone the repository
2. Copy `.agents` into your CAA project root

```bash
git clone https://github.com/chenlei-gh/CADE.git
cp -r cade/.agents /path/to/your/caa/project/
```

3. Open the project in your editor. Done.

```
your_project/
├── .agents/skills/catia-caa-dev/   ← CADE
├── MyFramework.edu/
├── MyModule.m/
└── ...
```

First use auto-detects CATIA. Zero manual configuration.

### 🚀 MCP Auto-Setup

CADE comes with an auto-setup tool that detects your editors and configures MCP automatically:

```bash
# One-click — auto-detects and configures all editors
python .agents/skills/catia-caa-dev/tools/setup_mcp.py

# Or configure a specific editor
python .agents/skills/catia-caa-dev/tools/setup_mcp.py --editor cursor

# Preview changes without writing
python .agents/skills/catia-caa-dev/tools/setup_mcp.py --dry-run
```

> 🟢 **Zed users**: Nothing to do — SKILL.md is auto-detected.  
> 🟡 **Claude Desktop / Cursor / VS Code / Windsurf**: Run the setup script above.

<details>
<summary>📋 Manual MCP config (click to expand)</summary>

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

Config templates: `config/editors/`
- `claude_desktop.json` → `%APPDATA%/Claude/claude_desktop_config.json`
- `cursor.json` → `.cursor/mcp.json`
- `vscode.json` → `.vscode/mcp.json`
- `windsurf.json` → `.windsurf/mcp.json`
</details>

### Core Features

| Feature | Description |
|---------|-------------|
| **One-Shot Command** | One call → .cpp, .h, Header, Catalog, NLS, Icon, Dictionary, Imakefile |
| **Diagnose & Auto-Fix** | Detects missing entries, broken refs. Generates executable FixPlan |
| **Safe Refactoring** | Rename/move commands, interfaces, modules. Auto-updates all references |
| **Snapshot & Diff** | Versioned workspace snapshots. AI sees exactly what changed |
| **Dependency Graph** | 9 relation types, Mermaid visualization, cascade delete |
| **Full Rollback** | Every operation backed up. Rollback to any point |
| **CAA Knowledge System** | API docs, dev patterns, real examples. AI loads on demand |

### Interfaces

**CLI** — 19 commands for terminal

```bash
cade create command <name> <module> --dialog --wb <wb>   # Create command
cade create feature <name> <module>                      # Create Feature
cade create extension <name> <target> <module>           # Create Extension

cade build                        # mkmk -u (incremental)
cade build --full                 # mkmk -a (full rebuild)
cade build --clean                # mkmk -c (clean+build)
cade build --threads 8            # Multi-threaded

cade run                          # Start CATIA
cade run --stop                   # Stop CATIA
cade run --macro script.CATScript # Run macro
cade run --status                 # Check if running

cade analyze                      # Full workspace analysis
cade analyze --modules            # List modules
cade analyze --deps MyCmd         # Entity dependencies
cade analyze --graph              # Mermaid dependency diagram

cade diagnose                     # Find issues
cade fix                          # Diagnose + auto-fix
cade fix --apply                  # Apply fixes directly

cade refactor rename <old> <new> --module <m>
cade refactor move <cmd> --from <m1> --to <m2>

cade snapshot                     # Workspace snapshot
cade snapshot --diff              # Diff from previous
cade rollback --list              # List backup points
cade rollback --id 20260707_...   # Rollback

cade validate                     # Workspace integrity check
cade suggest                      # AI-suggested next action
cade expose <comp> <module>       # Expose component service
cade prereq <target>              # View prerequisite
cade rv                           # Create Runtime View
cade docs                         # Auto-generate project docs
cade version                      # CATIA + CADE version info
cade test --quick                 # Run test suite
```

**MCP Server** — 32 tools for all AI editors

Tools: `analyze_workspace`, `create_executable_command`, `diagnose_and_fix`, `rename_command`, `incremental_build`, `start_catia`, `stop_catia`, `rollback`, `workspace_snapshot`, and 23 more.

**Python API** — ~80 functions for direct use

```python
from intents import create_executable_command, create_feature, suggest_next_action
from diagnostics import diagnose_workspace, diagnose_and_fix
from refactor import rename_command, move_command, rename_module
from build import incremental_build, full_build, create_runtime_view
from run import start_catia_runtime, stop_catia, run_catia_macro
from actions import ActionContext, analyze_workspace, get_dependencies

ctx = ActionContext()  # auto-detects workspace
```

### Standout Features

| Feature | Value |
|---------|-------|
| **Intent Layer** | "Create command with dialog" → engine handles 8 file operations |
| **Specification Layer** | Contract between AI and Generator. AI makes Spec, Generator consumes Spec |
| **Rich Domain Model** | 10 entities know their own paths, registration, NLS blocks, file structures |
| **Architecture Guarantees** | Verified: layers don't cross, ChangeSet is sole file writer |
| **Knowledge System** | `knowledge/` (API docs) + `patterns/` (arch patterns) + `examples/` (real CAA code) |

### Architecture

```
AI / CLI / MCP
     ↓
Specification → Validation → Generator → ChangeSet → File System
     ↓
CodeModel (10 entities) + DependencyGraph + Diagnostics + FixPlan
     ↓
Build Engine (35 cmds) + Runtime Engine (7 cmds) + Rollback
     ↓
Knowledge System (按需加载 — Catalog 索引)
```

**Core Philosophy**: Capability grows by accumulating knowledge assets, not by modifying code.

### Quick Test

```bash
python tests/test_master.py --quick   # 20s, all suites
```

> [🌐 中文](#chinese)

---

<a name="chinese"></a>

## 🇨🇳 中文

### 需要什么

- Python 3.7+
- 已安装 CATIA V5 或 V6

### 安装

1. 克隆仓库
2. 把 `.agents` 复制到 CAA 项目根目录

```bash
git clone https://github.com/chenlei-gh/CADE.git
cp -r cade/.agents /你的/CAA/项目/路径/
```

3. 用编辑器打开项目。完成。

```
你的项目/
├── .agents/skills/catia-caa-dev/   ← CADE
├── MyFramework.edu/
├── MyModule.m/
└── ...
```

首次使用自动检测 CATIA。零手动配置。

### 🚀 MCP 自动配置

CADE 自带自动配置工具，检测你的编辑器并自动配置 MCP：

```bash
# 一键配置 — 自动检测并配置所有编辑器
python .agents/skills/catia-caa-dev/tools/setup_mcp.py

# 或指定编辑器
python .agents/skills/catia-caa-dev/tools/setup_mcp.py --editor cursor

# 预览变更（不写入文件）
python .agents/skills/catia-caa-dev/tools/setup_mcp.py --dry-run
```

> 🟢 **Zed 用户**：无需操作 — SKILL.md 自动识别。  
> 🟡 **Claude Desktop / Cursor / VS Code / Windsurf**：运行上述配置脚本即可。

<details>
<summary>📋 手动配置（点击展开）</summary>

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

配置模板：`config/editors/`
- `claude_desktop.json` → `%APPDATA%/Claude/claude_desktop_config.json`
- `cursor.json` → `.cursor/mcp.json`
- `vscode.json` → `.vscode/mcp.json`
- `windsurf.json` → `.windsurf/mcp.json`
</details>

### 核心功能

| 功能 | 说明 |
|------|------|
| **一键创建命令** | 一次调用生成 .cpp/.h/Header/Catalog/NLS/Icon/Dictionary/Imakefile |
| **诊断与自动修复** | 发现缺失条目、破损引用，生成可执行 FixPlan |
| **安全重构** | 重命名/移动命令、接口、模块，自动更新所有引用 |
| **快照与 Diff** | 版本化工作区快照，AI 清楚看到每一步变化 |
| **依赖图** | 9 种关系类型，Mermaid 可视化，级联删除 |
| **完整回滚** | 每个操作自动备份，可回滚到任意节点 |
| **CAA 知识系统** | API 文档、开发模式、真实示例，AI 按需加载 |

### 接口

**CLI** — 19 个终端命令

```bash
cade create command <名称> <模块> --dialog --wb <工作台>   # 创建命令
cade create feature <名称> <模块>                          # 创建 Feature
cade create extension <名称> <目标> <模块>                 # 创建扩展

cade build                        # mkmk -u（增量编译）
cade build --full                 # mkmk -a（全量编译）
cade build --clean                # mkmk -c（清理编译）
cade build --threads 8            # 多线程编译

cade run                          # 启动 CATIA
cade run --stop                   # 停止 CATIA
cade run --macro 脚本.CATScript   # 运行宏
cade run --status                 # 检查运行状态

cade analyze                      # 完整工作区分析
cade analyze --modules            # 列出模块
cade analyze --deps MyCmd         # 实体依赖查询
cade analyze --graph              # Mermaid 依赖图

cade diagnose                     # 发现问题
cade fix                          # 诊断 + 自动修复
cade fix --apply                  # 直接应用修复

cade refactor rename <旧名> <新名> --module <模块>
cade refactor move <命令> --from <源> --to <目标>

cade snapshot                     # 工作区快照
cade snapshot --diff              # 与上次差异对比
cade rollback --list              # 列出回滚点
cade rollback --id 20260707_...   # 回滚

cade validate                     # 工作区完整性检查
cade suggest                      # AI 推荐下一步
cade expose <组件> <模块>         # 暴露组件服务
cade prereq <目标>                # 查看依赖
cade rv                           # 创建 Runtime View
cade docs                         # 自动生成项目文档
cade version                      # CATIA + CADE 版本信息
cade test --quick                 # 运行测试套件
```

**MCP Server** — 32 个工具，支持所有 AI 编辑器

工具列表：`analyze_workspace`、`create_executable_command`、`diagnose_and_fix`、`rename_command`、`incremental_build`、`start_catia`、`stop_catia`、`rollback`、`workspace_snapshot` 等 23 个。

**Python API** — ~80 个函数直接调用

```python
from intents import create_executable_command, create_feature, suggest_next_action
from diagnostics import diagnose_workspace, diagnose_and_fix
from refactor import rename_command, move_command, rename_module
from build import incremental_build, full_build, create_runtime_view
from run import start_catia_runtime, stop_catia, run_catia_macro
from actions import ActionContext, analyze_workspace, get_dependencies

ctx = ActionContext()  # 自动检测工作区
```

### 突出能力

| 能力 | 价值 |
|------|------|
| **意图层** | "创建带对话框的命令" → 引擎自动处理 8 个文件操作 |
| **Specification 层** | AI 和 Generator 之间的契约。AI 生成 Spec，Generator 消费 Spec |
| **Rich Domain Model** | 10 个实体知道自己的一切：路径、注册项、NLS 块、文件结构 |
| **架构保证** | 已验证：层次不越界，ChangeSet 是唯一文件写入者 |
| **知识系统** | `knowledge/`（API 文档）+ `patterns/`（架构模式）+ `examples/`（真实 CAA 代码）|

### 架构

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

**核心理念**：系统能力增长通过沉淀知识资产实现，而非修改代码。

### Quick Test

```bash
python tests/test_master.py --quick   # 20 秒，全部套件
```

> [🇬🇧 English](#english)

---

## 📜 License

MIT — see [LICENSE](.agents/skills/catia-caa-dev/LICENSE)

---

<div align="center">

**[文档](.agents/skills/catia-caa-dev/docs/) · [架构](.agents/skills/catia-caa-dev/docs/references/ARCHITECTURE.md) · [更新日志](.agents/skills/catia-caa-dev/CHANGELOG.md)**

</div>
