---
id: ui.toolbar
title: Toolbar / CommandHeader / CATIAfrGeneralWksAddin
category: knowledge
domain: ui
keywords: [toolbar, CATCommandHeader, CATCmdAccess, CATCmdContainer, catalog, workbench, addin, command registration, CATIAfrGeneralWksAddin, MacDeclareHeader]
apis: [CATCommandHeader, CATCmdAccess, CATCmdContainer, CATCmdStarter, MacDeclareHeader, MacImplementHeader]
requires: [infra.selection]
patterns: []
examples: []
release: [R19, R28]
tags: [ui, command, registration, addin]
---

# CATIAfrGeneralWksAddin 命令注册（官方模式）

**⚠️ 关键约束：CommandHeader 类必须用 `MacDeclareHeader` 宏生成，且必须在 .cpp 文件中使用（不能在 .h 文件）。**

## 官方原始示例

参考：`CAADoc/CAAApplicationFrame.edu/CAAAfrGeneralWksAddin.m/src/CAAAfrGeneralWksAdn.cpp`

## 正确代码模板

### Addin.cpp（同一个 .cpp 文件，不需要单独 .h）

```cpp
#include "TTModuleAddin.h"
#include "CATIAfrGeneralWksAddin.h"
#include "CATCreateWorkshop.h"

// ⭐ 关键：MacDeclareHeader 必须在 .cpp 中使用！
#include "CATCommandHeader.h"
MacDeclareHeader(QuickCmdHdr);

CATImplementClass(TTModuleAddin,DataExtension,CATBaseUnknown,TTModuleAddin);

TIE_CATIAfrGeneralWksAddin(TTModuleAddin);

void TTModuleAddin::CreateCommands()
{
    // ⭐ 必须用 4 参数构造 (HeaderID, LoadName, ClassName, Argument)
    new QuickCmdHdr(
        "TTModule.QuickCmd",   // HeaderID
        "TTModule",             // LoadName — StartCommand() 定位 DLL
        "QuickCmd",             // ClassName
        (void*)NULL             // Argument
    );
}

CATCmdContainer* TTModuleAddin::CreateToolbars()
{
    NewAccess(CATCmdContainer, pToolbar, TTModuleTlb);
    AddToolbarView(pToolbar, 1, Right);

    NewAccess(CATCmdStarter, pCmd, QuickCmd);
    SetAccessCommand(pCmd, "TTModule.QuickCmd");
    SetAccessChild(pToolbar, pCmd);

    return pToolbar;
}
```

## 为什么不能在 .h 中使用 MacDeclareHeader

```
MacDeclareHeader = MacDefineHeader (类声明)
                 + MacImplementHeader (方法实现)

放在 .h → 每个 .cpp include 它 → 链接器报"重复定义"
放在 .cpp → 只有一次声明和实现 → 正确
```

## 为什么不能用 CATImplementHeaderResources 代替

```cpp
// ❌ 错误：只实现 GetFW() 和 GetResourceFile()，不声明类！
CATImplementHeaderResources(QuickCmdHdr, CATCommandHeader, QuickCmdHdr);

// ✅ 正确：完整声明类 + 实现所有构造函数
MacDeclareHeader(QuickCmdHdr);
```

## 为什么必须用 4 参数构造

`CATCommandHeader::StartCommand()` 使用 LoadName 定位 DLL、使用 ClassName 创建命令实例。单参数构造缺少这两项 → 命令无法创建。

## 按钮不显示排查清单

1. ☐ `MacDeclareHeader` 在 .cpp 中？（不能在 .h 中）
2. ☐ 4 参数构造？(HeaderID, LoadName, ClassName, Argument)
3. ☐ `win_b64/code/dictionary/` 有 .dico 文件？
4. ☐ `win_b64/resources/msgcatalog/` 有 .CATRsc + .CATNls？
5. ☐ `win_b64/resources/graphic/icons/normal/` 有图标 .bmp？
6. ☐ CNEXT 启动时 `CATDictionaryPath` 指向 Runtime View？
7. ☐ Dictioanry 内容：`TTModuleAddin CATIAfrGeneralWksAddin libTTModule`
