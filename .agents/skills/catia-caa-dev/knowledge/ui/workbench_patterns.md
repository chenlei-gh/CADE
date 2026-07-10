---
id: ui.workbench_patterns
title: Workbench & Addin Patterns
category: knowledge
domain: ui
keywords: [workbench, addin, toolbar, menu, visibility, CATIPrtWksAddin, CATCmdContainer]
apis: [CATIPrtWksAddin, CATIGenericWksAddin, CATCmdContainer, CATCmdAccess, CATCmdMenu]
requires: [ui.dialog]
patterns: []
examples: []
release: [R19, R28]
tags: [ui, workbench, addin]
---

# CAA Workbench & Addin Patterns

## 架构关系

```
Workbench (CATIPrtWksAddin / CATIGenericWksAddin)
    │
    ├── Toolbar 1 ── Command 1
    │              ── Command 2
    │
    └── Toolbar 2 ── Command 3
                   ── Command 4
```

## Workbench 基本结构

### Interface (PublicInterfaces/IATWorkbench.h)

```cpp
#include "CATBaseUnknown.h"
#include "CATIPrtWksAddin.h"  // Part workbench

extern IID IID_IATWorkbench;

class IATWorkbench : public CATIPrtWksAddin {
    CATDeclareInterface;
public:
    // CATIPrtWksAddin 接口
    virtual void CreateCommands() = 0;
    virtual CATCmdAccess *CreateToolbars() = 0;
};
```

### 实现 (LocalInterfaces/ATWorkbench.h)

```cpp
#include "IATWorkbench.h"
#include "CATBaseUnknown.h"

class ATWorkbench : public CATBaseUnknown {
    CATDeclareClass;
public:
    ATWorkbench();
    virtual ~ATWorkbench();

    // 工作台扩展接口
    void CreateCommands() override;
    CATCmdAccess *CreateToolbars() override;

private:
    CATCmdContainer *_pToolbar1;
    CATCmdContainer *_pToolbar2;
};
```

### 注册 Addin (src/ATAddin.cpp)

```cpp
#include "ATWorkbench.h"
#include "TIE_CATIPrtWksAddin.h"

CATImplementClass(ATWorkbench, Implementation, CATBaseUnknown, CATNull);
CATImplementBOA(IATWorkbench, CATIPrtWksAddin);

void ATWorkbench::CreateCommands() {
    // 创建命令访问器
    new CATCmdAccess("ATAutoRenameCmd",   &ATAutoRenameCmd::Factory);
    new CATCmdAccess("ATBOMExportCmd",    &ATBOMExportCmd::Factory);
    new CATCmdAccess("ATExplodeCmd",      &ATExplodeCmd::Factory);
}

CATCmdAccess *ATWorkbench::CreateToolbars() {
    // Toolbar 1: Actions
    _pToolbar1 = new CATCmdContainer("AT Actions");
    _pToolbar1->AddCommand("ATAutoRenameCmd");
    _pToolbar1->AddCommand("ATBOMExportCmd");
    _pToolbar1->AddSeparator();
    _pToolbar1->AddCommand("ATExplodeCmd");
    
    return _pToolbar1;
}
```

## 工作台类型

| Tip | 从哪个基类继承 |
|-----|--------------|
| Part | `CATIPrtWksAddin` |
| Assembly | `CATIPrtWksAddin`（Product 也是 Part） |
| Drawing | `CATIDrwWksAddin` |
| Generic（独立） | `CATIGenericWksAddin` |

## 水平条 vs 垂直条

```cpp
// 水平 Toolbar（菜单区域）
CATCmdContainer *pTb = new CATCmdContainer("AT Actions", CATDlgFraNoFrame);

// 垂直 Toolbar（侧边工具栏）
CATCmdContainer *pVTB = new CATCmdContainer("AT Side Panel",
    CATDlgFraNoFrame | CATDlgGridLayout);
```

## Toolbar 控件类型

```cpp
// 普通按钮
_pToolbar->AddCommand("ATAutoRenameCmd");

// 分隔线
_pToolbar->AddSeparator();

// 下拉菜单
CATCmdMenu *pMenu = new CATCmdMenu("Options");
pMenu->AddCommand("ATOption1");
pMenu->AddCommand("ATOption2");
_pToolbar->AddMenu(pMenu);

// 子 Toolbar
CATCmdContainer *pSub = new CATCmdContainer("Sub Tools");
pSub->AddCommand("ATSubCmd1");
_pToolbar->AddToolbar(pSub);
```

## 命令可见性控制

不是所有命令都显示在 Toolbar：

```cpp
void ATWorkbench::CreateCommands() {
    // 命令注册（必须全部注册）
    new CATCmdAccess("ATAutoRenameCmd",   &ATAutoRenameCmd::Factory);
    new CATCmdAccess("ATInternalCmd",     &ATInternalCmd::Factory);
    new CATCmdAccess("ATBatchCmd",        &ATBatchCmd::Factory);
}

CATCmdAccess *ATWorkbench::CreateToolbars() {
    _pToolbar = new CATCmdContainer("AT Actions");
    _pToolbar->AddCommand("ATAutoRenameCmd");   // ✅ 可见
    // ATInternalCmd 注册了但不在 Toolbar → 脚本/宏可用
    // ATBatchCmd 注册了但不在 Toolbar → 通过菜单调用
    return _pToolbar;
}
```

## AI 生成规则

- [ ] Workbench 类继承正确的 Addin 接口（Part/Drawing/Generic）
- [ ] 每个 Command 用 `new CATCmdAccess` 注册
- [ ] `CreateCommands()` 注册所有命令
- [ ] `CreateToolbars()` 只放需要 UI 显示的命令
- [ ] 用 `AddSeparator()` 分组
- [ ] 用 `AddMenu()` 创建下拉菜单
