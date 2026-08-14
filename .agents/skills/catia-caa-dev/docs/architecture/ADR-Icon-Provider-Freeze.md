# ADR: Icon Provider Architecture

**Status**: Accepted (Official Base overlay implemented)
**Date**: 2026-08-14
**Baseline**: `4b6abb2` freeze docs + Official Base (`CACHE_VER=v11`) + primitive cull (`CACHE_VER=v12`)
**Audience**: CADE developers and AI agents
**Scope**: semantic resolver stays frozen; rendering gains a runtime Official
Base layer. Does **not** copy B28 BMPs into the repo.

> CADE 默认仍是 71 Primitive + 现有 Badge。
> Official Base 是**运行时检索**：对本机 B28 `normal/I_*.bmp` 做有限精确
> 候选 `exists()`，命中则当底图再叠现有 Badge；未命中 / 歧义 / 语义不等价
> 则 Primitive。官方文件不进仓库。

---

## 1. Context

S1–S4 用只读审计回答了三个容易走偏的问题：

1. 多样性不足，是不是因为当时的 127 primitives 太少？（后裁到 71）
2. 是不是必须上 Icon Grammar / Modifier？
3. 是不是应该把 CATIA 官方图标做成新的主路径？

证据给出的答案：

- Primitive 规模够用（S2 Object Coverage 100%，New Primitive 0）
- Grammar 暂无充分需求（Pressure 2.7%，MED）
- 官方图标**值得作为 Base**，但不值得做成 9832 文件扫描 / 模糊匹配子系统

用户随后明确产品目标：

> 运行时检索本机 B28 官方 `normal/I_*.bmp` 作为 Base，再叠 CADE 现有 Badge。
> 官方文件不进 CADE。不是 16 项入库，也不是只引用 `Icon.Normal = "I_Hole"`。

因此本 ADR 从「16 项白名单、禁止 Overlay、未实现」修订为
「有限候选检索 + Overlay，已实现」。

---

## 2. Decision

```text
命令名
  → analyze_command()          # 语义不变
  → Official Resolver
        有限候选 exists()
        │
        ├─ HIGH + 语义可接受
        │      ↓
        │  本机 I_*.bmp（只读）
        │      + 现有 Badge
        │
        └─ 未命中 / 歧义 / DENY / 未安装
               ↓
          71 Primitive + 现有 Badge
               ↓
          写出工作区 I_<命令名>.bmp
          CATRsc Icon.Normal = "I_<命令名>"
```

**不是**把 CATRsc 改成 `"I_Hole"`。叠了 Badge 后必须指向合成结果。

更准确的分层：

```text
CATIA Official Semantic Base
    ↓  “CATIA 已经定义过这个语义，且文件名精确可对上”

CADE Primitive Fallback
    ↓  “CATIA 没定义过，或对不上，或 CADE 自有语义”
```

---

## 3. Official Resolver rules

禁止 `"I_" + object` 盲拼，禁止 `glob('I_Hole*')` 取第一张。

1. **DENY**（语义不等价，即使文件存在也不用）  
   `rename` / `bom` / `color` / `tool` / `feature` / `element` /
   `properties` / `mode` / `numeric` / `assemble` / `loft` / `axis` /
   `boss` / `reference`  
   四个生产命令因此保持 Primitive：
   `CAAAutoColor` / `CAAAutoRename` / `CAABOMTool` / `CAAPartToAsm`
2. **命名陷阱别名**（不是覆盖率白名单）  
   `sketch → I_Sketcher`  
   `remove → I_RemoveBody`  
   `pattern + circular → I_CircularPattern`  
   `pattern + rectangular → I_RectangularPattern`  
   泛化 `pattern`（无修饰）→ Primitive（没有 `I_Pattern.bmp`）
3. **弱对象**（`part` / `product` / `body` / …）  
   仅当没有非噪声 modifier 时才试 `I_Part.bmp` 等。  
   `PartToAsm` 的 `asm` 会挡住，避免套 `I_Part`。
4. **否则**试精确 `I_{Pascal(obj)}.bmp`。  
   `I_Hole` 与 `I_Hole3D` 同时存在时只用精确名，忽略变体。  
   精确名不存在、只有变体（`loft` / `axis`）→ Primitive。
5. Overlay：有 badge 就叠，**包括 CREATE 的 `+`**。  
   满幅官方图标（如 Hole）叠 badge 可能偏挤——先实现，用预览验证，
   不做空位检测 / Grammar。

