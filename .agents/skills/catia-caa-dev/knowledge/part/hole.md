---
id: part.hole
title: Hole
category: knowledge
domain: part
keywords: [hole, drilled hole, pocket, simple hole, counterbore, countersink, diameter, depth]
apis: [CATIHole, CATISpecObject, CATICkeParm, CATIPrtPart]
requires: [mecmod.feature]
patterns: [analyzer.geometry, analyzer.rule]
examples: []
release: [R19, R28]
tags: [geometry, feature, check]
---

# Hole (孔)

CATIA Part Design 中的 Hole Feature，包括 Simple Hole、Counterbore、Countersink 等类型。

## 核心 API

```cpp
// 获取孔 Feature
CATISpecObject_var spSpecObj = ...;
CATIHole_var pHole = spSpecObj;

// 读取直径
CATICkeParm_var pDiameter = pHole->GetDiameter();
double diameter = pDiameter->Value();

// 读取深度
CATICkeParm_var pDepth = pHole->GetDepth();
double depth = pDepth->Value();

// 孔类型 (Simple, Tapered, Counterbored, Countersunk, Counterdrilled)
int holeType = pHole->GetHoleType();
```

## 遍历所有孔

```cpp
CATIPrtPart_var pPart = ...;
CATISpecObject_var pRoot = pPart;
CATListValCATISpecObject_var children;
pRoot->GetChildren(children);

for (int i = 1; i <= children.Size(); i++) {
    CATISpecObject_var child = children[i];
    if (child->IsATypeOf("Hole")) {
        CATIHole_var pHole = child;
        double d = pHole->GetDiameter()->Value();
        // 检查是否合规...
    }
}
```

## 孔类型常量

| 类型 | 常量 |
|------|------|
| Simple | `CATSimpleHole` |
| Tapered | `CATTaperedHole` |
| Counterbored | `CATCounterboredHole` |
| Countersunk | `CATCountersunkHole` |
| Counterdrilled | `CATCounterdrilledHole` |

## 常用判断

| 场景 | 方式 |
|------|------|
| 判断是否为孔 | `IsATypeOf("Hole")` |
| 获取直径 | `GetDiameter()->Value()` |
| 获取深度 | `GetDepth()->Value()` |
| 判断孔类型 | `GetHoleType()` |
| 获取底部类型 | `GetBottomType()` (Flat / V-Bottom) |
