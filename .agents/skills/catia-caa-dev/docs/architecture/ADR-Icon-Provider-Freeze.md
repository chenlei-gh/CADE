# ADR: Icon Provider Architecture (Official-Only)

**Status**: Accepted (Official-Only, primitives deleted)
**Date**: 2026-08-17
**Baseline**: `CACHE_VER=v13`, supersedes v12 freeze + Official Base overlay
**Audience**: CADE developers and AI agents
**Scope**: 71 Primitive 全部删除；图标系统改为 Official-Only。
官方 BMP 运行时引用，不入仓库。

> CADE 不再拥有自有图标库。每个图标 = CATIA 官方 BMP（运行时只读）
> + 现有 Badge 角标（如有动词）。未命中时用官方兜底图
> `I_P3DefaultIcon`。CATIA 未安装时退化为灰色占位符（仅 CI/测试）。

---

## 1. Context

S1–S4 的审计链证明了三个关键事实：

1. **Primitive 不是必需的** — 官方图标库已覆盖绝大多数 CATIA 标准语义
2. **官方图标可以作为 Base** — CNEXT 能直接读取 4/8-bit 22×22 BMP
3. **模糊匹配 9832 张图不可行** — 语义陷阱太多，必须显式映射

但 v12 架构（Official Base + 71 Primitive fallback）存在一个根本矛盾：

> **CADE 自有命令（AutoColor/AutoRename/BOM/PartToAsm）没有官方一一对应，
> 它们被迫使用 Primitive，导致用户看到的是两套视觉语言。**

用户最终决定：**删除全部 Primitive，完全使用官方图标。**

关键转折：通过 B28 msgcatalog 交叉验证（CATRsc → CATNls），找到了
三个生产命令的官方语义等价图标，消除了 DENY 的必要性：

| CADE 语义 | 官方文件 | 验证来源 | 官方标题 |
|---|---|---|---|
| rename | `I_RenameFamily` | `CATFileMngtCmdHeader.RenameHdr` | "Rename" |
| bom | `I_DNBBOMtoXML` | `DNBProcCmdHeader` | "Export MBOM to XML" |
| color | `I_AutomaticColorProperty` | `CATGraphicPropertiesToolbar` | "Automatic color" |

---

## 2. Decision

```text
命令名
  → analyze_command()          # 语义分析保留（6级链）
  → official_candidate_stem()  # 显式映射：alias / exact Pascal / DENY
  → resolve_official_icon()
        │
        ├─ 命中（stem 存在 + 文件存在）
        │      ↓
        │  官方 BMP（只读）+ Badge（如有动词）
        │
        ├─ 未命中（stem 为 None 或文件缺失）
        │      ↓
        │  I_P3DefaultIcon（官方兜底图）+ Badge
        │
        └─ CATIA 未安装
               ↓
          灰色占位符 + Badge（仅 CI/测试环境）
```

**不再有 Primitive fallback。** 官方兜底图确保 `develop()` 永不断。

---

## 3. Official Resolver rules (v4.0)

禁止 `"I_" + object` 盲拼，禁止 `glob('I_Hole*')` 取第一张。

1. **DENY**（S5 已验证语义不等价，即使文件存在也不用）
   `tool` / `mode` / `assemble` / `reference`
   → 全部落到 `I_P3DefaultIcon`
   （原 11 词 DENY 经 S5/S6 重审：`properties/loft/axis/boss` 翻为 ALIAS，
   `feature/element` 因官方图为 Selection 上下文而自然落兜底，`numeric` 为 NONE）

2. **命名陷阱别名 + 已验证语义等价**（`_OFFICIAL_ALIAS`）
   基础：`sketch→I_Sketcher` / `remove→I_RemoveBody`
   msgcatalog 验证：`rename→I_RenameFamily` / `bom→I_DNBBOMtoXML` /
   `color→I_AutomaticColorProperty` / `properties→I_Properties`
   `pattern + circular → I_CircularPattern`
   `pattern + rectangular → I_RectangularPattern`
   泛化 `pattern`（无修饰）→ DENY → 兜底图

   **Batch-2（S6 索引，22 条，CATNls 标题验证）**：
   通用：`material→I_ApplyMaterial` / `pan→I_Translate` / `loft→I_ICMLoftLT` /
   `search→I_Find` / `revolve→I_RevolutionSurface` / `boolean→I_CldBoolean` /
   `arc→I_ArcCircle` / `curvature→I_SurfCurvAna` / `drill→I_DrillHoles` /
   `transform→I_SpdTransform` / `statistic→I_CATFmtFollow` /
   `configure→I_VPMNavConfigure` / `table→I_DrwTable`
   域特定（按最大包含纳入，标题对但语境偏窄）：`spring→I_MldSpring` /
   `boss→I_SpdBoss` / `gear→I_GearJoint` / `axis→I_AxisLine` /
   `annotation→I_Sch_DatumSymbol` / `distance→I_BandAnalysis` /
   `setting→I_DNBVisuSettings` / `mill→I_MfgEndMillTool` / `symmetry→I_ShapeSymmetry`

