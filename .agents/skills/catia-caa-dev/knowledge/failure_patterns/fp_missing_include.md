---
id: fp.missing_include
title: Missing #include / 头文件缺失
category: knowledge
domain: failure_patterns
severity: compile_error
apis: []
frameworks: []
keywords: [include, header, compile, missing]
tags: [failure_pattern, compile, infrastructure]
release: [R19, R28]
---
# Missing #include

## 症状

```text
mkmk error: 'CATISpecObject' does not name a type
mkmk error: 'CATIPrtContainer_var' was not declared in this scope
```

## 原因

生成的 .cpp/.h 文件缺少必要的 `#include`。

## 常见缺失列表

| 使用的类型 | 需要 #include |
|-----------|--------------|
| `CATISpecObject` | `CATISpecObject.h` |
| `CATISpecObject_var` | `CATISpecObject.h` |
| `CATIPrtContainer` | `CATIPrtContainer.h` |
| `CATIProduct` | `CATIProduct.h` |
| `CATIMeasurable` | `CATIMeasurable.h` |
| `CATIMechanicalUpdate` | `CATIMechanicalUpdate.h` |
| `CATIVisProperties` | `CATIVisProperties.h` |
| `CATDlgDialog` | `CATDlgDialog.h` |
| `CATPathElement` | `CATPathElement.h` |
| `CATMathTransformation` | `CATMathTransformation.h` |

## 修复

在 .h 或 .cpp 文件顶部添加缺失的 include。

## 预防规则

- [ ] 模板生成时自动添加常用 include
- [ ] 基于模板类型推断需要的头文件
- [ ] 命令模板默认 include: `CATStateCommand.h`, `CATDialogEngine.h`
- [ ] Feature 模板默认 include: `CATISpecObject.h`, `CATIMechanicalFeature.h`
