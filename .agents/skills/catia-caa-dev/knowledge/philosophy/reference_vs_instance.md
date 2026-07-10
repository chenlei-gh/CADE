---
id: philo.ref_vs_instance
title: Reference vs Instance / 实例化哲学
category: knowledge
domain: philosophy
keywords: [reference, instance, occurrence, CATIProduct, shared geometry, pattern]
apis: [CATISpecObject, CATIDerivation, CATIProduct, CATIProductOccurrence]
frameworks: [ObjectModelerBase, CATAssemblyInterfaces]
release: [R19, R28]
tags: [philosophy, reference, instance, core]
---
# Reference vs Instance

CAA 中最容易出错的概念。理解它需要区分三种存在：

| 概念 | CAA 接口 | 说明 |
|------|---------|------|
| **Reference** | `CATISpecObject` (on root) | 定义——几何体、属性、颜色都存储在这里 |
| **Instance** | `CATISpecObject` (not root) | 出现——指向 Reference，有自己的位置/变换 |
| **Occurrence** | `CATIProductOccurrence` | 路径——从根到实例的完整导航路径 |

## 关键规则

1. **几何体共享** — 同一 Reference 的所有 Instance 共享几何体。修改 Reference 的几何体会影响所有 Instance。
2. **属性独立** — Instance 可以覆盖部分属性（如 InstanceName, 位置矩阵）。
3. **Instance 数量 ≠ Reference 数量** — 装配体中 Instance 数量通常远大于 Reference 数量。

## 代码示例

```cpp
// 从 Instance 获取 Reference
CATISpecObject_var spInstance = ...;
CATIDerivation_var spDeriv = spInstance;
CATISpecObject_var spReference;
spDeriv->GetReference(spReference);

// 获取 Instance 的变换矩阵
CATIMovable_var spMovable = spInstance;
CATMathTransformation matrix;
spMovable->GetAbsPosition(matrix);

// 遍历 Instance 的子节点
CATIPrtContainer_var spContainer = spInstance;
CATListValCATISpecObject children;
spContainer->ListChildren(children);
```

## 常见陷阱

- ❌ 在 Instance 上直接修改几何体（应该修改 Reference）
- ❌ 混淆 InstanceName 和 PartNumber
- ❌ 在遍历时同时修改容器结构
- ❌ 假设 Instance 的 `QueryInterface` 能获取 Reference 的接口
