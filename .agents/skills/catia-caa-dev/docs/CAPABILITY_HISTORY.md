# Capability History

> **给 AI 的架构记忆，不是审批系统。**
>
> 本文件回答一个问题：**"这个能力不是遗漏，是主动删除/关闭的。"**
> CADE 是 AI 开发辅助系统——未来的 Agent 不会主动 `git show <commit>` 去
> 理解某个能力为什么不存在。当 AI 检索不到某个看似应该存在的能力时，
> 应来这里确认它是被有意移除的，而不是一个待补的缺口。
>
> 范围：只记录**已删除 (removed)** 和**有意不可用 (unavailable)** 的能力。
> 活能力见 `skills/lifecycle.yaml`（生命周期声明层）、`capabilities.yaml`
> （路由契约层）和 `tools/check_capabilities.py`（检测层）。保持文档级——
> 不要在这里加 owner/maturity/依赖等字段，那些属于 registry 的后续阶段。

---

## Removed

### suggest_next_action
- **Removed**: commit `1ef2cee`（原 `intents/recommendation.py`，212 行）
- **Reason**: 无 runtime 路由——没有任何 kernel/CLI 入口调用它。属于 Phantom
  Capability（文件+函数+语义存在，入口+运行路径缺失）。
- **Superseded by**: verifier-driven repair flow（RepairLoop 产生修复建议）。
- **Restore condition**: 仅当 RepairLoop 需要独立的"下一步动作规划"能力时，
  从 git 历史恢复并先接 kernel 路由。

### optimizer (cmd_optimize / intent/optimizer.py)
- **Removed**: commit `1ef2cee`（`intent/optimizer.py`，166 行 + `cade.py` 入口）
- **Reason**: CLI 存在但无执行能力——`cade optimize` 只返回分析文本，没有
  真正的优化对象。`score_plan/optimize/recommend/compare` 无生产调用方。
- **Restore condition**: 当 planner 产生多个候选 plan、需要真实排序/择优时。

### diagnose_and_fix
- **Removed**: commit `1ef2cee`（原 `diagnostics.py` 内函数）
- **Reason**: 一次性 diagnose+apply-all，已被 RepairLoop（诊断→修复→验证
  重试循环）取代。两个修复系统并存会让 AI 误判该用哪个。
- **Superseded by**: `repair.py` / RepairLoop。

### skills/intents.py（孤儿模块文件）
- **Removed**: commit `9363428`（22 行）
- **Reason**: 被 `intents/` 包目录遮蔽——Python 优先解析包，这个同名 `.py`
  文件永远不会被 import，是死代码。存在即误导。

### run_catia_with_runtime
- **Removed**: commit `9363428`（原 `run.py` 内函数）
- **Reason**: 与 `start_catia_runtime` 功能重复且不被调用。
- **Superseded by**: `start_catia_runtime(workspace_path=...)`。

### create_ui_dialog
- **Removed**: commit `1ef2cee`（原 `intents/commands.py` 内函数）
- **Reason**: kernel 的 `with_dialog=True` 路径已在内部实现对话框生成，
  该独立入口造成同一能力两个入口（路径分叉）。

### workspace_build_config
- **Removed**: 函数早已删除（commit `9363428`），SKILL.md 文档行于
  `96163a4` 移除。
- **Reason**: 无入口。是反向 Phantom——文档承诺了代码里不存在的能力
  （`from build import workspace_build_config` 会 ImportError）。

### expose_service
- **Removed**: 架构减法退役（Phase 1 历史残留清理）。
- **Reason**: 未接入 kernel intent router，长期以 `blocked / do_not_fix` 存留；
  CADE 现行架构闭环不维护不可用运行时概念，因此物理退役该能力、CLI 入口及关联测试。
- **Restore condition**: 若未来有真正的服务暴露需求，基于完备的 IDL/TIE 代码生成与
  Kernel Router 支持重新设计引入。

### spec_generation
- **Removed**: 架构减法退役（Phase 2 Specification 实验支线整链退役）。
- **Reason**: 未接入 kernel 生产管线（原 `skills/experimental/specification.py` 与
  `generator.generate_from_spec()` 构成未被生产使用的第二套实验生成链）。生产管线
  统一采用 Requirement → Intent → Planner → ChangeSet/Writer → Verification 闭环。
- **Restore condition**: 若未来确有 Spec 驱动的独立抽象需求，应先定义好与 Kernel 生产
  管线的端到端集成契约后再行引入，不维护悬空实验链。

### readiness_check / cade check
- **Removed**: 架构减法退役（Phase 3 旧质量门退役）。
- **Reason**: 原 `tools/production_readiness_check.py` 仅为早期泛 Python 指标清单
  （grep TODO/password、行数/文件数统计等），完全不覆盖 CATIA CAA 编译器工具链、
  构建门禁、领域模型与生命周期核心安全；且 `cmd_check` 仅为薄壳子进程包装。
- **Architectural Decision**: 不保留 `cade check` 命令，亦不创建新的综合聚合包装层
  （避免重新引入职责混杂、语义模糊的“万能入口”）；引导全面收敛至职责清晰的现役专项入口：
  - 测试套件全量/快速回归：`cade test [--quick]` / `python test_master.py`
  - 环境与工作区健康诊断：`cade health [workspace]`
  - 静态代码与依赖审查：`cade validate [workspace]`
  - 框架依赖合法性验证：`cade prereq validate [workspace]`
  - 架构能力契约审计：`python tools/check_capabilities.py`
  - 全局交叉一致性审计：`python tests/test_cross_reference.py`
- **Restore condition**: 永久退役；不设单点聚合质量门，各专项质量门保持独立可验证。

---

## Unavailable（有意关闭，非 bug）

### create_feature
- **Status**: unavailable（见 `skills/lifecycle.yaml`）
- **Why not enabled**: feature 模板经 B28 全目录核实基于不存在的 API（CATIMmiResultFeature / SetResult / catalog 调用链，见 `knowledge/failure_patterns/fp_template_feature_apis.md`）。
- **Boundary**: `create_feature()` 返回 `status: error` 并附不可用原因与替代指引（手工基于 CATMecModUseItf 开发）；在 `skills/lifecycle.yaml` 中标记为 `unavailable` 与 `action: do_not_fix`，禁止 Agent 误判为临时故障并尝试自动修复。
- **Enable condition**: 基于真实 B28 CATMecModUseItf 规范重新验证并实现新特征模板与生成逻辑后，将 `lifecycle.yaml` 状态改为 active。

---

## 维护规程

- 删除一个能力时：在此追加一条（removed/commit/reason/restore condition）。
- 关闭一个能力时：登记到 Unavailable + `skills/lifecycle.yaml`。
- 恢复一个能力时：从对应条目删除，并在 `lifecycle.yaml` 标记 active。
- **不要**把本文件扩成完整生命周期 registry——状态机留给
  `lifecycle.yaml` 的后续阶段。本文件只负责"为什么不存在"。
