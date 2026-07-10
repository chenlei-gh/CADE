---
id: pb.create_context_menu
title: Create Context Menu / 创建右键菜单
category: playbook
domain: ui
keywords: [context menu, right click, CATIContextualMenu, CATExtIContextualMenu, CATCmdStarter, DataExtension]
capabilities: [cap.selection]
apis: [CATIContextualMenu, CATExtIContextualMenu, CATCmdStarter, CATISpecObject]
frameworks: [ApplicationFrame, ObjectModelerBase]
difficulty: intermediate
effort: small
release: [R19, R28]
tags: [playbook, context_menu, ui]
---
# Create Context Menu (创建右键菜单)

为 CATIA Feature 或 Product 添加右键菜单项，点击后触发自定义命令。

## 目标

在特征树或 3D 视图中右键点击某类对象时，显示自定义菜单项。

## 实现步骤

1. **创建 DataExtension** → 继承 CATExtIContextualMenu
2. **创建 CmdStarter** → 继承 CATCmdStarter，实现命令启动
3. **注册菜单项** → 在 DataExtension 中定义菜单结构
4. **字典注册** → 在 Framework.dico 中注册 DataExtension

## 关键代码骨架

```cpp
// DataExtension — 提供菜单项
class MyContextMenu : public CATExtIContextualMenu {
    CATDeclareClass;

    void GetContextualMenu(CATCmdContainer *iContainer) {
        // 创建菜单
        CATCmdStarter *pStarter = new MyCmdStarter("Export BOM", ...);
        iContainer->AddCommand(pStarter);
    }
};

// CmdStarter — 点击后执行
class MyCmdStarter : public CATCmdStarter {
    CATDeclareClass;

    HRESULT StartCommand() {
        // 获取当前选中对象
        CATISpecObject_var spSelected = GetSelectedObject();
        // 启动命令...
        return S_OK;
    }
};
```

## Dictionary 注册

```text
MyModule.MyContextMenu  libMyModule  CATExtIContextualMenu  CATPart
```

## 注意事项

- DataExtension 的 `target_object` 决定菜单在哪些对象上显示
- `CATPart` = 所有 Part 实体，`CATProduct` = 所有 Product 实体
- 菜单可以嵌套子菜单
- 命令启动后 DataExtension 生命周期由 CATIA 管理
