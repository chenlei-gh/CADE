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

CAA 对话框布局的常见错误和正确做法。所有"正确"示例均经 B28 头文件/生产项目实证。

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
// 用 GridLayout + SetGridConstraints（5参重载，生产实证）
CATDlgFrame *pFrame = new CATDlgFrame(this, "F",
    CATDlgFraNoFrame | CATDlgGridLayout);
_pLabel->SetGridConstraints(0, 0, 1, 1, CATGRID_LEFT);
_pEditor->SetGridConstraints(0, 1, 1, 1, CATGRID_4SIDES);

// 控件宽度用可见字符数控制，不用像素
_pEditor->SetVisibleTextWidth(30);
```

> **原因**: 硬编码在 DPI 缩放、不同分辨率、不同语言下都会错位。GridLayout 自动适配；`SetVisibleTextWidth(n)` 按字符数定宽，跨语言稳定。

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
_pEditor->SetGridConstraints(0, 0, 1, 1, CATGRID_4SIDES);
```

> **原因**: GridLayout 下，未设置 GridConstraints 的控件可能重叠或不可见。

---

## 3. 顶层垂直堆叠用 GridLayout（窗口不收缩）

### ❌ 错误

```cpp
// 对话框顶层用 GridLayout 堆叠多个区域，隐藏某区域时窗口留空白
: CATDlgDialog(iParent, "DlgId", CATDlgGridLayout)
...
_pMainList->SetGridConstraints(0, 0, 1, 1, CATGRID_4SIDES);
_pEditPanel->SetGridConstraints(1, 0, 1, 1, CATGRID_4SIDES);
_pEditPanel->SetVisibility(CATDlgHide);   // 隐藏了，但网格行仍占位 → 窗口底部一大块空白
```

### ✅ 正确（生产实证：attachment 布局 + AutoResize）

```cpp
// 顶层不设 GridLayout，用窗口风格 CATDlgWndAutoResize + 附件布局
: CATDlgDialog(iParent, "DlgId",
               CATDlgWndAutoResize | CATDlgWndBtnOKCancel | CATDlgWndNoResize)

void Build() {
    _pMainList = new CATDlgMultiList(this, "ListId");
    // SetHorizontalAttachment 垂直堆叠（top→bottom）；行号是 tab 线索引
    SetHorizontalAttachment(0, CATDlgTopOrLeft, _pMainList, NULL);

    _pEditPanel = new CATDlgFrame(this, "EditPanelId",
                                  CATDlgFraNoFrame | CATDlgGridLayout);
    _pEditPanel->SetVisibility(CATDlgHide);   // 未 attach → 不占空间
}

// 显示面板：attach + show，AutoResize 自动撑高窗口
SetHorizontalAttachment(10, CATDlgTopOrLeft, _pEditPanel, NULL);
_pEditPanel->SetVisibility(CATDlgShow);

// 隐藏面板：detach + hide，窗口收缩回原样，不留空白
ResetAttachment(_pEditPanel);
_pEditPanel->SetVisibility(CATDlgHide);
```

> **原因**: `SetVisibility(CATDlgHide)` 在 GridLayout 里只是"不画"，格子还在，AutoResize 窗口会留出一块空白。`ResetAttachment()` 把面板**从布局中摘除**，不占用任何空间，窗口精确收缩。这是生产项目（CAAAutoRenameDlg）验证过的模式。

---

## 4. Frame 嵌套过深（>5 层）

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
// 控制在 3-4 层，用带标题 Frame / Tab 替代深层嵌套
CATDlgFrame *pTop = new CATDlgFrame(this, "Top", CATDlgGridLayout);
  CATDlgFrame *pGroup = new CATDlgFrame(pTop, "Group", CATDlgGridLayout);
  pGroup->SetTitle(NLS("Dlg.Group", "Options"));   // 默认 Frame 自带标题栏
    _pEditor = new CATDlgEditor(pGroup, "Edt");
