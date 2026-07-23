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

## 预防规则（已实现：diagnostics `_check_link_with_coverage`）

CADE 的 diagnostics 引擎自动扫描源码 `#include`，通过 header_map 查出其所属框架，与 IdentityCard.xml 的 prerequisite 声明对比。缺失 prerequisite 的会报 ERROR 并附修复指引。同时 `_check_imakefile` 检查 LINK_WITH 条目是否误填框架名（如 `VisualizationBase` 而非 `CATViz`）。
