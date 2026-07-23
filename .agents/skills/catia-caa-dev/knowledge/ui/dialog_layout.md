---
id: ui.dialog_layout
title: Dialog Layout & GridConstraints
category: knowledge
domain: ui
keywords: [layout, grid, constraints, anchor, nesting, resize, frame, stretch]
apis: [CATDlgGridConstraints, CATDlgFrame, CATDlgDialog, CATDlgTabContainer]
requires: [ui.dialog]
patterns: [ui.master_detail]
examples: []
release: [R19, R28]
tags: [ui, layout, grid]
---

# CAA Dialog Layout & Advanced Controls

## ⚠️ 重要修正

之前版本以下 API 经核实**不存在或签名错误**：

| 虚构/错误 | 真实 API |
|-----------|---------|
| `SetGridConstraints(pFrame, gc)` 两参 | **两种都合法**（CATDialog.h L577/L606）：`SetGridConstraints(gc)` 单参对象，或 `SetGridConstraints(row, col, rspan, cspan, anchor)` 5 参重载（生产项目常用后者，更紧凑） |
| `gc.SetRow(r).SetColumn(c).SetSpan(...).SetAnchor(...)` 链式 | **无链式 setter**；用构造函数 `CATDlgGridConstraints(row, col, rspan, cspan, anchor)` 或直接写公有成员 `Row`/`Column` |
| `CATGRID_HORIZONTAL` / `CATGRID_VERTICAL` | 不存在。水平填充用 `CATGRID_LEFT\|CATGRID_RIGHT`；垂直用 `CATGRID_TOP\|CATGRID_BOTTOM` |
| `CATDlgFraGroupFrame` / `CATDlgFraSunkenFrame` | 不存在。Frame 风格只有 `CATDlgFraNoTitle`/`CATDlgFraNoFrame`/`CATDlgFraNoMargin`；标题用 `SetTitle()` |
| `pTab->AttachTab(frame, "Title")` | 不存在。**以 TabContainer 为父创建 Frame 即自动成页**；页控制用 `SetSelectedPage/GetSelectedPage/GetPageCount` |
| `CATDlgProgressBar` | 真实类名是 `CATDlgProgress` |
| `CATDlgMultiEditor` | 不存在；多行文本用 `CATDlgEditor` + 多行风格，或 `CATDlgCombo` 的 `SetVisibleTextHeight` |
| `pCombo->AddItem(...)` / `SetVisibleItemCount(n)` | 真实：`pCombo->SetLine(text, -1)` 追加；可见行数 `SetVisibleTextHeight(n)` |
| `pSpinner->SetStep(n)` | 不存在；步进数是 `SetRange(min, max, stepCount)` 的第 3 参 |
| `CATDlgNotification` + `SetMessage()` | 真实类 `CATDlgNotify`，方法 `SetText()` |
| `CATDlgLstMultipleSelection` / `CATDlgLstNoEdit` | 真实风格 `CATDlgLstMultisel`（多选）；无 NoEdit 风格 |
| `CATDlgFileOpen` / `pFile->GetName()` | 打开是默认风格（保存才需 `CATDlgFileSave`）；取文件用 `GetSelection()` |
| `CenterOnScreen()` | 不存在；`SetRectDimensions(x, y, height, width)` 存在（注意 h/w 顺序） |
| `CATDialogAgent::DoEvents()` | 不存在 |

## 布局模式速查

### ⭐ 顶层布局选型（生产实证）

| 场景 | 顶层布局 | 窗口风格 |
|------|---------|---------|
| 对话框只含一个表单 | `CATDlgGridLayout`（对话框或单 Frame） | `CATDlgWndBtnOKCancel` 等 |
| **多个区域垂直堆叠，或有动态显隐面板** | **attachment 布局**（不设 GridLayout） | **必须配 `CATDlgWndAutoResize`** |

**attachment 布局（生产项目 CAAAutoRenameDlg 实证模式）：**

```cpp
// 构造函数：窗口风格配 AutoResize
MyDlg::MyDlg(CATDialog *iParent)
    : CATDlgDialog(iParent, "MyDlgId",
                   CATDlgWndAutoResize | CATDlgWndBtnOKCancel | CATDlgWndNoResize)
{}

void MyDlg::Build() {
    // SetHorizontalAttachment 垂直堆叠（top→bottom）；第1参是 tab 线索引，
    // 索引大小决定上下顺序，间隔留大些（0/10/20）方便以后插入新行
    _pList = new CATDlgMultiList(this, "ListId");
    SetHorizontalAttachment(0, CATDlgTopOrLeft, _pList, NULL);

    // 内部表单仍用 GridLayout Frame（两种布局各司其职）
    _pForm = new CATDlgFrame(this, "FormId", CATDlgFraNoFrame | CATDlgGridLayout);
    SetHorizontalAttachment(10, CATDlgTopOrLeft, _pForm, NULL);
    // ... 表单控件见下
}
```

