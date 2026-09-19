<div align="center">

<img src="https://img.shields.io/badge/python-3.7%2B-blue?style=for-the-badge" />
<img src="https://img.shields.io/badge/CATIA-V5-orange?style=for-the-badge" />
<img src="https://img.shields.io/badge/license-MIT-lightgrey?style=for-the-badge" />

</div>

<div align="center">

<pre>
   ██████╗  █████╗ ██████╗ ███████╗
  ██╔════╝ ██╔══██╗██╔══██╗██╔════╝
  ██║      ███████║██║  ██║█████╗  
  ██║      ██╔══██║██║  ██║██╔══╝  
  ╚██████╗ ██║  ██║██████╔╝███████╗
   ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝
</pre>

🟥🟥🟥🟥&ensp;🟦🟦🟦🟦&ensp;🟪🟪🟪🟪&ensp;🟩🟩🟩🟩&ensp;🟪🟪🟪🟪&ensp;🟧🟧🟧🟧&ensp;🩵🩵🩵🩵

<sub>Mfg · Assembly · Geometry · Analysis · Settings · Data · Test</sub>

</div>

---

# CADE — CATIA CAA Development Engine

<div align="center">

### An AI-native development kernel for CATIA V5 CAA

*From intent to generated code, verification, build, runtime, diagnosis, and recovery.*

