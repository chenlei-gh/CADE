---
id: infra.error_handling
title: Error Handling
category: knowledge
domain: infrastructure
keywords: [error, HRESULT, CHECK_ARGS, IF_FAILED_RETURN, exception, CATError]
apis: [HRESULT, CATError, CATTry, CATCatch]
requires: []
patterns: []
examples: []
release: [R19, R28]
tags: [infrastructure, error, debugging]
---

# CAA Error Handling

## 核心原则

所有 CAA 方法返回 `HRESULT`，不要返回 `void` 或 `bool`。

```cpp
// ❌ 错误
void DoSomething() { ... }
bool Compute() { ... }

// ✅ 正确
HRESULT DoSomething() { ... return S_OK; }
HRESULT Compute() { ... return S_OK; }
```

## 返回值规范

| 值 | 含义 | 何时用 |
|----|------|--------|
| `S_OK` | 成功 | 正常返回 |
| `S_FALSE` | 成功但不需要继续 | Condition() 返回 FALSE 等价 |
| `E_FAIL` | 通用失败 | 出错 |
| `E_INVALIDARG` | 参数无效 | NULL 指针检查 |
| `E_OUTOFMEMORY` | 内存不足 | new 失败 |
| `E_NOTIMPL` | 未实现 | 占位方法 |
| `E_UNEXPECTED` | 意外状态 | 不该发生的路径 |

## 模式 1：参数验证

```cpp
HRESULT ATAutoRenameCmd::Rename(CATISpecObject *iSpecObj, CATUnicodeString &iNewName) {
    // 1. 参数验证
    if (!iSpecObj) {
        return E_INVALIDARG;
    }
    if (iNewName.GetLength() == 0) {
        CATError("ATAutoRenameCmd::Rename", "Rename",
                 "Empty name not allowed");
        return E_INVALIDARG;
    }
    
    // 2. 执行逻辑
    HRESULT hr = iSpecObj->SetAttribute("V_Name", iNewName);
    if (FAILED(hr)) {
        CATError("ATAutoRenameCmd::Rename", "Rename",
                 "Failed to set name attribute");
        return hr;
    }
    
    return S_OK;
}
```

## 模式 2：链式调用

```cpp
HRESULT ATAutoRenameCmd::ProcessFeature(CATISpecObject *iObj) {
    HRESULT hr = S_OK;
    
    // 获取接口
    CATIParmPublisher_var spPub = NULL_var;
    hr = iObj->QueryInterface(IID_CATIParmPublisher, (void**)&spPub);
    if (FAILED(hr)) return hr;
    
    // 获取参数
    CATISpecAttrAccess_var spAccess = NULL_var;
    hr = iObj->QueryInterface(IID_CATISpecAttrAccess, (void**)&spAccess);
    if (FAILED(hr)) return hr;
    
    return S_OK;
}
```

**法则**：
- 每步检查 `FAILED(hr)`
- 使用 `_var` 后缀声明智能指针
- QueryInterface 是 CAA 最常用的模式

## 模式 3：CATTry/CATCatch

```cpp
HRESULT ATAutoRenameCmd::SafeOperation() {
    CATTry {
        // 可能抛异常的代码
        CATISpecObject *pObj = GetCurrentObject();
        if (!pObj) throw CATError("No object selected");
        
        // 正常逻辑
        pObj->Update();
        return S_OK;
    }
    CATCatch(CATError, e) {
        CATError("ATAutoRenameCmd", "SafeOperation", e.GetMessage());
        return E_FAIL;
    }
    CATEndTry
    
    return S_OK;
}
```

## 模式 4：智能指针（CAA 特有）

```cpp
// ❌ 错误：手动管理内存
CATISpecObject *pObj = GetObject();
// ... 使用 pObj ...
pObj->Release();  // 容易忘

// ✅ 正确：使用 _var 智能指针
CATISpecObject_var spObj = GetObject();
// ... 使用 spObj ... 
// 自动 Release
```

## 模式 5：错误上报

```cpp
HRESULT ATAutoRenameCmd::BatchRename(CATLISTV(CATISpecObject_var) &iObjects) {
    int successCount = 0;
    int failCount = 0;
    
    for (int i = 0; i < iObjects.Size(); i++) {
        HRESULT hr = Rename(iObjects[i], _newName);
        if (SUCCEEDED(hr)) {
            successCount++;
        } else {
            failCount++;
            // 记录错误但不中断整个批量操作
            CATUnicodeString indexStr;
            indexStr.BuildFromNum(i);
            CATUnicodeString msg("Failed on object #");
            msg.Append(indexStr);
            CATError("ATAutoRenameCmd", "BatchRename", msg);
        }
    }
    
    // 返回总体结果
    if (failCount > 0 && successCount == 0) {
        return E_FAIL;  // 全部失败
    }
    if (failCount > 0) {
        return S_FALSE; // 部分失败
    }
    return S_OK;  // 全部成功
}
```

## AI 生成规则

- [ ] 所有方法返回 `HRESULT`（除 GetState 等生命周期方法）
- [ ] 每个指针参数校验 `if (!ptr) return E_INVALIDARG;`
- [ ] QueryInterface 后检查 `FAILED(hr)`
- [ ] 使用 `_var` 智能指针
- [ ] 调用 CATError 上报可读错误信息
- [ ] 不要 `return -1` 或 `return false`（用 HRESULT）
- [ ] 链式调用时每步检查返回值
