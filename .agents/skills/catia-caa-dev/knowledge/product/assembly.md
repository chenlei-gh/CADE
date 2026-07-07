---
id: product.assembly
title: Assembly
category: knowledge
domain: product
keywords: [assembly, product, component, instance, position, constraints, CATIProduct, CATIPrtContainer]
apis: [CATIProduct, CATIPrtContainer, CATIMovable, CATIConstraints, CATIPosition]
requires: [mecmod.feature]
patterns: [block.visitor]
examples: []
release: [R19, R28]
tags: [assembly, product, structure]
---

# Assembly (装配)

CATIA 装配设计（Assembly Design）通过 Product 和 Component 模型组织。

## 核心 API

### 获取 Product 根

```cpp
CATIPrtContainer* pContainer = ...;
CATIProduct_var pRootProduct = pContainer->GetRootProduct();
```

### 遍历子组件

```cpp
CATIProduct_var pRoot = ...;
CATListValCATIProduct_var children;
pRoot->GetChildren(children);

for (int i = 1; i <= children.Size(); i++) {
    CATIProduct_var child = children[i];
    // 处理子组件...
}
```

### 获取组件实例名称

```cpp
CATIProduct_var pProduct = ...;
CATUnicodeString name = pProduct->GetName();
CATUnicodeString instance = pProduct->GetInstanceName();
```

### 获取组件位置

```cpp
CATIMovable_var pMovable = pProduct;
CATMathTransformation position;
pMovable->GetAbsPosition(position);
```

### 获取组件约束

```cpp
CATIConstraints_var pConstraints = pProduct;
CATListValCATISpecObject_var constraints;
pConstraints->GetConstraints(constraints);
```

## 常用判断

| 场景 | 方式 |
|------|------|
| 获取根 Product | `GetRootProduct()` |
| 遍历子组件 | `GetChildren()` |
| 获取实例名 | `GetInstanceName()` |
| 获取绝对位置 | `GetAbsPosition()` |
| 获取约束 | `GetConstraints()` |
| 获取 Part 容器 | `GetPartContainer()` |
| 判断是否为 Part | `IsPart()` |
