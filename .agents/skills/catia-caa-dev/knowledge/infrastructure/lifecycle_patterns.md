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
① Activate()          ← 命令激活，开始交互（setup agent, 启动事件监听）
    ↓
   [用户操作中...]
    ↓
② Desactivate()       ← 命令正常结束，清理资源
    ↓
③ Cancel()            ← 用户取消（ESC / 关闭按钮），中间状态清理
```

> ⚠️ 上一个版本的图里还列了 `GetState()` 和 `Condition()` 作为命令激活前的前置步骤，但这两个方法并不是 `CATCommand`/`CATStateCommand` 生命周期的部分（见下方说明），已从主流程图中删除，避免误导。

### GetState() — ⚠️ 未在 CAADoc 中找到官方依据，谨慎使用

> **注意**：在 `CAADoc` 官方参考手册中未找到任何 `GetState(CATNotification*, ...)` 类似签名的方法，也未找到 `CATStaEnable`/`CATStaDisable`/`CATStaMenuBar`/`CATStaDialogAvailable`/`CATCommandCompletion` 这些符号。这些符号目前无法验证其真实性，**不要直接使用下面的示例代码**。若需控制命令头的可用/不可用状态，已确认的官方机制是 `CATCommandHeader` 的 `BecomeAvailable()` / `BecomeUnavailable()` 方法，以及构造函数的 `iState` 参数（合法值 `CATFrmAvailable` / `CATFrmUnavailable`，定义在 `CATCommandHeader.h`）。

```cpp
// ✅ 已确认的官方控制命令可用性的方式（CATCommandHeader 方法）
void ATAutoRenameCmdHeader::UpdateAvailability() {
    CATFrmEditor *pEditor = CATFrmEditor::GetCurrentEditor();
    if (!pEditor) {
        BecomeUnavailable();
        return;
    }
    BecomeAvailable();
}
```

**法则**：
- 不要在此类方法里做耗时操作
- 若需要在命令头上实现动态启用/灰掉逻辑，优先参考 `CATCmdHeaderSensitivityMngt::SetSensitivity()`（`ApplicationFrame` 框架）

### Condition() — ⚠️ 同样未在 CAADoc 中找到作为 `CATCommand` 方法的依据

> **注意**：`Condition()` 在 CAADoc 中确实存在，但它是 `CATStateCommand::Condition(ConditionMethod, void*)`——用于**注册一个条件方法地址**以创建 `CATStateCondition` 对象（给 `AddTransition()` 用），**不是**一个你自己重写的无参无返回值方法。真实用法是：

```cpp
// ✅ 真实用法：在 BuildGraph() 中用 Condition() 包装一个条件回调方法
CATBoolean ATAutoRenameCmd::CheckHasSelection(void *iUsefulData) {
    CATPathElementAgent *pAgent = (CATPathElementAgent*)iUsefulData;
    return pAgent && pAgent->GetPathElement() ? TRUE : FALSE;
}

void ATAutoRenameCmd::BuildGraph() {
    // ...
    AddTransition(pStateA, pStateB,
        Condition((ConditionMethod)&ATAutoRenameCmd::CheckHasSelection, (void*)_pAgent));
}
```

**法则**：
- `ConditionMethod` 方法的真实签名是 `CATBoolean (CATCommand::*)(void *iData)`
- 返回 `TRUE`/`FALSE` 用于控制状态转换是否发生，不是控制命令是否启动

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
    
    return CATStatusChangeRCCompleted;
}
```

**法则**：
- 创建 Agent（选择器）
- 创建和显示 Dialog
- 绑定事件回调
- 返回 `CATStatusChangeRCCompleted`（`CATStatusChangeRC` 只有两个合法值：`CATStatusChangeRCCompleted` / `CATStatusChangeRCAborted`，不存在 "Continue" 这个值）

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
    
    return CATStatusChangeRCCompleted;
}
```

**法则**：
- 释放 Dialog（RequestDelayedDestruction）
- 释放 Agent（Release）
- 置空指针
- 返回 `CATStatusChangeRCCompleted`

### Cancel()

```cpp
CATStatusChangeRC ATAutoRenameCmd::Cancel(CATCommand *iFromClient,
                                            CATNotification *iNotif) {
    // 取消 = 清理 + 不保存结果
    Desactivate(iFromClient, iNotif);
    return CATStatusChangeRCCompleted;
}
```

**法则**：
- 通常直接调用 `Desactivate()`
- 如果 Desactivate 有副作用（写入了数据），Cancel 需要额外清理
- 返回 `CATStatusChangeRCCompleted`（`CATStatusChangeRC` 只有 Completed/Aborted 两个合法值，官方样例 `CAADegAnalysisNumericCmd::Cancel()` 返回的也是 `CATStatusChangeRCCompleted`）
- **⚠️ 用户点击 Dialog 的关闭/取消按钮时，框架实际调用的是 `Cancel()`，不是 `Desactivate()`**——两者都必须隐藏 Dialog（`SetVisibility(CATDlgHide)`），否则关闭按钮会没有反应，详见 [fp_dialog_cancel_not_desactivate.md](../failure_patterns/fp_dialog_cancel_not_desactivate.md)

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

- [ ] `Activate()` 方法
- [ ] `Desactivate()` 方法
- [ ] `Cancel()` 方法（通常委托给 Desactivate）
- [ ] 所有成员指针初始化为 NULL
- [ ] 析构函数清理资源
