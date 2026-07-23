---
id: philo.caterror
title: CATIA Error Handling / CATError 异常处理哲学
category: knowledge
domain: philosophy
keywords: [CATError, CATTry, CATCatch, HRESULT, error handling, exception, CHECK_ARGS]
apis: [CATError, CATTry, CATCatch, HRESULT, CHECK_ARGS, CATImplementClass]
frameworks: [System]
release: [R19, R28]
tags: [philosophy, error, exception, core]
---
# CATIA Error Handling

CAA 有自己独特的错误处理体系，混合了 HRESULT 返回码和宏异常处理。

## HRESULT 模式

```cpp
// ✅ 标准返回模式
HRESULT MyMethod() {
    HRESULT hr = S_OK;
    // ...
    return hr;
}

// ✅ 检查宏
CHECK_ARGS(spObj);       // 参数为空 → 返回 E_INVALIDARG
IF_FAILED_RETURN(hr);    // hr 失败 → 立即返回
```

## CATTry / CATCatch

CAA 的异常处理不是标准 C++ try-catch：

```cpp
CATTry {
    // 可能抛出 CATError 的代码
    spFeature->Update();
}
CATCatch(CATError, e) {
    // 处理 CATIA 错误
    CATUnicodeString msg = e.GetMessage();
    return E_FAIL;
}
CATEndTry
```

**关键规则**:
- `CATTry` 只能捕获 `CATError` 类型
- 标准 `try-catch` 不能捕获 CAA 内部异常
- `CATCatch` 后必须 `CATEndTry`

## 常见模式

```cpp
HRESULT SafeUpdate(CATISpecObject *iFeature) {
    HRESULT hr = S_OK;
    CHECK_ARGS(iFeature);

    CATTry {
        CATISpecObject_var spFeature = iFeature;
        if (NULL_var != spFeature) {
            spFeature->Update();
        }
    }
    CATCatch(CATError, e) {
        // 记录错误但不阻断流程
        hr = E_FAIL;
    }
    CATEndTry

    return hr;
}
```

## AI 生成规则

- [ ] 所有 public 方法返回 HRESULT
- [ ] 使用 CHECK_ARGS 验证参数
- [ ] 关键操作（Update, Compute）用 CATTry/CATCatch 包裹
- [ ] 不要在 CATTry 块中返回（会跳过 CATEndTry）
- [ ] 析构函数中不能抛异常——CAA 析构标准模式
