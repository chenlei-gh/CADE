# 生成式图标规范（Generated Base Spec）

**Status**: v3 — Ultra-3D 工业写实与透明多尺度规范（PartToAsm 真实闭环验收，2026-09-17）
**Date**: 2026-09-17
**Scope**: 仅用于官方 B28 图标库**无法语义匹配**的命令（DENY / CADE 自有语义）。
官方有等价图的一律继续用官方 BMP，本规范不介入。

> 生成产物是**开发期生成、提交入库的离线资产**，运行时零 API、零不确定性。
> Master 原稿采用 512×512 高精度透明矢量/代码化渲染，并自动下采样导出 256 / 64 / 32 / 22 多尺度资产。

---

## 1. 架构定位与代际演进

```text
语义命中官方 → B28 官方 BMP（现状不变）
语义未命中   → Generated Base（本规范 v3）→ 确定性 3D 渲染管线 → 入库资产
              路径 A（推荐主路径）：Ultra-3D 参数化真实机械写实渲染
                     高精 512 Master 建模 + Phong 材质光影 + 接触柔和阴影 + 纯透明底
              路径 B（辅助）：高分辨率 AI 概念原型 → 结构化参数化重绘落地
              ↓
         自动导出：512/256 HD PNG, 64 高分屏 PNG, 32 Large PNG, 22 Normal BMP/PNG
```

### v2 到 v3 的核心代际跨越（用户实机验收实证）

| 规范维度 | v2 旧像素画路线（已废弃） | v3 Ultra-3D 工业写实路线（当前标准） | 演进原因与实证 |
|---|---|---|---|
| **背景机制** | 强制纯平灰底 `(192,192,192)` | **100% 纯透明（Alpha = 0）**，带自适应柔和环境软投影 | 灰底在现代深色 IDE 或透明工具栏下产生死板色块；纯透明底具有无限界面兼容性。 |
| **分辨率矩阵** | 仅 22×22 点阵直接手绘 | **512×512 Master 原稿**，向下自适应平滑导出 256/64/32/22 | 现代高分屏（2K/4K）下 22×22 硬点阵产生严重狗牙与分辨率失真；高清 Master 兼顾现代与传统。 |
| **留白与构图** | 极端空旷（留白 80%）或撑爆破边（留白 5%） | **弹性指导留白（居中块状推荐占 68%~72%）**，四周保留自然呼吸间隙 | 兼顾独立 3D 物体美学与饱满工业分量感，无切边截断。不作为所有形态长宽比的绝对硬卡死。 |
| **机械造型** | 抽象齿轮/平面色块/直角细折线 | **真实工程零件实体**（阶梯法兰轴套、加强筋、沉头安装螺栓、配合倒角） | 工业工程师对“装配”的直观理解是孔轴配合与零件就位，而非抽象几何符号。 |
| **光影与立体感**| 禁止 3D、禁止渐变、禁止抗锯齿 | **真实 Phong 曲率光照 + 镜面高光母线 + 菲涅尔边缘光 + 接触 AO 阴影** | 曲面金属高光与前后落差营造极强 3D 纵深感。 |

## 2. 风格与参数规范

| 项 | 规范值 |
|---|---|
| 画布 | Master 512×512（主设计源），导出 256/64/32/22 适配各级 DPI |
| 背景 | **纯透明（Alpha = 0）**，附带两级高斯模糊环境遮挡软投影（Contact AO Shadow） |
| 调色板 | 传承 CATIA 经典工程调色板：工程金黄 `(255,210,30)`、铣削铝合金银灰 `(240,245,252)` 到 `(165,175,192)`、工业深蓝墨水轮廓 `(24,16,82)`、装配导向红 `(235,30,30)` |
| 光影体系 | 主光源偏左上方（Phong 模型），带纯白镜面高光反射线（Specular Strip）与暗部菲涅尔环境反光（Rim Bounce） |
| 构图与留白 | 主体实体占比约 68%~72%（居中机械块状推荐指导区间；细长构件视几何长宽比自然呼吸，以四周留有透气空间、不硬碰撞画布边缘为准） |
| 机械细节 | 具有工程可信度：必须体现倒角（Chamfer）、沉孔（Counterbore）、加强筋（Gusset）或装配基准面等工业特征 |

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

