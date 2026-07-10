---
id: infra.lifecycle
title: Command Lifecycle
category: knowledge
domain: infrastructure
keywords: [lifecycle, activate, desactivate, state, constructor, destructor, cleanup]
apis: [CATStateCommand, CATStatusChangeRC]
requires: []
patterns: [ui.wizard]
examples: []
release: [R19, R28]
tags: [infrastructure, lifecycle, command]
---

# CAA Command Lifecycle

## StateCommand Lifecycle

```
用户点击命令
    ↓
① GetState()          ← 检查激活条件（返回 CATStaEnable/CATStaDisable）
    ↓
② Condition()         ← 检查输入参数有效性 → 返回 S_OK/S_FALSE
    ↓
③ Activate()          ← 命令激活，开始交互（setup agent, 启动事件监听）
    ↓
   [用户操作中...]
    ↓
④ Desactivate()       ← 命令结束，清理资源
    ↓
⑤ Cancel()            ← 用户取消（ESC），中间状态清理
```

### GetState()

```cpp
CATStatusChangeRC ATAutoRenameCmd::GetState(CATNotification *iNotif,
                                              CATCommandCompletion *iCompl) {
    // 检查是否有选中对象
    CATFrmEditor *pEditor = CATFrmEditor::GetCurrentEditor();
    if (!pEditor) return CATStaDisable;
    
    CATPathElement path = pEditor->GetUIActiveObject();
    if (path.GetSize() == 0) return CATStaDisable;
    
    return CATStaEnable;  // 或者是 CATStaMenuBar / CATStaDialogAvailable
}
```

**法则**：
- `CATStaDisable` — 不显示或灰掉
- `CATStaEnable` — 可点击
- `CATStaMenuBar` — 仅在菜单栏显示
- 不要在 GetState 里做耗时操作

### Condition()

```cpp
CATBoolean ATAutoRenameCmd::Condition() {
    // 验证输入参数是否合法
    CATFrmEditor *pEditor = CATFrmEditor::GetCurrentEditor();
    if (!pEditor) return FALSE;
    
    CATPathElement *pPath = pEditor->GetUIActiveObject();
    if (!pPath || pPath->GetSize() == 0) return FALSE;
    
    return TRUE;  // 条件满足，进入 Activate
}
```

**法则**：
- 返回 `TRUE` → 进入 `Activate()`
- 返回 `FALSE` → 命令不启动
- 此处可做轻量验证（不要长时间操作）

### Activate()

```cpp
CATStatusChangeRC ATAutoRenameCmd::Activate(CATCommand *iFromClient,
                                              CATNotification *iNotif) {
    // 1. 初始化 Agent
    _pAgent = new CATFeatureImportAgent("CATPart");
    _pAgent->AddOrderedType("CATISpecObject");
    
    // 2. 创建对话框
    _pDlg = new ATAutoRenameDlg(this);
    _pDlg->Build();
    _pDlg->SetVisibility(CATDlgShow);
    
    // 3. 绑定回调
    AddAnalyseNotificationCB(this, _pDlg->GetApplyNotification(),
                              (CATCommandMethod)&ATAutoRenameCmd::OnApply,
                              NULL);
    
    return CATStatusChangeContinue;
}
```

**法则**：
- 创建 Agent（选择器）
- 创建和显示 Dialog
- 绑定事件回调
- 返回 `CATStatusChangeContinue`

### Desactivate()

```cpp
CATStatusChangeRC ATAutoRenameCmd::Desactivate(CATCommand *iFromClient,
                                                 CATNotification *iNotif) {
    // 1. 清理 Dialog
    if (_pDlg) {
        _pDlg->SetVisibility(CATDlgHide);
        _pDlg->RequestDelayedDestruction();
        _pDlg = NULL;
    }
    
    // 2. 清理 Agent
    if (_pAgent) {
        _pAgent->RemoveAllElementaryFilters();
        _pAgent->Release();
        _pAgent = NULL;
    }
    
    return CATStatusChangeCompleted;
}
```

**法则**：
- 释放 Dialog（RequestDelayedDestruction）
- 释放 Agent（Release）
- 置空指针
- 返回 `CATStatusChangeCompleted`

### Cancel()

```cpp
CATStatusChangeRC ATAutoRenameCmd::Cancel(CATCommand *iFromClient,
                                            CATNotification *iNotif) {
    // 取消 = 清理 + 不保存结果
    Desactivate(iFromClient, iNotif);
    return CATStatusChangeCanceled;
}
```

**法则**：
- 通常直接调用 `Desactivate()`
- 如果 Desactivate 有副作用（写入了数据），Cancel 需要额外清理
- 返回 `CATStatusChangeCanceled`

## 常见生命周期模式

### 模式 1：Agent + Dialog（最常见）

```
Activate → 创建 Agent → 用户选择 → 点 Apply → Desactivate
         → 用户取消 → Cancel
```

适用于：选择特征然后执行操作

### 模式 2：即时命令（无 Agent）

```
Activate → 直接执行 → Desactivate
```

适用于：`undo`、`redo`、`copy/paste`

### 模式 3：模态命令

```
Activate → Show modal dialog → 用户确认/logic → Desactivate
```

适用于：需要复杂参数输入的操作

## AI 生成规则

生成命令代码时必须包含：

- [ ] `GetState()` 方法（至少返回 `CATStaEnable`）
- [ ] `Condition()` 方法
- [ ] `Activate()` 方法
- [ ] `Desactivate()` 方法
- [ ] `Cancel()` 方法（通常委托给 Desactivate）
- [ ] 所有成员指针初始化为 NULL
- [ ] 析构函数清理资源
