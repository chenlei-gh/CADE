---
id: mecmod.feature
title: Feature Model
category: knowledge
domain: mecmod
keywords: [feature, spec object, CATISpecObject, feature tree, update, parent, children, IsSubTypeOf]
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

// CATISpecObject 没有 GetChildren，需 QueryInterface CATINavigateObject
CATINavigateObject_var pNav = pRoot;
CATListValCATBaseUnknown_var* children = pNav->GetChildren();  // 返回裸指针，调用方负责释放

if (children) {
    for (int i = 1; i <= children->Size(); i++) {
        CATISpecObject_var child = (*children)[i];
        // 处理子 Feature...
    }
    delete children;  // GetChildren 返回新分配的列表
}
```

### 获取父 Feature

```cpp
CATISpecObject_var pFeature = ...;
CATISpecObject* pParent = pFeature->GetFather();   // CATISpecObject::GetFather() 返回裸指针
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
if (pFeature->IsSubTypeOf(CATUnicodeString("EdgeFillet"))) {
    // 这是圆角...
}
```

## 递归遍历整个 Feature Tree

```cpp
void TraverseFeature(CATISpecObject_var pRoot) {
    CATINavigateObject_var pNav = pRoot;
    CATListValCATBaseUnknown_var* children = pNav->GetChildren();
    if (!children) return;

    for (int i = 1; i <= children->Size(); i++) {
        CATISpecObject_var child = (*children)[i];
        // 处理当前 Feature
        ProcessFeature(child);

        // 递归子节点
        TraverseFeature(child);
    }
    delete children;
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
| 遍历子节点 | `CATINavigateObject::GetChildren()` |
| 获取父节点 | `CATISpecObject::GetFather()` |
| 判断类型 | `IsSubTypeOf("TypeName")` |
| 获取名称 | `GetName()` |
| 获取 Body | `CATIMfBRep::GetBody()` → `CATBody` |
