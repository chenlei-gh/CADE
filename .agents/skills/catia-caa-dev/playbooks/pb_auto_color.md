---
id: pb.auto_color
title: Auto Color Parts / 零件自动着色
category: playbook
domain: product
keywords: [color, auto, random, visualization, graphic properties, material, shade]
capabilities: [cap.visualization, cap.geometry_query, cap.assembly_tree]
apis: [CATIVisProperties, CATIVisManager, CATISpecObject, CATIProduct]
frameworks: [CATGraphicProperties, Visualisation, CATAssemblyInterfaces]
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

1. **获取根 Product**：`CATISpecObject_var spRoot = ...`
2. **遍历子零件**：`CATIPrdIterator` 或递归遍历 Children
3. **获取每个零件的几何体**：`QueryInterface(CATIPartRequest) → GetBody()`
4. **分配颜色**：`CATIVisProperties::SetPropertiesColor(R, G, B)`
5. **Update**：`CATIModelEvents::Dispatch()`

## 完整代码

```cpp
HRESULT AutoColorParts(CATISpecObject *iRoot) {
    CATIPrtContainer_var spContainer = iRoot;
    if (NULL_var == spContainer) return E_FAIL;

    CATListValCATISpecObject children;
    spContainer->ListChildren(children);

    for (int i = 1; i <= children.Size(); i++) {
        CATISpecObject_var spChild = children[i];
        
        // 随机颜色
        int r = rand() % 256;
        int g = rand() % 256;
        int b = rand() % 256;

        // 应用到几何
        CATIVisProperties_var spVis = spChild;
        if (NULL_var != spVis) {
            spVis->SetPropertiesColor(r, g, b);
        }
    }
    return S_OK;
}
```

## 注意事项

- 颜色应用后需调用 `Update()` 或 `CATIModelEvents::Dispatch()`
- 大装配建议用进度条
- 可预先定义调色板（按零件类型/材质匹配颜色）
- 装配体中 Reference/Instance 共用几何体，着色影响所有实例

## 相关 Playbook

- `pb.export_bom` — 导出 BOM 可同时记录颜色信息
