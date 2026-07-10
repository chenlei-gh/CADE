---
id: ui.dialog_layout
title: Dialog Layout & GridConstraints
category: knowledge
domain: ui
keywords: [layout, grid, constraints, anchor, nesting, resize, frame, stretch]
apis: [CATDlgGridConstraints, CATDlgFrame, CATDlgDialog]
requires: [ui.dialog]
patterns: [ui.master_detail]
examples: []
release: [R19, R28]
tags: [ui, layout, grid]
---

# CAA Dialog Layout & Advanced Controls

## 布局模式速查

### 单列垂直

```cpp
void Build() {
    CATDlgFrame *pFrame = new CATDlgFrame(this, "F",
        CATDlgFraNoFrame | CATDlgGridLayout);
    CATDlgGridConstraints g;
    int row = 0;
    
    _pLabel1 = new CATDlgLabel(pFrame, "L1", "Input:");
    _pLabel1->SetGridConstraints(pFrame, g.SetRow(row++).SetColumn(0));
    
    _pEditor1 = new CATDlgEditor(pFrame, "E1");
    _pEditor1->SetGridConstraints(pFrame, g.SetRow(row++).SetColumn(0));
    
    _pLabel2 = new CATDlgLabel(pFrame, "L2", "Output:");
    _pLabel2->SetGridConstraints(pFrame, g.SetRow(row++).SetColumn(0));
    
    _pEditor2 = new CATDlgEditor(pFrame, "E2");
    _pEditor2->SetGridConstraints(pFrame, g.SetRow(row++).SetColumn(0));
}
```

### 双列标签-输入

```cpp
void Build() {
    CATDlgFrame *pFrame = new CATDlgFrame(this, "F",
        CATDlgFraNoFrame | CATDlgGridLayout);
    CATDlgGridConstraints g;
    int row = 0;
    
    auto AddRow = [&](const char *label, CATDlgEditor *&editor) {
        CATDlgLabel *pLbl = new CATDlgLabel(pFrame, label, label);
        pLbl->SetGridConstraints(pFrame, g.SetRow(row).SetColumn(0));
        editor = new CATDlgEditor(pFrame, label);
        editor->SetGridConstraints(pFrame, g.SetRow(row).SetColumn(1));
        row++;
    };
    
    AddRow("Name:",     _pNameEditor);
    AddRow("Prefix:",   _pPrefixEditor);
    AddRow("Value:",    _pValueEditor);
    AddRow("Unit:",     _pUnitEditor);
}
```

### Tab 页

```cpp
void Build() {
    CATDlgTabContainer *pTab = new CATDlgTabContainer(this, "Tabs");
    
    // Tab 1: Input
    CATDlgFrame *pInputTab = new CATDlgFrame(pTab, "InputTab",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pInputEditor = new CATDlgEditor(pInputTab, "Input");
    pTab->AttachTab(pInputTab, "Input");

    // Tab 2: Options
    CATDlgFrame *pOptTab = new CATDlgFrame(pTab, "OptTab",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pOptionCB = new CATDlgCheckButton(pOptTab, "Opt", "Enable");
    pTab->AttachTab(pOptTab, "Options");

    // Tab 3: Preview
    CATDlgFrame *pPrevTab = new CATDlgFrame(pTab, "PrevTab",
        CATDlgFraNoFrame);
    CATDlgLabel *pPreview = new CATDlgLabel(pPrevTab, "Prev",
        "Result will appear here");
    pTab->AttachTab(pPrevTab, "Preview");
}
```

### 分组框 (GroupBox)

```cpp
CATDlgFrame *pGroup1 = new CATDlgFrame(pParent, "G1",
    CATDlgFraGroupFrame | CATDlgGridLayout);
pGroup1->SetTitle("Rename Options");

_pPrefixRB = new CATDlgRadioButton(pGroup1, "Prefix", "Prefix");
_pSuffixRB = new CATDlgRadioButton(pGroup1, "Suffix", "Suffix");
```

---

## GridConstraints 完整参数

`CATDlgGridConstraints` 控制控件在网格中的位置、跨度、伸缩和锚定行为：