[**Quick Start**](#06--quick-start) · [**Why CADE?**](#02--why-cade) · [**The Loop**](#03--the-development-loop) · [**Capabilities**](#04--core-capabilities) · [**Architecture**](#05--architecture) · [**Docs**](.agents/skills/catia-caa-dev/docs/) · [**中文说明**](#-中文说明)

</div>

---

## 01 · What is CADE?

**CADE** (CATIA CAA Development Engine) is an AI-native development kernel designed specifically for Dassault Systèmes CATIA V5 CAA C++ development.

Developing CAA applications has traditionally required navigating fragmented RADE wizards, hand-crafting dozens of boilerplate files, memorizing undocumented macros, and manually diagnosing arcane compilation errors. CADE replaces this friction with a unified engineering closed loop:

```text
              User Intent
                   │
                   ▼
          ┌─────────────────┐
          │   CADE Kernel   │
          │                 │
          │ develop         │
          │ analyze         │
          │ repair          │
          └────────┬────────┘
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
   Knowledge     Planning    Impact
       │           │           │
       └───────────┼───────────┘
                   ▼
              Generation
                   │
                   ▼
               Verify
                   │
              ┌────┴────┐
              │         │
             pass      fail
              │         │
              ▼         ▼
            Build     Repair
              │         │
              ▼         │
             Run ◄──────┘
              │
              ▼
            CATIA
```

---

## 02 · Why CADE?

| Traditional CAA Development | With CADE |
|---|---|
| **Wizard-driven**: Click through dozens of RADE dialogs | **Intent-driven**: Natural language requirements mapped directly to code |
| **Manual assembly**: Stitch together 8+ files per component | **Coherent generation**: Complete component scaffolding in a single call |
| **Doc hunting**: Search fragmented SDK & CAADoc repeatedly | **Knowledge retrieval**: 5-layer grounded knowledge and API verification |
| **Manual troubleshooting**: Build, inspect logs, and guess fixes | **Automated loop**: Integrated Build → Verify → Repair pipeline |
| **Risky refactoring**: Renaming breaks `.dico`, NLS, and Imakefile | **Atomic ChangeSet**: Change preview, disk backup, and instant rollback |
| **AI hallucination**: Generic models invent non-existent CAA APIs | **Grounded verification**: Header validation against CATIA B28 SDK |
| **Tool sprawl**: Dozens of disconnected scripts and commands | **3 Kernel modes**: AI interacts with three stable, high-level modes |

---

## 03 · The Development Loop

AI interacts with only **three stable modes**. CADE handles the underlying implementation complexity, state tracking, and recovery.

```text
develop()
   │
   ├─ clarify      — Resolve requirement ambiguities with structured decision trees
   ├─ decompose    — Break compound requirements into coherent sub-intents
   ├─ plan         — Formulate dependency-ordered change plans
   ├─ retrieve     — Ground code generation with 5-layer CAA knowledge
   ├─ generate     — Scaffold complete, compilable CAA component files
   └─ verify       — Validate syntax, includes, and CAA structural rules

analyze()
   │
   ├─ inspect      — Scan workspace topology and discover CAA entities
   ├─ retrieve     — Query API signatures, SDK headers, and playbooks
   ├─ diagnose     — Detect broken references, missing exports, and misconfigurations
   └─ impact       — Compute blast-radius analysis before refactoring

repair()
   │
   ├─ diagnose     — Classify build failures, mkmk diagnostics, and lint issues
   ├─ change       — Execute targeted fix plans or safe refactoring operations
   ├─ verify       — Validate repaired code against compiler and build gates
   └─ rollback     — Cleanly restore workspace if a repair sequence regresses
```

> **Design Philosophy**: AI interacts with three modes. CADE handles the implementation complexity underneath.

---

## 04 · Core Capabilities

### 🏗️ Generate
- **Commands & StateCommands**: Full state-chart initialization, agent bindings, and lifecycle methods.
- **Dialogs & Windows**: CATDlgDialog, containers, controls, and event subscriber callbacks.
- **Workbenches & Addins**: Custom workbenches, toolbars, menus, and Addin interface implementations.
- **Components & Interfaces**: COM-style interfaces, TIE/BOA macros, code extensions, and data members.
- **Complete Scaffolding**: Produces `.h`, `.cpp`, `Imakefile.mk`, `.dico` entries, NLS message catalogs, and icons simultaneously.

### 🔨 Build & Run
- **mkmk Integration**: Incremental builds (`mkmk -u`) and clean full rebuilds.
- **Prerequisites Engine**: Automatic dependency resolution and `IdentityCard.h` verification.
- **Runtime View**: Automated assembly of `win_b64` runtime trees (`mkCreateRuntimeView`).
- **CATIA Launcher**: Process control via `mkrun` with environment initialization.
- **Telemetry & Error Parsing**: Real-time compiler log classification and error location.

### 🔍 Analyze
- **Workspace Model**: Rich domain model mapping Frameworks, Modules, Commands, Interfaces, and Workbenches.
- **Dependency Graph**: Complete inter-module dependency visualization with Mermaid export.
- **Blast-Radius Impact**: Identify all affected files, dictionaries, and callers before modifying code.
- **Header & API Verification**: Grounded checks against official Dassault B28 SDK headers.

### 🛠️ Repair & Refactor
- **Atomic Refactoring**: Rename commands/interfaces and move commands across modules safely.
- **Token-Aware Dictionaries**: Precise `.dico` line-level updates without substring corruption.
- **ChangeSet & Rollback**: Every destructive operation creates a timestamped disk backup for 100% reversible rollbacks.
- **Auto-Fix Plans**: Pre-packaged automated remediation for common CAA setup mistakes.

### 🧠 Knowledge System
- **5-Layer Retrieval**: `Capability` → `Playbook` → `Knowledge` → `Framework` → `CAADoc`.
- **Battle-Tested Playbooks**: Proven recipes for Drawing, Surface/GSD, FTA/PMI, and Native Command Investigation.
- **Failure Patterns**: Hardened guards against known CATIA SDK crashes, macro gotchas, and memory leaks.

### 🎨 Developer Experience
- **Color-Coded BMP Icons**: Automatic 22×22 anti-aliased BMP generation mapped by engineering domain.
- **Token-Optimized Responses**: MCP output filters out compiler noise, reducing AI context consumption by ~50%.
- **Editor Integrations**: Native support for Zed, Cursor, VS Code, Windsurf, and Claude Desktop via MCP.

---

## 05 · Architecture

CADE is structured around two central engines: the **Kernel Execution Pipeline** and the **Unified Retrieval Facade**.

### Kernel Execution Pipeline

```text
                 ┌──────────────┐
                 │     Kernel   │
                 └──────┬───────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
       develop       analyze        repair
          │             │             │
          └─────────────┼─────────────┘
                        ▼
              Internal Engine
                        │
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
 Requirements       Retrieval        Execution
 Planner            Knowledge        Build & Run
 Verifier           Framework        Refactor
 Repair Loop        CAADoc           Rollback
```

### 5-Layer Knowledge & Retrieval

```text
                  Retrieval Facade
                         │
      ┌──────────────────┼──────────────────┐
      ▼                  ▼                  ▼
   Catalog          ApiRegistry         HeaderMap
 (Index/Playbooks)  (Verified APIs)   (B28 SDK Headers)
      │                  │                  │
      └──────────────────┼──────────────────┘
                         ▼
                 Method / UseCase
                         │
                         ▼
                 Official CAADoc
```

> **Core Tenet**: Capability grows by accumulating structured knowledge assets, not by expanding code complexity.

---

## 06 · Quick Start

### 1. Clone & Install

```bash
# 1. Clone CADE repository
git clone https://github.com/chenlei-gh/CADE.git

# 2. Copy the .agents folder into your CAA workspace
cp -r ./CADE/.agents /path/to/your/caa/workspace/

# 3. Install optional icon generation dependency
pip install Pillow
```

### 2. Open in Editor

- **Zed**: Works out of the box (reads `.agents/skills/`).
- **Cursor / VS Code / Windsurf / Claude**: Run `python .agents/skills/catia-caa-dev/tools/setup_mcp.py` to configure the MCP server.

### 3. Prompt Your AI Agent

Simply instruct your AI editor in natural language:

```text
"Create a CATIA state command named MyAnalysisCmd in AnalysisModule.m
with a dialog containing an OK/Cancel button, and register it to MyWorkbench."
```

CADE automatically handles clarification, planning, code generation, dictionary updates, build verification, and runtime deployment.

---

## 07 · Verification & Reliability

CADE maintains strict quality gates verified through automated test suites:

- **Static Verification**: Validates generated C++ syntax, header includes, macro expansions, and Imakefile definitions without requiring a full compiler run.
- **Architecture Contracts**: Enforces layer isolation, single-facade retrieval access, and clean module boundaries.
- **Semantic & Schema Checks**: Ensures Rich Domain Model integrity, ChangeSet cleanliness, and 100% reversible rollback execution.
- **Fault-Injection & Resiliency**: Validates recovery from corrupt manifests, broken builds, and interrupted operations.
- **Lifecycle Verification**: Exercises end-to-end CAA build (`mkmk`) and CATIA runtime launch (`CNEXT`).

Run the verification suite locally:

```bash
# Fast test suite (skips live CATIA launch)
python .agents/skills/catia-caa-dev/tests/test_master.py --quick

# Full regression suite (includes CATIA lifecycle)
python .agents/skills/catia-caa-dev/tests/test_master.py
```

> **Test Baseline**: 42 suites (41 quick + 1 CATIA lifecycle) · 43 test files · 100% pass rate.

---

## 08 · Scope & Boundaries

To keep engineering goals focused and reliable, CADE maintains clear functional boundaries:

| CADE is | CADE is not |
|---|---|
| **CAA development automation kernel** | CATIA itself |
| **AI development assistant for CAA engineers** | General-purpose CAD automation |
| **Complete CAA component scaffolding generator** | Your proprietary engineering algorithms |
| **Build, runtime, diagnosis & rollback tooling** | A replacement for CATIA/RADE or MSVC compilers |
| **Grounded CAA knowledge & retrieval engine** | A generic, hallucination-prone coding assistant |

> **CADE is a developer tool for CATIA CAA. It is not an end-user CATIA product.**

---

## 09 · Documentation

- **[SKILL Specification](.agents/skills/catia-caa-dev/SKILL.md)** — Comprehensive agent instructions and execution contracts.
- **[Architecture Guide](.agents/skills/catia-caa-dev/docs/references/ARCHITECTURE.md)** — Deep dive into Kernel, Domain Model, and ChangeSet internals.
- **[Retrieval Architecture](.agents/skills/catia-caa-dev/docs/architecture/retrieval.md)** — Knowledge retrieval facade and indexing contracts.
- **[Deployment & Setup](.agents/skills/catia-caa-dev/docs/guides/DEPLOYMENT_GUIDE.md)** — Environment setup and upgrade procedures.
- **[Examples](.agents/skills/catia-caa-dev/docs/examples/)** — Working examples of Commands, Extensions, and Multi-Interface components.
- **[Changelog](.agents/skills/catia-caa-dev/CHANGELOG.md)** — Version history and architecture evolution records.

---

## 10 · License

Distributed under the [MIT License](.agents/skills/catia-caa-dev/LICENSE).  
Copyright © [chenlei-gh](https://github.com/chenlei-gh).

---

## 🇨🇳 中文说明

### 01 · 什么是 CADE？

**CADE**（CATIA CAA Development Engine）是专为达索系统 CATIA V5 CAA C++ 开发设计的 **AI 原生开发内核**。

传统 CAA 开发门槛高、RADE 向导繁琐、头文件与宏规则复杂、编译报错难以定位。CADE 将自然语言需求转化为标准的 CAA 工程资产，串联起 **需求澄清 → 规划生成 → 静态验证 → mkmk 构建 → CATIA 运行 → 诊断修复 → 原子回滚** 的完整开发闭环。

### 02 · 为什么选择 CADE？

| 传统 CAA 开发 | 使用 CADE |
|---|---|
| **向导繁琐**：在 RADE 界面反复点击向导 | **意图驱动**：自然语言直接映射到标准代码 |
| **手工拼装**：每个组件手动维护 8 个以上关联文件 | **内聚生成**：一次调用生成完整的组件脚手架 |
| **反复查阅**：官方 SDK / CAADoc 查阅低效 | **知识检索**：5 层检索门面与真实 API 校验防幻觉 |
| **人工排错**：编译失败后手动查日志、猜原因 | **闭环修复**：构建 → 验证 → 修复全自动管线 |
| **重构高危**：重命名极易漏改 `.dico`、NLS 与 Imakefile | **原子重构**：ChangeSet 变更预览、备份与秒级回滚 |
| **工具碎片**：数十个独立脚本，调用链路复杂 | **内核统一**：AI 仅需交互 3 种极简稳定模式 |

### 03 · 开发闭环（3 种模式）

CADE 为 AI 提供 3 种高层稳定模式，隐藏底层的状态管理与执行复杂度：

- `develop()`：需求澄清（决策树）、复合意图分解、生成任务规划、知识检索、代码脚手架生成、规则静态验证。
- `analyze()`：工作区结构拓扑扫描、Mermaid 依赖图导出、改动影响面（Blast Radius）分析、API 真实性校验。
- `repair()`：编译报错分类、自动修复计划执行、安全重构、回滚恢复。

> **核心哲学**：AI 专注于高层工程意图；CADE 负责底层工程细节与可逆安全保障。

### 04 · 快速开始

1. **克隆仓库**：
   ```bash
   git clone https://github.com/chenlei-gh/CADE.git
   ```
2. **复制配置**：将 `CADE/.agents` 文件夹复制到你的 CAA 工程根目录下。
3. **安装依赖**：`pip install Pillow`（用于本地生成领域分类 BMP 图标）。
4. **开始开发**：
   - **Zed**：开箱即用。
   - **Cursor / VS Code / Windsurf / Claude**：运行 `python .agents/skills/catia-caa-dev/tools/setup_mcp.py` 配置 MCP。
5. **在 AI 编辑器中提问**：
   > *"在 AnalysisModule.m 中创建一个名为 MyAnalysisCmd 的状态机命令，带确定/取消对话框，并注册到工作台。"*

### 05 · 项目边界

- **CADE 是**：CAA 开发自动化内核、AI 辅助编程中间件、CAA 结构脚手架生成器与构建诊断工具。
- **CADE 不是**：CATIA 软件本身、通用 CAD 自动化工具、用户专有业务算法的替代者，也不是 RADE/编译器的替代品。

> **CADE 是面向 CATIA CAA 开发者的工程工具，而非终端用户的 CATIA 应用程序。**
