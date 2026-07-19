---
id: pb.auto_color
title: Auto Color Parts / 零件自动着色
category: playbook
domain: product
keywords: [color, auto, random, visualization, graphic properties, material, shade]
capabilities: [cap.visualization, cap.geometry_query, cap.assembly_tree]
apis: [CATIVisProperties, CATVisPropertiesValues, CATIProduct]
frameworks: [Visualization, CATAssemblyInterfaces]
difficulty: beginner
effort: small
release: [R19, R28]
tags: [playbook, color, automation]
---

# Auto Color Parts (零件自动着色)

遍历装配体或零件中的所有几何体，为每个 PartBody 分配随机/固定颜色。

## 目标

一键给装配中所有子零件赋予不同颜色，便于区分和检查。

## 前置条件

- 已加载 CATPart 或 CATProduct 文档
- 可选：颜色映射表（零件名→颜色）

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.assembly_tree` | 遍历装配树获取所有子零件 |
| `cap.geometry_query` | 获取每个零件的 Body/几何体 |
| `cap.visualization` | 修改图形属性（颜色/透明度） |

## 实现步骤

1. **获取根 Product**：`CATIProduct_var spRoot = ...`
2. **遍历子零件**：`CATIProduct::GetChildren()`/`GetAllChildren()`
3. **获取每个零件上的 `CATIVisProperties`**：QueryInterface 得到（该接口管理图形属性）
4. **分配颜色**：先向 `CATVisPropertiesValues::SetColor(r, g, b)` 写入颜色，再调用
   `CATIVisProperties::SetPropertiesAtt(values, CATVPColor, geomType)` 应用
5. **刷新显示**：提交后由 CATIA 自行刷新视图，无需手动 Dispatch

> ⚠️ **修正**：`CATIVisProperties` 接口没有 `SetPropertiesColor(R,G,B)` 方法。真实接口的颜色
> 修改方法需两步：1) 创建 `CATVisPropertiesValues` 对象并调用 `SetColor(r,g,b)`；
> 2) 将其作为参数传入 `SetPropertiesAtt(iValues, CATVPColor, iGeomType)`（定义在基接口
> `CATIVisPropertiesAbstract` 中，官方样例见 `CAAGviApplyProperties.cpp`）。

## 完整代码

```cpp
HRESULT AutoColorParts(CATIProduct *iRoot) {
    if (NULL == iRoot) return E_FAIL;

    CATListValCATBaseUnknown_var *pChildren = iRoot->GetChildren();
    if (NULL == pChildren) return S_OK;

    for (int i = 1; i <= pChildren->Size(); i++) {
        CATIVisProperties_var spVis = (*pChildren)[i];
        if (NULL_var == spVis) continue;

        // 随机颜色
        unsigned int r = rand() % 256;
        unsigned int g = rand() % 256;
        unsigned int b = rand() % 256;

        // 先写入 CATVisPropertiesValues，再通过 SetPropertiesAtt 应用
        CATVisPropertiesValues values;
        values.SetColor(r, g, b);
        HRESULT rc = spVis->SetPropertiesAtt(values, CATVPColor, CATVPGlobalType);
        if (FAILED(rc)) continue;
    }
    delete pChildren;
    return S_OK;
}
```

## 注意事项

- `SetPropertiesAtt` 返回 `HRESULT`，失败请检查 `iGeomType` 是否与实际几何类型匹配
- 大装配建议用进度条
- 可预先定义调色板（按零件类型/材质匹配颜色）
- 装配体中 Reference/Instance 共用几何体，着色影响所有实例

## 相关 Playbook

- `pb.export_bom` — 导出 BOM 可同时记录颜色信息