```cpp
CATDlgGridConstraints(
    int iRow,              // 行号 (0-based)
    int iColumn,           // 列号 (0-based)
    int iRowSpan,          // 跨行数 (默认 1)
    int iColumnSpan,       // 跨列数 (默认 1)
    unsigned int iAnchor,  // 锚定/填充方式
    int iGravity = 0       // 重力对齐 (0=居中)
);
```

### 锚定常量 (iAnchor)

| 常量 | 含义 | 适用场景 |
|------|------|---------|
| `CATGRID_LEFT` | 左对齐，高度不变 | 标签、短文本 |
| `CATGRID_RIGHT` | 右对齐，高度不变 | 数值显示 |
| `CATGRID_TOP` | 顶部对齐，宽度不变 | 垂直标签 |
| `CATGRID_BOTTOM` | 底部对齐 | 状态栏 |
| `CATGRID_4SIDES` | 四边填充（控件撑满格子） | 输入框、列表、多行文本 |
| `CATGRID_HORIZONTAL` | 水平填充，高度不变 | 横向按钮 |
| `CATGRID_VERTICAL` | 垂直填充，宽度不变 | 竖向工具栏 |

### 跨行/跨列 (Span)

```cpp
// 按钮横跨两列
_pFullWidthBtn->SetGridConstraints(pFrame,
    CATDlgGridConstraints(row, 0, 1, 2, CATGRID_4SIDES));
//                         ↑   ↑  ↑  ↑
//                        row col rs cs(跨2列)

// 多行编辑器跨3行
_pMultiEdit->SetGridConstraints(pFrame,
    CATDlgGridConstraints(row, 0, 3, 1, CATGRID_4SIDES));
//                         ↑   ↑  ↑  ↑
//                        row col rs(跨3行) cs
```

### 链式调用

```cpp
CATDlgGridConstraints g;
_pWidget->SetGridConstraints(pFrame,
    g.SetRow(0)
     .SetColumn(1)
     .SetSpan(1, 2)      // 跨2列
     .SetAnchor(CATGRID_4SIDES));
```

---

## 多层嵌套布局

实际项目的对话框很少只有一层 Frame，通常是 3-5 层嵌套：

```
Dialog (CATDlgGridLayout)
 ├── TopFrame (CATDlgGridLayout)           ← 第2层: 搜索/过滤
 │    ├── SearchEditor (Col 0)
 │    └── SearchBtn    (Col 1)
 │
 ├── MainFrame (水平, 默认)                 ← 第2层: 主内容
 │    ├── LeftPanel (CATDlgGridLayout)     ← 第3层: 列表
 │    │    ├── SelectorList
 │    │    └── AddBtn / RemoveBtn
 │    │
 │    └── RightPanel (CATDlgGridLayout)    ← 第3层: 详情
 │         ├── NameEditor
 │         ├── TypeCombo
 │         └── PropertiesFrame             ← 第4层: 属性组
 │              ├── LengthEditor
 │              └── WidthEditor
 │
 └── BottomFrame (水平)                     ← 第2层: 按钮栏
      ├── StatusLabel
      ├── Spacer     (CATDlgFrame 占位)
      ├── OKBtn
      └── CancelBtn
```

### 嵌套代码示例

