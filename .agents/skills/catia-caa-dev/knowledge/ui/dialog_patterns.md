---
id: ui.dialog_patterns
title: Dialog Widget Patterns
category: knowledge
domain: ui
keywords: [widget, build, controls, preview, decision, selector, combo, radio]
apis: [CATDlgDialog, CATDlgEditor, CATDlgCombo, CATDlgRadioButton, CATDlgSpinner]
requires: [ui.dialog]
patterns: [ui.result_dialog, ui.master_detail, ui.dynamic_form, ui.wizard]
examples: []
release: [R19, R28]
tags: [ui, widget, pattern]
---

# CAA Dialog Widget Patterns

## 决策索引

根据需求特征，快速定位正确的实现模式：

| 需求特征 | 推荐模式 | 跳转 |
|---------|---------|------|
| 简单参数输入（名称/数值） | 双列标签-输入 | [dialog_layout.md §2](dialog_layout.md) |
| 多类别配置 | Tab 页 | [dialog_layout.md §3](dialog_layout.md) |
| 相关选项分组 | GroupBox | [dialog_layout.md §4](dialog_layout.md) |
| 选择特征→执行操作 | Agent + Dialog | [event_patterns.md §选择事件](event_patterns.md) |
| 批量处理带进度 | ProgressBar + 循环 | [dialog_layout.md §Progress](dialog_layout.md) |
| 按钮触发动作 | OnApply 回调 | [event_patterns.md §Dialog按钮](event_patterns.md) |
| 下拉切换模式 | Combo + OnModeChanged | [event_patterns.md §Combo](event_patterns.md) |
| 文件选择 | CATDlgFile | [dialog_layout.md §File](dialog_layout.md) |
| 多步骤向导 | 状态机切换 Panel | [wizard.md](../../patterns/ui/wizard.md) |
| 实时预览 | 双面板（参数+预览） | 下方 §实时预览模式 |
| 记住上次设置 | 持久化偏好 | [dialog_dataflow.md](dialog_dataflow.md) §持久化 |
| 📋 列表-详情（选择+编辑） | Master-Detail 布局 | [master_detail.md](../../patterns/ui/master_detail.md) |
| 🎛 模式切换显示不同控件 | 动态表单 | [dynamic_form.md](../../patterns/ui/dynamic_form.md) |
| 🌳 分类导航（树+内容） | 树形导航 | [layout_advanced.md §3](layout_advanced.md) |
| 📐 可拖拽分栏 | Splitter | [layout_advanced.md §5](layout_advanced.md) |
| ⚠️ 常见布局错误 | 反模式参考 | [layout_anti_patterns.md](layout_anti_patterns.md) |
| 🔧 多层嵌套布局 | 3-4 层 Frame 嵌套 | [dialog_layout.md §多层嵌套](dialog_layout.md) |
| 📏 布局伸缩/锚定 | GridConstraints 参数 | [dialog_layout.md §GridConstraints](dialog_layout.md) |

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
        AddAnalyseNotificationCB(this, pBtn->GetPushBActivateNotification(),
            (CATCommandMethod)&MyCmd::OnApply, NULL);
    }
    return CATStatusChangeRCCompleted;
}

// ⚠️ 重要修正：回调方法的真实类型是 CATCommandMethod（CATCommand.h）：
// typedef void (CATBaseUnknown::*CATCommandMethod)(CATCommand*, CATNotification*, CATCommandClientData)
// 返回值是 void（不是 CATStatusChangeRC），第三参数是 CATCommandClientData（实际上是 void*），不存在 CATCommandClientInfo 这个类型
void MyCmd::OnApply(CATCommand *iCmd, CATNotification *iNotif,
                     CATCommandClientData iUsefulData) {
    CATUnicodeString name = _pDlg->GetNewName();
    // 执行操作...
}
```

## 实时预览模式

左边参数面板 + 右边预览面板，参数变化即时反映。

```cpp
void MyDlg::Build() {
    CATDlgFrame *pMain = new CATDlgFrame(this, "Main", CATDlgFraNoFrame);
    CATDlgFrame *pLeft = new CATDlgFrame(pMain, "Left",
        CATDlgFraNoFrame | CATDlgGridLayout);
    _pNameEditor = new CATDlgEditor(pLeft, "Name");
    _pWidthSpinner = new CATDlgSpinner(pLeft, "Width");
    CATDlgFrame *pRight = new CATDlgFrame(pMain, "Right",
        CATDlgFraSunkenFrame);
    _pPreviewLabel = new CATDlgLabel(pRight, "Preview", "");
    AddAnalyseNotificationCB(this,
        _pNameEditor->GetEditorNotification(),
        (CATCommandMethod)&MyDlg::OnPreviewUpdate, NULL);
}

void MyDlg::OnPreviewUpdate(CATCommand *iCmd, CATNotification *iNotif,
                             CATCommandClientData iUsefulData) {
    CATUnicodeString name = _pNameEditor->GetText();
    int width = _pWidthSpinner->GetValue();
    CATUnicodeString preview;
    preview.BuildFromNum(width);
    preview = name + " (" + preview + "mm)";
    _pPreviewLabel->SetTitle(preview);
}
```

## AI 生成规则

- [ ] 继承 `CATDlgDialog`
- [ ] 实现 `Build()` 方法
- [ ] 控件用 GridLayout 排列（最灵活）
- [ ] 每个控件创建后立即调用 `SetGridConstraints`
- [ ] 提供 Getter 方法供 Command 读取
- [ ] 不在 Dialog 里写业务逻辑
- [ ] Dialog 构造函数接收 `CATCommand *iParent`
- [ ] 嵌套不超过 4 层，超过用 GroupBox/Tab/Splitter
- [ ] 禁止硬编码 `SetRectDimensions` 代替 `SetGridConstraints`
- [ ] 同 Frame 内控件 ID 必须唯一
- [ ] 必须设默认按钮 `SetDefaultPushButton`
- [ ] Frame 风格必须显式指定（`CATDlgFraNoFrame` 等）
- [ ] Desactivate **和** Cancel 都必须隐藏 Dialog（`SetVisibility(CATDlgHide)`）——用户关闭对话框时框架实际调用的是 `Cancel()`，只写 Desactivate 会导致关闭按钮无效，详见 [fp_dialog_cancel_not_desactivate.md](../failure_patterns/fp_dialog_cancel_not_desactivate.md)
- [ ] 真正的销毁（`RequestDelayedDestruction()`）只放在析构函数里，禁止在 Cancel/Desactivate 里直接 delete
- [ ] Dialog 构造函数的父窗口参数禁止传 NULL，否则对话框静默不可见，详见 [fp_dialog_null_parent.md](../failure_patterns/fp_dialog_null_parent.md)
- [ ] 复杂布局先查 [决策索引](#决策索引) 匹配模式
- [ ] 不确定时查 [layout_anti_patterns.md](layout_anti_patterns.md) 排除错误做法
