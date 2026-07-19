---
id: ui.layout_advanced
title: Advanced Layout Patterns
category: knowledge
domain: ui
keywords: [master-detail, dynamic form, tree nav, wizard, splitter, advanced layout]
apis: [CATDlgDialog, CATDlgTree, CATStateCommand, CATDlgSplitter, CATDlgTabContainer]
requires: [ui.dialog, ui.dialog_layout]
patterns: [ui.master_detail, ui.dynamic_form, ui.wizard]
examples: []
release: [R19, R28]
tags: [ui, advanced, layout]
---

# CAA Advanced Layout Patterns

高级布局模式：列表-详情、动态表单、树形导航、向导。

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
    _pSearchBtn = new CATDlgPushButton(pSearchFrame, "SearchBtn", "🔍");

    // --- 主内容区 ---
    CATDlgFrame *pMain = new CATDlgFrame(this, "MainF", CATDlgFraNoFrame);

    // 左侧: 列表
    CATDlgFrame *pLeft = new CATDlgFrame(pMain, "LeftF",
        CATDlgFraSunkenFrame | CATDlgGridLayout);
    _pList = new CATDlgSelectorList(pLeft, "ItemList",
        CATDlgLstSingleSelection | CATDlgLstNoEdit);
    _pList->SetGridConstraints(pLeft,
        CATDlgGridConstraints(0, 0, 1, 2, CATGRID_4SIDES));
    _pAddBtn = new CATDlgPushButton(pLeft, "AddBtn", "Add");
    _pRemoveBtn = new CATDlgPushButton(pLeft, "RemoveBtn", "Remove");

    // 右侧: 详情
    CATDlgFrame *pRight = new CATDlgFrame(pMain, "RightF",
        CATDlgFraGroupFrame | CATDlgGridLayout);
    pRight->SetTitle("Properties");
    CATDlgGridConstraints g;
    int row = 0;

    CATDlgLabel *pNameLbl = new CATDlgLabel(pRight, "NmLbl", "Name:");
    pNameLbl->SetGridConstraints(pRight, g.SetRow(row).SetColumn(0));
    _pNameEditor = new CATDlgEditor(pRight, "NmEdt");
    _pNameEditor->SetGridConstraints(pRight, g.SetRow(row++).SetColumn(1));

    CATDlgLabel *pTypeLbl = new CATDlgLabel(pRight, "TpLbl", "Type:");
    pTypeLbl->SetGridConstraints(pRight, g.SetRow(row).SetColumn(0));
    _pTypeCombo = new CATDlgCombo(pRight, "TpCbo");
    _pTypeCombo->SetGridConstraints(pRight, g.SetRow(row++).SetColumn(1));

    // --- 按钮栏 ---
    CATDlgFrame *pBottom = new CATDlgFrame(this, "BottomF", CATDlgFraNoFrame);
    _pStatusLabel = new CATDlgLabel(pBottom, "Status", "Ready");
    _pOKBtn = new CATDlgPushButton(pBottom, "OKBtn", "OK");
    _pCancelBtn = new CATDlgPushButton(pBottom, "CancelBtn", "Cancel");
}

