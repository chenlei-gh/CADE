---
id: fp.dialog_cancel_not_desactivate
title: Dialog Close Goes Through Cancel Not Desactivate / 对话框关闭走 Cancel 而非 Desactivate
category: knowledge
domain: failure_patterns
severity: runtime_error
apis: [CATDlgDialog, CATStateCommand, CATDialogAgent, RequestDelayedDestruction]
frameworks: [DialogEngine]
keywords: [dialog, close, Cancel, Desactivate, not closing, won't close, RequestDelayedDestruction, SetVisibility]
tags: [failure_pattern, runtime, ui, dialog, lifecycle]
release: [R19, R28]
---
# Dialog Close Goes Through Cancel Not Desactivate / 对话框关闭走 Cancel 而非 Desactivate

## 症状

对话框可以正常打开，但点击对话框的"关闭"按钮（或标题栏的 ×）没有任何反应——对话框仍然停留在屏幕上，无法关闭。

## 原因

状态机用 `AddTransition(pDlgState, NULL, IsOutputSetCondition(_pDlgAgent))` 之类的写法把对话框关闭映射为"回到 NULL 结束态"，代码里只在 `Desactivate()` 里做了隐藏/销毁：

```cpp
// ❌ 错误：只处理了 Desactivate，Cancel 是空的
CATStatusChangeRC MyCmd::Desactivate(CATCommand *iFromClient,
                                       CATNotification *iNotif) {
    if (_pDialog) {
        _pDialog->SetVisibility(CATDlgHide);
        _pDialog->RequestDelayedDestruction();
        _pDialog = NULL;
    }
    return CATStatusChangeRCCompleted;
}

CATStatusChangeRC MyCmd::Cancel(CATCommand *iFromClient,
                                  CATNotification *iNotif) {
    // 空实现——点击对话框关闭按钮时框架实际调的是这里！
    return CATStatusChangeRCAborted;
}
```

通过在 `Activate`/`Desactivate`/`Cancel` 三个方法里加日志实机追踪确认：**用户点击对话框的关闭/取消按钮时，框架实际调用的是 `Cancel()`，不是 `Desactivate()`**。`Desactivate()` 对应的是命令正常完成（比如用户点了 Apply/OK 且状态机走到了正常结束态）。只实现 `Desactivate()` 会导致关闭按钮完全没有效果。

## 修复

`Desactivate()` 和 `Cancel()` 都要隐藏对话框；真正的销毁只放在析构函数里：

```cpp
CATStatusChangeRC MyCmd::Desactivate(CATCommand *iFromClient,
                                       CATNotification *iNotif) {
    if (_pDialog) {
        _pDialog->SetVisibility(CATDlgHide);   // 隐藏，不销毁
    }
    return CATStatusChangeRCCompleted;
}

CATStatusChangeRC MyCmd::Cancel(CATCommand *iFromClient,
                                  CATNotification *iNotif) {
    if (_pDialog) {
        _pDialog->SetVisibility(CATDlgHide);   // 隐藏，不销毁
    }
    return CATStatusChangeRCAborted;
}

MyCmd::~MyCmd() {
    if (_pDialog) {
        _pDialog->RequestDelayedDestruction();  // 真正的销毁只在这里
        _pDialog = NULL;
    }
}
```

参考官方样例：`CAADoc/CAADialogEngine.edu/CAADegGeoCommands.m/src/CAADegAnalysisNumericCmd.cpp`——`Cancel()` 和 `Desactivate()` 都只调用 `SetVisibility(CATDlgHide)`，`RequestDelayedDestruction()` 只出现在析构函数里。

**切勿在 `Cancel()`/`Desactivate()` 里直接 `delete _pDialog` 或调用非 delayed 的销毁**——对话框可能仍在处理待发的通知，直接销毁会导致崩溃或悬空指针。

## 预防规则

- [ ] `Cancel()` 和 `Desactivate()` 都必须隐藏对话框（`SetVisibility(CATDlgHide)`）
- [ ] 真正的对话框销毁（`RequestDelayedDestruction()`）只放在析构函数里，绝不放在 `Cancel()`/`Desactivate()`
- [ ] 禁止在 `Cancel()`/`Desactivate()` 里直接 `delete` 对话框指针
- [ ] 排查"对话框点关闭没反应"时，第一步检查 `Cancel()` 是否为空实现——关闭按钮触发的通常是 `Cancel()` 而不是 `Desactivate()`
- [ ] 用日志在 `Activate`/`Desactivate`/`Cancel` 三处打点，实机点击验证框架实际走的是哪条路径，不要凭假设编码

## 相关

- [dialog_patterns.md](../ui/dialog_patterns.md) — Dialog Widget 模式
- [lifecycle_patterns.md](../infrastructure/lifecycle_patterns.md) — Command 生命周期总览
