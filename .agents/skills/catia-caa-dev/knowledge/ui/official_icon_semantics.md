---
id: ui.official_icon_semantics
title: B28 官方图标语义学（颜色/构图/视觉家族）
category: knowledge
domain: ui
keywords: [icon, B28, official icon, semantics, vocabulary, morpheme, palette, fg, PartDesign, Sketcher, gear, swatch, badge, I_Pad, I_Part, I_Product]
apis: []
requires: []
patterns: []
examples: []
release: [R28]
tags: [ui, icon, semantics, official-base, generated-base]
---

# B28 官方图标语义学（Official Icon Semantics）

对 B28 `resources/graphic/icons/normal/` 的实测语义分析。**不是**从文件名推断，而是逐像素测量 + CATRsc 引用频次统计。

> 数据来源：3077 个 `msgcatalog/*.CATRsc` 扫描（6789 个唯一图标 stem），40 个高频工具图标逐像素分析（2026-08-18）。
> 对应工具：`tools/icon_design_lib.py`（已代码化语素）/ `tools/icon_gen_pipeline.py`（门禁）。

---

## 1. "高频"的两种度量，语义完全不同

| 度量 | Top 结果 | 含义 |
|---|---|---|
| CATRsc 引用数 | `I_Update`(40) / `I_Open`(39) / `I_Line`(38) / `I_Plane`(37) / `I_MeasureBetween`(29) | **被多少命令头共享** → 基础设施图标 |
| 用户点击频率 | Pad / Pocket / Hole / Sketcher（引用仅 1~5） | 每个特征图标一一对应单一命令 |

**结论**：做 CADE 图标时参考哪套词汇，取决于命令语义域，不是引用数排名。基础设施图标（Update/Open/Save/Select）是 OS 通用词汇；特征图标才是 CATIA 私有编码。

---

## 2. 颜色即语义域（全部实测采样，非猜测）

| 颜色 | RGB | 语义 | 采样源 |
|---|---|---|---|
| 实体黄 | `(255,255,150)` | PartDesign 实体正面（加/减材料的"材料"） | I_Pad / I_Pocket / I_Hole / I_Slot / I_Shell |
| 齿轮黄 | `(255,238,135)` | 装配体/参考元素 | I_Part / I_Product / I_Plane |
| 青色 | `(75,230,255)` | **几何线框 / 控制点 / 辅助元素** | I_Point / I_Line / I_Circle / I_Spline |
| 墨蓝 | `(24,16,82)` | 轮廓 + 伪3D 挤出（结构色，无独立语义） | 30/40 高频图标共享 |
| **红** | `(155,0,0)` | **切除区域 / 特征作用的边或面** | I_Groove 红槽 / I_Chamfer / I_Fillet 红虚线圈 |
| **蓝** | `(10,0,255)` | **参考 / 副本 / 阵列实例** | I_Offset 虚线副本 / I_CircularPattern 阵列件 / I_Coincidence |
| 绿 | `(47,255,144)` | 系统撤销族 | I_Undo / I_Redo 弯箭头 |
| 黑 | `(0,0,0)` | 系统命令族轮廓 | I_Save / I_Copy / I_Paste / I_Cut |

**墨蓝是结构色不是语义色**——它画轮廓和阴影，不表达"这是什么"。语义由黄/青/红/蓝/绿承担。

---

## 3. 构图即操作语义（官方自己复用的手法）

| 构图手法 | 语义 | 证据 |
|---|---|---|
| **凸出 vs 凹入** | 加材料 vs 减材料 | I_Pad（黄块凸出墨蓝框）与 I_Pocket（黄面内墨蓝凹槽）**同一构图、方向相反**——Pad/Pocket 是一对反义词图标 |
| 红色虚线圈选 | 特征作用的边/面 | I_Chamfer 与 I_Fillet 几乎同构图，只用圈出边的几何（斜/圆）区分 |
| **虚线副本** | 偏移 / 参考 / 阵列 | I_Offset 蓝色虚线方块、I_CircularPattern 蓝菱形绕灰环 |
| 双主体对称 | 镜像 / 显隐切换 | I_Mirror 两黄块分居中缝、I_SwapHideShow 双齿轮 |
| 循环双箭头 | 更新 / 刷新 | I_Update（全库 CATRsc 引用第 1，40 次） |
| 实物工具隐喻 | 测量 | I_MeasureBetween=箭头+尺、I_MeasureItem=卡尺、I_MeasureInertia=砝码 |
| OS 通用词汇 | 系统命令 | I_Open=文件夹、I_Save=软盘、I_Copy=双文档、I_Select=鼠标指针、I_Erase=橡皮、I_Identify=箭头+问号 |

---

## 4. 三个视觉家族（背景色 = 资源类型语义）

