---
id: ui.wizard
title: Wizard / Multi-Step Dialog
category: pattern
domain: ui
keywords: [dialog, wizard, step, state, progress, multi-page, next, back]
apis: [CATDlgDialog, CATDlgFrame, CATDlgPushButton, CATStateCommand, AddDialogState, AddTransition]
requires: [ui.dialog]
patterns: []
examples: []
release: [R19, R28]
tags: [pattern, ui, wizard, multi-step, state]
---

# Wizard Pattern (多步骤向导模式)

通过状态机驱动的多步骤对话框，Back/Next 切换面板。

## 适用场景

- 数据导出向导（选格式 → 配置参数 → 确认 → 执行）
- 数据导入/转换向导
- 复杂参数设置（如 3D 标注配置）
- 任何需要引导用户分步完成的复杂操作

## 架构

```
CATStateCommand
    │
    ├── State 1: Welcome/Format Select  ← 初始状态
    │     ├── Dialog Panel 0 (可见)
    │     ├── [Next →] 转换到 State 2
    │     └── [Cancel] 退出
    │
    ├── State 2: Options/Config
    │     ├── Dialog Panel 1 (可见)
    │     ├── [← Back] 转换到 State 1
    │     ├── [Next →] 转换到 State 3
    │     └── [Cancel] 退出
    │
    └── State 3: Confirm/Execute
          ├── Dialog Panel 2 (可见)
          ├── [← Back] 转换到 State 2
          └── [Finish] 执行 + 退出
```

## 实现模板

### Command 端（状态机）

```cpp
void ExportWizardCmd::BuildGraph() {
    // Panel 索引映射
    // Panel 0 = Format Select
    // Panel 1 = Options
    // Panel 2 = Confirm & Execute

    CATDialogState *pState1 = GetInitialState("Step1");
    CATDialogState *pState2 = AddDialogState("Step2");
    CATDialogState *pState3 = AddDialogState("Step3");

    AddTransition(pState1, pState2,
        IsOutputSetCondition(_pDlg->GetNextNotification()),
        Action((ActionMethod)&ExportWizardCmd::GoToStep2));

    AddTransition(pState2, pState1,
        IsOutputSetCondition(_pDlg->GetBackNotification()),
        Action((ActionMethod)&ExportWizardCmd::GoToStep1));

    AddTransition(pState2, pState3,
        IsOutputSetCondition(_pDlg->GetNextNotification()),
        Action((ActionMethod)&ExportWizardCmd::GoToStep3));

    AddTransition(pState3, pState2,
        IsOutputSetCondition(_pDlg->GetBackNotification()),
        Action((ActionMethod)&ExportWizardCmd::GoToStep2));

    // Finish = 执行操作
    AddTransition(pState3, NULL,
        IsOutputSetCondition(_pDlg->GetFinishNotification()),
        Action((ActionMethod)&ExportWizardCmd::ExecuteExport));
}
```

### Dialog 端（Panel 切换）

```cpp
class WizardDlg : public CATDlgDialog {
    CATDlgFrame *_panels[MAX_STEPS];  // 预创建所有 Panel
    CATDlgPushButton *_pBackBtn, *_pNextBtn, *_pCancelBtn;
    CATDlgLabel *_pStepIndicator;  // "Step 2 of 5"
    int _currentStep, _totalSteps;

    CATDlgPushButton *GetNextBtn()  { return _pNextBtn; }
    CATDlgPushButton *GetBackBtn()  { return _pBackBtn; }
    CATDlgPushButton *GetFinishBtn() { return _pNextBtn; }  // 最后一步复用

    CATNotification *GetNextNotification()   { return _pNextBtn->GetPushNotification(); }
    CATNotification *GetBackNotification()   { return _pBackBtn->GetPushNotification(); }
    CATNotification *GetFinishNotification() { return _pNextBtn->GetPushNotification(); }

    void ShowPanel(int index) {
        for (int i = 0; i < _totalSteps; i++) {
            _panels[i]->SetVisibility(i == index ? CATDlgShow : CATDlgHide);
        }
        _currentStep = index;
        _pBackBtn->SetSensitivity(index > 0 ? CATDlgEnable : CATDlgDisable);
        bool isLast = (index == _totalSteps - 1);
        _pNextBtn->SetTitle(isLast ? "Finish" : "Next →");
        _pStepIndicator->SetTitle(BuildStepText(index + 1, _totalSteps));
    }
};
```

## 关键设计点

1. **Panel 预创建** — 所有步骤的 Panel 在 `Build()` 中创建，运行时只切换可见性
2. **状态机驱动** — 用 `CATStateCommand` + `AddDialogState` + `AddTransition`
3. **最后一步复用 Next 按钮** — 改标题为 "Finish"
4. **Back 按钮可用性** — 第一步禁用，其他步骤启用
5. **步骤指示器** — 始终显示 "Step X of Y"
6. **数据跨步骤保留** — 数据存在 Command 成员变量中，不因 Panel 切换丢失

## AI 生成规则

- [ ] 用 `CATStateCommand`（不是 `CATCommand`）实现向导
- [ ] 所有 Panel 在 Build() 预创建
- [ ] 每步对应一个 `CATDialogState`
- [ ] 用 `AddTransition` 定义步骤间跳转
- [ ] 条件转换用 `IsOutputSetCondition(GetXxxNotification())`
- [ ] 最后一步的 Next 按钮改为 Finish
- [ ] 第一步禁用 Back 按钮
- [ ] 向导结束必须调用 `RequestDelayedDestruction()`
