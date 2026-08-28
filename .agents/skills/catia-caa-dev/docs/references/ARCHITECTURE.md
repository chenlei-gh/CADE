# CADE v3.2 系统架构

> **快照**：2026-08-28（对照当时 `skills/` 源码）  
> **本文是方向图，不是契约，也不是维护验证的证据。**  
> 行数、模块数、测试套件数会漂移。要证明“某函数会不会被调用 / 某入口是否存在”，必须读源码或跑测试，不要引用本节数字结案。

权威来源（发生冲突时以它们为准，不以本文为准）：

| 问题 | 权威 |
|------|------|
| 用户 Agent 怎么用 CADE | `SKILL.md` |
| 意图 → 能力 → 入口 | `capabilities.yaml`（存在性不对账文件有没有） |
| 能力能不能用 | `skills/lifecycle.yaml` |
| CAA 知识/API 检索 | `docs/architecture/retrieval.md` + `get_retrieval()` |
| 模板路径 | `templates/README.md` |
| 实际行为 | 对应 `skills/*.py` |

---

## 怎么读这张图

两套工作不要混：

```text
用户 Agent 做 CAA 开发
    → MCP develop / analyze / repair
    → 不必知道内部模块

维护 CADE 自身
    → 本文只回答“大概该看哪一类文件”
    → 局部证据不够时继续读源码，不要把本文当充分证据
```

MCP 只暴露 3 个工具：`develop` / `analyze` / `repair`。其余 CLI/Python 能力没有 mcp binding，这是设计，不是文档漏列。

### 维护问题 → 先看哪（仍须读源码结案）

| 你在问 | 先打开 | 不要当成充分证据的 |
|--------|--------|-------------------|
| 用户该调哪个工具 | `SKILL.md` 强制工作流 + `capabilities.yaml` | 本文分层图 |
| 某能力是否可用 / 是否 experimental | `skills/lifecycle.yaml` + `tools/check_capabilities.py` | 文件在不在磁盘上 |
| develop 会不会落盘 | `kernel.py`：`ModePolicy` + `_execute_develop_plan` + `_apply_changeset_dict` | 「预览→确认」旧叙述 |
| 某 create_* 实际写什么文件 | `actions.py` / `intents/` → `changeset.py` → `templates/README.md` | 模板目录名猜测 |
| 某 Intent 是否 dispatch 到 action | `kernel.py` `_execute_develop_plan` 的分支，再读对应 action | 「函数存在」 |
| MCP 暴露了几个工具 | `mcp_server.py` 的 `TOOLS` | SKILL 里「41 个旧工具可达」 |
| 响应字段会不会被优化器丢掉 | `token_optimizer.py` `_PASSTHROUGH_KEYS` | 优化器文件全读 |
| CAA API 真不真 | `docs/architecture/retrieval.md` §0 Lookup Map → `get_retrieval()` | `knowledge/` 手写文档 |
| 编译 / Runtime View | `build.py` / `runtime_view.py` / `parser.py` | 只看 mkmk 返回码 |
| 测试覆盖了什么 | `tests/test_master.py` 的 `SUITES` | 本文或 SKILL 里的套件数字 |
| 字符串/C++ 模板里的 CAA 写法 | `templates/` + grep；Python AST 看不见 | 任何 Python 符号索引 |

---

## 核心分层

```
┌─────────────────────────────────────────────┐
│                  AI Agent                    │
│         (Zed / Claude / Cursor)              │
├─────────────────────────────────────────────┤
│         MCP Server (mcp_server.py)           │
│         Token Optimizer (token_optimizer.py) │
├─────────────────────────────────────────────┤
│              Kernel (kernel.py)              │
│     develop · analyze · repair 三模式        │
├──────────┬──────────┬───────────────────────┤
│ Intent   │ Actions  │  Tools / Retrieval     │
│ Engine   │ (CRUD)   │                       │
├──────────┼──────────┼───────────────────────┤
│ Planner  │ create_* │  cade.py (CLI)         │
│ Impact   │ delete_* │  build.py (mkmk)       │
│          │ analyze  │  run.py (CNEXT)        │
│          │ refactor │  retrieval.py (五索引) │
├──────────┴──────────┼───────────────────────┤
│   Generator         │  Icon Provider         │
│   Changeset (写入)  │  Backup (回滚)         │
├─────────────────────┴───────────────────────┤
│           Meta Model (10实体)                │
│     Framework · Module · Command · Dialog    │
│     Interface · Component · Feature · ...    │
└─────────────────────────────────────────────┘
```

