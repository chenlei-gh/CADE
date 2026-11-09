# ADR: CADE UI Semantic Layer

**Status**: Accepted (Phase 0 — documentation only, no code change)
**Date**: 2026-08-13
**Superseded-in-part (2026-08-14)**: the *clarification* layer is governed by
`UI_GENERATOR_CLARIFICATION_POLICY.md` — an empirically validated four-axis
boundary that is explicitly **not** a UI Semantic Model. This ADR's
"Semantic Model → generator" direction for dialog *generation* remains an
unvalidated hypothesis (Phase 0); do not treat it as the clarification
contract, and do not start Phase 1 without reverse-tracking evidence from a
real UI sample.
**Audience**: CADE developers and AI agents
**Scope**: the future direction of CADE's dialog/UI capability; does not yet
modify `create_dialog` or `templates/dialog/`

> CADE 不直接生成 Dassault 私有 UI 描述文件，而建立自身 UI Semantic Model，
> 通过后端生成 CATDlg 实现，并保留未来兼容 DSGen 的可能。

---

## 1. Context

CADE's current `create_dialog(ctx, name, module, framework)` emits a static
skeleton from `templates/dialog/DialogClass.{h,cpp}`: one `CATDlgFrame` +
one `CATDlgLabel` + one `CATDlgEditor`, hard-wired in the template body. It
has **no layout/pages/controls parameters** and **no user-code preservation
mechanism**. `create_dialog` uses `ChangeSet.add_create_file`, and
`ChangeSet._pre_validate_files` rejects a `created` path that already
exists — so **CADE today has no "regenerate" action at all**; it only
creates.

Two pressures force this decision:

1. **`.DSGen` was discovered** to be CAA **Dialog Designer**'s code
   generation file (visual drag-and-drop → `.DSGen` → mkmk invokes a
   dedicated generator → `LocalGenerated/` C++). It is a Dassault-private
   format with no public schema, and the designer does not update the
   Identity card or Imakefile. It is a **design-input layer**, not a thing
   CADE should emit or reverse-engineer.

2. **Users want to hand-edit generated dialogs.** Under the current
   template model this is impossible beyond a one-shot scaffold: there is
   no way to regenerate structure without losing hand-written logic.

The underlying insight: Dassault chose "semantic model → generator → C++"
decades ago for Dialog Designer. CADE is not inventing a new route — it is
re-implementing the same engineering idea in the AI era, with its own
semantic model instead of the closed `.DSGen`.

---

## 2. Decision

CADE will **not** generate `.DSGen`. It will build its own
**UI Semantic Model** and generate `CATDlg` C++ through a backend, keeping
a future `.DSGen` compatibility path open but out of scope for now.

The term is **UI Semantic Model**, not "UI DSL". A DSL invites premature
language design (parser, grammar). What CADE lacks is not syntax — it is an
**intent model**: *why* this control exists, *what* semantic role it fills,
*what task* a page performs. The model captures purpose and structure; the
backend decides concrete `CATDlg*` instantiation.

The Semantic Model is **CADE-controlled generation input**, not a universal
source of truth for all external UI representations.

```
User intent
     ↓
UI Semantic Model          ← CADE owns this (declarative, versioned)
     ↓
Backend
     ├── CATDlg C++         ← Phase 2
     └── .DSGen (future)    ← Phase 3 research only, not emission
```

---

## 3. Ownership Boundary (hand-editing)

**Ownership is a semantic invariant, not a filename convention.** `_Base`
is only the current implementation choice; the invariant below must hold
even if a future implementation uses `generated/`/`user/` directories or
`ownership: generated` metadata instead.

**Core invariant:**

> **CADE-owned files may be regenerated.
> User-owned files must never be implicitly overwritten.**

Concretely, for the current `_Base` mechanism:

| Region | Owner | Re-generated? | Hand-editable? |
|---|---|---|---|
| Structure / layout / resource binding | CADE (driven by semantic model) | Yes, overwritten | No |
| Callbacks / business logic | User | No | Yes |

- CADE emits `XxxDlg_Base.h` / `XxxDlg_Base.cpp`: structure, control
  instantiation, layout, NLS binding. Regenerated on every semantic change,
  **never hand-edited**.
- User writes `XxxDlg.h` / `XxxDlg.cpp`: inherits `XxxDlg_Base`, implements
  callbacks and business logic. **Never touched by CADE.**

This mirrors Dialog Designer's own model (grayed-out generated code +
callback injection), which is why it is the recommended default.