// 仅 3 层
```

> **原因**: CAA 的 GridLayout 在 5 层以上可能有布局计算问题。分组用**默认 Frame + SetTitle**（B28 无 `CATDlgFraGroupFrame`/`CATDlgFraSunkenFrame`，Frame 风格只有 NoTitle/NoFrame/NoMargin）。

---

## 5. 混用 GridLayout 和绝对定位

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
_pEditor->SetGridConstraints(0, 0, 1, 1, CATGRID_4SIDES);

// 要么全用绝对定位（不推荐）
CATDlgFrame *pFrame = new CATDlgFrame(this, "F", CATDlgFraNoFrame);
_pEditor->SetRectDimensions(10, 10, 200, 25);
```

> **原因**: GridLayout 会忽略控件的 RectDimensions，导致混乱。

---

## 6. 标签和输入框分属不同 Frame

### ❌ 错误

```cpp
// 标签在 pTop，输入框在 pMain → 布局断裂
CATDlgLabel *pLbl = new CATDlgLabel(pTop, "Lbl");
CATDlgEditor *pEdt = new CATDlgEditor(pMain, "Edt");
```

### ✅ 正确

```cpp
// 同行控件必须在同一个 Frame 下
CATDlgFrame *pRow = new CATDlgFrame(pMain, "Row",
    CATDlgFraNoFrame | CATDlgGridLayout);
CATDlgLabel *pLbl = new CATDlgLabel(pRow, "Lbl");
CATDlgEditor *pEdt = new CATDlgEditor(pRow, "Edt");
pLbl->SetGridConstraints(0, 0, 1, 1, CATGRID_RIGHT);
pEdt->SetGridConstraints(0, 1, 1, 1, CATGRID_LEFT | CATGRID_RIGHT);
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

## 9. 窗口风格漏配 AutoResize / 按钮

### ❌ 错误

```cpp
// 窗口大小固定死，内容多了被裁剪、少了留空
: CATDlgDialog(iParent, "DlgId", CATDlgWndBtnOKCancel)
```

### ✅ 正确

```cpp
// AutoResize：窗口随内容自适应（配合 attachment 布局的动态面板尤其重要）
: CATDlgDialog(iParent, "DlgId",
               CATDlgWndAutoResize | CATDlgWndBtnOKCancel | CATDlgWndNoResize)
```

| 窗口风格常量 | 作用 |
|-------------|------|
| `CATDlgWndAutoResize` | 窗口随可见内容自动调整大小 |
| `CATDlgWndNoResize` | 禁止用户拖边框改大小（布局由代码全权控制时常配） |
| `CATDlgWndBtnOKCancel` | 自带 OK/Cancel 按钮行 |
| `CATDlgWndBtnClose` | 自带 Close 按钮 |

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

- [ ] 禁止硬编码 `SetRectDimensions` 替代布局约束；控件宽度用 `SetVisibleTextWidth(n)`
- [ ] GridLayout 下每个控件创建后立即调用 `SetGridConstraints`（单参对象或 5 参重载均可，**两参 `SetGridConstraints(pFrame, gc)` 不存在**）
- [ ] 顶层垂直堆叠用 **attachment 布局**（`SetHorizontalAttachment` + `CATDlgWndAutoResize`），不要顶层 GridLayout
- [ ] 动态显隐面板用 `ResetAttachment()` 脱离布局 + `SetVisibility`，不要只 `SetVisibility`（会留空白）
- [ ] 嵌套不超过 4 层，超过用带标题 Frame/Tab/Splitter 重构
- [ ] 同 Frame 内控件 ID 必须唯一
- [ ] 同行标签和输入框必须在同一 Frame
- [ ] Dialog 不写业务逻辑，只提供 Getter/Setter
- [ ] Frame 风格显式指定（分组用默认 Frame + SetTitle，B28 无 GroupFrame/SunkenFrame）
- [ ] Desactivate 必须清理 Dialog 和 Agent
