# CADE v3.2 系统架构

> 2026-07-16 · 29 模块 · 82 模板 · 39 测试套件

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
│ Intent   │ Actions  │  Tools                │
│ Engine   │ (CRUD)   │                       │
├──────────┼──────────┼───────────────────────┤
│ Planner  │ create_* │  cade.py (CLI)         │
│ Impact   │ delete_* │  build.py (mkmk)       │
│ Optimizer│ analyze  │  run.py (CNEXT)        │
│          │ refactor │  refactor.py           │
│          │ rollback │  diagnostics.py        │
├──────────┴──────────┼───────────────────────┤
│   Generator (16类型) │  Icon Provider (107图案)│
│   Changeset (预览)   │  Backup (回滚)         │
├─────────────────────┴───────────────────────┤
│           Meta Model (10实体)                │
│     Framework · Module · Command · Dialog    │
│     Interface · Component · Feature · ...    │
└─────────────────────────────────────────────┘
```

## 模块清单 (29)

| 模块 | 职责 | 行数 |
|------|------|------|
| `kernel.py` | 三模式调度中心 | ~600 |
| `cade.py` | CLI 入口 (build/dev/run/refactor) | ~600 |
| `actions.py` | 原子操作 (创建/删除/分析) | ~1200 |
| `build.py` | mkmk 编译管线 + 环境初始化 | ~530 |
| `run.py` | CNEXT 启动/停止/热重启 | ~590 |
| `generator.py` | 模板引擎 (16 种类型) | ~580 |
| `icon_provider.py` | 107 种几何图标，RGBA 多色 | ~340 |
| `changeset.py` | 变更预览 + 应用/回滚 | ~380 |
| `meta_model.py` | 工作区元模型 (10 实体) | ~1150 |
| `refactor.py` | 重命名/移动/提取接口 | ~500 |
| `diagnostics.py` | 问题检测 + FixPlan | ~780 |
| `repair.py` | 自动修复闭环 | ~120 |
| `verifier.py` | 静态 + mkmk 代码验证 | ~530 |
| `backup.py` | 操作备份 + 回滚点管理 | ~400 |
| `analyzer.py` | 工作区分析 + 建议 | ~200 |
| `env.py` | CATIA 环境检测 (零硬编码) | ~580 |
| `parser.py` | mkmk 输出解析 | ~200 |
| `catalog.py` | 知识目录索引 | ~50 |
| `requirements.py` | 需求澄清 + 分解 | ~120 |
| `specification.py` | 规格对象定义 | ~430 |
| `clean.py` | 工作区清理 | ~160 |
| `docgen.py` | 文档自动生成 | ~300 |
| `token_optimizer.py` | AI Token 优化 | ~350 |
| `mcp_server.py` | MCP 协议服务 | ~100 |
| `runtime_view.py` | Runtime View 管理 | ~340 |
| `workspace.py` | 工作区工具 | ~220 |
| `utils.py` | 缓存/日志/格式化 | ~200 |
| `version_strategy.py` | B28 版本适配 | ~230 |

## 数据流

```
用户: "创建 HoleAnalysisCmd"
        │
        ▼
  Kernel.develop()
        │
        ▼
  Intent Engine → intent = CREATE_COMMAND
        │
        ▼
  Planner → [create_command, update_catalog, update_nls, generate_icon]
        │
        ▼
  Actions.create_command()
    ├── Generator → CommandClass.h/cpp + Header + Catalog + NLS + Imakefile
    ├── IconProvider → I_hole.bmp (几何图案 + 域颜色 + RGBA 渲染)
    └── Changeset → 预览 → 确认 → 应用
        │
        ▼
  Build (cade build)
    ├── tck_init → tck_profile → mkinit → mkGetPreq → mkmk
    └── copy_icons_to_runtime()
        │
        ▼
  Run (cade dev / cade run)
    ├── mkrun → CNEXT.exe
    └── Runtime View deployed
```

## 图标系统

```
Domain keyword → resolve_icon() → 107 patterns
    │
    ├── _get_color_for_icon() → 7-category color
    └── _draw_icon_4x_rgba()  → RGBA body/edge/dim/accent
            │
            ▼
    88x88 4x supersample → LANCZOS → 22x22
            │
            ▼
    FASTOCTREE quantize → 8-bit indexed BMP
            │
            ▼
    CNext/resources/graphic/icons/normal/
```

## 关键设计决策

| 决策 | 原因 |
|------|------|
| 意图驱动而非模板驱动 | AI 只需表达意图，内核自动分解 |
| Changeset 预览机制 | 所有操作先预览再应用，支持回滚 |
| 纯本地图标生成 | 零网络依赖，离线可用 |
| 4x 超采样渲染 | 边缘平滑，专业品质 |
| B28 白边高亮 | 深色工具栏可见性 |
| 零硬编码 CATIA 路径 | `catia_detector.py` 动态检测 |
| mkmk 输出解析 | 结构化错误/警告，非字符串匹配 |

## 模块依赖关系

```
kernel.py ── 调度中心
  ├── actions.py ── 原子操作
  │   ├── generator.py    (模板引擎)
  │   ├── icon_provider.py (图标生成)
  │   ├── changeset.py    (变更预览)
  │   ├── backup.py       (回滚管理)
  │   ├── meta_model.py   (元模型)
  │   ├── analyzer.py     (工作区分析)
  │   └── build.py ── env.py ── version_strategy.py
  ├── verifier.py ── build.py
  ├── repair.py ── diagnostics.py ── meta_model.py
  ├── refactor.py ── changeset.py + meta_model.py
  └── requirements.py