3. **弱对象**（`part` / `product` / `body` / …）
   仅当没有非噪声 modifier 时才试 `I_Part.bmp` 等。
   `PartToAsm` 的 `asm` 会挡住 → 兜底图。

4. **否则**试精确 `I_{Pascal(obj)}.bmp`。
   精确名不存在 → 兜底图（不再 Primitive）。

5. Overlay：有 badge 就叠，**包括 CREATE 的 `+`**。

6. **生产部署强制带角标**（2026-08-18 用户裁决）：CATRsc `Icon.Normal`
   必须引用 `I_<stem>Badge`（官方底图 + Badge 合成版），禁止引用纯官方
   stem。语义链产出 badge=None 的命令（如 AutoColor/BOM/PartToAsm），
   部署时按命令动作显式指定 badge glyph（`check`/`pencil`/`move` 等 23
   字形之一）。纯官方底图仍部署在工作区作未引用参照，不作生产图标。
   **角标规格**（同日用户裁决 v2）：右下角、面积 ≈ 图标 1/3（13×13 @ 22²，
   `BADGE_PLATE_RATIO = 13/22`）、**无底板无背景色**（透明层纯字形，官方
   底图像素透过来）；全 23 字形配色入 `BADGE_GLYPH_COLORS`（饱和填充 +
   官方墨线 (8,8,103)，语义色：创建绿 / 删除红 / 铅笔橙 / 箭头亮蓝……），
   调色板保存时从该表动态集优先色防量化丢色。四个生产命令角标互异：
   `check`（AutoColor）/ `pencil`（AutoRename）/ `export`（BOM，扣官方
   标题 "Export MBOM to XML"）/ `move`（PartToAsm）。

7. **Generated Base**（2026-08-18 PartToAsm 试点闭环）：官方确无等价的
   CADE 自有语义，可按 `ICON_GENERATION_SPEC` 生成图标——LLM 像素设计
   （主路径，`icon_design_lib` 官方语素）或外部文生图（可选），一律过
   后处理管线门禁（22×22 / ≤16 色 / 四角纯 / fg∈[15,70]）+ 人工验收 +
   CATIA 实机。资产入库 `assets/icons/generated/`：`I_CADE*` 前缀 BMP +
   provenance JSON + 设计源 .py（资产可从代码确定性重建）。这是
   “无自有图标库”原则的唯一例外；官方 BMP 原件仍永不入库。规则 6 的
   Badge 强制**不适用**于主体已含语义的 Generated Base（spec §6 豁免，
   如 PartToAsm 的齿轮对本身即装配语义）。

检索路径来自 `config/caa_env_config.txt` 的 `CATIA_INSTALL` +
`win_b64|intel_a/resources/graphic/icons/normal`。未安装则全部占位符。

---

## 4. What was deleted

| 删除项 | 原行数 | 说明 |
|---|---|---|
| `DOMAIN_MAP` | ~40 | 改为 `OBJECT_VOCAB` frozenset（纯语义token集） |
| `COLOR_MAP` | ~50 | 官方BMP自带颜色，无需CADE配色 |
| `ACCENT_MAP` | ~6 | 同上 |
| `_get_color_for_icon` | ~8 | 同上 |
| `_render_icon` | ~40 | Primitive渲染器，删除 |
| 71个基图字形 | ~170 | 只保留23个badge字形 |
| `_apply_checker` | ~18 | 官方BMP自带纹理，无需halftone |
| `_rasterize_catia` | ~10 | 官方BMP直接保存，无需重采样 |
| Helper函数 | ~60 | `_cube/_fillet_block/_iso_block/_extrude_profile*/_bez` 等 |
| `PATTERN_NAMES` | ~5 | 改为 `BADGE_GLYPHS` |

