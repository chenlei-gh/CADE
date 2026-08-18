# 生成式图标规范（Generated Base Spec）

**Status**: v2 — 试点闭环（PartToAsm 通过 gate E 用户实机验收，2026-08-18）
**Date**: 2026-08-18
**Scope**: 仅用于官方 B28 图标库**无法语义匹配**的命令（DENY / CADE 自有语义）。
官方有等价图的一律继续用官方 BMP，本规范不介入。

> 生成产物是**开发期生成、提交入库的离线资产**，运行时零 API、零不确定性。
> 原料必须过后处理管线 + 验收门禁才算数。

---

## 1. 架构定位

```text
语义命中官方 → B28 官方 BMP（现状不变）
语义未命中   → Generated Base（本规范）→ 后处理管线 → 入库资产
              路径 A（已验证主路径）：LLM 像素设计
                     icon_design_lib 官方语素直接绘制 22×22
              路径 B（可选）：外部文生图 → §3 Prompt → 同一管线门禁
              ↓ 生成失败 / 验收不过（>3 次）
         I_P3DefaultIcon 兜底
```

**为什么路径 A 是主路径**（试点实证）：22×22 / ≤16 色 / 硬边像素画恰恰是
扩散模型的弱项（必然抗锯齿、控不住精确色板），而是 LLM 逐像素控制的强项；
且零外部工具、零成本、确定性可复现（设计源 .py 入库，资产可从代码重建）。

## 2. 风格规范（硬性提示词块，参数全部实测自官方库）

| 项 | 规范值 |
|---|---|
| 画布 | 最终 22×22（允许大图生成，但必须按像素画约束出图） |
| 背景 | 纯平 `(192,192,192)`（#C0C0C0），四角必须干净 |
| 描边 | 墨蓝 `(24,16,82)`（官方采样值，实体/齿轮系），1~2px 硬边 |
| 高光 | 白色，只在左上边缘（官方式浮起） |
| 填充 | 饱和纯色，单图 ≤16 色 |
| 主体 | **单主体**（禁止场景化构图），右下角留简（给 Badge 让位） |
| 铺满 | 实体类图标 fg ≈ 40~50%（用户裁决：24% 太小，**要铺满**；官方 I_Pad/I_Hole 即高视觉密度） |
| 禁止 | 抗锯齿 / 渐变 / 投影 / 文字 / 写实 / 3D 渲染感 / 现代扁平 UI 风 |

**官方采样调色板**（不猜色值，全部实测自 B28）：

| 色 | RGB | 用途 | 采样源 |
|---|---|---|---|
| 墨蓝 | `(24,16,82)` | 轮廓/伪3D挤出 | I_Pad/I_Hole |
| 实体黄 | `(255,255,150)` | PartDesign 实体正面 | I_Pad/I_Hole |
| 齿轮黄 | `(255,238,135)` | 齿轮面 | I_Part/I_Product |
| 齿轮毂 | `(255,255,0)` | 毂孔亮黄 | I_Part |
| 青齿轮 | `(75,230,255)` 边 `(0,157,167)` | 装配副齿轮 | I_Product |

## 2.1 官方词汇提取（试点验证的核心方法论）

**不发明视觉语言——先查官方怎么表达相邻语义：**

1. 找相邻语义的官方图标（PartToAsm → `I_Part` / `I_Product`）
2. 提取官方语义编码（**齿轮数 = 装配层级**：1 齿轮 = part，齿轮对 = product）
3. 采样官方原色（见上表）
4. 用同一编码组合新语义（左 1 齿轮 + 右齿轮对，间隙 = 转移，无需箭头）

验证过的语素已沉淀为 **`tools/icon_design_lib.py`**：`gear()` / `cube3d()` /
`frame()` / `swatches()` / `letter_a()` + 官方调色板常量。新图标直接调用，不重画。

