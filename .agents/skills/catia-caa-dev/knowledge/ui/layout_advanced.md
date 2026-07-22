---
id: ui.layout_advanced
title: Advanced Layout Patterns
category: knowledge
domain: ui
keywords: [master-detail, dynamic form, tree nav, wizard, splitter, advanced layout]
apis: [CATDlgDialog, CATDlgTabContainer, CATStateCommand, CATDlgSplitter, CATDlgSelectorList]
requires: [ui.dialog, ui.dialog_layout]
patterns: [ui.master_detail, ui.dynamic_form, ui.wizard]
examples: []
release: [R19, R28]
tags: [ui, advanced, layout]
---

# CAA Advanced Layout Patterns

高级布局模式：列表-详情、动态表单、树形导航、向导。

## ⚠️ 重要修正

本文件曾使用以下**经核实不存在**的 API：`CATDlgTree`/`CATDlgTreeItem`（无对话框树控件）、`CATDlgFraSunkenFrame`/`CATDlgFraGroupFrame`（Frame 风格只有 NoTitle/NoFrame/NoMargin）、`CATDlgLstSingleSelection`/`CATDlgLstNoEdit`、两参 `SetGridConstraints` 与链式 `SetRow/SetColumn`、`CATDlgSplitterVertical`/`AttachLeft`/`SetMinimumSize`、`SetCurrentTab`、Combo `AddItem`。已全部修正为 B28 实证 API（修正明细见 [ui.dialog_layout](dialog_layout.md) 开头的对照表）。

---

## 1. 列表-详情模式 (Master-Detail)

左侧列表选择条目，右侧面板显示/编辑详情。

```
┌──────────────────────────────────────────────────┐
│ [Search: ________________] [🔍]                   │ ← 搜索栏
├──────────────────┬───────────────────────────────┤
│  SelectorList    │  Properties                   │ ← GroupBox
│  ┌──────────────┐│  ┌───────────────────────────┐│
│  │ Item 1       ││  │ Name:  [_______________]  ││
│  │ Item 2       ││  │ Type:  [Combo ▼]          ││
│  │ Item 3       ││  │ Length:[Spinner]  mm      ││
│  │ Item 4       ││  │ Width: [Spinner]  mm      ││
│  │              ││  └───────────────────────────┘│
│  └──────────────┘│                               │
│  [Add] [Remove]  │                               │
├──────────────────┴───────────────────────────────┤
│ Ready                                  [OK] [Cancel] │
└──────────────────────────────────────────────────┘
```

### 关键实现

```cpp
void ListDetailDlg::Build() {
    // --- 搜索栏 ---
    CATDlgFrame *pSearchFrame = new CATDlgFrame(this, "SearchF",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pSearchEditor = new CATDlgEditor(pSearchFrame, "SearchEdt");
    _pSearchBtn = new CATDlgPushButton(pSearchFrame, "SearchBtn");

    // --- 主内容区 ---
    CATDlgFrame *pMain = new CATDlgFrame(this, "MainF", CATDlgFraNoFrame);

    // 左侧: 列表（风格只用 NoFrame；单选不加风格位，多选才用 CATDlgLstMultisel）
    CATDlgFrame *pLeft = new CATDlgFrame(pMain, "LeftF",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pList = new CATDlgSelectorList(pLeft, "ItemList");
    _pList->SetGridConstraints(
        CATDlgGridConstraints(0, 0, 1, 2, CATGRID_4SIDES));
    _pAddBtn = new CATDlgPushButton(pLeft, "AddBtn");
    _pRemoveBtn = new CATDlgPushButton(pLeft, "RemoveBtn");

    // 右侧: 详情（默认 Frame 带标题栏 + SetTitle）
    CATDlgFrame *pRight = new CATDlgFrame(pMain, "RightF", CATDlgGridLayout);
    pRight->SetTitle(CATMsgCatalog::BuildMessage("ATCatalog", "AT_GROUP_PROPS"));
    int row = 0;

    CATDlgLabel *pNameLbl = new CATDlgLabel(pRight, "NmLbl");
    pNameLbl->SetGridConstraints(CATDlgGridConstraints(row, 0, 1, 1, CATGRID_RIGHT));
    _pNameEditor = new CATDlgEditor(pRight, "NmEdt");
    _pNameEditor->SetGridConstraints(CATDlgGridConstraints(row++, 1, 1, 1,
        CATGRID_LEFT | CATGRID_RIGHT));

    CATDlgLabel *pTypeLbl = new CATDlgLabel(pRight, "TpLbl");
    pTypeLbl->SetGridConstraints(CATDlgGridConstraints(row, 0, 1, 1, CATGRID_RIGHT));
    _pTypeCombo = new CATDlgCombo(pRight, "TpCbo");
    _pTypeCombo->SetGridConstraints(CATDlgGridConstraints(row++, 1, 1, 1,
        CATGRID_LEFT | CATGRID_RIGHT));

    // --- 按钮栏 ---
    CATDlgFrame *pBottom = new CATDlgFrame(this, "BottomF", CATDlgFraNoFrame);
    _pStatusLabel = new CATDlgLabel(pBottom, "Status");
    _pOKBtn = new CATDlgPushButton(pBottom, "OKBtn");
    _pCancelBtn = new CATDlgPushButton(pBottom, "CancelBtn");
}

// 选择联动：列表选中 → 更新右侧详情
// 注意：回调真实类型为 CATCommandMethod（void (CATBaseUnknown::*)(CATCommand*, CATNotification*, CATCommandClientData)），
// 无返回值，且不存在 CATCommandClientInfo 类型
void OnListSelectionChanged(CATCommand *iCmd,
    CATNotification *iNotif, CATCommandClientData iUsefulData) {
    int selCount = _pList->GetSelectCount();
    if (selCount > 0) {
        int *selArr = new int[selCount];
        _pList->GetSelect(selArr, selCount);
        ItemData data = _itemData[selArr[0]];
        delete [] selArr;
        _pNameEditor->SetText(data.name);
        _pTypeCombo->SetSelect(data.typeIndex);
        _pRemoveBtn->SetSensitivity(CATDlgEnable);
    } else {
        _pNameEditor->SetText("");
        _pRemoveBtn->SetSensitivity(CATDlgDisable);
    }
}
```

