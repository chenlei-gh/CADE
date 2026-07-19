---
id: cap.parameter_system
title: Parameter System
category: capability
domain: infrastructure
keywords: [parameter, formula, relation, Knowledgeware, CATICkeParm, value, expression, unit, publish, check]
apis: [CATICkeParm, CATICkeInst, CATICkeParmFactory, CATIParmPublisher, CATICkeRelation, CATICheck]
frameworks: [KnowledgeInterfaces, KnowHow]
playbooks: [analyzer.rule, workflow.batch]
requires: [mecmod.feature]
release: [R19, R28]
tags: [capability]
---

# Parameter System (参数系统)

Reading, writing, and publishing CATIA Knowledgeware parameters — including formulas, relations, design tables, and engineering checks — within the feature-parameter graph.

## ⚠️ 重要修正

本文档早期版本存在多处虚构或错误的 API，已按官方本地 CAADoc 核实并修正：

| 错误写法 | 问题 | 正确写法 |
|------|------|------|
| `frameworks: [KnowledgeInterfaces, KnowledgeItf]` | `KnowledgeItf` 框架不存在 | 仅 `KnowledgeInterfaces`；Check 相关接口在 `KnowHow` 框架 |
| `CATICkeParm::Value()` 返回 `double` | 签名错误 | `Value()` 返回 `CATICkeInst_var`（一个值容器），需再调用 `AsReal()`/`AsInteger()`/`AsString()`/`AsBoolean()` 才能取出基础类型 |
| `CATICkeParm::SetValue()` | 方法名虚构 | 是 `Valuate()` 的多个重载（`int`/`double`/`CATCke::Boolean`/`CATICkeInst_var&`/`CATUnicodeString&`） |
| `CATICkeParm::GetName()` / `GetUnit()` | 方法名虚构 | 名称是 `Name()`（无 Get 前缀，直接返回）；`CATICkeParm` 本身没有 `GetUnit()`，取带单位字符串用 `Show()`/`ShowReal(unit)` |
| `CATISpecObject::GetParameter(name)` / `GetParameters(list)` | 在 `CATISpecObject`、`MecModInterfaces`、`PartInterfaces` 中均无匹配，虚构 | 未找到公开的通用「按名称取 Feature 参数」方法；实际做法通常是通过具体 Feature 接口（如 `CATINewHole`,不同 Feature 类型各异）或 `CATIParmPublisher::GetAllChildren()`/`GetDirectChildren()` 遍历已发布的参数树 |
| `CATIParmFactory` | 类名错误 | 真实类名是 `CATICkeParmFactory` |
| `CATIParmFactory::CreateEquation()` + `SetExpression()` + `SetTargetParameter()` + `Valuate()` | 整套方法均虚构；公式不是通过分步 setter 构建的 | `CATICkeParmFactory::CreateFormula(iRelationName, iComment, iFamily, iOutputParameter, iListOfParameters, iBody, iRoot=NULL_var, iRealnames=1)` 一次性创建并求值，直接返回 `CATICkeRelation_var`（公式体 `iBody` 是字符串，例如 `"Length * 0.5"`） |
| `CATICkeEquation` 接口 | 不存在；公式对象本身就是 `CATICkeRelation` | 使用 `CATICkeRelation_var`，通过 `CreateFormula`/`CreateCheck` 创建 |
| `CATIParmPublisher::Publish(name)` | `CATIParmPublisher` 真实方法是 `Append`/`RemoveChild`/`GetContainer`/`GetDirectChildren`/`GetAllChildren`/`VisitChildren`/`AllowUserAppend`，没有 `Publish()` | 简单字符串发布（`Publish(name, object)`/`Unpublish`/`IsPublished`/`ListPublications`）属于**另一个不同的接口** `CATIPrdObjectPublisher`（`ProductStructure` 框架，用于 Product 级发布），不要与 `CATIParmPublisher` 混淆 |

## 1. Summary

The parameter system capability covers programmatic access to CATIA's Knowledgeware layer: creating/reading/writing feature parameters, driving geometry with formulas, publishing parameters for external consumption, and validating design intent via checks and relations.

## 2. Core Concepts

