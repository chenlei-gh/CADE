---
id: ui.dynamic_form
title: Dynamic Form Layout
category: pattern
domain: ui
keywords: [dialog, dynamic, show, hide, combo, mode, sensitivity, visibility, conditional]
apis: [CATDlgDialog, CATDlgCombo, CATDlgFrame, SetVisibility, SetSensitivity]
requires: [ui.dialog]
patterns: []
examples: []
release: [R19, R28]
tags: [pattern, ui, layout, dynamic, conditional]
---

# Dynamic Form Pattern (动态表单模式)

根据用户选择，动态显示/隐藏不同的控件组。

## 适用场景

- 多模式批量操作（如 Prefix/Suffix/Replace 切换）
- 条件配置（选择不同导出格式 → 显示不同配置项）
- 权限控制（Admin 用户显示高级选项）
- 参数联动（勾选某选项 → 显示关联参数）

## 实现模型

```
Combo/Mode Selector 变化
    ↓
OnModeChanged() 回调
    ↓
判断当前选择 → 确定哪些 Panel 显示
    ↓
调用 Panel->SetVisibility(CATDlgShow/CATDlgHide)
    ↓
(可选) 调用 ResetPanelState() 清空隐藏面板的数据
```

## 实现模板

```cpp
// Panel 预设
void DynamicFormDlg::Build() {
    _pModeCombo = new CATDlgCombo(pFrame, "Mode");
    _pModeCombo->AddItem("Prefix");
    _pModeCombo->AddItem("Suffix");
    _pModeCombo->AddItem("Replace");

    // 三个面板都在 Build 中预创建
    _pPrefixPanel  = CreatePanel("Prefix", ...);
    _pSuffixPanel  = CreatePanel("Suffix", ...);
    _pReplacePanel = CreatePanel("Replace", ...);

    // 绑定切换事件
    AddAnalyseNotificationCB(this,
        _pModeCombo->GetComboSelectNotification(),
        (CATCommandMethod)&DynamicFormDlg::OnModeChanged, NULL);

    // 默认显示第一个
    OnModeChanged(NULL, NULL, NULL);  // 手动触发一次
}

// 切换逻辑（回调方法签名为 CATCommandMethod，无返回值，非 CATStatusChangeRC）
void DynamicFormDlg::OnModeChanged(CATCommand *iCmd, CATNotification *iNotif,
                                    CATCommandClientData iUsefulData) {
    int sel = _pModeCombo->GetSelect();
    _pPrefixPanel->SetVisibility(sel == 0 ? CATDlgShow : CATDlgHide);
    _pSuffixPanel->SetVisibility(sel == 1 ? CATDlgShow : CATDlgHide);
    _pReplacePanel->SetVisibility(sel == 2 ? CATDlgShow : CATDlgHide);
}
```

完整实现参考: [layout_advanced.md §2](../../knowledge/ui/layout_advanced.md)

## 三种动态策略

| 策略 | 适用场景 | 方法 |
|------|---------|------|
| **预创建+切换可见性** | 面板数 ≤ 5 | `SetVisibility` |
| **条件创建** | 面板由外部配置决定 | 运行时 `new` 控件 |
| **启用/禁用** | 同一面板、不同权限 | `SetSensitivity` |

## AI 生成规则

- [ ] 所有面板在 `Build()` 中预创建
- [ ] `OnModeChanged` 中调用 `SetVisibility` 切换
- [ ] 初始化时手动触发一次 `OnModeChanged`
- [ ] 切换模式时清空/重置隐藏面板的数据
- [ ] 控件数量 > 20 时考虑 Tab 页替代动态切换
- [ ] 用 `CATDlgCombo` 做模式选择器（非 RadioButton）
