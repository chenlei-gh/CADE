---
id: cap.selection
title: Object Selection
category: capability
domain: infrastructure
keywords: [selection, CATPathElement, CATFrmEditor, highlight, reframe, 3D view, spec tree, pick, multi-select]
apis: [CATCSO, CATPathElement, CATFrmEditor, CATISO, CATISelectionSet]
frameworks: [ApplicationFrame, InteractiveInterfaces]
playbooks: [block.locator, ui.result_dialog, analyzer.geometry]
requires: [mecmod.feature]
release: [R19, R28]
tags: [capability]
---

# Object Selection (对象选择)

Programmatic selection of objects in the 3D viewer and specification tree — including single/multi-select, path construction, highlight, and camera reframe for interactive workflows.

## ⚠️ 重要修正

之前版本引用了 `CATISelection`、`CATFrmDocument`、`CATISelectElement`、`CATMultiSelectElement` 等接口/类，经 CAADoc 核实**均不存在**。`CATFrmEditor` 上也没有 `GetSelection()` 方法。真实的当前选择集是 `CATCSO`（Current Selection of Objects），通过 `CATFrmEditor::GetCSO()` 获取。

## 1. Summary

The selection capability enables programmatic control over the CATIA selection mechanism: constructing `CATPathElement` paths to identify objects in the assembly/document hierarchy, adding/removing objects from the current selection set (`CATCSO`), and controlling the camera to frame selected objects.

## 2. Core Concepts

- **CATPathElement**: A hierarchical path from root document/container through intermediate products/parts down to a leaf feature or cell
- **CATFrmEditor**: The current active editor window; exposes several distinct object sets, not a single "selection" object:
  - `GetCSO()` → `CATCSO*` — the **C**urrent **S**election of **O**bjects (what the user has picked)
  - `GetPSO()` → the Preselected Set of Objects (hover/pre-highlight)
  - `GetHSO()` → the Highlighted Set of Objects
  - `GetISO()` / `GetFurtiveISO()` → `CATISO*` — Interactive Set of Objects, manages viewers themselves (`AddViewer`, `AddElement`, etc.), not a camera-reframe controller
- **CATCSO**: real methods are `AddElement(CATBaseUnknown*, int iDispatchChange=1)`, `RemoveElement(CATBaseUnknown*, int)`, `Empty(int)`, `Contains(CATBaseUnknown*)`, `GetSize()`, `InitElementList()`/`NextElement()` for iteration. Note: `AddElement` takes a `CATBaseUnknown*` (often a `CATPathElement*`), not a value type
- **CATISelectionSet** (`InteractiveInterfaces`): a separate, persistent named selection-set mechanism — `AddElement(CATPathElement*, CATISelectionSetElement*&, int)`, `FindElement()`, `GetSize()`, `IsMember()`, `RemoveElement()`, `ListElement()`. Distinct from `CATCSO`; used for saved/reusable groups of objects rather than the live interactive selection
- **Reframe**: there is **no** `CATISO::ReframeOnObject()` method. Automatic camera reframing is controlled per-camera via `CATIReframeCamera::SetReframe(int)`/`GetReframe()` (ApplicationFrame); explicit reframe-on-selection is typically triggered by sending a reframe notification (see official sample `CAAVisBaseReframeNotification`), not by calling a method directly on `CATISO`

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATFrmEditor::GetCurrentEditor()` | Static method to retrieve the active editing session |
| `CATFrmEditor::GetCSO()` | Returns the `CATCSO*` current selection of objects |
| `CATCSO::AddElement()` / `RemoveElement()` / `Empty()` / `Contains()` / `GetSize()` | Manage the live selection |
| `CATPathElement` | Hierarchical path identifying an object from document root to leaf instance |
| `CATFrmEditor::GetISO()` / `GetFurtiveISO()` | Interactive Set of Objects — manages viewers, not camera framing |
| `CATISelectionSet` | Named/persistent selection-set container (different from `CATCSO`) |
| `CATIReframeCamera` | Per-camera automatic-reframe toggle (`SetReframe`/`GetReframe`) |

## 4. Common Patterns

### 4.1 Select a Feature Programmatically

```cpp
CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
CATCSO* pCSO = pEditor->GetCSO();

// Build path from document root to feature
CATPathElement* pFeaturePath = new CATPathElement(pFeature);

// Select the feature (adds to the live current selection)
pCSO->AddElement(pFeaturePath);
```

### 4.2 Retrieve Currently Selected Objects

```cpp
CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
CATCSO* pCSO = pEditor->GetCSO();

int count = pCSO->GetSize();
pCSO->InitElementList();
CATBaseUnknown* pElem = NULL;
while (NULL != (pElem = pCSO->NextElement())) {
    // pElem is typically a CATPathElement*; QueryInterface as needed
}
```

### 4.3 Clear and Re-select Multiple Features

```cpp
CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
CATCSO* pCSO = pEditor->GetCSO();

pCSO->Empty();  // Reset existing selection

CATListOfCATISpecObjects failedFeatures = ...;
for (int i = 1; i <= failedFeatures.Size(); i++) {
    CATPathElement* pPath = new CATPathElement(failedFeatures[i]);
    pCSO->AddElement(pPath);
}
```

### 4.4 Persistent Named Selection Set (CATISelectionSet)

```cpp
CATISelectionSet_var spSet = ...; // obtained via CATISelectionSetsFactory
CATISelectionSetElement* pSetElem = NULL;
CATPathElement* pPath = new CATPathElement(pFeature);
HRESULT rc = spSet->AddElement(pPath, pSetElem);
```

## 5. Related Capabilities

- **[cap.visualization](visualization.md)** — Apply persistent color/transparency alongside selection highlights
- **[cap.assembly_tree](assembly-tree.md)** — Build paths through product hierarchy for assembly-level selection
- **[cap.feature_recognition](feature-recognition.md)** — Recognize feature types before selective highlighting
- **[cap.geometry_query](geometry-query.md)** — Select specific faces/edges from geometric query results
