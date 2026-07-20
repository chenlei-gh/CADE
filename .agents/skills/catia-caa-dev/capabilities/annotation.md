---
id: cap.annotation
title: 3D Annotation (TPS / FTA / PMI)
category: capability
domain: infrastructure
keywords: [annotation, PMI, FTA, TPS, dimension, tolerance, datum, roughness, capture, 3D view, GD&T, semantic]
apis: [CATITPS, CATITPSComponent, CATITPSFactoryElementary, CATITPSFactoryAdvanced, CATITPSFactoryTTRS, CATITPSCaptureFactory, CATITPSViewFactory, CATITPSDocument, CATITPSSet, CATITPSCapture, CATITPSView, CATITPSList, CATITPSRetrieveServices]
frameworks: [CATTPSInterfaces]
playbooks: [analyzer.rule, analyzer.geometry, ui.result_dialog]
requires: [mecmod.feature, mecmod.topology]
release: [R19, R28]
tags: [capability]
---

# 3D Annotation / TPS / FTA (三维标注)

Creating and querying 3D PMI (Product Manufacturing Information) annotations — dimensions, tolerances, datums, roughness symbols, flag notes — through the TPS (Technological Product Specification) object model used by the FTA (Functional Tolerancing & Annotation) workbench.

## ⚠️ 重要修正

旧版本文档中几乎所有接口名/方法名/工作流程均为虚构，经 CAADoc（`CATTPSInterfaces` 框架）和官方 `CAATpiXxx` 教学用例核实修正：

