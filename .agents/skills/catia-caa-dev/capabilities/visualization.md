---
id: cap.visualization
title: Visualization
category: capability
domain: infrastructure
keywords: [visualization, color, material, transparency, show, hide, graphic, highlight, opacity, render]
apis: [CATIVisProperties, CATVisPropertiesValues, CATVisPropertyType]
frameworks: [Visualization]
playbooks: [analyzer.geometry, block.locator, ui.result_dialog]
requires: [mecmod.feature]
release: [R19, R28]
tags: [capability]
---

# Visualization (可视化)

Controlling the visual appearance of CATIA features and products — color, transparency, and show/hide state — for analysis feedback and user interaction.

## ⚠️ 重要修正

旧版本引用的 `CATIVisProperties::SetColor()`/`SetOpacity()`/`SetVisible()`/`SetMaterial()`/`SetColorToInherited()`、静态方法 `CATVisProperties::SetHighlight()`、`CATISO::ReframeOnObject()`、`CATIVisManager` 作为"全局可见性管理器"的描述，经 CAADoc 核实**均不存在**。真实机制如下：

- 所有图形属性的读写都必须先构造一个 `CATVisPropertiesValues` 值对象，再通过
  `CATIVisProperties::SetPropertiesAtt(values, propertyType, geomType)` 一次性应用（该方法实际
  定义在基接口 `CATIVisPropertiesAbstract` 上）。没有任何 `SetColor`/`SetOpacity` 之类的直接
  快捷方法。
- `CATVisPropertiesValues` 本身没有材质相关方法，只有：`SetColor`/`GetColor`、
  `SetOpacity`/`GetOpacity`、`SetLineType`、`SetWidth`、`SetSymbolType`、`SetLayer`、
  `SetShowAttr`/`GetShowAttr`（用于显示/隐藏，`CATShowAttribut` 枚举）、`SetPickAttr`、
  `SetInheritance`/`GetInheritance`/`ResetInheritance`（重置为继承值，而不是叫
  `SetColorToInherited`）。
- 相机自动重新取景由 `CATIReframeCamera::SetReframe(int)`/`GetReframe()` 控制，是一个
  开关而不是"对指定对象重新取景"的调用；`CATISO` 没有 `ReframeOnObject()` 方法（详见
  `cap.selection`）。
- `CATVisManager` 是底层可视化调度器（`AttachTo`/`DetachFrom`/`Commit`/`BuildRep` 等），
  面向 rep-path 与 viewpoint 的连接管理，并非简单的"图层/可见性全局管理器"；日常业务代码
  一般不直接调用它。

## 1. Summary

The visualization capability provides programmatic control over how CATIA objects appear in the 3D viewer: setting fill color, opacity/transparency, line style, and show/hide state, via the `CATVisPropertiesValues` + `CATIVisProperties::SetPropertiesAtt()` pattern.

## 2. Core Concepts

- **CATIVisProperties**: COM interface implemented via a data extension on visualizable objects (deriving `CATI3DGeoVisu`/`CATI2DGeoVisu`); all read/write goes through its base `CATIVisPropertiesAbstract`
- **CATVisPropertiesValues**: a plain value-holder struct — you fill it with the property you want (color, opacity, line type, ...), then pass it to `SetPropertiesAtt`/read it back from `GetPropertiesAtt`
- **CATVisPropertyType**: enum selecting *which* property the values struct currently represents (e.g. `CATVPColor`, `CATVPShow`, `CATVPSymbol`, `CATVPAllPropertyType`)
- **CATVisGeomType**: enum selecting *which geometry kind* the property applies to (e.g. `CATVPPoint`, `CATVPGlobalType` for "the whole object")
- **Show/Hide**: expressed as a `CATShowAttribut` value set via `SetShowAttr()`/read via `GetShowAttr()` inside a `CATVisPropertiesValues`, applied with property type `CATVPShow`
- **Inheritance**: a property can be reset to inherit from its parent using `ResetInheritance()`/`SetInheritance(type, flag)`, not a per-property "SetXToInherited" method

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATIVisProperties` | COM interface on spec objects; actual read/write methods live on base `CATIVisPropertiesAbstract` |
| `CATIVisPropertiesAbstract::SetPropertiesAtt(values, type, geomType)` | Apply a `CATVisPropertiesValues` set for the given property/geometry type |
| `CATIVisPropertiesAbstract::GetPropertiesAtt(values, type, geomType)` | Read the current property/geometry values |
| `CATVisPropertiesValues::SetColor(r,g,b,alpha=0)` / `GetColor()` | Fill-color RGB (0–255 each) |
| `CATVisPropertiesValues::SetOpacity(opacity, unused)` / `GetOpacity()` | Transparency value |
| `CATVisPropertiesValues::SetShowAttr(CATShowAttribut)` / `GetShowAttr()` | Show/hide state |
| `CATVisPropertyType` (enum) | `CATVPColor`, `CATVPShow`, `CATVPSymbol`, `CATVPLineType`, `CATVPAllPropertyType`, ... |
| `CATVisGeomType` (enum) | `CATVPGlobalType` (whole object), `CATVPPoint`, ... |

## 4. Common Patterns

### 4.1 Color a Feature Based on Analysis Result

```cpp
CATISpecObject_var pFeature = ...;
CATIVisProperties_var pVis = pFeature;
if (NULL_var == pVis) return;

CATVisPropertiesValues values;
if (bPassedAnalysis) {
    values.SetColor(0, 255, 0);    // Green
} else {
    values.SetColor(255, 0, 0);    // Red
}
pVis->SetPropertiesAtt(values, CATVPColor, CATVPGlobalType);
```

### 4.2 Read Back Current Color

```cpp
CATVisPropertiesValues values;
HRESULT rc = pVis->GetPropertiesAtt(values, CATVPColor, CATVPGlobalType);
if (SUCCEEDED(rc)) {
    unsigned int r, g, b;
    values.GetColor(r, g, b);
}
```

### 4.3 Show/Hide a Feature

```cpp
CATVisPropertiesValues values;
values.SetShowAttr(CATShow);   // or CATNoShow to hide
pVis->SetPropertiesAtt(values, CATVPShow, CATVPGlobalType);
```

### 4.4 Batch Set Transparency on Analyzed Faces

```cpp
CATListOfCATFaces failedFaces = ...;
unsigned int opacity = 128;  // 50% transparent

for (int i = 1; i <= failedFaces.Size(); i++) {
    CATIVisProperties_var pVis = failedFaces[i];
    if (NULL_var == pVis) continue;

    CATVisPropertiesValues values;
    values.SetColor(255, 100, 100);   // Soft red
    values.SetOpacity(opacity, 0);
    pVis->SetPropertiesAtt(values, CATVPAllPropertyType, CATVPGlobalType);
}
```

### 4.5 Reset to Inherited Visual Properties

```cpp
CATVisPropertiesValues values;
values.ResetInheritance();  // Reset all properties to parent/inherited state
pVis->SetPropertiesAtt(values, CATVPAllPropertyType, CATVPGlobalType);
```

## 5. Related Capabilities

- **[cap.selection](selection.md)** — Selection set (`CATCSO`) and camera reframe (`CATIReframeCamera`)
- **[cap.feature_recognition](feature-recognition.md)** — Color-code features by type or analysis category
- **[cap.geometry_query](geometry-query.md)** — Highlight specific faces/edges found by geometric queries
- **[cap.assembly_tree](assembly-tree.md)** — Show/hide or color assembly components for BOM review
- **[cap.parameter_system](parameter-system.md)** — Drive visual states from parameter check results
