<div align="center">

<img src="https://img.shields.io/badge/python-3.7%2B-blue?style=for-the-badge" />
<img src="https://img.shields.io/badge/CATIA-V5-orange?style=for-the-badge" />
<img src="https://img.shields.io/badge/license-MIT-lightgrey?style=for-the-badge" />

</div>

# CADE — CATIA CAA 开发引擎

**面向 CATIA V5 CAA C++ 的 AI 原生开发内核。** 从意图到经过验证、编译通过、运行测试的代码。

[English](README.md) · [简体中文](README.zh-CN.md)

---

## CADE 做什么

CADE 把碎片化的 CAA 开发流程（RADE 向导、手动拼装文件、翻文档、试错排错）替换为一条闭环：

```text
意图 → 澄清 → 规划 → 生成 → 验证 → 构建 (mkmk) → 运行 (mkrun) → 修复（如需要）
```

三个稳定入口，其余全部内部处理：

| 模式 | 做什么 |
|---|---|
| `develop` | 分解需求、规划变更、生成 CAA 脚手架、验证语法与结构 |
| `analyze` | 扫描工作区拓扑、对照官方 SDK 头文件核实 API、计算依赖图与影响面 |
| `repair` | 诊断构建失败、执行定向修复、对照编译器门禁验证、回归时回滚 |

---

## 核心能力

### 代码生成

单次调用生成完整、可编译的 CAA 组件脚手架——不是需要你自己拼接的碎片。

- **命令与状态机**：状态转换图初始化、`PathElementAgent` 绑定、生命周期方法（`Activated`、`Canceled`、`Desactivated`）、OK/Cancel 对话框模式。
- **对话框**：`CATDlgDialog` 容器/控件布局、事件订阅回调、NLS 消息目录条目。
- **工作台与扩展**：自定义工作台容器、工具栏、`CommandHeader` 注册、`CATIAfrGeneralWksAddin` 字典绑定。
- **组件与接口**：COM 风格接口声明、`TIE`/`BOA` 宏、代码扩展、数据成员脚手架。
- **资源文件**：`.dico` 字典条目、`.CATNls`/`.CATRsc` 消息目录、BMP 图标生成（22×22，抗锯齿，按工程领域映射）。
- **Imakefile.mk**：正确的 `BUILT_OBJECT_TYPE`、`LINK_WITH` 依赖、前置框架声明。

每个生成的组件包含 CAA 要求的全部 8+ 个跨目录文件：`LocalInterfaces/*.h`、`src/*.cpp`、`CNext/code/dictionary/*.dico`、`CNext/resources/msgcatalog/*.CATNls`、模块 `Imakefile.mk`。

### 构建与运行时

- **mkmk 集成**：增量构建（`mkmk -u`）、全量重建、多线程编译、解析后的错误输出。
- **前置依赖引擎**：自动 `IdentityCard.xml` 框架依赖解析与 `mkGetPreq` 工作区填充。
- **Runtime View 装配**：自动化 `mkCreateRuntimeView` 生成 `win_b64` 运行时树。
- **带工作区启动 CATIA**：`run.py <workspace>` 通过 `mkrun` 设置 `CATDLLPath` / `CATDictionaryPath` / `CATMsgCatalogPath`。裸跑 `CATSTART.exe` 启动的 CATIA 不加载任何自定义 CAA DLL——看结果里的 `runtime_view_mounted`，不要只看 `status=started`。
- **编译型 CAA Batch**：`run_caa_batch` 通过 `CATBatch.exe` 运行描述符驱动的 `batchmain` 库，带预检（描述符、DLL、导出表、输入文件）。

### 静态分析与影响评估

- **工作区拓扑扫描**：从 `IdentityCard.xml`、`.dico` 字典、`Imakefile.mk` 解析 Framework/Module/Interface/Component 关系。
- **API 真实性校验**：对照官方 CATIA B28 SDK 头文件核实 CAA API 用法——防止 AI 幻觉出不存在的宏、类和方法签名。
- **依赖图**：模块间依赖可视化，支持 Mermaid 导出。
- **影响面分析**：重构前识别所有受影响文件、字典条目和调用方。

### 修复与重构

- **ChangeSet 机制**：所有破坏性操作在写盘前生成预览，带备份的可逆回滚。
- **字典感知重构**：重命名命令或接口时，原子操作同步更新 `.dico` 条目、NLS 目录和头文件包含。
- **自动修复计划**：针对常见 CAA 配置错误（缺前置依赖、宏用法错误、字典引用断裂）的定向修复。

