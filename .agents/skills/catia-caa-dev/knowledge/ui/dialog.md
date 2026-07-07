---
id: ui.dialog
title: Dialog
category: knowledge
domain: ui
keywords: [dialog, CATDlgDialog, CATDlgFrame, CATDlgPushButton, CATDlgEditor, CATDlgCombo, CATDlgList, CATDlgLabel, GUI, listview]
apis: [CATDlgDialog, CATDlgFrame, CATDlgPushButton, CATDlgEditor, CATDlgCombo, CATDlgList, CATDlgLabel]
requires: []
patterns: [ui.result_dialog]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [ui, dialog, gui]
---

# Dialog (对话框)

CAA 对话框通过 `CATDlgDialog` 及相关控件构建。

## 核心控件

| 控件 | 类 | 用途 |
|------|-----|------|
| 对话框 | `CATDlgDialog` | 对话框容器 |
| 框架 | `CATDlgFrame` | 分组容器 |
| 按钮 | `CATDlgPushButton` | 普通按钮 |
| 文本框 | `CATDlgEditor` | 单行文本输入 |
| 下拉框 | `CATDlgCombo` | 下拉选择 |
| 列表 | `CATDlgList` | 多行列表 |
| 标签 | `CATDlgLabel` | 文本标签 |
| 复选框 | `CATDlgCheckButton` | 勾选 |
| 单选按钮 | `CATDlgRadioButton` | 单选项 |
| 选择器 | `CATDlgSelectorList` | Feature 选择 |

## 基本用法

```cpp
// 创建对话框
CATDlgDialog* pDlg = new CATDlgDialog(
    "CheckerDlg",          // Dialog ID
    CATDlgWndModal,         // 模态
    CATDlgGridLayout        // Grid 布局
);

// 创建 ListView
CATDlgList* pList = new CATDlgList(pDlg, "ResultList");

// 创建按钮
CATDlgPushButton* pOK = new CATDlgPushButton(pDlg, "OK");
CATDlgPushButton* pCancel = new CATDlgPushButton(pDlg, "Cancel");
```

## 布局示例

```cpp
CATDlgDialog* pDlg = ...;

// Frame 容器
CATDlgFrame* pFrame = new CATDlgFrame(pDlg, "ResultFrame");

// List 在 Frame 中
CATDlgList* pList = new CATDlgList(pFrame, "ResultList");

// Button 在对话框底部
CATDlgPushButton* pBtn = new CATDlgPushButton(pDlg, "Close");
```

## 常用操作

| 场景 | 方式 |
|------|------|
| 显示对话框 | `pDlg->SetVisibility(CATDlgShow)` |
| 设置列表项 | `pList->SetLine(int, char**, int)` |
| 获取选中行 | `pList->GetSelect(&line)` |
| 清空列表 | `pList->ClearLine()` |
| 双击回调 | 实现 `CATDlgListNotification` |