关键 API（CATDlgFrame.h / CATDlgWindow.h 实证）：
- `SetHorizontalAttachment(tabIndex, CATDlgTopOrLeft, obj, NULL)` — 垂直堆叠
- `SetVerticalAttachment(tabIndex, CATDlgTopOrLeft, obj, NULL)` — 水平并排
- `ResetAttachment(obj)` — 把对象**从布局中摘除**（不占空间，配合动态显隐）
- `Attach4Sides(obj)` — 让对象撑满整个 Frame
- 附件模式：`CATDlgTopOrLeft`（固定）/ `CATDlgTopOrLeftRelative`（可拉伸）/ `CATDlgCenter` 等

**动态显隐面板（窗口自动收缩，不留空白）：**

```cpp
// 显示：attach + show
SetHorizontalAttachment(10, CATDlgTopOrLeft, _pEditPanel, NULL);
_pEditPanel->SetVisibility(CATDlgShow);

// 隐藏：detach + hide —— ResetAttachment 让面板不占布局空间，
// AutoResize 窗口随之收缩回原样（只 SetVisibility 会留一块空白！）
ResetAttachment(_pEditPanel);
_pEditPanel->SetVisibility(CATDlgHide);
```

### 单列垂直

```cpp
void Build() {
    CATDlgFrame *pFrame = new CATDlgFrame(this, "F",
        CATDlgFraNoFrame | CATDlgGridLayout);
    int row = 0;

    _pLabel1 = new CATDlgLabel(pFrame, "L1");
    _pLabel1->SetGridConstraints(CATDlgGridConstraints(row++, 0, 1, 1, CATGRID_LEFT));

    _pEditor1 = new CATDlgEditor(pFrame, "E1");
    _pEditor1->SetGridConstraints(CATDlgGridConstraints(row++, 0, 1, 1,
        CATGRID_LEFT | CATGRID_RIGHT));   // 水平填充

    _pLabel2 = new CATDlgLabel(pFrame, "L2");
    _pLabel2->SetGridConstraints(CATDlgGridConstraints(row++, 0, 1, 1, CATGRID_LEFT));

    _pEditor2 = new CATDlgEditor(pFrame, "E2");
    _pEditor2->SetGridConstraints(CATDlgGridConstraints(row++, 0, 1, 1,
        CATGRID_LEFT | CATGRID_RIGHT));
}
```

### 双列标签-输入

```cpp
void Build() {
    CATDlgFrame *pFrame = new CATDlgFrame(this, "F",
        CATDlgFraNoFrame | CATDlgGridLayout);

    // 手工逐行（CAA 代码避免 lambda，兼容老编译器）
    int row = 0;
    _pNameLabel = new CATDlgLabel(pFrame, "NameLbl");
    _pNameLabel->SetGridConstraints(CATDlgGridConstraints(row, 0, 1, 1, CATGRID_RIGHT));
    _pNameEditor = new CATDlgEditor(pFrame, "NameEdt");
    _pNameEditor->SetGridConstraints(CATDlgGridConstraints(row++, 1, 1, 1,
        CATGRID_LEFT | CATGRID_RIGHT));

    _pValueLabel = new CATDlgLabel(pFrame, "ValueLbl");
    _pValueLabel->SetGridConstraints(CATDlgGridConstraints(row, 0, 1, 1, CATGRID_RIGHT));
    _pValueEditor = new CATDlgEditor(pFrame, "ValueEdt");
    _pValueEditor->SetGridConstraints(CATDlgGridConstraints(row++, 1, 1, 1,
        CATGRID_LEFT | CATGRID_RIGHT));
}
```

### Tab 页

页 = 以 `CATDlgTabContainer` 为父创建的 Frame，**自动附加，无需 AttachTab**：

