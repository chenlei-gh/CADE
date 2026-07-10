# CAA Dialog Widget Patterns

## 基本结构

```cpp
class ATAutoRenameDlg : public CATDlgDialog {
    CATDeclareClass;

public:
    ATAutoRenameDlg(CATCommand *iParent);
    virtual ~ATAutoRenameDlg();
    void Build() override;

    // Getter（命令读取用户输入）
    CATUnicodeString GetNewName();
    CATBoolean IsPrefixMode();
    int GetCounterValue();

private:
    CATDlgLabel      *_pNameLabel;
    CATDlgEditor     *_pNameEditor;
    CATDlgRadioButton *_pPrefixRB;
    CATDlgRadioButton *_pSuffixRB;
    CATDlgSpinner    *_pCounter;
    CATDlgPushButton *_pApplyBtn;
    CATDlgPushButton *_pCancelBtn;
};
```

## Build() 模式

```cpp
void ATAutoRenameDlg::Build() {
    // 1. 创建容器（风格 + 布局）
    CATDlgFrame *pFrame = new CATDlgFrame(this, "MainFrame",
        CATDlgFraNoFrame | CATDlgGridLayout);
    CATDlgGridConstraints grid;

    // 2. 添加控件（一行一个 Row）
    _pNameLabel = new CATDlgLabel(pFrame, "NameLbl", "New Name:");
    _pNameLabel->SetGridConstraints(pFrame, grid.SetRow(0).SetColumn(0));
    
    _pNameEditor = new CATDlgEditor(pFrame, "NameEdt");
    _pNameEditor->SetGridConstraints(pFrame, grid.SetRow(0).SetColumn(1));
    _pNameEditor->SetVisibleTextMaxWidth(200);

    // 3. Radio Group
    CATDlgFrame *pRadioFrame = new CATDlgFrame(pFrame, "ModeFrame",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pPrefixRB = new CATDlgRadioButton(pRadioFrame, "PrefixRB", "Prefix");
    _pPrefixRB->SetState(CATDlgCheck);  // 默认选中
    _pSuffixRB = new CATDlgRadioButton(pRadioFrame, "SuffixRB", "Suffix");
    
    // 4. Spinner（数字微调）
    _pCounter = new CATDlgSpinner(pFrame, "CounterSpn");
    _pCounter->SetRange(1, 9999);

    // 5. 按钮
    _pApplyBtn = new CATDlgPushButton(pFrame, "ApplyBtn", "Apply");
    _pCancelBtn = new CATDlgPushButton(pFrame, "CancelBtn", "Cancel");

    // 6. 设置默认按钮
    SetDefaultPushButton(_pApplyBtn);
}
```

## 控件速查表

| 控件 | 类 | 用途 | 关键方法 |
|------|-----|------|---------|
| 标签 | `CATDlgLabel` | 显示只读文本 | |
| 输入框 | `CATDlgEditor` | 单行文本 | `GetText()`, `SetText()` |
| 多行文本 | `CATDlgMultiEditor` | 多行文本 | |
| 复选框 | `CATDlgCheckButton` | 开/关 | `GetState()`, `SetState(CATDlgCheck\|CATDlgUncheck)` |
| 单选按钮 | `CATDlgRadioButton` | 互斥选项 | 同上，需手动互斥 |
| 下拉框 | `CATDlgCombo` | 多选一 | `AddItem()`, `GetSelect()` |
| 列表框 | `CATDlgSelectorList` | 多选 | `SetLine()`, `GetSelect()` |
| 按钮 | `CATDlgPushButton` | 触发动作 | 绑定 Notification |
| 数字微调 | `CATDlgSpinner` | 整数输入 | `GetValue()`, `SetRange()` |
| 进度条 | `CATDlgProgressBar` | 显示进度 | `SetValue()` |
| 文件选择 | `CATDlgFile` | 选择文件 | `GetName()` |
| 分隔线 | `CATDlgSeparator` | 视觉分隔 | |
| Tab 页 | `CATDlgTabContainer` | 多页切换 | `AttachTab()` |

## 布局模式

### 网格布局（最常用）

```cpp
CATDlgGridConstraints grid;
_pWidget1->SetGridConstraints(pFrame, grid.SetRow(0).SetColumn(0));
_pWidget2->SetGridConstraints(pFrame, grid.SetRow(0).SetColumn(1));
_pWidget3->SetGridConstraints(pFrame, grid.SetRow(1).SetColumn(0).SetSpan(2, 1));
// Row 1, Column 0, Span 2 columns
```

### 垂直/水平布局

```cpp
// 垂直排列 Frame
CATDlgFrame *pVFrame = new CATDlgFrame(this, "V",
    CATDlgFraNoFrame | CATDlgGridLayout);
// 水平排列 Frame
CATDlgFrame *pHFrame = new CATDlgFrame(this, "H",
    CATDlgFraNoFrame);  // 默认水平
```

## 回调绑定（在 Command 中）

```cpp
// Activate() 中绑定
CATStatusChangeRC MyCmd::Activate(...) {
    _pDlg = new MyDlg(this);
    _pDlg->Build();
    _pDlg->SetVisibility(CATDlgShow);

    // 绑定 Apply 按钮
    CATDlgPushButton *pBtn = _pDlg->GetApplyButton();
    if (pBtn) {
        AddAnalyseNotificationCB(this, pBtn->GetPushNotification(),
            (CATCommandMethod)&MyCmd::OnApply, NULL);
    }
    return CATStatusChangeContinue;
}

CATStatusChangeRC MyCmd::OnApply(void *iData, CATNotification *iNotif,
                                   CATCommandClientInfo *iInfo) {
    CATUnicodeString name = _pDlg->GetNewName();
    // 执行操作...
    return CATStatusChangeContinue;
}
```

## AI 生成规则

- [ ] 继承 `CATDlgDialog`
- [ ] 实现 `Build()` 方法
- [ ] 控件用 GridLayout 排列（最灵活）
- [ ] 提供 Getter 方法供 Command 读取
- [ ] 不在 Dialog 里写业务逻辑
- [ ] Dialog 构造函数接收 `CATCommand *iParent`
