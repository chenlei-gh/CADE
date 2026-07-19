---
id: ui.layout_anti_patterns
title: Layout Anti-Patterns
category: knowledge
domain: ui
keywords: [anti-pattern, mistake, hardcode, nesting, common error, wrong way, correct way]
apis: [CATDlgDialog, CATDlgFrame, CATDlgGridConstraints]
requires: [ui.dialog, ui.dialog_layout]
patterns: []
examples: []
release: [R19, R28]
tags: [ui, anti-pattern, debugging]
---

# CAA Layout Anti-Patterns

CAA 对话框布局的常见错误和正确做法。

---

## 1. 硬编码像素位置

### ❌ 错误

```cpp
// 用绝对像素位置
_pEditor->SetRectDimensions(10, 20, 200, 25);
_pLabel->SetRectDimensions(10, 50, 100, 20);
```

### ✅ 正确

```cpp
// 用 GridLayout + SetGridConstraints
CATDlgFrame *pFrame = new CATDlgFrame(this, "F",
    CATDlgFraNoFrame | CATDlgGridLayout);
_pLabel->SetGridConstraints(pFrame,
    CATDlgGridConstraints(0, 0, 1, 1, CATGRID_LEFT));
_pEditor->SetGridConstraints(pFrame,
    CATDlgGridConstraints(0, 1, 1, 1, CATGRID_4SIDES));
```

> **原因**: 硬编码在 DPI 缩放、不同分辨率、不同语言下都会错位。GridLayout 自动适配。

---

## 2. 忘记调用 SetGridConstraints

### ❌ 错误

```cpp
// 创建了控件但没设置网格约束
_pEditor = new CATDlgEditor(pFrame, "Edt");  // 控件位置不可预测！
```

### ✅ 正确

```cpp
_pEditor = new CATDlgEditor(pFrame, "Edt");
_pEditor->SetGridConstraints(pFrame,
    CATDlgGridConstraints(0, 0, 1, 1, CATGRID_4SIDES));
```

> **原因**: GridLayout 下，未设置 GridConstraints 的控件可能重叠或不可见。

---

## 3. Frame 嵌套过深（>5 层）

### ❌ 错误

```cpp
// 6 层嵌套
CATDlgFrame *p1 = new CATDlgFrame(this, "A", CATDlgGridLayout);
CATDlgFrame *p2 = new CATDlgFrame(p1, "B", CATDlgGridLayout);
CATDlgFrame *p3 = new CATDlgFrame(p2, "C", CATDlgGridLayout);
CATDlgFrame *p4 = new CATDlgFrame(p3, "D", CATDlgGridLayout);
CATDlgFrame *p5 = new CATDlgFrame(p4, "E", CATDlgGridLayout);
CATDlgFrame *p6 = new CATDlgFrame(p5, "F", CATDlgGridLayout);
// 难以维护、性能差、渲染可能异常
```

### ✅ 正确

```cpp
// 控制在 3-4 层，用 GroupBox / Tab 替代深层嵌套
CATDlgFrame *pTop = new CATDlgFrame(this, "Top", CATDlgGridLayout);
  CATDlgFrame *pGroup = new CATDlgFrame(pTop, "Group",
      CATDlgFraGroupFrame | CATDlgGridLayout);
    _pEditor = new CATDlgEditor(pGroup, "Edt");
// 仅 3 层
```

> **原因**: CAA 的 GridLayout 在 5 层以上可能有布局计算问题。用语义化容器（GroupBox/Tab/Splitter）替代无意义的多层嵌套。

---

## 4. 混用 GridLayout 和绝对定位

### ❌ 错误

```cpp
CATDlgFrame *pFrame = new CATDlgFrame(this, "F", CATDlgGridLayout);
// 又手动设 RectDimensions
_pEditor->SetRectDimensions(10, 10, 200, 25);
// GridLayout 和绝对定位互相冲突
```

### ✅ 正确

```cpp
// 要么全用 GridLayout
CATDlgFrame *pFrame = new CATDlgFrame(this, "F", CATDlgGridLayout);
_pEditor->SetGridConstraints(pFrame, ...);

// 要么全用绝对定位（不推荐）
CATDlgFrame *pFrame = new CATDlgFrame(this, "F", CATDlgFraNoFrame);
_pEditor->SetRectDimensions(10, 10, 200, 25);
```

> **原因**: GridLayout 会忽略控件的 RectDimensions，导致混乱。

---

## 5. 标签和输入框分属不同 Frame

### ❌ 错误

```cpp
// 标签在 pTop，输入框在 pMain → 布局断裂
CATDlgLabel *pLbl = new CATDlgLabel(pTop, "Lbl", "Name:");
CATDlgEditor *pEdt = new CATDlgEditor(pMain, "Edt");
```

### ✅ 正确

