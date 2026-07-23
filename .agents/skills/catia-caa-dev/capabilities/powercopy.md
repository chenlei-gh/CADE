---
id: cap.powercopy
title: PowerCopy & UDF
category: capability
domain: infrastructure
keywords: [PowerCopy, UDF, UserFeature, instantiate, template, publish, parameter, mapping, reuse, user defined feature, copy paste, CATICutAndPastable, CATPathElement, cross-document]
apis: [CATIUdfFactory, CATIUdfFeature, CATIUdfInstantiate, CATIUdfFeatureInstance, CATIUdfFeatureSet, CATIUdfFeatureUser, CATISpecObject]
frameworks: [MechanicalCommands, MecModInterfaces, ObjectModelerBase]
playbooks: [block.visitor, workflow.batch, analyzer.rule]
requires: [mecmod.feature, cap.parameter_system]
release: [R19, R28]
tags: [capability]
---

# PowerCopy & UDF (超级副本与用户定义特征)

Creating, publishing, and instantiating PowerCopies and User-Defined Features (UDFs, 即 CATIA 中的 "User Feature") — template-based reuse of feature groups with input mapping and published-parameter mapping.

## ⚠️ 重要修正

旧版本文档中的接口名存在虚构和大小写错误，经 CAADoc（`MechanicalCommands` 框架）核实修正：

| 旧写法（虚构/错误） | 真实情况 |
|---------------------|---------|
| `CATIPowerCopy` | **不存在**。PowerCopy 和 User Feature 共用同一个定义接口 **`CATIUdfFeature`**；创建则通过 **`CATIUdfFactory::CreatePowerCopy()`** / **`CreateUserFeature(name)`** |
| `CATIUDFInstantiate` | 大小写错误。真实接口名是 **`CATIUdfInstantiate`**（Udf，仅U大写） |
| `CATIUDFFeature` | 大小写错误。真实接口名是 **`CATIUdfFeature`** |
| `CATIGetUDFActivity` | **不存在**，零匹配，纯属虚构 |
| `CATICatalog` | **不存在**（裸接口）。官方文档明确说明"目录与特征之间没有直接链接"（catalog 与 CAA 特征无编程接口耦合），编目集成属于交互层面，不是通过某个 `CATICatalog` API |
| `CATIParmPublisher::Publish()` | 该接口没有 `Publish()` 方法（真实方法是 `Append/RemoveChild/GetContainer/...`）。UDF/PowerCopy 场景真正"发布参数"的方法是 **`CATIUdfFeature::AddParameter()`** / **`RemoveParameter()`**（对应官方术语 Published Parameter） |
| `CATIGSMFactory`（用于"创建UDF放置目标容器"） | 与UDF放置无关，应移除。目标位置通过 `CATIUdfInstantiate::SetDestinationPath()` / `SetDestinationPathOfInsertion()` 指定一个 `CATPathElement`，不需要 GSM 工厂 |
| `pUDFFeature->Explode()` | **不存在**。PowerCopy 用 Copy/Paste 机制实例化，结果本身就是独立、可编辑的普通特征，不需要"展开"；User Feature 用 Instance/Reference 机制（黑盒），没有公开的 `Explode()` API，只能通过 `CATIUdfFeatureInstance` 编辑其输入/参数 |
| `pUDFFeature->GetChildren(children)` | **不存在**。User Feature 实例的产出通过 **`CATIUdfFeatureInstance::GetOutputsNumber()`** + **`GetOutput(pos, output)`** 逐个获取（主结果 + 外部输出），而非"children"列表 |
| Framework `CATMecModUseItf` | 真实框架是 **`MechanicalCommands`**（`CATIUdfFactory`/`CATIUdfFeature`/`CATIUdfInstantiate`/`CATIUdfFeatureInstance`/`CATIUdfFeatureSet`/`CATIUdfFeatureUser` 均属此框架） |

## 1. Summary

The PowerCopy and User Feature (UDF) capability covers the programmatic lifecycle of reusable feature templates: creating a reference via `CATIUdfFactory`, defining its content (components, inputs, published parameters) via `CATIUdfFeature`, instantiating it into a target Part via `CATIUdfInstantiate`, and — for User Features only — editing an existing instance's inputs/parameters via `CATIUdfFeatureInstance`.

