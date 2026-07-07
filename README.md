# CADE - CATIA CAA Development Engine

> **AI-powered CATIA V5 CAA development lifecycle engine with rich domain model, knowledge system, and intelligent automation.**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0.0-green.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)

**CADE** transforms CATIA CAA development by providing an AI-friendly development engine that understands CAA semantics, manages dependencies, automates builds, and accelerates the entire development lifecycle.

---

## 🚀 Core Capabilities

### 🎯 Intent-Driven Development
AI describes what to build; CADE handles the complexity:
- **Create commands, workbenches, dialogs, features** with natural language
- **Intelligent recommendations** based on project context
- **Semantic validation** ensuring CAA correctness

### 🧠 Knowledge System (v2.0)
- **9 Knowledge modules** (mecmod, part, product, ui, infrastructure)
- **6 Development patterns** (analyzers, workflows, UI patterns)
- **Real CAA examples** for Few-shot learning
- **Catalog-based indexing** for instant AI lookup

### 🔄 Complete Lifecycle Management
- **Specification-driven generation** with rollback support
- **Build automation** (mkmk, incremental, clean builds)
- **Runtime management** (CATIA startup, environment setup)
- **Diagnostics & Fix Plans** for automated issue resolution

### 📊 Rich Domain Model
10+ CAA object types with full dependency tracking:
- Framework, Module, Command, Dialog, Interface, Feature
- Workbench, Extension, Factory, Resource

### 🛠️ Developer Tools
- **CLI** - 88+ commands for terminal workflows
- **MCP Server** - Model Context Protocol integration
- **Refactoring** - Safe rename, move, and restructure operations
- **Workspace Snapshot** - Real-time development state tracking

---

## 📁 Project Structure

```
.agents/skills/catia-caa-dev/
├── 📘 SKILL.md                    # 88 AI triggers + capability index
├── 📦 catalog/                    # Knowledge indexing
│   └── index.yaml                 # Keyword → Resource mapping
├── 📚 knowledge/                  # CAA API & Domain Knowledge
│   ├── mecmod/                    # Feature, Topology
│   ├── part/                      # Fillet, Hole, Chamfer
│   ├── product/                   # Assembly
│   ├── ui/                        # Dialog, Toolbar
│   └── infrastructure/            # Selection, Command
├── 🎨 patterns/                   # Development Patterns
│   ├── analyzer/                  # Geometry analyzers, rule checkers
│   ├── blocks/                    # Reusable pattern blocks
│   ├── ui/                        # Result dialogs
│   └── workflow/                  # Batch processing
├── 💡 examples/                   # Real CAA Projects
│   └── geometry/fillet_checker.md
├── 🐍 skills/                     # Python Engine
│   ├── actions.py                 # 88+ development actions
│   ├── meta_model.py              # 10 CAA domain models
│   ├── specification.py           # Spec-driven generation
│   ├── generator.py               # Code generation
│   ├── workspace.py               # Workspace management
│   ├── build.py                   # Build automation
│   ├── run.py                     # Runtime management
│   ├── diagnostics.py             # Issue detection & fix plans
│   ├── mcp_server.py              # MCP protocol server
│   └── intents/                   # Intent recognition
├── 📋 templates/                  # 25+ CAA templates
│   ├── command/                   # Command templates
│   ├── dialog/                    # Dialog templates
│   ├── workbench/                 # Workbench templates
│   ├── feature/                   # Feature templates
│   └── ...
├── 🧪 tests/                      # 19 test suites (52s, 100% pass)
└── 📖 docs/                       # Complete documentation
    ├── guides/                    # Getting started, AI guide, FAQ
    ├── references/                # Architecture, quick reference
    └── examples/                  # Real-world examples
```

---

## ⚡ Quick Start

### Prerequisites
- **CATIA V5** (R19+, tested on R28)
- **CAA RADE** installation
- **Python 3.8+**
- **Zed Editor** (or any AI-enabled editor)

### Installation

1. **Clone this repository**
```bash
git clone https://github.com/your-username/catia-caa-dev-engine.git
cd catia-caa-dev-engine
```

2. **Copy `.agents` to your workspace**
```bash
# Copy the entire .agents folder to your CATIA workspace root
# For example:
cp -r .agents D:/your-catia-workspace/
```

3. **Configure environment**
```bash
# Edit your workspace paths in SKILL.md or let AI auto-detect
cd .agents/skills/catia-caa-dev
```

