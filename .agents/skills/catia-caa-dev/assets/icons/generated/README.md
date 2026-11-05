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

- **CATIA 运行时透明契约**：8-bit 索引色 BMP（≤256 色），调色板 `Palette[0]` 严格锁定为 `(192, 192, 192)` 背景灰。
- **四角纯净度**：4 个角点像素索引必须恒为 0，杜绝显示时出现暗框与毛刺。
- **前景填充率**：`fg_ratio` 严格控制在 [15%, 75%] 之间。
- **双规声明**：对应 `.CATRsc` 必须成对提供 `Icon.Normal` 与 `Icon.Large`。