| 旧写法（虚构） | 真实情况 |
|---------------|---------|
| Framework `CATAnalysisGPSInterfaces` | 真实框架是 **`CATTPSInterfaces`**（`CATAnalysisGPSInterfaces` 是完全不同的模块，用于 GPS 传感器/结构模板分析，与 3D 标注无关） |
| `CATITPSFactory`（单一工厂接口） | **不存在**。标注创建拆分为多个工厂接口，获取方式分两类：全局单例 **`CATITPSFactoryAdvanced`**（直接对几何选择创建标注，如 `CreateTextOnGeometry`）、**`CATITPSFactoryTTRS`**（从几何选择构造 `CATITTRS` 参考面）；挂在 `CATITPSSet` 实例上的 **`CATITPSFactoryElementary`**（基础创建，产出未完全赋值的标注）、**`CATITPSCaptureFactory`**、**`CATITPSViewFactory`** |
| `pTPSFactory = pTPSContainer`（直接类型转换获取工厂） | **只有 `CATITPSFactoryAdvanced`/`CATITPSFactoryTTRS`/`CATITPSRetrieveServices` 是全局单例**，通过全局函数 **`CATTPSInstantiateComponent(CATTPSComponent iComp, void** opiComp)`** 获取（`iComp` 取值如 `DfTPS_ItfTPSFactoryAdvanced=13`/`DfTPS_ItfTPSFactoryTTRS=32`）。**`CATITPSFactoryElementary` 不在此列**——真实枚举 `CATTPSComponent` 里根本不存在 `DfTPS_ItfTPSFactoryElementary` 这个值；`CATITPSFactoryElementary` 实际是挂在 **`CATITPSSet`** 实例上的接口，需要对一个 Set 做 `QueryInterface(IID_CATITPSFactoryElementary, ...)` 才能拿到（发布产品字典 `CATTPSSet.dic` 证实） |
| `CATITPSAnnotation`（作为公共基接口） | **不存在**。多态基接口是 **`CATITPSComponent`**（纯标记接口，无任何方法）；真正携带数据的公共接口是 **`CATITPS`**（只有 `GetSet()`/`GetTTRS()`/`SetTTRS()`），名字/类型需通过 `CATIAlias`（名字）和 QueryInterface 到具体子接口（类型判断） |
| `CATITPSCapture::Activate()`/`SetViewDirection()`/`AddAnnotation()`/`RemoveAnnotation()` | 均不存在。激活当前 Capture 用 **`SetCurrent(TRUE)`**；相机用 **`SetCamera(CATI3DCamera*)`**；管理其标注用 **`SetTPSs(CATITPSList*)`**/`GetTPSs()`（整体替换列表，非逐个 Add/Remove） |
| `pTPSFactory->CreateCaptureView()` / `pTPSSet->CreateCapture()` | **不存在**。`CATITPSSet` 本身**没有** `CreateCapture()`/`CreateView()` 方法（它只有 Get/Set 存取方法）。真实创建方式：对同一个 `CATITPSSet` 实例做 `QueryInterface(IID_CATITPSCaptureFactory, ...)` 拿到 **`CATITPSCaptureFactory`**，再调用其 **`CreateCapture(CATITPSCapture**)`**；`CATITPSView` 同理，通过 `QueryInterface(IID_CATITPSViewFactory, ...)` 拿到 **`CATITPSViewFactory::CreateView(...)`**。三个工厂接口（`CATITPSFactoryElementary`/`CATITPSCaptureFactory`/`CATITPSViewFactory`）都是这种“挂在 Set 上、QueryInterface 获取”的模式，与全局单例工厂（`CATITPSFactoryAdvanced`/`CATITPSFactoryTTRS`）的获取方式不同 |
| `CATITPSDimension::SetNominalValue()`/`SetUpperTolerance()`/`SetLowerTolerance()` | `CATITPSDimension` 本身是纯类型标记接口（无方法）。实际数值方法在 **`CATITPSDimensionLimits`** 接口上：`GetNominalValue()`、`SetLimits(bottom, up)`、`SetSingleLimit()`、`SetModifier()` 等 |
| `pTPSFactory->CreateLinearDimension(face1, face2)` | 不存在这种便捷签名。真实流程：先用 `CATITPSFactoryTTRS::GetTTRS()`（全局单例工厂）把几何包装成 `CATITTRS`，再对 `CATITPSSet` 实例 QueryInterface 到 `CATITPSFactoryElementary`，用 `CreateSemanticDimension(ttrs, CATTPSDimensionType, CATTPSLinearDimensionSubType, &dimension)` 创建 |
| `pTPSFactory->CreateGeometricTolerance(face)` + `SetSymbol()`/`AddDatumReference()`/`SetModifier(MMC)` | 不存在。真实创建是 **`CreateToleranceWithDRF(CATTPSTypeWithDRF, ttrs, refFrame, &tol)`**（带基准参考框）或 **`CreateToleranceWithoutDRF(CATTPSTypeWithoutDRF, ttrs, &tol)`**（形位公差，如平面度）；材料条件修饰符（MMC等）通过独立的 **`CATITPSMaterialCondition::SetModifier()`** 接口设置 |
| `pTPSFactory->CreateDatum(plane)` + `pDatum->SetLabel()` | `CreateDatum()` 存在但返回 `CATITPSDatumSimple`（不是泛型 `CATITPSDatum`——`CATITPSDatum` 也是纯类型标记接口）。`SetLabel()`/`GetTargets()` 等真实数据方法都在 `CATITPSDatumSimple` 上 |
| `pAnnot->IsATypeOf(CATITPSDimension::ClassName())` | 类型判断应通过 **`QueryInterface(IID_CATITPSDimension, ...)`** 到具体的类型标记接口，而不是字符串比较 |
| `pAnnot->GetType()`/`pAnnot->GetName()` | 不存在于任何 TPS 接口。名字通过 QueryInterface 到 **`CATIAlias`** 后调用 `GetAlias()` 获取 |
| `pCapture->GetAllAnnotations(list)` 返回 `CATListValCATITPSAnnotation_var` | 不存在这种模板列表类型。真实容器是 **`CATITPSList`**（`Count(&n)`/`Item(pos, &item)`——**0-based** 索引/`Add()`/`Remove()`），元素是 `CATITPSComponent*` |
| 查询"哪些标注关联某几何"没有对应 API | 真实方法是 **`CATITPSRetrieveServices::RetrieveTPSsFromPath(CATPathElement*, CATIProduct*, CATITPSList**)`** |

## 1. Summary

3D annotation (TPS) creation and query is split across three factory interfaces obtained through the global `CATTPSInstantiateComponent()` function (not QueryInterface on a container), a family of typing/marker interfaces (`CATITPSComponent`, `CATITPSDimension`, `CATITPSDatum`, `CATITPSForm`, ...) used purely for polymorphic classification via QueryInterface, and dedicated data interfaces (`CATITPSDimensionLimits`, `CATITPSDatumSimple`, `CATITPSMaterialCondition`, `CATITPSRoughness`, `CATITPSFlagNote`, ...) that carry the actual values. Annotations are organized into `CATITPSSet` (a document-level tolerancing set) containing `CATITPSCapture` (a saved 3D view of a subset of annotations) and `CATITPSView` (a support plane for annotations, associated with a drafting view).

## 2. Core Concepts

