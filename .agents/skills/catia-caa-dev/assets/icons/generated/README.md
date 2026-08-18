# Generated Base Icons

文生图入库资产目录。仅存放通过 `ICON_GENERATION_SPEC` 验收的 Generated Base。

## 命名

- stem 前缀 `I_CADE*`（与官方 `I_*` 区分），如 `I_CADEPartToAsm`
- 每个资产两件套：`<stem>.bmp`（8-bit 调色板，背景 = 索引 0）+ `<stem>.json`（provenance）

## provenance JSON 格式

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

## 规则

- 官方有等价图的语义**禁止**入库生成资产（Official Base 优先）
- Badge 一律程序化叠加，文生图不画角标
- 未过门禁（≤16 色 / fg%∈[15,70] / 四角纯）的资产不得入库
