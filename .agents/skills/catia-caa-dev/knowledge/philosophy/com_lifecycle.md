---
id: philo.com_lifecycle
title: COM Lifecycle Management / COM 生命周期哲学
category: knowledge
domain: philosophy
keywords: [AddRef, Release, smart pointer, CATBaseUnknown, memory leak, _var, AddRef/Release]
apis: [CATBaseUnknown, AddRef, Release, QueryInterface]
frameworks: [System]
release: [R19, R28]
tags: [philosophy, COM, lifecycle, memory, core]
---
# COM Lifecycle Management

CAA 基于 Dassault 的 COM 变体。对象生命周期由引用计数管理。

## 核心原则

1. **永远使用 Smart Pointer** — `CATISpecObject_var`、`CATIProduct_var` 等 `_var` 后缀类型自动管理 AddRef/Release
2. **裸指针只在局部使用** — 函数参数、临时变量，不能存储
3. **QueryInterface 返回的指针需要 Release？** — `_var` 类型自动处理，裸指针需要手动 Release

## Smart Pointer 模式

```cpp
// ✅ 正确：_var 自动管理
CATISpecObject_var spFeature = ...;
spFeature->Update();  // spFeature 离开作用域自动 Release

// ✅ 正确：函数内临时裸指针
void ProcessFeature(CATISpecObject *iFeature) {
    CATIProduct_var spProduct = iFeature;  // 自动 AddRef/Release
}

// ❌ 错误：裸指针成员变量
class MyClass {
    CATISpecObject *_feature;  // 谁负责 Release？内存泄漏风险！
};

// ✅ 正确：使用 _var 成员
class MyClass {
    CATISpecObject_var _feature;  // 自动管理
};
```

## Null 检查

```cpp
// ✅ CATIA 标准模式
CATISpecObject_var spObj = ...;
if (NULL_var == spObj) return E_FAIL;   // 注意：NULL_var 不是 nullptr
if (!!spObj) { /* spObj 非空 */ }

// ❌ 不要用 nullptr
if (spObj == nullptr) ...  // 不兼容 CATIA 的 NULL_var 语义
```

## 常见内存泄漏场景

| 场景 | 原因 | 修复 |
|------|------|------|
| 裸指针存入容器 | 容器不管理生命周期 | 使用 `CATLISTV(CATISpecObject_var)` |
| `QueryInterface` 后不 Release | 返回的新指针有 +1 Ref | 使用 `_var` 接收 |
| 循环引用 | A→B, B→A, 互相 AddRef | 使用弱引用或手动断开 |
| 异常路径未清理 | try-catch 中提前返回 | RAII (Smart Pointer 自动清理) |