Ownership is file-level: a file is either CADE-owned or user-owned, never
both. A user-code-region approach (`// BEGIN USER CODE … END USER CODE`)
embeds user content inside a generated file and therefore introduces a
mixed-ownership file. This ADR does **not** define how such files are
handled on regeneration — it is neither adopted nor specified here.

**Hard boundary to acknowledge:** hand-editing *layout/control placement*
is the genuinely hard case — it diverges the semantic model from the
generated artifact, which is the *same trap as `.DSGen` bidirectional
sync*. This ADR therefore routes layout changes through the semantic model,
not through direct edits to generated C++.

---

## 4. Change Semantics (create vs. regenerate)

CADE today has file-level operations (`create`/`modify`/`patch`/`delete`)
but no **action-level** distinction between creating and regenerating. This
ADR introduces that distinction for dialogs:

**`create_dialog` remains creation-only.**

```
create_dialog:
  - creates a new dialog
  - fails if the target already exists
```

Keeping `create` a strong, non-mutating contract lets an agent know
unambiguously whether it is creating something new or modifying something
existing. It must not silently grow regeneration behaviour.

**A new `regen_dialog` capability is introduced** (only when
semantic-driven generation is implemented, i.e. Phase 2):

```
regen_dialog:
  - regenerates CADE-owned generated files
  - never overwrites user-owned files
  - does not implicitly mutate unrelated project files
```

```
Intent Action
      ↓
Change Semantics        ← create / regenerate (this ADR)
      ↓
File Operations         ← ChangeSet create/modify/patch/delete
```

`regen_dialog` is a **narrow capability**, not the start of a generic
`update_*` framework. Do **not** immediately design `regen_command`,
`regen_feature`, `regen_all`, or `update_project`. Extend only when a real,
measured need appears.

Evolution:

```
create_dialog
     │
     │ first creation
     ▼
┌──────────────────────┐
│  Generated Scaffold  │ ← CADE-owned
│  User Extension      │ ← User-owned
└──────────────────────┘
             │
             │ semantic change
             ▼
       regen_dialog
             │
             ├── regenerate scaffold
             └── preserve user extension
```

**Explicitly deferred:** the ChangeSet ownership/idempotency semantics
required to implement `regen_dialog` are a separate design task. This ADR
records the decision only; it does not implement `regen_dialog` now.

---

## 5. Roadmap & Implementation Checklist (符合 Dassault 官方交互标准)

基于 Exa 调研检索的 Dassault Systèmes 官方 CAADoc（`CAADegSampleDialogWithPanelState`、`class_CATPanelState`、`class_CATMmrPrtPanelStateCmd` 等）权威标准，将交互方案落地拆解为以下阶段性待办任务：

| 阶段 | 交付物 / 任务项 | 官方标准对齐项 | 状态 |
|---|---|---|---|
| **Phase 0** | **架构决策与所有权边界** | 确定 MVP 解耦架构，区分 CADE 生成层与用户扩展层 | ✅ 已完成 |
| **Phase 1** | **交互核心模板与代码骨架重构 (消除伪代码与历史隐患)** | | ✅ 已完成 |
| 1.1 | 重构 `CommandClass.{h,cpp}` 模板 | 消除虚构 API（如 `CATStateCondition`、错误的 `_pGlobalUndo->Begin()`）；引入官方标准 `CATPanelState` 自动状态流转；规范 `RequestDelayedDestruction()` 析构清理与 `Activate/Desactivate` 挂起恢复 | ✅ 已完成 |
| 1.2 | 规范 `DialogClass.{h,cpp}` 模板 | 严格遵循两阶段构造（Two-Phase Construction，构造函数绝不创建子控件，统一在 `Build()` 中实例化并绑定 NLS；提供 MVP 数据访问接口） | ✅ 已完成 |
| 1.3 | 规范 3D 选择代理（Selection Agent）标准模式 | 引入 `CATPathElementAgent` 标准配置（`CATDlgEngRepeat` + `IsLastModifiedAgentCondition` + `AddElementType` 显式类型过滤） | ✅ 已完成 |
| **Phase 2** | **全链路交互脚手架生成与装配 (Interactive Scaffold)** | | ✅ 已完成 |
| 2.1 | 交互组件一键联动生成 (Command + Dialog + Header + Addin + Dico + NLS) | 杜绝人工拼写不一致与漏配字典导致的“未知命令”或“按钮静默失败”；自动补全缺失的 UI 前置库 | ✅ 已完成 |
| 2.2 | 双模驱动支持 (批处理无头模式 vs 交互窗口模式隔离) | `SetVisibility(0)` 与无头安全分支，防止批处理下由于找不到主窗口产生空指针崩溃 | ✅ 已完成 |
| **Phase 3** | **交互静态合规守卫与安全拦截 (Interactive Linter)** | | ✅ 已完成 |
| 3.1 | 语法与生命周期反模式检查器 | 静态拦截 `delete pDialog`、`delete pAgent`、未判空的 `GetFrame()` 调用，强制要求 `RequestDelayedDestruction()` | ✅ 已完成 |
| 3.2 | 资源与字典联动自动化核验 | 检查命令头与实现类名称一致性、`.dico` 导出一致性，新增 Addin 自动修复计划 | ✅ 已完成 |
| **Phase 4** | **单元测试与全套验证闭环** | | ✅ 已完成 |
| 4.1 | 交互模板与生成器测试用例 | 覆盖模板变量替换、两阶段构造、语法自检（77/77 自动化测试全部通过） | ✅ 已完成 |
| 4.2 | 生产环境回归验证 | 确保现有 CADE 构建与业务工作区完全兼容，全量规则与测试闭环 | ✅ 已完成 |