// 选择联动：列表选中 → 更新右侧详情
// 注意：回调真实类型为 CATCommandMethod（void (CATBaseUnknown::*)(CATCommand*, CATNotification*, CATCommandClientData)），
// 无返回值，且不存在 CATCommandClientInfo 类型
void OnListSelectionChanged(CATCommand *iCmd,
    CATNotification *iNotif, CATCommandClientData iUsefulData) {
    int sel = _pList->GetSelect(NULL);
    if (sel >= 0) {
        ItemData data = _itemData[sel];
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
    _pModeCombo->AddItem("Prefix");
    _pModeCombo->AddItem("Suffix");
    _pModeCombo->AddItem("Replace");
    AddAnalyseNotificationCB(this, _pModeCombo->GetComboSelectNotification(),
        (CATCommandMethod)&DynamicFormDlg::OnModeChanged, NULL);

    // --- 动态面板组 ---

    // Prefix 面板（默认可见）
    _pPrefixPanel = new CATDlgFrame(pFrame, "PrefixP",
        CATDlgFraGroupFrame | CATDlgGridLayout);
    _pPrefixPanel->SetTitle("Prefix Options");
    _pPrefixEditor = new CATDlgEditor(_pPrefixPanel, "PrefEdt");
    _pUpperRB = new CATDlgRadioButton(_pPrefixPanel, "UpperRB", "Upper");
    _pLowerRB = new CATDlgRadioButton(_pPrefixPanel, "LowerRB", "Lower");

    // Suffix 面板（默认隐藏）
    _pSuffixPanel = new CATDlgFrame(pFrame, "SuffixP",
        CATDlgFraGroupFrame | CATDlgGridLayout);
    _pSuffixPanel->SetTitle("Suffix Options");
    _pSuffixPanel->SetVisibility(CATDlgHide);
    _pSuffixEditor = new CATDlgEditor(_pSuffixPanel, "SufEdt");

    // Replace 面板（默认隐藏）
    _pReplacePanel = new CATDlgFrame(pFrame, "ReplaceP",
        CATDlgFraGroupFrame | CATDlgGridLayout);
    _pReplacePanel->SetTitle("Replace Options");
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
        pEdt->SetGridConstraints(_pDynamicPanel,
            CATDlgGridConstraints(i, 0, 1, 1, CATGRID_4SIDES));
        _dynamicEditors.Append(pEdt);
    }
}
```

---

## 3. 树形导航模式

左侧树形结构 + 右侧内容区，类似 CATIA Options 对话框：

```
┌──────────────────────────────────────────────┐
│ Tree                         │ Content       │
│ ┌──────────────────────────┐ │ ┌────────────┐│
│ │ ▼ General               │ │ │ Language:  ││
│ │   ├─ Display            │ │ │ [English ▼]││
│ │   └─ Units              │ │ │            ││
│ │ ▼ Modeling              │ │ │ Auto Save: ││
│ │   ├─ Part Design        │ │ │ ☑ Enable   ││
│ │   ├─ Surface            │ │ │ Interval:  ││
│ │   └─ Sheet Metal        │ │ │ [10] min   ││
│ │ ▼ Export                │ │ │            ││
│ │   ├─ STEP               │ │ │ Unit:      ││
│ │   └─ IGES               │ │ │ (●)mm ( )in││
│ └──────────────────────────┘ │ └────────────┘│
└──────────────────────────────────────────────┘
```

### 关键实现

```cpp
void TreeNavDlg::Build() {
    // 主容器水平排列
    CATDlgFrame *pMain = new CATDlgFrame(this, "MainF", CATDlgFraNoFrame);

    // 左侧树
    CATDlgFrame *pTreeFrame = new CATDlgFrame(pMain, "TreeF",
        CATDlgFraSunkenFrame | CATDlgGridLayout);
    _pTree = new CATDlgTree(pTreeFrame, "NavTree");
    _pTree->SetGridConstraints(pTreeFrame,
        CATDlgGridConstraints(0, 0, 1, 1, CATGRID_4SIDES));

    // 构建树节点
    CATDlgTreeItem *pRoot = _pTree->AddItem(NULL, "General");
    CATDlgTreeItem *pDisplay = _pTree->AddItem(pRoot, "Display");
    CATDlgTreeItem *pUnits = _pTree->AddItem(pRoot, "Units");
    CATDlgTreeItem *pModeling = _pTree->AddItem(NULL, "Modeling");
    CATDlgTreeItem *pPart = _pTree->AddItem(pModeling, "Part Design");

    // 右侧内容区（用 CATDlgTabContainer 模拟页面切换）
    _pContentTabs = new CATDlgTabContainer(pMain, "ContentTabs");
    // 每个树节点对应一个 Tab 页，切换时改变可见 Tab

    // 绑定树节点点击事件
    AddAnalyseNotificationCB(this, _pTree->GetTreeSelectNotification(),
        (CATCommandMethod)&TreeNavDlg::OnTreeSelection, NULL);
}

void TreeNavDlg::OnTreeSelection(CATCommand *iCmd,
    CATNotification *iNotif, CATCommandClientData iUsefulData) {
    CATDlgTreeItem *pSelected = _pTree->GetSelect();
    int pageIndex = GetPageIndexForNode(pSelected);
    _pContentTabs->SetCurrentTab(pageIndex);
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

用 `CATDlgSplitter` 实现用户可拖拽调节大小的左右/上下分区：

```cpp
CATDlgSplitter *pSplitter = new CATDlgSplitter(pMain, "Splitter",
    CATDlgSplitterVertical);  // 或 CATDlgSplitterHorizontal

// 左侧面板
CATDlgFrame *pLeftPane = new CATDlgFrame(pSplitter, "LeftPane",
    CATDlgFraSunkenFrame | CATDlgGridLayout);
_LeftPane->SetMinimumSize(150, 200);

// 右侧面板
CATDlgFrame *pRightPane = new CATDlgFrame(pSplitter, "RightPane",
    CATDlgFraSunkenFrame | CATDlgGridLayout);
_RightPane->SetMinimumSize(200, 200);

pSplitter->AttachLeft(pLeftPane);
pSplitter->AttachRight(pRightPane);
```

---

## AI 生成规则

- [ ] 列表-详情: 左侧 `CATDlgSelectorList` + 右侧 `CATDlgFrame(GroupBox)`
- [ ] 动态表单: Combo 切换 → `SetVisibility` 控制面板
- [ ] 树形导航: 左侧 `CATDlgTree` + 右侧 `CATDlgTabContainer`
- [ ] 向导: `CATStateCommand` 状态机 + Dialog `ShowPanel(n)`
- [ ] 可伸缩: `CATDlgSplitter` + `SetMinimumSize`
- [ ] 动态控件用 `RequestDelayedDestruction()` 清理
- [ ] 所有面板切换必须在 `Build()` 中预创建，运行时只切换可见性
- [ ] 面板过多（>5）考虑用树形导航或 Tab 页替代直接堆叠
