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

## 核心 API

```cpp
// 获取倒角 Feature
CATISpecObject_var spSpecObj = ...;
CATIChamfer_var pChamfer = spSpecObj;

// 读取长度 1
CATICkeParm_var pLength1 = pChamfer->GetLength1();
double length1 = pLength1->Value();

// 读取长度 2 (非对称时)
CATICkeParm_var pLength2 = pChamfer->GetLength2();
double length2 = pLength2->Value();

// 读取角度
CATICkeParm_var pAngle = pChamfer->GetAngle();
double angle = pAngle->Value();

// 倒角模式 (Length1*Angle 或 Length1*Length2)
int mode = pChamfer->GetMode();
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
        // 检查参数...
    }
}
```

## 倒角模式

| 模式 | 说明 |
|------|------|
| `CATChamferLengthAngle` | 长度+角度模式 |
| `CATChamferLengthLength` | 长度+长度模式 |

## 常用判断

| 场景 | 方式 |
|------|------|
| 判断是否为倒角 | `IsATypeOf("EdgeChamfer")` |
| 获取长度 | `GetLength1()->Value()` |
| 获取角度 | `GetAngle()->Value()` |
| 获取模式 | `GetMode()` |
| 获取支持边 | `GetEdge()` |