4. **Activate in Zed**
Open your workspace in Zed, and CADE will be automatically available in the AI assistant panel.

5. **Test the installation**
Ask the AI assistant:
```
List all available CAA development capabilities
```

---

## 💬 AI Usage Examples

### Create a Simple Command
```
Create a command named "HelloWorld" in TestModule that shows a message box
```

### Create a Workbench with Commands
```
Create a new workbench "GeometryTools" with commands for fillet checking and hole analysis
```

### Build & Run
```
Build the current workspace and start CATIA
```

### Add a Dialog
```
Add a dialog to HelloWorld command with an OK button and text field
```

### Diagnose Issues
```
Check the workspace for missing Dictionary entries and suggest fixes
```

---

## 🏗️ Architecture Principles

### **Specification-Driven**
```
Intent → Specification → Generator → Build → Runtime → Diagnostics
```
All generations go through validated specifications, enabling rollback and verification.

### **Knowledge-Centric**
```
SKILL.md (triggers) → Catalog (index) → Knowledge/Patterns/Examples
```
System capability grows through **data accumulation, not code changes**.

### **Domain Model First**
10 rich CAA domain objects (CommandModel, ModuleModel, etc.) encapsulate:
- CAA semantics & constraints
- Dependency relationships
- Path resolution
- Validation rules

### **Zero Hardcoding**
- No absolute paths
- Environment auto-detection
- Platform-agnostic design

---

## 📊 System Metrics

| Metric | Value |
|--------|-------|
| **Test Coverage** | 19 suites, 100% pass, 52s |
| **AI Triggers** | 88 capabilities |
| **Templates** | 25+ CAA templates |
| **Knowledge Files** | 16 (9 knowledge + 6 patterns + 1 example) |
| **Domain Models** | 10 CAA object types |
| **Build Commands** | 35+ Build/Runtime commands |
| **CLI Tools** | 88+ terminal commands |
| **Lines of Code** | 42,000+ |
| **Production Ready** | 27/27 checks ✅ |

---

## 🔧 Advanced Features

### Workspace Snapshot
Real-time development state tracking:
```yaml
frameworks: [TestFramework]
modules: [TestModule]
commands: [HelloCmd]
build_status: success
diagnostics: []
```

### Dependency Graph
Automatic dependency tracking:
```
Framework → Module → Command → Dialog → Resources
```
Cascade delete, impact analysis, and refactoring support.

### Diagnostics + Fix Plans
Not just error detection—automatic fix generation:
```yaml
problem: Command not registered
reason: Missing Dictionary entry
fix_plan:
  - action: add_dictionary_entry
    target: HelloCmd
    framework: TestFramework
```

### Rollback System
Every operation is reversible:
```python
changeset = create_command("HelloCmd")
# ... test ...
changeset.rollback()  # Complete cleanup
```

---

## 📚 Documentation

- **[Getting Started](docs/guides/GETTING_STARTED.md)** - Quick setup guide
- **[AI Guide](docs/guides/AI_GUIDE.md)** - How to use with AI assistants
- **[Architecture](docs/references/ARCHITECTURE.md)** - System design
- **[Knowledge System](docs/KNOWLEDGE_SYSTEM_ARCHITECTURE.md)** - v2.0 knowledge architecture
- **[FAQ](docs/guides/FAQ.md)** - Common questions
- **[Examples](docs/examples/)** - Real-world workflows

---

## 🧪 Testing

Run the complete test suite:
```bash
cd .agents/skills/catia-caa-dev
python -m pytest tests/ -v
```

Test categories:
- **L1-L3**: Unit & Integration tests
- **L4**: Architecture constraint validation
- **L5**: CAA semantic integrity
- **L6**: Fault injection & recovery
- **L7**: Knowledge system validation

---

## 🤝 Contributing

We welcome contributions! Areas of interest:
- Additional CAA knowledge modules (Drafting, SheetMetal, Manufacturing)
- More development patterns
- Real CAA project examples
- Bug reports and feature requests

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

Copyright 2024 CADE Project

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

Built with insights from:
- CATIA V5 CAA RADE documentation
- 20+ years of CAA development experience
- AI-driven development research
- Open-source CAA community

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-username/catia-caa-dev-engine/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/catia-caa-dev-engine/discussions)
- **Documentation**: [docs/](docs/)

---

<div align="center">

**"System capability grows through accumulating knowledge assets, not modifying code."**

*The philosophy behind CADE v2.0*

</div>