- **Parameter values are boxed**: `CATICkeParm::Value()` returns a `CATICkeInst_var` — a value-holder that must be unboxed via `AsReal()`, `AsInteger()`, `AsBoolean()`, or `AsString()`
- **Feature-parameter binding**: Parameters are children of features in the spec tree; there is no single generic `GetParameter(name)` — access is feature-type-specific or via published-parameter traversal
- **Formula/Check creation is atomic**: `CATICkeParmFactory::CreateFormula()` / `CreateCheck()` build and valuate the relation in a single call from a body string — there is no separate "set expression then valuate" step
- **Relations**: `CATICkeRelation` is the base for formulas and checks; it exposes `Evaluate()`, `IsBroken()`, `IsUpdated()`, `Parameters()`/`InParameters()`/`OutParameters()`
- **Two distinct publishing interfaces**: `CATIParmPublisher` (Knowledgeware parameter tree, `Append`/`GetAllChildren`) vs. `CATIPrdObjectPublisher` (Product-level named publications, `Publish`/`Unpublish`/`IsPublished`) — do not conflate them
- **Unit system**: `Show()`/`ShowReal(CATICkeUnit_var&)` render a parameter's value as a unit-aware string (e.g. `"3mm"`); `CATICkeUnit`/`CATICkeMKSUnit` describe units
- **Design tables**: `CATIDesignTable` — external CSV/Excel files that drive parameter configurations across multiple features
- **Checks**: Created via `CATICkeParmFactory::CreateCheck()`, returned as a `CATICkeRelation_var`; the `CATICheck` interface (in framework `KnowHow`) is the run/report-oriented view

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATICkeParm` | Base parameter interface; `Value()` (boxed), `Valuate(...)` overloads, `Name()`, `Rename()`, `Show()`/`ShowReal()`, `Type()` |
| `CATICkeInst` | Boxed value container returned by `CATICkeParm::Value()`; unboxed via `AsReal()`/`AsInteger()`/`AsBoolean()`/`AsString()`/`AsObject()` |
| `CATICkeParmFactory` | Create parameters and relations: `CreateLength`, `CreateAngle`, `CreateInteger`, `CreateBoolean`, `CreateString`, `CreateFormula`, `CreateCheck`, `CreateDesignTable`, `CreateLaw` |
| `CATICkeRelation` | Base interface for formulas and checks; `Evaluate()`, `IsBroken()`, `IsUpdated()`, `Parameters()` |
| `CATIParmPublisher` | Knowledgeware parameter-tree container; `Append`/`RemoveChild`/`GetDirectChildren`/`GetAllChildren` |
| `CATIPrdObjectPublisher` | Product-level named publications (different interface/framework); `Publish`/`Unpublish`/`IsPublished`/`ListPublications` |
| `CATICheck` (`KnowHow`) | Knowledgeware check — reports pass/fail/information |
| `CATICkeUnit` / `CATICkeMKSUnit` | Unit descriptor for dimensional parameters |

## 4. Common Patterns

### 4.1 Read a Parameter's Value

```cpp
CATICkeParm_var pParam = ...;   // obtained from a feature-specific accessor

CATICkeInst_var pValue = pParam->Value();   // boxed value, NOT a double
double realValue = pValue->AsReal();         // unbox to double (SI units)
CATUnicodeString display = pParam->Show();   // e.g. "12.5mm", unit-aware string
```

### 4.2 Write a Parameter's Value

```cpp
CATICkeParm_var pParam = ...;
pParam->Valuate(12.5);                    // double overload, value in MKS (meters for length)
// or
pParam->Valuate(CATUnicodeString("12.5mm"));  // string overload, unit-aware
```

### 4.3 Create a Formula (Parameter Driven by Expression)

```cpp
CATICkeParmFactory_var pFactory = ...;
CATICkeParm_var pHeightParam = ...;       // output parameter to be driven
CATCkeListOfParm inputParams;             // list of parameters referenced by the body

// CreateFormula builds AND valuates the relation in one call
CATICkeRelation_var pFormula = pFactory->CreateFormula(
    "MyFormula",          // relation name
    "",                   // comment
    "",                   // family
    pHeightParam,          // output parameter
    inputParams,           // input parameters referenced in the body
    "Length * 0.5",        // body expression string
    NULL_var,               // root publisher (optional)
    1);                     // use real names in body

if (NULL_var == pFormula) {
    // syntax error occurred; a CATCkeParseException was raised
}
```

### 4.4 Create a Check

```cpp
CATICkeParmFactory_var pFactory = ...;
CATCkeListOfParm checkedParams;

CATICkeRelation_var pCheck = pFactory->CreateCheck(
    "MyCheck", "", "", checkedParams,
    "Length > 0mm",   // body expression (boolean)
    NULL_var, 1);
```

### 4.5 Traverse Published Parameters (Knowledgeware Tree)

```cpp
CATIParmPublisher_var pRoot = ...;   // e.g. the part's root publisher
CATListValCATBaseUnknown_var* pChildren = pRoot->GetAllChildren();
if (pChildren != NULL) {
    for (int i = 1; i <= pChildren->Size(); i++) {
        CATICkeParm_var pParam = (*pChildren)[i];
        if (pParam != NULL_var) {
            CATUnicodeString name = pParam->Name();
        }
    }
    delete pChildren;
}
```

### 4.6 Publish a Product-Level Object (CATIPrdObjectPublisher — distinct interface)

```cpp
CATIPrdObjectPublisher_var pPublisher = pProduct;   // Product-level, NOT CATIParmPublisher
int rc = pPublisher->Publish("ExternalHeight", pObjectToPublish);
// rc == 1: publication created; rc == 0: name already exists
```

## 5. Related Capabilities

- **[cap.feature_recognition](feature-recognition.md)** — Identify features before reading their parameters
- **[cap.assembly_tree](assembly-tree.md)** — Access parameters across assembly-level product instances
- **[cap.geometry_query](geometry-query.md)** — Validate geometry against parameter-driven tolerances
- **[cap.visualization](visualization.md)** — Color-code features based on parameter check results