- **TTRS (Tolerant Topological Reference Surface)**: The geometry-agnostic reference object every TPS annotation attaches to; built from a `CATSO` (Selected Object) geometry selection via `CATITPSFactoryTTRS::GetTTRS()`, or created implicitly by `CATITPSFactoryAdvanced`'s `*OnGeometry` methods
- **Typing (marker) interfaces vs. data interfaces**: `CATITPSComponent` (root), `CATITPSDimension`, `CATITPSDatum`, `CATITPSForm` are pure "is-a" markers with no methods — always QueryInterface further to a data-bearing interface (`CATITPSDimensionLimits`, `CATITPSDatumSimple`, `CATITPSFlatness`, ...) to read/write values
- **CATITPS**: The minimal common data interface shared by (almost) all annotations — links an annotation to its owning `CATITPSSet` and to the `CATITTRS` list it is applied on
- **Factory split**: `CATITPSFactoryElementary` creates a bare, not-yet-fully-valuated annotation attached to a pre-built `CATITTRS`; `CATITPSFactoryAdvanced` is the convenience layer used by interactive commands — it takes a `CATSO*` + `CATMathPlane*` directly and builds the TTRS internally. Two different acquisition patterns: `CATITPSFactoryAdvanced`/`CATITPSFactoryTTRS`/`CATITPSRetrieveServices` are global singletons fetched via `CATTPSInstantiateComponent()`; `CATITPSFactoryElementary`/`CATITPSCaptureFactory`/`CATITPSViewFactory` are instead implemented directly on a `CATITPSSet` instance and must be obtained via `QueryInterface` on that Set
- **CATITPSSet**: The document-level aggregation of all TPS objects for a given part/product reference (`GetTPSs()`/`SetTPSs()`, `GetTTRSs()`, `GetViews()`, `GetCaptures()`, `GetActiveView()`/`SetActiveView()`, `GetStandard()`). It has no `CreateCapture()`/`CreateView()` methods of its own — QueryInterface it to `CATITPSCaptureFactory`/`CATITPSViewFactory` to create those
- **CATITPSCapture**: A named, saved 3D view of a chosen subset of annotations (which `CATITPSs` are shown, the camera, clipping plane, hide/show state); exactly one capture per set can be `SetCurrent(TRUE)` at a time
- **CATITPSView**: A support plane for annotations, tied to an associated 2D drafting view; created via `CATITPSViewFactory::CreateView()`
- **CATITPSList**: The generic, 0-based collection type used throughout TPS APIs (`Count`/`Item`/`Add`/`Remove`) instead of `CATListValXxx_var` templates
- **Name/type discovery**: An annotation's display name comes from `CATIAlias::GetAlias()` (via QueryInterface); its concrete kind is discovered by QueryInterface-ing to the relevant typing interface, not by a string-returning `GetType()`

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATTPSInstantiateComponent(CATTPSComponent, void**)` | Global function to retrieve the global-singleton TPS factories/services (e.g. `DfTPS_ItfTPSFactoryAdvanced`, `DfTPS_ItfTPSFactoryTTRS`, `DfTPS_ItfRetrieveServices`). Does **not** cover `CATITPSFactoryElementary`/`CATITPSCaptureFactory`/`CATITPSViewFactory` — see next row |
| `CATITPSSet::QueryInterface(IID_CATITPSFactoryElementary/CATITPSCaptureFactory/CATITPSViewFactory, ...)` | The other acquisition path: these three factory interfaces are implemented directly on a `CATITPSSet` instance, not fetched via `CATTPSInstantiateComponent()` |
| `CATITPSFactoryTTRS::GetTTRS()` | Builds a `CATITTRS` reference surface from a `CATSO` geometry selection |
| `CATITPSFactoryElementary` | Low-level creation (obtained via QueryInterface on a `CATITPSSet`): `CreateSemanticDimension`, `CreateNonSemanticDimension`, `CreateToleranceWithDRF`/`WithoutDRF`, `CreateDatum`, `CreateDatumTarget`, `CreateDatumReferenceFrame`, `CreateRoughness`, `CreateFlagNote`, `CreateText`, `CreateTextNOA` |
| `CATITPSFactoryAdvanced` | High-level creation directly from a geometry selection (global singleton): `CreateTextOnGeometry`, `CreateFlagNoteOnGeometry`, `CreateNOAOnGeometry`, `CreateWeldOnGeometry`, `CreateTextOnAnnotation` |
| `CATITPSCaptureFactory::CreateCapture(CATITPSCapture**)` | Creates a capture on a `CATITPSSet` (obtained via QueryInterface on that Set) |
| `CATITPSViewFactory::CreateView(...)` | Creates a view on a `CATITPSSet` (obtained via QueryInterface on that Set) |
| `CATITPSDocument` | Document-level entry point: `GetSets()`, `GetBags()`, `GetTolerancingContainer()` |
| `CATITPSSet` | Aggregates a document's TPS objects: `GetTPSs()`/`SetTPSs()`, `GetTTRSs()`, `GetCaptures()`, `GetViews()`, `GetActiveView()`/`SetActiveView()`, `GetStandard()`. No `CreateCapture()`/`CreateView()` of its own |
| `CATITPSCapture` | A saved 3D annotation view: `SetTPSs()`/`GetTPSs()`, `SetCurrent()`, `SetCamera()`, `SetClippingPlane()` |
| `CATITPSDimensionLimits` | Numeric data of a dimension: `GetNominalValue()`, `SetLimits()`, `SetSingleLimit()`, `SetModifier()` |
| `CATITPSDatumSimple` | Datum data: `SetLabel()`/`GetLabel()`, `SetTargets()`/`GetTargets()` |
| `CATITPSMaterialCondition` | GD&T material condition modifier (MMC/LMC/RFS) on a tolerance or one of its datum references |
| `CATITPSRetrieveServices::RetrieveTPSsFromPath()` | Finds all TPS annotations linked to a selected `CATPathElement` |
| `CATITPSList` / `CATCreateCATITPSList()` | Generic 0-based collection (`Count()`, `Item()`, `Add()`, `Remove()`); instantiated via the global function `CATCreateCATITPSList(CATITPSList* iCopy, CATITPSList** oList)`, not a factory |

## 4. Common Patterns

### 4.1 Retrieve the TPS Factories

```cpp
#include "CATTPSInstantiateComponent.h"
#include "CATITPSFactoryTTRS.h"
#include "CATITPSFactoryElementary.h"

