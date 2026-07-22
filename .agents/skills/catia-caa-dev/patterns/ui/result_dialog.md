---
id: ui.result_dialog
title: Result Dialog
category: pattern
domain: ui
keywords: [dialog, result, listview, table, display, double click, locate, report]
apis: [CATDlgDialog, CATDlgSelectorList, CATDlgFrame, CATDlgPushButton, CATFrmEditor, CATCSO]
requires: [ui.dialog, infra.selection]
patterns: [block.locator]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [pattern, ui, dialog, result, locate]
---

# Result Dialog Pattern (结果对话框模式)

用于在对话框中展示分析/检查结果，支持双击定位到对应 Feature。

## ⚠️ 重要修正

之前版本使用的 `CATDlgList`（含 `SetLine(i, cols, n)` 多列签名）、`GetSelection()->SelectElement()`、`CATISO::ReframeOnObject()` 经核实**均不存在**。真实列表控件是 `CATDlgSelectorList`（单列）或 `CATDlgTableView`（多列表格）；选择集是 `CATCSO`；定位用 `CAT3DViewer::ReframeOn`。详见 [ui.dialog](../../knowledge/ui/dialog.md)、[infra.selection](../../knowledge/infrastructure/selection.md)、[block.locator](../blocks/locator.md)。

## 适用场景

- 几何分析结果展示
- 规则检查结果展示
- DFM 报告展示
- 任何需要列表+定位的场景

## UI 布局

```
┌─────────────────────────────────┐
│  Result Dialog                  │
│ ┌─────────────────────────────┐ │
│ │ [✗] Fillet1 — R < 2mm      │ │  ← CATDlgSelectorList
│ │ [✓] Fillet2 — OK           │ │     （多列需求用 CATDlgTableView）
│ │ [✗] Hole1   — D < 5mm      │ │
│ └─────────────────────────────┘ │
│                                 │
│  Total: 3  |  Pass: 1  Fail: 2 │  ← 统计信息
│                                 │
│        [Close]   [Export]       │  ← 按钮
└─────────────────────────────────┘
```

双击某行 → 定位到对应 Feature

## 实现步骤

### Step 1: 创建 Dialog

```cpp
class ResultDialog : public CATDlgDialog {
public:
    ResultDialog(CATDialog *iParent);
    void SetResults(const ResultList &results);
    void OnListSelect();                    // 选中回调（自定义方法）

private:
    CATDlgSelectorList *_pList;
    CATDlgLabel        *_pSummary;
    ResultList          _results;
};
```

构造与布局（真实签名）：

```cpp
ResultDialog::ResultDialog(CATDialog *iParent)
    : CATDlgDialog(iParent, "ResultDlg",
                   CATDlgWndModal | CATDlgWndOK)
{
    CATDlgFrame *pFrame = new CATDlgFrame(this, "ResultF",
        CATDlgFraNoFrame | CATDlgGridLayout);

    _pList = new CATDlgSelectorList(pFrame, "ResultList");
    _pList->SetGridConstraints(CATDlgGridConstraints(0, 0, 1, 1, CATGRID_4SIDES));
    _pList->SetVisibleTextHeight(10);

    _pSummary = new CATDlgLabel(pFrame, "SummaryLbl");
    _pSummary->SetGridConstraints(CATDlgGridConstraints(1, 0, 1, 1, CATGRID_LEFT));

    // 选中通知挂回调
    AddAnalyseNotificationCB(_pList,
        _pList->GetListSelectNotification(),
        (CATCommandMethod)&ResultDialog::OnListSelect, NULL);
}
```

### Step 2: 填充列表

`CATDlgSelectorList::SetLine(text, index=-1)` 追加单行文本；多列信息拼进字符串（或改用 `CATDlgTableView`）：

```cpp
void ResultDialog::SetResults(const ResultList &results) {
    _results = results;
    _pList->ClearLine();

    for (int i = 1; i <= _results.Size(); i++) {
        const Result &r = _results[i];
        CATUnicodeString line;
        line.Append(r.passed ? "[OK] " : "[FAIL] ");
        line.Append(r.name);
        line.Append(" — ");
        line.Append(r.problem);
        _pList->SetLine(line, -1);          // -1 = 追加
    }
    UpdateSummary();
}
```

### Step 3: 选中定位（真实 API：CATCSO）

```cpp
void ResultDialog::OnListSelect() {
    int count = _pList->GetSelectCount();
    if (count < 1) return;
    int *selArr = new int[count];
    _pList->GetSelect(selArr, count);
    int line = selArr[0];
    delete [] selArr;

    if (line < 0 || line >= _results.Size()) return;

    CATISpecObject_var spFeature = _results[line + 1].feature;  // CAA 列表 1-based

    CATFrmEditor *pEditor = CATFrmEditor::GetCurrentEditor();
    if (!pEditor) return;
    CATCSO *pCSO = pEditor->GetCSO();
    pCSO->Empty();
    pCSO->AddElement(new CATPathElement(spFeature));
    // 相机定位：CAT3DViewer::ReframeOn(boundingSphere)，见 block.locator
}
```

## 关键点

1. **行信息自足** —— Status/Name/Problem 拼进单行文本；真正多列用 `CATDlgTableView`
2. **视觉区分** —— `[OK]/[FAIL]` 前缀；`SetLine` 支持图标/颜色重载（见 `CATDlgSelectorList.h`）
3. **选中必做两件事** —— CSO 清空 + 加入 CATPathElement
4. **统计信息** —— 底部 Label 显示 Total/Pass/Fail
5. **CAA 列表 1-based** —— `GetSelect` 返回的行号从 0 起而业务集合从 1 起，注意换算
