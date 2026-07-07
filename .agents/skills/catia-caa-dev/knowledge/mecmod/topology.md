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
CATBody_var pBody = pFeature->GetBody();
```

## 遍历 Face

```cpp
CATBody_var pBody = ...;
CATListOfCATCells cells;
pBody->GetAllCells(cells);

for (int i = 1; i <= cells.Size(); i++) {
    CATCell_var cell = cells[i];
    if (cell->IsAType(CATFace::ClassName())) {
        CATFace_var face = cell;
        // 处理面...
    }
}
```

## 常用操作

```cpp
// 获取面积
double area = face->GetArea();

// 获取面的法向量
CATMathVector normal;
face->GetNormal(normal);

// 获取边的长度
double length = edge->GetLength();

// 获取边的两端顶点
CATVertex_var startV, endV;
edge->GetVertices(startV, endV);

// 获取顶点坐标
CATMathPoint pt;
vertex->GetCoordinates(pt);
```

## 常用判断

| 场景 | 方式 |
|------|------|
| 判断面类型 | `face->IsAType(CATPlaneFace::ClassName())` |
| 获取 Body | `feature->GetBody()` |
| 遍历面 | `body->GetAllCells()` |
| 获取面积 | `face->GetArea()` |
| 获取边长 | `edge->GetLength()` |