**保留**：
- 23个badge字形（`_draw_icon_4x_rgba` 中）
- `_gear` / `_star` helper（badge用）
- `_render_badge_plate` / `_compose_official` / `_rasterize_hd`
- `analyze_command()` 6级语义链（输出改为官方stem）
- `copy_icons_to_runtime` / `get_icon` / `resolve_icon*` API

**新增**：
- `OBJECT_VOCAB` frozenset（替代 DOMAIN_MAP keys + "color"）
- `DEFAULT_OFFICIAL_STEM = "I_P3DefaultIcon"`
- `_render_placeholder`（CATIA未安装时的灰色占位符）

---

## 5. Evidence Summary

### S1–S3（沿用，不变）

见 git 历史中 v12 ADR。核心结论：Primitive 规模够用、Grammar 暂无需求、
ACTIONABLE_FALLBACK = 0。

### S4 — Official Base mechanism（沿用）

- S4-A：Resolver 必须语义驱动（Sketch → I_Sketcher）
- S4-B：CNEXT 能直接读取官方 4/8-bit 22×22 BMP

### S5 — Official-Only 可行性验证（2026-08-17）

- **msgcatalog 交叉验证法**：`*.CATRsc`（图标名→命令头key）→
  `*.CATNls`（key→标题），读 `encoding='mbcs'`
- 找到 3 个生产命令的官方语义等价图标（见 §1 表格）
- `I_Rename.bmp` 是孤儿文件（无 CATRsc 引用）→ 不可用
- `I_DECProductToPart` = "Product to Part"（方向反）→ PartToAsm 无匹配
- `I_Assemble` = 几何接合（GSD/hybrid），不是装配创建 → 维持 DENY
- `I_P3DefaultIcon`：全库无 CATRsc 引用（无语义污染），名为 "Default Icon"
  → 选为兜底图。26×26 P，`_compose_official` 已有 NEAREST resize

### S6 — Official 语义索引与 Batch-2（2026-08-17）

动机：原 11 词 DENY 里混入了可翻案词条，且 `OBJECT_VOCAB` 122 词的官方覆盖
从未全量核过。

- **全量语义索引**（`tmp/icon_official_index.py`，只读离线）：扫 3077 个
  CATRsc，得 **3790 个被命令引用的 stem**（不是 9832 原始文件——其余是
  状态变体/域特定/孤儿），其中 **3651 个有 CATNls 标题（96.3%）**。索引落
  `tmp/icon_official_index.json` 复用。
- **方法论修正：按 CATNls 标题做词边界匹配，不是按文件名子串**。文件名
  搜索撞 `pan→panel`（复材面板）；标题搜索一击命中 `pan→I_Translate`（标题
  即 "Pan"）。`loft→I_ICMLoftLT`（标题 "Loft"）、`symmetry→I_ShapeSymmetry`
  （标题 "Symmetry..."，非复材 `I_Symmetry` "Symmetric Plies"）同理由标题
  才找到。
- **refs 是流行度不是正确性**：`arc` 按 refs 第一是 `I_Measure3Points`（r=4，
  "Arc through Three Points"，构造法），通用语义是 `I_ArcCircle`（r=1，"Arc"）；
  `table` 按 refs 第一是复材 `I_CompositesPlyMgt`，通用选 `I_DrwTable`。
- **DENY 重审**：`properties/loft/axis/boss` 翻出 DENY 进 ALIAS；
  `tool/mode/assemble/reference` 维持 DENY（S5 已证不等价）。
- **Batch-2 = 22 条新 ALIAS**（13 通用 + 9 域特定按最大包含纳入，见 §3）。
- **C 组拒入**（防陷阱红线）：动词 `analyze/check/verify`（走 badge 非 object 图）；
  语义错配 `cog→CoG`（质心非齿轮）、`step→SnapSteps`（捕捉步距非 STEP 格式）。

**覆盖率口径**（不同分母，禁止合成一个数）：

| 口径 | 分母 | 已验证可用 |
|---|---|---|
| 全量 OBJECT_VOCAB | 122 | 65（53%）= 27 ALIAS + 38 HIGH |
| 真实命令（S2 案例） | 70 | 加权更高（高频集中在有图标的标准特征） |
| 官方全库 | 9832 | 不是分母——只是资源池 |

### 测试

- `test_icons.py`：96/96 通过（含 Batch-2 的 22 条 stem 断言 + 3 条解析抽查）
- `test_master.py --quick`：41/41 suites

