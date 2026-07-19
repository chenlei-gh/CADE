---
id: cap.surface_operations
title: Surface Operations (GSD)
category: capability
domain: infrastructure
keywords: [surface, GSD, extrude, sweep, offset, split, develop, CATGSM, generative shape design]
apis: [CATIGSMFactory, CATIGSMExtrude, CATIGSMOffset, CATIGSMSplit, CATIGSMAssemble, CATIGSMDevelop]
frameworks: [GSMInterfaces, GSOInterfaces]
playbooks: [analyzer.geometry, block.visitor, workflow.batch]
requires: [mecmod.feature, mecmod.topology]
release: [R19, R28]
tags: [capability]
---

# Surface Operations / GSD (曲面操作)

Creating and manipulating GSD (Generative Shape Design) surfaces — extrude, sweep, offset, join (assemble), split, and develop — for complex surface modeling and analysis workflows.

## ⚠️ 重要修正

旧版本文档中的多个接口名、工厂方法和 setter 方法均为虚构，经 CAADoc（`GSMInterfaces`/`GSOInterfaces` 框架）核实修正如下：

| 旧写法（虚构） | 真实情况 |
|---------------|---------|
| `CATIGSMJoin` 接口 | 不存在。合并曲面/曲线的真实接口是 **`CATIGSMAssemble`**，由 `CATIGSMFactory::CreateAssemble(list, devUser, connex)` 创建 |
| `CATIGSMRevolute` | 不存在。旋转曲面接口名是 **`CATIGSMRevol`** |
| `CATIGSMTrim` 独立创建方式 | `CATIGSMTrim` 接口确实存在，但没有对应 `CreateTrim()`；Trim 概念在 GSM 中通常通过 `CreateSplit()` 组合两个方向的 Split 实现 |
| `CATIGSMBoundary`/`CATIGSMFill` | 接口名真实存在，但下方示例代码未覆盖，本次未展开核实其方法签名 |
| `pExtrude->SetProfile()/SetDirection()/SetLimit1()/SetLimit2()` | `CATIGSMExtrude` 真实 setter 是 `SetProfil()`（法语拼写，无 e）、`SetDir(CATIGSMDirection_var)`、`SetFirstLimitValue()`/`SetSecondLimitValue()`；且工厂方法 `CreateExtrude(profile, direction, length1, length2, orientation)` 通常一次性把这些都传入，不必逐个 setter 调用 |
| `pOffset->SetSurface()/SetOffset()/SetBothSidesOffset()` | `CATIGSMOffset` 真实 setter 是 `SetProfil()`（参考面）、`SetOffsetValue()`（偏移值）；没有 `SetBothSidesOffset()` 方法。工厂方法是 `CreateOffset(surface, offsetValue, invertDirection, suppressMode)` |
| `pJoin->AddElements()/SetMergingTolerance()` | 应为 `CATIGSMAssemble`；工厂方法 `CreateAssemble(CATLISTV(CATISpecObject_var)& list, iDevUser, iConnex)` 一次性传入要合并的元素列表，没有单独的 `AddElements`/`SetMergingTolerance` 方法 |
| `pSweep->SetSweepType(...)`, `SetProfile()`, `SetGuideCurve()`, `SetSpine()` | `CATIGSMFactory` 没有通用 `CreateSweep()`；而是按扫描子类型分别调用 `CreateExplicitSweep(guide, profile, ...)`、`CreateLinearSweep(guide1, guide2)`、`CreateCircularSweep(...)`、`CreateConicalSweep(...)`，返回不同的具体接口（`CATIGSMSweepUnspec`/`CATIGSMSweepSegment`/`CATIGSMSweepCircle`/`CATIGSMSweepConic`） |
| `pDevelop->SetSurface()/SetReferencePoint()/SetDirection()/GetResult()` | `CATIGSMDevelop`（属于 `GSOInterfaces` 框架，不是 `GSMUseItf`）真实 setter 是 `SetSupport()`（展开所依赖的曲面）、`SetWireToDevelop()`（要展开的平面线框）、`SetPlaneAxisOrigin()`/`SetPlaneAxisDirection()`（定位轴），没有 `GetResult()` 方法 |
| `pSplit->SetElementToSplit()/AddCuttingElement()/SetOrientation(int)` | 真实方法是 `SetElemToCut()`、`AddCuttingElem(elem, CATGSMOrientation)`、`SetOrientation(CATGSMOrientation, int rank=...)`（枚举类型而非 int） |

## 1. Summary

The surface operations capability provides programmatic control over the CATIA GSD workbench: creating surface features (extrude, sweep) via `CATIGSMFactory`, modifying existing surfaces (offset, split, assemble/join), and applying develop/flatten operations for sheet metal and composite blank development.

## 2. Core Concepts

