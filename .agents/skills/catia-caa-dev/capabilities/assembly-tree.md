---
id: cap.assembly_tree
title: Assembly Tree Traversal
category: capability
domain: infrastructure
keywords: [assembly, product, instance, reference, BOM, traversal, CATIProduct, component, children, occurrence]
apis: [CATIProduct, CATIDocRoots, CATInit, CATIMovable, CATAsmConstraintServices, CATICst]
frameworks: [CATAssemblyInterfaces, ProductStructure]
playbooks: [analyzer.geometry, block.visitor, workflow.batch]
requires: [mecmod.feature]
release: [R19, R28]
tags: [capability]
---

# Assembly Tree (装配树遍历)

Navigating the CATIA product structure to traverse assembly trees, resolve instance/reference relationships, and extract BOM data.

## ⚠️ 重要修正

早期版本文档存在多处虚构 API，已按官方本地 CAADoc 核实并修正，详见 [knowledge/product/assembly.md](../knowledge/product/assembly.md) 的完整修正表。要点：

- `CATIPrtContainer::GetRootProduct()` 不存在（`CATIPrtContainer` 是 Part 文档容器接口，只有 `GetGeometricContainer()`/`GetPart()`）。根 Product 应通过 `CATInit::GetRootContainer(IID_CATIProduct)` 或 `CATIDocRoots::GiveDocRoots()` 获取。
- `CATIChildren`、`CATIPrdIterator`、`CATIReference`、`CATIConstraints`、`CATIPosition` 均为虚构接口，CAADoc 中无任何匹配。
- 子组件遍历用 `CATIProduct::GetChildren()` / `GetAllChildren()`（直接返回值，非输出参数）。
- 参考名称（Part Number）用 `CATIProduct::GetPartNumber()`，不是 `CATIReference::GetPartNumber()`。
- 装配约束用静态服务类 `CATAsmConstraintServices::ListConstraints()`，约束对象类型是 `CATICst`。

## 1. Summary

Assembly tree traversal is the fundamental capability for walking the CATIA product hierarchy — from root product down to leaf components — resolving instance names, reference documents, positions, and constraints for BOM extraction, validation, and reporting.

## 2. Core Concepts

- **Product vs. Component**: A `CATIProduct` is a node in the assembly tree; it may reference a `CATPart` or `CATProduct` document
- **Instance vs. Reference**: Each occurrence in the tree has an instance name (`GetPrdInstanceName`) and resolves to a reference product (`GetReferenceProduct`) whose shared identity is `GetPartNumber`
- **Root access**: Entry point is `CATInit::GetRootContainer(IID_CATIProduct)` on the `CATDocument`, or the older `CATIDocRoots::GiveDocRoots()`
- **Child iteration**: `CATIProduct::GetChildren()` returns direct children; `GetAllChildren()` returns the full (deep) subtree — both are direct return values, not output parameters
- **Position chain**: `CATIMovable` exposes both the cumulative absolute transformation (`GetAbsPosition`) and the relative transformation to a given context (`GetPosition`)
- **BOM context**: Multi-level BOM requires recursive traversal with occurrence counting and path resolution
- **Shared references**: A single reference document may appear multiple times in the tree under different instances
- **Constraints**: Assembly constraints are not exposed on `CATIProduct` itself — they are queried via the static service `CATAsmConstraintServices::ListConstraints()`, returning a list of `CATICst`

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATInit` | `GetRootContainer(IID_CATIProduct)` — official entry point to a document's root product |
| `CATIDocRoots` | Older entry point; `GiveDocRoots()` returns the document's root element(s) |
| `CATIProduct` | Core product node interface; instance name, part number, children, reference access |
| `CATIMovable` | Absolute (`GetAbsPosition`) and relative (`GetPosition`) transformation of an instance |
| `CATAsmConstraintServices` | Static service class; `ListConstraints(CATIProduct*, CATLISTV(CATICst_var)&)` |
| `CATICst` | A single assembly constraint object (type, value, related elements) |

## 4. Common Patterns

### 4.1 Root-to-Leaf Recursive Traversal

```cpp
void TraverseProduct(CATIProduct_var pProduct, int depth) {
    CATUnicodeString partNumber = pProduct->GetPartNumber();
    CATUnicodeString instance;
    pProduct->GetPrdInstanceName(instance);

    // Process current node (e.g., BOM collection)
    CollectBOMEntry(pProduct, depth, partNumber, instance);

    // GetChildren() is a direct return, not an output parameter;
    // its element type is CATBaseUnknown_var, cast each entry to CATIProduct_var
    CATListValCATBaseUnknown_var* pChildren = pProduct->GetChildren();
    if (pChildren != NULL) {
        for (int i = 1; i <= pChildren->Size(); i++) {
            CATIProduct_var child = (*pChildren)[i];
            if (child != NULL_var) {
                TraverseProduct(child, depth + 1);
            }
        }
        delete pChildren;
    }
}
```

### 4.2 Get Absolute Position (World Transform)

```cpp
CATIMovable_var pMovable = pProduct;
CATMathTransformation worldTransform;
pMovable->GetAbsPosition(worldTransform);

CATMathPoint origin;
origin.SetCoord(0, 0, 0);
CATMathPoint worldOrigin = worldTransform.ApplyToPoint(origin);
```

### 4.3 BOM Extraction (Flat List with Occurrence Count)

```cpp
void ExtractBOM(CATDocument* pProductDocument,
                CATListValCATUnicodeString& partNumbers,
                CATListOfInt& counts) {
    CATInit* pInit = NULL;
    pProductDocument->QueryInterface(IID_CATInit, (void**)&pInit);
    CATIProduct_var root = pInit->GetRootContainer(IID_CATIProduct);
    pInit->Release();

    if (root != NULL_var) {
        CountInstances(root, partNumbers, counts);
    }
}

void CountInstances(CATIProduct_var pNode,
                    CATListValCATUnicodeString& numbers,
                    CATListOfInt& counts) {
    CATUnicodeString partNumber = pNode->GetPartNumber();

    // Aggregate counts across occurrences
    int idx = FindInList(partNumber, numbers);
    if (idx > 0) {
        counts[idx]++;
    } else {
        numbers.Append(partNumber);
        counts.Append(1);
    }

    // Recurse into children
    CATListValCATBaseUnknown_var* pChildren = pNode->GetChildren();
    if (pChildren != NULL) {
        for (int i = 1; i <= pChildren->Size(); i++) {
            CATIProduct_var child = (*pChildren)[i];
            if (child != NULL_var) {
                CountInstances(child, numbers, counts);
            }
        }
        delete pChildren;
    }
}
```

### 4.4 Reading Assembly Constraints

```cpp
#include "CATAsmConstraintServices.h"
#include "CATICst.h"

CATIProduct_var pReferenceProduct = ...;   // must be a reference product, not an instance
CATLISTV(CATICst_var) constraints;
HRESULT hr = CATAsmConstraintServices::ListConstraints(pReferenceProduct, constraints);
if (SUCCEEDED(hr)) {
    for (int i = 1; i <= constraints.Size(); i++) {
        CATICst_var pCst = constraints[i];
        CATLONG32 cstType = pCst->GetCstType();
        // process constraint...
    }
}
```

## 5. Related Capabilities

- **[cap.geometry_query](geometry-query.md)** — Query geometric bodies from leaf product instances
- **[cap.feature_recognition](feature-recognition.md)** — Identify feature types within part references
- **[cap.visualization](visualization.md)** — Apply show/hide and color to assembly nodes
- **[cap.parameter_system](parameter-system.md)** — Read/write parameters on product and part nodes