## 2. Core Concepts

- **PowerCopy vs. User Feature**: Both are defined through the same `CATIUdfFeature` interface. A **PowerCopy** is instantiated with a Copy/Paste mechanism — the resulting features are independent, editable copies. A **User Feature** is instantiated with an Instance/Reference mechanism — the result is a "black box" feature that keeps a link to its reference and exposes only its published inputs/parameters/outputs
- **Component**: A feature (geometrical feature, knowledge object, constraint, another User Feature, a surfacic set, or a Body) selected to form the reference's content, set via `CATIUdfFeature::SetComponents()`
- **Input**: A feature referenced from *outside* the component set through an external link (e.g., a plane a sketch is built on); inputs must be valuated at instantiation time
- **Published Parameter**: A knowledge parameter of a component explicitly exposed via `CATIUdfFeature::AddParameter()` so its value can be changed at instantiation time
- **Role**: A human-readable NLS name given to an input or a published parameter (`SetInputRole()` / `SetParameterRole()`), shown in the instantiation/edition dialog
- **Sets**: References live in one of two non-mechanical feature sets aggregated under the MechanicalPart — the "PowerCopy" set (index `0`) or the "UserFeatures" set (index `1`), retrieved via `CATIUdfFactory::GetFeatureSet(mode)`
- **Destination**: At instantiation, the target location is a `CATPathElement`, set either on the whole MechanicalPart (`SetDestinationPath`) or on a specific destination feature with a relative position "Inside"/"After" (`SetDestinationPathOfInsertion`)
- **⚠️ Cross-document `CATPathElement` hazard**: `CATPathElement`-based targeting is only safe when source and target live in the **same document** (same `PrtContainer`). Passing a `CATPathElement` that references objects from a *different* document (e.g. cross-document Copy/Paste via `CATICutAndPastable::Paste`) crashes the CATIA process with an **uncatchable** runtime exception. For cross-document paste, pass `NULL` targets and let the container decide, or use the Automation layer (`Selection.Copy/PasteSpecial`). See [fp.paste_cross_doc_catpathelement](../knowledge/failure_patterns/fp_paste_cross_doc_catpathelement.md)
- **Instantiation transaction order**: `SetDestinationPath(...)` → valuate inputs (`SetNewInput`/`UseIdenticalName`) → optionally modify published parameters (`GetParameters`) → `Instantiate(...)` → optionally `GetInstantiated()`/`SetDisplayName()` → `EndInstantiate()` → `Reset()`
- **Editing instances**: Only User Feature instances are editable after creation, through `CATIUdfFeatureInstance` (bracketed by `Init()`/`Reset()`); PowerCopy instances are ordinary independent features with no dedicated edition interface
- **Type**: A User-Feature-only classification string (no equivalent for PowerCopy), set via `CATIUdfFeatureUser::SetType()`/`GetType()`, useful to hook a custom `CATIEdit` panel per type

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATIUdfFactory` | Implemented by the Part container (`CATIPrtContainer`); creates/lists PowerCopy and User Feature references (`CreatePowerCopy()`, `CreateUserFeature(name)`, `GetPowerCopyList()`, `GetUserFeatureList()`, `GetFeatureSet(mode)`) |
| `CATIUdfFeature` | Defines the reference's content: `SetComponents()`, `VerifyComponents()`, inputs (`GetListInputs`/`SetInputRole`), published parameters (`AddParameter`/`RemoveParameter`/`SetParameterRole`), preview image |
| `CATIUdfInstantiate` | Drives instantiation of a reference: `SetDestinationPath()`/`SetDestinationPathOfInsertion()`, `SetNewInput()`/`UseIdenticalName()`, `GetParameters()`, `Instantiate()`, `GetInstantiated()`, `EndInstantiate()`, `Reset()` |
| `CATIUdfFeatureInstance` | Edits an existing **User Feature instance**: `Init()`, `SetNewInput()`, `GetParameter()`, outputs (`GetOutputsNumber`/`GetOutput`), `Reset()` |
| `CATIUdfFeatureSet` | The PowerCopy/UserFeatures aggregation set; `AppendFeature()` registers a newly created reference so it appears in `GetPowerCopyList()`/`GetUserFeatureList()` |
| `CATIUdfFeatureUser` | Advanced edition of a User Feature reference: outputs management (`AddOutput`/`RemoveOutput`/`ReplaceOutput`) and `SetType()`/`GetType()` |

## 4. Common Patterns

### 4.1 Create a PowerCopy Reference from Selected Features

```cpp
// Retrieve CATIUdfFactory on the Part container (implemented by CATIPrtContainer)
CATIPrtContainer* pPrtContainer = ...;
CATIUdfFactory* pUdfFactory = NULL;
pPrtContainer->QueryInterface(IID_CATIUdfFactory, (void**)&pUdfFactory);

