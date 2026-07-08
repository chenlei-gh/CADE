<div align="center">

<img src="https://img.shields.io/badge/tests-700%2B-brightgreen?style=for-the-badge" />
<img src="https://img.shields.io/badge/python-3.7%2B-blue?style=for-the-badge" />
<img src="https://img.shields.io/badge/CATIA-V5%20%7C%20V6-orange?style=for-the-badge" />
<img src="https://img.shields.io/badge/license-MIT-lightgrey?style=for-the-badge" />

</div>

---

# CADE — CATIA CAA Development Engine

<div align="center">

### 🎯 AI-Powered CATIA CAA Development. *One command. Eight files. Done.*

From "I need a dialog command" to compiling code — without touching RADE wizards.

**[Quick Start](#-quick-start) · [Why CADE?](#-why-cade) · [Commands](#-what-it-can-do) · [Docs](.agents/skills/catia-caa-dev/docs/) · [中文](#-中文)**

</div>

---

## ⚡ Quick Start

```bash
# 1. Clone into your CAA project
git clone https://github.com/chenlei-gh/CADE.git
cp -r cade/.agents /path/to/your/caa/project/

# 2. That's it. Open in your editor.
#    CADE auto-detects CATIA. Zero config.
```

> [!TIP]
> **Zed** — works out of the box.  
> **Claude / Cursor / VS Code / Windsurf** — run `python .agents/skills/catia-caa-dev/tools/setup_mcp.py`

<details><summary>📋 Manual MCP setup</summary>

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
</details>

---

## 🔥 Why CADE?

| ❌ Without CADE | ✅ With CADE |
|---|---|
| Manually create 8 files per command | `cade create command MyCmd MyModule` |
| Run RADE wizards, click through dialogs | Tell AI: "create a command with dialog" |
| `mkmk -u` then `mkCreateRuntimeView` then `CNEXT` | `cade build && cade run` |
| Guess what's broken after refactoring | `cade diagnose && cade fix --apply` |
| No way to undo a mistaken delete | `cade rollback --id latest` |

---

## 🧰 What It Can Do

### 🏗 Create
```bash
cade create command MyCmd MyModule --dialog --wb MyWb
cade create feature  MyFeature MyModule
cade create extension MyExt CATPart MyModule
```
→ Generates `.cpp`, `.h`, Header, Catalog, NLS, Icon, Dictionary, Imakefile — **all 8 files in one call**.

### 🔨 Build & Run
```bash
cade build                          # incremental (mkmk -u)
cade build --full --threads 8       # full rebuild, 8 threads
cade run                            # start CATIA Runtime View
cade run --macro test.CATScript     # run a macro
cade run --stop                     # stop all CATIA processes
```

### 🔍 Analyze & Fix
```bash
cade analyze                        # full workspace scan
cade analyze --graph                # Mermaid dependency diagram
cade diagnose                       # find issues
cade fix --apply                    # auto-fix broken references
cade validate                       # integrity check
```

### ♻️ Refactor & Rollback
```bash
cade refactor rename OldCmd NewCmd --module MyModule
cade refactor move MyCmd --from M1 --to M2
cade snapshot                     # checkpoint
cade rollback --id latest         # undo anything
```

### 🤖 AI & Docs
```bash
cade suggest                      # AI recommends next action
cade docs                         # auto-generate documentation
cade prereq MyModule              # view prerequisites
cade rv                           # create Runtime View
cade test --quick                 # run all 18 test suites (~8s)
```

> 🔌 Also available as **MCP Server** (38 tools) and **Python API** (~80 functions) — [see docs](.agents/skills/catia-caa-dev/docs/).

---

## 🏛 Architecture

```mermaid
graph TD
    A[AI / CLI / MCP] --> B[Specification]
    B --> C[Validation]
    C --> D[Generator]
    D --> E[ChangeSet]
    E --> F[File System]

    A --> G[CodeModel<br/>10 Entities]
    G --> H[DependencyGraph<br/>9 Relation Types]
    G --> I[Diagnostics + FixPlan]
    G --> J[Refactor Engine]

    A --> K[Build Engine<br/>35 Commands]
    A --> L[Runtime Engine<br/>7 Commands]
    A --> M[Rollback System]

    N[Knowledge System<br/>9 Knowledge + 6 Pattern + 1 Example + Catalog] --> G
```

> **Philosophy**: Capability grows by accumulating knowledge assets, not by modifying code.

---

## 📊 By the Numbers

| | |
|---|---|
| **Test Suites** | 18 (L1-L7 + Integration + Audit) |
| **Test Cases** | 700+ |
| **Pass Rate** | 100% |
| **Templates** | 25+ |
| **APIs** | 15 (Intent + Action) |
| **CLI Commands** | 19 |
| **MCP Tools** | 38 |
| **Build Commands** | 35 |
| **Spec Types** | 8 |
| **Refactor Operations** | 3 |
| **Domain Entities** | 10 |
| **Knowledge Assets** | 16 (9K + 6P + 1E) |

---

## 📂 Project Structure

```
your_project/
├── .agents/skills/catia-caa-dev/   ← CADE (drop-in)
│   ├── skills/                     ← Engine (22 modules)
│   ├── templates/                  ← 25+ code templates
│   ├── knowledge/                  ← CAA API reference (9 domains)
│   ├── patterns/                   ← Architecture patterns (6 types)
│   ├── examples/                   ← Real CAA projects
│   ├── tests/                      ← 18 suites, 700+ cases
│   ├── tools/                      ← Setup, validation, utilities
│   ├── config/                     ← Editor MCP templates
│   └── docs/                       ← Full documentation
├── MyFramework.edu/
├── MyModule.m/
└── ...
```

---

## 🇨🇳 中文

### 是什么？

**CADE** 是 CATIA CAA V5/V6 的 AI 驱动开发引擎。用自然语言告诉 AI "创建一个带对话框的命令"，引擎自动生成 8 个文件。一句命令替代 RADE 向导的多次点击。

```bash
cade create command 我的命令 我的模块 --dialog --wb 我的工作台
```

### 核心理念

能力增长靠沉淀知识资产，不靠修改代码。

| 功能 | |
|------|---|
| 🏗 **一键创建** | 一次调用生成 8 个文件 |
| 🔍 **诊断修复** | 自动发现并修复破损引用 |
| ♻️ **安全重构** | 重命名/移动，自动更新所有引用 |
| ⏪ **完整回滚** | 每步操作有备份，随时回退 |
| 📊 **依赖图** | 9 种关系，Mermaid 可视化 |
| 📚 **知识系统** | API 文档 + 模式 + 示例，AI 按需加载 |

---

## 📜 License

MIT © [chenlei-gh](https://github.com/chenlei-gh)

---

<div align="center">

**[📖 Documentation](.agents/skills/catia-caa-dev/docs/) · [🏗 Architecture](.agents/skills/catia-caa-dev/docs/references/ARCHITECTURE.md) · [📝 Changelog](.agents/skills/catia-caa-dev/CHANGELOG.md)**

</div>