// CATITPSFactoryTTRS is a global singleton, retrieved through the
// global function -- NOT by QueryInterface on a document/container
CATITPSFactoryTTRS* pFactTTRS = NULL;
HRESULT rc = CATTPSInstantiateComponent(DfTPS_ItfTPSFactoryTTRS, (void**)&pFactTTRS);

// CATITPSFactoryElementary is NOT a global singleton -- there is no
// DfTPS_ItfTPSFactoryElementary enum value. It is implemented directly
// on a CATITPSSet instance, so it must be obtained via QueryInterface
// on that Set (same pattern as CATITPSCaptureFactory/CATITPSViewFactory).
CATITPSSet* pTPSSet = ...;  // retrieved e.g. from CATITPSDocument::GetSets()
CATITPSFactoryElementary* pFactElem = NULL;
rc = pTPSSet->QueryInterface(IID_CATITPSFactoryElementary, (void**)&pFactElem);
```

### 4.2 Create a Semantic Linear Dimension Between Two Faces

```cpp
// 1) Wrap the geometry selection into a CATITTRS reference
CATSO* pGeometrySelected = ...;  // e.g. built from a face path
CATITTRS* pTTRS = NULL;
pFactTTRS->GetTTRS(pGeometrySelected, &pTTRS);

// 2) Create the semantic dimension on that reference
CATITPSDimension* pDimension = NULL;
rc = pFactElem->CreateSemanticDimension(pTTRS, CATTPSDimensionTypeLinear,
                                         CATTPSLinearDimensionSubTypeStandard,
                                         &pDimension);

// 3) CATITPSDimension itself has no data methods -- query the data interface
CATITPSDimensionLimits* pLimits = NULL;
pDimension->QueryInterface(IID_CATITPSDimensionLimits, (void**)&pLimits);
if (pLimits) {
    pLimits->SetLimits(-0.05, 0.1);  // lower/upper tolerance in millimeters
    pLimits->Release();
}

pTTRS->Release();
pDimension->Release();
```

### 4.3 Create a Flatness Tolerance (Form Tolerance, No DRF)

```cpp
CATITTRS* pTTRS = NULL;
pFactTTRS->GetTTRS(pTargetFaceSelected, &pTTRS);

// Flatness has no Datum Reference Frame
CATITPSForm* pFlatness = NULL;
rc = pFactElem->CreateToleranceWithoutDRF(CATTPSTypeWithoutDRFFlatness, pTTRS, &pFlatness);

