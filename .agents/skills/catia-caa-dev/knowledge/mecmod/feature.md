---
id: mecmod.feature
title: Feature Model
category: knowledge
domain: mecmod
keywords: [feature, spec object, CATISpecObject, feature tree, update, parent, children, IsATypeOf]
apis: [CATISpecObject, CATIPrtPart, CATIPrtContainer, CATISpecAccess]
requires: []
patterns: [block.visitor, analyzer.geometry]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [core, feature, traversal]
---

# Feature (特征)

CAA 中 Feature 是通过 Spec Object 模型来表示的。所有 Part Design 操作的结果（Pad、Pocket、Fillet、Hole 等）都是 Feature。

## 核心 API

### 获取根 Feature (Part)

```cpp
CATIPrtContainer* pContainer = ...;
CATIPrtPart_var pPart = pContainer->GetPart();
CATISpecObject_var pRoot = pPart;
```

### 遍历子 Feature

```cpp
CATISpecObject_var pRoot = ...;
CATListValCATISpecObject_var children;
pRoot->GetChildren(children);

for (int i = 1; i <= children.Size(); i++) {
    CATISpecObject_var child = children[i];
    // 处理子 Feature...
}
```

### 获取父 Feature

```cpp
CATISpecObject_var pFeature = ...;
CATISpecObject_var pParent = pFeature->GetParent();
```

### 获取 Feature 名称

```cpp
CATUnicodeString name = pFeature->GetName();
```

### 获取 Feature 类型

```cpp
CATUnicodeString type = pFeature->GetType();
// 例如: "Pad", "Pocket", "EdgeFillet", "Hole", "EdgeChamfer"
```

### 判断 Feature 类型

```cpp
if (pFeature->IsATypeOf("EdgeFillet")) {
    // 这是圆角...
}
```

## 递归遍历整个 Feature Tree

```cpp
void TraverseFeature(CATISpecObject_var pRoot) {
    CATListValCATISpecObject_var children;
    pRoot->GetChildren(children);

    for (int i = 1; i <= children.Size(); i++) {
        CATISpecObject_var child = children[i];
        // 处理当前 Feature
        ProcessFeature(child);

        // 递归子节点
        TraverseFeature(child);
    }
}
```

## 常用 Feature 类型

| StartUp 类型 | 说明 |
|-------------|------|
| Pad | 拉伸凸台 |
| Pocket | 拉伸凹槽 |
| Shaft | 旋转体 |
| Groove | 旋转槽 |
| Hole | 孔 |
| EdgeFillet | 边圆角 |
| FaceFillet | 面圆角 |
| EdgeChamfer | 倒角 |
| Draft | 拔模 |
| Shell | 抽壳 |
| Thickness | 加厚 |
| Mirror | 镜像 |
| Pattern | 阵列 |
| Split | 分割 |
| SolidCombine | 布尔运算 |

## 常用判断

| 场景 | 方式 |
|------|------|
| 获取 Part 根 | `CATIPrtPart` → `CATISpecObject` |
| 遍历子节点 | `GetChildren()` |
| 获取父节点 | `GetParent()` |
| 判断类型 | `IsATypeOf("TypeName")` |
| 获取名称 | `GetName()` |
| 获取 Body | `GetBody()` → `CATBody` |
