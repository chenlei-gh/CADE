---
id: cap.surface_operations
title: Surface Operations (GSD)
category: capability
domain: infrastructure
keywords: [surface, GSD, extrude, sweep, offset, join, split, flatten, develop, CATGSM, generative shape design]
apis: [CATIGSMFactory, CATIGSMSweep, CATIGSMOffset, CATIGSMJoin, CATIGSMSplit, CATIGSMExtrude, CATIGSMDevelop]
frameworks: [CATGSMUseItf, CATGSOUseItf]
playbooks: [analyzer.geometry, block.visitor, workflow.batch]
requires: [mecmod.feature, mecmod.topology]
release: [R19, R28]
tags: [capability]
---

# Surface Operations / GSD (曲面操作)

Creating and manipulating GSD (Generative Shape Design) surfaces — extrude, revolve, sweep, offset, join, split, trim, flatten, and develop — for complex surface modeling and analysis workflows.

## 1. Summary

The surface operations capability provides programmatic control over the CATIA GSD workbench: creating surface features (extrude, revolve, sweep, loft), modifying existing surfaces (offset, join, split, trim, boundary), and applying advanced operations (flatten, develop, unfold) for sheet metal, composite, and Class-A surface workflows.

## 2. Core Concepts

- **GSD feature model**: Surface features are spec objects (`CATISpecObject`) created by `CATIGSMFactory` and inserted into a `GeometricalSet` or `OrderedGeometricalSet`
- **Wireframe prerequisites**: Most surface operations require wireframe inputs — sketches, curves, lines, points — created via `CATIGSMFactory` wireframe methods
- **Input/output propagation**: Surface features maintain references to their input geometry; modifying an input curve automatically updates the dependent surface
- **Join and heal**: `CATIGSMJoin` merges adjacent surfaces into a single topology; `CATIGSMHeal` fills gaps within a tolerance
- **Split and trim**: `CATIGSMSplit` cuts a surface with a curve or another surface; trim operations involve mutual splitting of two surfaces
- **Offset and thickness**: `CATIGSMOffset` creates a parallel surface at a given distance; useful for tool offset paths and clearance analysis
- **Sweep family**: Explicit sweep (profile + guide), line sweep (two guides), circle sweep, and conical sweep — each with subtype-specific parameters
- **Flatten / Develop**: `CATIGSMDevelop` maps a 3D surface onto a 2D plane for pattern making; critical for composites and sheet metal blank development
- **Multi-output features**: Some operations (split, trim) produce two result bodies — the kept side and the discarded side
- **Hybrid design**: In hybrid mode, surface and solid features coexist in the same body; surface features can be used to split or thicken solids

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATIGSMFactory` | Central factory for creating all GSD surface and wireframe features |
| `CATIGSMExtrude` | Extrude a profile curve along a direction to create a ruled surface |
| `CATIGSMRevolute` | Revolve a profile curve around an axis to create a surface of revolution |
| `CATIGSMSweep` | Sweep a profile along one or two guide curves with optional spine |
| `CATIGSMLoft` | Loft a surface through multiple section curves with optional guide curves |
| `CATIGSMOffset` | Create a parallel surface at a constant or variable distance from a reference surface |
| `CATIGSMJoin` | Merge two or more contiguous surfaces into a single topological surface |
| `CATIGSMSplit` | Cut a surface with a cutting element (curve or surface) and keep one side |
| `CATIGSMTrim` | Mutually trim two surfaces or two curves at their intersection |
| `CATIGSMBoundary` | Extract the boundary curve(s) of a surface as wireframe geometry |
| `CATIGSMDevelop` | Flatten/develop a 3D surface into its 2D planar representation |
| `CATIGSMFill` | Fill a closed boundary with a tangent or curvature-continuous surface patch |

## 4. Common Patterns

### 4.1 Create an Extruded Surface

```cpp
CATIGSMFactory_var pGSMFactory = pGeomSet;
CATIGSMExtrude_var pExtrude = pGSMFactory->CreateExtrude();

