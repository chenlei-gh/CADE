---
id: ui.wizard
title: Wizard / Multi-Step Dialog
category: pattern
domain: ui
keywords: [dialog, wizard, step, state, progress, multi-page, next, back]
apis: [CATDlgDialog, CATDlgFrame, CATDlgPushButton, CATStateCommand, CATDialogAgent, AddDialogState, AddTransition, AddDialogAgent, AddAnalyseNotificationCB]
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

## 关键机制：按钮如何驱动状态转换（易错点）

`IsOutputSetCondition()` 的参数必须是一个 **`CATDialogAgent*`**（被 `AddDialogAgent()` 挂到状态上的 agent 实例），**不能**直接传按钮的 `GetPushBActivateNotification()` 返回值——那是 `CATNotification*`，与 `IsOutputSetCondition(CATCommand*)` 的参数类型不匹配。

真实的"按钮点击 → 状态转换"绑定是三层机制（已用官方示例 `CAAGSMInterfaces.edu/CAAGsiFeaturesSplSewSkinBasicUI.m`（`CAAGSMSewSkinBasicDlg.cpp` + `CAAGSMSewSkinBasicCmd.cpp`）交叉验证）：

1. **Dialog 端**：按钮用 `AddAnalyseNotificationCB(pBtn, pBtn->GetPushBActivateNotification(), callback, clientData)` 监听点击；回调内部用 `SendNotification(GetFather(), &_CustomNotif)` 把一个自定义 `CATNotification` 子类实例发给父 Command（`_CustomNotif` 是 Dialog 类的成员，类型是自定义的 `CATNotification` 子类，例如 `CAANextStepNotification`）。
2. **Command 端**：为每个逻辑事件创建一个 `CATDialogAgent *pAgent = new CATDialogAgent("NextId")`，用 `pAgent->AcceptOnNotify(_pDlg, "CAANextStepNotification")`（第二参数是自定义通知类的类名字符串）把 agent 绑定到该通知。
3. **挂到状态**：`pState->AddDialogAgent(pAgent)`，然后 `AddTransition(pState1, pState2, IsOutputSetCondition(pAgent), Action(...))`——条件检测的是这个 agent 是否被 valued，不是按钮通知本身。

## 实现模板

### 自定义通知类（Local Interfaces 头文件）

```cpp
// WizardNotifications.h
#include "CATNotification.h"

class CAANextStepNotification : public CATNotification {
public:
    CATDeclareClass;
    CAANextStepNotification();
    virtual ~CAANextStepNotification();
};

class CAABackStepNotification : public CATNotification {
public:
    CATDeclareClass;
    CAABackStepNotification();
    virtual ~CAABackStepNotification();
};

class CAAFinishStepNotification : public CATNotification {
public:
    CATDeclareClass;
    CAAFinishStepNotification();
    virtual ~CAAFinishStepNotification();
};
```

### Dialog 端（按钮 → 自定义通知）