```cpp
void MyComplexDlg::Build() {
    // === 第1层: 对话框本身 (GridLayout) ===
    
    // === 第2层: 顶部搜索栏 ===
    CATDlgFrame *pTop = new CATDlgFrame(this, "TopFrame",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pSearchEditor = new CATDlgEditor(pTop, "SearchEdt");
    _pSearchEditor->SetGridConstraints(pTop,
        CATDlgGridConstraints(0, 0, 1, 1, CATGRID_4SIDES));
    _pSearchBtn = new CATDlgPushButton(pTop, "SearchBtn", "Search");
    _pSearchBtn->SetGridConstraints(pTop,
        CATDlgGridConstraints(0, 1, 1, 1, CATGRID_HORIZONTAL));
    
    // === 第2层: 主内容区 (水平 Frame) ===
    CATDlgFrame *pMain = new CATDlgFrame(this, "MainFrame", CATDlgFraNoFrame);
    
    // === 第3层: 左侧列表 ===
    CATDlgFrame *pLeft = new CATDlgFrame(pMain, "LeftPanel",
        CATDlgFraSunkenFrame | CATDlgGridLayout);
    _pSelectorList = new CATDlgSelectorList(pLeft, "SelList",
        CATDlgLstMultipleSelection);
    _pSelectorList->SetGridConstraints(pLeft,
        CATDlgGridConstraints(0, 0, 1, 2, CATGRID_4SIDES));
    _pAddBtn = new CATDlgPushButton(pLeft, "AddBtn", "Add");
    _pRemoveBtn = new CATDlgPushButton(pLeft, "RemoveBtn", "Remove");
    
    // === 第3层: 右侧详情 ===
    CATDlgFrame *pRight = new CATDlgFrame(pMain, "RightPanel",
        CATDlgFraGroupFrame | CATDlgGridLayout);
    pRight->SetTitle("Properties");
    
    _pNameEditor = new CATDlgEditor(pRight, "NameEdt");
    _pTypeCombo = new CATDlgCombo(pRight, "TypeCbo");
    
    // === 第4层: 属性子组 ===
    CATDlgFrame *pProp = new CATDlgFrame(pRight, "PropFrame",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pLengthEditor = new CATDlgEditor(pProp, "LenEdt");
    _pWidthEditor = new CATDlgEditor(pProp, "WidEdt");
    
    // === 第2层: 底部按钮栏 ===
    CATDlgFrame *pBottom = new CATDlgFrame(this, "BottomFrame",
        CATDlgFraNoFrame);
    _pStatusLabel = new CATDlgLabel(pBottom, "Status", "Ready");
    _pOKBtn = new CATDlgPushButton(pBottom, "OKBtn", "OK");
    _pCancelBtn = new CATDlgPushButton(pBottom, "CancelBtn", "Cancel");
}
```

---

## 布局伸缩策略

对话框缩放时，不同控件行为不同：

| 控件类型 | 伸缩策略 | Anchor 设置 |
|---------|---------|------------|
| 输入框 | 水平拉伸 | `CATGRID_HORIZONTAL` |
| 多行文本 | 四边拉伸 | `CATGRID_4SIDES` |
| 列表/树 | 四边拉伸 | `CATGRID_4SIDES` |
| 标签 | 固定 | `CATGRID_LEFT` 或 `CATGRID_RIGHT` |
| 按钮 | 固定 | 默认 |
| 进度条 | 水平拉伸 | `CATGRID_HORIZONTAL` |
| 分隔线 | 水平拉伸 | `CATGRID_HORIZONTAL` |
| 图片 | 固定 | 默认 |
| Tab 页 | 四边拉伸 | `CATGRID_4SIDES` |

### 常用布局比例

```cpp
// 左列 30% + 右列 70%（通过 Frame 宽度比例）
CATDlgFrame *pLeft = new CATDlgFrame(pMain, "L", ...);
CATDlgFrame *pRight = new CATDlgFrame(pMain, "R", ...);
// pLeft->SetRectDimensions(..., 200, ...)  // 固定宽度
// pRight 自动填充剩余空间
```

---

## 对话框初始大小和位置

```cpp
void Build() {
    // ... 控件创建 ...
    
    // 设置对话框标题
    SetTitle("Batch Rename");
    
    // 设置初始大小
    SetRectDimensions(1, 1, 400, 300);  // x, y, w, h
    
    // 居中
    CenterOnScreen();
}
```

---

## 高级控件

### Combo（下拉框）

```cpp
CATDlgCombo *pCombo = new CATDlgCombo(pFrame, "Combo");
pCombo->AddItem("Option 1");
pCombo->AddItem("Option 2");
pCombo->AddItem("Option 3");
pCombo->SetVisibleItemCount(5);  // 显示 5 行

// 读取选中的
int sel = pCombo->GetSelect();    // -1 = 未选中
CATUnicodeString text = pCombo->GetItem(sel);
```

### SelectorList（多选列表）

