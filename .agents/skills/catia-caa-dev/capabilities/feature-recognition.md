---
id: cap.feature_recognition
title: Feature Recognition
category: capability
domain: infrastructure
keywords: [feature, recognition, IsSubTypeOf, late type, GetType, hole, pocket, pad, fillet, startup]
apis: [CATISpecObject, CATIPrtPart]
frameworks: [MecModInterfaces, ObjectSpecsLegacy]
playbooks: [analyzer.geometry, analyzer.rule, block.visitor]
requires: [mecmod.feature, mecmod.topology]
release: [R19, R28]
tags: [capability]
---

# Feature Recognition (特征识别)

Identifying CATIA feature types at runtime — distinguishing Pad from Pocket, Hole from Fillet — using `IsSubTypeOf`, `GetType`, and StartUp lookups.

## ⚠️ 重要修正

旧版本文档中的多个 API 和方法名经 CAADoc（`ObjectSpecsLegacy`/`MecModInterfaces` 框架）核实修正：

| 旧写法（虚构） | 真实情况 |
|---------------|---------|
| `CATISpecObject::GetParent()` | 不存在。真实方法是 **`GetFather()`** |
| `CATISpecObject::GetChildren()` | 不存在。真实方法是 **`ListComponents()`**（返回 `CATListValCATISpecObject_var*`，需 `delete`） |
| `CATISpecObject::IsATypeOf(name)` | `CATISpecObject` 无此方法。真实类型检查方法是 **`IsSubTypeOf(CATUnicodeString&)`** |
| `CATICatalog` | **不存在**。没有裸 `CATICatalog` 接口用于 "late type 绑定"。只有 `ComponentsCatalogsInterfaces` 中的具体子接口（`CATICatalogChapter`、`CATICatalogQuery` 等） |
| `CATISpecAccess` | **不存在**，CAADoc 零匹配，纯虚构 |
| `StartUp`（独立 API） | 不存在独立接口。`StartUp` 只是一个概念，通过 `CATISpecObject::GetStartUp()`（返回 `CATISpecObject*`）使用 |

## 1. Summary

Feature recognition is the capability to programmatically determine what type of feature a `CATISpecObject` represents (Pad, Pocket, Hole, EdgeFillet, etc.) at runtime, enabling conditional processing, rule checking, and automated validation of part geometry.

## 2. Core Concepts

- **`IsSubTypeOf` vs. `GetType`**: `IsSubTypeOf("Pad")` checks the type system via the StartUp chain; `GetType()` returns the late type string directly for comparison
- **StartUp**: The feature template that defines type identity, obtained via `CATISpecObject::GetStartUp()`
- **Feature tree navigation**: Navigate up to parent via `GetFather()`, navigate down to children via `ListComponents()` (returns `CATListValCATISpecObject_var*`, caller must `delete`)
- **Generative vs. dress-up**: Generative features (Pad, Pocket, Shaft) create new geometry; dress-up features (Fillet, Chamfer, Draft) modify existing geometry
- **Boolean features**: `SolidCombine` represents Add/Remove/Intersect operations that combine bodies
- **Reference features**: `GeometricalSet`, `OrderedGeometricalSet` contain wireframe and surface reference geometry
- **Pattern/mirror**: `Pattern` and `Mirror` replicate features and reference the seed feature
- **Hybrid body**: In hybrid design mode, solid and surface features coexist in the same body

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATISpecObject::GetType()` | Returns the late type string (e.g., "Pad", "Hole") |
| `CATISpecObject::IsSubTypeOf(name)` | Check if the feature derives from a given StartUp type |
| `CATISpecObject::GetStartUp()` | Returns the StartUp object (the template/factory ancestor) |
| `CATISpecObject::GetFather()` | Navigate up to the aggregating parent feature or body |
| `CATISpecObject::ListComponents()` | Navigate down to child features (returns `CATListValCATISpecObject_var*`, must `delete`) |
| `CATIPrtPart` | Entry point for the Part container, the root of the feature tree |

## 4. Common Patterns

### 4.1 Type Check with IsSubTypeOf

```cpp
CATISpecObject_var pFeature = ...;

if (pFeature->IsSubTypeOf("Pad")) {
    // Process pad-specific logic
    double height = GetPadHeight(pFeature);
} else if (pFeature->IsSubTypeOf("Pocket")) {
    double depth = GetPocketDepth(pFeature);
} else if (pFeature->IsSubTypeOf("Hole")) {
    double diameter = GetHoleDiameter(pFeature);
} else if (pFeature->IsSubTypeOf("EdgeFillet")) {
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