### 知识体系

结构化知识栈，7 个独立索引各回答一个不同的问题：

| 索引 | 回答什么 | 证据级别 |
|---|---|---|
| `Catalog` | 哪个知识文件覆盖这个主题？ | 知识路由 |
| `HeaderMap` | 哪个头文件声明了这个类型？ | 官方 SDK 证明 |
| `MethodIndex` | 这个类暴露了哪些方法？ | 官方 SDK 证明 |
| `ApiRegistry` | 这个 API 是否已登记并验证？ | 人工审核注册表 |
| `DicIndex` | 这个名字是否随产品字典发布？ | 发布证据 |
| `UseCaseIndex` | 官方例程是否提到过这个符号？ | 出现证据 |
| `SampleDataIndex` | 内置测试模型在哪里？ | 文件位置 |

一个索引命中不等于另一个索引的证明。`DicIndex` 匹配到名字不代表有公共 C++ 入口；`UseCaseIndex` 在官方例程中找到符号不代表调用链正确。

---

## 安装

### 前置要求

| 要求 | 说明 |
|---|---|
| **操作系统** | Windows 64 位（10 或 11） |
| **CATIA V5** | B28 或更高版本，安装时包含 CAA RADE / TCK |
| **编译器** | Visual Studio 2012+（B28 用 VC11，B30+ 用 VC14） |
| **Python** | 3.7+（仅需标准库——零外部依赖） |
| **可选** | `pip install Pillow`（仅 BMP 图标生成需要） |

### 第 1 步：克隆 CADE

```bash
git clone https://github.com/chenlei-gh/CADE.git
```

### 第 2 步：部署到你的 CAA 工作区

把技能文件和治理规则复制到你的 CAA 工程根目录：

```powershell
# PowerShell
Copy-Item -Recurse .\CADE\.agents D:\你的CAA工程目录\
Copy-Item .\CADE\AGENTS.md D:\你的CAA工程目录\
```

```bash
# Bash / Git Bash
cp -r ./CADE/.agents /d/你的CAA工程目录/
cp ./CADE/AGENTS.md /d/你的CAA工程目录/
```

工程根目录的 `AGENTS.md` 是必须的——它告诉 AI Agent 使用 CADE 的工具链，而不是猜测 CAA 代码模式。

### 第 3 步：安装 Git Hooks（每个 clone 一次）

```bash
cd D:\你的CAA工程目录
sh scripts/install-git-hooks.sh
```

安装两个 hook：
- `pre-commit`：提醒你为受控资产变更声明意图（不阻断）。
- `commit-msg`：对暂存的 `.cpp`/`.h`/`.dico`/`.CATNls`/`Imakefile.mk` 文件强制要求 `CADE-Intent:` trailer。

### 第 4 步：验证环境检测

```bash
python .agents/skills/catia-caa-dev/skills/env.py
```

预期输出包含你的 CATIA 安装路径、TCK 环境和工作区配置。如果检测失败，检查 `CATIA_HOME` 或标准达索注册表项是否已设置。

### 第 5 步：连接编辑器

- **Zed**：开箱即用——自动读取 `.agents/skills/` 和 `AGENTS.md`。
- **Cursor / VS Code / Windsurf / Claude Desktop**：运行 MCP 配置脚本：
  ```bash
  python .agents/skills/catia-caa-dev/tools/setup_mcp.py
  ```

### 第 6 步：验证安装

```bash
# 快速测试套件（48 个套件，约 100 秒，不需要 CATIA）
python .agents/skills/catia-caa-dev/tests/test_master.py --quick

# 静态审计（交叉引用 + 深度审计，不需要 CATIA）
python scripts/static_audit.py
```

两个都应报告 100% 通过。如果不通过，最常见原因是 CATIA 安装路径缺失或配置错误。

### 第 7 步：带工作区启动 CATIA

```bash
python .agents/skills/catia-caa-dev/skills/run.py D:/你的CAA工程目录
```

检查 JSON 输出中的 `"runtime_view_mounted": true`。如果显示 `false`，说明工作区 Runtime View 尚未创建——先运行：

```bash
python .agents/skills/catia-caa-dev/skills/build.py D:/你的CAA工程目录 --rv
```

---

## 使用

### 生成 CAA 组件

