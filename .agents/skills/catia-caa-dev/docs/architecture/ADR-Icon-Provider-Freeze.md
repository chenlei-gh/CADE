# ADR: Icon Provider Architecture Freeze

**Status**: Accepted (documentation freeze only, no code change)
**Date**: 2026-08-14
**Baseline**: `b1cc725` (icon tests 58/58, master suites 41/41)
**Audience**: CADE developers and AI agents
**Scope**: freeze the Icon Provider architecture after S1–S4; does **not**
modify `icon_provider.py`, `DOMAIN_MAP`, primitives, production commands,
or CATIA resources

> CADE 默认仍是 127 Primitive + 现有 Badge。Official Base 只是未来按真实
> 需求启用的 16 项显式白名单：不建库、不扫 B28、不模糊匹配、不做 Overlay。

---

## 1. Context

S1–S4 用只读审计回答了三个容易走偏的问题：

1. 多样性不足，是不是因为 127 primitives 太少？
2. 是不是必须上 Icon Grammar / Modifier？
3. 是不是应该把 CATIA 官方图标做成新的主路径？

证据给出的答案都是否定的（或至少：当前没有充分证据继续造架构）。
冻结是方案的一部分，不是项目没做完。

---

## 2. Decision

Icon Provider 进入 **冻结 + 真实需求驱动维护**：

```text
真实语义
  │
  ├─ CREATE / 无 operation 且命中 16 项 Official 白名单
  │        ↓
  │   CATRsc Icon.Normal = "I_Xxx"
  │   （运行时引用 B28 normal/，工作区 0 个官方 BMP）
  │
  └─ 其它动词 / 未命中 / CATIA 未安装 / 语义不等价
           ↓
      127 Primitive + 现有 Badge
```

**当前实现状态**：生产路径仍是 127 Primitive + Badge。
16 项 Official Base **只是设计冻结，未实现**。不得把本 ADR
读成「Official Base 已上线」或「现有工具栏图标已达到 CATIA 原生风格」。

更准确的分层不是「两套平级图标库」，而是：

```text
CATIA Official Semantic Base
    ↓  “CATIA 已经定义过这个语义”

CADE Primitive Fallback
    ↓  “CATIA 没定义过这个语义”
```

---

## 3. Layered Outcome (do not collapse)

| 目标 | 状态 |
|---|---|
| 架构目标 | **达到** |
| 复杂度控制 | **达到** |
| 官方视觉语言接入**路径** | **达到** |
| 最终图标视觉产品目标 | **尚未验证，不能宣布完成** |

现有四个生产命令（`CAAAutoColor` / `CAAAutoRename` / `CAABOMTool` /
`CAAPartToAsm`）继续走 Primitive + Badge。它们在 Official Coverage
审计中 **HIGH = 0**，不得为了「看起来更官方」强行套相近文件名。

---

## 4. Evidence Summary

数字必须按集合分开，禁止合成一个「覆盖率」。

### S1 — Semantic resolver (command-name benchmark)

Phase A 补 `DOMAIN_MAP` / `VERB_MAP` / 连续前缀归一化。
89 个命令名审计集（真实命令 + 构造样本 + 测试命令的**混合集**）：
semantic coverage ≈ 91%，FALLBACK ≈ 9%。
这是 **Icon Resolver Semantic Benchmark Coverage**，
**不是** production coverage。

### S2 — Semantic cases

对话中曾出现「73 条」口径，**那份清单未落盘**。
本轮按同一口径重建 **70** 条真实语义案例（0 synthetic）。
不得声称「找回原来的 73 条」。

重建 70 条对照 B28 `normal/`（约 9832 个 `I_*.bmp`）的 Official
Coverage：

| 分类 | 数量 | 含义 |
|---|---:|---|
| OFFICIAL_HIGH | 38 (54%) | 语义等价，将来可进 Resolver |
| OFFICIAL_AMBIGUOUS | 22 (31%) | 能找到文件，但不能自动引用 |
| PRIMITIVE_ONLY | 7 | 官方视觉语言没有对应命令图标 |
| NONE | 3 | 无候选 |

Object Coverage = 100%。New Primitive = 0。
Grammar Pressure = 2.7%，且仅 MED confidence。

