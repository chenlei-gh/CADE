---
id: infra.selection
title: Selection
category: knowledge
domain: infrastructure
keywords: [selection, select, pick, highlight, CATISelection, CATPathElement, reframe, locate]
apis: [CATISelection, CATFrmEditor, CATPathElement, CATISO]
requires: []
patterns: [block.locator, ui.result_dialog]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [ui, interaction, locate]
---

# Selection (选择)

CAA 中选择操作的核心，用于选中、高亮、定位 Feature。

## 核心 API

### 获取当前选择集

```cpp
CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
CATISelection_var pSelection = pEditor->GetSelection();
```

### 选择 Feature

```cpp
CATISelection_var pSelection = ...;
CATPathElement path(feature);
pSelection->SelectElement(path);
```

### 清除选择

```cpp
pSelection->Clear();
```

### 获取已选中的元素

```cpp
CATISelection_var pSelection = ...;
CATISelectionResults_var pResults = pSelection->GetSelection();
// 遍历结果...
```

## 高亮 Feature

```cpp
CATISpecObject_var pFeature = ...;
CATVisProperties::SetHighlight(pFeature, TRUE);
```

## 双击定位 Feature

```cpp
CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
CATPathElement path(pFeature);
CATISO* pISO = pEditor->GetISO();
pISO->ReframeOnObject(path);
```

## 选中后滚动到可见

```cpp
CATISelection_var pSelection = ...;
CATPathElement path(feature);
pSelection->SelectElement(path);

CATISO* pISO = CATFrmEditor::GetCurrentEditor()->GetISO();
pISO->ReframeOnObject(path);
```

## 常用模式

| 场景 | 方式 |
|------|------|
| 选择单个对象 | `SelectElement(CATPathElement)` |
| 清除选择 | `Clear()` |
| 高亮对象 | `CATVisProperties::SetHighlight()` |
| 定位对象 | `CATISO::ReframeOnObject()` |
| 取消高亮 | `CATVisProperties::SetHighlight(FALSE)` |
| 获取选中数量 | `GetSelection()->Size()` |
