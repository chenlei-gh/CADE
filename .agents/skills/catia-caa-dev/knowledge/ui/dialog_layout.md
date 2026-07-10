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

## 对话框大小和位置

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
```

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

## AI 生成规则

- [ ] 复杂表单用 GridLayout + 双列模式
- [ ] 多类别用 TabContainer
- [ ] 相关控件用 GroupBox 分组
- [ ] 提供 `ValidateInput()` 验证方法
- [ ] 控件状态联动用 `SetSensitivity`
- [ ] 长文本用 `MultiEditor`
- [ ] 文件选择用 `CATDlgFile`
- [ ] 不要硬编码像素位置，用网格布局