// Create the reference
CATIUdfFeature_var spUdfFeature = pUdfFactory->CreatePowerCopy();

// Name it via CATIAlias (CreatePowerCopy takes no name argument)
CATIAlias_var spAlias = spUdfFeature;
spAlias->SetAlias("MountingBoss");

// Select the components to include
CATListValCATBaseUnknown_var* pComponents = new CATLISTV(CATBaseUnknown_var);
pComponents->Append(pPadFeature);
pComponents->Append(pFilletFeature);
pComponents->Append(pHoleFeature);

// Verify, then valuate (SetComponents can only be called once)
CATUnicodeString message;
if (SUCCEEDED(spUdfFeature->VerifyComponents(pComponents, message))) {
    spUdfFeature->SetComponents(pComponents);
}

// Register the reference in the PowerCopy set (index 0) so it becomes visible
CATIUdfFeatureSet_var spFeatureSet = pUdfFactory->GetFeatureSet(0);
spFeatureSet->AppendFeature((CATISpecObject_var)spUdfFeature);

pUdfFactory->Release();
```

### 4.2 Publish Input Parameters for the Reference

```cpp
CATIUdfFeature_var spUdfFeature = ...;  // After SetComponents()

// Rename inputs so the end user understands what to select
// x ranges from 1 to the size of GetListInputs()
spUdfFeature->SetInputRole(1, "AnchorPlane");

// Publish a parameter so its value can be overridden at instantiation
CATICkeParm_var pHoleDiameter = pHoleFeature->GetParameter("Diameter");
spUdfFeature->AddParameter((CATBaseUnknown_var)pHoleDiameter);
spUdfFeature->SetParameterRole((CATBaseUnknown_var)pHoleDiameter, "HoleDiameter");

CATICkeParm_var pPadHeight = pPadFeature->GetParameter("Height");
spUdfFeature->AddParameter((CATBaseUnknown_var)pPadHeight);
spUdfFeature->SetParameterRole((CATBaseUnknown_var)pPadHeight, "PadHeight");
```

### 4.3 Instantiate a User Feature Reference into a Target Part

```cpp
// pRefFeature is a reference obtained from GetUserFeatureList() on the
// source Part's CATIUdfFactory
CATISpecObject_var spRefFeature = ...;
CATIUdfInstantiate* pUdfInstantiate = NULL;
spRefFeature->QueryInterface(IID_CATIUdfInstantiate, (void**)&pUdfInstantiate);

// 1) Destination: the whole MechanicalPart of the target document
CATISpecObject_var spTargetPart = pTargetPrtContainer->GetPart();
CATBaseUnknown_var spTargetPartBuk = spTargetPart;
CATPathElement pathToPart((CATBaseUnknown*)spTargetPartBuk);

CATBaseUnknown* pUIActiveObject = NULL;
CATBaseUnknown_var spDestination = NULL_var;
pUdfInstantiate->SetDestinationPath(&pathToPart, pUIActiveObject, spDestination);

// 2) Valuate inputs (position from 1 to GetOldInputs() list size)
CATPathElement pathOnInput(pTargetPlaneFeature);
pUdfInstantiate->SetNewInput(1, &pathOnInput);