The real Phase-3 hard problem is **Semantic ⇅ `.DSGen` bidirectional sync**
(which source owns the UI truth), not generation itself. It is deliberately
out of scope until Phases 1–2 prove the semantic model.

---

## 6. Layering

Do **not** stuff layout/pages/controls into the existing `create_dialog`
signature. The new capability lives in its own subtree, adopting a
`semantic` → `generator` → `validator` layering:

```
skills/
 └── ui/
      ├── semantic/           # Dialog Semantic Schema (declarative, versioned)
      ├── generators/
      │     └── catdlg/       # semantic model → CATDlg C++
      └── examples/           # worked examples
```

This keeps the UI capability from polluting the command/object-level
`intents/` layer.

---

## 7. Alternatives Considered

| Alternative | Verdict | Reason |
|---|---|---|
| Generate `.DSGen` directly | Rejected | Dassault-private format, no public schema; conflicts with the build-gate/fabricated-API goal |
| Reverse-engineer `.DSGen` by guessing | Rejected | Same as above; unstable, unmaintainable |
| Make `create_dialog` idempotent (regenerate on existing) | Rejected | Dilutes `create`'s contract; creation silently grows mutation semantics |
| Generic `update_*`/`regen_*` framework now | Rejected | Scope creep; one concrete need must not become a ChangeSet redesign |
| User-code regions instead of base/derived split | Not adopted | Introduces mixed-ownership files; handling rules are out of scope |

---

## 8. Consequences

- `create_dialog` keeps a strict, auditable contract: create-or-fail.
- Dialog ownership becomes first-class, so regeneration can never silently
  destroy user logic.
- CADE gains a "live regeneration source" model (semantic model → scaffold
  + user extension), which is the prerequisite for any future `.DSGen`
  compatibility.
- The `_Base` filename is implementation detail; the ownership invariant
  survives any future switch to `generated/`/`user/` or metadata ownership.

---

## 9. Non-Goals and Forbidden Inferences

This ADR is deliberately narrow. A capable but over-eager agent must not
derive any of the following from the positive statements above.

1. **No mixed-ownership file semantics.** This ADR does not define how a
   file containing both generated and user content is handled on
   regeneration. Ownership is file-level; a mixed-ownership file is not a
   model this ADR endorses, and its handling rules are out of scope.

2. **No ownership-tagging mechanism.** How a file is marked CADE-owned vs
   user-owned (filename suffix, metadata, provenance) is a ChangeSet /
   generation design concern. This ADR does not prescribe it.

3. **The Semantic Model is not a universal source of truth.** It is
   CADE-controlled generation input. This ADR does not claim it owns all
   external UI representations (e.g. a future Dialog Designer / `.DSGen`
   round-trip).

4. **Future `.DSGen` must not constrain the current Semantic Model.**
   Phases 1–2 must not reserve fields or structure for an unverified
   `.DSGen` capability.

5. **No automatic migration of existing dialogs.** Introducing
   `regen_dialog` does not authorize automatically migrating, splitting, or
   refactoring existing `create_dialog` artifacts. Existing dialogs are
   left as-is unless explicitly migrated by design.

---

*Related: `docs/architecture/retrieval.md` (retrieval contract),
`docs/CAPABILITY_HISTORY.md` (capability governance),
`templates/dialog/` (current template model to be superseded in Phase 2).*
