---
id: mecmod.topology
title: Topology
category: knowledge
domain: mecmod
keywords: [topology, body, face, edge, vertex, shell, cell, area, length]
apis: [CATBody, CATFace, CATEdge, CATVertex, CATCell, CATShell, CATGeoFactory]
requires: [mecmod.feature]
patterns: [analyzer.geometry]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [core, geometry, topology]
---

# Topology (拓扑)

CAA CGM 拓扑对象用于访问几何模型中的 Body、Face、Edge、Vertex 等。

## 核心对象层次

```
CATBody
  ├── CATShell (壳)
  │    └── CATFace (面)
  │         └── CATLoop (环)
  │              └── CATEdge (边)
  │                   └── CATVertex (顶点)
  └── CATCell (单元格)
```

## 从 Feature 获取 Body

```cpp
CATISpecObject_var pFeature = ...;

// 方式1: BRep 特征 (Pad/Pocket 等)
CATIMfBRep_var pBRep = pFeature;          // QueryInterface CATIMfBRep
CATBody* pBody = pBRep->GetBody();        // 返回 CATBody*

// 方式2: 几何元素 (GSM 结果)
CATIGeometricalElement_var pGeom = pFeature;
CATBody_var pBody2 = pGeom->GetBodyResult();  // 返回 CATBody_var
```

## 遍历 Face

```cpp
CATBody* pBody = ...;
CATLISTP(CATCell) cells;
CATLONG32 maxDim = 0;
CATBoolean homogeneous = FALSE;
pBody->GetCellsHighestDimension(maxDim, homogeneous, NULL, &cells);

for (int i = 1; i <= cells.Size(); i++) {
    CATCell* cell = cells[i];
    if (cell->GetDimension() == 2) {      // 2 = Face
        CATFace* face = (CATFace*)cell;
        // 处理面...
    }
}
```

## 常用操作

```cpp
// 获取面积
double area = face->CalcArea();            // CATFace::CalcArea() 返回 double

// 获取面的法向量
CATMathVector normal;
CATSurParam centerParam;
face->EstimateCenterParam(centerParam);
face->EvalNormal(centerParam, normal);     // CATFace::EvalNormal(param, normal)

// 获取边的长度
double length = edge->CalcLength();        // CATEdge::CalcLength() 返回 double

// 获取边的两端顶点
CATVertex* startV = NULL;
CATVertex* endV = NULL;
edge->GetVertices(&startV, &endV);         // 参数为 CATVertex**

// 获取顶点坐标
CATPoint* pPoint = vertex->GetPoint();     // CATVertex::GetPoint() 返回 CATPoint*
CATMathPoint pt = pPoint->GetMathPoint();  // CATPoint::GetMathPoint() 返回 CATMathPoint
```

## 常用判断

| 场景 | 方式 |
|------|------|
| 判断 Cell 维度 | `cell->GetDimension()` (0=Vertex, 1=Edge, 2=Face) |
| 获取 Body | `CATIMfBRep::GetBody()` / `CATIGeometricalElement::GetBodyResult()` |
| 遍历面 | `body->GetCellsHighestDimension()` / `CATCell::CreateBoundaryIterator()` |
| 获取面积 | `face->CalcArea()` 或 `CATIMeasurableSurface::GetArea(double&)` |
| 获取边长 | `edge->CalcLength()` 或 `CATIMeasurableCurve::GetLength(double&)` |
