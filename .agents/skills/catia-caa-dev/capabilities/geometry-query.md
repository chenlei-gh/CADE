---
id: cap.geometry_query
title: Geometry Query
category: capability
domain: infrastructure
keywords: [geometry, body, face, edge, vertex, topology, traversal, CATBody, CATFace, area, length]
apis: [CATISpecObject, CATIMfBRep, CATBody, CATFace, CATEdge, CATGeoFactory, CATCell, CATShell, CATVertex]
frameworks: [MecModInterfaces, GMModelInterfaces, GeometricObjects]
playbooks: [analyzer.geometry, block.visitor]
requires: [mecmod.feature, mecmod.topology]
release: [R19, R28]
tags: [capability]
---

# Geometry Query (几何查询)

Querying geometric topology — bodies, faces, edges, and vertices — from CATIA features for measurement, analysis, and validation.

## ⚠️ 重要修正

旧版本文档中的多个方法名和框架名经 CAADoc（`GMModelInterfaces`/`MecModInterfaces`/`GeometricObjects` 框架）核实修正：

| 旧写法（虚构） | 真实情况 |
|---------------|---------|
| `CATISpecObject::GetBody()` | `CATISpecObject` 本身没有此方法。需先转换为 **`CATIMfBRep`** 接口（`MecModInterfaces` 框架），再调用其 `GetBody()` |
| `CATFace::GetArea()` | 不存在。真实方法是 **`CalcArea()`** |
| `CATEdge::GetLength()` | 不存在。真实方法是 **`CalcLength()`** |
| `CATVertex::GetCoordinates(point)` | 不存在。真实方法是 **`GetPoint()`**（返回 `CATPoint*`），再用 `CATPoint::GetCoord()`/`GetX()`/`GetY()`/`GetZ()` 取坐标 |
| `cell->IsAType(CATFace::ClassName())` | 方法名错。真实方法是 **`IsATypeOf(CATFaceType)`**（参数是类型常量如 `CATFaceType`/`CATEdgeType`，不是 `ClassName()` 字符串） |
| `edge->GetVertices(startV, endV)` 用 `CATVertex_var&` | 真实签名参数是双重指针 **`GetVertices(CATVertex**, CATVertex**)`** |
| Framework `CATMecModUseItf`/`AdvancedTopologicalOpe` | `CATBody`/`CATFace`/`CATEdge`/`CATVertex`/`CATCell`/`CATShell` 实际属于 **`GMModelInterfaces`**；`CATGeoFactory` 属于 **`GeometricObjects`**；`GetBody()`（通过 `CATIMfBRep`）属于 **`MecModInterfaces`** |

## 1. Summary

Geometry query is the capability to access the CGM (CATIA Geometric Modeler) topology objects attached to features, enabling face/edge/vertex iteration, geometric property measurement (area, length, curvature), and spatial queries for downstream analysis or rule checking.

## 2. Core Concepts

- **Topology hierarchy**: `CATBody` → `CATShell` → `CATFace` → `CATLoop` → `CATEdge` → `CATVertex`
- **Body access**: A feature (`CATISpecObject`) that produces BRep geometry can be queried through the `CATIMfBRep` interface, whose `GetBody()` returns the resulting `CATBody`
- **Cell iteration**: `GetAllCells(list, dimension)` (inherited from `CATTopology`) returns all topological cells of a given dimension from a body
- **Geometric properties**: Cells provide type-specific measurement methods (`CATFace::CalcArea()`, `CATEdge::CalcLength()`), not a generic `GetArea()`/`GetLength()` on `CATCell`
- **Type discrimination**: Use `CATBaseUnknown::IsATypeOf(CATClassId)` with a type constant (`CATFaceType`, `CATEdgeType`, ...) to distinguish cell/geometry types
- **Topology vs. geometry**: Topology describes connectivity; geometry (surfaces/curves) provides the mathematical shape
- **Factory context**: `CATGeoFactory` is the geometry container/factory that creates and owns `CATBody` and other geometric objects in a document
- **Adjacency queries**: Navigate from face to bounding edges, or from edge to adjacent faces via `CATCell::GetNeighborCell(s)`

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATIMfBRep::GetBody()` | Returns the `CATBody` associated with a BRep-producing feature |
| `CATBody` (extends `CATTopology`) | Top-level geometric container; owns shells, cells, and the result of Boolean/fillet operations; provides `GetAllCells(list, dim)` |
| `CATFace::CalcArea()` | Computes the area of a topological face |
| `CATEdge::CalcLength()` | Computes the length of a topological edge; `GetVertices(CATVertex**, CATVertex**)` for bounding vertices |
| `CATVertex::GetPoint()` | Returns the `CATPoint*` geometry; use `CATPoint::GetCoord()`/`GetX()`/`GetY()`/`GetZ()` for coordinates |
| `CATCell::IsATypeOf(CATClassId)` | Type discrimination using type constants (`CATFaceType`, `CATEdgeType`, `CATVertexType`) |
| `CATShell` | A connected set of faces forming a closed or open shell |
| `CATGeoFactory` | Factory/container that creates `CATBody` and other geometric objects within a document |

## 4. Common Patterns

### 4.1 Iterate All Faces of a Feature

```cpp
CATISpecObject_var pFeature = ...;
CATIMfBRep_var pBRep = pFeature;  // Query the BRep interface
if (NULL_var == pBRep) return;

CATBody_var pBody = pBRep->GetBody();

CATListOfCATCells cells;
pBody->GetAllCells(cells, 2);  // dimension 2 = faces

for (int i = 1; i <= cells.Size(); i++) {
    CATCell* cell = cells[i];
    if (cell->IsATypeOf(CATFaceType)) {
        CATFace* face = (CATFace*)cell;
        double area = face->CalcArea();
        // Analyze face...
    }
}
```

### 4.2 Iterate Edges with Vertex Access

```cpp
CATBody_var pBody = ...;
CATListOfCATCells edges;
pBody->GetAllCells(edges, 1);  // dimension 1 = edges

for (int i = 1; i <= edges.Size(); i++) {
    CATCell* cell = edges[i];
    if (!cell || !cell->IsATypeOf(CATEdgeType)) continue;
    CATEdge* edge = (CATEdge*)cell;

    double length = edge->CalcLength();

    CATVertex *pStartV = NULL, *pEndV = NULL;
    edge->GetVertices(&pStartV, &pEndV);

    double x, y, z;
    if (pStartV) pStartV->GetPoint()->GetCoord(x, y, z);
}
```

### 4.3 Body Validation (Check for Empty/Null)

```cpp
CATISpecObject_var pFeature = ...;
CATIMfBRep_var pBRep = pFeature;
CATBody_var pBody = (NULL_var != pBRep) ? pBRep->GetBody() : NULL_var;

if (NULL_var == pBody) {
    // Feature does not produce geometry (e.g., suppressed, empty sketch)
    return;
}

CATListOfCATCells faces;
pBody->GetAllCells(faces, 2);
int faceCount = faces.Size();
if (faceCount == 0) {
    // Body has no faces — likely an error state
}
```

## 5. Related Capabilities

- **[cap.feature_recognition](feature-recognition.md)** — Identify which feature types produce which geometry
- **[cap.assembly_tree](assembly-tree.md)** — Navigate from assembly down to part-level geometry
- **[cap.visualization](visualization.md)** — Color faces or edges based on analysis results
- **[cap.parameter_system](parameter-system.md)** — Drive geometric queries from parameter values
