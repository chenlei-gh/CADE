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

[English](README.md) · [**简体中文**](README.zh-CN.md)

[**Quick Start**](#06--quick-start) · [**Why CADE?**](#02--why-cade) · [**The Loop**](#03--the-development-loop) · [**Capabilities**](#04--core-capabilities) · [**Example**](#07--end-to-end-example) · [**Architecture**](#05--architecture) · [**Docs**](.agents/skills/catia-caa-dev/docs/) · [**License**](#11--license--disclaimer)

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
- **CATIA Launcher**: Workspace launch goes through `run.py <workspace>` and `mkrun`, which mounts that workspace Runtime View. A bare `CATSTART.exe` / `CNEXT.exe` starts CATIA with no custom CAA DLLs. `status=started` is not `runtime_view_mounted`.
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
      ┌──────────────────┼────────────────────┐
      ▼                  ▼                  ▼
   Catalog          ApiRegistry         HeaderMap
 MethodIndex        UseCaseIndex        DicIndex
 SampleDataIndex
      │                  │                  │
      └──────────────────┴───────────────────┘
                         ▼
              Official CAADoc sources
```

The facade answers seven different questions. A hit in one index is not proof for another: Catalog matches a knowledge file, HeaderMap/MethodIndex prove a public type or method, DicIndex only says a name ships, UseCaseIndex only records that an official sample mentioned a symbol, and SampleDataIndex only locates a built-in model.

When no playbook covers a request, `analyze()` may recover an official use-case fragment. That fragment is not a verified call chain. Kernel promotes it to `official_usecase_chain` only when `index_consistency` is exactly `consistent`. Live exploration currently emits `root_matched_metadata_unverified` or `unknown`, so real queries stay `official_usecase_fragment`. A root-path match is not metadata-vs-source consistency, and a static fragment is not an `mkmk` or CATIA runtime result.

> **Core Tenet**: Capability grows by accumulating structured knowledge assets, not by expanding code complexity.

---

## 06 — Quick Start

### 1. Prerequisites
- **OS**: Windows 64-bit (required for CATIA V5 CAA development)
- **Toolchain**: CATIA V5 (e.g. B28) + CAA RADE / TCK + Visual Studio (e.g. VC11/VC14)
- **Python**: Python 3.7+ (Standard library only; CADE core has **zero** external dependencies)
- **Optional**: `pip install Pillow` (only required for 22×22 engineering BMP icon generation)

### 2. Setup Workspace

#### Option A: Initial Workspace Deployment
Clone CADE and copy both the `.agents` skills directory and the project governance rule `AGENTS.md` into your CAA workspace root:

```powershell
# PowerShell (Windows)
git clone https://github.com/chenlei-gh/CADE.git
Copy-Item -Recurse .\CADE\.agents D:\YourCAAWorkspace\
Copy-Item .\CADE\AGENTS.md D:\YourCAAWorkspace\
```

#### Option B: Continuous Mirroring (Recommended for active dev)
If you already maintain a production workspace (e.g. shadow copy), use the automated mirror script to avoid copying runtime caches (`__pycache__`, logs) and record `.sync_stamp`:

```bash
# Bash / MSYS2
sh sync_agents.sh
```

### 3. Verify & Connect
1. **Verify Environment Detection**:
   ```bash
   python .agents/skills/catia-caa-dev/skills/env.py
   ```
2. **Editor Setup**:
   - **Zed**: Works out of the box (reads `.agents/skills/` and `AGENTS.md`).
   - **Cursor / VS Code / Windsurf / Claude**: Run `python .agents/skills/catia-caa-dev/tools/setup_mcp.py` to configure the MCP server.
3. **Launch CATIA with the workspace mounted**:
   ```bash
   python .agents/skills/catia-caa-dev/skills/run.py D:/YourCAAWorkspace
   ```
   `workspace` is a positional argument, not `--workspace`. This path uses `mkrun` and sets `CATDLLPath` / `CATDictionaryPath` / `CATMsgCatalogPath`. Do not launch `<CATIA_INSTALL>/win_b64/code/bin/CATSTART.exe` or `CNEXT.exe`, and do not call `run.py` without a workspace: CATIA will start, but no custom CAA DLL loads. Check `runtime_view_mounted` in the JSON result; `status=started` only means the process is up.

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
Clarify Intent ➔ Plan Task ➔ Generate Scaffolding ➔ Verify Syntax ➔ Build (mkmk) ➔ Run (run.py <workspace> → mkrun)
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

# Static drift gate only (cross-reference + deep audit; no CATIA)
python scripts/static_audit.py
```

There is no hosted CI in this repository. The two static suites above are the ones that catch documentation drift (for example an unregistered `skills/*.py`). Install the local push gate once per clone:

```bash
sh scripts/install-git-hooks.sh
```

That copies `scripts/git-hooks/pre-push` into `.git/hooks/`. `.git/hooks` is not distributed with the repo, so a fresh clone does not get the gate until the installer is run. Bypass a single push with `git push --no-verify`.

> **Test baseline**: 47 suites (46 fast suites + 1 CATIA lifecycle suite) · Fast regression: 46/46 passing.

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
| **Official use-case fragment recovery** | A proven call-chain synthesizer or auto-published playbook |

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

### Tool Licensing & Generated Code Ownership
- **CADE Engine & CLI**: The CADE source code, CLI utilities, and core agent instructions are licensed under the permissive MIT License.
- **Generated Work Products**: CADE asserts no copyright, intellectual property claim, or license propagation over the CAA code, scaffolding, or component artifacts generated by or derived through its execution. CADE does not claim ownership of user-created work products. Ownership and usage rights remain subject to applicable employment agreements, project contracts, third-party licenses, and applicable law.
- **Proprietary & Third-Party Dependencies**: Generated code may necessarily reference or include Dassault Systèmes CAA APIs, header files, macros, interface definitions, and runtime linkages. Such platform-specific references and compiled artifacts remain governed exclusively by your own commercial licensing, software agreements, and CAA developer contracts with Dassault Systèmes SE or relevant third parties. CADE conveys no license, sublicense, or indemnity regarding proprietary Dassault Systèmes intellectual property.

### Trademark & Third-Party Disclaimer
- **CATIA**, **CAA**, **RADE**, and related marks are registered trademarks of Dassault Systèmes SE in France and/or other countries.
- CADE is an independent, third-party open-source engineering tool and is not affiliated with, endorsed by, sponsored by, or supported by Dassault Systèmes.
- Any CAA code templates, schemas, and architectural references provided herein are intended solely for developer productivity and engineering reference. Users remain solely responsible for validating runtime behavior, compiling within authorized environments, and complying with all applicable software license agreements.
