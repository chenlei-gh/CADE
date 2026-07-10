---
id: cap.geometry_query
title: Geometry Query
category: capability
domain: infrastructure
keywords: [geometry, body, face, edge, vertex, topology, traversal, CATBody, CATFace, area, length]
apis: [CATISpecObject, CATBody, CATFace, CATEdge, CATGeoFactory, CATCell, CATShell, CATVertex]
frameworks: [CATMecModUseItf, AdvancedTopologicalOpe]
playbooks: [analyzer.geometry, block.visitor]
requires: [mecmod.feature, mecmod.topology]
release: [R19, R28]
tags: [capability]
---

# Geometry Query (几何查询)

Querying geometric topology — bodies, faces, edges, and vertices — from CATIA features for measurement, analysis, and validation.

## 1. Summary

Geometry query is the capability to access the CGM (CATIA Geometric Modeler) topology objects attached to features, enabling face/edge/vertex iteration, geometric property measurement (area, length, curvature), and spatial queries for downstream analysis or rule checking.

## 2. Core Concepts

- **Topology hierarchy**: `CATBody` → `CATShell` → `CATFace` → `CATLoop` → `CATEdge` → `CATVertex`
- **Body access**: Any `CATISpecObject` (feature) that produces geometry exposes a `CATBody` via `GetBody()`
- **Cell iteration**: `GetAllCells()` returns all topological cells of a given dimension from a body
- **Geometric properties**: Each cell provides measurement methods (`GetArea()`, `GetLength()`, `GetCoordinates()`)
- **Type discrimination**: Use `IsAType()` or `ClassName()` to distinguish face types (plane, cylinder, torus, B-spline)
- **Topology vs. geometry**: Topology describes connectivity; geometry (surfaces/curves) provides the mathematical shape
- **Factory context**: `CATGeoFactory` is the container that owns all `CATBody` objects in a document
- **Adjacency queries**: Navigate from face to bounding edges, or from edge to adjacent faces

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATISpecObject` | Feature interface that provides `GetBody()` to access its geometric result |
| `CATBody` | Top-level geometric container; owns shells, cells, and the result of Boolean/fillet operations |
| `CATFace` | A topological face with area, normal, and associated geometric surface |
| `CATEdge` | A topological edge with length, curvature, and bounding vertices |
| `CATVertex` | A topological vertex with 3D coordinates |
| `CATCell` | Base class for all topological cells; provides `GetAllCells()` for iteration |
| `CATShell` | A connected set of faces forming a closed or open shell |
| `CATGeoFactory` | Factory/container for all `CATBody` instances within a document |
| `CATPlaneFace` / `CATCylinderFace` | Typed face subclasses for geometric type discrimination |

## 4. Common Patterns

### 4.1 Iterate All Faces of a Feature

```cpp
CATISpecObject_var pFeature = ...;
CATBody_var pBody = pFeature->GetBody();

CATListOfCATCells cells;
pBody->GetAllCells(cells, 2);  // dimension 2 = faces

for (int i = 1; i <= cells.Size(); i++) {
    CATCell_var cell = cells[i];
    if (cell->IsAType(CATFace::ClassName())) {
        CATFace_var face = cell;
        double area = face->GetArea();
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
    CATEdge_var edge = edges[i];
    if (!edge) continue;

    double length = edge->GetLength();

    CATVertex_var startV, endV;
    edge->GetVertices(startV, endV);

    CATMathPoint startPt, endPt;
    startV->GetCoordinates(startPt);
    endV->GetCoordinates(endPt);
}
```

### 4.3 Body Validation (Check for Empty/Null)

```cpp
CATISpecObject_var pFeature = ...;
CATBody_var pBody = pFeature->GetBody();

if (NULL_var(pBody)) {
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