cade.py ── CLI 入口
  ├── kernel.py
  ├── build.py
  ├── run.py
  └── docgen.py

run.py
  ├── env.py
  └── utils.py

mcp_server.py
  ├── kernel.py
  └── token_optimizer.py
```

最大依赖深度: 3，零循环依赖。

## 设计原则

1. **意图驱动** — AI 表达"创建可执行命令"，内核自动分解为 Command + Header + Catalog + NLS + Icon
2. **Changeset 预览** — 所有操作先生成 `{created, modified, deleted}` 预览，确认后一次性写入
3. **原子 + 可逆** — 每个 create 有对应 delete，每个操作可回滚到备份点
4. **结构化输出** — 所有 API 返回 dict，MCP 层 token-optimized JSON
5. **查询优于猜测** — 从工作区元模型查询可用选项，不猜测路径/类型
6. **零硬编码** — CATIA 路径、版本、架构均通过 `catia_detector.py` 动态检测

## 错误处理流

```
操作失败
  │
  ├── 编译错误 → parser.py 解析 mkmk 输出
  │   ├── 已知模式 → repair.py 自动修复
  │   └── 未知模式 → diagnostics.py 生成 FixPlan → AI 审查
  │
  ├── 运行时错误 → diagnostics.py 分析
  │   ├── 缺失 include → verifier.py 建议
  │   └── API 不兼容 → version_strategy.py 查找 B28 替代
  │
  └── 环境错误 → env.py 诊断
      ├── CATIA 未安装 → 明确报错
      └── TCK 未初始化 → 自动 tck_init
```

## 回滚机制

```
操作执行前 → backup.py 创建备份点
  │
  ▼
Changeset 应用 → 文件写入
  │
  ├── 成功 → 备份点标记为 applied
  │
  └── 失败 → rollback_operation()
      ├── 从备份恢复原始文件
      ├── 删除新创建的文件
      └── 恢复到操作前状态

回滚链: backup.py → changeset.py → actions.py
用户接口: actions.rollback_operation() / actions.list_rollback_points()
```

## 知识系统架构

```
catalog/index.yaml ── 全局索引
  │
  ├── knowledge/frameworks/   (149 CAADoc 框架)
  ├── knowledge/mecmod/       (机械设计)
  ├── knowledge/part/         (零件设计)
  ├── knowledge/product/      (装配设计)
  ├── knowledge/ui/           (界面开发)
  ├── knowledge/drawing/      (工程图)
  ├── knowledge/surface/      (曲面/GSD)
  ├── knowledge/fta/          (容差分析)
  ├── knowledge/infrastructure/ (系统框架)
  ├── knowledge/philosophy/   (6 CAA 哲学)
  └── knowledge/failure_patterns/ (3 失败模式)

capabilities/ ── 能力入口 (按功能域)
playbooks/    ── 成熟方案 (按场景)
patterns/     ── 架构模式 (按模式类型)
```

## 版本兼容

`version_strategy.py` 管理跨版本差异:
- **B28 API 适配**: `Undo()` → `ExecuteUndo()`, CATDeclareClass → CATImplementClass
- **模板版本感知**: 模板自动选择对应版本的 API
- **test_version_strategy.py** 验证所有版本的模板一致性

## 元模型实体关系

```
Workspace
  └── Framework (*.edu)
        ├── IdentityCard.h
        ├── Module (*.m)
        │     ├── Command
        │     │     ├── Header (CATCommandHeader)
        │     │     ├── Dialog (optional)
        │     │     └── Icon (CATRsc + BMP)
        │     ├── Interface (IDL + C++)
        │     ├── Component (BOA/TIE)
        │     ├── Feature (StartUp + BuildTime)
        │     ├── Extension (DataExtension)
        │     ├── Workbench + Addin
        │     └── EventListener
        ├── Catalog (CATAfrCommandHeaderAccess)
        ├── Dictionary (.dico)
        ├── NLS (CATNls)
        └── Imakefile (.mk)
```

10 个核心实体，每个有完整的 CRUD + 依赖追踪 + 级联删除。

## 构建管线详解

```
build_workspace(ws)
  │
  ├── 1. env.py: CAAEnvironment.load_config()
  │   └── catia_detector.py 动态扫描 CATIA 安装
  │
  ├── 2. setup_prerequisite_path()
  │   └── 链接 Framework Prerequisites → CATIA 安装
  │
  ├── 3. 生成 batch 脚本
  │   ├── tck_init.bat    ← 初始化 TCK 工具链
  │   ├── tck_profile.bat ← 加载编译 Profile
  │   ├── mkinit.bat      ← 初始化工作区
  │   └── mkGetPreq       ← 解析 Prerequisites
  │
  ├── 4. 执行 mkmk -u -a
  │   ├── parser.py 实时解析 stdout/stderr
  │   ├── 结构化错误: {file, line, code, message}
  │   └── 结构化警告: {file, line, code, message}
  │
  ├── 5. 编译后处理
  │   ├── copy_icons_to_runtime()  ← 图标 → win_b64/
  │   ├── verify_build()           ← 验证产物完整性
  │   └── 生成 build.json 缓存
  │
  └── 返回: {status, error_count, warning_count, duration, errors[], warnings[]}