B28 深度语义分析（3077 个 CATRsc 引用频次 + 40 个高频图标逐像素）见
**`knowledge/ui/official_icon_semantics.md`**。从中提取的储备语素
（`red_marker` / `dashed_copy` / `boss` / `notch` / `ctrl_point` /
`cycle_arrows` + `RED_MARK` / `REF_BLUE` / `DEPTH_GRAY`）已在 lib 定义但
**未经 gate E 验证**——仅在真实命令需要时接线，首次用于生产必须过完整 A–E 门禁。

## 3. Prompt 模板（仅路径 B 外部文生图使用）

路径 A（LLM 像素设计）不需要 Prompt——语义推理显式进行，隐喻直接画出来。
以下三层结构只在走外部文生图工具时使用。

**只给语义，隐喻由模型发明。** 任何视觉方向词（symbolic icon / moving
part / arrow / container……）都是替模型做设计——哪怕只缩减到一个对象。
本规范是受控实验：验证模型仅凭 CADE 语义 + CATIA 风格约束，能否自己
产生合格的 22×22 CATIA 风格单主体隐喻。

```text
[风格块，固定]
1990s CAD software toolbar icon, pixel art style, flat solid background
#C0C0C0, hard 1-2px dark-navy (#080867) outlines, saturated flat fills,
subtle white highlight on top-left edges, no anti-aliasing, no gradients,
no shadows, no text, centered composition, single clear subject occupying
about half of the canvas, keep bottom-right corner area simple.

[语义槽，每图标一段：纯语义，零视觉词]
Semantic intent: {semantic}

[隐喻自选块，固定]
Invent the simplest single-subject visual metaphor that communicates this
semantic intent. The choice of metaphor, geometry, objects, and colors is
yours — keep it minimal and symbolic.

[负向块，固定]
Negative: text, letters, watermark, gradient, blur, photorealistic,
3D render, glossy, modern flat UI, anti-aliased edges
```

模型支持参考图输入时，喂 2~4 张官方图做风格锚（如 `I_Hole` / `I_Pad`）。

### 当前试点 Prompt（PartToAsm，语义：零件转入装配）

```text
1990s CAD software toolbar icon, pixel art style, flat solid background
#C0C0C0, hard 1-2px dark-navy (#080867) outlines, saturated flat fills,
subtle white highlight on top-left edges, no anti-aliasing, no gradients,
no shadows, no text, centered composition, single clear subject occupying
about half of the canvas, keep bottom-right corner area simple.

Semantic intent: PartToAsm — moving/converting a part into an assembly
context.

Invent the simplest single-subject visual metaphor that communicates this
semantic intent. The choice of metaphor, geometry, objects, and colors is
yours — keep it minimal and symbolic.

Negative: text, letters, watermark, gradient, blur, photorealistic,
3D render, glossy, modern flat UI, anti-aliased edges
```

**同一 Prompt 变 seed 出 4~8 个候选，不改 Prompt 本体。** 全部丢
`tmp/gen_inbox/`，管线批量处理后出对比 sheet（候选 × 官方锚点并排）。

### 隐喻记录（试点核心产出）

4~8 个候选不是"挑一张最好看的"——评审时为每个候选记录**模型自己提出
的视觉隐喻**（填 gate JSON 的 `provenance.metaphor`）：

| 候选 | 模型隐喻 | A/B 机器门禁 | C 人工 | E 实机 |
|---|---|---|---|---|
| A | （评审时填） | | | |
| B | | | | |

这张表回答的是比单张 BMP 更有价值的问题：**对于 CADE 自有语义，文生图
模型到底能不能产生符合 CATIA 视觉语言的单主体隐喻。**

## 4. 后处理管线（`tools/icon_gen_pipeline.py`，确定性代码）

模型输出 PNG 丢入 `tmp/gen_inbox/`，管线执行：

1. 中心裁方 → LANCZOS 缩到 22×22
2. MedianCut 量化 ≤16 色（无抖动）
3. 背景吸附：四角采样，容差 36 内的像素强制归一 `(192,192,192)`
4. `_save_palette_bmp`：背景钉调色板索引 0 → 8-bit BMP（CNEXT 透明机制）
5. 出 8× 放大预览 PNG + 门禁报告 + provenance 草稿 JSON

## 5. 验收门禁（A–E，E 是最终裁决）

