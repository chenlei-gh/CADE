---
id: ui.dialog
title: Dialog
category: knowledge
domain: ui
keywords: [dialog, CATDlgDialog, CATDlgFrame, CATDlgPushButton, CATDlgEditor, CATDlgCombo, CATDlgSelectorList, CATDlgLabel, GUI, listview]
apis: [CATDlgDialog, CATDlgFrame, CATDlgPushButton, CATDlgEditor, CATDlgCombo, CATDlgSelectorList, CATDlgLabel, CATDlgTableView]
requires: []
patterns: [ui.result_dialog]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [ui, dialog, gui]
---

# Dialog (对话框)

CAA 对话框通过 `CATDlgDialog` 及相关控件构建，布局用 Grid 风格 + `CATDlgGridConstraints`。

## ⚠️ 重要修正

之前版本引用的 `CATDlgList` 经核实**不存在**。真实的列表控件是 `CATDlgSelectorList`（简单多选列表）和 `CATDlgTableView`（多列表格，CATIAApplicationFrame）。所有控件构造签名统一为 `(CATDialog* iParent, const CATString& iName, CATDlgStyle iStyle=NULL)`——**没有标题/文本参数**，显示文本来自 NLS 资源（.CATNls，按控件名索引）或继承自 `CATDialog::SetTitle()`。

## 核心控件

| 控件 | 类 | 用途 |
|------|-----|------|
| 对话框 | `CATDlgDialog` | 对话框容器（自带 OK/CANCEL 等标准按钮风格位） |
| 框架 | `CATDlgFrame` | 分组/布局容器 |
| 按钮 | `CATDlgPushButton` | 普通按钮 |
| 文本框 | `CATDlgEditor` | 单行文本输入 |
| 下拉框 | `CATDlgCombo` | 下拉选择/可编辑输入 |
| 列表 | `CATDlgSelectorList` | 多行列表（单选/多选） |
| 表格 | `CATDlgTableView` | 多列表格（CATIAApplicationFrame） |
| 标签 | `CATDlgLabel` | 文本标签 |
| 复选框 | `CATDlgCheckButton` | 勾选 |
| 单选按钮 | `CATDlgRadioButton` | 单选项 |
| Tab 容器 | `CATDlgTabContainer` | 多页签 |
| 文件选择 | `CATDlgFile` | 打开/保存文件对话框 |
| 数字微调 | `CATDlgSpinner` | 数值输入 |
| 进度条 | `CATDlgProgress` | 进度显示（**注意：不叫 CATDlgProgressBar**） |

## 基本用法

```cpp
// 创建对话框：第1参是父对象，第2参是控件名（NLS 键），第3参是风格位
CATDlgDialog* pDlg = new CATDlgDialog(
    this,                    // 父 CATDialog（通常是 Command）
    "CheckerDlg",            // 控件名 → NLS 键
    CATDlgWndModal | CATDlgWndOK | CATDlgWndCANCEL  // 模态 + 标准按钮
);

// 创建列表（真实类是 CATDlgSelectorList）
CATDlgSelectorList* pList = new CATDlgSelectorList(pDlg, "ResultList");

// 创建按钮
CATDlgPushButton* pApply = new CATDlgPushButton(pDlg, "ApplyBtn");
```

NLS 文件（`CNext/resources/msgcatalog/xxx.CATNls`）按控件名提供显示文本：

```
CheckerDlg.Title     = "Check Results";
ApplyBtn.Title       = "Apply";
ResultList.Title     = "Failed Features";
```

## 布局示例

```cpp
// Frame 容器：CATDlgFraNoFrame 去边框，CATDlgGridLayout 启用网格布局
CATDlgFrame* pFrame = new CATDlgFrame(pDlg, "ResultFrame",
    CATDlgFraNoFrame | CATDlgGridLayout);

// 控件放入网格：SetGridConstraints 只收 1 个参数
CATDlgSelectorList* pList = new CATDlgSelectorList(pFrame, "ResultList");
pList->SetGridConstraints(CATDlgGridConstraints(0, 0, 1, 1, CATGRID_4SIDES));

CATDlgPushButton* pBtn = new CATDlgPushButton(pDlg, "CloseBtn");
pBtn->SetGridConstraints(CATDlgGridConstraints(1, 0, 1, 1, CATGRID_RIGHT));
```

## 常用操作

| 场景 | 方式 |
|------|------|
| 显示对话框 | `pDlg->SetVisibility(CATDlgShow)` |
| 设置列表项 | `pList->SetLine(CATUnicodeString, index=-1)`（追加） |
| 获取选中行 | `pList->GetSelect(int* oRows, int iSize)`（调用方提供数组） |
| 选中数量 | `pList->GetSelectCount()` |
| 清空列表 | `pList->ClearLine()` |
| 读文本框 | `pEditor->GetText()` → `CATUnicodeString&` |
| 写文本框 | `pEditor->SetText(const CATUnicodeString&)` |
| 下拉框加项 | `pCombo->SetLine(CATUnicodeString, index=-1)` |
| 下拉框选中 | `pCombo->GetSelect()` → int（-1 未选） |
| 启用/禁用 | `pWidget->SetSensitivity(CATDlgEnable/CATDlgDisable)` |
| 设显示文本 | `pWidget->SetTitle(const CATUnicodeString&)` |
| 按钮回调 | `AddAnalyseNotificationCB(pBtn, pBtn->GetPushBActivateNotification(), ...)` |

## 事件通知

每个控件提供 `GetXxxNotification()` 工厂方法返回通知对象，用 `AddAnalyseNotificationCB` 挂回调：

```cpp
AddAnalyseNotificationCB(pApply, pApply->GetPushBActivateNotification(),
    (CATCommandMethod)&MyCmd::OnApply, NULL);
// CATDlgDialog 自身: GetDiaOKNotification / GetDiaCANCELNotification / ...
```

## 参考样例

- 表格控件：`CAACATIAApplicationFrm.edu/CAACafDlgView.m/src/SampleListEditor.cpp`