```cpp
class WizardDlg : public CATDlgDialog {
    CATDlgFrame *_panels[MAX_STEPS];  // 预创建所有 Panel
    CATDlgPushButton *_pBackBtn, *_pNextBtn, *_pCancelBtn;
    CATDlgLabel *_pStepIndicator;  // "Step 2 of 5"
    int _currentStep, _totalSteps;

    CAANextStepNotification   _NextNotif;
    CAABackStepNotification   _BackNotif;
    CAAFinishStepNotification _FinishNotif;

    void Build() {
        // ... 创建 panels/buttons ...
        AddAnalyseNotificationCB(_pNextBtn, _pNextBtn->GetPushBActivateNotification(),
            (CATCommandMethod)&WizardDlg::OnButton, (CATCommandClientData)ACTION_NEXT);
        AddAnalyseNotificationCB(_pBackBtn, _pBackBtn->GetPushBActivateNotification(),
            (CATCommandMethod)&WizardDlg::OnButton, (CATCommandClientData)ACTION_BACK);
    }

    void OnButton(CATCommand *iFrom, CATNotification *iNotif, CATCommandClientData iData) {
        int action = CATPtrToINT32(iData);
        bool isLast = (_currentStep == _totalSteps - 1);
        switch (action) {
            case ACTION_NEXT:
                SendNotification(GetFather(), isLast ? &_FinishNotif : &_NextNotif);
                break;
            case ACTION_BACK:
                SendNotification(GetFather(), &_BackNotif);
                break;
        }
    }

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

### Command 端（状态机）

```cpp
void ExportWizardCmd::BuildGraph() {
    // Panel 索引映射
    // Panel 0 = Format Select
    // Panel 1 = Options
    // Panel 2 = Confirm & Execute

    _pNextAgent   = new CATDialogAgent("NextId");
    _pBackAgent   = new CATDialogAgent("BackId");
    _pFinishAgent = new CATDialogAgent("FinishId");

    _pNextAgent->AcceptOnNotify(_pDlg, "CAANextStepNotification");
    _pBackAgent->AcceptOnNotify(_pDlg, "CAABackStepNotification");
    _pFinishAgent->AcceptOnNotify(_pDlg, "CAAFinishStepNotification");

    CATDialogState *pState1 = GetInitialState("Step1");
    CATDialogState *pState2 = AddDialogState("Step2");
    CATDialogState *pState3 = AddDialogState("Step3");

    pState1->AddDialogAgent(_pNextAgent);
    pState2->AddDialogAgent(_pNextAgent);
    pState2->AddDialogAgent(_pBackAgent);
    pState3->AddDialogAgent(_pBackAgent);
    pState3->AddDialogAgent(_pFinishAgent);

    AddTransition(pState1, pState2,
        IsOutputSetCondition(_pNextAgent),
        Action((ActionMethod)&ExportWizardCmd::GoToStep2));

    AddTransition(pState2, pState1,
        IsOutputSetCondition(_pBackAgent),
        Action((ActionMethod)&ExportWizardCmd::GoToStep1));

    AddTransition(pState2, pState3,
        IsOutputSetCondition(_pNextAgent),
        Action((ActionMethod)&ExportWizardCmd::GoToStep3));

    AddTransition(pState3, pState2,
        IsOutputSetCondition(_pBackAgent),
        Action((ActionMethod)&ExportWizardCmd::GoToStep2));

    // Finish = 执行操作
    AddTransition(pState3, NULL,
        IsOutputSetCondition(_pFinishAgent),
        Action((ActionMethod)&ExportWizardCmd::ExecuteExport));
}
```

## 关键设计点

1. **Panel 预创建** — 所有步骤的 Panel 在 `Build()` 中创建，运行时只切换可见性
2. **状态机驱动** — 用 `CATStateCommand` + `AddDialogState` + `AddTransition`
3. **按钮不直接参与条件判断** — 按钮通过 `AddAnalyseNotificationCB` 触发自定义 `CATNotification`，`CATDialogAgent` 通过 `AcceptOnNotify` 监听该通知，`IsOutputSetCondition` 只认 agent，不认按钮或按钮的通知
4. **最后一步复用 Next 按钮** — 改标题为 "Finish"，Dialog 内部据此发不同的通知（`_NextNotif` vs `_FinishNotif`）
5. **Back 按钮可用性** — 第一步禁用，其他步骤启用
6. **步骤指示器** — 始终显示 "Step X of Y"
7. **数据跨步骤保留** — 数据存在 Command 成员变量中，不因 Panel 切换丢失

## AI 生成规则

- [ ] 用 `CATStateCommand`（不是 `CATCommand`）实现向导
- [ ] 所有 Panel 在 Build() 预创建
- [ ] 每步对应一个 `CATDialogState`
- [ ] 按钮点击通过 `AddAnalyseNotificationCB` + 自定义 `CATNotification` 子类转发给父 Command，不要假设存在 `GetXxxNotification()` 便捷方法直接返回可用于 `IsOutputSetCondition` 的对象
- [ ] Command 端为每个逻辑事件创建 `CATDialogAgent`，用 `AcceptOnNotify(pDlg, "自定义通知类名")` 绑定
- [ ] 用 `AddDialogAgent(pAgent)` 把 agent 挂到相关的 `CATDialogState` 上
- [ ] 用 `AddTransition` + `IsOutputSetCondition(pAgent)` 定义步骤间跳转（条件参数是 agent，不是按钮或通知）
- [ ] 最后一步的 Next 按钮改为 Finish，Dialog 内部据此发送不同的自定义通知
- [ ] 第一步禁用 Back 按钮
- [ ] 向导结束必须调用 `RequestDelayedDestruction()`
