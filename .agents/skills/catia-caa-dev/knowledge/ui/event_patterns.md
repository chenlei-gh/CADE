---
id: ui.event_patterns
title: Event & Notification Patterns
category: knowledge
domain: ui
keywords: [event, callback, notification, agent, cleanup, AddAnalyseNotificationCB, CSO]
apis: [CATNotification, CATPathElementAgent, AddAnalyseNotificationCB, AddCSOClient, CATCommandMethod]
requires: [ui.dialog]
patterns: [ui.dynamic_form]
examples: []
release: [R19, R28]
tags: [ui, event, callback]
---

# CAA Event & Notification Patterns

## 事件绑定基本模式

```cpp
CATStatusChangeRC MyCmd::Activate(CATCommand *iFromClient,
                                    CATNotification *iNotif) {
    // 1. 创建 Dialog
    _pDlg = new MyDlg(this);
    _pDlg->Build();
    _pDlg->SetVisibility(CATDlgShow);

    // 2. 绑定按钮事件
    AddAnalyseNotificationCB(this,
        _pDlg->GetApplyBtn()->GetPushBActivateNotification(),
        (CATCommandMethod)&MyCmd::OnApply, NULL);

    AddAnalyseNotificationCB(this,
        _pDlg->GetCancelBtn()->GetPushBActivateNotification(),
        (CATCommandMethod)&MyCmd::OnCancel, NULL);

    // 3. 绑定选择事件（选择器 Agent 用 CATPathElementAgent，非 CATFeatureImportAgent）
    _pAgent = new CATPathElementAgent("PathEltSelection");
    _pAgent->AddElementType(IID_CATISpecObject);
    AddCSOClient(_pAgent);

    return CATStatusChangeRCCompleted;
}
```

> ⚠️ **重要修正**：`CATFeatureImportAgent`不具备 `AddOrderedType()` 方法（它自身只有 `HowManyElementsCreated`/`SetAgentBehavior`/`SetImportApplicativeId` 三个方法，专用于导入/创建特征场景）。普通选择场景应使用 `CATPathElementAgent`，其方法是 `AddElementType(CATClassId)`（不是 `AddOrderedType`）。

## 回调签名规范

```cpp
// 标准回调签名（CATCommandMethod 定义于 CATCommand.h）
// typedef void (CATBaseUnknown::*CATCommandMethod)(CATCommand*, CATNotification*, CATCommandClientData)
void OnAction(CATCommand *iCmd,
              CATNotification *iNotif,
              CATCommandClientData iUsefulData);

// iCmd:    发布通知的命令
// iNotif:  通知对象（可获取来源）
// iUsefulData: 绑定时传入的第 4 参数（void*）
```

> ⚠️ **重要修正**：回调的真实返回值是 `void`（不是 `CATStatusChangeRC`），第三参数类型是 `CATCommandClientData`（实际上就是 `void*`），**不存在** `CATCommandClientInfo` 这个类型。回调无需—也无法—通过返回值控制命令状态机；对话框关闭等操作需在回调内部主动调用（如 `RequestDelayedDestruction()`）。

## 常见事件类型

### Dialog 按钮事件

```cpp
// Apply 按钮（回调无返回值，签名为 CATCommandMethod 真实签名）
void OnApply(CATCommand *iCmd, CATNotification *iNotif,
             CATCommandClientData iUsefulData) {
    CATUnicodeString name = _pDlg->GetNewName();
    HRESULT hr = ExecuteRename(name);
    
    if (SUCCEEDED(hr)) {
        // 成功 → 可以关闭对话框
        RequestDelayedDestruction();
    }
    // 失败 → 保持对话框打开，不需要任何返回值来“继继等待”
}

// Cancel 按钮
void OnCancel(CATCommand *iCmd, CATNotification *iNotif,
              CATCommandClientData iUsefulData) {
    RequestDelayedDestruction();
}
```

### 选择事件

```cpp
// 注意：CATPathElementAgent 没有 GetPathElement()/SetHighlightObject()，
// 单选取值用 GetValue()（直接返回 CATPathElement*）；
// CATPathElement 取对象的真实方法是 FindElement(IID&)，直接返回 CATBaseUnknown*（无 HRESULT）
void OnSelect(CATCommand *iCmd, CATNotification *iNotif,
              CATCommandClientData iUsefulData) {
    if (!_pAgent) return;
    
    // 获取选中的元素
    CATPathElement *pPath = _pAgent->GetValue();
    if (!pPath) return;

    CATBaseUnknown *pObj = pPath->FindElement(IID_CATISpecObject);
    CATISpecObject_var spObj = pObj;
    if (NULL_var != spObj) {
        // 更新 UI
        _pDlg->SetSelectedName(spObj->GetName());
    }
}
```

### Combo 变化事件