// 3) Optionally override published parameters
CATListValCATBaseUnknown_var* pParamList = NULL;
CATListOfCATUnicodeString* pRoleList = NULL;
pUdfInstantiate->GetParameters(pParamList, pRoleList);
// modify each CATICkeParm found in pParamList as needed via CATICkeParm::Valuate()

// 4) Instantiate (destination Part is NULL_var: already set by SetDestinationPath)
HRESULT rc = pUdfInstantiate->Instantiate(NULL_var);

// 5) Retrieve the new instance and name it (must be between Instantiate/EndInstantiate)
CATBaseUnknown_var spNewInstance = pUdfInstantiate->GetInstantiated(NULL_var);
pUdfInstantiate->SetDisplayName("MountingBoss.1");

// 6) End and reset the instantiation transaction
pUdfInstantiate->EndInstantiate();
pUdfInstantiate->Reset();
pUdfInstantiate->Release();
```

### 4.4 Use "Identical Name" Auto-Valuation for Repeated Instantiation

```cpp
CATIUdfInstantiate* pUdfInstantiate = ...;  // After SetDestinationPath

// Automatically valuates every input by matching each input's role against
// the CATIAlias name of features under iRoot — handy when instantiating
// the same reference many times on similarly-named geometry
pUdfInstantiate->UseIdenticalName((CATBaseUnknown_var)spSearchRoot);

// Any input left unresolved can still be set manually afterwards
CATBaseUnknown_var spCheckInput1 = pUdfInstantiate->GetNewInput(1);
if (NULL_var == spCheckInput1) {
    CATPathElement pathOnFallback(pFallbackFeature);
    pUdfInstantiate->SetNewInput(1, &pathOnFallback);
}
```

### 4.5 Edit an Existing User Feature Instance

```cpp
// Only User Feature instances are editable; PowerCopy instances are plain
// independent features (Copy/Paste result) with no dedicated edit interface
CATISpecObject_var spUdfInstance = ...;  // A previously instantiated User Feature
CATIUdfFeatureInstance* pUdfEdit = NULL;
spUdfInstance->QueryInterface(IID_CATIUdfFeatureInstance, (void**)&pUdfEdit);

pUdfEdit->Init();

// Change one input by position
CATPathElement newInputPath(pNewInputFeature);
pUdfEdit->SetNewInput(1, &newInputPath);

// Read a published parameter by its role
CATBaseUnknown_var spParam;
pUdfEdit->GetParameter("HoleDiameter", spParam);
CATICkeParm_var spCkeParam = spParam;
if (!NULL_var(spCkeParam)) {
    spCkeParam->Valuate(12.0);
}

pUdfEdit->Reset();
pUdfEdit->Release();
```

### 4.6 Enumerate the Outputs of a User Feature Instance

```cpp
CATISpecObject_var spUdfInstance = ...;
CATIUdfFeatureInstance* pUdfEdit = NULL;
spUdfInstance->QueryInterface(IID_CATIUdfFeatureInstance, (void**)&pUdfEdit);
pUdfEdit->Init();

int outputCount = 0;
pUdfEdit->GetOutputsNumber(outputCount);

for (int i = 1; i <= outputCount; i++) {
    CATBaseUnknown_var spOutput;
    pUdfEdit->GetOutput(i, spOutput);
    // i == 1 is always the main User Feature result;
    // i == 2..N are the external outputs declared via CATIUdfFeatureUser::AddOutput()
    CATUnicodeString role;
    pUdfEdit->GetOutputRole(i, role);
}

pUdfEdit->Reset();
pUdfEdit->Release();
```

## 5. Related Capabilities

- **[cap.feature_recognition](feature-recognition.md)** — Identify features to include as PowerCopy/User Feature components
- **[cap.parameter_system](parameter-system.md)** — Manipulate `CATICkeParm` values retrieved as published parameters or inputs
- **[cap.surface_operations](surface-operations.md)** — GSD surface features can be included as PowerCopy/User Feature components
- **[cap.document_export](document-export.md)** — Save the reference Part document so its PowerCopy/User Feature can be reused, including as a catalog entry