```cpp
CATDlgSelectorList *pList = new CATDlgSelectorList(pFrame, "List",
    CATDlgLstMultipleSelection | CATDlgLstNoEdit);

pList->SetLine("Item A");
pList->SetLine("Item B");
pList->SetLine("Item C");

// 获取选中（返回选中索引数组）
int *selArr = NULL;
int count = pList->GetSelect(&selArr);
if (selArr) delete[] selArr;
```

### File Selector

```cpp
CATDlgFile *pFile = new CATDlgFile(pFrame, "File",
    CATDlgFileOpen);  // 或 CATDlgFileSave

CATUnicodeString path = pFile->GetName();
```

### Progress Bar

```cpp
CATDlgProgressBar *pProgress = new CATDlgProgressBar(pFrame, "Progress");
pProgress->SetRange(0, 100);

// 在操作循环中更新
for (int i = 0; i < total; i++) {
    int pct = (i * 100) / total;
    pProgress->SetValue(pct);
    CATDialogAgent::DoEvents();  // 刷新 UI
}
```

### MultiEditor（多行文本框）

```cpp
CATDlgMultiEditor *pMulti = new CATDlgMultiEditor(pFrame, "Multi");
pMulti->SetVisibleTextHeight(10);   // 10 行高
pMulti->SetVisibleTextWidth(400);   // 宽度

CATUnicodeString text = pMulti->GetText();
pMulti->SetText("Initial text");
```

### Separator（分隔线）

```cpp
CATDlgSeparator *pSep = new CATDlgSeparator(pFrame, "Sep");
```

### Spinner（数字微调）

```cpp
CATDlgSpinner *pSpinner = new CATDlgSpinner(pFrame, "Spin");
pSpinner->SetRange(1, 9999);
pSpinner->SetValue(100);
pSpinner->SetStep(10);  // 每次步进 10

int val = pSpinner->GetValue();
```

---

## 控件启用/禁用

```cpp
// 根据模式切换控件状态
void ATAutoRenameDlg::OnModeChanged() {
    if (_pPrefixRB->GetState() == CATDlgCheck) {
        _pPrefixEditor->SetSensitivity(CATDlgEnable);
        _pSuffixEditor->SetSensitivity(CATDlgDisable);
    } else {
        _pPrefixEditor->SetSensitivity(CATDlgDisable);
        _pSuffixEditor->SetSensitivity(CATDlgEnable);
    }
}

// 根据权限隐藏整个 Group
_pAdminGroup->SetVisibility(CATDlgHide);
```

---

## 验证输入

```cpp
CATBoolean ATAutoRenameDlg::ValidateInput() {
    CATUnicodeString name = _pNameEditor->GetText();
    
    if (name.GetLength() == 0) {
        CATDlgNotification *pNotif = new CATDlgNotification(this, "Warning");
        pNotif->SetMessage("Name cannot be empty");
        pNotif->SetVisibility(CATDlgShow);
        _pNameEditor->SetFocus();
        return FALSE;
    }
    
    if (name.GetLength() > 50) {
        CATDlgNotification *pNotif = new CATDlgNotification(this, "Warning");
        pNotif->SetMessage("Name too long (max 50)");
        pNotif->SetVisibility(CATDlgShow);
        return FALSE;
    }
    
    return TRUE;
}
```

---

## AI 生成规则

- [ ] 复杂表单用 GridLayout + 双列模式
- [ ] 多类别用 TabContainer
- [ ] 相关控件用 GroupBox 分组
- [ ] `SetGridConstraints` 必须显式调用，不可省略
- [ ] 输入框用 `CATGRID_4SIDES` 锚定
- [ ] 标签用 `CATGRID_LEFT` 锚定
- [ ] 跨列控件用 `SetSpan(1, N)`
- [ ] 提供 `ValidateInput()` 验证方法
- [ ] 控件状态联动用 `SetSensitivity`
- [ ] 长文本用 `MultiEditor`
- [ ] 文件选择用 `CATDlgFile`
- [ ] 不要硬编码像素位置，用网格布局
- [ ] 3 层以上嵌套需要注释标明层级
- [ ] 对话框大小用 `SetRectDimensions` + `CenterOnScreen`
