---
id: ui.result_dialog
title: Result Dialog
category: pattern
domain: ui
keywords: [dialog, result, listview, table, display, double click, locate, report]
apis: [CATDlgDialog, CATDlgList, CATDlgFrame, CATDlgPushButton, CATFrmEditor, CATPathElement]
requires: [ui.dialog, infra.selection]
patterns: [block.locator]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [pattern, ui, dialog, result, locate]
---

# Result Dialog Pattern (结果对话框模式)

用于在对话框中展示分析/检查结果，支持双击定位到对应 Feature。

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
│ │ Status │ Name   │ Problem   │ │  ← CATDlgList (表格)
│ │  ✗     │ Fillet1│ R < 2mm  │ │
│ │  ✓     │ Fillet2│ OK        │ │
│ │  ✗     │ Hole1  │ D < 5mm  │ │
│ └─────────────────────────────┘ │
│                                 │
│  Total: 3  |  Pass: 1  Fail: 2 │  ← 统计信息
│                                 │
│        [Close]   [Export]       │  ← 按钮
└─────────────────────────────────┘
```

双击某行 → 定位到对应 Feature

## 实现步骤

### Step 1: 定义列结构

```cpp
// 列定义
enum ResultColumn {
    COL_STATUS = 0,
    COL_NAME,
    COL_TYPE,
    COL_PROBLEM,
    COL_COUNT  // 总列数
};
```

### Step 2: 创建 Dialog

```cpp
class ResultDialog : public CATDlgDialog {
public:
    ResultDialog();
    void SetResults(const CATListValResult& results);
    void OnDoubleClick(int line);

private:
    CATDlgList* m_pList;
    CATDlgLabel* m_pSummary;
    CATListValResult m_results;
};
```

### Step 3: 填充列表

```cpp
void ResultDialog::SetResults(const CATListValResult& results) {
    m_pList->ClearLine();

    for (int i = 1; i <= results.Size(); i++) {
        const Result& r = results[i];
        char* cols[COL_COUNT];

        cols[COL_STATUS]  = r.passed ? "✓" : "✗";
        cols[COL_NAME]    = r.feature->GetName();
        cols[COL_TYPE]    = r.feature->GetType();
        cols[COL_PROBLEM] = r.problem;

        m_pList->SetLine(i, cols, COL_COUNT);
    }

    UpdateSummary();
}
```

### Step 4: 双击定位

```cpp
void ResultDialog::OnDoubleClick(int line) {
    if (line < 1 || line > m_results.Size()) return;

    CATISpecObject_var pFeature = m_results[line].feature;
    CATPathElement path(pFeature);

    CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
    pEditor->GetSelection()->Clear();
    pEditor->GetSelection()->SelectElement(path);
    pEditor->GetISO()->ReframeOnObject(path);
}
```

## 关键点

1. **列清晰** —— Status/Name/Type/Problem 四列是最小集合
2. **颜色/图标区分** —— 通过/失败应有视觉区分
3. **双击必做两件事** —— Select + Reframe
4. **统计信息** —— 底部显示 Total/Pass/Fail 计数
5. **导出按钮** —— 可选，导出为 CSV/TXT
