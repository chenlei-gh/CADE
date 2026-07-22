---
id: infra.selection
title: Selection
category: knowledge
domain: infrastructure
keywords: [selection, select, pick, highlight, CATCSO, CATPathElement, reframe, locate, HSO, ISO]
apis: [CATCSO, CATFrmEditor, CATPathElement, CATISO, CATISelectionSet]
requires: []
patterns: [block.locator, ui.result_dialog]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [ui, interaction, locate]
---

# Selection (选择)

CAA 中选择操作的核心：通过 `CATFrmEditor` 暴露的对象集合（CSO/HSO/ISO）管理选中、高亮与相机定位。

## ⚠️ 重要修正

之前版本引用的 `CATISelection`、`CATISelectionResults`、`SelectElement()`、`CATVisProperties::SetHighlight()`、`CATISO::ReframeOnObject()` 经 CAADoc 核实**均不存在**。`CATFrmEditor` 上也没有 `GetSelection()` 方法。真实的当前选择集是 `CATCSO`（Current Selection of Objects），通过 `CATFrmEditor::GetCSO()` 获取。

## 核心 API

`CATFrmEditor` 暴露 4 个不同的对象集合，**不是一个统一的 "Selection" 对象**：

| 方法 | 返回 | 用途 |
|------|------|------|
| `GetCSO()` | `CATCSO*` | **当前选择集**（用户已点选的对象） |
| `GetHSO()` | — | 高亮对象集 |
| `GetPSO()` | — | 预选集（悬停预高亮） |
| `GetISO()` | `CATISO*` | 交互对象集（管理 viewer，**不做相机定位**） |

### 获取当前选择集

```cpp
CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
CATCSO* pCSO = pEditor->GetCSO();
```

### 选择 Feature（加入当前选择集）

`CATCSO::AddElement` 接收 `CATBaseUnknown*`（通常是 `CATPathElement*`），不是值类型：

```cpp
CATCSO* pCSO = CATFrmEditor::GetCurrentEditor()->GetCSO();
CATPathElement* pPath = new CATPathElement(pFeature);
pCSO->AddElement(pPath);          // 可选第2参 iDispatchChange=1 触发通知
```

### 清除选择

```cpp
pCSO->Empty();   // 可选 int 参数控制通知
```

### 遍历已选中的元素

```cpp
CATCSO* pCSO = CATFrmEditor::GetCurrentEditor()->GetCSO();
int count = pCSO->GetSize();
pCSO->InitElementList();
CATBaseUnknown* pElem = NULL;
while (NULL != (pElem = pCSO->NextElement())) {
    // pElem 通常是 CATPathElement*，按需 QueryInterface
}
```

其他真实方法：`RemoveElement(CATBaseUnknown*, int)`、`Contains(CATBaseUnknown*)`。

## 高亮 Feature

**不存在** `CATVisProperties::SetHighlight()` 静态方法。持久化高亮/颜色通过 `CATIVisProperties` 接口（从 Feature 上 QueryInterface 获得）：

```cpp
CATIVisProperties* pIProps = NULL;
HRESULT rc = pFeature->QueryInterface(IID_CATIVisProperties, (void**)&pIProps);
if (SUCCEEDED(rc)) {
    CATVisPropertiesValues props;
    props.SetColor(255, 0, 0);                       // 红色
    // GeomType 真实取值（CATVisGeomType.h 的 #define）：
    // CATVPGlobalType/CATVPMesh/CATVPEdge/CATVPLine/CATVPPoint/CATVPAsm
    pIProps->SetPropertiesAtt(props, CATVPColor, CATVPAsm);
    pIProps->Release();
}
```

临时的"高亮集"用 `CATFrmEditor::GetHSO()`。交互式高亮模式见 `CATRep::SetHighlightMode`、`CATIGraphNode::SetHighlight(int)`。

## 双击定位 / 相机定位 Feature

**不存在** `CATISO::ReframeOnObject()`。相机定位对 viewer 操作：

```cpp
// 方式1: 对指定 3D 包围球定位
CAT3DViewer* pViewer = ...;
CAT3DBoundingSphere bs = ...;      // 从对象的 rep 获取
pViewer->ReframeOn(bs);

// 方式2: 对当前显示内容全景定位
CATViewer* pViewer = ...;
pViewer->Reframe();
```

选中后自动跟随相机的开关在 `CATIReframeCamera::SetReframe(int)`（ApplicationFrame）。

## 持久命名选择集（CATISelectionSet）

与 `CATCSO`（实时交互选择）不同，`CATISelectionSet`（InteractiveInterfaces）是**可保存、可复用**的命名选择集：

```cpp
CATISelectionSet_var spSet = ...;   // 经 CATISelectionSetsFactory 获得
CATISelectionSetElement* pSetElem = NULL;
CATPathElement* pPath = new CATPathElement(pFeature);
HRESULT rc = spSet->AddElement(pPath, pSetElem);
// 其他: FindElement / GetSize / IsMember / RemoveElement / ListElement
```

## 交互式拾取（用户点选）

让用户在 3D 中拾取对象，用 DialogEngine 的 Agent，而不是直接操作 CSO：

```cpp
CATPathElementAgent* pAgent = new CATPathElementAgent("PickAgent");
pAgent->AddElementType(IID_CATIxxx);      // 过滤可拾取类型（可多次调用）
// 在 CATStateCommand 的状态图中挂接，拾取结果经
// CATDialogAgent 通知回调 → GetValue() 取 CATPathElement
```

## 常用模式

| 场景 | 方式 |
|------|------|
| 选择单个对象 | `CATCSO::AddElement(new CATPathElement(feature))` |
| 清除选择 | `CATCSO::Empty()` |
| 持久高亮/变色 | `CATIVisProperties::SetPropertiesAtt(props, CATVPColor, ...)` |
| 相机定位对象 | `CAT3DViewer::ReframeOn(CAT3DBoundingSphere&)` |
| 遍历选中 | `CATCSO::InitElementList()` + `NextElement()` |
| 选中数量 | `CATCSO::GetSize()` |
| 命名选择集 | `CATISelectionSet::AddElement(path, elem)` |
| 用户交互拾取 | `CATPathElementAgent`（DialogEngine） |

## 参考样例

- HSO/ISO 用法：`CAAAfrGeoCommands.m/src/CAAAfrBoundingElementCmd.cpp`
- 可视化属性：`CAAGeometryVisualization.edu/CAAGviApplyProperties.m/src/CAAGviApplyProperties.cpp`