生产生成路径：`Intent → intents/ → changeset → build_gate`。  
`experimental/specification.py` **未接入 kernel**，不要当成生产模块。

---

## 模块清单（快照）

顶层 `skills/*.py` 生产模块 33 个。行数为 2026-08-28 物理行数，仅作体量参考。

### Kernel / 入口

| 模块 | 职责 | 行数 |
|------|------|------|
| `kernel.py` | 三模式调度；`develop` 默认 auto-apply | 1391 |
| `mcp_server.py` | MCP：仅 develop / analyze / repair | 235 |
| `cade.py` | CLI 入口 | 788 |
| `token_optimizer.py` | MCP 响应压缩（passthrough 键不可丢） | 240 |

### 检索（CAA 领域，走 `get_retrieval()`）

| 模块 | 职责 | 行数 |
|------|------|------|
| `retrieval.py` | 五索引门面 | 208 |
| `catalog.py` | CatalogIndex | 554 |
| `api_registry.py` | ApiRegistry | 202 |
| `header_map.py` | HeaderMap | 349 |
| `method_index.py` | MethodIndex | 324 |

契约与禁止事项见 `docs/architecture/retrieval.md`。不要把 CADE 自身源码检索塞进这层。

### 生成 / 写入

| 模块 | 职责 | 行数 |
|------|------|------|
| `actions.py` | 原子操作（创建/删除/分析） | 1648 |
| `generator.py` | 模板引擎 | 581 |
| `icon_provider.py` | 官方图标运行时引用 + Badge | 801 |
| `changeset.py` | 变更预览 + 应用 | 744 |
| `backup.py` | 操作备份 + 回滚点 | 409 |
| `meta_model.py` | 工作区元模型（10 实体） | 1077 |
| `analyzer.py` | 工作区分析 | 510 |
| `requirements.py` | 需求澄清 + 分解 | 845 |
| `intents/` | 高级意图（command/object/service） | — |
| `intent/` | Planner / Impact（计划层） | — |

### 构建 / 运行

| 模块 | 职责 | 行数 |
|------|------|------|
| `build.py` | mkmk 管线 + 环境初始化 | 951 |
| `build_gate.py` | 编译前静态门禁 | 226 |
| `run.py` | CNEXT 启动/停止 | 694 |
| `runtime_view.py` | Runtime View | 348 |
| `env.py` | CATIA 环境检测（零硬编码） | 809 |
| `parser.py` | mkmk 输出解析 | 254 |
| `version_strategy.py` | 版本适配 | 218 |
| `workspace.py` | 工作区工具 | 223 |
| `clean.py` | 工作区清理 | 166 |
| `docgen.py` | 文档生成 | 354 |
| `utils.py` | 缓存/日志/格式化 | 433 |

### 诊断 / 修复

| 模块 | 职责 | 行数 |
|------|------|------|
| `diagnostics.py` | 问题检测 + FixPlan | 895 |
| `repair.py` | 自动修复闭环 | 512 |
| `verifier.py` | 静态 + mkmk 验证 | 719 |
| `refactor.py` | 重命名/移动 | 608 |
| `ui_lint.py` | UI 失效模式静态检查 | 346 |

### 非生产

| 模块 | 状态 | 行数 |
|------|------|------|
| `experimental/specification.py` | `lifecycle.yaml`: experimental；未接入 kernel | 435 |

`tools/` 是维护/辅助脚本（CAADoc 索引、capability 对账、环境安装），**不属于 Kernel 运行链**。

---

## 数据流（生产）

