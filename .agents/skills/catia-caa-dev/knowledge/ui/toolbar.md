---
id: ui.toolbar
title: Toolbar / CommandHeader
category: knowledge
domain: ui
keywords: [toolbar, CATCommandHeader, CATCmdAccess, CATCmdContainer, catalog, workbench, addin, command registration]
apis: [CATCommandHeader, CATCmdAccess, CATCmdContainer, CATCmdStarter]
requires: [infra.selection]
patterns: []
examples: []
release: [R19, R28]
tags: [ui, command, registration]
---

# Toolbar / CommandHeader (工具栏/命令头)

CAA 命令通过 `CATCommandHeader` 注册到 Workbench 的 Toolbar 中。

## CommandHeader 基本结构

```cpp
// CATCommandHeader 宏声明 (在 Header 文件中)
CATCommandHeader(MyCmdHeader, "MyCmd",
    CATCommandAccess::User,      // 访问级别
    CATCommandMode::Shared,      // 命令模式
    "MyWorkbench",               // 所属 Workbench
    "MyToolbar",                 // 所属 Toolbar
    "My Command",                // 显示名称
    "Cmd Icon",                  // 图标资源
    "Tooltip Text",              // 工具提示
    "MyModule"                   // 所属 Module
);
```

## Workbench Addin 注册

```cpp
// Workbench Addin 中创建 Toolbar
void MyWorkbenchAddin::CreateCommands() {
    // 创建 Toolbar
    new CATCmdContainer("MyToolbar");

    // 添加命令到 Toolbar
    new MyCmdHeader("MyCmd",
        "MyModule",       // Module
        "MyToolbar",       // Toolbar
        "My Command"       // Display Name
    );
}
```

## Catalog 注册

命令必须在 Catalog 中注册才能被 CATIA 识别：

```xml
<!-- Catalog 文件 -->
<Command name="MyCmd" class="MyCmdClass" module="MyModule"/>
```

## 常用参数

| 参数 | 说明 |
|------|------|
| Access | `User` / `Admin` / `Restricted` |
| Mode | `Shared` / `Exclusive` |
| Workbench | 命令所属 Workbench ID |
| Toolbar | 命令所属 Toolbar ID |
| Icon | 图标资源名称 |
| Tooltip | 鼠标悬停提示 |
