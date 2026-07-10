---
id: ui.context_menu_pattern
title: Context Menu Pattern
category: pattern
domain: ui
keywords: [context menu, right click, CATIContextualMenu, DataExtension, CATCmdStarter, NewAccess]
apis: [CATIContextualMenu, CATExtIContextualMenu, CATCmdStarter, CATCmdContainer]
requires: [ui.context_menu, ui.toolbar]
patterns: []
examples: []
release: [R19, R28]
tags: [pattern, ui, context-menu]
---

# Context Menu Pattern (右键菜单模式)

为指定类型对象追加右键菜单项。推荐拆分为两个模块：命令模块 + 菜单模块。

## 适用场景

- 为特定 Feature 类型添加自定义右键菜单
- 在 CATPart/CATProduct 特征树上加右键操作
- 在 3D 视图对象上右键触发自定义命令


## 完整实现

### 模块 1：MyCtxMenuModule.m（菜单 DataExtension）

**LocalInterfaces/MyObjCtxMenu.h**：

```cpp
#include "CATExtIContextualMenu.h"

class MyObjCtxMenu : public CATExtIContextualMenu {
    CATDeclareClass;
public:
    MyObjCtxMenu();
    virtual ~MyObjCtxMenu();
private:
    MyObjCtxMenu(const MyObjCtxMenu &);
    MyObjCtxMenu &operator=(const MyObjCtxMenu &);
};
```

**src/MyObjCtxMenu.cpp**：

```cpp
#include "MyObjCtxMenu.h"
#include "CATCreateWorkshop.h"

CATImplementClass(MyObjCtxMenu, DataExtension, CATBaseUnknown, MyTargetType);
#include "TIE_CATIContextualMenu.h"
TIE_CATIContextualMenu(MyObjCtxMenu);

MyObjCtxMenu::MyObjCtxMenu()
{
    CATCmdContainer *pMenu = NULL;
    if (SUCCEEDED(CATExtIContextualMenu::GetContextualMenu(pMenu))
        && NULL != pMenu)
    {
        NewAccess(CATCmdSeparator, pSep, MyObjCtxSep);
        NewAccess(CATCmdStarter, pStarter, MyObjCtxStr);
        SetAccessCommand(pStarter, "MyObjInspectHdr");  // ← 跨文件 ID
        SetAccessNext(pSep, pStarter);
        AddAccessChild(pMenu, pSep);
    }
}

MyObjCtxMenu::~MyObjCtxMenu() {}
```

**Imakefile.mk**：

```makefile
BUILT_OBJECT_TYPE = SHARED LIBRARY
LINK_WITH = CATIAApplicationFrame \
            CATApplicationFrame  \
            JS0GROUP
```

### 模块 2：MyCommands.m（命令 + Header）

**LocalInterfaces/MyInspectCmd.h** + **MyCommandHeader.h**：

```cpp
// MyCommandHeader.h
#include "CATCommandHeader.h"
MacDeclareHeader(MyCommandHeader);
```

**Addin 中创建 Header**（`CreateCommands()`）：

```cpp
#include "MyCommandHeader.h"

void MyWorkshopAddin::CreateCommands()
{
    // 创建 Header — 关键：ID 必须和 DataExtension 中一致
    new MyCommandHeader(
        "MyObjInspectHdr",           // ← 跨文件 ID
        "MyCommands",                // DLL 名
        "MyInspectCmd",              // 命令类名
        (void *)NULL);
}
```

### Framework 级 .dico

```
MyTargetType CATIContextualMenu libMyCtxMenuModule
```

### 资源文件

**MyCommandHeader.CATNls**：

```
MyCommandHeader.MyObjInspectHdr.Title  = "Inspect Object";
MyCommandHeader.MyObjInspectHdr.ShortHelp = "Inspect the selected object";
```

**MyCommandHeader.CATRsc**：

```
MyCommandHeader.MyObjInspectHdr.Icon.Normal = "I_MyInspect";
```

---

## 跨文件 ID 对照表

| 文件 | 标识符 | 说明 |
|------|--------|------|
| `MyObjCtxMenu.cpp` | `"MyObjInspectHdr"` | `SetAccessCommand` 的第二个参数 |
| `MyWorkshopAddin.cpp` | `"MyObjInspectHdr"` | `new MyCommandHeader(...)` 的第一个参数 |
| `MyCommandHeader.CATNls` | `MyCommandHeader.MyObjInspectHdr.Title` | 类名.头ID.Title |
| `MyCommandHeader.CATRsc` | `MyCommandHeader.MyObjInspectHdr.Icon` | 类名.头ID.Icon |

> ⚠️ 这 4 处必须完全一致。建议用 `cade diagnose` 做完整性检查。

---

## 常见问题

**菜单不显示**：
1. `.dico` 中 LateType 是否正确
2. Header ID 是否和 `SetAccessCommand` 一致
3. 当前 Workshop 是否已加载 Command Header

**点击后不执行**：
1. Command 类是否正确实现
2. DLL 是否正确编译到 Runtime View

**重复实现冲突**：
- 同一个 LateType 只能有一个 `CATIContextualMenu` 实现
- 扩展 DS 原生对象前，先确认是否已有实现

---

## AI 生成规则

- [ ] 拆分为两个模块：命令模块 + 菜单模块
- [ ] DataExtension 继承 `CATExtIContextualMenu`
- [ ] `CATImplementClass` 第四个参数 = 目标 LateType
- [ ] Header ID 在 DataExtension 和 Addin 中保持一致
- [ ] .dico 中绑定 LateType → CATIContextualMenu → DLL
- [ ] NLS 资源属于 Header 类，不是 Command 类
- [ ] 不在菜单构造中创建 Command Header
