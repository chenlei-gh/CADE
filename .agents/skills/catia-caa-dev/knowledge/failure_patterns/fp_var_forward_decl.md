---
id: fp.var_forward_decl
title: _var Smart Pointer Needs Full Header Include / _var 智能指针必须完整 include
category: knowledge
domain: failure_patterns
severity: compile_error
apis: [CATIPrtContainer, CATISpecObject, CATIProduct, CATBaseUnknown]
frameworks: [System, ObjectModelerBase]
keywords: [_var, smart pointer, forward declaration, 前向声明, C2146, missing semicolon, class CATI, include, header]
tags: [failure_pattern, compile, smart_pointer]
release: [R19, R28]
---
# _var Smart Pointer Needs Full Header Include / _var 智能指针必须完整 include

## 症状

编译时报 20+ 个 `C2146: 语法错误: 缺少";"(在"GetXxx"的前面)` 错误，全部集中在使用了 `CATIXxx_var` 返回类型的函数声明处。

## 原因

CAA 的 `XXX_var` 后缀类型（如 `CATIPrtContainer_var`、`CATISpecObject_var`）不是裸指针，而是智能指针类（类似 `com_ptr_t`）。它的**完整类定义**位于对应的接口头文件 `CATIXxx.h` 中。

前向声明 `class CATIXxx;` 只告诉编译器"这个类型存在"，但不提供 `_var` 类的成员（构造、析构、`operator->` 等）。编译器在遇到 `CATIXxx_var` 时找不到这些定义，就报语法错误。

这是 C++ 通用习惯（"减少 include 耦合，用前向声明"）和 CAA `_var` 特性的冲突。

## 修复

把前向声明换成完整 include：

```cpp
// ❌ 崩溃：前向声明不够，_var 类型未定义
class CATIPrtContainer;
static CATIPrtContainer_var GetPrtContainer(CATDocument* pDoc);

// ✅ 正确：完整 include 提供 _var 定义
#include "CATIPrtContainer.h"
static CATIPrtContainer_var GetPrtContainer(CATDocument* pDoc);
```

## 核心教训

- CAA 的 `_var` 类型**永远**需要完整 `#include`，不能用前向声明替代。
- 前向声明 `class CATIXxx;` 只适用于**裸指针** `CATIXxx*` 的场景（函数参数/返回值是裸指针、不调用任何方法）。
- 一旦你在该文件里用了 `CATIXxx_var`、`CATIXxx_var` 作为局部变量/返回值、或调用了 `->` 操作，就必须 `#include`。

（来源：2026-07-23，CADE `CAAPartToAsm.edu` S2 编译排查，`CAAPtsDocUtils.h`）
