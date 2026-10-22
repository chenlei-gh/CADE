<div align="center">

<img src="https://img.shields.io/badge/python-3.7%2B-blue?style=for-the-badge" />
<img src="https://img.shields.io/badge/CATIA-V5-orange?style=for-the-badge" />
<img src="https://img.shields.io/badge/license-MIT-lightgrey?style=for-the-badge" />

</div>

# CADE — CATIA CAA Development Engine

**AI-native development kernel for CATIA V5 CAA C++.** From intent to verified, compiled, and runtime-tested code.

[English](README.md) · [简体中文](README.zh-CN.md)

---

## What CADE Does

CADE replaces the fragmented CAA development workflow (RADE wizards, manual file assembly, doc hunting, trial-and-error debugging) with a single closed loop:

```text
Intent → Clarify → Plan → Generate → Verify → Build (mkmk) → Run (mkrun) → Repair (if needed)
```

Three stable entry points, everything else is handled internally:

| Mode | What it does |
|---|---|
| `develop` | Decompose requirements, plan changes, generate CAA scaffolding, verify syntax and structure |
| `analyze` | Scan workspace topology, query API signatures against official SDK headers, compute dependency graphs and blast-radius impact |
| `repair` | Diagnose build failures, execute targeted fixes, validate against compiler gates, rollback on regression |

---

## Core Capabilities

### Code Generation

Generates complete, compilable CAA component scaffolding in a single call — not fragments you stitch together yourself.

- **Commands & StateCommands**: State-chart initialization, `PathElementAgent` bindings, lifecycle methods (`Activated`, `Canceled`, `Desactivated`), OK/Cancel dialog patterns.
- **Dialogs**: `CATDlgDialog` with container/control layouts, event subscriber callbacks, NLS message catalog entries.
- **Workbenches & Addins**: Custom workbench containers, toolbars, `CommandHeader` registration, `CATIAfrGeneralWksAddin` dictionary bindings.
- **Components & Interfaces**: COM-style interface declarations, `TIE`/`BOA` macros, code extensions, data member scaffolding.
- **Resources**: `.dico` dictionary entries, `.CATNls`/`.CATRsc` message catalogs, BMP icon generation (22×22, anti-aliased, domain-mapped).
- **Imakefile.mk**: Correct `BUILT_OBJECT_TYPE`, `LINK_WITH` dependencies, and prerequisite framework declarations.

Every generated component includes all 8+ cross-directory files that CAA requires: `LocalInterfaces/*.h`, `src/*.cpp`, `CNext/code/dictionary/*.dico`, `CNext/resources/msgcatalog/*.CATNls`, and the module `Imakefile.mk`.

### Build & Runtime

- **mkmk integration**: Incremental builds (`mkmk -u`), clean rebuilds, multi-threaded compilation with parsed error output.
- **Prerequisites engine**: Automatic `IdentityCard.xml` framework dependency resolution and `mkGetPreq` workspace population.
- **Runtime View assembly**: Automated `mkCreateRuntimeView` for `win_b64` runtime trees.
- **CATIA launch with workspace mounted**: `run.py <workspace>` invokes `mkrun` with `CATDLLPath` / `CATDictionaryPath` / `CATMsgCatalogPath` set. Bare `CATSTART.exe` starts CATIA without loading any custom CAA DLLs — check `runtime_view_mounted` in the result, not just `status=started`.
- **Compiled CAA Batch**: `run_caa_batch` runs descriptor-driven `batchmain` libraries through `CATBatch.exe` with preflight validation (descriptor, DLL, export table, input files).

### Static Analysis & Impact Assessment

- **Workspace topology scanning**: Parses Framework/Module/Interface/Component relationships from `IdentityCard.xml`, `.dico` dictionaries, and `Imakefile.mk` files.
- **API grounding**: Verifies CAA API usage against official CATIA B28 SDK headers — prevents AI hallucination of non-existent macros, classes, and method signatures.
- **Dependency graph**: Inter-module dependency visualization with Mermaid export.
- **Blast-radius analysis**: Identifies all affected files, dictionary entries, and callers before refactoring.

### Repair & Refactoring

