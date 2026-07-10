---
id: cap.annotation
title: 3D Annotation (FTA / PMI)
category: capability
domain: infrastructure
keywords: [annotation, PMI, FTA, dimension, tolerance, datum, capture, 3D view, TPS, GD&T, semantic]
apis: [CATITPSView, CATITPSAnnotation, CATITPSDimension, CATITPSTolerance, CATITPSDatum, CATITPSCapture, CATITPSFactory]
frameworks: [CATAnalysisGPSInterfaces]
playbooks: [analyzer.rule, analyzer.geometry, ui.result_dialog]
requires: [mecmod.feature, mecmod.topology]
release: [R19, R28]
tags: [capability]
---

# 3D Annotation / FTA (三维标注)

Creating and managing 3D PMI (Product Manufacturing Information) annotations — dimensions, tolerances, datums, GD&T frames, and capture views — within the FTA (Functional Tolerancing & Annotation) workbench.

## 1. Summary

The annotation capability enables programmatic creation and query of 3D annotations (FTA/PMI): linear and angular dimensions, geometric tolerances, datum features and targets, surface texture symbols, flag notes, and capture views that organize annotations into viewable sets for downstream manufacturing and inspection.

## 2. Core Concepts

- **TPS (Technological Product Specification)**: The semantic framework for 3D annotations — every annotation carries semantic meaning, not just graphical representation
- **Capture views**: `CATITPSCapture` groups annotations into named views (e.g., "Front View", "Section A-A") that can be individually displayed and exported
- **Annotation-View relationship**: Every annotation belongs to a capture view; annotations without a view cannot be displayed
- **Dimension types**: Linear, angular, radial, diameter, chamfer, coordinate — each with specific reference geometry requirements
- **Tolerance frames**: GD&T (Geometric Dimensioning & Tolerancing) frames include feature control frames with symbol, tolerance value, and datum references
- **Datum features**: `CATITPSDatum` identifies a reference feature (plane, cylinder, etc.) used as a datum for tolerance frames
- **Semantic references**: Annotations maintain semantic links to the geometry they describe; if geometry changes, annotations may become invalid
- **Annotation sets**: Collections of related annotations grouped under a common parent; useful for organizing by manufacturing stage
- **Standards compliance**: Annotations follow ASME Y14.5 or ISO 1101 standards; the standard determines symbol appearance and interpretation
- **View orientation**: Each capture view has an associated 3D camera position; activating a view reframes the viewer accordingly

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATITPSView` | Base interface for all annotation views and annotation sets |
| `CATITPSCapture` | A named 3D capture view that groups annotations and stores camera orientation |
| `CATITPSAnnotation` | Base interface for all annotation objects; provides semantic reference access |
| `CATITPSDimension` | Linear, angular, radial, and diameter dimension annotations |
| `CATITPSTolerance` | GD&T feature control frame with symbol, tolerance, modifiers, and datum references |
| `CATITPSDatum` | Datum feature and datum target annotations |
| `CATITPSFactory` | Factory for creating all annotation types within a capture view context |
| `CATITPSComponent` | Component-level annotation access; iterate annotations, resolve semantic targets |
| `CATITPSSet` | Annotation set container; hierarchy of related annotations |
| `CATITPSRoughness` | Surface texture / roughness symbol annotation |

## 4. Common Patterns

### 4.1 Create a Capture View

```cpp
CATITPSFactory_var pTPSFactory = pTPSContainer;
CATITPSCapture_var pCapture = pTPSFactory->CreateCaptureView();

// Name the view
pCapture->SetName("Front View - Machining Dimensions");

// Set camera orientation (optional)
CATMathDirection viewDirection(0, 1, 0);  // Looking along Y-axis
pCapture->SetViewDirection(viewDirection);

// Activate the view for annotation creation
pCapture->Activate();
```

### 4.2 Create a Linear Dimension

```cpp
CATITPSFactory_var pTPSFactory = pTPSContainer;

// Reference geometry for dimension
CATISpecObject_var pFace1 = ...;  // First reference face
CATISpecObject_var pFace2 = ...;  // Second reference face

CATITPSDimension_var pDimension =
    pTPSFactory->CreateLinearDimension(pFace1, pFace2);

// Set dimension parameters
pDimension->SetNominalValue(25.0);       // 25 mm
pDimension->SetUpperTolerance(0.1);      // +0.1
pDimension->SetLowerTolerance(-0.05);    // -0.05

// Add to active capture view
pActiveCapture->AddAnnotation(pDimension);
```

### 4.3 Create a GD&T Tolerance Frame

```cpp
CATITPSFactory_var pTPSFactory = pTPSContainer;

// Create tolerance frame on a feature
CATISpecObject_var pTargetFace = ...;
CATITPSTolerance_var pTolerance =
    pTPSFactory->CreateGeometricTolerance(pTargetFace);

// Set GD&T characteristics
pTolerance->SetSymbol(CATITPSTolerance::Flatness);  // Flatness symbol
pTolerance->SetToleranceValue(0.05);                 // 0.05 mm tolerance zone

// Add datum references
CATITPSDatum_var pDatumA = ...;  // Previously created datum
pTolerance->AddDatumReference(pDatumA);

// Set material condition modifier
pTolerance->SetModifier(CATITPSTolerance::MMC);  // Maximum Material Condition

pActiveCapture->AddAnnotation(pTolerance);
```

### 4.4 Create a Datum Feature

```cpp
CATITPSFactory_var pTPSFactory = pTPSContainer;

// Create datum on a planar face
CATISpecObject_var pDatumPlane = ...;
CATITPSDatum_var pDatum = pTPSFactory->CreateDatum(pDatumPlane);

// Set datum label
pDatum->SetLabel("A");  // Datum A

// Optionally set datum target type
// pDatum->SetAsDatumTarget(TRUE);

pActiveCapture->AddAnnotation(pDatum);
```

### 4.5 Iterate All Annotations in a Capture View

```cpp
CATITPSCapture_var pCapture = ...;

CATListValCATITPSAnnotation_var annotations;
pCapture->GetAllAnnotations(annotations);

for (int i = 1; i <= annotations.Size(); i++) {
    CATITPSAnnotation_var pAnnot = annotations[i];
    CATUnicodeString name = pAnnot->GetName();
    CATUnicodeString type = pAnnot->GetType();

    if (pAnnot->IsATypeOf(CATITPSDimension::ClassName())) {
        CATITPSDimension_var pDim = pAnnot;
        double nominal = pDim->GetNominalValue();
        // Process dimension...
    }
}
```

### 4.6 Delete and Clean Up Annotations

```cpp
CATITPSCapture_var pCapture = ...;
CATITPSAnnotation_var pAnnotation = ...;

// Remove from capture view
pCapture->RemoveAnnotation(pAnnotation);

// If annotation has no more references, it may be garbage collected
// or explicitly deleted from the TPS container
```

## 5. Related Capabilities

- **[cap.visualization](visualization.md)** — Highlight features that have associated annotations or missing PMI
- **[cap.geometry_query](geometry-query.md)** — Query geometric properties for dimension reference resolution
- **[cap.feature_recognition](feature-recognition.md)** — Identify feature types to determine recommended annotation set
- **[cap.selection](selection.md)** — Select annotation objects in the 3D view and reframe to capture views