**A. 语义**：一眼表达目标语义（试点 = Part → Assembly），不是
Cube / Box / Move / Add 这类泛化读法。

**B. 构图**：单主体；无场景、无文字、无 UI、无多个独立对象堆叠、
不模拟 3D 渲染。

**C. 官方风格**：22×22 后仍清晰；1~2px 轮廓稳定；色块符合 B28 调色；
视觉重量接近官方；缩小后仍有 CATIA 味道。

**D. 工程**（管线自动硬门禁，不过直接打回）：

- 22×22、8-bit indexed BMP、≤16 色、背景钉调色板索引 0、四角纯背景
- 主体占比 fg% ∈ [15%, 70%]（官方实测区间）
- CNEXT 能正常读取

**E. CATIA 实机（最终裁决）**：

- 像素指标漂亮 ≠ 工具栏里看起来正确（此前犯过这个方法论错误）
- 流程：机器指标 → 人工视觉验收（8× 对比 sheet + 隐喻记录）→
  CATIA 22×22 Toolbar 实机 → PASS / REJECT
- 单图标重生 ≤3 次；超过则降级（LLM 像素设计 / 兜底图）
- 指标硬门禁只有人工验收时可豁免（须记录理由）

## 6. Badge 条款

- Badge **一律程序化叠加**（`_render_badge_plate` 现有路径），不让文生图画
  10px 小字形——它画不好，且角标统一是家族感来源
- **箭头/Badge 边界**：转移/方向语义若属于主体语义本身（如 PartToAsm
  的 "→"），允许由生成主体表达，此时经人工验收可省略 Badge 避免双重
  语义；创建/删除/编辑等操作动词永远走程序化 Badge，不交给生成
- 不在 Prompt 中指定箭头颜色——官方风格审计未证明"绿色箭头"是 B28
  稳定语义元素

## 7. 命名与溯源

- 生成资产 stem 前缀 `I_CADE*`（与官方 `I_*` 一眼区分），如 `I_CADEPartToAsm`
- 入库位置：`assets/icons/generated/<stem>.bmp` + 同名 `.json` provenance：

```json
{
  "stem": "I_CADEPartToAsm",
  "semantic": "parttoasm",
  "model": "<生成模型>",
  "prompt": "<完整 prompt>",
  "seed": null,
  "generated_at": "<日期>",
  "pipeline": "icon_gen_pipeline.py v1",
  "gate": {"colors": 12, "fg": 0.42},
  "approved_by": "user",
  "approved_at": "<日期>"
}
```

## 8. 一致性措施

同一模型、同一风格块、同一管线、同批出对比 sheet（`--batch` 自动生成
候选 × 官方锚点并排图）。四个图标必须是"一家人"，风格漂移的单独
重生成，不接受"各自漂亮"。

## 9. 试点闭环（PartToAsm）— **已完成**

```text
CADE Semantic (parttoasm)
  → Official Pool 证明无合适官方图（S5 已完成）
  → LLM 像素设计 ×6 隐喻候选（插入/环抱/包容/落位/附着/箭头）
  → 管线门禁（22×22 / ≤16 色 / 背景吸附 / 调色板 BMP）
  → 对比 sheet 人工 Visual QA → 用户指出官方齿轮词汇（关键转折）
  → 官方词汇提取（I_Part/I_Product）+ 采样原色 + 铺满修正
  → CATIA 22×22 Toolbar 实机 → **PASS（2026-08-18 用户验收）**
  → 入库 I_CADEPartToAsm.bmp + .json provenance + .py 设计源
```

**试点结论**：

1. Official Asset + Generated Asset 能覆盖官方不存在的 CADE 语义 ✓
2. LLM 像素设计是 Generated Base 的合格主路径 ✓
3. 官方词汇提取是最有效的隐喻来源（用户直觉 > 模型自由发明）✓
4. 设计源 .py 入库使资产可从代码确定性重建（已验证 0/484 像素差）✓

**Primitive 删除的依赖条件已满足**：试点 E 通过，71 Primitive 的删除
获得工程依据（它们本就已于 v13 删除，此处确认无回退必要）。