```
用户: "创建 HoleAnalysisCmd"
        │
        ▼
  Kernel.develop()          # ModePolicy.DEVELOP.auto_apply = True
        │
        ▼
  Intent → Planner
        │
        ▼
  Actions.create_command()  # 等 create_* / intents
    ├── Generator → 骨架文件
    ├── IconProvider → 图标
    └── Changeset（序列化）
        │
        ▼
  _apply_changeset_dict()   # 非 --preview 时自动 apply
        │
        ├── status: "ok" + rollback_id     ← 文件已落盘
        └── preview 模式才停在未 apply
        │
        ▼
  Build (cade build) → Run (cade dev / cade run)
```

直接调用 `actions.py` 仍可能返回 `pending` + `changeset`，那是底层 API，不是 `develop()` 的行为。

---

## 图标系统

```
Domain keyword → analyze_command() → IconSemantic
    │  (EXACT → COMPOUND → LONGEST → FALLBACK)
    ▼
Official Resolver（有限精确候选 exists()，不扫全库、不模糊）
    ├─ HIGH + 语义可接受 → 本机 B28 I_*.bmp + Badge
    └─ 未命中 / DENY / 歧义     → 生成底图 + Badge
            │
            ▼
    22×22 24-bit BMP（CATRsc 仍是 I_<命令名>）
            │
            ▼
    CNext/resources/graphic/icons/normal/
```

现行细节：`docs/architecture/ADR-Icon-Provider-Freeze.md`。

---

## 关键设计决策

| 决策 | 原因 |
|------|------|
| 意图驱动而非模板驱动 | AI 只需表达意图，内核自动分解 |
| develop 自动 apply | MCP 一次调用落盘；用 rollback 撤销，而不是二次 confirm |
| Changeset + 备份 | 可预览、可回滚 |
| 检索必须走 facade | 禁止运行时扫 knowledge/ 或 SDK 冒充权威 |
| 能力 ≠ 文件存在 | Phantom Capability；路由看 yaml，生命周期看 lifecycle.yaml |
| 纯本地图标 | 零网络依赖 |
| 零硬编码 CATIA 路径 | `catia_detector.py` 动态检测 |

---

## 模块依赖关系（示意）

```
kernel.py ── 调度中心
  ├── actions.py / intents/
  │   ├── generator.py
  │   ├── icon_provider.py
  │   ├── changeset.py
  │   ├── backup.py
  │   ├── meta_model.py
  │   └── analyzer.py
  ├── retrieval.py ── catalog / api_registry / header_map / method_index
  ├── verifier.py / build_gate.py ── build.py ── env.py
  ├── repair.py ── diagnostics.py
  ├── refactor.py
  └── requirements.py

mcp_server.py ── kernel.py ── token_optimizer.py
cade.py ── kernel.py / build.py / run.py / …
```

这是阅读方向，不是可机械验证的调用图。深度与是否有环以 import 为准。

---

## 设计原则

1. **意图驱动** — AI 表达“创建可执行命令”，内核分解为 Command + Header + Catalog + NLS + Icon
2. **Changeset** — 先生成 `{created, modified, deleted}`；`develop()` 默认写入
3. **原子 + 可逆** — 每个 create 有对应 delete；操作可回滚
4. **结构化输出** — API 返回 dict；MCP 层 token-optimized JSON
5. **查询优于猜测** — 工作区状态查元模型；CAA API 查 Retrieval
6. **零硬编码** — CATIA 路径/版本/架构动态检测
7. **Cache 是加速器** — 检索缓存不是第二真相源；损坏必须告警，不能静默当权威

---

## 错误处理流

```
操作失败
  │
  ├── 编译错误 → parser.py 解析 mkmk 输出
  │   ├── 已知模式 → repair.py
  │   └── 未知模式 → diagnostics.py FixPlan
  │
  ├── 运行时错误 → diagnostics.py
  │   ├── 缺失 include → verifier.py
  │   └── API 不兼容 → version_strategy.py
  │
  └── 环境错误 → env.py
      ├── CATIA 未安装 → 明确报错
      └── TCK 未初始化 → tck_init
```

