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

### 🎯 AI-Powered CATIA CAA Development. *One command. Eight files. Done.*

</div>

---

## 🚀 Quick Start

```bash
# Clone into your CAA project
git clone https://github.com/chenlei-gh/CADE.git
cp -r cade/.agents /path/to/your/caa/project/

# Open in editor. CADE auto-detects CATIA. Zero config.
python .agents/skills/catia-caa-dev/tools/setup_mcp.py
```

> [!TIP]
> **Zed** — works out of the box. **Claude / Cursor / VS Code / Windsurf** — run setup script above.

---

## 📖 Navigation

| 你想... | 看这个 |
|---------|--------|
| 🏗 **创建第一个命令** | [[Getting Started]] |
| 🔍 **分析工作区** | [[Workspace Analysis]] |
| 🔧 **诊断和修复** | [[Diagnostics & FixPlan]] |
| ♻️ **重构代码** | [[Safe Refactoring]] |
| 📦 **理解架构** | [[Architecture Overview]] |
| 🤖 **AI 如何调用 CADE** | [[AI Integration Guide]] |
| 📚 **查阅 API 参考** | [[CAA API Reference]] |
| 🧩 **使用开发模式** | [[Development Patterns]] |
| 📝 **查看真实示例** | [[Real Examples]] |
| 🔌 **配置 MCP Server** | [[MCP Server Setup]] |
| 🧪 **运行测试** | [[Test Suite]] |
| 🆘 **遇到问题** | [[Troubleshooting]] |

---

## 🧠 Core Philosophy

> **Capability grows by accumulating knowledge assets, not by modifying code.**

CADE is not just a tool — it's a **knowledge engine** for CATIA CAA development.

```
AI / CLI / MCP
     ↓
Specification → Validation → Generator → ChangeSet → File System
     ↓
CodeModel (10 entities) + DependencyGraph (9 relations) + Diagnostics + FixPlan
     ↓
Build Engine (35 cmds) + Runtime Engine (7 cmds) + Rollback
     ↓
Knowledge System (9 Knowledge + 6 Pattern + 1 Example + Catalog)
```

---

## ⚡ Three Rules (最高优先级)

| # | Rule | Meaning |
|---|------|---------|
| 1 | 🚫 **Don't Reinvent** | Use templates. Don't write CAA boilerplate manually. |
| 2 | 🚫 **Don't Guess** | Check docs first on unknown errors. Never speculate. |
| 3 | 🚫 **Don't Skip Help** | Search knowledge/patterns/examples/docs before coding. |

```
Unknown Error
    ↓
① Check docs/FAQ.md, docs/guides/   ← Help docs first
    ↓
② cade diagnose                     ← Let engine analyze
    ↓
③ Check knowledge/                   ← API reference
    ↓
④ Check patterns/                    ← Architecture patterns
    ↓
⑤ Check examples/                    ← Real code examples
    ↓
⑥ cade fix --apply                   ← Auto-fix
```

---

## 📊 By the Numbers

| | |
|---|---|
| **Test Suites** | 19 (L1-L7 + Integration + Audit) |
| **Test Cases** | 700+ |
| **Pass Rate** | 100% |
| **Templates** | 25+ |
| **APIs** | 15 (Intent + Action) |
| **CLI Commands** | 19 |
| **MCP Tools** | 38 |
| **Build Commands** | 35 |
| **Domain Entities** | 10 |
| **Knowledge Assets** | 16 (9K + 6P + 1E) |

---

## 📂 Project Structure

```
your_project/
├── .agents/skills/catia-caa-dev/   ← CADE (drop-in)
│   ├── SKILL.md                    ← Main skill doc (start here)
│   ├── skills/                     ← Engine (23 modules)
│   │   ├── intents/                ← Intent Layer (6 subs)
│   │   ├── actions.py              ← Action Layer
│   │   ├── specification.py        ← Spec Layer
│   │   ├── diagnostics.py          ← Diagnostics + FixPlan
│   │   ├── refactor.py             ← Safe Refactoring
│   │   ├── generator.py            ← Code Generator
│   │   ├── meta_model.py           ← Domain Model
│   │   ├── token_optimizer.py      ← AI Token Optimizer
│   │   └── ...
│   ├── templates/                  ← 25+ code templates
│   ├── knowledge/                  ← CAA API reference (9 domains)
│   ├── patterns/                   ← Architecture patterns (6 types)
│   ├── examples/                   ← Real CAA projects
│   ├── tests/                      ← 19 suites, 700+ cases
│   ├── docs/                       ← Full documentation
│   ├── tools/                      ← Setup, validation, utilities
│   └── config/                     ← Editor MCP templates
├── MyFramework.edu/
├── MyModule.m/
└── ...
```

---

## 🔗 Links

- [📖 Main Documentation](https://github.com/chenlei-gh/CADE/tree/main/.agents/skills/catia-caa-dev/docs)
- [🏗 Architecture Reference](https://github.com/chenlei-gh/CADE/tree/main/.agents/skills/catia-caa-dev/docs/references/ARCHITECTURE.md)
- [📝 Changelog](https://github.com/chenlei-gh/CADE/tree/main/.agents/skills/catia-caa-dev/CHANGELOG.md)
- [📋 SKILL.md](https://github.com/chenlei-gh/CADE/tree/main/.agents/skills/catia-caa-dev/SKILL.md)

---

<div align="center">

**Made with ❤️ for CATIA CAA Developers**

*Questions? [[Troubleshooting]] · Ideas? Open an [Issue](https://github.com/chenlei-gh/CADE/issues)*

</div>