- **GSD feature model**: Surface features are spec objects (`CATISpecObject`) created by `CATIGSMFactory` and inserted into a `GeometricalSet`/`OrderedGeometricalSet`
- **Factory-driven creation**: Most GSD features are created by calling a specific `CreateXxx(...)` method on `CATIGSMFactory` that takes the key inputs directly as parameters (not built up incrementally through setters), then optionally refined via setters on the returned specific interface
- **Assemble (not "Join")**: Merging surfaces/curves is done via `CATIGSMAssemble`, created with `CreateAssemble(listOfElementsToAssemble, iDevUser, iConnex)`
- **Sweep family has no single generic interface**: each sweep subtype (explicit, linear, circular, conical) has its own factory method and its own result interface
- **Split**: `CATIGSMSplit` cuts one element with one or more cutting elements (`SetElemToCut`, `AddCuttingElem`), with `CATGSMOrientation` controlling which side is kept
- **Develop/Flatten**: `CATIGSMDevelop` lives in the `GSOInterfaces` framework (not `GSMUseItf`), and maps a planar wire onto a 3D revolution/reference surface (or the inverse), driven by `SetSupport`/`SetWireToDevelop`/positioning parameters

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATIGSMFactory` | Central factory for creating all GSD surface and wireframe features |
| `CATIGSMFactory::CreateExtrude(profile, direction, length1, length2, orientation)` | Create an extruded surface in one call |
| `CATIGSMExtrude` | Result interface; refine via `SetFirstLimitValue`/`SetSecondLimitValue`/`SetDir`/`SetProfil` |
| `CATIGSMFactory::CreateOffset(surface, offsetValue, invertDirection, suppressMode)` | Create a parallel/offset surface |
| `CATIGSMFactory::CreateAssemble(listOfElements, devUser, connex)` | Merge (assemble/"join") multiple curves or surfaces |
| `CATIGSMFactory::CreateSplit()` / `CreateSplit(toCut, cutting, orientation)` | Create a split element |
| `CATIGSMSplit` | Refine via `SetElemToCut`, `AddCuttingElem`, `SetOrientation` |
| `CATIGSMFactory::CreateExplicitSweep(...)` / `CreateLinearSweep(...)` / `CreateCircularSweep(...)` / `CreateConicalSweep(...)` | Create the specific sweep subtype needed |
| `CATIGSMDevelop` (`GSOInterfaces`) | Flatten/develop a planar wire against a reference surface: `SetSupport`, `SetWireToDevelop`, `SetPosMode`, `SetPlaneAxisOrigin` |

## 4. Common Patterns

### 4.1 Create an Extruded Surface

```cpp
CATIGSMFactory_var pGSMFactory = pGeomSet;
CATIGSMDirection_var pDirection = ...; // e.g. an axis or line feature

CATIGSMExtrude_var pExtrude = pGSMFactory->CreateExtrude(
    pProfileCurve, pDirection,
    /*length1*/ NULL_var, /*length2*/ NULL_var, /*orientation*/ FALSE);

// Refine limits after creation
pExtrude->SetFirstLimitValue(100.0);  // 100 mm extrusion
pExtrude->SetSecondLimitValue(0.0);   // no reverse extrusion

pExtrude->GetImmediateParent()->Update();  // Compute the result
```

### 4.2 Create an Offset Surface

```cpp
CATIGSMFactory_var pGSMFactory = pGeomSet;

CATIGSMOffset_var pOffset = pGSMFactory->CreateOffset(
    pBaseSurface, /*offsetValue*/ NULL_var,
    /*invertDirection*/ FALSE, /*suppressMode*/ FALSE);

pOffset->SetOffsetValue(5.0);  // 5 mm offset
```

### 4.3 Assemble (Join) Multiple Surfaces

```cpp
CATIGSMFactory_var pGSMFactory = pGeomSet;

CATLISTV(CATISpecObject_var) surfaces;
surfaces.Append(pSurface1);
surfaces.Append(pSurface2);
surfaces.Append(pSurface3);

CATIGSMAssemble_var pAssemble = pGSMFactory->CreateAssemble(surfaces);
```

### 4.4 Explicit Sweep Along a Guide Curve

```cpp
CATIGSMFactory_var pGSMFactory = pGeomSet;

// CreateExplicitSweep(guide, profile, instanciateTransfo)
CATIGSMSweepUnspec_var pSweep =
    pGSMFactory->CreateExplicitSweep(pGuideCurve, pProfileCurve, TRUE);
```

### 4.5 Develop (Flatten) a Wire Against a Support Surface

```cpp
CATIGSMFactory_var pGSMFactory = pGeomSet;
CATIGSMDevelop_var pDevelop = ...; // obtained via the appropriate factory call for develop

pDevelop->SetSupport(pRevolutionSurface);       // surface to develop against
pDevelop->SetWireToDevelop(pPlanarWire);        // planar wire being mapped
pDevelop->SetPlaneAxisOrigin(pOriginPoint);     // positioning
```

### 4.6 Split a Surface

```cpp
CATIGSMFactory_var pGSMFactory = pGeomSet;
CATIGSMSplit_var pSplit = pGSMFactory->CreateSplit();

pSplit->SetElemToCut(pSurface);
pSplit->AddCuttingElem(pCuttingCurve, CATGSMSameOrientation);
```

## 5. Related Capabilities

- **[cap.geometry_query](geometry-query.md)** — Query topology of generated surfaces for measurement and analysis
- **[cap.feature_recognition](feature-recognition.md)** — Identify existing surface feature types before modification
- **[cap.visualization](visualization.md)** — Color-code surfaces by operation type or analysis result
- **[cap.selection](selection.md)** — Select surface features and their input curves in the 3D view
