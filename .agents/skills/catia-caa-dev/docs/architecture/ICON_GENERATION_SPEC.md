# 文生图图标规范（Generated Base Spec）

**Status**: v1 试点（pilot = PartToAsm 一个图标，验收通过后回写 ADR）
**Date**: 2026-08-18
**Scope**: 仅用于官方 B28 图标库**无法语义匹配**的命令（DENY / CADE 自有语义）。
官方有等价图的一律继续用官方 BMP，本规范不介入。

> 文生图产物是**开发期生成、提交入库的离线资产**，运行时零 API、零不确定性。
> 模型出图只是原料，必须过后处理管线 + 验收门禁才算数。

---

## 1. 架构定位

```text
语义命中官方 → B28 官方 BMP（现状不变）
语义未命中   → 文生图（本规范）→ 后处理管线 → 入库资产 → Badge 程序化叠加
              ↓ 生成失败 / 验收不过（>3 次）
         LLM 像素设计 或 I_P3DefaultIcon 兜底
```

## 2. 风格规范（硬性提示词块，参数全部实测自官方库）

| 项 | 规范值 |
|---|---|
| 画布 | 最终 22×22（允许大图生成，但必须按像素画约束出图） |
| 背景 | 纯平 `(192,192,192)`（#C0C0C0），四角必须干净 |
| 描边 | 墨蓝 `(8,8,103)`（#080867），1~2px 硬边 |
| 高光 | 白色，只在左上边缘（官方式浮起） |
| 填充 | 饱和纯色，单图 ≤16 色 |
| 主体 | **单主体**（禁止场景化构图），居中，占画布 ~50%，右下角留简（给 Badge 让位） |
| 禁止 | 抗锯齿 / 渐变 / 投影 / 文字 / 写实 / 3D 渲染感 / 现代扁平 UI 风 |

## 3. Prompt 模板（固定三段式，只换主题槽）

```text
[风格块，固定]
1990s CAD software toolbar icon, pixel art style, flat solid background
#C0C0C0, hard 1-2px dark-navy (#080867) outlines, saturated flat fills,
subtle white highlight on top-left edges, no anti-aliasing, no gradients,
no shadows, no text, centered composition, single clear subject occupying
about half of the canvas, keep bottom-right corner area simple

[主题槽，每图标一句，几何名词]
{subject}

[负向块，固定]
text, letters, watermark, gradient, blur, photorealistic, 3D render,
glossy, modern flat UI, anti-aliased edges
```

模型支持参考图输入时，喂 2~4 张官方图做风格锚（如 `I_Hole` / `I_Pad`）。

### 当前试点 Prompt（PartToAsm，语义：零件转入装配）

```text
1990s CAD software toolbar icon, pixel art style, flat solid background
#C0C0C0, hard 1-2px dark-navy (#080867) outlines, saturated flat fills,
subtle white highlight on top-left edges, no anti-aliasing, no gradients,
no shadows, no text, centered composition, single clear subject occupying
about half of the canvas, keep bottom-right corner area simple:
a small solid steel-blue cube representing a mechanical part, with a bold
green arrow pointing from the cube into a larger hollow dark-navy square
frame representing an assembly

Negative: text, letters, watermark, gradient, blur, photorealistic,
3D render, glossy, modern flat UI, anti-aliased edges
```

## 4. 后处理管线（`tools/icon_gen_pipeline.py`，确定性代码）

模型输出 PNG 丢入 `tmp/gen_inbox/`，管线执行：

1. 中心裁方 → LANCZOS 缩到 22×22
2. MedianCut 量化 ≤16 色（无抖动）
3. 背景吸附：四角采样，容差 36 内的像素强制归一 `(192,192,192)`
4. `_save_palette_bmp`：背景钉调色板索引 0 → 8-bit BMP（CNEXT 透明机制）
5. 出 8× 放大预览 PNG + 门禁报告 + provenance 草稿 JSON

## 5. 验收门禁

**自动硬门禁**（不过直接打回重生）：

- 22×22、≤16 色、四角纯背景（管线保证）
- 主体占比 fg% ∈ [15%, 70%]（官方实测区间）

**人工门禁**：

- 8× 放大对比图过目，与官方图标并排看是否"一家人"
- 单图标重生 ≤3 次；超过则降级（LLM 像素设计 / 兜底图）
- 指标硬门禁只有人工验收时可豁免（须记录理由）

## 6. Badge 条款

- Badge **一律程序化叠加**（`_render_badge_plate` 现有路径），不让文生图画
  10px 小字形——它画不好，且角标统一是家族感来源
- 若生成主体本身已含操作语义（如箭头），经人工验收可省略 Badge，避免双重语义

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

同一模型、同一风格块、同一管线、同批出对比 sheet。四个图标必须是"一家人"，
风格漂移的单独重生成，不接受"各自漂亮"。