- **ChangeSet mechanism**: All destructive operations produce a preview with backup-backed rollback before any disk write.
- **Dictionary-aware refactoring**: Renaming a command or interface updates `.dico` entries, NLS catalogs, and header includes in a single atomic operation.
- **Auto-fix plans**: Targeted remediation for common CAA setup mistakes (missing prerequisites, incorrect macro usage, broken dictionary references).

### Knowledge System

Structured knowledge stack with 7 independent indexes, each answering a different question:

| Index | Answers | Evidence level |
|---|---|---|
| `Catalog` | Which knowledge file covers this topic? | Knowledge routing |
| `HeaderMap` | Which header declares this type? | Official SDK proof |
| `MethodIndex` | What methods does this class expose? | Official SDK proof |
| `ApiRegistry` | Is this API registered and verified? | Curated registry |
| `DicIndex` | Does this name ship in the product dictionary? | Shipping evidence |
| `UseCaseIndex` | Did an official sample mention this symbol? | Occurrence evidence |
| `SampleDataIndex` | Where is the built-in test model? | File location |

A hit in one index is not proof for another. `DicIndex` matching a name doesn't mean a public C++ entry point exists. `UseCaseIndex` finding a symbol in an official sample doesn't prove the call chain is correct.

---

## Installation

### Prerequisites

| Requirement | Details |
|---|---|
| **OS** | Windows 64-bit (10 or 11) |
| **CATIA V5** | B28 or later, installed with CAA RADE / TCK |
| **Compiler** | Visual Studio 2012+ (VC11 for B28, VC14 for B30+) |
| **Python** | 3.7+ (standard library only — zero external dependencies) |
| **Optional** | `pip install Pillow` (only for BMP icon generation) |

### Step 1: Clone CADE

```bash
git clone https://github.com/chenlei-gh/CADE.git
```

### Step 2: Deploy to Your CAA Workspace

Copy the skill files and governance rules into your CAA project root:

```powershell
# PowerShell
Copy-Item -Recurse .\CADE\.agents D:\YourCAAWorkspace\
Copy-Item .\CADE\AGENTS.md D:\YourCAAWorkspace\
```

```bash
# Bash / Git Bash
cp -r ./CADE/.agents /d/YourCAAWorkspace/
cp ./CADE/AGENTS.md /d/YourCAAWorkspace/
```

The `AGENTS.md` file at the project root is required — it tells the AI agent to use CADE's tools instead of guessing CAA code patterns.

### Step 3: Install Git Hooks (One-Time Per Clone)

```bash
cd D:\YourCAAWorkspace
sh scripts/install-git-hooks.sh
```

This installs two hooks:
- `pre-commit`: Reminds you to declare intent for controlled asset changes (non-blocking).
- `commit-msg`: Enforces the `CADE-Intent:` trailer for staged `.cpp`/`.h`/`.dico`/`.CATNls`/`Imakefile.mk` files.

### Step 4: Verify Environment Detection

```bash
python .agents/skills/catia-caa-dev/skills/env.py
```

Expected output includes your CATIA installation path, TCK environment, and workspace configuration. If detection fails, check that `CATIA_HOME` or the standard Dassault registry entries are set.

### Step 5: Connect Your Editor

- **Zed**: Works out of the box — reads `.agents/skills/` and `AGENTS.md` automatically.
- **Cursor / VS Code / Windsurf / Claude Desktop**: Run the MCP setup script:
  ```bash
  python .agents/skills/catia-caa-dev/tools/setup_mcp.py
  ```

### Step 6: Verify the Installation

```bash
# Quick test suite (48 suites, ~100s, no CATIA needed)
python .agents/skills/catia-caa-dev/tests/test_master.py --quick

# Static audit (cross-reference + deep audit, no CATIA needed)
python scripts/static_audit.py
```

Both should report 100% pass. If they don't, the most common cause is a missing or misconfigured CATIA installation path.

### Step 7: Launch CATIA with Your Workspace

```bash
python .agents/skills/catia-caa-dev/skills/run.py D:/YourCAAWorkspace
```

Check the JSON output for `"runtime_view_mounted": true`. If it says `false`, your workspace Runtime View hasn't been created yet — run:

```bash
python .agents/skills/catia-caa-dev/skills/build.py D:/YourCAAWorkspace --rv
```

---

## Usage

### Generate a CAA Component

Tell your AI editor in natural language:

