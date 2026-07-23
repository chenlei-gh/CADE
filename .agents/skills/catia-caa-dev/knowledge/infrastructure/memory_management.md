---
id: infra.memory
title: Memory Management
category: knowledge
domain: infrastructure
keywords: [memory, reference counting, AddRef, Release, smart pointer, leak, CATBaseUnknown]
apis: [CATBaseUnknown, AddRef, Release, CompatibleCast]
requires: []
patterns: []
examples: []
release: [R19, R28]
tags: [infrastructure, memory, reference]
---

# CAA Memory Management

## 黄金法则

**CAA 用引用计数，不是 GC。你不 Release，内存就泄漏。**

## 智能指针（`_var`）

```cpp
// ❌ 手动管理：极容易遗漏
CATISpecObject *pObj = NULL;
hr = pPath->FindElement(IID_CATISpecObject, (void**)&pObj);
// ... 使用 pObj ...
pObj->Release();  // 忘了 = 内存泄漏

// ✅ 智能指针：自动 Release
CATISpecObject_var spObj = NULL_var;
hr = pPath->FindElement(IID_CATISpecObject, (void**)&spObj);
// ... 使用 spObj ...
// 自动 Release（离开作用域时）
```

## AddRef / Release 规则

| 场景 | 谁负责 Release | 说明 |
|------|--------------|------|
| `new` 自己 | 自己 | 或交给 parent |
| `QueryInterface` | 调用者 | 每次 QI 都 +1 ref |
| `GetDirectObject` | 调用者 | 调用者 Release |
| `AddRef()` 手动 | 你 | 手动 +1 后必须手动 Release |
| 传给 parent | parent | `parent->AddChild(this)` 后 parent 负责 |

## 常见泄漏模式及修复

### 泄漏 1：忘了 Release

```cpp
// ❌ 泄漏
void DoWork() {
    CATISpecObject *pObj = GetCurrentObject();
    CATUnicodeString name = pObj->GetName();
    // pObj never Released
}

// ✅ 用 _var
void DoWork() {
    CATISpecObject_var spObj = GetCurrentObject();
    CATUnicodeString name = spObj->GetName();
    // spObj auto-Release
}
```

### 泄漏 2：提前 return

```cpp
// ❌ 提前 return 绕过了 Release
HRESULT Process(CATISpecObject *iObj) {
    if (!iObj) return E_INVALIDARG;  // OK，参数不用 Release
    
    CATIParmPublisher *pPub = NULL;
    iObj->QueryInterface(IID_CATIParmPublisher, (void**)&pPub);
    if (!pPub) return E_FAIL;  // ❌ pPub 已 AddRef，泄漏！
    
    pPub->Release();  // 正常路径释放
    return S_OK;
}

// ✅ 用 _var 自动处理
HRESULT Process(CATISpecObject *iObj) {
    if (!iObj) return E_INVALIDARG;
    
    CATIParmPublisher_var spPub = NULL_var;
    iObj->QueryInterface(IID_CATIParmPublisher, (void**)&spPub);
    if (NULL_var == spPub) return E_FAIL;  // spPub auto-Release
    
    return S_OK;
}
```

### 泄漏 3：循环引用

```cpp
// ❌ Parent → Child → Parent 循环引用
class Parent : public CATBaseUnknown {
    Child *_pChild;
};
class Child : public CATBaseUnknown {
    Parent *_pParent;  // 持有 Parent 引用 → 循环
};

// ✅ 用 CATCallback 或弱引用
class Child : public CATBaseUnknown {
    // 不持有 Parent 引用，用通知机制
};
```

## 析构模式

```cpp
ATAutoRenameCmd::~ATAutoRenameCmd() {
    // 1. 先释放子对象
    if (_pDlg) {
        _pDlg->RequestDelayedDestruction();
        _pDlg = NULL;
    }
    
    // 2. 释放 Agent
    if (_pAgent) {
        _pAgent->SetFilter(NULL);
        _pAgent->Release();
        _pAgent = NULL;
    }
    
    // 3. 父类析构自动调用
}
```

## Checklist

新建组件时检查：

- [ ] 所有指针成员初始化为 NULL
- [ ] 析构函数释放所有 AddRef 过的指针
- [ ] QueryInterface 后用 `_var` 或手动 Release
- [ ] 提前 return 路径也有 Release
- [ ] 无循环引用
- [ ] 不持有跨生命周期指针（如 Document 指针）