检索路径来自 `config/caa_env_config.txt` 的 `CATIA_INSTALL` +
`win_b64|intel_a/resources/graphic/icons/normal`。未安装则全部 Primitive。
探测失败不得写配置、不得抛错。

---

## 4. Layered Outcome (do not collapse)

| 目标 | 状态 |
|---|---|
| 架构目标 | **达到** |
| 复杂度控制 | **达到**（无 9832 扫描、无独立图标库） |
| 官方视觉语言接入路径 | **达到且已实现** |
| 最终图标视觉产品目标 | **部分验证**：S4-B 证明 CNEXT 可读官方 4/8-bit；Overlay 需实机再看 |

---

## 5. Evidence Summary

数字必须按集合分开，禁止合成一个「覆盖率」。

### S1 — Semantic resolver (command-name benchmark)

Phase A 补 `DOMAIN_MAP` / `VERB_MAP` / 连续前缀归一化。
89 个命令名审计集（真实命令 + 构造样本 + 测试命令的**混合集**）：
semantic coverage ≈ 91%，FALLBACK ≈ 9%。
这是 **Icon Resolver Semantic Benchmark Coverage**，
**不是** production coverage。本轮 **不改** `analyze_command()`。

### S2 — Semantic cases

对话中曾出现「73 条」口径，**那份清单未落盘**。
按同一口径重建 **70** 条真实语义案例（0 synthetic）。
不得声称「找回原来的 73 条」。

重建 70 条对照 B28 `normal/`（约 9832 个 `I_*.bmp`）的 Official
Coverage：

| 分类 | 数量 | 含义 |
|---|---:|---|
| OFFICIAL_HIGH | 38 (54%) | 语义等价，可进 Resolver |
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

- **S4-A**：Resolver 必须语义驱动。Sketch → `I_Sketcher`；
  Boolean Remove → `I_RemoveBody`。
- **S4-B**：CNEXT 能直接读取官方 4/8-bit 22×22 BMP。
  **只实机验证了 2 个样本**（`I_Hole.bmp` 4-bit、`I_Pad.bmp` 8-bit）。
- Overlay：本轮在渲染层实现；满幅图标是否好看由预览 / 实机判断，
  不因此回退整个 Official Base。

---

## 6. Forbidden

- 扫描或复制 B28 `normal/`（约 9832 个 `I_*.bmp`）进仓库
- 建立 Official Icon Library / 把官方原件写入 ChangeSet
- 模糊匹配 / 相似度搜索官方图标
- `glob('I_Hole*')` 取第一张
- Modifier / State / Context / Icon Grammar
- 为消灭 fallback 增加 suffix / token 规则（先验证跨上下文语义竞争）
- 把审计脚本、S4-B 隔离区、官方 BMP 纳入本仓库
- 征用现有四个生产命令做图标实验
- 为 AutoRename 用 `I_Rename`、为 BOM 用 `I_BomLeft`、为 Color 用 `I_ColorChooser`
- 改 `analyze_command()` / `DOMAIN_MAP` 只为提高官方命中率
- 顺手改正 SKILL.md「123 个图案」计数

官方资源位置（只读，不入库）：

`C:/Program Files/Dassault Systemes/B28/win_b64/resources/graphic/icons/normal/`

---

## 7. Reopen Conditions

只允许下面几条重新打开本主题。其它「感觉不够丰富」一律拒绝。

1. **真实生产命令命中 Official，但选错了文件**  
   → 只加一条别名或 DENY，回归 icon tests。
2. **满幅官方图标 + Badge 在 Toolbar 被证明不可用**  
   → 只对该 object 跳过 Overlay 或跳过 Official，不做空位检测引擎。
3. **四个生产图标在 22×22 Toolbar 被证明不够像 / 不够认**  
   → 单独 Visual QA（线宽、对比、badge 重量），**不动架构**。

---

## 8. Consequences

- KPI 从「图案数量」降级。有价值的是 Object Coverage、
  New Primitive Pressure、Grammar Pressure、
  Official HIGH（语义等价，不是文件命中）、
  ACTIONABLE_FALLBACK、以及尚未评估的 Official Style Fidelity。
- SKILL.md 仍写「123 个几何图案」——本 ADR **不顺手改正**该计数；
  权威实现计数以 `icon_provider.py` 为准（71；从 127 裁掉 56 个无语义引用的装饰图案）。
- 下次改 Icon Provider 必须先回答：「它解决了哪个真实命令？」
- `CACHE_VER` = `v12`；缓存键含官方 stem，旧缓存自动失效。