---

## 回滚机制

```
操作执行前 → backup.py 创建备份点
  │
  ▼
Changeset.apply()
  ├── 成功 → 备份点 applied；develop 返回 rollback_id
  └── 失败 → rollback_operation()
```

回滚链：`backup.py` → `changeset.py` → `actions.py`  
用户/Agent 接口：`repair()` / `actions.rollback_operation()` / `list_rollback_points()`

---

## 知识系统（产品面）

```
get_retrieval()
  ├── CatalogIndex     catalog/index.yaml + knowledge/frameworks
  ├── ApiRegistry      capabilities / templates / knowledge
  ├── HeaderMap        CATIA PublicInterfaces
  ├── MethodIndex      caadoc 解析缓存
  └── UseCaseIndex     CAADoc 样例存在性
```

教学文档分层：`capabilities/` → `playbooks/` → `knowledge/` → `patterns/`。  
手写文档不是同等可信，见 `KNOWLEDGE_AUDIT_STATUS.md`。

**高效检索**：先打开 `docs/architecture/retrieval.md` §0 Lookup Map（问题 → 索引 → 命令）。不要 grep `knowledge/`，不要把 CADE 自身源码检索塞进这一层。

---

## 版本兼容

`version_strategy.py` 管理跨版本差异（如 B28 API 适配）。模板是否选对版本，以该模块和对应测试为准。

---

## 元模型实体关系

```
Workspace
  └── Framework (*.edu)
        ├── IdentityCard.h
        ├── Module (*.m)
        │     ├── Command → Header / Dialog / Icon
        │     ├── Interface / Component / Feature / Extension
        │     ├── Workbench + Addin
        │     └── EventListener
        ├── Catalog / Dictionary / NLS / Imakefile
```

约 10 个核心实体；CRUD、依赖、级联删除以 `meta_model.py` / `actions.py` 为准。

---

## 构建管线

```
build_workspace(ws)
  ├── env.py: CAAEnvironment.load_config()
  ├── Prerequisites
  ├── tck_init → tck_profile → mkinit → mkGetPreq
  ├── mkmk（增量常见 flags: -u -a）
  ├── parser.py 解析 stdout/stderr
  └── 编译后：Runtime View 同步 / 产物校验
```

成功不能只看 mkmk 返回码，还要看 parser 错误数和 DLL 新鲜度（见 `SKILL.md` Build 判定）。

---

## 运行时管线

```
start_catia_runtime(workspace_path)
  ├── 可选停止已有 CNEXT
  ├── 挂载工作区 Runtime View（CATDLLPath 等）
  ├── tck_init → tck_profile → mkinit → mkrun
  └── 无 workspace 的裸启动不会加载自定义 CAA DLL
```

---

## CLI 命令参考（以 `cade.py` 为准）

```
cade develop <request> [--workspace] [--preview]
cade build [workspace] [--full|--clean|--threads N]
cade dev <workspace>
cade run [workspace] [--stop|--macro|--status]
cade create <type> <name> <module> …
cade analyze / diagnose / validate / suggest
cade fix / refactor / rollback
cade docs / rv / setup / prereq / check / test / version
cade plan / impact
cade expose     # unavailable：设计态拦截，不要当运行时故障去修
```

---

## 测试

`tests/test_*.py` 快照为 **44** 个文件（2026-08-28）。分层说明见 `docs/TEST_DOCUMENTATION.md`。  
quick 模式不跑真实 mkmk/CNEXT；生成代码后仍须在真实工作区 Build。

---

## 配置

```
catalog/index.yaml
config/editors/*.json     ← 用户侧 MCP 模板（不要把维护工具写进这里）
cache/*.json / *.pickle   ← 加速器，不是事实库
skills/capabilities.yaml
skills/lifecycle.yaml
```

---

## Token 优化

`token_optimizer.py` 在 MCP 响应前压缩。关键字段（如 `questions`、`rollback_id`）必须透传；改优化器前先读 `_PASSTHROUGH_KEYS`，不要以本文推断。
