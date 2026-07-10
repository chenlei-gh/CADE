---
id: cap.assembly_tree
title: Assembly Tree Traversal
category: capability
domain: infrastructure
keywords: [assembly, product, instance, reference, BOM, traversal, CATIProduct, component, children, occurrence]
apis: [CATIProduct, CATIPrtContainer, CATIChildren, CATIPrdIterator, CATIMovable, CATIReference]
frameworks: [CATAssemblyInterfaces, ProductStructure]
playbooks: [analyzer.geometry, block.visitor, workflow.batch]
requires: [mecmod.feature]
release: [R19, R28]
tags: [capability]
---

# Assembly Tree (装配树遍历)

Navigating the CATIA product structure to traverse assembly trees, resolve instance/reference relationships, and extract BOM data.

## 1. Summary

Assembly tree traversal is the fundamental capability for walking the CATIA product hierarchy — from root product down to leaf components — resolving instance names, reference documents, positions, and constraints for BOM extraction, validation, and reporting.

## 2. Core Concepts

- **Product vs. Component**: A `CATIProduct` is a node in the assembly tree; it may reference a `CATPart` or `CATProduct` document
- **Instance vs. Reference**: Each occurrence in the tree has an instance name (user-visible) and a reference (the linked document)
- **Root access**: Entry point is `CATIPrtContainer::GetRootProduct()` from the session document
- **Child iteration**: `CATIChildren` provides access to immediate children; `CATIPrdIterator` enables depth-first / breadth-first traversal
- **Position chain**: `CATIMovable` exposes the cumulative transformation (absolute position) from root to leaf
- **BOM context**: Multi-level BOM requires recursive traversal with occurrence counting and path resolution
- **Shared references**: A single reference document may appear multiple times in the tree under different instances
- **Constraints**: Assembly constraints (`CATIConstraints`) live on product nodes and relate instances

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATIPrtContainer` | Top-level container for a CATProduct document; provides `GetRootProduct()` |
| `CATIProduct` | Core product node interface; name, instance name, children, reference access |
| `CATIChildren` | Interface to enumerate child products of a node |
| `CATIPrdIterator` | Iterator for controlled-depth traversal (pre-order, post-order, leaf-only) |
| `CATIReference` | Resolves the document reference behind a product instance |
| `CATIMovable` | Absolute position (transformation matrix) of an instance in world space |
| `CATIConstraints` | Access assembly constraints defined on a product node |
| `CATIPosition` | Read/set relative position between parent and child instance |

## 4. Common Patterns

### 4.1 Root-to-Leaf Recursive Traversal

```cpp
void TraverseProduct(CATIProduct_var pProduct, int depth) {
    CATUnicodeString name = pProduct->GetName();
    CATUnicodeString instance = pProduct->GetInstanceName();

    // Process current node (e.g., BOM collection)
    CollectBOMEntry(pProduct, depth, name, instance);

    // Get children
    CATIChildren_var pChildren = pProduct;
    CATListValCATIProduct_var childList;
    pChildren->GetChildren(childList);

    for (int i = 1; i <= childList.Size(); i++) {
        TraverseProduct(childList[i], depth + 1);
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
void ExtractBOM(CATIPrtContainer* pContainer,
                CATListValCATUnicodeString& partNumbers,
                CATListOfInt& counts) {
    CATIProduct_var root = pContainer->GetRootProduct();
    CountInstances(root, partNumbers, counts);
}

void CountInstances(CATIProduct_var pNode,
                    CATListValCATUnicodeString& numbers,
                    CATListOfInt& counts) {
    CATIReference_var ref = pNode;
    CATUnicodeString partNumber = ref->GetPartNumber();

    // Aggregate counts across occurrences
    int idx = FindInList(partNumber, numbers);
    if (idx > 0) {
        counts[idx]++;
    } else {
        numbers.Append(partNumber);
        counts.Append(1);
    }

    // Recurse into children
    CATIChildren_var children = pNode;
    CATListValCATIProduct_var childList;
    children->GetChildren(childList);
    for (int i = 1; i <= childList.Size(); i++) {
        CountInstances(childList[i], numbers, counts);
    }
}
```

## 5. Related Capabilities

- **[cap.geometry_query](geometry-query.md)** — Query geometric bodies from leaf product instances
- **[cap.feature_recognition](feature-recognition.md)** — Identify feature types within part references
- **[cap.visualization](visualization.md)** — Apply show/hide and color to assembly nodes
- **[cap.parameter_system](parameter-system.md)** — Read/write parameters on product and part nodes
