---
id: cap.feature_recognition
title: Feature Recognition
category: capability
domain: infrastructure
keywords: [feature, recognition, IsATypeOf, late type, StartUp, hole, pocket, pad, fillet, catalog]
apis: [CATISpecObject, CATICatalog, StartUp, CATISpecAccess, CATIPrtPart]
frameworks: [CATMecModUseItf, ObjectModelerBase]
playbooks: [analyzer.geometry, analyzer.rule, block.visitor]
requires: [mecmod.feature, mecmod.topology]
release: [R19, R28]
tags: [capability]
---

# Feature Recognition (特征识别)

Identifying CATIA feature types at runtime — distinguishing Pad from Pocket, Hole from Fillet — using `IsATypeOf`, late type binding, and StartUp catalog lookups.

## 1. Summary

Feature recognition is the capability to programmatically determine what type of feature a `CATISpecObject` represents (Pad, Pocket, Hole, EdgeFillet, etc.) at runtime, enabling conditional processing, rule checking, and automated validation of part geometry.

## 2. Core Concepts

- **IsATypeOf vs. late type**: `IsATypeOf("Pad")` checks the C++ class hierarchy; late type via `CATICatalog` checks the StartUp registration regardless of C++ inheritance
- **StartUp catalog**: The feature type registry that maps StartUp names (e.g., "Pad") to implementation classes
- **Feature tree context**: A feature's type often determines which children it can have (e.g., a Sketch under a Pad)
- **Generative vs. dress-up**: Generative features (Pad, Pocket, Shaft) create new geometry; dress-up features (Fillet, Chamfer, Draft) modify existing geometry
- **Boolean features**: `SolidCombine` represents Add/Remove/Intersect operations that combine bodies
- **Reference features**: `GeometricalSet`, `OrderedGeometricalSet` contain wireframe and surface reference geometry
- **Pattern/mirror**: `Pattern` and `Mirror` replicate features and reference the seed feature
- **Hybrid body**: In hybrid design mode, solid and surface features coexist in the same body

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATISpecObject::IsATypeOf(name)` | Check if the feature is of a specific C++ class type |
| `CATISpecObject::GetType()` | Returns the StartUp type string (e.g., "Pad", "Hole") |
| `CATICatalog` | Late type binding — match a StartUp name to its implementation |
| `CATISpecAccess` | Provides access to the spec object model from the document |
| `CATIPrtPart` | Entry point for the Part container, the root of the feature tree |
| `CATISpecObject::GetParent()` | Navigate up to the parent feature or body |
| `CATISpecObject::GetChildren()` | Navigate down to child features (e.g., Sketch under Pad) |
| StartUp lookup | Resolve feature StartUp name to its factory for instantiation |

## 4. Common Patterns

### 4.1 C++ Type Check with IsATypeOf

```cpp
CATISpecObject_var pFeature = ...;

if (pFeature->IsATypeOf("Pad")) {
    // Process pad-specific logic
    double height = GetPadHeight(pFeature);
} else if (pFeature->IsATypeOf("Pocket")) {
    double depth = GetPocketDepth(pFeature);
} else if (pFeature->IsATypeOf("Hole")) {
    double diameter = GetHoleDiameter(pFeature);
} else if (pFeature->IsATypeOf("EdgeFillet")) {
    double radius = GetFilletRadius(pFeature);
}
```

### 4.2 Late Type via GetType (StartUp Name)

```cpp
CATISpecObject_var pFeature = ...;
CATUnicodeString typeName = pFeature->GetType();

// typeName could be: "Pad", "Pocket", "Hole", "EdgeFillet",
//   "EdgeChamfer", "Draft", "Shell", "Mirror", "Pattern",
//   "SolidCombine", "Split", "Thickness", "Shaft", "Groove"

if (typeName == "SolidCombine") {
    // Handle Boolean operation
    ProcessBooleanFeature(pFeature);
}
```

### 4.3 Feature Classification (Generative vs. Dress-Up)

```cpp
enum FeatureClass { GENERATIVE, DRESS_UP, REFERENCE, TRANSFORM, BOOLEAN, UNKNOWN };

FeatureClass ClassifyFeature(CATISpecObject_var pFeature) {
    CATUnicodeString type = pFeature->GetType();

    if (type == "Pad" || type == "Pocket" || type == "Shaft" ||
        type == "Groove" || type == "Hole" || type == "Rib" || type == "Slot")
        return GENERATIVE;

    if (type == "EdgeFillet" || type == "FaceFillet" ||
        type == "EdgeChamfer" || type == "Draft" ||
        type == "Shell" || type == "Thickness")
        return DRESS_UP;

    if (type == "Mirror" || type == "Pattern")
        return TRANSFORM;

    if (type == "SolidCombine")
        return BOOLEAN;

    return UNKNOWN;
}
```

## 5. Related Capabilities

- **[cap.geometry_query](geometry-query.md)** — Access geometry produced by recognized features
- **[cap.assembly_tree](assembly-tree.md)** — Navigate to parts before feature recognition
- **[cap.parameter_system](parameter-system.md)** — Read feature parameters (hole diameter, fillet radius)
- **[cap.visualization](visualization.md)** — Highlight or color-code recognized features