---

## 2. 动态布局 (Dynamic Form)

用户选择不同模式时，控件组显示/隐藏：

```
┌──────────────────────────────────────────┐
│ Mode: [Prefix ▼]                         │ ← Combo 切换
├──────────────────────────────────────────┤
│ ┌─ Prefix Options ──────────────────────┐│ ← 条件显示
│ │ Prefix Text: [______________]         ││
│ │ Case: (●) Upper  ( ) Lower  ( ) Keep ││
│ └───────────────────────────────────────┘│
│ ┌─ Numbering ───────────────────────────┐│ ← 始终显示
│ │ Start: [1]  Step: [1]  Digits: [3]    ││
│ └───────────────────────────────────────┘│
└──────────────────────────────────────────┘
```

### 关键实现

```cpp
void DynamicFormDlg::Build() {
    // Mode 切换
    _pModeCombo = new CATDlgCombo(pFrame, "ModeCbo");
    _pModeCombo->SetLine(CATUnicodeString("Prefix"), -1);
    _pModeCombo->SetLine(CATUnicodeString("Suffix"), -1);
    _pModeCombo->SetLine(CATUnicodeString("Replace"), -1);
    AddAnalyseNotificationCB(this, _pModeCombo->GetComboSelectNotification(),
        (CATCommandMethod)&DynamicFormDlg::OnModeChanged, NULL);

    // --- 动态面板组 ---

    // Prefix 面板（默认可见）：默认 Frame 带标题栏
    _pPrefixPanel = new CATDlgFrame(pFrame, "PrefixP", CATDlgGridLayout);
    _pPrefixPanel->SetTitle(CATMsgCatalog::BuildMessage("ATCatalog", "AT_GROUP_PREFIX"));
    _pPrefixEditor = new CATDlgEditor(_pPrefixPanel, "PrefEdt");
    _pUpperRB = new CATDlgRadioButton(_pPrefixPanel, "UpperRB");
    _pLowerRB = new CATDlgRadioButton(_pPrefixPanel, "LowerRB");

    // Suffix 面板（默认隐藏）
    _pSuffixPanel = new CATDlgFrame(pFrame, "SuffixP", CATDlgGridLayout);
    _pSuffixPanel->SetTitle(CATMsgCatalog::BuildMessage("ATCatalog", "AT_GROUP_SUFFIX"));
    _pSuffixPanel->SetVisibility(CATDlgHide);
    _pSuffixEditor = new CATDlgEditor(_pSuffixPanel, "SufEdt");

    // Replace 面板（默认隐藏）
    _pReplacePanel = new CATDlgFrame(pFrame, "ReplaceP", CATDlgGridLayout);
    _pReplacePanel->SetTitle(CATMsgCatalog::BuildMessage("ATCatalog", "AT_GROUP_REPLACE"));
    _pReplacePanel->SetVisibility(CATDlgHide);
    _pFindEditor = new CATDlgEditor(_pReplacePanel, "FindEdt");
    _pReplaceEditor = new CATDlgEditor(_pReplacePanel, "ReplEdt");
}

void DynamicFormDlg::OnModeChanged(CATCommand *iCmd,
    CATNotification *iNotif, CATCommandClientData iUsefulData) {
    int mode = _pModeCombo->GetSelect();

    // 全部隐藏
    _pPrefixPanel->SetVisibility(CATDlgHide);
    _pSuffixPanel->SetVisibility(CATDlgHide);
    _pReplacePanel->SetVisibility(CATDlgHide);

    // 显示对应面板
    switch (mode) {
        case 0: _pPrefixPanel->SetVisibility(CATDlgShow);  break;
        case 1: _pSuffixPanel->SetVisibility(CATDlgShow);  break;
        case 2: _pReplacePanel->SetVisibility(CATDlgShow); break;
    }
}
```