```

## 运行时管线详解

```
start_catia_runtime(workspace_path)
  │
  ├── 1. 检查 CNEXT 是否已运行
  │   ├── 已运行 → stop_catia(force=False) 优雅关闭
  │   └── _clean_cnext_sessions() 清理热启动文件
  │
  ├── 2. 构建环境
  │   ├── CAAEnvironment.load_config()
  │   └── CATDLLPath += workspace/win_b64/code/bin
  │
  ├── 3. 生成启动 batch
  │   ├── tck_init → tck_profile → mkinit
  │   ├── set CATGraphicPath  ← 图标可见性
  │   └── cd workspace && call mkrun
  │
  ├── 4. 启动
  │   ├── DETACHED_PROCESS (CATIA 独立于 Python)
  │   └── CREATE_NO_WINDOW (抑制 cmd 弹窗)
  │
  └── 轮询检测 CNEXT.exe (30 次 × 0.5s)
```

## CLI 命令参考

```
cade build <workspace>          # mkmk 编译
cade dev <workspace>            # 编译 + 启动 (一键闭环)
cade run <workspace>            # 仅启动 CNEXT
cade diagnose [workspace]       # 诊断工作区问题
cade fix [--apply]              # 自动修复
cade plan <type> <name> <mod>   # 生成开发计划
cade impact <entity> <type>     # 变更影响分析
cade refactor rename <...>      # 重命名
cade refactor move <...>        # 移动
cade rollback --list            # 列出回滚点
cade rollback --id <id>         # 执行回滚
cade clean                      # 清理构建产物
```

## 测试架构 (L1-L6)

| 层级 | 描述 | 测试文件 | 数量 |
|------|------|----------|------|
| L1 | 单元测试 (函数级) | test_icons.py, test_token_*.py | 3 |
| L2 | 模块测试 (单模块) | test_refactor.py, test_repair_loop.py | 4 |
| L3 | 集成测试 (模块协作) | test_e2e_integration.py | 1 |
| L4 | 架构测试 (不变量) | test_l4_architecture.py | 1 |
| L5 | 语义测试 (正确性) | test_l5_semantic.py, test_specification.py | 2 |
| L6 | 故障注入 (鲁棒性) | test_l6_fault_injection.py | 1 |
| E2E | 端到端 (AI 模拟) | test_ai_integration.py, test_full_*.py | 3 |
| 回归 | 全量回归 | test_full_regression.py (1287 行) | 1 |
| 专项 | 特定功能 | test_phase*.py, test_skill_*.py 等 | 23 |

总计 39 个测试文件，~11,000 行测试代码。

## 图标分类统计

| 类别 | 数量 | 示例 |
|------|------|------|
| 形状 | 11 | box, circle, triangle, hexagon, diamond, ring |
| 操作 | 6 | play, drill, cut, cursor, move, merge |
| 箭头 | 8 | arrow-up/down/left/right, refresh, chevron |
| 工具 | 8 | settings, search, pencil, ruler, funnel, delete |
| 媒体 | 4 | pause, stop, forward, backward |
| 编辑 | 5 | copy, paste, undo, redo, zoom-in/out |
| 数据 | 9 | doc, folder, disk, export, import, book, db |
| 符号 | 7 | check, angle, chart, code, link, star, heart |
| 数学 | 6 | plus, minus, multiply, divide, equal, percent |
| 对象 | 8 | key, bell, tag, pin, flag, trophy, shield, clock |
| 通信 | 6 | mail, chat, phone, share, wifi, globe |
| 自然 | 5 | sun, moon, cloud, lightning, flame |
| 日常 | 8 | home, user, calendar, camera, map, battery, power |
| 3D | 4 | cube, contour, package, download/upload |
| 锁/UI | 6 | lock, unlock, window, eye, hand, info, warning, question |
| **合计** | **107** | |

## 配置系统

```
catalog/index.yaml        ← 知识索引
config/editors/*.json     ← 编辑器 MCP 模板 (Claude/Cursor/VSCode/Windsurf)
cache/build.json          ← 编译缓存
cache/generate.json       ← 生成缓存
cache/runtime.json        ← 运行时状态
intent/templates/task_templates.json ← 任务模板
requirements/decision_trees/*.yaml   ← 决策树 (3)
```

## Token 优化策略

`token_optimizer.py` 在 MCP 响应前自动压缩：
- **mode=auto**: 自动检测内容类型选择策略
- **mode=compact**: 移除冗余字段，保留核心数据
- **mode=summary**: 仅返回摘要 (status + counts)
- 平均节省 50-70% token，对 AI Agent 透明
