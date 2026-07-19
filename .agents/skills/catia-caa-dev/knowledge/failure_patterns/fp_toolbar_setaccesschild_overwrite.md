---
id: fp.toolbar_setaccesschild_overwrite
title: SetAccessChild Overwrite / 多命令挂同一工具栏只有最后一个可点击
category: knowledge
domain: failure_patterns
severity: runtime_error
apis: [CATCmdContainer, CATCmdStarter, SetAccessChild, SetAccessNext]
frameworks: [ApplicationFrame]
keywords: [toolbar, SetAccessChild, SetAccessNext, CreateToolbars, overwrite, only last button works]
tags: [failure_pattern, runtime, ui, toolbar]
release: [R19, R28]
---
# SetAccessChild Overwrite / 多命令挂同一工具栏只有最后一个可点击

## 症状

一个工具栏上放了多个命令按钮，图标都能正常显示，但点击时只有**最后添加的那一个**按钮有响应，前面的按钮点击后完全没有反应（不报错、GetState 也不会被调用）。

## 原因

`CreateToolbars()` 里对每个命令都调用了 `SetAccessChild(pToolbar, pCmd)`：

```cpp
// ❌ 错误：SetAccessChild 每次调用都覆盖前一个子节点
CATCmdContainer* MyAddin::CreateToolbars()
{
    NewAccess(CATCmdContainer, pToolbar, MyModuleTlb);
    AddToolbarView(pToolbar, 1, Right);

    NewAccess(CATCmdStarter, pCmd1, FirstCmd);
    SetAccessCommand(pCmd1, "MyModule.FirstCmd");
    SetAccessChild(pToolbar, pCmd1);   // 设置唯一子节点为 pCmd1

    NewAccess(CATCmdStarter, pCmd2, SecondCmd);
    SetAccessCommand(pCmd2, "MyModule.SecondCmd");
    SetAccessChild(pToolbar, pCmd2);   // ← 覆盖！pCmd1 从工具栏的访问链上被摘掉

    return pToolbar;
}
```

`SetAccessChild(container, child)` 语义是"设置 container 的唯一子节点"，不是"追加子节点"。第二次调用会把 `pToolbar` 的子节点指针从 `pCmd1` 改为 `pCmd2`，`pCmd1` 虽然图标资源仍能正常渲染（图标由 Dictionary/资源系统单独驱动），但已经不在工具栏的命令访问链上，因此点击无效。

## 修复

第一个 Starter 用 `SetAccessChild`，之后每个新增的 Starter 改用 `SetAccessNext(prev, new)` 链接成单链表：

```cpp
// ✅ 正确：SetAccessChild 只调一次，后续用 SetAccessNext 链接
CATCmdContainer* MyAddin::CreateToolbars()
{
    NewAccess(CATCmdContainer, pToolbar, MyModuleTlb);
    AddToolbarView(pToolbar, 1, Right);

    NewAccess(CATCmdStarter, pCmd1, FirstCmd);
    SetAccessCommand(pCmd1, "MyModule.FirstCmd");
    SetAccessChild(pToolbar, pCmd1);      // 第一个：设为子节点

    NewAccess(CATCmdStarter, pCmd2, SecondCmd);
    SetAccessCommand(pCmd2, "MyModule.SecondCmd");
    SetAccessNext(pCmd1, pCmd2);          // 第二个起：链接到前一个

    NewAccess(CATCmdStarter, pCmd3, ThirdCmd);
    SetAccessCommand(pCmd3, "MyModule.ThirdCmd");
    SetAccessNext(pCmd2, pCmd3);          // 依次链接

    return pToolbar;
}
```

参考官方样例：`CAADoc/CAAApplicationFrame.edu/CAAAfrGeometryWshop.m/src/CAAAfrGeometryWks.cpp`——多命令场景一律用 `SetAccessNext` 串联，`SetAccessChild` 全程只调用一次。

## 预防规则

- [ ] 一个 `CATCmdContainer`（工具栏/菜单）上 `SetAccessChild` 全程只能调用一次（挂第一个 Starter）
- [ ] 第 2 个及以后的 Starter 必须用 `SetAccessNext(前一个, 新的)` 链接
- [ ] 排查"工具栏图标都显示但只有部分能点"时，第一步检查是否误用了多次 `SetAccessChild`
- [ ] 生成器批量生成多命令模板时，必须自动切换为链式 `SetAccessNext` 而不是重复 `SetAccessChild`

## 相关

- [toolbar.md](../ui/toolbar.md) — 命令注册基础模式
