---
id: part.fillet
title: Edge Fillet
category: knowledge
domain: part
keywords: [fillet, edge fillet, blend, radius, round]
apis: [CATIEdgeFillet, CATIFillet, CATIGeometricalElement, CATISpecObject, CATICkeParm]
requires: [mecmod.feature]
patterns: [analyzer.geometry, analyzer.rule]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [geometry, feature, check]
---

# Edge Fillet (圆角 / Blend)

CATIA 中圆角通过 `EdgeFillet` Feature 表示。

> ⚠️ **重要修正**：`CATIFillet` 确实存在，但它只是一个**空的基础标记接口**（"base interface for each kind of fillets: edge fillets, face fillet, tritangent fillet"），本身不提供 `GetRadius()`/`GetEdge()` 等任何方法。真正带有这些方法的接口是 **`CATIEdgeFillet`**（继承自 `CATIFillet`）。而且 `GetRadius()` 是**直接返回 `double`** 的 const 方法，不是返回智能指针对象再 `->Value()`；取支持边/面用 `GetObject()`（返回列表指针），没有 `GetEdge()` 方法。

## 核心 API

```cpp
// 获取圆角 Feature
CATISpecObject_var spSpecObj = ...;
CATIEdgeFillet_var pFillet = spSpecObj;   // 注意：不是 CATIFillet_var
if (NULL_var == pFillet) return;

// 圆角类型：常量半径 or 变量半径
CATPrtFilletType type = pFillet->GetFilletType();  // CONSTANT 或 VARIABLE

// 读取半径（仅适用于 CONSTANT 类型，直接返回 double）
if (type == CONSTANT) {
    double radius = pFillet->GetRadius();
}

// 变量半径圆角：按顶点取半径
if (type == VARIABLE) {
    CATLISTV(CATISpecObject_var) *pVertices = pFillet->GetVertex();
    if (pVertices && pVertices->Size() > 0) {
        double r = pFillet->GetRadiusOnVertex((*pVertices)[1]);
    }
}

// 获取被倒圆角的边/面列表（返回列表指针，不是单个对象）
CATLISTV(CATISpecObject_var) *pObjList = pFillet->GetObject();
if (pObjList && pObjList->Size() > 0) {
    CATISpecObject_var firstEdgeOrFace = (*pObjList)[1];
}
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
        CATIEdgeFillet_var pFillet = child;
        if (NULL_var == pFillet) continue;
        // 检查半径...
    }
}
```

## 常用判断

| 场景 | 方式 |
|------|------|
| 判断是否为圆角 | `IsATypeOf("EdgeFillet")` |
| 获取圆角类型 | `CATPrtFilletType GetFilletType() const`（`CONSTANT`/`VARIABLE`） |
| 获取常量半径值 | `double GetRadius() const`（仅 `CONSTANT` 类型有效，直接返回 double） |
| 获取指定顶点的变量半径 | `double GetRadiusOnVertex(CATISpecObject_var iVertex) const`（仅 `VARIABLE` 类型有效） |
| 获取变化模式 | `CATPrtFilletVariation GetVariation() const`（`CUBIC`/`LINEAR`） |
| 获取支持边/面 | `CATLISTV(CATISpecObject_var)* GetObject() const`（返回列表，非单个对象） |
| 获取传播模式 | `CATPrtFilletPropagation GetPropagation() const`（`TANGENCY`/`MINIMAL`） |
| 获取圆角名称 | `CATISpecObject->GetName()` |