```cpp
void Build() {
    CATDlgTabContainer *pTab = new CATDlgTabContainer(this, "Tabs");

    // 每个以 pTab 为父的 Frame 自动成为一个页
    CATDlgFrame *pInputTab = new CATDlgFrame(pTab, "InputTab",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pInputEditor = new CATDlgEditor(pInputTab, "Input");

    CATDlgFrame *pOptTab = new CATDlgFrame(pTab, "OptTab",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pOptionCB = new CATDlgCheckButton(pOptTab, "Opt");

    // 页标题来自各 Frame 的 NLS Title；页控制：
    pTab->SetSelectedPage(0);        // 默认显示第1页
    // int n = pTab->GetPageCount();
}
```

### 分组框 (GroupBox)

带标题分组：**默认 Frame 就带标题栏**，不要加 `CATDlgFraNoTitle`；标题经 `SetTitle()` 或 NLS：

```cpp
CATDlgFrame *pGroup1 = new CATDlgFrame(pParent, "G1", CATDlgGridLayout);
pGroup1->SetTitle(CATMsgCatalog::BuildMessage("ATCatalog", "AT_GROUP_RENAME"));  // 或 NLS 键 G1.Title

_pPrefixRB = new CATDlgRadioButton(pGroup1, "Prefix");
_pSuffixRB = new CATDlgRadioButton(pGroup1, "Suffix");
```

---

## GridConstraints 完整参数

```cpp
CATDlgGridConstraints(
    short iTopRow,          // 行号 (0-based)
    short iLeftColumn,      // 列号 (0-based)
    short iRowSpan,         // 跨行数
    short iColumnSpan,      // 跨列数
    unsigned int iJustification  // 锚定/填充方式
);
// 也有无参构造 + 公有成员 Row / Column 可直接赋值
```

### 锚定常量 (iJustification) — 真实完整列表

`SetGridConstraints` 两个重载都合法（B28 CATDialog.h L577/L606）：
```cpp
// 单参对象版
_pEditor->SetGridConstraints(CATDlgGridConstraints(0, 0, 1, 1, CATGRID_4SIDES));
// 5 参版（生产项目常用，更紧凑；注意头文件注释里 rspan/cspan 描述与惯例相反，
// 实际行为：第3参=跨行数 rowspan，第4参=跨列数 colspan）
_pEditor->SetGridConstraints(0, 0, 1, 1, CATGRID_4SIDES);
```

| 常量 | 含义 |
|------|------|
| `CATGRID_LEFT` | 贴左 |
| `CATGRID_RIGHT` | 贴右 |
| `CATGRID_TOP` | 贴顶 |
| `CATGRID_BOTTOM` | 贴底 |
| `CATGRID_4SIDES` | 四边填充（=LEFT\|RIGHT\|TOP\|BOTTOM，撑满格子） |
| `CATGRID_CST_WIDTH` | 固定宽度 |
| `CATGRID_CST_HEIGHT` | 固定高度 |
| `CATGRID_CST_SIZE` | 固定宽高 |
| `CATGRID_CENTER` | 居中 |

水平填充 = `CATGRID_LEFT | CATGRID_RIGHT`；垂直填充 = `CATGRID_TOP | CATGRID_BOTTOM`。

### 跨行/跨列 (Span)

```cpp
// 按钮横跨两列
_pFullWidthBtn->SetGridConstraints(CATDlgGridConstraints(row, 0, 1, 2, CATGRID_4SIDES));
//                                                          ↑   ↑  ↑  ↑
//                                                        row col rs cs(跨2列)

// 多行编辑器跨3行
_pMultiEdit->SetGridConstraints(CATDlgGridConstraints(row, 0, 3, 1, CATGRID_4SIDES));
```

---

## 多层嵌套布局

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
      ├── OKBtn
      └── CancelBtn
