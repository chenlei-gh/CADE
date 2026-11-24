# Generated Base Icons (Universal Icon Studio)

CADE 通用高清图标资产目录。所有资产统一由 `skills/icon_studio.py`（Universal Icon Studio）驱动生成与验收。

## 命名与尺寸矩阵

- Stem 前缀：`I_CADE*`（与官方原生 `I_*` 区分），例如 `I_CADEDateStamp`、`I_CADEPartToAsm`。
- 每个资产全套标配（Ultra-HD Pipeline）：
  - `<stem>_512.png`：512×512 Master RGBA 原稿（超平滑抗锯齿与物理光影）
  - `<stem>_256.png`：256×256 文档高清资产
  - `<stem>_64.png`：64×64 高分屏 UI 资产
  - `<stem>_32.png` & `<stem>_32.bmp`：32×32 CATIA Large Mode 位图（8-bit 索引色，Palette[0] 锁定背景灰）
  - `<stem>.png` & `<stem>.bmp`：22×22 CATIA Normal Mode 位图（8-bit 索引色，Palette[0] 锁定背景灰）
  - `<stem>.json`：质量门禁与 Provenance 元数据

## 统一生成与部署命令

```bash
# 生成任意工具全套高清图标资产
python -m icon_studio <ToolName> [--stem I_CADEXxx] [--metaphor stamp_clock|part_to_asm|bom_table|color_swatch|name_card|cube_solid]

# 一键部署至 CAA Framework（自动写入 icons/normal 并配置 .CATRsc Normal+Large 双规声明）
python -c "from icon_studio import UniversalIconStudio; UniversalIconStudio.deploy_tool_icon('<ToolName>', '<FwPath>')"
```

## 工业质量门禁规则

- **双尺度专用渲染**：22×22 与 32×32 必须在各自的整数像素网格上**独立布局与绘制**，禁止由 512 母版缩放产生（4px 特征缩到 22px 仅剩 0.17px，必然发虚）。32px 不复用 22 单位坐标，而是使用原生 32 单位布局增加结构细节。
- **官方轮廓基准**：B28 `I_Pad` / `I_Hole` / `I_Pocket` 实测为 **1 物理像素**墨蓝外轮廓与内部分隔线；禁止重新改成 2px 粗描边。细腻感来自面内结构、纯色高光与暗面，不来自模糊、抖动或过渡色。
- **CATIA 运行时透明契约**：8-bit 索引色 BMP（≤256 色）。CADE 自己写出的图标把 `Palette[0]` 锁定为声明的背景掩码色（合法掩码：`(192,192,192)` 灰 / `(24,16,82)` 墨蓝 / `(180,180,180)`）。官方 B28 图标不遵守这条：背景色可以在任意调色板位置，审计它们用 `lint_icon_asset(..., profile="official")`，按颜色而不是索引 0 认背景。生成与部署仍走 `profile="cade"`，不放宽。
- **四角纯净度**：4 个角点像素索引必须恒为 0，杜绝显示时出现暗框与毛刺。
- **前景色数预算（G2）**：排除背景掩码后的有效前景色 —— 22×22 ≤ **16** 色、32×32 ≤ **24** 色（512 Master 不限）。超预算 **FAIL**。
- **轮廓锐边（G3）**：`sharp_ratio ≥ 0.85`（仅统计相邻异色像素对，通道差 ≥56 为硬边），孤立噪点 `isolated_ratio ≤ 0.02`。
- **前景填充率**：`fg_ratio` 严格控制在 [15%, 75%] 之间（上限 75% 而非 70%，
  否则会拒绝官方实体族基准 `I_Pad 73%` / `I_Pocket 74%` / `I_Hole 74%`）。
- **PNG Alpha 纯净度（G6）**：512/256/64 导出件中 `A=0` 的像素 RGB 必须为 0；22/32 是平面 RGB 画布不含 Alpha，不适用。由 `lint_png_asset()` 校验。
- **双规声明**：对应 `.CATRsc` 必须成对提供 `Icon.Normal` 与 `Icon.Large`。部署只改属于本工具的行（按 header 前缀匹配），不会波及其他命令。
- **无逃生阀**：任何硬门禁失败即禁止部署、禁止注入 `.CATRsc`；只有 PASS / FAIL，没有 WARN 降级。

> 16 色是**上限不是质量保证**——8 色但轮廓断裂的图标照样 FAIL。G2 与 G3 必须同时通过。