```cpp
// 同行控件必须在同一个 Frame 下
CATDlgFrame *pRow = new CATDlgFrame(pMain, "Row",
    CATDlgFraNoFrame | CATDlgGridLayout);
CATDlgLabel *pLbl = new CATDlgLabel(pRow, "Lbl", "Name:");
CATDlgEditor *pEdt = new CATDlgEditor(pRow, "Edt");
pLbl->SetGridConstraints(pRow, CATDlgGridConstraints(0, 0, ...));
pEdt->SetGridConstraints(pRow, CATDlgGridConstraints(0, 1, ...));
```

---

## 6. 按钮不设默认按钮

### ❌ 错误

```cpp
_pOKBtn = new CATDlgPushButton(pFrame, "OK", "OK");
// 没设默认按钮 → Enter 键无效
```

### ✅ 正确

```cpp
_pOKBtn = new CATDlgPushButton(pFrame, "OK", "OK");
SetDefaultPushButton(_pOKBtn);  // Enter 键触发 OK
```

---

## 7. 控件 ID 重复

### ❌ 错误

```cpp
// 同一个 Frame 下两个 Editor 同名 → 运行时异常
CATDlgEditor *p1 = new CATDlgEditor(pFrame, "Editor");
CATDlgEditor *p2 = new CATDlgEditor(pFrame, "Editor");  // 重复！
```

### ✅ 正确

```cpp
// 每个控件唯一 ID
CATDlgEditor *p1 = new CATDlgEditor(pFrame, "NameEditor");
CATDlgEditor *p2 = new CATDlgEditor(pFrame, "ValueEditor");
```

---

## 8. Dialog 中写业务逻辑

### ❌ 错误

```cpp
void MyDlg::OnApply() {
    // Dialog 直接操作 CATIA 数据 → 职责混乱
    CATISpecObject_var spObj = GetSelectedObject();
    spObj->SetAttribute("Name", _pEditor->GetText());
    spObj->Update();
}
```

### ✅ 正确

```cpp
// Dialog 只管 UI，通过 Getter 暴露数据
CATUnicodeString MyDlg::GetNewName() {
    return _pNameEditor->GetText();
}

// Command 执行业务逻辑
// 注意：回调方法（CATCommandMethod 签名）无返回值，不能用 CATStatusChangeRC 控制状态
void MyCmd::OnApply(CATCommand *iCmd, CATNotification *iNotif,
                     CATCommandClientData iUsefulData) {
    CATUnicodeString name = _pDlg->GetNewName();
    HRESULT hr = RenameFeature(name);  // 业务在 Command
    if (SUCCEEDED(hr)) {
        RequestDelayedDestruction();  // 成功后主动关闭
    }
}
```

---

## 9. 不设 Frame 风格导致无边框

### ❌ 错误

```cpp
CATDlgFrame *pFrame = new CATDlgFrame(this, "F", CATDlgGridLayout);
// 缺少 CATDlgFraNoFrame → 出现多余的 3D 边框
```

### ✅ 正确

```cpp
// 明确指定边框风格
CATDlgFrame *pFrame = new CATDlgFrame(this, "F",
    CATDlgFraNoFrame | CATDlgGridLayout);    // 无边框容器

CATDlgFrame *pGroup = new CATDlgFrame(this, "G",
    CATDlgFraGroupFrame | CATDlgGridLayout);  // 带标题分组框
pGroup->SetTitle("Options");

CATDlgFrame *pSunken = new CATDlgFrame(this, "S",
    CATDlgFraSunkenFrame | CATDlgGridLayout); // 下凹框
```

| Frame 风格常量 | 视觉效果 |
|---------------|---------|
| `CATDlgFraNoFrame` | 无边框（透明容器） |
| `CATDlgFraGroupFrame` | 分组框（带标题线框） |
| `CATDlgFraSunkenFrame` | 下凹框（列表/预览区） |
| 不设风格 | 3D 凸起边框（通常不推荐） |

---

## 10. Desactivate 中不清理控件

### ❌ 错误

```cpp
CATStatusChangeRC MyCmd::Desactivate(...) {
    return CATStatusChangeRCCompleted;  // 什么都没清理
}
```

### ✅ 正确

```cpp
CATStatusChangeRC MyCmd::Desactivate(...) {
    if (_pDlg) {
        _pDlg->SetVisibility(CATDlgHide);
        _pDlg->RequestDelayedDestruction();
        _pDlg = NULL;
    }
    if (_pAgent) {
        RemoveCSOClient(_pAgent);
        _pAgent->Release();
        _pAgent = NULL;
    }
    return CATStatusChangeRCCompleted;
}
```

---

## AI 生成规则

- [ ] 禁止硬编码 `SetRectDimensions` 替代 `SetGridConstraints`
- [ ] 每个控件创建后立即调用 `SetGridConstraints`
- [ ] 嵌套不超过 4 层，超过用 GroupBox/Tab/Splitter 重构
- [ ] 同 Frame 内控件 ID 必须唯一
- [ ] 同行标签和输入框必须在同一 Frame
- [ ] 必须设默认按钮 `SetDefaultPushButton`
- [ ] Dialog 不写业务逻辑，只提供 Getter/Setter
- [ ] Frame 风格必须显式指定 `CATDlgFraNoFrame`
- [ ] Desactivate 必须清理 Dialog 和 Agent