### 动态控件创建（高级）

```cpp
// 根据配置动态添加控件
void DynamicFormDlg::CreateDynamicControls() {
    // 先清除旧控件
    for (int i = 0; i < _dynamicEditors.Size(); i++) {
        _dynamicEditors[i]->RequestDelayedDestruction();
    }
    _dynamicEditors.Clear();

    // 根据用户配置创建新控件
    for (int i = 0; i < _config.fieldCount; i++) {
        CATDlgEditor *pEdt = new CATDlgEditor(_pDynamicPanel, "DynEdt");
        pEdt->SetGridConstraints(
            CATDlgGridConstraints(i, 0, 1, 1, CATGRID_4SIDES));
        _dynamicEditors.Append(pEdt);
    }
}
```

---

## 3. 树形导航模式

⚠️ **不存在 `CATDlgTree`/`CATDlgTreeItem`**——Dialog 框架没有树控件。CATIA 规格树的实现类是 `CATNavigBox`/`CATFrmNavigGraphicWindow`（CATIAApplicationFrame），不是可嵌入对话框的控件。

需要"左侧导航 + 右侧内容"时，**用 `CATDlgSelectorList` 模拟树**（层级用缩进文本表达），或直接用多页 `CATDlgTabContainer`：

```cpp
void TreeNavDlg::Build() {
    CATDlgFrame *pMain = new CATDlgFrame(this, "MainF", CATDlgFraNoFrame);

    // 左侧：用 SelectorList 模拟导航树（缩进表达层级）
    CATDlgFrame *pNavFrame = new CATDlgFrame(pMain, "NavF",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pNavList = new CATDlgSelectorList(pNavFrame, "NavList");
    _pNavList->SetGridConstraints(
        CATDlgGridConstraints(0, 0, 1, 1, CATGRID_4SIDES));

    _pNavList->SetLine(CATUnicodeString("General"), -1);
    _pNavList->SetLine(CATUnicodeString("    Display"), -1);
    _pNavList->SetLine(CATUnicodeString("    Units"), -1);
    _pNavList->SetLine(CATUnicodeString("Modeling"), -1);
    _pNavList->SetLine(CATUnicodeString("    Part Design"), -1);

    // 右侧：每个导航项一个 Tab 页（Frame 以 TabContainer 为父即自动成页）
    _pContentTabs = new CATDlgTabContainer(pMain, "ContentTabs");
    CATDlgFrame *pPage1 = new CATDlgFrame(_pContentTabs, "Page1", CATDlgGridLayout);
    CATDlgFrame *pPage2 = new CATDlgFrame(_pContentTabs, "Page2", CATDlgGridLayout);
    // ... 每页填充控件 ...

    // 绑定列表选中事件
    AddAnalyseNotificationCB(this, _pNavList->GetListSelectNotification(),
        (CATCommandMethod)&TreeNavDlg::OnNavSelection, NULL);
}

void TreeNavDlg::OnNavSelection(CATCommand *iCmd,
    CATNotification *iNotif, CATCommandClientData iUsefulData) {
    int count = _pNavList->GetSelectCount();
    if (count < 1) return;
    int *selArr = new int[count];
    _pNavList->GetSelect(selArr, count);
    _pContentTabs->SetSelectedPage(selArr[0]);   // 真实方法：SetSelectedPage
    delete [] selArr;
}
```

