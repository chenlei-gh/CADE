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

[**Quick Start**](#06--quick-start) · [**Why CADE?**](#02--why-cade) · [**The Loop**](#03--the-development-loop) · [**Capabilities**](#04--core-capabilities) · [**Example**](#07--end-to-end-example) · [**Architecture**](#05--architecture) · [**Docs**](.agents/skills/catia-caa-dev/docs/) · [**License**](#11--license--disclaimer) · [**中文说明**](#-中文说明)

</div>

---

## 01 — What is CADE?

**CADE** (CATIA CAA Development Engine) is an AI-native development kernel designed specifically for Dassault Systèmes CATIA V5 CAA C++ development.

Developing CAA applications has traditionally required navigating fragmented RADE wizards, hand-crafting boilerplate across multiple directories, memorizing complex macros, and manually diagnosing arcane compiler errors. CADE replaces this friction with an integrated development closed loop:

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

## 02 — Why CADE?

| Traditional CAA Development | With CADE |
|---|---|
| **Wizard-driven**: Click through dozens of RADE dialogs | **Intent-driven**: Natural language requirements mapped directly to code |
| **Manual assembly**: Stitch together 8+ files per component | **Coherent generation**: Complete component scaffolding in a single call |
| **Doc hunting**: Search fragmented SDK & CAADoc repeatedly | **Knowledge retrieval**: Structured knowledge stack and API verification |
| **Manual troubleshooting**: Build, inspect logs, and guess fixes | **Automated loop**: Integrated Build → Verify → Repair pipeline |
| **Risky refactoring**: Renaming breaks `.dico`, NLS, and Imakefile | **ChangeSet & Backup**: Change preview with backup-backed rollback |
| **AI hallucination**: Generic models invent non-existent CAA APIs | **Grounded verification**: Header validation against CATIA B28 SDK |
| **Tool sprawl**: Dozens of disconnected scripts and commands | **3 Kernel modes**: AI interacts with three stable, high-level modes |

---

## 03 — The Development Loop

AI interacts with only **three stable modes**. CADE handles the underlying implementation complexity, state tracking, and recovery.

```text
develop()
   │
   ├─ clarify      — Resolve requirement ambiguities with structured decision trees
   ├─ decompose    — Break compound requirements into coherent sub-intents
   ├─ plan         — Formulate dependency-ordered change plans
   ├─ retrieve     — Ground code generation with structured CAA knowledge
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
   ├─ change       — Execute targeted fix plans or refactoring operations
   ├─ verify       — Validate repaired code against compiler and build gates
   └─ rollback     — Cleanly restore workspace if a repair sequence regresses
```

> **Design Philosophy**: AI interacts with three modes. CADE handles the implementation complexity underneath.

---

## 04 — Core Capabilities

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
- **Refactoring**: Rename commands/interfaces and move supported components with ChangeSet validation.
- **Dictionary-aware Refactoring**: Updates `.dico` resources during supported refactoring operations.
- **ChangeSet & Rollback**: Destructive operations use backups and reversible ChangeSet execution.
- **Auto-Fix Plans**: Automated remediation for common CAA setup mistakes.

### 🧠 Knowledge System
- **Structured Knowledge Stack**: `Capability` → `Playbook` → `Knowledge` → `Framework` → `CAADoc`.
- **Battle-Tested Playbooks**: Recipes for Drawing, Surface/GSD, FTA/PMI, and Native Command Investigation.
- **Failure Patterns**: Guards against known CATIA SDK crashes, macro gotchas, and memory leaks.

### 🎨 Developer Experience
- **Color-Coded BMP Icons**: Automatic 22×22 anti-aliased BMP generation mapped by engineering domain.
- **Token-Optimized Responses**: MCP output filters out compiler noise, reducing AI context consumption by ~50%.
- **Editor Integrations**: Native support for Zed, Cursor, VS Code, Windsurf, and Claude Desktop via MCP.

---

## 05 — Architecture

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

### Knowledge & Retrieval Facade

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

## 06 — Quick Start

### 1. Clone & Setup

```powershell
# PowerShell (Windows / recommended for CATIA V5)
git clone https://github.com/chenlei-gh/CADE.git
Copy-Item -Recurse .\CADE\.agents C:\YourCAAWorkspace\
pip install Pillow
```

```bash
# Bash
git clone https://github.com/chenlei-gh/CADE.git
cp -r ./CADE/.agents /path/to/your/caa/workspace/
pip install Pillow
```

### 2. Open in Editor

- **Zed**: Works out of the box (reads `.agents/skills/`).
- **Cursor / VS Code / Windsurf / Claude**: Run `python .agents/skills/catia-caa-dev/tools/setup_mcp.py` to configure the MCP server.

---

## 07 — End-to-End Example

### Request
Prompt your AI editor in natural language:

```text
"Create a CATIA state command named MyAnalysisCmd in AnalysisModule.m
with an OK/Cancel dialog, and register it to MyWorkbench."
```

### Scaffolding Output
CADE automatically generates the coherent CAA file structure across directories:

```text
AnalysisModule.m/
 ├── LocalInterfaces/
 │    ├── MyAnalysisCmd.h
 │    └── MyAnalysisCmdHeader.h
 ├── src/
 │    ├── MyAnalysisCmd.cpp
 │    └── MyAnalysisCmdHeader.cpp
 ├── CNext/
 │    ├── code/dictionary/Framework.dico
 │    └── resources/msgcatalog/MyAnalysisCmd.CATNls
 └── Imakefile.mk
```

### Automated Pipeline
```text
Clarify Intent ➔ Plan Task ➔ Generate Scaffolding ➔ Verify Syntax ➔ Build (mkmk) ➔ Run (CNEXT)
```

---

## 08 — Verification & Reliability

CADE maintains strict quality gates verified through automated test suites:

- **Static Verification**: Validates generated C++ syntax, header includes, macro expansions, and Imakefile definitions without requiring a full compiler run.
- **Architecture Contracts**: Enforces layer isolation, single-facade retrieval access, and clean module boundaries.
- **Semantic & Schema Checks**: Ensures Rich Domain Model integrity, ChangeSet cleanliness, and rollback execution.
- **Fault-Injection & Resiliency**: Validates recovery from corrupt manifests, broken builds, and interrupted operations.
- **Lifecycle Verification**: Exercises end-to-end CAA build (`mkmk`) and CATIA runtime launch (`CNEXT`).

Run the verification suite locally:

```bash
# Fast test suite (skips live CATIA launch)
python .agents/skills/catia-caa-dev/tests/test_master.py --quick

# Full regression suite (includes CATIA lifecycle)
python .agents/skills/catia-caa-dev/tests/test_master.py
```

> **Test baseline**: 43 suites (42 fast suites + 1 CATIA lifecycle suite) · Fast regression: 42/42 passing.

---

## 09 — Scope & Boundaries

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

## 10 — Documentation

- **[SKILL Specification](.agents/skills/catia-caa-dev/SKILL.md)** — Comprehensive agent instructions and execution contracts.
- **[Architecture Guide](.agents/skills/catia-caa-dev/docs/references/ARCHITECTURE.md)** — Deep dive into Kernel, Domain Model, and ChangeSet internals.
- **[Retrieval Architecture](.agents/skills/catia-caa-dev/docs/architecture/retrieval.md)** — Knowledge retrieval facade and indexing contracts.
- **[Deployment & Setup](.agents/skills/catia-caa-dev/docs/guides/DEPLOYMENT_GUIDE.md)** — Environment setup and upgrade procedures.
- **[Examples](.agents/skills/catia-caa-dev/docs/examples/)** — Working examples of Commands, Extensions, and Multi-Interface components.
- **[Changelog](.agents/skills/catia-caa-dev/CHANGELOG.md)** — Version history and architecture evolution records.

---

## 11 — License & Disclaimer

Distributed under the [MIT License](LICENSE).  
Copyright © 2026 [chenlei-gh](https://github.com/chenlei-gh) & CADE Contributors.

### Generated Code Ownership
All CAA code, components, and project scaffolds generated by CADE belong entirely to the user and are not subject to any copyright restrictions or license propagation from CADE itself.

### Trademark & Third-Party Disclaimer
- **CATIA**, **CAA**, **RADE**, and related marks are registered trademarks of Dassault Systèmes SE in France and/or other countries.
- CADE is an independent, third-party open-source development tool and is not affiliated with, endorsed by, sponsored by, or supported by Dassault Systèmes.
- Any CAA code templates and references provided herein are intended to aid developer productivity. Users remain responsible for complying with their own Dassault Systèmes licensing and CAA development agreements.

---

## 🇨🇳 中文说明

<div align="center">

[**快速开始**](#06--快速开始) · [**为什么选择 CADE**](#02--为什么选择-cade) · [**开发闭环**](#03--开发闭环3-种模式) · [**核心能力**](#04--核心能力) · [**完整示例**](#07--端到端完整示例) · [**系统架构**](#05--系统架构) · [**开源许可**](#11--开源许可与免责声明)

</div>

### 01 — 什么是 CADE？

**CADE**（CATIA CAA Development Engine）是专为达索系统 CATIA V5 CAA C++ 开发设计的 **AI 原生开发内核**。

传统 CAA 开发门槛高、RADE 向导繁琐、跨多个目录手动维护样板文件、宏定义复杂晦涩，且编译报错难以定位。CADE 将这些工程阻力替换为一体化的开发闭环：

```text
              用户意图 (User Intent)
                        │
                        ▼
             ┌─────────────────────┐
             │     CADE 内核       │
             │                     │
             │  develop() 开发     │
             │  analyze() 分析     │
             │  repair()  修复     │
             └──────────┬──────────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
      领域知识       任务规划       影响分析
          │             │             │
          └─────────────┼─────────────┘
                        ▼
                   组件脚手架生成
                        │
                        ▼
                   静态规则校验
                        │
                   ┌────┴────┐
                   │         │
                 通过       失败
                   │         │
                   ▼         ▼
               mkmk 构建   自动修复
                   │         │
                   ▼         │
               运行验证 ◄────┘
                   │
                   ▼
               CATIA V5
```

---

### 02 — 为什么选择 CADE？

| 传统 CAA 开发模式 | 使用 CADE 内核 |
|---|---|
| **向导驱动**：在复杂的 RADE 界面中反复点击配置 | **意图驱动**：自然语言需求直接解析映射为标准工程代码 |
| **手动拼装**：每个组件需手动在多个目录拼装 8+ 个关联文件 | **内聚生成**：单次调用生成完整、严谨且可编译的组件脚手架 |
| **翻阅文档**：在分散的官方 SDK 与 CAADoc 文档中反复搜索 | **知识检索**：结构化知识体系支撑，结合官方 SDK 头文件核实防幻觉 |
| **人工排错**：构建失败后手动分析冗长日志、盲目猜测原因 | **自动化闭环**：一体化的 构建 → 验证 → 诊断 → 修复 自动化管线 |
| **高危重构**：手动重命名极易漏改 `.dico`、NLS 与 Imakefile 导致隐蔽崩溃 | **ChangeSet 机制**：操作前提供变更预览，配备自动磁盘备份与可逆回滚 |
| **模型幻觉**：通用大模型经常捏造不存在的 CAA 宏与 API | **真实性校验**：基于 CATIA B28 SDK 头文件进行强约束校验 |
| **工具碎片**：数十个分散的脚本与命令，调用链复杂割裂 | **内核模式收敛**：AI 仅需与 3 种高层、稳定的内核模式交互 |

---

### 03 — 开发闭环（3 种模式）

AI 仅与 **3 种稳定模式** 交互。CADE 负责处理底层的实现复杂度、状态管理与可逆安全恢复：

```text
develop() 开发模式
   │
   ├─ clarify      — 借助结构化决策树消除模糊需求
   ├─ decompose    — 将复合需求拆解为高内聚子意图
   ├─ plan         — 生成满足依赖拓扑的有序变更计划
   ├─ retrieve     — 调取结构化 CAA 知识体系与模式指引
   ├─ generate     — 生成完整规范、开箱即编译的 CAA 组件脚手架
   └─ verify       — 严格校验语法、包含路径与 CAA 结构规范

analyze() 分析模式
   │
   ├─ inspect      — 全面扫描并解析工作区骨架（Framework/Module/组件）
   ├─ retrieve     — 查询官方 API 签名、头文件映射与架构模式
   ├─ diagnose     — 深度审计工作区健康度、循环依赖与潜在坏味道
   └─ impact       — 评估重命名、移动或删除操作的改动影响面（Blast Radius）

repair() 修复模式
   │
   ├─ diagnose     — 分类编译故障、mkmk 诊断日志与静态检查告警
   ├─ change       — 执行针对性的自动修复计划或受控重构操作
   ├─ verify       — 对照编译器与构建门禁验证修复后的代码
   └─ rollback     — 当修复出现回归或意外时，基于磁盘备份干净还原工作区
```

> **核心哲学**：AI 专注于高层工程意图；CADE 负责底层工程细节与可逆安全保障。

---

### 04 — 核心能力

#### 🏗️ 生成（Generate）
- **命令与状态机（Commands & StateCommands）**：完整的状态转换图初始化、选择代理（PathElementAgent）绑定与生命周期实现。
- **对话框与面板（Dialogs & Panels）**：自动生成基于 CATDlgDialog 的控件布局、数据流映射与回调事件处理。
- **工作台与扩展（Workbenches & Addins）**：定制工作台容器、工具栏布局、命令头（Command Headers）与环境绑定。
- **CAA 领域组件（CAA Domain Objects）**：接口声明、TIE 绑定宏、组件实现、晚绑定（Late Binding）与特征扩展。
- **资源与国际化（Resources & NLS）**：字典文件（`.dico`）、消息目录（`CATNls`、`CATRsc`）及各语言定义。

#### 🔨 构建与运行（Build & Run）
- **mkmk 构建闭环**：多进程编译执行、构建门禁过滤与编译器报错语义解析。
- **前置依赖解析（Prerequisites）**：跨 Framework 依赖管理、构建环境初始化与运行时视图（Runtime View）装配。
- **CATIA 容器运行**：自动化启动 CNEXT、挂载测试工作区与自动化批处理宏执行。

#### 🔍 静态与影响分析（Analyze）
- **工作区拓扑扫描**：自动解析 Framework、Module、Interface、Component 与引用关系。
- **改动影响面分析（Blast Radius）**：评估重命名或组件移动波及的下游依赖、构建目标与运行时影响。
- **头文件与 API 真实性校验**：基于达索官方 CATIA B28 SDK 头文件严格核实，杜绝模型幻觉。

#### 🛠️ 修复与重构（Repair & Refactor）
- **组件重构（Refactoring）**：支持重命名命令与接口、跨 Module 迁移受支持的组件，并基于 ChangeSet 提供变更验证。
- **字典感知重构（Dictionary-aware Refactoring）**：在受支持的重构操作中同步更新 `.dico` 字典资源映射。
- **ChangeSet 机制与可逆回滚**：所有破坏性操作执行前自动建立带时间戳的磁盘备份，保障基于备份的安全回滚。
- **自动修复计划**：针对 CAA 典型缺失依赖、宏语法与配置错误提供针对性自动修复方案。

#### 🧠 结构化知识体系（Knowledge System）
- **结构化知识栈**：`Capability` → `Playbook` → `Knowledge` → `Framework` → `CAADoc` 多级资产支撑。
- **实战 Playbook 沉淀**：覆盖工程图（Drawing）、曲面/GSD、三维标注（FTA/PMI）与原生命令逆向调查实战方案。
- **故障模式库（Failure Patterns）**：收录防御 CATIA 崩溃、宏陷阱与内存泄漏的针对性规则。

#### 🎨 开发者体验（Developer Experience）
- **工程语义图标生成**：根据工程领域（Mfg、Assembly、Geometry 等）自动生成 22×22 平滑抗锯齿 BMP 图标。
- **现代化编辑器集成**：原生深度适配 Zed 编辑器技能规范，并通过 MCP 协议无缝接入主流 AI 编程环境。

---

### 05 — 系统架构

CADE 由两大核心引擎支撑：**内核执行管线（Kernel Execution Pipeline）** 与 **统一检索门面（Unified Retrieval Facade）**。

#### 内核执行管线

```text
                 ┌─────────────────────────────────┐
                 │           CADE 内核             │
                 │   develop  ·  analyze  · repair │
                 └────────────────┬────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
     需求澄清与分解             统一检索门面            执行与恢复引擎
  RequirementsClarifier        Retrieval Facade           Build (mkmk)
  RequirementsDecomposer       结构化知识检索            Run (CNEXT)
  IntentPlanner                API 真实性注册表         ChangeSet 执行
  CodeVerifier                 官方头文件映射           磁盘备份与回滚
  RepairLoop                   SDK / CAADoc 索引        Refactor 重构
```

#### 知识与检索门面

```text
                  统一检索门面 (Retrieval Facade)
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   能力与场景编排              API 与头文件映射            底层索引与沉淀
  Capabilities (13)        HeaderMap (头文件映射)       FrameworkMap (148)
  Playbooks (15)           ApiRegistry (B28 符号)       CAADoc 原生用例索引
  Knowledge (32K+14P)      MethodIndex (方法签名)       Native Investigation
  FailurePatterns (15)
```

---

### 06 — 快速开始

#### 1. 克隆与配置

```powershell
# PowerShell（Windows / 推荐 CATIA V5 环境）
git clone https://github.com/chenlei-gh/CADE.git
Copy-Item -Recurse .\CADE\.agents C:\你的CAA工程目录\
pip install Pillow
```

> 提示：也可以直接手动将 `CADE/.agents` 目录复制到你的 CAA 工程根目录下。

```bash
# Bash
git clone https://github.com/chenlei-gh/CADE.git
cp -r ./CADE/.agents /path/to/your/caa/workspace/
pip install Pillow
```

#### 2. 连接你的 AI 编辑器

- **Zed**：开箱即用（自动识别并加载 `.agents/skills/` 下的技能规范）。
- **Cursor / VS Code / Windsurf / Claude**：运行 `python .agents/skills/catia-caa-dev/tools/setup_mcp.py` 自动配置 MCP 服务。

---

### 07 — 端到端完整示例

#### 自然语言需求
在 AI 编辑器中直接下达指令：

```text
"在 AnalysisModule.m 中创建一个名为 MyAnalysisCmd 的状态机命令，
带确定/取消对话框，并将其注册到工作台 MyWorkbench。"
```

#### 自动生成的脚手架目录结构
CADE 自动跨目录生成一致且内聚的 CAA 工程资产：

```text
AnalysisModule.m/
 ├── LocalInterfaces/
 │    ├── MyAnalysisCmd.h
 │    └── MyAnalysisCmdHeader.h
 ├── src/
 │    ├── MyAnalysisCmd.cpp
 │    └── MyAnalysisCmdHeader.cpp
 ├── CNext/
 │    ├── code/dictionary/Framework.dico
 │    └── resources/msgcatalog/MyAnalysisCmd.CATNls
 └── Imakefile.mk
```

#### 自动化流转管线
```text
澄清意图 ➔ 规划任务 ➔ 生成脚手架 ➔ 静态验证 ➔ mkmk 构建 ➔ CNEXT 运行
```

---

### 08 — 质量保障与可靠性

CADE 拥有严密的自动化工程质量保障防线：

- **静态代码验证**：无需完整编译器即可验证生成的 C++ 语法、头文件引入、宏展开与 Imakefile 规范。
- **架构契约保障**：严格保障分层隔离、统一检索门面与模块清晰边界。
- **语义与模式校验**：确保领域模型完整性、ChangeSet 干净度与回滚执行可行性。
- **故障注入韧性**：验证在清单文件损坏、构建中断与操作异常时的恢复韧性。
- **真实生命周期校验**：端到端覆盖真实 CAA 构建（`mkmk`）与 CATIA 运行时启动（`CNEXT`）。

```bash
# 快速回归验证
python .agents/skills/catia-caa-dev/tests/test_master.py --quick

# 完整回归验证（含 CATIA 运行时生命周期套件）
python .agents/skills/catia-caa-dev/tests/test_master.py
```

> **测试基线**：43 套件（42 快速套件 + 1 CATIA 生命周期套件）· 快速回归通过：42/42。

---

### 09 — 项目边界与非目标

为了保持工程聚焦与系统稳定性，CADE 保持明确的能力边界：

| CADE 是 | CADE 不是 |
|---|---|
| 面向 CATIA CAA 开发者的开发自动化内核 | 替换 CATIA 软件本身的终端产品 |
| 面向 CAA C++ 场景的 AI 辅助编程系统 | 通用 CAD 参数化建模或自动化脚本引擎 |
| 高内聚 CAA 代码结构与工程脚手架生成器 | 负责编写用户专属业务核心算法的替代者 |
| 覆盖验证、构建、诊断与运行的工程工具链 | 达索官方 CATIA、RADE 或 mkmk 编译器的替代品 |
| 面向 CAA 专有领域的结构化知识与检索系统 | 脱离 CATIA 上下文的通用代码补全插件 |

> **CADE 是专为 CATIA CAA 开发者打造的工程提效内核，而非面向最终用户的 CATIA 应用程序。**

---

### 10 — 文档与参考

- **[SKILL 规范文档](.agents/skills/catia-caa-dev/SKILL.md)** — Agent 完整执行指引与交互契约。
- **[系统架构指南](.agents/skills/catia-caa-dev/docs/references/ARCHITECTURE.md)** — 内核管道、领域模型与 ChangeSet 机制深度解析。
- **[知识系统架构](.agents/skills/catia-caa-dev/knowledge/README.md)** — 结构化知识体系层级与检索契约。
- **[实战 Playbook 目录](.agents/skills/catia-caa-dev/playbooks/README.md)** — 精选工程场景套路与逆向调查指南。
- **[更新日志](.agents/skills/catia-caa-dev/CHANGELOG.md)** — 版本发布历史、演进记录与迁移注意事项。

---

### 11 — 开源许可与免责声明

本项目采用 [MIT 许可证](LICENSE) 开源发布。  
版权所有 © 2026 [chenlei-gh](https://github.com/chenlei-gh) 及 CADE 贡献者。

#### 生成代码所有权 (Generated Code Ownership)
使用 CADE 生成的所有 CAA 源码、构件与项目工程资产无条件归用户所有，不受 CADE 本身开源协议的版权传染或使用限制。

#### 商标与合规声明 (Trademark & Compliance)
- **CATIA**、**CAA**、**RADE** 及相关标识均为达索系统（Dassault Systèmes SE）在法国和/或其他国家/地区的注册商标。
- CADE 是一套独立的第三方开源辅助开发内核与工具链，与达索系统（Dassault Systèmes）无官方隶属、赞助、授权、认证或背书关系。
- 项目所包含的代码模板、知识索引及脚手架仅用于辅助 CAA 开发者提升日常工程效率。用户在使用本工具开发专有业务模块时，应确保遵守自身与达索系统签订的商业许可协议与 CAA 开发者准则。