在 AI 编辑器中用自然语言描述需求：

```text
"在 AnalysisModule.m 中创建一个名为 MyAnalysisCmd 的状态机命令，
带确定/取消对话框，并将其注册到工作台 MyWorkbench。"
```

CADE 生成完整文件集：

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

### 构建

```bash
python .agents/skills/catia-caa-dev/skills/build.py D:/你的CAA工程目录/YourModule.m
```

### 运行

```bash
python .agents/skills/catia-caa-dev/skills/run.py D:/你的CAA工程目录
```

### CLI 参考

```text
cade develop "<需求>" [--preview]              # 完整管线：意图 → 代码
cade build [工作区] [--full|--clean]           # mkmk 构建
cade run [工作区] [--stop|--macro]             # CATIA 运行时
cade batch <参数.xml> [--dry-run]              # 编译型 CAA Batch (CATBatch)
cade edit-logic --file <路径> --reason "..."   # 登记手动代码编辑
cade analyze [工作区] [--modules|--deps]       # 工作区分析
cade diagnose [工作区]                         # 诊断问题
cade fix [工作区]                              # 自动修复
cade verify [模块]                             # 定向验证
cade rollback --id <id>                        # 回滚变更集
cade refactor rename <旧名> <新名> --module <m> # 重命名并更新字典
```

---

## 质量保障

CADE 通过自动化测试套件维护质量门禁：

- **静态验证**：C++ 语法、头文件包含、宏展开、Imakefile 定义——不需要编译器。
- **架构契约**：分层隔离、统一检索门面访问、模块边界强制。
- **故障注入**：清单损坏、构建中断、操作异常时的恢复能力。
- **生命周期验证**：端到端 CAA 构建（`mkmk`）和 CATIA 运行时启动（`CNEXT`）。

```bash
# 快速套件（48 个套件，跳过 CATIA 启动）
python .agents/skills/catia-caa-dev/tests/test_master.py --quick

# 完整回归（含 CATIA 生命周期）
python .agents/skills/catia-caa-dev/tests/test_master.py

# 仅静态漂移门禁
python scripts/static_audit.py
```

**测试基线**：49 个套件（48 快速 + 1 CATIA 生命周期）。快速回归：48/48 通过。

---

## 项目边界

| CADE 是 | CADE 不是 |
|---|---|
| CAA 开发自动化内核 | CATIA 本身 |
| CAA 工程师的 AI 开发助手 | 通用 CAD 自动化 |
| CAA 组件脚手架生成器 | 你的专有工程算法 |
| 构建、运行时、诊断与回滚工具链 | CATIA/RADE 或 MSVC 的替代品 |
| 有依据的 CAA 知识与检索引擎 | 通用的、容易幻觉的编程助手 |
| 官方例程片段回收 | 已证明的调用链合成器 |

> CADE 是 CATIA CAA 开发者的工具，不是终端用户的 CATIA 产品。

---

## 文档

- [SKILL 规范](.agents/skills/catia-caa-dev/SKILL.md) — Agent 指令与执行契约
- [架构指南](.agents/skills/catia-caa-dev/docs/references/ARCHITECTURE.md) — 内核、领域模型与 ChangeSet 内部机制
- [部署指南](.agents/skills/catia-caa-dev/docs/guides/DEPLOYMENT_GUIDE.md) — 环境搭建与升级流程
- [示例](.agents/skills/catia-caa-dev/docs/examples/) — 命令、扩展、多接口组件的完整示例
- [更新日志](.agents/skills/catia-caa-dev/CHANGELOG.md) — 版本历史

---

## 许可证

基于 [MIT 许可证](LICENSE) 开源。
版权所有 © 2026 [chenlei-gh](https://github.com/chenlei-gh) 及 CADE 贡献者。

### 工具授权与生成物权利

- **CADE 内核与工具链**：MIT 许可证。
- **生成工件**：CADE 不对生成的 CAA 代码、脚手架或组件工件主张版权或许可证传染性。所有权归用户，受适用雇佣协议、项目合同和第三方许可约束。
- **专有依赖**：生成的代码引用达索系统 CAA API、头文件、宏和运行时链接。这些受你与达索系统 SE 的商业许可协议管辖。

### 商标声明

**CATIA**、**CAA**、**RADE** 是达索系统 SE 的注册商标。CADE 是独立的第三方开源工具，与达索系统无隶属、赞助或背书关系。