---

## 4. 向导模式 (Wizard)

多步骤向导，通过 Back/Next 按钮切换页面：

```
┌──────────────────────────────────────────────┐
│ Wizard: Export Configuration                  │
│ Step 1 of 3: Select Format                   │
├──────────────────────────────────────────────┤
│                                              │
│  Select export format:                       │
│  (●) STEP                                    │
│  ( ) IGES                                    │
│  ( ) STL                                     │
│  ( ) CSV                                     │
│                                              │
├──────────────────────────────────────────────┤
│                          [Cancel]  [Next →]  │
└──────────────────────────────────────────────┘
```

### 关键实现

```cpp
// 在 Command 中用状态机 + 多 Panel 实现向导
void ExportWizardCmd::BuildGraph() {
    // State 1: Welcome
    CATDialogState *pState1 = GetInitialState("Step1_SelectFormat");
    _pDlg->ShowPanel(0);  // Panel 0 = Format selection

    // State 2: Options
    CATDialogState *pState2 = AddDialogState("Step2_Options");

    // State 3: Confirm
    CATDialogState *pState3 = AddDialogState("Step3_Confirm");

    // 转换: Next 按钮
    AddTransition(pState1, pState2,
        AndCondition(
            IsOutputSetCondition(_pDlg->GetNextNotification()),
            Condition((ConditionMethod)&ExportWizardCmd::IsStep1Valid)
        ),
        Action((ActionMethod)&ExportWizardCmd::OnStep1ToStep2)
    );

    AddTransition(pState2, pState3,
        IsOutputSetCondition(_pDlg->GetNextNotification()),
        Action((ActionMethod)&ExportWizardCmd::OnStep2ToStep3));

    // Back 按钮
    AddTransition(pState2, pState1,
        IsOutputSetCondition(_pDlg->GetBackNotification()),
        Action((ActionMethod)&ExportWizardCmd::OnStep2ToStep1));
}

// Dialog 端：多 Panel 切换
void WizardDlg::ShowPanel(int index) {
    for (int i = 0; i < _panels.Size(); i++) {
        _panels[i]->SetVisibility(i == index ? CATDlgShow : CATDlgHide);
    }
    _pBackBtn->SetSensitivity(index > 0 ? CATDlgEnable : CATDlgDisable);
    _pNextBtn->SetTitle(index == _panels.Size() - 1 ? "Finish" : "Next →");
    _pStepLabel->SetTitle(BuildStepText(index + 1, _panels.Size()));
}
```

---

## 5. 可伸缩分隔面板 (Splitter)

`CATDlgSplitter` 真实存在，构造 `(parent, name, style)`；**子面板以 splitter 为父创建即自动挂接**（无 `AttachLeft/AttachRight`），分隔条位置用 `Get/SetSashPosition(double)`，`SwitchChildren()` 交换两 pane。无 `SetMinimumSize`、`CATDlgSplitterVertical` 经核实不存在（方向由布局决定）：

```cpp
CATDlgSplitter *pSplitter = new CATDlgSplitter(pMain, "Splitter");

// 左侧面板（以 splitter 为父，自动成为第 1 个 pane）
CATDlgFrame *pLeftPane = new CATDlgFrame(pSplitter, "LeftPane",
    CATDlgFraNoFrame | CATDlgGridLayout);

// 右侧面板（自动成为第 2 个 pane）
CATDlgFrame *pRightPane = new CATDlgFrame(pSplitter, "RightPane",
    CATDlgFraNoFrame | CATDlgGridLayout);

pSplitter->SetSashPosition(0.3);   // 分隔条在 30% 处
```

---

## AI 生成规则

- [ ] 列表-详情: 左侧 `CATDlgSelectorList` + 右侧带标题 `CATDlgFrame`
- [ ] 动态表单: Combo 切换 → `SetVisibility` 控制面板
- [ ] 树形导航: **无 CATDlgTree**——用 SelectorList 缩进模拟 + `CATDlgTabContainer` 换页
- [ ] 向导: `CATStateCommand` 状态机 + Dialog `ShowPanel(n)`
- [ ] 可伸缩: `CATDlgSplitter` + `SetSashPosition`（子面板以 splitter 为父自动挂接）
- [ ] 动态控件用 `RequestDelayedDestruction()` 清理
- [ ] 所有面板切换必须在 `Build()` 中预创建，运行时只切换可见性
- [ ] 面板过多（>5）考虑用树形导航或 Tab 页替代直接堆叠
