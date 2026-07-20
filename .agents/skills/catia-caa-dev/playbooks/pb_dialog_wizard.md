---
id: pb.dialog_wizard
title: Dialog Wizard Pattern / 对话框向导模式
category: playbook
domain: ui
keywords: [wizard, dialog, step, back, next, finish, state command, multi-step, form, CATStateCommand, AddDialogState, AddTransition]
capabilities: [cap.selection, cap.parameter_system]
apis: [CATStateCommand, CATDialogState, CATDialogAgent, CATPathElementAgent, CATDlgDialog, CATDlgFrame, CATDlgPushButton]
frameworks: [DialogEngine, ApplicationFrame, Dialog]
difficulty: intermediate
effort: medium
release: [R19, R28]
tags: [playbook, dialog, wizard, state command, UI]
---

# Dialog Wizard Pattern (对话框向导模式)

实现多步骤向导对话框：Back/Next/Finish/Cancel，每个步骤独立状态，数据跨步骤传递。

完整的状态机架构、Panel 切换模板见 `patterns/ui/wizard.md`；本 playbook 聚焦于选择+参数编辑这类具体场景下的状态转换写法。

## 目标

创建一个标准的 CAA 多步骤向导：步骤1选对象 → 步骤2设参数 → 步骤3预览确认 → Finish 执行。

## 前置条件

- 已创建 `CATStateCommand` 子类骨架
- 每个步骤对应一个 `CATDialogState`（由 `GetInitialState`/`AddDialogState` 创建，不是自定义枚举）

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.selection` | 步骤1：用户在3D中选择对象（`CATPathElementAgent`） |
| `cap.parameter_system` | 步骤2：读取/设置参数值 |

## 实现步骤

1. **在构造函数或 `BuildGraph()` 中创建状态**：`GetInitialState("Step1")` 取初始状态，`AddDialogState("StepN")` 创建后续状态，**把返回的 `CATDialogState*` 存成 Command 成员变量**（没有 `GetState(enum)` 这种按枚举取状态的方法）
2. **`BuildGraph()` 用 `AddTransition(source, target, condition, action)` 定义跳转**：`AddTransition` 的参数是"源状态 + 目标状态 + 条件 + 动作"，不是"目标状态 + 判定函数 + 按钮对象"
3. **条件用 `IsOutputSetCondition(pAgent)`，参数是 `CATDialogAgent*`，不是按钮通知**：按钮点击先用 `AddAnalyseNotificationCB` 在 Dialog 里转发成自定义 `CATNotification` 子类，Command 端再用 `CATDialogAgent::AcceptOnNotify(pDlg, "自定义通知类名")` 绑定并 `AddDialogAgent()` 挂到状态上——`IsOutputSetCondition` 检测的是这个 agent 有没有被 valued，直接传 `GetPushBActivateNotification()` 的返回值（`CATNotification*`）类型不匹配，是错误写法。完整机制和示例见 `patterns/ui/wizard.md`
4. **步骤1激活选择过滤**：用 `CATPathElementAgent::AddElementType(CATClassId)` 限制可选类型（如 `IID_CATIPart`），通过 `AddCSOClient()` 挂接；没有 `CATISelectionAgent`/`CATPartType` 这类接口和枚举
5. **数据传递**：使用 Command 成员变量在状态间共享数据
6. **Finish 后触发重算**：调用 `CATISpecObject::Update()`（不是 `CATIModelEvents::Dispatch()`）

## 状态转换图

```text
[Start] → Step1 (选择对象)
              │ Next（选择有效）
              ▼
         Step2 (设置参数)
              │ Next（参数有效）  │ Back
              ▼                   ▲
         Step3 (预览确认)---------┘
              │ Finish
              ▼
           [Execute + Update]
```

## 关键代码

```cpp
class MyWizardCmd : public CATStateCommand {
    CATDeclareClass;
public:
    MyWizardCmd();
    virtual void BuildGraph();
    void OnSelect(CATCommand*, CATNotification*, CATCommandClientData);
    void ExecuteWizard(CATCommand*, CATNotification*, CATCommandClientData);

private:
    CATDialogState   *_pStep1, *_pStep2, *_pStep3;
    MyWizardDlg      *_pDlg;
    CATDialogAgent   *_pNextAgent, *_pBackAgent, *_pFinishAgent;
    CATPathElementAgent *_pSelectAgent;
    CATISpecObject_var  _spSelected;
};