| 家族 | 背景 | 轮廓 | 词汇 | 色数 | 代表 |
|---|---|---|---|---|---|
| **建模命令族** | `(192,192,192)` | 墨蓝 | CATIA 私有编码（§2/§3） | 3~8 | Pad / Line / Measure / Plane |
| **系统命令族** | `(191,191,191)` | 黑 | Windows 95 通用 | 7~15 | Undo / Save / Copy / Paste |
| **文档族** | `(180,180,180)` | 墨蓝+灰 | 齿轮/立方体 + 白文档页 | 8~9 | I_Part / I_Product |

**背景色本身携带"这是命令还是文档"的类型语义**。CADE 工具是命令，一律用 `(192,192,192)`；`icon_design_lib.BG` 已固化。

---

## 5. fg 密度与语义类型强相关

| 类型 | fg 范围 | 实测 | 含义 |
|---|---|---|---|
| 实体族 | 55~75% | I_Pad 73% / I_Pocket 74% / I_Hole 74% | 高视觉密度 = 实体感 |
| 复合族 | 35~50% | I_Mirror 60% / I_Shell 56% / I_MeasureItem 47% | 双元素/工具隐喻 |
| 线框族 | 5~25% | I_Point 5% / I_Line 11% / I_Circle 19% / I_CircularPattern 21% | 几何元素天然留白 |

**对 CADE 的校验**：PartToAsm 铺满 fg=47.9% 落在复合族区间 ✓；管线门禁 fg∈[15%,70%] 覆盖全部三个族 ✓。

---

## 6. 关键修正：单主体 → 单一语义单元

官方自己违反"单主体"：I_Mirror / I_SwapHideShow / I_Copy 都是双主体。

**准确规则**：单**一语义单元**。对称/对比/复制语义天然允许双主体；禁止的是无关联的多对象场景化堆叠。

---

## 7. 已代码化语素（`tools/icon_design_lib.py`）

### 7.1 经过 gate E 实机验证（生产可用）

| 语素 | 官方编码 | 采样源 |
|---|---|---|
| `gear()` | 齿轮数 = 装配层级（1=part，对=product） | I_Part / I_Product |
| `cube3d()` | 黄面+墨蓝伪3D挤出+白高光 = PartDesign 实体 | I_Pad / I_Hole |
| `frame()` | 嵌套轮廓框 = 装配容器/边界 | 通用 |
| `swatches()` | 饱和色板网格 = 颜色属性 | I_AutomaticColorProperty |
| `letter_a()` | 白卡+字母 = 命名 | I_RenameFamily |
| 调色板常量 | `BG/INK/FACE/GEAR_FACE/GEAR_HUB/CYAN/CYAN_EDGE/WHITE` | 全部实测 |

### 7.2 储备语素（已定义，**未经 gate E**，真实需求出现时再接线）

| 语素 | 官方编码 | 采样源 |
|---|---|---|
| `red_marker()` | 红色虚线框 = 特征作用的边/面 | I_Chamfer / I_Fillet |
| `dashed_copy()` | 蓝色虚线方块 = 偏移/参考/阵列副本 | I_Offset / I_CircularPattern |
| `boss()` | 黄块凸出 = 加材料 | I_Pad |
| `notch()` | 凹槽凹入（深灰 `(75,75,75)` 内腔）= 减材料 | I_Pocket / I_Hole |
| `ctrl_point()` | 青色控制点 = 几何辅助 | I_Point / I_Line / I_Circle |
| `cycle_arrows()` | 双循环弧箭头 = 更新/刷新 | I_Update |
| `RED_MARK` / `REF_BLUE` / `DEPTH_GRAY` | 语义色常量 | §2 |

---

## 8. AI 生成规则

- [ ] 新 CADE 命令图标：**先查本文件 §2/§3** 官方是否已有同语义编码，有则提取复用，不发明视觉语言
- [ ] 背景一律 `(192,192,192)`（建模命令族），禁止用文档族 `(180,180,180)` 或系统族 `(191,191,191)`
- [ ] 轮廓用墨蓝 `(24,16,82)`，语义色按 §2 选：实体黄=材料、青=几何辅助、红=作用位置、蓝=参考副本、绿=系统操作
- [ ] 加/减材料语义用凸出/凹入对偶表达（`boss()`/`notch()`），不另造隐喻
- [ ] 偏移/参考/复制语义用蓝色虚线（`dashed_copy()`），不用实心副本
- [ ] 实体类图标 fg 目标 40~50%（铺满）；线框类可低至 15%；禁超 70%
- [ ] 语义单元必须单一：允许对称/对比双主体（Mirror 式），禁止无关联场景堆叠
- [ ] 储备语素（§7.2）首次用于生产命令时，必须过完整 A–E 门禁并在 provenance JSON 记录

---

**最后更新**: 2026-08-18（基于 3077 CATRsc + 40 图标逐像素实测）
