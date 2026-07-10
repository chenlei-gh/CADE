---
id: ui.context_menu
title: Context Menu (右键菜单)
category: knowledge
domain: ui
keywords: [context menu, right click, CATIContextualMenu, CATExtIContextualMenu, CATCmdStarter, CATCmdSeparator, NewAccess, SetAccessCommand]
apis: [CATIContextualMenu, CATExtIContextualMenu, CATCmdStarter, CATCmdSeparator, CATCmdContainer]
requires: [ui.dialog, ui.toolbar]
patterns: [ui.context_menu_pattern]
examples: []
release: [R19, R28]
tags: [ui, context-menu, data-extension]
---

# CAA Context Menu (右键菜单)

为指定类型对象追加右键菜单项。链路：`CATIContextualMenu → DataExtension → CATCmdStarter → Command Header → Command`。

## 调用链

```
用户右键对象 → CATIA 查询 CATIContextualMenu → .dico 定位 DataExtension
→ CATExtIContextualMenu 提供默认菜单 → DataExtension 追加 CATCmdStarter
→ CATCmdStarter 通过 Header ID 绑定 CATCommandHeader → 用户点击 → 启动 Command
```

## 四个角色

| 角色 | 类型 | 职责 |
|------|------|------|
| 目标对象 | 业务 LateType | 用户右键的对象 |
| 菜单扩展 | `CATIContextualMenu` / `CATExtIContextualMenu` | 取默认菜单并追加项目 |
| 菜单入口 | `CATCmdStarter` | 菜单中一个可点击项 |
| 命令本体 | `CATCommandHeader` + `CATCommand` | 执行实际业务 |

## 核心约束

1. **必须继承 `CATExtIContextualMenu` 适配器**，不能用 BOA
2. **用 `TIE_CATIContextualMenu` 暴露接口**
3. **以 DataExtension 方式挂载**（不是 Implementation）
4. **构造时取默认菜单、追加 Starter**，不重写 `GetContextualMenu()`
5. **不要手动释放菜单容器**，由适配器管理

## DataExtension 头文件

```cpp
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
```

## DataExtension 实现文件

```cpp
// MyObjContextualMenu.cpp
#include "MyObjContextualMenu.h"
#include "CATCreateWorkshop.h"

// ⚠️ 第四个参数 = 目标对象的 LateType
CATImplementClass(
    MyObjContextualMenu,
    DataExtension,              // 不是 Implementation！
    CATBaseUnknown,
    TargetLateType);            // 被右键的目标类型

#include "TIE_CATIContextualMenu.h"
TIE_CATIContextualMenu(MyObjContextualMenu);

MyObjContextualMenu::MyObjContextualMenu()
{
    CATCmdContainer *pMenu = NULL;
    HRESULT hr = CATExtIContextualMenu::GetContextualMenu(pMenu);
    if (SUCCEEDED(hr) && NULL != pMenu) {
        // 分隔线
        NewAccess(CATCmdSeparator, pSeparator, MyObjCtxSep);
        // 菜单项
        NewAccess(CATCmdStarter, pStarter, MyObjInspectCtx);
        SetAccessCommand(pStarter, "MyObjInspectHdr");
        // 串联
        SetAccessNext(pSeparator, pStarter);
        AddAccessChild(pMenu, pSeparator);
    }
}

MyObjContextualMenu::~MyObjContextualMenu() {}
```

## 关键 API

| API | 作用 |
|-----|------|
| `CATExtIContextualMenu::GetContextualMenu(pMenu)` | 取得默认菜单（借用指针，不 Release） |
| `NewAccess(CATCmdSeparator, ...)` | 创建分隔符 |
| `NewAccess(CATCmdStarter, ...)` | 创建菜单项 |
| `SetAccessCommand(pStarter, "HeaderID")` | 绑定到已注册的 Command Header |
| `SetAccessNext(a, b)` | 串联访问节点（a → b） |
| `AddAccessChild(pMenu, pStarter)` | 追加到菜单末尾 |

## interface dictionary 绑定

在 framework 级 `.dico` 文件中：

```
TargetLateType CATIContextualMenu libMyObjContextualMenu
```

| 列 | 含义 | 必须一致 |
|----|------|---------|
| `TargetLateType` | 目标对象类型 | = `CATImplementClass` 第四参数 |
| `CATIContextualMenu` | 查询的接口 | 固定 |
| `libMyObjContextualMenu` | 承载 DLL | = 模块的共享库名 |

## 多模块拆分（推荐）

```
MyCommands.m/         ← 命令实现 + Command Header（在 Addin 中创建）
MyContextualMenu.m/   ← 菜单 DataExtension（只负责布局 + Header ID 绑定）
```

**不要在菜单 DataExtension 中创建 Command Header**。Header 应由 Workshop Addin 统一管理。

## 生命周期

- `pMenu` → 从适配器取的借用指针，**不 Release**
- Starter/Separator → 挂到菜单容器上，**随容器销毁**
- Command Header → 由 Editor 管理，**不由菜单释放**
- DataExtension → 随目标对象创建/销毁

## NLS 资源

右键菜单标题来自 **Header 的 NLS 资源**（不是 Command 的）：

```
# MyCommandHeader.CATNls
MyCommandHeader.MyInspectHdr.Title  = "Inspect Object";
MyCommandHeader.MyInspectHdr.ShortHelp = "Inspect the selected object";
```

图标：

```
# MyCommandHeader.CATRsc
MyCommandHeader.MyInspectHdr.Icon.Normal = "I_MyInspect";
```

## Imakefile.mk

```
BUILT_OBJECT_TYPE = SHARED LIBRARY
LINK_WITH = CATIAApplicationFrame \     # CATIContextualMenu
            CATApplicationFrame  \      # CATCmdContainer, CATCmdStarter
            JS0GROUP
```

---

## AI 生成规则

- [ ] 继承 `CATExtIContextualMenu`（不是 `CATBaseUnknown`）
- [ ] 用 `CATImplementClass(..., DataExtension, ..., TargetLateType)`
- [ ] 构造中取默认菜单、追加 Starter
- [ ] `SetAccessCommand` 的 Header ID 必须和 Addin 中创建的一致
- [ ] .dico 中第三列 = DLL 名（不含 lib 前缀和扩展名）
- [ ] 命令模块和菜单模块分离
- [ ] 不在 DataExtension 中释放菜单容器
