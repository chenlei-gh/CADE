---
id: part.hole
title: Hole
category: knowledge
domain: part
keywords: [hole, drilled hole, pocket, simple hole, counterbore, countersink, diameter, depth]
apis: [CATINewHole, CATISimpleHole, CATISpecObject, CATICkeParm, CATIPrtPart]
requires: [mecmod.feature]
patterns: [analyzer.geometry, analyzer.rule]
examples: []
release: [R19, R28]
tags: [geometry, feature, check]
---

# Hole (孔)

CATIA Part Design 中的 Hole Feature，包括 Simple Hole、Counterbore、Countersink 等类型。

> ⚠️ **重要修正**：真实接口名是 `CATINewHole`（`CATIHole` 不存在）。所有 `Get*` 方法都是 **void 返回、通过输出引用参数传值**的写法（`void GetXxx(Type& oValue)`），不是"返回一个带 `->Value()` 的智能指针对象"再链式调用的写法。`CATISimpleHole` 也是真实接口，但只是继承自 `CATINewHole` 的空标记接口，不额外提供方法。

## 核心 API

```cpp
// 获取孔 Feature
CATISpecObject_var spSpecObj = ...;
CATINewHole_var pHole = spSpecObj;
if (NULL_var == pHole) return;  // 不是孔特征

// 读取直径（void 返回，输出参数）
double diameter = 0.0;
pHole->GetDiameter(diameter);

// 也可以拿到关联的参数对象（重载版本）
CATICkeParm_var pDiameterParm;
pHole->GetDiameter(pDiameterParm);

// 孔类型 (Simple, Tapered, Counterbored, Countersunk, Counterdrilled)
int holeType = 0;
pHole->GetHoleType(holeType);

// 底部类型
int bottomType = 0;
pHole->GetBottomType(bottomType);

// 位置与方向
CATMathPoint origin;
CATMathDirection direction;
pHole->GetPosition(origin, direction);
```

> ⚠️ **没有 `GetDepth()` 方法**。孔的"深度"不是一个独立的 double 属性，而是通过 `GetLimit(CATISpecObject_var& oBottomLimit)` 拿到控制孔底部限制的对象（Limit 对象，比如 Up-To-Plane、Blind 深度等），深度值需要从这个限制对象上进一步解析。不要假设存在 `pHole->GetDepth()->Value()` 这种写法。

## 遍历所有孔

```cpp
CATIPrtPart_var pPart = ...;
CATISpecObject_var pRoot = pPart;
CATListValCATISpecObject_var children;
pRoot->GetChildren(children);

for (int i = 1; i <= children.Size(); i++) {
    CATISpecObject_var child = children[i];
    if (child->IsATypeOf("Hole")) {
        CATINewHole_var pHole = child;
        if (NULL_var == pHole) continue;
        double d = 0.0;
        pHole->GetDiameter(d);
        // 检查是否合规...
    }
}
```

## 孔类型常量

`GetHoleType(int&)`/`SetHoleType(int)` 使用的整型常量含义（Simple / Tapered / Counterbored / Countersunk / Counterdrilled），具体数值需参照 `CATINewHole` 官方文档中 `HoleType` 的合法值说明，不要凭空编号。

## 常用判断

| 场景 | 方式 |
|------|------|
| 判断是否为孔 | `IsATypeOf("Hole")` |
| 获取直径 | `void GetDiameter(double& oDiameter)` |
| 获取直径参数对象 | `void GetDiameter(CATICkeParm_var& oDiameterParm)` |
| 判断孔类型 | `void GetHoleType(int& oHoleType)` |
| 获取底部类型 | `void GetBottomType(int& oBottomType)`（Flat / V-Bottom / Trimmed） |
| 获取底部限制对象（深度相关） | `void GetLimit(CATISpecObject_var& oBottomLimit)` |
| 获取方位 | `void GetPosition(CATMathPoint& oOrigin, CATMathDirection& oDirection)` |
| 是否有螺纹 | `void IsThreaded(int& oThreadMode)` |
