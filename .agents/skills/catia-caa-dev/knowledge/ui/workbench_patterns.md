---
id: ui.workbench_patterns
title: Workbench & Addin Patterns
category: knowledge
domain: ui
keywords: [workbench, addin, toolbar, menu, visibility, CATIPrtWksAddin, CATIAfrGeneralWksAddin, MacDeclareHeader]
apis: [CATIPrtWksAddin, CATIWorkbenchAddin, CATIAfrGeneralWksAddin, CATCmdContainer, CATCmdStarter, CATCommandHeader]
requires: [ui.dialog]
patterns: []
examples: []
release: [R19, R28]
tags: [ui, workbench, addin]
---

# CAA Workbench & Addin Patterns

## ⚠️ 重要修正

之前版本以下 API 经核实**不存在或签名错误**：

| 虚构/错误 | 真实 API |
|-----------|---------|
| `CATIGenericWksAddin` | 不存在。通用 addin 接口是 **`CATIAfrGeneralWksAddin`**（ApplicationFrame）；`CATIPrtWksAddin`（MechanicalModelerUI）继承自 **`CATIWorkbenchAddin`** |
| `new CATCmdAccess("name", &Factory)` | 不存在此构造。命令注册用 **`MacDeclareHeader(XxxCmdHdr)`** 生成 Header 类 + 4 参构造 `(HeaderID, LoadName, ClassName, Argument)` |
| `new CATCmdContainer("Title")` | 无公开构造。用 **`NewAccess(CATCmdContainer, pTb, NameId)`** 宏 |
| `pTb->AddCommand(...)` / `AddSeparator()` | 不存在。挂命令用 **`NewAccess(CATCmdStarter,...)` + `SetAccessCommand` + `SetAccessChild`/`SetAccessNext`** 宏链 |
| `CATCmdMenu` / `AddMenu()` / `AddToolbar()` | 均不存在 |
| `CATImplementClass(X, Implementation, CATBaseUnknown, CATNull)` | `CATNull` 不存在；Workbench addin 用 `DataExtension` + 自身类名作第 4 参 |

完整正确模板见 [ui.toolbar](toolbar.md)（已核实），本文件补充 Workbench 层面的组织模式。

## 架构关系

```
Workbench Addin (CATIAfrGeneralWksAddin / CATIPrtWksAddin)
    │
    ├── CreateCommands()   → 注册所有命令（MacDeclareHeader 生成的 Header 类）
    │
    └── CreateToolbars()   → 只挂需要 UI 显示的命令（NewAccess 宏链）
              │
              ├── Toolbar 1 ── Starter→Cmd1 ── Starter→Cmd2
              └── Toolbar 2 ── Starter→Cmd3
```

## 注册 Addin（真实官方模式）

参考官方样例 `CAADoc/CAAApplicationFrame.edu/CAAAfrGeneralWksAddin.m/src/CAAAfrGeneralWksAdn.cpp`：

```cpp
#include "ATModuleAddin.h"
#include "CATIAfrGeneralWksAddin.h"
#include "CATCreateWorkshop.h"

// ⭐ MacDeclareHeader 必须在 .cpp 中使用（不能在 .h，否则链接重复定义）
#include "CATCommandHeader.h"
MacDeclareHeader(ATRenameCmdHdr);
MacDeclareHeader(ATBOMCmdHdr);

CATImplementClass(ATModuleAddin, DataExtension, CATBaseUnknown, ATModuleAddin);
TIE_CATIAfrGeneralWksAddin(ATModuleAddin);

void ATModuleAddin::CreateCommands()
{
    // 4 参构造: (HeaderID, LoadName=DLL名, ClassName, Argument)
    new ATRenameCmdHdr("ATModule.AutoRenameCmd", "ATModule", "AutoRenameCmd", (void*)NULL);
    new ATBOMCmdHdr(   "ATModule.BOMExportCmd",  "ATModule", "BOMExportCmd",  (void*)NULL);
}

CATCmdContainer* ATModuleAddin::CreateToolbars()
{
    NewAccess(CATCmdContainer, pToolbar, ATModuleTlb);
    AddToolbarView(pToolbar, 1, Right);

    NewAccess(CATCmdStarter, pCmd1, ATRenameCmd);
    SetAccessCommand(pCmd1, "ATModule.AutoRenameCmd");
    SetAccessChild(pToolbar, pCmd1);       // 第一个命令：SetAccessChild

    NewAccess(CATCmdStarter, pCmd2, ATBOMCmd);
    SetAccessCommand(pCmd2, "ATModule.BOMExportCmd");
    SetAccessNext(pCmd1, pCmd2);           // 第二个起：SetAccessNext 链接

    return pToolbar;
}
```

## 工作台类型

| 目标 Workbench | Addin 接口 | Framework |
|---------------|-----------|-----------|
| 通用（多数场景） | `CATIAfrGeneralWksAddin` | ApplicationFrame |
| Part Design | `CATIPrtWksAddin` | MechanicalModelerUI |

二者最终都继承 `CATIWorkbenchAddin`。字典 (.dico) 条目格式：

```
ATModuleAddin  CATIAfrGeneralWksAddin  libATModule
```

## 命令可见性控制

`CreateCommands()` 注册的命令**不一定**出现在工具栏——`CreateToolbars()` 只挂需要 UI 显示的：

```cpp
void ATModuleAddin::CreateCommands() {
    // 全部注册（脚本/宏/菜单可用）
    new ATRenameCmdHdr(  "ATModule.AutoRenameCmd", "ATModule", "AutoRenameCmd", (void*)NULL);
    new ATInternalCmdHdr("ATModule.InternalCmd",   "ATModule", "InternalCmd",   (void*)NULL);
    new ATBatchCmdHdr(   "ATModule.BatchCmd",      "ATModule", "BatchCmd",      (void*)NULL);
}

CATCmdContainer* ATModuleAddin::CreateToolbars() {
    NewAccess(CATCmdContainer, pToolbar, ATModuleTlb);
    AddToolbarView(pToolbar, 1, Right);

    // 只挂需要按钮显示的命令
    NewAccess(CATCmdStarter, pCmd, ATRenameCmd);
    SetAccessCommand(pCmd, "ATModule.AutoRenameCmd");
    SetAccessChild(pToolbar, pCmd);
    // InternalCmd / BatchCmd 不挂 → 无按钮，但仍可被宏/批处理调用

    return pToolbar;
}
```

## ⚠️ 多命令挂同一工具栏（最易踩的坑）

`SetAccessChild` 是"设置唯一子节点"，**重复调用会覆盖**——先注册的按钮图标仍在但点击无反应。第一个用 `SetAccessChild`，之后每个用 `SetAccessNext(prev, new)` 链接。详见 [fp_toolbar_setaccesschild_overwrite.md](../failure_patterns/fp_toolbar_setaccesschild_overwrite.md)。

## AI 生成规则

- [ ] Addin 用 `CATImplementClass(X, DataExtension, CATBaseUnknown, X)` + `TIE_CATIAfrGeneralWksAddin(X)`
- [ ] Header 类用 `MacDeclareHeader` 生成，**只在 .cpp**
- [ ] 命令构造必须 4 参 `(HeaderID, LoadName, ClassName, Argument)`
- [ ] `CreateCommands()` 注册所有命令；`CreateToolbars()` 只挂需显示的
- [ ] Toolbar 用 `NewAccess`/`SetAccessChild`/`SetAccessNext` 宏链，**禁止发明 `AddCommand`/`CATCmdMenu`**
- [ ] .dico 条目：`AddinClass CATIAfrGeneralWksAddin libYourModule`
