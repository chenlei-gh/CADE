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

# CADE — CATIA CAA 开发引擎

<div align="center">

### 面向 CATIA V5 CAA 的 AI 原生开发内核

*从意图到生成代码、验证、构建、运行时、诊断与恢复。*

[English](README.md) · [**简体中文**](README.zh-CN.md)

[**快速开始**](#06--快速开始) · [**为什么选择 CADE**](#02--为什么选择-cade) · [**开发闭环**](#03--开发闭环3-种模式) · [**核心能力**](#04--核心能力) · [**完整示例**](#07--端到端完整示例) · [**系统架构**](#05--系统架构) · [**开源许可**](#11--开源许可与免责声明)

</div>

---

## 01 — 什么是 CADE？

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

## 02 — 为什么选择 CADE？

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

## 03 — 开发闭环（3 种模式）

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

## 04 — 核心能力

### 🏗️ 生成（Generate）
- **命令与状态机（Commands & StateCommands）**：完整的状态转换图初始化、选择代理（PathElementAgent）绑定与生命周期实现。
- **对话框与面板（Dialogs & Panels）**：自动生成基于 CATDlgDialog 的控件布局、数据流映射与回调事件处理。
- **工作台与扩展（Workbenches & Addins）**：定制工作台容器、工具栏布局、命令头（Command Headers）与环境绑定。
- **CAA 领域组件（CAA Domain Objects）**：接口声明、TIE 绑定宏、组件实现、晚绑定（Late Binding）与特征扩展。
- **资源与国际化（Resources & NLS）**：字典文件（`.dico`）、消息目录（`CATNls`、`CATRsc`）及各语言定义。

### 🔨 构建与运行（Build & Run）
- **mkmk 构建闭环**：多进程编译执行、构建门禁过滤与编译器报错语义解析。
- **前置依赖解析（Prerequisites）**：跨 Framework 依赖管理、构建环境初始化与运行时视图（Runtime View）装配。
- **CATIA 启动**：必须带工作区走 `run.py <workspace>` → `mkrun`，才会挂载该工作区的 Runtime View。裸跑 `CATSTART.exe` / `CNEXT.exe` 只会起一个不加载自定义 CAA DLL 的 CATIA。`status=started` 不等于 `runtime_view_mounted`。

### 🔍 静态与影响分析（Analyze）
- **工作区拓扑扫描**：自动解析 Framework、Module、Interface、Component 与引用关系。
- **改动影响面分析（Blast Radius）**：评估重命名或组件移动波及的下游依赖、构建目标与运行时影响。
- **头文件与 API 真实性校验**：基于达索官方 CATIA B28 SDK 头文件严格核实，杜绝模型幻觉。

### 🛠️ 修复与重构（Repair & Refactor）
- **组件重构（Refactoring）**：支持重命名命令与接口、跨 Module 迁移受支持的组件，并基于 ChangeSet 提供变更验证。
- **字典感知重构（Dictionary-aware Refactoring）**：在受支持的重构操作中同步更新 `.dico` 字典资源映射。
- **ChangeSet 机制与可逆回滚**：所有破坏性操作执行前自动建立带时间戳的磁盘备份，保障基于备份的安全回滚。
- **自动修复计划**：针对 CAA 典型缺失依赖、宏语法与配置错误提供针对性自动修复方案。

### 🧠 结构化知识体系（Knowledge System）
- **结构化知识栈**：`Capability` → `Playbook` → `Knowledge` → `Framework` → `CAADoc` 多级资产支撑。
- **实战 Playbook 沉淀**：覆盖工程图（Drawing）、曲面/GSD、三维标注（FTA/PMI）与原生命令逆向调查实战方案。
- **故障模式库（Failure Patterns）**：收录防御 CATIA 崩溃、宏陷阱与内存泄漏的针对性规则。

### 🎨 开发者体验（Developer Experience）
- **工程语义图标生成**：根据工程领域（Mfg、Assembly、Geometry 等）自动生成 22×22 平滑抗锯齿 BMP 图标。
- **现代化编辑器集成**：原生深度适配 Zed 编辑器技能规范，并通过 MCP 协议无缝接入主流 AI 编程环境。

---

## 05 — 系统架构

CADE 由两大核心引擎支撑：**内核执行管线（Kernel Execution Pipeline）** 与 **统一检索门面（Unified Retrieval Facade）**。

### 内核执行管线

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

### 知识与检索门面

```text
                  统一检索门面 (Retrieval Facade)
                                │
        ┌───────────────────────┬─────────────────────┐
        ▼                       ▼                       ▼
   能力与场景编排              API 与头文件映射            官方证据索引
  Capabilities (13)        HeaderMap (头文件)         UseCaseIndex (出现证据)
  Playbooks (15)           MethodIndex (方法)        DicIndex (发布字典)
  Knowledge / Patterns     ApiRegistry (已登记 API)   SampleDataIndex (样件路径)
  FailurePatterns (15)     CatalogIndex (知识路由)   CAADoc 源码片段
```

七索引各答一件事。知识目录命中不等于 API 存在；字典命中只说明这个名字随产品发布，不代表有公共 C++ 入口；官方例程命中只证明符号出现过，不证明调用顺序。

没有现成 Playbook 时，`analyze()` 可以从官方例程收回源码片段。这不是已验证调用链。Kernel 只有在 `index_consistency` 严格等于 `consistent` 时，才会把片段提升为 `official_usecase_chain`。当前真实探索只会写出 `root_matched_metadata_unverified` 或 `unknown`，因此结果停在 `official_usecase_fragment`。根路径匹配不等于索引元数据已与源码核对；静态片段也不等于 `mkmk` 编译或 CATIA 运行通过。

---

## 06 — 快速开始

### 1. 前置依赖与环境
- **操作系统**：Windows 64 位（CATIA V5 CAA 开发必须环境）
- **官方工具链**：CATIA V5（如 B28）+ CAA RADE / TCK + Visual Studio（如 VC11 / VC14）
- **Python 环境**：Python 3.7+（仅需标准库，CADE 内核本身 **0 外部依赖**）
- **可选依赖**：`pip install Pillow`（仅在使用 22×22 工程语义 BMP 图标生成时需要）

### 2. 工作区部署与配置

#### 方案 A：新工作区初始部署
克隆 CADE 并将 `.agents` 技能目录与项目治理规范 `AGENTS.md` 一同放入你的 CAA 工程根目录下：

```powershell
# PowerShell（Windows）
git clone https://github.com/chenlei-gh/CADE.git
Copy-Item -Recurse .\CADE\.agents D:\你的CAA工程目录\
Copy-Item .\CADE\AGENTS.md D:\你的CAA工程目录\
```

> **注意**：必须将 `AGENTS.md` 放置在工程根目录，以确保 AI Agent 严格遵守 CADE 唯一开发闭环，防止模型绕过工具链直接修改受控资产。

#### 方案 B：持续镜像与同步（推荐）
若你维护独立的生产工作区或影子目录，推荐使用项目内置的同步脚本，它会自动排除 `__pycache__`、测试日志等临时产物，并打上 `.sync_stamp` 版本校验戳：

```bash
# Bash / Git Bash
sh sync_agents.sh
```

### 3. 环境校验与编辑器连接
1. **验证环境自检**：
   ```bash
   python .agents/skills/catia-caa-dev/skills/env.py
   ```
2. **连接 AI 编辑器**：
   - **Zed**：开箱即用（自动加载 `.agents/skills/` 下的技能规范与根目录 `AGENTS.md` 治理规则）。
   - **Cursor / VS Code / Windsurf / Claude**：运行 `python .agents/skills/catia-caa-dev/tools/setup_mcp.py` 自动配置 MCP 服务。
3. **带工作区启动 CATIA**：
   ```bash
   python .agents/skills/catia-caa-dev/skills/run.py D:/你的CAA工程目录
   ```
   `workspace` 是位置参数，不是 `--workspace`。这条路径走 `mkrun`，并设置 `CATDLLPath` / `CATDictionaryPath` / `CATMsgCatalogPath`。不要直接跑安装目录里的 `CATSTART.exe` 或 `CNEXT.exe`，也不要不带工作区调 `run.py`：CATIA 会起来，但任何自定义 CAA DLL 都不加载。看返回 JSON 的 `runtime_view_mounted`，不要只看 `status=started`。

---

## 07 — 端到端完整示例

### 自然语言需求
在 AI 编辑器中直接下达指令：

```text
"在 AnalysisModule.m 中创建一个名为 MyAnalysisCmd 的状态机命令，
带确定/取消对话框，并将其注册到工作台 MyWorkbench。"
```

### 自动生成的脚手架目录结构
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

### 自动化流转管线
```text
澄清意图 ➔ 规划任务 ➔ 生成脚手架 ➔ 静态验证 ➔ mkmk 构建 ➔ run.py <workspace> → mkrun
```

---

## 08 — 质量保障与可靠性

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

# 仅跑静态漂移门禁（交叉引用 + 深度审计；不启动 CATIA）
python scripts/static_audit.py
```

本仓库没有托管 CI。上面两个秒级静态套件用来拦文档漂移（例如 `skills/*.py` 未登记进 `SKILL.md` 文件树）。每个 clone 装一次本机 push 门禁：

```bash
sh scripts/install-git-hooks.sh
```

它把 `scripts/git-hooks/pre-push` 复制到 `.git/hooks/`。`.git/hooks` 不随仓库分发，新 clone 不跑安装脚本就没有这道门禁。单次绕过用 `git push --no-verify`。

> **测试基线**：47 套件（46 快速套件 + 1 CATIA 生命周期套件）· 快速回归通过：46/46。

---

## 09 — 项目边界与非目标

为了保持工程聚焦与系统稳定性，CADE 保持明确的能力边界：

| CADE 是 | CADE 不是 |
|---|---|
| 面向 CATIA CAA 开发者的开发自动化内核 | 替换 CATIA 软件本身的终端产品 |
| 面向 CAA C++ 场景的 AI 辅助编程系统 | 通用 CAD 参数化建模或自动化脚本引擎 |
| 高内聚 CAA 代码结构与工程脚手架生成器 | 负责编写用户专属业务核心算法的替代者 |
| 覆盖验证、构建、诊断与运行的工程工具链 | 达索官方 CATIA、RADE 或 mkmk 编译器的替代品 |
| 面向 CAA 专有领域的结构化知识与检索系统 | 脱离 CATIA 上下文的通用代码补全插件 |
| 官方例程片段回收（证据不足时拒绝提升） | 已证明的调用链合成器，或自动发布的 Playbook |

> **CADE 是专为 CATIA CAA 开发者打造的工程提效内核，而非面向最终用户的 CATIA 应用程序。**

---

## 10 — 文档与参考

- **[SKILL 规范文档](.agents/skills/catia-caa-dev/SKILL.md)** — Agent 完整执行指引与交互契约。
- **[系统架构指南](.agents/skills/catia-caa-dev/docs/references/ARCHITECTURE.md)** — 内核管道、领域模型与 ChangeSet 机制深度解析。
- **[知识系统架构](.agents/skills/catia-caa-dev/knowledge/README.md)** — 结构化知识体系层级与检索契约。
- **[实战 Playbook 目录](.agents/skills/catia-caa-dev/playbooks/README.md)** — 精选工程场景套路与逆向调查指南。
- **[更新日志](.agents/skills/catia-caa-dev/CHANGELOG.md)** — 版本发布历史、演进记录与迁移注意事项。

---

## 11 — 开源许可与免责声明

本项目采用 [MIT 许可证](LICENSE) 开源发布。  
版权所有 © 2026 [chenlei-gh](https://github.com/chenlei-gh) 及 CADE 贡献者。

### 工具授权与生成物权利边界 (Licensing & Code Ownership)
- **CADE 内核与工具链**：CADE 本身的程序代码、CLI 工具集与 Agent 技能指令集在宽松的 MIT 许可证下开源分发。
- **生成工件与业务代码所有权**：CADE 不对使用本工具生成、派生或辅助构建的 CAA 业务源码、工程脚手架及定制构件主张任何版权所有权或开源协议传染性。CADE 不主张对用户创作的业务代码和工程成果享有所有权，相关成果的所有权及使用权仍受适用法律、劳动或项目合同、第三方许可协议以及用户与相关权利人之间的约定约束。
- **专有平台与第三方依赖合规**：生成代码中所引用的达索系统 CAA 头文件、宏展开、组件接口及链接依赖，其知识产权与使用条件完全受用户自身合法持有的达索系统（Dassault Systèmes SE）商业授权协议与 CAA 开发者准则管辖。CADE 不转让、不授予亦不代理任何达索系统专有知识产权。

### 商标与第三方合规声明 (Trademark & Compliance)
- **CATIA**、**CAA**、**RADE** 及相关标识均为达索系统（Dassault Systèmes SE）在法国和/或其他国家/地区的注册商标。
- CADE 是一套独立的第三方开源工程提效内核与辅助工具，与达索系统（Dassault Systèmes）无官方隶属、赞助、授权、认证或背书关系。
- 项目所包含的代码模板、知识索引及工程参考仅用于辅助 CAA 开发者提升日常工程效率。用户在使用本工具开发专有业务模块时，应确保遵守自身与达索系统及其他第三方组件签订的商业许可协议与开发规范。
