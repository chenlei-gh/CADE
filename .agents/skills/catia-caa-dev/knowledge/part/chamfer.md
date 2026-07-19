---
id: part.chamfer
title: Edge Chamfer
category: knowledge
domain: part
keywords: [chamfer, edge chamfer, bevel, angle, length]
apis: [CATIChamfer, CATISpecObject, CATICkeParm]
requires: [mecmod.feature]
patterns: [analyzer.geometry, analyzer.rule]
examples: []
release: [R19, R28]
tags: [geometry, feature, check]
---

# Edge Chamfer (倒角)

CATIA Part Design 中的倒角 Feature，通过 `EdgeChamfer` 类型和 `CATIChamfer` 接口操作。

> ⚠️ **重要修正**：`CATIChamfer` **没有 `GetAngle()` 方法**。角度值是通过 `GetLength2()` 返回的——当 `GetMode()` 为 `LENGTH_ANGLE` 时，`GetLength2()` 的返回值代表角度（而非第二个长度）。同时 `GetLength1()`/`GetLength2()`/`GetMode()`/`GetObject()` 等方法都是**直接返回值**（`double`/`CATPrtChamferMode`/`CATLISTV(CATISpecObject_var)*`），不是返回智能指针对象再链式调用 `->Value()`。`GetEdge()` 也不存在，取支持边/面用 `GetObject()`（返回列表，非单个对象）。

## 核心 API

```cpp
// 获取倒角 Feature
CATISpecObject_var spSpecObj = ...;
CATIChamfer_var pChamfer = spSpecObj;
if (NULL_var == pChamfer) return;

// 倒角模式（直接返回，非输出参数）
CATPrtChamferMode mode = pChamfer->GetMode();   // LENGTH 或 LENGTH_ANGLE

// 读取长度 1（始终是长度，直接返回 double）
double length1 = pChamfer->GetLength1();

// 读取长度 2：其含义取决于 mode
double length2OrAngle = pChamfer->GetLength2();
if (mode == LENGTH_ANGLE) {
    double angle = length2OrAngle;      // 此时代表角度（度）
} else {
    double length2 = length2OrAngle;    // 此时代表第二个长度
}

// 获取被倒角的边/面列表（返回列表指针，不是单个对象）
CATLISTV(CATISpecObject_var) *pObjList = pChamfer->GetObject();
if (pObjList && pObjList->Size() > 0) {
    CATISpecObject_var firstEdgeOrFace = (*pObjList)[1];
}
```

## 遍历所有倒角

```cpp
CATIPrtPart_var pPart = ...;
CATISpecObject_var pRoot = pPart;
CATListValCATISpecObject_var children;
pRoot->GetChildren(children);

for (int i = 1; i <= children.Size(); i++) {
    CATISpecObject_var child = children[i];
    if (child->IsATypeOf("EdgeChamfer")) {
        CATIChamfer_var pChamfer = child;
        if (NULL_var == pChamfer) continue;
        // 检查参数...
    }
}
```

## 倒角模式（`CATPrtChamferMode`，`GetMode()`/`ModifyMode()` 的合法值）

| 模式 | 说明 |
|------|------|
| `LENGTH` | 长度+长度模式（`GetLength1()`/`GetLength2()` 均为长度） |
| `LENGTH_ANGLE` | 长度+角度模式（`GetLength2()` 返回的是角度） |

## 常用判断

| 场景 | 方式 |
|------|------|
| 判断是否为倒角 | `IsATypeOf("EdgeChamfer")` |
| 获取第一长度 | `double GetLength1() const`（直接返回 double） |
| 获取第二长度/角度 | `double GetLength2() const`（含义取决于 `GetMode()`） |
| 获取模式 | `CATPrtChamferMode GetMode() const` |
| 获取支持边/面 | `CATLISTV(CATISpecObject_var)* GetObject() const`（返回列表，非单个对象） |
| 获取传播模式 | `CATPrtChamferPropagation GetPropagation() const`（`_TANGENCY`/`_MINIMAL`） |
| 获取参考面方向 | `CATPrtChamferReferenceFace GetReferenceFace() const` |
