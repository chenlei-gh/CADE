---
id: pb.create_context_menu
title: Create Context Menu / 创建右键菜单
category: playbook
domain: ui
keywords: [context menu, right click, CATIContextualMenu, CATExtIContextualMenu, CATCmdStarter, DataExtension, NewAccess, SetAccessCommand]
capabilities: [cap.selection]
apis: [CATIContextualMenu, CATExtIContextualMenu, CATCmdStarter, CATCmdSeparator, CATCmdContainer]
frameworks: [ApplicationFrame, ObjectModelerBase]
difficulty: intermediate
effort: small
release: [R19, R28]
tags: [playbook, context_menu, ui]
---
# Create Context Menu (创建右键菜单)

为 CATIA 某类对象（LateType）添加右键菜单项，点击后启动一个已注册的 Command。

## 目标

在特征树或 3D 视图中右键点击某类对象时，显示自定义菜单项，并触发对应命令。

## 实现步骤

1. **创建 DataExtension** → 直接继承 `CATExtIContextualMenu`（不重写 `GetContextualMenu`）
2. **构造函数中取默认菜单并追加 Starter** → 用 `NewAccess`/`SetAccessCommand` 宏绑定到已注册的 Command Header
3. **在 Workshop Addin 中创建 Command Header + 实际的 CATCommand**（命令本体，不在菜单 DataExtension 里）
4. **字典注册** → 在 framework 级 `.dico` 中注册 `TargetLateType CATIContextualMenu libMyModule`

## 关键代码骨架

```cpp
// DataExtension — 追加菜单项到目标对象的默认右键菜单
// MyObjContextualMenu.h
#include "CATExtIContextualMenu.h"

class MyObjContextualMenu : public CATExtIContextualMenu {
    CATDeclareClass;
public:
    MyObjContextualMenu();
    virtual ~MyObjContextualMenu();
private:
    MyObjContextualMenu(const MyObjContextualMenu &);
    MyObjContextualMenu &operator=(const MyObjContextualMenu &);
};

// MyObjContextualMenu.cpp
#include "MyObjContextualMenu.h"
#include "CATCreateWorkshop.h"

// 第四个参数 = 目标对象的 LateType（被右键的对象类型）
CATImplementClass(
    MyObjContextualMenu,
    DataExtension,              // 不是 Implementation！
    CATBaseUnknown,
    CATPart);                   // 例：挂在所有 Part 实体上

#include "TIE_CATIContextualMenu.h"
TIE_CATIContextualMenu(MyObjContextualMenu);

MyObjContextualMenu::MyObjContextualMenu()
{
    CATCmdContainer *pMenu = NULL;
    // 取默认菜单（借用指针，不 Release），不重写 GetContextualMenu()
    HRESULT hr = CATExtIContextualMenu::GetContextualMenu(pMenu);
    if (SUCCEEDED(hr) && NULL != pMenu) {
        NewAccess(CATCmdSeparator, pSeparator, MyObjCtxSep);
        NewAccess(CATCmdStarter, pStarter, MyObjInspectCtx);
        // 绑定到已在 Workshop Addin 中注册的 Command Header ID
        SetAccessCommand(pStarter, "MyObjInspectHdr");
        SetAccessNext(pSeparator, pStarter);
        AddAccessChild(pMenu, pSeparator);
    }
}

MyObjContextualMenu::~MyObjContextualMenu() {}
```

命令本体（实际业务逻辑）是一个独立的 `CATCommand`，随 Header ID `"MyObjInspectHdr"` 在 Workshop Addin 中注册，与菜单 DataExtension 完全分离；点击菜单项后由 CATIA 命令框架负责实例化并启动它，菜单代码本身不需要、也不应该去"手动获取选中对象再调用某个 StartCommand"这类便捷入口——这类方法在 `CATCmdStarter`/`CATExtIContextualMenu` 中并不存在。选中对象应在 Command 内部通过标准的 Selection/Interactor 机制获取（参见 `capabilities/selection.md`），不是通过菜单扩展。

## Dictionary 注册

在 framework 级 `.dico` 中（列序：目标 LateType，查询接口，承载库名）：

```text
CATPart CATIContextualMenu libMyModule
```

## 注意事项

- `CATExtIContextualMenu::GetContextualMenu(CATCmdContainer*&)` 只能在构造函数中调用取默认菜单，**不要重写它**；DataExtension 追加项目即可，不需要（也不能）自己实现菜单查询逻辑
- `CATCmdStarter` 没有可重写的 `StartCommand()` 方法；菜单项通过 `SetAccessCommand` 绑定 Header ID，真正的命令逻辑写在独立的 `CATCommand` 里
- `CATPart` = 所有 Part 实体，`CATProduct` = 所有 Product 实体；`CATImplementClass` 第四参数必须与 `.dico` 第一列一致
- 菜单可以嵌套子菜单（`CATCmdContainer` 之间可以互相追加）
- `pMenu` 是从适配器借用的指针，**不要 Release**；Starter/Separator 挂到容器上后随容器销毁
- 命令模块和菜单模块建议分离到两个 `.m` 目录：命令实现 + Header 在 Addin 中创建，菜单 DataExtension 只负责布局和绑定 Header ID
- 完整调用链、生命周期规则、NLS/图标资源配置详见 `knowledge/ui/context_menu.md`
