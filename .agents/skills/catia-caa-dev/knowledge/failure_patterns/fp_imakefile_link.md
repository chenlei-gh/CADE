---
id: fp.imakefile_link
title: Imakefile LINK_WITH Missing / 编译链接缺失
category: knowledge
domain: failure_patterns
severity: compile_error
apis: []
frameworks: []
keywords: [imakefile, LINK_WITH, link, compile]
tags: [failure_pattern, compile, infrastructure]
release: [R19, R28]
---
# Imakefile LINK_WITH Missing

## 症状

```text
mkmk error: unresolved external symbol "CATIProduct::ListChildren(...)"
mkmk error: linker failed
```

## 原因

生成的 Imakefile.mk 中 `LINK_WITH` 缺少必需的 Framework。

## 检测

- 扫描生成的 .cpp 文件中的 `#include` 和使用的接口
- 对比 Imakefile.mk 的 `LINK_WITH` 列表
- 缺失的 Framework 自动建议添加

## 修复

```makefile
# 修改前
LINK_WITH = CATAssemblyInterfaces

# 修改后
LINK_WITH = CATAssemblyInterfaces CATProductStructure CATMecModUseItf
```

## 预防规则

- [ ] 使用 `CATIProduct` → 需链接 `CATProductStructure`
- [ ] 使用 `CATIMeasurable` → 需链接 `CATMecModUseItf`
- [ ] 使用 `CATISpecObject` → 需链接 `ObjectModelerBase`
- [ ] 使用 `CATIVisProperties` → 需链接 `CATGraphicProperties`
- [ ] 使用 `CATDlgDialog` → 需链接 `DialogEngine`