---

## 6. Forbidden

- 扫描或复制 B28 `normal/` 进仓库（唯一例外：经 spec 门禁 + 人工 +
  实机验收的 `I_CADE*` Generated Base 资产可入库，必须含 provenance）
- 建立 Official Icon Library / 把官方原件写入 ChangeSet
- 模糊匹配 / 相似度搜索官方图标
- `glob('I_Hole*')` 取第一张
- Modifier / State / Context / Icon Grammar
- 恢复 Primitive 渲染器
- 为 AutoRename 用 `I_Rename`（孤儿文件）、为 Color 用 `I_ColorChooser`
- 把 `I_Assemble` 给装配类命令用（它是几何接合）
- 把 `I_DECProductToPart` 给 PartToAsm 用（方向反）
- 改 `analyze_command()` / `OBJECT_VOCAB` 只为提高官方命中率

官方资源位置（只读，不入库）：

`C:/Program Files/Dassault Systemes/B28/win_b64/resources/graphic/icons/normal/`

---

## 7. Reopen Conditions

1. **真实生产命令命中 Official，但选错了文件**
   → 只加一条别名或 DENY，回归 icon tests。
2. **满幅官方图标 + Badge 在 Toolbar 被证明不可用**
   → 只对该 object 跳过 Overlay 或跳过 Official，不做空位检测引擎。
3. **兜底图 `I_P3DefaultIcon` 在 22×22 缩小后不可辨认**
   → 换用其他官方兜底图（需同样无 CATRsc 引用），或调整 resize 算法。
4. **DENY 列表中某词条被重新核实有官方等价**
   → 按 msgcatalog 交叉验证法找到证据后，从 DENY 移到 ALIAS。
5. **Generated Base 资产实机被否**
   → 回退到对应 Badge 合成版，按 spec 重生；不绕过门禁手工改 BMP。

---

## 8. Consequences

- `CACHE_VER` = `v13`；缓存键含官方 stem，旧缓存自动失效。
- `ICON_HASH` 输入更新：去掉 DOMAIN_MAP/COLOR_MAP/ACCENT_MAP，
  加 OBJECT_VOCAB / DEFAULT_OFFICIAL_STEM / `_render_placeholder`。
- `update_golden_icons.py` 已废弃（Primitive 渲染器已删），
  改为提示用 CLI `--render` 生成预览。
- `CAAPartToAsm` 的 `I_parttoasm.bmp` 已重新生成为官方兜底图
  `I_P3DefaultIcon` 的 8bpp NEAREST 缩放版（Primitive 遗产文件已替换）。
- 生产 CATRsc `Icon.Normal` 指向（§3 规则 6/7）：
  - `CAAAutoColor`：`"I_CADEAutoColor"`（Generated Base，官方色板词汇
    2×3 饱和色板网格 + 右下 r4 自动化齿轮压边，无 Badge；规则裁决无人工
    选择；`I_AutomaticColorPropertyBadge.bmp` 保留作回退）
  - `CAAAutoRename`：`"I_CADEAutoRename"`（Generated Base，官方命名片
    词汇 白卡 + 手绘像素 `A`（`letter_a()`，Pillow≥10 默认字体抗锯齿违反
    硬边条款）+ r3 齿轮，无 Badge；规则裁决；`I_RenameFamilyBadge.bmp`
    保留作回退）
  - `CAABOMTool`：`"I_CADEBOMTool"`（Generated Base，官方 BOM 词汇
    装配树 父+双子黄节点连线 + 白表格卡 3 蓝行 (0,140,255)，无 Badge；
    规则裁决；`I_DNBBOMtoXMLBadge.bmp` 保留作回退）
  - `CAAPartToAsm`：`"I_CADEPartToAsm"`（Generated Base，官方齿轮词汇
    左单黄齿轮=part / 右青咬黄齿轮对=asm，无 Badge；gate E 用户验收通过；
    `I_parttoasmBadge.bmp` 保留作回退）
- **无 Badge 豁免已扩展至全部 4 个生产命令**（2026-08-18 用户裁决）：
  主体自带语义的 Generated Base 不叠加 Badge，§3 规则 6 的强制角标条款
  仅适用于「官方底图原样引用」场景；旧 `*Badge.bmp` 全部保留作回退。
- 下次改 Icon Provider 必须先回答：「它解决了哪个真实命令？」
