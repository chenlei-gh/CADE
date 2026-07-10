---
id: cap.parameter_system
title: Parameter System
category: capability
domain: infrastructure
keywords: [parameter, formula, relation, Knowledgeware, CATICkeParm, value, expression, unit, publish, check]
apis: [CATICkeParm, CATIParmFactory, CATIParmPublisher, CATICkeRelation, CATICkeEquation, CATICheck]
frameworks: [KnowledgeInterfaces, KnowledgeItf]
playbooks: [analyzer.rule, workflow.batch]
requires: [mecmod.feature]
release: [R19, R28]
tags: [capability]
---

# Parameter System (参数系统)

Reading, writing, and publishing CATIA Knowledgeware parameters — including formulas, relations, design tables, and engineering checks — within the feature-parameter graph.

## 1. Summary

The parameter system capability covers programmatic access to CATIA's Knowledgeware layer: creating/reading/writing feature parameters, driving geometry with formulas, publishing parameters for external consumption, and validating design intent via checks and relations.

## 2. Core Concepts

- **Parameter types**: `CATLength`, `CATAngle`, `CATBoolean`, `CATString`, `CATInteger`, `CATReal` — each with unit-aware value handling
- **Feature-parameter binding**: Parameters are children of features in the spec tree; each feature's StartUp defines its parameter set
- **Formula evaluation**: `CATICkeEquation` links a parameter value to an expression referencing other parameters
- **Relations**: `CATICkeRelation` encompasses formulas, design tables, law curves, and checks
- **Publishing**: `CATIParmPublisher` exposes a parameter to external consumers (assembly context, DMU, PLM)
- **Unit system**: All dimensional parameters carry a unit (mm, deg, etc.); `CATICkeUnit` provides conversion
- **Design tables**: External CSV/Excel files that drive parameter configurations across multiple features
- **Checks (CATICheck)**: Knowledgeware rules that validate design intent and can report violations
- **Parameter sets**: Container nodes (`CATIParmSet`) that organize parameters in logical groups
- **Relation evaluation order**: Knowledgeware engine resolves the dependency DAG to determine evaluation sequence

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATICkeParm` | Base parameter interface; read/write value, get unit, get type |
| `CATICkeParm::Valuate()` | Evaluate the parameter value through its formula chain |
| `CATICkeParm::SetValue()` | Set a raw numeric value with automatic unit handling |
| `CATIParmFactory` | Create new parameters (length, angle, integer, string, boolean) |
| `CATIParmPublisher` | Publish a parameter for external visibility outside its owning document |
| `CATICkeRelation` | Base interface for formulas, checks, and design tables |
| `CATICkeEquation` | Formula interface; set expression string, drive target parameter |
| `CATICheck` | Knowledgeware check — a rule that reports pass/fail/information |
| `CATICkeUnit` | Unit descriptor for dimensional parameters (mm, deg, m, inch) |

## 4. Common Patterns

### 4.1 Read a Feature Parameter by Name

```cpp
CATISpecObject_var pFeature = ...;
CATICkeParm_var pParam = pFeature->GetParameter("Length");

if (!NULL_var(pParam)) {
    double value = pParam->Value();
    // value is in SI (meters for length, radians for angle)
}
```

### 4.2 Iterate All Parameters of a Feature

```cpp
CATISpecObject_var pFeature = ...;
CATListValCATISpecObject_var paramList;
pFeature->GetParameters(paramList);

for (int i = 1; i <= paramList.Size(); i++) {
    CATICkeParm_var pParam = paramList[i];
    CATUnicodeString name = pParam->GetName();
    CATUnicodeString unit = pParam->GetUnit();
    double value = pParam->Value();
}
```

### 4.3 Create a Formula (Parameter Driven by Expression)

```cpp
CATIParmFactory_var pFactory = ...;
CATICkeEquation_var pEquation = pFactory->CreateEquation();

// Drive parameter "Height" from expression
pEquation->SetExpression("Length * 0.5");
pEquation->SetTargetParameter(pHeightParam);

// Evaluate immediately
pEquation->Valuate();
```

### 4.4 Publish a Parameter for External Use

```cpp
CATICkeParm_var pParam = ...;
CATIParmPublisher_var pPublisher = pParam;

CATUnicodeString publishName = "ExternalHeight";
pPublisher->Publish(publishName);
// Now accessible from assembly context via published parameter name
```

## 5. Related Capabilities

- **[cap.feature_recognition](feature-recognition.md)** — Identify features before reading their parameters
- **[cap.assembly_tree](assembly-tree.md)** — Access parameters across assembly-level product instances
- **[cap.geometry_query](geometry-query.md)** — Validate geometry against parameter-driven tolerances
- **[cap.visualization](visualization.md)** — Color-code features based on parameter check results
