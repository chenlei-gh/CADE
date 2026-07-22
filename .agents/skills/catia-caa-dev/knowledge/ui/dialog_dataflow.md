---
id: ui.dialog_dataflow
title: Dialog Dataflow & Architecture
category: knowledge
domain: ui
keywords: [dataflow, command-dialog, persistence, NLS, architecture, communication, preferences]
apis: [CATDlgDialog, CATStateCommand, CATMsgCatalog, CATNotification]
requires: [ui.dialog]
patterns: [ui.master_detail, ui.dynamic_form]
examples: []
release: [R19, R28]
tags: [ui, architecture, dataflow]
---

# CAA UI Architecture & Dataflow

## 整体架构

```
Command (CATStateCommand)
    │
    ├── owns → Dialog (CATDlgDialog)
    │            │
    │            ├── Layout (CATDlgFrame + GridLayout)
    │            ├── Widgets (Editor, Combo, Radio, ...)
    │            └── Validation (ValidateInput)
    │
    ├── owns → Agent (CATFeatureImportAgent)
    │            │
    │            └── Events (OnSelect, OnApply, OnCancel)
    │
    └── registered in → Workbench/Addin (Toolbar)
```

## 数据流向

### 模式 1：Dialog → Command（最常见）

```
用户点击 Apply
    ↓
Dialog.OnApply() 触发的通知
    ↓
Command.OnApply 回调
    ↓ 读取 Dialog 数据
_pNameEditor->GetText()  →  CATUnicodeString name
_pCombo->GetSelect()     →  int mode
_pSpinner->GetValue()    →  int count
    ↓
Command 执行业务逻辑
    ↓
关闭 Dialog / 继续等待
```

### 模式 2：Agent → Command → Dialog

```
用户选择几何对象
    ↓
Agent.OnSelect 通知
    ↓
Command.OnSelect 回调
    ↓ 获取特征数据
CATISpecObject_var spObj = GetSelectedObject()
CATUnicodeString name = GetFeatureName(spObj)
    ↓ 更新 Dialog 显示
_pDlg->SetCurrentName(name)
_pDlg->SetPreview(length, area)
```

## Command-Dialog 通信契约

```cpp
// Dialog 提供 Getter（Command 读取用户输入）
class MyDlg : public CATDlgDialog {
public:
    CATUnicodeString GetNewName();
    CATBoolean IsPrefixMode();
    int GetCounterValue();
};

// Dialog 提供 Setter（Command 更新 Dialog 显示）
class MyDlg : public CATDlgDialog {
public:
    void SetCurrentName(const CATUnicodeString &iName);
    void SetPreview(double iLength, double iArea);
    void SetProgress(int iPercent);
};

// Command 持有 Dialog 引用
class MyCmd : public CATStateCommand {
private:
    MyDlg *_pDlg;           // 一个 Command 通常一个 Dialog
    CATFeatureImportAgent *_pAgent;  // 一个或多个 Agent
};
```

## 持久化偏好

记住用户上次的设置，下次打开自动恢复：

```cpp
// 保存偏好（在 Desactivate 中）
CATStatusChangeRC MyCmd::Desactivate(...) {
    if (_pDlg) {
        _prefs.name = _pDlg->GetNewName();
        _prefs.mode = _pDlg->GetMode();
        _prefs.counter = _pDlg->GetCounterValue();
    }
    return CATStatusChangeRCCompleted;
}

// 恢复偏好（在 Activate 中）
CATStatusChangeRC MyCmd::Activate(...) {
    _pDlg = new MyDlg(this);
    _pDlg->Build();
    _pDlg->SetCurrentName(_prefs.name);      // 恢复上次输入
    _pDlg->SetMode(_prefs.mode);
    _pDlg->SetVisibility(CATDlgShow);
    return CATStatusChangeRCCompleted;
}
```

> ⚠️ **重要修正**：`CATStatusChangeRC` 只有两个合法值：`CATStatusChangeRCCompleted` 与 `CATStatusChangeRCAborted`（定义于 `CATCommand.h`）。不存在 `CATStatusChangeContinue`/`CATStatusChangeCompleted`/`CATStatusChangeCanceled` 这些值。`Activate()` 返回 `CATStatusChangeRCCompleted` 表示激活成功完成（即使对话框仍在显示，命令已进入等待交互的“完成”状态，与对话框是否关闭无关）。

## NLS 国际化

```cpp
// ❌ 硬编码（且构造签名为 (parent, name, style)，第3参不是标题）
_pNameLabel = new CATDlgLabel(pFrame, "NameLbl");
_pNameLabel->SetTitle(CATUnicodeString("New Name:"));

// ✅ NLS：构造后 SetTitle 喂 CATMsgCatalog 消息
_pNameLabel = new CATDlgLabel(pFrame, "NameLbl");
_pNameLabel->SetTitle(CATMsgCatalog::BuildMessage("ATCatalog", "AT_DLG_NAME_LABEL"));
// 或零代码：直接在 .CATNls 里写 NameLbl.Title = "New Name:";
```

NLS 文件 (CNext/resources/msgcatalog/Framework.CATNls):
```
AT_DLG_NAME_LABEL = "New Name:";
AT_DLG_PREFIX_RB  = "Prefix";
AT_DLG_SUFFIX_RB  = "Suffix";
```

## 关键原则

1. **Dialog 只管 UI** — 不访问 CATIA 数据模型，不执行业务逻辑
2. **Command 只管逻辑** — 通过 Getter 读取 Dialog，不直接操作 Dialog 控件
3. **Agent 只管道选择** — 不处理业务，把选中对象传给 Command
4. **数据单向流动** — Dialog → Command（读取），Command → Dialog（显示）
