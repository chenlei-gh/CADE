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
        _pDlg->GetApplyBtn()->GetPushNotification(),
        (CATCommandMethod)&MyCmd::OnApply, NULL);

    AddAnalyseNotificationCB(this,
        _pDlg->GetCancelBtn()->GetPushNotification(),
        (CATCommandMethod)&MyCmd::OnCancel, NULL);

    // 3. 绑定选择事件
    _pAgent = new CATFeatureImportAgent("CATPart");
    _pAgent->AddOrderedType("CATISpecObject");
    AddCSOClient(_pAgent);

    return CATStatusChangeContinue;
}
```

## 回调签名规范

```cpp
// 标准回调签名
CATStatusChangeRC OnAction(void *iData,
                            CATNotification *iNotif,
                            CATCommandClientInfo *iInfo);

// iData:   用户数据（绑定时的第4参数）
// iNotif:  通知对象（可获取来源）
// iInfo:   命令客户端信息
```

## 常见事件类型

### Dialog 按钮事件

```cpp
// Apply 按钮
CATStatusChangeRC OnApply(void *iData, CATNotification *iNotif,
                           CATCommandClientInfo *iInfo) {
    CATUnicodeString name = _pDlg->GetNewName();
    HRESULT hr = ExecuteRename(name);
    
    if (SUCCEEDED(hr)) {
        // 成功 → 可以关闭对话框
        RequestDelayedDestruction();
        return CATStatusChangeCompleted;
    }
    
    // 失败 → 继续等待
    return CATStatusChangeContinue;
}

// Cancel 按钮
CATStatusChangeRC OnCancel(void *iData, CATNotification *iNotif,
                             CATCommandClientInfo *iInfo) {
    RequestDelayedDestruction();
    return CATStatusChangeCanceled;
}
```

### 选择事件

```cpp
CATStatusChangeRC OnSelect(void *iData, CATNotification *iNotif,
                             CATCommandClientInfo *iInfo) {
    if (!_pAgent) return CATStatusChangeContinue;
    
    // 获取选中的特征
    CATPathElement *pPath = _pAgent->GetPathElement();
    CATISpecObject_var spObj = NULL_var;
    HRESULT hr = pPath->FindElement(IID_CATISpecObject, (void**)&spObj);
    
    if (SUCCEEDED(hr) && NULL_var != spObj) {
        // 高亮选中对象
        _pAgent->SetHighlightObject(spObj);
        
        // 更新 UI
        _pDlg->SetSelectedName(spObj->GetName());
    }
    
    return CATStatusChangeContinue;
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
CATStatusChangeRC OnModeChanged(void *iData, CATNotification *iNotif,
                                  CATCommandClientInfo *iInfo) {
    int sel = _pModeCombo->GetSelect();
    // 根据选择更新 UI...
    return CATStatusChangeContinue;
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
CATStatusChangeRC OnRadioChanged(void *iData, CATNotification *iNotif,
                                   CATCommandClientInfo *iInfo) {
    CATDlgRadioButton *pSrc = (CATDlgRadioButton*)iNotif->GetSource();
    
    if (pSrc == _pRB1 && _pRB1->GetState() == CATDlgCheck) {
        _pRB2->SetState(CATDlgUncheck);
    } else if (pSrc == _pRB2 && _pRB2->GetState() == CATDlgCheck) {
        _pRB1->SetState(CATDlgUncheck);
    }
    
    return CATStatusChangeContinue;
}
```

## 双 Agent 模式

同时监控两个维度的输入：

```cpp
CATStatusChangeRC MyCmd::Activate(...) {
    // Agent 1: 选择要重命名的对象
    _pSelectAgent = new CATFeatureImportAgent("CATPart");
    _pSelectAgent->AddOrderedType("CATISpecObject");
    AddCSOClient(_pSelectAgent);

    // Agent 2: 选择参考对象（如模板）
    _pRefAgent = new CATFeatureImportAgent("CATPart");
    _pRefAgent->AddOrderedType("CATIPart");
    _pRefAgent->SetColor(0, 0, 255);  // 蓝色区分
    AddCSOClient(_pRefAgent);

    return CATStatusChangeContinue;
}
```

## 事件链：一个操作触发另一个

```cpp
CATStatusChangeRC OnSelect(void *iData, CATNotification *iNotif,
                             CATCommandClientInfo *iInfo) {
    // 选择对象 → 自动预填充名称
    CATISpecObject_var spObj = GetSelectedObject();
    if (NULL_var != spObj) {
        CATUnicodeString currentName = GetFeatureName(spObj);
        _pDlg->SetCurrentName(currentName);
        _pDlg->SuggestNewName(currentName);  // 自动建议新名字
    }
    return CATStatusChangeContinue;
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

    return CATStatusChangeCompleted;
}
```

## AI 生成规则

- [ ] 回调用 `(CATCommandMethod)&ClassName::MethodName` 绑定
- [ ] Radio 组手动实现互斥
- [ ] 事件回调返回 `CATStatusChangeContinue`（继续）/ `CATStatusChangeCompleted`（结束）
- [ ] Desactivate 中解绑所有事件
- [ ] 用 `AddCSOClient` 绑定选择 Agent
- [ ] 用 `RemoveCSOClient` 解绑
- [ ] 双 Agent 模式用不同颜色区分