```cpp
// 绑定
_pModeCombo = new CATDlgCombo(pFrame, "Mode");
_pModeCombo->AddItem("Prefix");
_pModeCombo->AddItem("Suffix");
AddAnalyseNotificationCB(this,
    _pModeCombo->GetComboNotification(),
    (CATCommandMethod)&MyCmd::OnModeChanged, NULL);

// 回调
void OnModeChanged(CATCommand *iCmd, CATNotification *iNotif,
                    CATCommandClientData iUsefulData) {
    int sel = _pModeCombo->GetSelect();
    // 根据选择更新 UI...
}
```

### Radio 组互斥

```cpp
void MyDlg::Build() {
    CATDlgFrame *pGroup = new CATDlgFrame(pParent, "Group",
        CATDlgFraGroupFrame | CATDlgGridLayout);
    pGroup->SetTitle("Mode");

    _pRB1 = new CATDlgRadioButton(pGroup, "RB1", "Option A");
    _pRB2 = new CATDlgRadioButton(pGroup, "RB2", "Option B");
    _pRB1->SetState(CATDlgCheck);  // 默认选中
}

// 手动互斥逻辑
void OnRadioChanged(CATCommand *iCmd, CATNotification *iNotif,
                     CATCommandClientData iUsefulData) {
    CATDlgRadioButton *pSrc = (CATDlgRadioButton*)iNotif->GetSource();
    
    if (pSrc == _pRB1 && _pRB1->GetState() == CATDlgCheck) {
        _pRB2->SetState(CATDlgUncheck);
    } else if (pSrc == _pRB2 && _pRB2->GetState() == CATDlgCheck) {
        _pRB1->SetState(CATDlgUncheck);
    }
}
```

## 双 Agent 模式

同时监控两个维度的输入：

```cpp
// 注意：选择 Agent 应用 CATPathElementAgent，其 AddElementType(CATClassId) 要求传入
// 接口的 CATClassId（如 IID_CATISpecObject）而非字符串；CATPathElementAgent 没有 SetColor()，
// 多 Agent 区分需依靠 SetBehavior() 的光标提示模式或 UI 上的其他提示，而不是选择颜色
CATStatusChangeRC MyCmd::Activate(CATCommand *iFromClient,
                                   CATNotification *iNotif) {
    // Agent 1: 选择要重命名的对象
    _pSelectAgent = new CATPathElementAgent("PathEltSelect");
    _pSelectAgent->AddElementType(IID_CATISpecObject);
    AddCSOClient(_pSelectAgent);

    // Agent 2: 选择参考对象（如模板）
    _pRefAgent = new CATPathElementAgent("PathEltRef");
    _pRefAgent->AddElementType(IID_CATIPart);
    AddCSOClient(_pRefAgent);

    return CATStatusChangeRCCompleted;
}
```

## 事件链：一个操作触发另一个

```cpp
void OnSelect(CATCommand *iCmd, CATNotification *iNotif,
              CATCommandClientData iUsefulData) {
    // 选择对象 → 自动预填充名称
    CATISpecObject_var spObj = GetSelectedObject();
    if (NULL_var != spObj) {
        CATUnicodeString currentName = GetFeatureName(spObj);
        _pDlg->SetCurrentName(currentName);
        _pDlg->SuggestNewName(currentName);  // 自动建议新名字
    }
}
```

## 资源清理

```cpp
CATStatusChangeRC MyCmd::Desactivate(CATCommand *iFromClient,
                                       CATNotification *iNotif) {
    // 1. 解绑 Agent 事件
    if (_pSelectAgent) {
        RemoveCSOClient(_pSelectAgent);
        _pSelectAgent->Release();
        _pSelectAgent = NULL;
    }

    // 2. 清理 Dialog
    if (_pDlg) {
        _pDlg->SetVisibility(CATDlgHide);
        _pDlg->RequestDelayedDestruction();
        _pDlg = NULL;
    }

    return CATStatusChangeRCCompleted;
}
```

## AI 生成规则

- [ ] 回调用 `(CATCommandMethod)&ClassName::MethodName` 绑定
- [ ] 回调方法签名为 `void Method(CATCommand*, CATNotification*, CATCommandClientData)`（**无**返回值，非 `CATStatusChangeRC`）
- [ ] Radio 组手动实现互斥
- [ ] `Activate`/`Desactivate`/`Cancel` 返回 `CATStatusChangeRCCompleted`（成功）/`CATStatusChangeRCAborted`（失败）
- [ ] Desactivate 中解绑所有事件
- [ ] 选择 Agent 用 `CATPathElementAgent`，方法是 `AddElementType(CATClassId)`
- [ ] 用 `AddCSOClient` 绑定选择 Agent
- [ ] 用 `RemoveCSOClient` 解绑