**不要追求 Official HIGH 越高越好。** 文件名相近 ≠ 语义等价
（例如 `AutoRename` 对上 `I_Rename` 仍应 fallback）。

### S3 — Regression baseline

`b1cc725`：58/58 icon tests，41/41 master suites。
ACTIONABLE_FALLBACK = 0（剩余 fallback 为测试夹具 / CAA 框架类 /
无语义名称；分类存在重叠，禁止写成 `17+8=25`）。

### S4 — Official Base mechanism

- **S4-A**：Resolver 必须语义驱动，禁止 `"I_" + object + ".bmp"` 拼接。
  Sketch → `I_Sketcher`（不是 `I_Sketch`）；
  Boolean Remove → `I_RemoveBody`（不是泛化 `I_Remove`）。
- **S4-B**：CNEXT 能直接读取官方 4/8-bit 22×22 BMP。
  **只实机验证了 2 个样本**（`I_Hole.bmp` 4-bit、`I_Pad.bmp` 8-bit），
  不是 16 项都已实机。隔离区不在本仓库。
- Overlay / Grammar / 大规模映射表：**不做**。

---

## 5. Official Base v1 (design freeze, not implemented)

正好 **16 项**。已排除 `Fillet`（Edge / Face 歧义）。

| Semantic | Official resource |
|---|---|
| Hole | `I_Hole` |
| Pad | `I_Pad` |
| Pocket | `I_Pocket` |
| Chamfer | `I_Chamfer` |
| Draft | `I_Draft` |
| Shell | `I_Shell` |
| Shaft | `I_Shaft` |
| Groove | `I_Groove` |
| Rib | `I_Rib` |
| Slot | `I_Slot` |
| Mirror | `I_Mirror` |
| Split | `I_Split` |
| Line | `I_Line` |
| Plane | `I_Plane` |
| Point | `I_Point` |
| Circle | `I_Circle` |

启用条件（全部满足才允许写那一行显式映射）：

1. 出现真实生产命令（不是审计样本）
2. object 与白名单项**语义等价**
3. operation = CREATE 或空
4. 不需要 badge 即可表达

### 明确不进 v1

`Fillet`、`Sweep`、`Sketch`（必须 `I_Sketcher`，命名陷阱）、
Pattern 系列、`Assemble` / `RemoveBody`、`Part` / `Product`、
四个生产命令、BOM / Rename / Color。

### 扩表唯一条件

真实命令 + 语义等价 + CREATE/空 + 不需要 badge。
**不为覆盖率加词。**

---

## 6. Forbidden (until a reopen condition fires)

- 修改 `icon_provider.py` / `DOMAIN_MAP` / 127 primitives
- 扫描或复制 B28 `normal/`（约 9832 个 `I_*.bmp`）进仓库
- 建立 Official Icon Library
- 模糊匹配 / 相似度搜索官方图标
- Overlay / Modifier / State / Context / Icon Grammar
- 为消灭 fallback 增加 suffix / token 规则（先验证跨上下文语义竞争）
- 把审计脚本、S4-B 隔离区、官方 BMP 纳入本仓库
- 征用现有四个生产命令做图标实验

官方资源位置（只读核实，不入库）：

`C:/Program Files/Dassault Systemes/B28/win_b64/resources/graphic/icons/normal/`

---

## 7. Reopen Conditions

只允许下面两条重新打开本主题。其它「感觉不够丰富」一律拒绝。

1. **出现命中白名单的真实 `CreateXxxCmd`**
   → 只写那一行显式映射，运行时引用 `I_Xxx`，回归 icon tests。
2. **四个生产图标在 22×22 Toolbar 被证明不够像 / 不够认**
   → 单独 Visual QA（线宽、对比、badge 重量），**不动架构**。

---

## 8. Consequences

- KPI 从「图案数量」降级。有价值的是 Object Coverage、
  New Primitive Pressure、Grammar Pressure、
  Official HIGH（语义等价，不是文件命中）、
  ACTIONABLE_FALLBACK、以及尚未评估的 Official Style Fidelity。
- SKILL.md 仍写「123 个几何图案」——本 ADR **不顺手改正**该计数；
  权威实现计数以 `icon_provider.py` 为准（冻结时为 127）。
- 下次改 Icon Provider 必须先回答：「它解决了哪个真实命令？」
