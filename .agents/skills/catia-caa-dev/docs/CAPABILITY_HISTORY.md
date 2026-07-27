# Capability History

> **给 AI 的架构记忆，不是审批系统。**
>
> 本文件回答一个问题：**"这个能力不是遗漏，是主动删除/关闭的。"**
> CADE 是 AI 开发辅助系统——未来的 Agent 不会主动 `git show <commit>` 去
> 理解某个能力为什么不存在。当 AI 检索不到某个看似应该存在的能力时，
> 应来这里确认它是被有意移除的，而不是一个待补的缺口。
>
> 范围：只记录**已删除 (removed)** 和**有意不可用 (unavailable)** 的能力。
> 活能力见 `skills/capabilities.yaml`（声明层）和 `tools/check_capabilities.py`
> （检测层）。保持文档级——不要在这里加 owner/maturity/依赖等字段，
> 那些属于 registry 的后续阶段。

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

---

## Unavailable（有意关闭，非 bug）

### expose_service
- **Status**: unavailable（见 `skills/capabilities.yaml`）
- **Since**: commit `71a6ad7`
- **Why not enabled**: CAA service exposure 是实验能力，未接 kernel intent
  router（`_detect_intent_type` 无 service 关键字）。
- **Boundary**: `cade expose` 在 router 层直接返回 `blocked / do_not_fix`，
  不进入 `develop()` 业务路径——让 Agent 读到"能力未开放"而非"执行失败"，
  避免触发自动修复循环。`services.py expose_service` 返回同样结构。
- **Enable condition**: kernel intent router 增加 service 意图并接通实现后，
  将 `capabilities.yaml` 中状态改为 active。

---

## 维护规程

- 删除一个能力时：在此追加一条（removed/commit/reason/restore condition）。
- 关闭一个能力时：登记到 Unavailable + `capabilities.yaml`。
- 恢复一个能力时：从对应条目删除，并在 `capabilities.yaml` 标记 active。
- **不要**把本文件扩成完整生命周期 registry——状态机留给
  `capabilities.yaml` 的后续阶段。本文件只负责"为什么不存在"。
