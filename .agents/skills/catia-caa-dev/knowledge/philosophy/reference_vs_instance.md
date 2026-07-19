---
id: philo.ref_vs_instance
title: Reference vs Instance / 实例化哲学
category: knowledge
domain: philosophy
keywords: [reference, instance, occurrence, CATIProduct, shared geometry, pattern, CATPathElement]
apis: [CATISpecObject, CATIProduct, CATPathElement]
frameworks: [ObjectSpecsLegacy, ProductStructure]
release: [R19, R28]
tags: [philosophy, reference, instance, core]
---
# Reference vs Instance

CAA 中最容易出错的概念。理解它需要区分三种存在：

| 概念 | CAA 接口 | 说明 |
|------|---------|------|
| **Reference** | `CATISpecObject`（Part 级）/ `CATIProduct`（Product 级，`IsReference()==TRUE`） | 定义——几何体、属性、颜色都存储在这里 |
| **Instance** | `CATISpecObject`（`GetReference()!=NULL`）/ `CATIProduct`（`GetReferenceProduct()` 指回其 Reference） | 出现——指向 Reference，有自己的位置/变换 |
| **Occurrence path** | `CATPathElement` | 路径——从根到实例的完整导航路径（用于选中/高亮特定 occurrence，而非独立接口） |

## ⚠️ 重要修正

| 错误写法 | 问题 | 正确写法 |
|------|------|------|
| `CATIDerivation_var spDeriv = spInstance; spDeriv->GetReference(spReference);` | `CATIDerivation` 接口不存在 | `CATISpecObject::GetReference()` 直接返回 `CATISpecObject*`（无输出参数），或 `CATIProduct::GetReferenceProduct()` 直接返回 `CATIProduct_var` |
| `CATIPrtContainer_var spContainer = spInstance; spContainer->ListChildren(children);` | `CATIPrtContainer` 是 Part 容器接口，没有 `ListChildren()`；且不适用于遍历 Product 子组件 | `CATIProduct::GetChildren()`/`GetAllChildren()`，直接返回 `CATListValCATBaseUnknown_var*` |
| `CATIProductOccurrence` 接口 | 不存在（CAADoc 无匹配） | Product 装配树中的"路径/occurrence"概念用 `CATPathElement` 表达，不是独立接口 |

## 关键规则

1. **几何体共享** — 同一 Reference 的所有 Instance 共享几何体。修改 Reference 的几何体会影响所有 Instance。
2. **属性独立** — Instance 可以覆盖部分属性（如 InstanceName、位置矩阵）。
3. **Instance 数量 ≠ Reference 数量** — 装配体中 Instance 数量通常远大于 Reference 数量。

## 代码示例

```cpp
// Part 级：从 Instance 获取 Reference（直接返回值，无输出参数）
CATISpecObject_var spInstance = ...;
CATISpecObject* pReference = spInstance->GetReference();
// pReference == NULL 表示 spInstance 本身就是 Reference

// Product 级：从 Instance 获取 Reference Product
CATIProduct_var pInstanceProduct = ...;
CATIProduct_var pReferenceProduct = pInstanceProduct->GetReferenceProduct();
CATBoolean isRef = pInstanceProduct->IsReference();

// 获取 Instance 的绝对位置变换矩阵
CATIMovable_var spMovable = pInstanceProduct;
CATMathTransformation matrix;
spMovable->GetAbsPosition(matrix);

// 遍历 Product 的子节点（直接返回值，元素需 cast 到 CATIProduct_var）
CATListValCATBaseUnknown_var* pChildren = pInstanceProduct->GetChildren();
if (pChildren != NULL) {
    for (int i = 1; i <= pChildren->Size(); i++) {
        CATIProduct_var child = (*pChildren)[i];
    }
    delete pChildren;
}
```

## 常见陷阱

- ❌ 在 Instance 上直接修改几何体（应该修改 Reference）
- ❌ 混淆 InstanceName（`GetPrdInstanceName`）和 PartNumber（`GetPartNumber`，Reference 共享）
- ❌ 在遍历时同时修改容器结构
- ❌ 假设 Instance 的 `QueryInterface` 能获取 Reference 的接口
- ❌ 混用 Part 级 API（`CATISpecObject::GetReference()`）和 Product 级 API（`CATIProduct::GetReferenceProduct()`）——两者签名和语义不同，不可互换