// Set input profile (sketch or curve)
pExtrude->SetProfile(pProfileCurve);

// Set extrusion direction
CATMathDirection direction(0, 0, 1);  // Z-axis
pExtrude->SetDirection(direction);

// Set limits
pExtrude->SetLimit1(100.0);  // 100 mm extrusion
pExtrude->SetLimit2(0.0);    // no reverse extrusion

pExtrude->Update();  // Compute the result
pGeomSet->AddChild(pExtrude);  // Insert into geometrical set
```

### 4.2 Create an Offset Surface

```cpp
CATIGSMFactory_var pGSMFactory = pGeomSet;
CATIGSMOffset_var pOffset = pGSMFactory->CreateOffset();

// Reference surface to offset
pOffset->SetSurface(pBaseSurface);

// Offset distance (positive = outward normal direction)
pOffset->SetOffset(5.0);  // 5 mm offset

// Optional: both sides offset
pOffset->SetBothSidesOffset(FALSE);

pOffset->Update();
pGeomSet->AddChild(pOffset);
```

### 4.3 Join Multiple Surfaces

```cpp
CATIGSMFactory_var pGSMFactory = pGeomSet;
CATIGSMJoin_var pJoin = pGSMFactory->CreateJoin();

// Add surfaces to join
CATListValCATISpecObject_var surfaces;
surfaces.Append(pSurface1);
surfaces.Append(pSurface2);
surfaces.Append(pSurface3);

pJoin->AddElements(surfaces);

// Set merging tolerance
pJoin->SetMergingTolerance(0.001);  // 1 micron

pJoin->Update();
pGeomSet->AddChild(pJoin);
```

### 4.4 Sweep Along a Guide Curve

```cpp
CATIGSMFactory_var pGSMFactory = pGeomSet;
CATIGSMSweep_var pSweep = pGSMFactory->CreateSweep();

// Set sweep type to explicit (profile + guide)
pSweep->SetSweepType(CATIGSMSweep::ExplicitSweep);

// Set profile and guide curve
pSweep->SetProfile(pProfileCurve);
pSweep->SetGuideCurve(pGuideCurve);

// Optional spine for twist control
pSweep->SetSpine(pSpineCurve);

pSweep->Update();
pGeomSet->AddChild(pSweep);
```

### 4.5 Flatten a Surface for Development

```cpp
CATIGSMFactory_var pGSMFactory = pGeomSet;
CATIGSMDevelop_var pDevelop = pGSMFactory->CreateDevelop();

// Surface to flatten
pDevelop->SetSurface(pSurfaceToFlatten);

// Optional: reference point and direction for flatten origin
pDevelop->SetReferencePoint(pOriginPoint);
pDevelop->SetDirection(pFlattenDirection);

pDevelop->Update();
pGeomSet->AddChild(pDevelop);

// Access the flattened result as planar geometry
CATBody_var flattenedBody = pDevelop->GetResult();
```

### 4.6 Split a Surface

```cpp
CATIGSMFactory_var pGSMFactory = pGeomSet;
CATIGSMSplit_var pSplit = pGSMFactory->CreateSplit();

// Element to split
pSplit->SetElementToSplit(pSurface);

// Cutting element (curve or surface)
pSplit->AddCuttingElement(pCuttingCurve);

// Side to keep
pSplit->SetOrientation(1);  // positive side

pSplit->Update();
pGeomSet->AddChild(pSplit);
```

## 5. Related Capabilities

- **[cap.geometry_query](geometry-query.md)** — Query topology of generated surfaces for measurement and analysis
- **[cap.feature_recognition](feature-recognition.md)** — Identify existing surface feature types before modification
- **[cap.visualization](visualization.md)** — Color-code surfaces by operation type or analysis result
- **[cap.selection](selection.md)** — Select surface features and their input curves in the 3D view
