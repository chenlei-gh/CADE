---
id: fp.undeclared_class
title: Undeclared Class / 未声明类
category: knowledge
domain: failure_patterns
severity: compile_error
apis: []
frameworks: []
keywords: [class, CATDeclareClass, CATImplementClass, compile]
tags: [failure_pattern, compile, infrastructure]
release: [R19, R28]
---
# Undeclared Class

## 症状

```text
mkmk error: 'MyFeature' is not a member of 'MyModule'
mkmk error: CATDeclareClass macro missing
mkmk error: CATImplementClass macro missing
```

## 原因

- 缺少 `CATDeclareClass`（.h 文件）
- 缺少 `CATImplementClass`（.cpp 文件）
- Dictionary 中未注册组件
- TIE 宏未正确使用

## CAA 类声明的完整模式

```cpp
// MyFeature.h
class MyFeature : public CATBaseUnknown {
    CATDeclareClass;           // ← 必须！声明 COM 类

public:
    MyFeature();
    virtual ~MyFeature();
};

// MyFeature.cpp
CATImplementClass(MyFeature, DataExtension, CATBaseUnknown, MyFeatureStartUp);
//                 ↑类名       ↑类型          ↑基类           ↑StartUp对象

// TIE 模式（BOA）
CATImplementBOA(MyFeature, CATIMyInterface);
```

## 修复

- `.h` 添加 `CATDeclareClass`
- `.cpp` 添加 `CATImplementClass`
- Dictionary 添加注册条目
- 检查 TIE 宏是否匹配接口

## 预防规则

- [ ] 所有 CAA 类必须在 .h 中有 `CATDeclareClass`
- [ ] 所有 CAA 类必须在 .cpp 中有 `CATImplementClass`
- [ ] DataExtension 的 StartUp 对象名必须是 `{ClassName}StartUp`
- [ ] 实现接口时必须同时有 TIE 宏和 Dictionary 条目