// The tolerance zone value itself is read/written through CATITPSDimensionLimits
CATITPSDimensionLimits* pLimits = NULL;
pFlatness->QueryInterface(IID_CATITPSDimensionLimits, (void**)&pLimits);
if (pLimits) {
    pLimits->SetSingleLimit(0.05);  // 0.05 mm tolerance zone
    pLimits->Release();
}

pTTRS->Release();
pFlatness->Release();
```

### 4.4 Create a Datum and Assign It as a Material-Condition Reference

```cpp
CATITTRS* pDatumTTRS = NULL;
pFactTTRS->GetTTRS(pDatumPlaneSelected, &pDatumTTRS);

CATITPSDatumSimple* pDatum = NULL;
rc = pFactElem->CreateDatum(pDatumTTRS, &pDatum);
pDatum->SetLabel(L"A");

// Apply a material condition modifier to a tolerance's datum reference
// (pTolerance was created via CreateToleranceWithDRF and implements
// CATITPSMaterialCondition on its Datum Reference Frame entries)
CATITPSMaterialCondition* pMatCond = NULL;
pTolerance->QueryInterface(IID_CATITPSMaterialCondition, (void**)&pMatCond);
if (pMatCond) {
    pMatCond->SetModifier(CATTPSMaterialConditionMMC, pDatum);
    pMatCond->Release();
}

pDatumTTRS->Release();
pDatum->Release();
```

### 4.5 Organize Annotations into a Capture View

```cpp
CATITPSSet* pTPSSet = ...;  // Retrieved from CATITPSDocument::GetSets()

// CATITPSSet has no CreateCapture() of its own -- QueryInterface it to
// CATITPSCaptureFactory, the interface that actually implements creation
CATITPSCaptureFactory* pCaptureFactory = NULL;
pTPSSet->QueryInterface(IID_CATITPSCaptureFactory, (void**)&pCaptureFactory);

// Create a new capture and make it the current one
CATITPSCapture* pCapture = NULL;
pCaptureFactory->CreateCapture(&pCapture);
pCapture->SetCurrent(TRUE);
pCaptureFactory->Release();

// Populate it with a list of TPS annotations to display
// (CATITPSList is instantiated via CATCreateCATITPSList, not a factory)
CATITPSList* pTPSList = NULL;
CATCreateCATITPSList(NULL, &pTPSList);
pTPSList->Add(0, (CATITPSComponent*)pDimension);
pTPSList->Add(1, (CATITPSComponent*)pFlatness);
pCapture->SetTPSs(pTPSList);

pCapture->Release();
```

### 4.6 Retrieve All Annotations Linked to a Selected Geometry Path

```cpp
CATITPSRetrieveServices* pRetrieveServices = NULL;
CATTPSInstantiateComponent(DfTPS_ItfRetrieveServices, (void**)&pRetrieveServices);

CATPathElement* pPathSelected = ...;  // From a selection agent
CATITPSList* pTPSList = NULL;
HRESULT rc = pRetrieveServices->RetrieveTPSsFromPath(pPathSelected, NULL, &pTPSList);

if (SUCCEEDED(rc) && pTPSList) {
    unsigned int count = 0;
    pTPSList->Count(&count);
    for (unsigned int i = 0; i < count; i++) {  // 0-based!
        CATITPSComponent* pItem = NULL;
        pTPSList->Item(i, &pItem);

        // Name via CATIAlias, type via QueryInterface to the specific interface
        CATIAlias* pAlias = NULL;
        pItem->QueryInterface(IID_CATIAlias, (void**)&pAlias);
        if (pAlias) {
            CATUnicodeString name = pAlias->GetAlias();
            pAlias->Release();
        }

        CATITPSDimension* pAsDimension = NULL;
        if (SUCCEEDED(pItem->QueryInterface(IID_CATITPSDimension, (void**)&pAsDimension))) {
            // It is a dimension tolerance; query CATITPSDimensionLimits for its value
            pAsDimension->Release();
        }

        pItem->Release();
    }
}
```

## 5. Related Capabilities

- **[cap.visualization](visualization.md)** — Highlight geometry that has associated annotations or missing PMI
- **[cap.geometry_query](geometry-query.md)** — Build the `CATSO`/`CATPathElement` geometry selection that a TPS annotation attaches to
- **[cap.feature_recognition](feature-recognition.md)** — Identify feature types to determine which annotations are applicable
- **[cap.selection](selection.md)** — Select geometry or existing annotation objects in the 3D view