```

### 嵌套代码示例

```cpp
void MyComplexDlg::Build() {
    // === 第2层: 顶部搜索栏 ===
    CATDlgFrame *pTop = new CATDlgFrame(this, "TopFrame",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pSearchEditor = new CATDlgEditor(pTop, "SearchEdt");
    _pSearchEditor->SetGridConstraints(CATDlgGridConstraints(0, 0, 1, 1,
        CATGRID_LEFT | CATGRID_RIGHT));
    _pSearchBtn = new CATDlgPushButton(pTop, "SearchBtn");
    _pSearchBtn->SetGridConstraints(CATDlgGridConstraints(0, 1, 1, 1, CATGRID_LEFT));

    // === 第2层: 主内容区 (水平 Frame) ===
    CATDlgFrame *pMain = new CATDlgFrame(this, "MainFrame", CATDlgFraNoFrame);

    // === 第3层: 左侧列表 ===
    CATDlgFrame *pLeft = new CATDlgFrame(pMain, "LeftPanel",
        CATDlgFraNoTitle | CATDlgGridLayout);
    _pSelectorList = new CATDlgSelectorList(pLeft, "SelList", CATDlgLstMultisel);
    _pSelectorList->SetGridConstraints(CATDlgGridConstraints(0, 0, 1, 2, CATGRID_4SIDES));
    _pAddBtn    = new CATDlgPushButton(pLeft, "AddBtn");
    _pRemoveBtn = new CATDlgPushButton(pLeft, "RemoveBtn");

    // === 第3层: 右侧详情（带标题分组） ===
    CATDlgFrame *pRight = new CATDlgFrame(pMain, "RightPanel", CATDlgGridLayout);
    pRight->SetTitle(CATMsgCatalog::BuildMessage("ATCatalog", "AT_GROUP_PROPS"));

    _pNameEditor = new CATDlgEditor(pRight, "NameEdt");
    _pTypeCombo  = new CATDlgCombo(pRight, "TypeCbo");

    // === 第4层: 属性子组 ===
    CATDlgFrame *pProp = new CATDlgFrame(pRight, "PropFrame",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pLengthEditor = new CATDlgEditor(pProp, "LenEdt");
    _pWidthEditor  = new CATDlgEditor(pProp, "WidEdt");

    // === 第2层: 底部按钮栏 ===
    CATDlgFrame *pBottom = new CATDlgFrame(this, "BottomFrame", CATDlgFraNoFrame);
    _pStatusLabel = new CATDlgLabel(pBottom, "Status");
    _pOKBtn     = new CATDlgPushButton(pBottom, "OKBtn");
    _pCancelBtn = new CATDlgPushButton(pBottom, "CancelBtn");
}
```

---

## 布局伸缩策略

| 控件类型 | 伸缩策略 | Justification 设置 |
|---------|---------|-------------------|
| 输入框 | 水平拉伸 | `CATGRID_LEFT \| CATGRID_RIGHT` |
| 多行文本 | 四边拉伸 | `CATGRID_4SIDES` |
| 列表/树 | 四边拉伸 | `CATGRID_4SIDES` |
| 标签 | 固定 | `CATGRID_LEFT` 或 `CATGRID_RIGHT` |
| 按钮 | 固定 | `CATGRID_LEFT` 等单边 |
| 进度条 | 水平拉伸 | `CATGRID_LEFT \| CATGRID_RIGHT` |
| 分隔线 | 水平拉伸 | `CATGRID_LEFT \| CATGRID_RIGHT` |
| Tab 页 | 四边拉伸 | `CATGRID_4SIDES` |

---

## 对话框初始大小和标题

```cpp
void Build() {
    // ... 控件创建 ...
    SetTitle(NLS("MyDlg.Title", "My Dialog"));  // NLS 优先
    SetRectDimensions(1, 1, 300, 400);   // (x, y, height, width) 注意 h/w 顺序！
    // 若用 CATDlgWndAutoResize 风格，无需 SetRectDimensions，窗口随内容自适应
}
```

控件宽度控制（不用像素）：`_pEditor->SetVisibleTextWidth(30);` 按可见字符数定宽，跨语言/字体稳定。

---

## 高级控件

### Combo（下拉框）

```cpp
CATDlgCombo *pCombo = new CATDlgCombo(pFrame, "Combo");
pCombo->SetLine(CATUnicodeString("Option 1"), -1);   // -1 = 追加
pCombo->SetLine(CATUnicodeString("Option 2"), -1);
pCombo->SetVisibleTextHeight(5);   // 下拉可见行数

int sel = pCombo->GetSelect();              // -1 = 未选中
CATUnicodeString text;
pCombo->GetLine(text, sel);                 // 取第 sel 行文本
```

### SelectorList（多选列表）

```cpp
CATDlgSelectorList *pList = new CATDlgSelectorList(pFrame, "List",
    CATDlgLstMultisel);

pList->SetLine(CATUnicodeString("Item A"), -1);
pList->SetLine(CATUnicodeString("Item B"), -1);

// 获取选中：调用方先问数量，再提供足够大的数组
int count = pList->GetSelectCount();
if (count > 0) {
    int *selArr = new int[count];
    pList->GetSelect(selArr, count);
    // ...
    delete [] selArr;
}
```

### File Selector

```cpp
// 打开文件 = 默认风格；保存 = CATDlgFileSave
CATDlgFile *pFile = new CATDlgFile(pFrame, "FileDlg");           // 打开
CATDlgFile *pSave = new CATDlgFile(pFrame, "SaveDlg", CATDlgFileSave);

pFile->SetFilterPattern(CATUnicodeString("*.CATPart"));
// 取选中文件：
CATUnicodeString path;
// pFile->GetSelection(path);   // GetSelection / GetSelectionCount
```

### Progress（进度条）

```cpp
CATDlgProgress *pProgress = new CATDlgProgress(pFrame, "Progress");
// 范围与取值方法见 CATDlgProgress.h（SetRange/SetValue 系列）

// 长循环中 UI 刷新：CAA 状态机命令天然在事件循环中分片执行；
// 批处理场景按状态拆分，而不是调用不存在的 DoEvents()
```

### Multi-line 文本

无 `CATDlgMultiEditor`。多行输入用 `CATDlgEditor` 配多行风格位，或退而用 `CATDlgCombo`（`SetVisibleTextHeight` 控制行高）。

### Separator（分隔线）

```cpp
CATDlgSeparator *pSep = new CATDlgSeparator(pFrame, "Sep");
pSep->SetGridConstraints(CATDlgGridConstraints(row, 0, 1, 2,
    CATGRID_LEFT | CATGRID_RIGHT));
```

### Spinner（数字微调）

```cpp
CATDlgSpinner *pSpinner = new CATDlgSpinner(pFrame, "Spin");
pSpinner->SetRange(1.f, 9999.f, 10);   // min, max, 步进数（无 SetStep）
pSpinner->SetValue(100.0);

double val = pSpinner->GetValue();
```

---

## 控件启用/禁用

```cpp
void ATAutoRenameDlg::OnModeChanged() {
    if (_pPrefixRB->GetState() == CATDlgCheck) {
        _pPrefixEditor->SetSensitivity(CATDlgEnable);
        _pSuffixEditor->SetSensitivity(CATDlgDisable);
    } else {
        _pPrefixEditor->SetSensitivity(CATDlgDisable);
        _pSuffixEditor->SetSensitivity(CATDlgEnable);
    }
}

// 隐藏整个 Group
_pAdminGroup->SetVisibility(CATDlgHide);
```

---

## 验证输入

```cpp
CATBoolean ATAutoRenameDlg::ValidateInput() {
    CATUnicodeString name = _pNameEditor->GetText();

    if (name.GetLength() == 0 || name.GetLength() > 50) {
        // 真实通知类是 CATDlgNotify，文本用 SetText
        CATDlgNotify *pNotif = new CATDlgNotify(this, "Warning");
        pNotif->SetText(CATMsgCatalog::BuildMessage("ATCatalog", "AT_ERR_NAME"));
        pNotif->SetVisibility(CATDlgShow);
        return FALSE;
    }
    return TRUE;
}
```

---

## AI 生成规则

- [ ] 顶层多区域堆叠/动态面板用 **attachment 布局**（`SetHorizontalAttachment` + `CATDlgWndAutoResize`），单一表单才用顶层 GridLayout
- [ ] 动态显隐面板：`ResetAttachment()` + `SetVisibility(Hide)` 隐藏；`SetHorizontalAttachment` + `SetVisibility(Show)` 显示
- [ ] 复杂表单内部用 GridLayout + 双列模式
- [ ] 多类别用 `CATDlgTabContainer`（Frame 以其为父自动成页）
- [ ] 分组用默认带标题 Frame + `SetTitle()`；**不要发明 CATDlgFraGroupFrame**
- [ ] `SetGridConstraints` 用单参对象或 5 参重载（**两参不存在**），GridLayout 下必须显式调用
- [ ] 水平填充 `CATGRID_LEFT|CATGRID_RIGHT`；四边 `CATGRID_4SIDES`
- [ ] 控件宽度用 `SetVisibleTextWidth(n)`，不硬编码像素
- [ ] 控件文本一律 NLS（BuildMessage + fallback，见 dialog_dataflow.md）
- [ ] 进度条类名 `CATDlgProgress`；通知类名 `CATDlgNotify`/`SetText`
- [ ] 提供 `ValidateInput()` 验证方法
- [ ] 控件状态联动用 `SetSensitivity(CATDlgEnable/Disable)`
- [ ] 文件选择用 `CATDlgFile`（打开默认/`CATDlgFileSave` 保存）
- [ ] 3 层以上嵌套需要注释标明层级
