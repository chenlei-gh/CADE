---
id: cap.powercopy
title: PowerCopy & UDF
category: capability
domain: infrastructure
keywords: [PowerCopy, UDF, instantiate, template, publish, parameter, mapping, catalog, reuse, user defined feature]
apis: [CATIPowerCopy, CATIUDFInstantiate, CATIGSMFactory, CATIParmPublisher, CATIUDFFeature, CATISpecObject]
frameworks: [ObjectModelerBase, CATMecModUseItf]
playbooks: [block.visitor, workflow.batch, analyzer.rule]
requires: [mecmod.feature, cap.parameter_system]
release: [R19, R28]
tags: [capability]
---

# PowerCopy & UDF (超级副本与用户定义特征)

Creating, publishing, and instantiating PowerCopies and User-Defined Features (UDFs) — template-based reuse of feature groups with parameter mapping and catalog integration.

## 1. Summary

The PowerCopy and UDF capability covers the programmatic lifecycle of reusable feature templates: defining a PowerCopy from a set of features, publishing input parameters and reference geometry, instantiating UDFs into target documents, mapping external references, and storing templates in catalogs for enterprise reuse.

## 2. Core Concepts

- **PowerCopy vs. UDF**: A PowerCopy is a group of features saved as a template that can be instantiated within the same part; a UDF (User-Defined Feature) is a PowerCopy embedded in a catalog document for cross-document reuse
- **Template definition**: A PowerCopy is defined by selecting a set of features (the "definition") and publishing their inputs (parameters, sketches, reference planes)
- **Input publication**: `CATIParmPublisher::Publish()` exposes a parameter as an input that the user must supply at instantiation time
- **Reference resolution**: When instantiating, each published input must be mapped to a concrete object (parameter, curve, surface, plane) in the target document
- **Instantiation scope**: UDFs can be instantiated into a Part body, a Geometrical Set, or an Ordered Geometrical Set depending on the feature types inside the template
- **Parameter remapping**: Published parameters can be re-mapped to formulas or driven by target document parameters during instantiation
- **Catalog storage**: `CATICatalog` stores UDF definitions for browsing and retrieval across the enterprise; UDFs are stored as StartUps in the catalog
- **Multi-level templates**: A PowerCopy may contain nested PowerCopies; resolution proceeds recursively during instantiation
- **Update behavior**: Instantiated UDF features maintain a link to their definition; updating the UDF definition propagates changes to all instances
- **Explode/Unexplode**: An instantiated UDF can be "exploded" into its constituent features, breaking the link to the definition template

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATIPowerCopy` | Interface for creating and managing PowerCopy definitions within a part |
| `CATIPowerCopy::Create()` | Create a new PowerCopy from a list of seed features |
| `CATIPowerCopy::AddFeature()` | Add a feature to the PowerCopy definition set |
| `CATIUDFInstantiate` | Interface for instantiating a UDF from a catalog into a target document |
| `CATIUDFInstantiate::Instantiate()` | Perform the UDF instantiation with parameter and reference mapping |
| `CATIUDFFeature` | Interface on the instantiated UDF result; provides access to mapped children |
| `CATIParmPublisher` | Publish specific parameters of a feature as UDF inputs |
| `CATIGetUDFActivity` | Query the active UDF instantiation context for UI-driven interactive placement |
| `CATICatalog` | Store and retrieve UDF/PowerCopy definitions in a catalog document |
| `CATIGSMFactory` | Factory used to create the target container (GeomSet, Body) for UDF placement |

## 4. Common Patterns

### 4.1 Create a PowerCopy from Selected Features

```cpp
// Select features to include in the PowerCopy
CATListValCATISpecObject_var seedFeatures;
seedFeatures.Append(pPadFeature);
seedFeatures.Append(pFilletFeature);
seedFeatures.Append(pHoleFeature);

// Create the PowerCopy
CATIPowerCopy_var pPowerCopy = pPartContainer;
pPowerCopy->Create(seedFeatures);

// Name the PowerCopy for identification
CATUnicodeString pcName = "MountingBoss";
pPowerCopy->SetName(pcName);
```

### 4.2 Publish Input Parameters for a PowerCopy

```cpp
CATIPowerCopy_var pPowerCopy = ...;

