---
id: block.locator
title: Selection Locator
category: pattern
domain: blocks
keywords: [locate, select, highlight, reframe, double click, zoom, find, navigate]
apis: [CATISelection, CATFrmEditor, CATPathElement, CATISO]
requires: [infra.selection]
patterns: [ui.result_dialog]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [block, locate, selection, ui]
---

# Selection Locator (双击定位积木)

可复用的"选中+定位到 Feature"的最小代码块。几乎所有结果展示工具都需要它。

## 核心代码

```cpp
void LocateFeature(CATISpecObject_var pFeature) {
    CATPathElement path(pFeature);

    CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
    if (!pEditor) return;

    // 1. 清除当前选择
    pEditor->GetSelection()->Clear();

    // 2. 选中目标
    pEditor->GetSelection()->SelectElement(path);

    // 3. 滚动到可视区域
    pEditor->GetISO()->ReframeOnObject(path);
}
```

## 用法

```cpp
// 双击回调
void MyDialog::OnListDoubleClick(int line) {
    CATISpecObject_var pFeature = m_results[line].feature;
    LocateFeature(pFeature);  // ← Block: Locator
}

// Select All 中定位第一个
void OnSelectAll() {
    if (m_results.Size() > 0) {
        LocateFeature(m_results[1].feature);  // ← Block: Locator
    }
}
```

## 变体

```cpp
// 仅高亮，不选中
void HighlightFeature(CATISpecObject_var pFeature) {
    CATVisProperties::SetHighlight(pFeature, TRUE);
}

// 取消所有高亮
void ClearAllHighlight() {
    // 遍历所有 feature，设置 SetHighlight(FALSE)
}

// 定位到 Feature 并闪烁
void FlashFeature(CATISpecObject_var pFeature) {
    for (int i = 0; i < 3; i++) {
        CATVisProperties::SetHighlight(pFeature, TRUE);
        Sleep(200);
        CATVisProperties::SetHighlight(pFeature, FALSE);
        Sleep(200);
    }
    LocateFeature(pFeature);
}
```