```text
"Create a CATIA state command named MyAnalysisCmd in AnalysisModule.m
with an OK/Cancel dialog, and register it to MyWorkbench."
```

CADE generates the complete file set:

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

### Build

```bash
python .agents/skills/catia-caa-dev/skills/build.py D:/YourCAAWorkspace/YourModule.m
```

### Run

```bash
python .agents/skills/catia-caa-dev/skills/run.py D:/YourCAAWorkspace
```

### CLI Reference

```text
cade develop "<request>" [--preview]       # Full pipeline: intent → code
cade build [workspace] [--full|--clean]    # mkmk build
cade run [workspace] [--stop|--macro]      # CATIA runtime
cade batch <param.xml> [--dry-run]         # Compiled CAA batch (CATBatch)
cade edit-logic --file <path> --reason "..."  # Register manual code edit
cade analyze [workspace] [--modules|--deps]   # Workspace analysis
cade diagnose [workspace]                  # Diagnose issues
cade fix [workspace]                       # Auto-repair
cade verify [module]                       # Targeted verification
cade rollback --id <id>                    # Rollback a changeset
cade refactor rename <old> <new> --module <m>  # Rename with dict update
```

---

## Verification

CADE maintains quality gates verified through automated test suites:

- **Static verification**: C++ syntax, header includes, macro expansions, and Imakefile definitions — without requiring a compiler.
- **Architecture contracts**: Layer isolation, single-facade retrieval access, module boundary enforcement.
- **Fault injection**: Recovery from corrupt manifests, broken builds, interrupted operations.
- **Lifecycle verification**: End-to-end CAA build (`mkmk`) and CATIA runtime launch (`CNEXT`).

```bash
# Fast suite (48 suites, skips live CATIA)
python .agents/skills/catia-caa-dev/tests/test_master.py --quick

# Full regression (includes CATIA lifecycle)
python .agents/skills/catia-caa-dev/tests/test_master.py

# Static drift gate only
python scripts/static_audit.py
```

**Test baseline**: 49 suites (48 fast + 1 CATIA lifecycle). Fast regression: 48/48 passing.

---

## Scope & Boundaries

| CADE is | CADE is not |
|---|---|
| CAA development automation kernel | CATIA itself |
| AI development assistant for CAA engineers | General-purpose CAD automation |
| CAA component scaffolding generator | Your proprietary engineering algorithms |
| Build, runtime, diagnosis & rollback tooling | A replacement for CATIA/RADE or MSVC |
| Grounded CAA knowledge & retrieval engine | A generic, hallucination-prone coding assistant |
| Official use-case fragment recovery | A proven call-chain synthesizer |

> CADE is a developer tool for CATIA CAA. It is not an end-user CATIA product.

---

## Documentation

- [SKILL Specification](.agents/skills/catia-caa-dev/SKILL.md) — Agent instructions and execution contracts
- [Architecture Guide](.agents/skills/catia-caa-dev/docs/references/ARCHITECTURE.md) — Kernel, Domain Model, and ChangeSet internals
- [Deployment Guide](.agents/skills/catia-caa-dev/docs/guides/DEPLOYMENT_GUIDE.md) — Environment setup and upgrade procedures
- [Examples](.agents/skills/catia-caa-dev/docs/examples/) — Working examples of Commands, Extensions, and Multi-Interface components
- [Changelog](.agents/skills/catia-caa-dev/CHANGELOG.md) — Version history

---

## License

Distributed under the [MIT License](LICENSE).
Copyright © 2026 [chenlei-gh](https://github.com/chenlei-gh) & CADE Contributors.

### Tool Licensing & Generated Code Ownership

- **CADE Engine & CLI**: MIT License.
- **Generated Work Products**: CADE asserts no copyright or license propagation over generated CAA code, scaffolding, or component artifacts. Ownership remains with the user, subject to applicable employment agreements, project contracts, and third-party licenses.
- **Proprietary Dependencies**: Generated code references Dassault Systèmes CAA APIs, headers, macros, and runtime linkages. These remain governed by your commercial licensing agreements with Dassault Systèmes SE.

### Trademark Disclaimer

**CATIA**, **CAA**, **RADE** are registered trademarks of Dassault Systèmes SE. CADE is an independent third-party open-source tool, not affiliated with, endorsed by, or sponsored by Dassault Systèmes.
