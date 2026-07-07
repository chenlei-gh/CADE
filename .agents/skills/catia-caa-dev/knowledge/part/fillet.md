---
id: part.fillet
title: Edge Fillet
category: knowledge
domain: part
keywords: [fillet, edge fillet, blend, radius, round]
apis: [CATIFillet, CATIGeometricalElement, CATISpecObject, CATICkeParm]
requires: [mecmod.feature]
patterns: [analyzer.geometry, analyzer.rule]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [geometry, feature, check]
---

# Edge Fillet (圆角 / Blend)

CATIA 中圆角通过 `EdgeFillet` Feature 表示，接口为 `CATIFillet`。

## 核心 API

```cpp
// 获取圆角 Feature
CATISpecObject_var spSpecObj = ...;
CATIFillet_var pFillet = spSpecObj;

// 读取半径
CATICkeParm_var pRadius = pFillet->GetRadius();
double radius = pRadius->Value();

// 读取支持边
CATISpecObject_var pEdge = pFillet->GetEdge();
```

## 遍历所有圆角

```cpp
CATIPrtPart_var pPart = ...;
CATISpecObject_var pRoot = pPart;
CATListValCATISpecObject_var children;
pRoot->GetChildren(children);

for (int i = 1; i <= children.Size(); i++) {
    CATISpecObject_var child = children[i];
    if (child->IsATypeOf("EdgeFillet")) {
        CATIFillet_var pFillet = child;
        // 检查半径...
    }
}
```

## 常用判断

| 场景 | 方式 |
|------|------|
| 判断是否为圆角 | `IsATypeOf("EdgeFillet")` |
| 获取半径值 | `GetRadius()->Value()` |
| 高亮圆角 | `CATVisProperties::SetHighlight()` |
| 选择圆角 | `CATISelection->SelectElement()` |
| 获取圆角名称 | `CATISpecObject->GetName()` |