void MyWizardCmd::BuildGraph() {
    // Dialog 内部把 Next/Back/Finish 按钮点击转发成自定义通知
    // （AddAnalyseNotificationCB + SendNotification，见 patterns/ui/wizard.md）
    _pNextAgent   = new CATDialogAgent("NextId");
    _pBackAgent   = new CATDialogAgent("BackId");
    _pFinishAgent = new CATDialogAgent("FinishId");
    _pNextAgent->AcceptOnNotify(_pDlg, "CAANextStepNotification");
    _pBackAgent->AcceptOnNotify(_pDlg, "CAABackStepNotification");
    _pFinishAgent->AcceptOnNotify(_pDlg, "CAAFinishStepNotification");

    _pStep1 = GetInitialState("Step1");
    _pStep2 = AddDialogState("Step2");
    _pStep3 = AddDialogState("Step3");

    _pStep1->AddDialogAgent(_pNextAgent);
    _pStep2->AddDialogAgent(_pNextAgent);
    _pStep2->AddDialogAgent(_pBackAgent);
    _pStep3->AddDialogAgent(_pBackAgent);
    _pStep3->AddDialogAgent(_pFinishAgent);

    // Step1 -> Step2：Next 按钮触发，选择有效才放行
    AddTransition(_pStep1, _pStep2,
        IsOutputSetCondition(_pNextAgent),
        NULL);

    // Step2 -> Step1：Back
    AddTransition(_pStep2, _pStep1,
        IsOutputSetCondition(_pBackAgent),
        NULL);

    // Step2 -> Step3：Next（参数校验建议在 OnApply 回调里做，转换条件保持简单）
    AddTransition(_pStep2, _pStep3,
        IsOutputSetCondition(_pNextAgent),
        NULL);

    // Step3 -> Step2：Back
    AddTransition(_pStep3, _pStep2,
        IsOutputSetCondition(_pBackAgent),
        NULL);

    // Step3 -> 结束（target=NULL 表示命令结束）：Finish 触发实际执行动作
    AddTransition(_pStep3, NULL,
        IsOutputSetCondition(_pFinishAgent),
        Action((ActionMethod)&MyWizardCmd::ExecuteWizard, NULL, NULL, NULL));
}

CATStatusChangeRC MyWizardCmd::Activate(CATCommand *iFromClient,
                                          CATNotification *iNotif) {
    _pDlg = new MyWizardDlg(this);
    _pDlg->Build();
    _pDlg->SetVisibility(CATDlgShow);

    // 步骤1：限制只能选 Part（没有 CATISelectionAgent/CATPartType 这类东西）
    _pSelectAgent = new CATPathElementAgent("WizardSelect");
    _pSelectAgent->AddElementType(IID_CATIPart);
    AddCSOClient(_pSelectAgent);

    return CATStatusChangeRCCompleted;
}

void MyWizardCmd::OnSelect(CATCommand *iCmd, CATNotification *iNotif,
                            CATCommandClientData iUsefulData) {
    CATPathElement *pPath = _pSelectAgent->GetValue();
    if (!pPath) return;
    CATBaseUnknown *pObj = pPath->FindElement(IID_CATISpecObject);
    _spSelected = pObj;
}

void MyWizardCmd::ExecuteWizard(CATCommand *iCmd, CATNotification *iNotif,
                                 CATCommandClientData iUsefulData) {
    // ... 应用参数、创建/修改特征 ...
    if (NULL_var != _spSelected) {
        _spSelected->Update();   // 真实触发重算入口，见 pb.batch_update_save
    }
    RequestDelayedDestruction();
}
```

## 注意事项

- 每个状态独立管理 Panel 可见性（参见 `patterns/ui/wizard.md` 的 `ShowPanel` 模式），避免状态间 UI 残留
- 状态数据通过 Command 成员变量传递，不要使用全局变量
- Back 返回时保留上一步的用户输入（缓存而非重置），可结合 `knowledge/ui/dialog_dataflow.md` 的持久化偏好模式
- Cancel 在所有步骤都应可用（`CATStateCommand` 有内建的 `GetCancelState()`，无需自己在每个状态里手动加 Cancel 转换）
- Finish 执行后触发重算用 `CATISpecObject::Update()`，**不存在** `CATIModelEvents::Dispatch()` 这个便捷更新入口（`CATIModelEvents` 是通知转发接口，`Dispatch(CATNotification&)` 分发的是通用通知对象，不是"触发 Update"的专用方法）
- 选择相关的 Agent/回调细节参见 `knowledge/ui/event_patterns.md`；参数读写细节参见 `capabilities/parameter-system.md`

## 相关 Playbook

- `pb.create_context_menu` — Wizard 可通过右键菜单触发启动
- `pb.batch_update_save` — Finish 后触发 Update 的完整真实机制