## 5. 验收门禁（A–E，路线隔离与分级防错）

### A. 语义门禁
一眼表达目标语义（如 PartToAsm = 精密零件装配就位），杜绝泛化几何块或无关符号。

### B. 构图门禁（按技术路径严格隔离）
- **路径 A（Ultra-3D 现代机械写实，推荐主路径）**：
  - 必须为真实的工业工程机械构件实体（如法兰盘、台阶轴、导向倒角、沉孔配合、加强筋等）；
  - 允许且推荐精准曲面 Phong 光影、反射高光线、菲涅尔轮廓反光与柔和接触阴影；
  - 杜绝无关场景堆砌、杜绝文字标签、主体居中且四周留有透气间隙。
- **路径 B（AI 概念原型 / 像素风格重绘，辅助路径）**：
  - 采用极简几何像素符号，纯平无渐变填色；
  - “禁止 3D、禁止渐变”仅作为此路径下的受控实验约束，**严禁反向套用为路径 A 的门禁**。

### C. 视觉质量门禁
- 512 高清母版细节扎实；下采样至 64/32/22 后轮廓与特征依然清晰可辨；
- 符合 CATIA 工程调色板调性；缩至 22×22 依然保持纯正工业机械质感。

### D. 工程防错门禁（Engineering Linting，区分必检与可选）

| 检查维度 | 性质 | 检查标准 | 处理动作 |
|---|---|---|---|
| **四角背景** | **Hard Gate（必检）** | 22×22 画布四个角点像素必须完全为背景色（无溢出脏边） | 不通过则打回 |
| **画布硬截断** | **Hard Gate（必检）** | 主体任何一边在画布边缘截断比例不得 > 60%（严禁机械零件被切掉边缘） | 不通过则打回 |
| **BMP 格式与透明索引** | **Hard Gate（必检）** | 必须为 22×22、8-bit indexed BMP；调色板索引 0 严格为 `CATIA_BG (192,192,192)`；四角及背景像素原始调色板索引值严格为 0 | 不通过则打回 |
| **BMP 色数上限** | **Hard Gate（必检）** | 22×22 运行时 BMP 色数不得超过 16 色 | 不通过则打回 |
| **Alpha 纯净度（PNG）** | **Hard Gate（必检）** | 覆盖全尺度 PNG：四角 Alpha 严格为 0，且 A=0 像素零 RGB 污染（杜绝重采样脏边） | 不通过则打回 |
| **前景比例** | **Soft Lint（指导）** | 全局有效区间 [15%, 70%]；居中块状零件推荐 [68%, 72%] | 报告占比，提供优化建议 |
| **孤立噪点** | **Soft Lint（报告）** | 统计孤立漂移像素点（连通度为 0 的像素） | 报告噪点数供人工复核，不作为当前硬失败条件 |
| **半透明比率（PNG）** | **Soft Lint（报告）** | 统计全尺度 PNG 下采样抗锯齿产生的半透明像素比率 | 报告比率供视觉复核，不作为硬门禁 |
| **最小线宽** | **Soft Lint（报告）** | 检查 22×22 关键轮廓是否维持 >= 1px | 报告细线分布供设计参考，不一刀切打死 |

> **统一 Lint 实施规范**：上述工程防错门禁已在 `tools/icon_gen_pipeline.py` 中抽象为模块级复用函数 `lint_bmp_asset()`、`lint_alpha_png()` 与 `clean_zero_alpha_rgb()`。路径 A（Ultra-3D 参数化脚本）与路径 B（AI 图片后处理）必须统一在导出阶段调用该 Lint，以真实测量数据写入 `provenance.json`，严禁两套标准或未经检测硬编码通过。
> **Alpha 纯净度界定**：`alpha_clean: true` 严格指代“四角全透明（A=0）且全透明像素零非零 RGB 脏溢出”；半透明像素（0 < A < 255）为真实曲面光影下采样抗锯齿产物，属于视觉过渡度量，最终融合效果由 CATIA 实机验收裁决。

### E. CATIA 实机验收（最终裁决）
- 机器指标负责兜底排除坏图，实机效果由 B28 真实工具栏加载裁决；
- 流程：机器 Hard/Soft Lint → 人工多尺度审查 → CATIA B28 工具栏实机验证 → APPROVED。

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
