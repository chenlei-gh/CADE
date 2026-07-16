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