// Publish key parameters as inputs
CATICkeParm_var pHoleDiameter = pHoleFeature->GetParameter("Diameter");
CATIParmPublisher_var pPublisher = pHoleDiameter;
pPublisher->Publish("HoleDiameter");  // Exposed as "HoleDiameter" input

CATICkeParm_var pPadHeight = pPadFeature->GetParameter("Height");
pPublisher = pPadHeight;
pPublisher->Publish("PadHeight");

// Also publish reference geometry (sketch plane, direction)
// Reference inputs define the placement context
pPowerCopy->PublishReference(pSketchPlane, "ReferencePlane");
```

### 4.3 Instantiate a UDF from a Catalog

```cpp
// Open the catalog containing the UDF
CATICatalog_var pCatalog = OpenCatalog("E:\\Templates\\UDFCatalog.catalog");

// Locate the UDF definition by name
CATIUDFInstantiate_var pUDFInst = pCatalog->GetUDF("MountingBoss");

// Prepare input mapping
CATListValCATUnicodeString paramNames;
CATListValCATUnicodeString paramValues;
paramNames.Append("HoleDiameter");
paramValues.Append("10.0");  // 10 mm hole

paramNames.Append("PadHeight");
paramValues.Append("25.0");  // 25 mm pad height

// Reference mapping: which plane in target to use
CATISpecObject_var pTargetPlane = ...;  // XY plane in target part
pUDFInst->SetReferenceInput("ReferencePlane", pTargetPlane);

// Set parameter overrides
pUDFInst->SetParameterInputs(paramNames, paramValues);

// Perform instantiation into target container
CATISpecObject_var pResult = pUDFInst->Instantiate(pTargetContainer);
```

### 4.4 Instantiate a PowerCopy in the Same Part

```cpp
CATIPowerCopy_var pPowerCopy = ...;

// Prepare input overrides
CATListValCATUnicodeString inputs;
CATListValCATUnicodeString values;
inputs.Append("HoleDiameter");
values.Append("8.5");  // 8.5 mm

inputs.Append("PadHeight");
values.Append("20.0");  // 20 mm

// Reference inputs: anchor point and plane
CATMathPoint anchorPoint(50, 30, 0);
CATISpecObject_var pRefPlane = ...;

pPowerCopy->SetReferenceInput("ReferencePlane", pRefPlane);
pPowerCopy->SetParameterInputs(inputs, values);

// Instantiate in a Geometrical Set or Body
CATISpecObject_var pInstance = pPowerCopy->Instantiate(pTargetGeomSet);
```

### 4.5 Explode a UDF Instance (Break Link to Definition)

```cpp
CATISpecObject_var pUDFInstance = ...;  // Previously instantiated UDF

// Check if it's a UDF instance
CATIUDFFeature_var pUDFFeature = pUDFInstance;
if (!NULL_var(pUDFFeature)) {
    // Explode breaks the link and makes features standalone
    pUDFFeature->Explode();

    // After explosion, individual features can be modified independently
    // without affecting the UDF definition or other instances
}
```

### 4.6 Iterate Mapped Children of a UDF Instance

```cpp
CATISpecObject_var pUDFInstance = ...;
CATIUDFFeature_var pUDFFeature = pUDFInstance;

// Retrieve individual features created by the UDF
CATListValCATISpecObject_var children;
pUDFFeature->GetChildren(children);

for (int i = 1; i <= children.Size(); i++) {
    CATISpecObject_var child = children[i];
    CATUnicodeString name = child->GetName();
    CATUnicodeString type = child->GetType();

    // Each child corresponds to a feature in the original template
    // e.g., "Pad.1", "EdgeFillet.1", "Hole.1"
}
```

## 5. Related Capabilities

- **[cap.feature_recognition](feature-recognition.md)** — Identify features to include in PowerCopy definitions
- **[cap.parameter_system](parameter-system.md)** — Publish and remap parameters between template and instance
- **[cap.surface_operations](surface-operations.md)** — Include GSD surface features in PowerCopy/UDF templates
- **[cap.document_export](document-export.md)** — Save UDF definitions to catalog files and export instantiation reports
