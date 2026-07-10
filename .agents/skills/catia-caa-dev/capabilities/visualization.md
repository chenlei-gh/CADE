---
id: cap.visualization
title: Visualization
category: capability
domain: infrastructure
keywords: [visualization, color, material, transparency, show, hide, graphic, highlight, opacity, render]
apis: [CATIVisProperties, CATIVisManager, CATGraphicProperties, CATVisProperties, CATISO]
frameworks: [CATGraphicProperties, Visualization]
playbooks: [analyzer.geometry, block.locator, ui.result_dialog]
requires: [mecmod.feature]
release: [R19, R28]
tags: [capability]
---

# Visualization (可视化)

Controlling the visual appearance of CATIA features and products — color, material, transparency, show/hide state, and highlight — for analysis feedback and user interaction.

## 1. Summary

The visualization capability provides programmatic control over how CATIA objects appear in the 3D viewer, including setting fill color, edge color, transparency, material assignment, show/hide toggling, and temporary highlighting of features for analysis results and user guidance.

## 2. Core Concepts

- **Visual properties**: Each `CATISpecObject` carries a set of graphic attributes — color (RGB), transparency (0–255), line type, and line weight
- **Inheritance model**: Visual properties can be inherited from parent product/part nodes or explicitly overridden on a per-feature basis
- **Show/Hide**: `CATIVisProperties::SetVisible()` toggles visibility in the 3D view without affecting geometry
- **Highlight**: Temporary visual emphasis used for selection feedback or analysis results; does not modify persistent properties
- **Material assignment**: `CATIVisProperties::SetMaterial()` applies a rendering material (aluminum, steel, glass, custom)
- **Transparency**: Ranges from 0 (opaque) to 255 (fully transparent); useful for seeing through covering parts
- **Edge color**: Separate color channel for feature/face edges; useful for distinguishing topology in analysis
- **Viewer reframe**: `CATISO::ReframeOnObject()` centers the camera on a specific feature
- **Layer management**: Objects can be assigned to layers for grouped visibility control across documents
- **Graphic properties vs. vis properties**: `CATGraphicProperties` is a lightweight struct for get/set operations; `CATIVisProperties` is the COM interface on objects

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATIVisProperties` | COM interface on spec objects for persistent show/hide, color, opacity, material |
| `CATIVisProperties::SetColor(r,g,b)` | Set the fill color of a feature (RGB 0–255) |
| `CATIVisProperties::SetOpacity(opacity)` | Set transparency (0=opaque, 255=transparent) |
| `CATIVisProperties::SetVisible(on/off)` | Show or hide a feature in the 3D viewer |
| `CATIVisProperties::SetMaterial(name)` | Assign a rendering material by name |
| `CATVisProperties::SetHighlight(obj, on/off)` | Static method for temporary highlight highlighting |
| `CATGraphicProperties` | Lightweight struct returned from `GetGraphicProperties()` with current color/opacity/line values |
| `CATISO` | Interactive Set Object — controls camera position (reframe, zoom, rotate) |
| `CATIVisManager` | Global visibility manager for layer assignment and view-level visibility control |

## 4. Common Patterns

### 4.1 Color a Feature Based on Analysis Result

```cpp
CATISpecObject_var pFeature = ...;
CATIVisProperties_var pVis = pFeature;

// Red for failure, green for pass
if (bPassedAnalysis) {
    pVis->SetColor(0, 255, 0);    // Green
} else {
    pVis->SetColor(255, 0, 0);    // Red
}
pVis->SetOpacity(0);  // Fully opaque
```

### 4.2 Temporary Highlight (Non-Persistent)

```cpp
CATISpecObject_var pFeature = ...;

// Highlight on
CATVisProperties::SetHighlight(pFeature, TRUE);

// ... show result, wait for user ...

// Highlight off
CATVisProperties::SetHighlight(pFeature, FALSE);
```

### 4.3 Show/Hide with Reframe

```cpp
CATISpecObject_var pFeature = ...;
CATIVisProperties_var pVis = pFeature;

// Ensure visible
pVis->SetVisible(TRUE);

// Reframe camera to center on the feature
CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
CATPathElement path(pFeature);
CATISO* pISO = pEditor->GetISO();
pISO->ReframeOnObject(path);
```

### 4.4 Batch Set Transparency on Analyzed Faces

```cpp
CATListOfCATFaces failedFaces = ...;
int opacity = 128;  // 50% transparent

for (int i = 1; i <= failedFaces.Size(); i++) {
    CATIVisProperties_var pVis = failedFaces[i];
    pVis->SetColor(255, 100, 100);  // Soft red
    pVis->SetOpacity(opacity);
}
```

### 4.5 Reset to Inherited Visual Properties

```cpp
CATIVisProperties_var pVis = pFeature;

// Reset color/opacity to parent or default
pVis->SetColorToInherited();
pVis->SetOpacityToInherited();
```

## 5. Related Capabilities

- **[cap.feature_recognition](feature-recognition.md)** — Color-code features by type or analysis category
- **[cap.geometry_query](geometry-query.md)** — Highlight specific faces/edges found by geometric queries
- **[cap.assembly_tree](assembly-tree.md)** — Show/hide or color assembly components for BOM review
- **[cap.parameter_system](parameter-system.md)** — Drive visual states from parameter check results
