---
id: fp.dialog_null_parent
title: Dialog NULL Parent / 对话框无父窗口不可见
category: knowledge
domain: failure_patterns
severity: runtime_error
apis: [CATDlgDialog, CATApplicationFrame]
frameworks: [DialogEngine, ApplicationFrame]
keywords: [dialog, parent, NULL, invisible, not showing, CATApplicationFrame, GetMainWindow]
tags: [failure_pattern, runtime, ui, dialog]
release: [R19, R28]
---
# Dialog NULL Parent / 对话框无父窗口不可见

## 症状

点击命令按钮后没有任何反应——不报错、不崩溃、也没有对话框弹出。日志显示 `Activate()` 和 `Build()` 都正常执行到底，`SetVisibility(CATDlgShow)` 也被调用了，但屏幕上什么都看不到。

## 原因

对话框构造时传入了 `NULL` 作为父窗口：

```cpp
// ❌ 错误：无父窗口
_pDialog = new MyDlg(NULL);
_pDialog->Build();
_pDialog->SetVisibility(CATDlgShow);
```

在 CATIA B28 下，没有父窗口的顶层 `CATDlgDialog` **不会被窗口管理器映射**——`SetVisibility(CATDlgShow)` 调用成功返回，但窗口实际从未显示。这是一个静默失败：没有异常、没有错误日志，只是"什么都没发生"。

## 修复

始终传入 `CATApplicationFrame::GetFrame()->GetMainWindow()` 作为对话框的父窗口：

```cpp
// MyCmd.cpp
#include "CATApplicationFrame.h"
#include "CATFrmWindow.h"

CATStatusChangeRC MyCmd::Activate(CATCommand *iFromClient,
                                    CATNotification *iNotif) {
    CATFrmWindow *pMainWindow = CATApplicationFrame::GetFrame()->GetMainWindow();

    // ✅ 正确：以主窗口为父窗口
    _pDialog = new MyDlg(pMainWindow);
    _pDialog->Build();
    _pDialog->SetVisibility(CATDlgShow);

    return CATStatusChangeRCCompleted;
}
```

参考官方样例：`CAADoc/CAADialogEngine.edu/CAADegGeoCommands.m/src/CAADegAnalysisNumericCmd.cpp`——对话框构造函数始终接收非空父窗口。

## 预防规则

- [ ] 对话框构造函数的父窗口参数禁止直接传 `NULL`
- [ ] 使用 `CATApplicationFrame::GetFrame()->GetMainWindow()` 作为顶层对话框的父窗口
- [ ] `SetVisibility(CATDlgShow)` 返回成功不代表对话框真的可见——实机点击验证是唯一可靠的确认方式
- [ ] 生成器模板中涉及 `new XxxDlg(...)` 的分支必须默认注入主窗口获取代码
