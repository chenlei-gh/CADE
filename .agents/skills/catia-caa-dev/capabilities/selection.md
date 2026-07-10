---
id: cap.selection
title: Object Selection
category: capability
domain: infrastructure
keywords: [selection, CATPathElement, CATFrmEditor, highlight, reframe, 3D view, spec tree, pick, multi-select]
apis: [CATISelection, CATPathElement, CATFrmEditor, CATISO, CATFrmDocument, CATISelectElement]
frameworks: [ApplicationFrame, InteractiveInterfaces]
playbooks: [block.locator, ui.result_dialog, analyzer.geometry]
requires: [mecmod.feature]
release: [R19, R28]
tags: [capability]
---

# Object Selection (对象选择)

Programmatic selection of objects in the 3D viewer and specification tree — including single/multi-select, path construction, highlight, and camera reframe for interactive workflows.

## 1. Summary

The selection capability enables programmatic control over the CATIA selection mechanism: constructing `CATPathElement` paths to identify objects in the assembly/document hierarchy, setting the current selection, retrieving selected objects, highlighting feedback, and controlling the camera to frame selected objects.

## 2. Core Concepts

- **CATPathElement**: A hierarchical path from root document/container through intermediate products/parts down to a leaf feature or cell; requires parent path for child resolution
- **CATFrmEditor**: The current active editor window that owns the selection state, viewer, and ISO controller
- **Selection state**: Each editor maintains a `CATISelection` that tracks which objects are currently selected (single or multi)
- **Add/remove selection**: `CATISelection::AddElement()` adds; `CATISelection::RemoveElement()` removes; `CATISelection::Clear()` deselects all
- **Selection events**: Selection changes fire notifications to all registered `CATISelectNotification` listeners
- **Highlight vs. selection**: Highlight is temporary visual feedback (via `CATVisProperties::SetHighlight()`); selection is persistent state with handles
- **Reframe**: `CATISO::ReframeOnObject()` centers the camera on a `CATPathElement`; essential for "find and show" workflows
- **Spec tree selection**: Objects in the specification tree can be selected programmatically using the same path/selection APIs
- **Multi-select**: `CATMultiSelectElement` allows batch selection of multiple objects in a single operation
- **Selection filter**: `CATISelection::SetFilter()` restricts selectable object types (e.g., only faces, only features, only products)

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATISelection` | Core selection interface on the editor; add, remove, clear, count, iterate selected elements |
| `CATPathElement` | Hierarchical path identifying an object from document root to leaf instance |
| `CATPathElement::AddChildElement()` | Append a child step to the path for nested product/part traversal |
| `CATFrmEditor` | Access the current editor, its selection, viewer, and ISO controller |
| `CATFrmEditor::GetCurrentEditor()` | Static method to retrieve the active editing session |
| `CATISO` | Interactive Set Object — controls camera: `ReframeOnObject()`, `ZoomIn()`, `Rotate()` |
| `CATFrmDocument` | Document-level frame access; provides path root from document-level context |
| `CATISelectElement` | Element descriptor for a single selection entry with path and visualization feedback |

## 4. Common Patterns

### 4.1 Select a Feature in the 3D View

```cpp
CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
CATISelection_var pSelection = pEditor->GetSelection();

// Build path from document root to feature
CATPathElement rootPath(pDocument->GetRootContainer());
CATPathElement featurePath(pFeature);
featurePath.SetParent(rootPath);

// Select the feature
pSelection->AddElement(featurePath);
```

### 4.2 Reframe Camera on a Selected Object

```cpp
CATISpecObject_var pFeature = ...;
CATPathElement path(pFeature);

CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
CATISO* pISO = pEditor->GetISO();
pISO->ReframeOnObject(path);
```

### 4.3 Retrieve Currently Selected Objects

```cpp
CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
CATISelection_var pSelection = pEditor->GetSelection();

int count = pSelection->GetNumberOfElements();
for (int i = 1; i <= count; i++) {
    CATISelectElement_var pElem = pSelection->GetElement(i);
    CATPathElement path = pElem->GetPath();
    CATISpecObject_var pObj = path.GetLeafObject();
    // Process selected object...
}
```

### 4.4 Select Multiple Features at Once

```cpp
CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
CATISelection_var pSelection = pEditor->GetSelection();

pSelection->Clear();  // Reset existing selection

CATListOfCATISpecObjects failedFeatures = ...;
for (int i = 1; i <= failedFeatures.Size(); i++) {
    CATPathElement path(failedFeatures[i]);
    pSelection->AddElement(path);
}
```

### 4.5 Highlight a Feature Temporarily (Non-Selection)

```cpp
CATISpecObject_var pFeature = ...;

// Temporary highlight on
CATVisProperties::SetHighlight(pFeature, TRUE);

// ... user reviews result ...

// Highlight off
CATVisProperties::SetHighlight(pFeature, FALSE);
```

## 5. Related Capabilities

- **[cap.visualization](visualization.md)** — Apply persistent color/transparency alongside selection highlights
- **[cap.assembly_tree](assembly-tree.md)** — Build paths through product hierarchy for assembly-level selection
- **[cap.feature_recognition](feature-recognition.md)** — Recognize feature types before selective highlighting
- **[cap.geometry_query](geometry-query.md)** — Select specific faces/edges from geometric query results
