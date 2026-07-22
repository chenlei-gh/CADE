---
id: mecmod.feature_patterns
title: Feature & Attribute Patterns
category: knowledge
domain: mecmod
keywords: [feature, attribute, CATISpecObject, StartUp, factory, object modeler, late type, catalog]
apis: [CATISpecObject, CATISpecAttribute, CATOsmSUHandler, CATFmStartUpFacade, CATICkeParmFactory]
requires: [mecmod.feature]
patterns: []
examples: []
release: [R19, R28]
tags: [mecmod, feature, attribute]
---

# CAA Feature & Attribute Patterns

## ⚠️ 重要修正

之前版本以下宏/类经 B28 全盘核实**均不存在**：

| 虚构 | 真实情况 |
|------|---------|
| `CATImplementStartUp(...)` 宏 | 不存在此宏。StartUp 是**目录(.CATfct)中的条目**，经 `CATOsmSUHandler` 实例化 |
| `CATFeatureStartUp` / `CATFeatureNoCatalogStartUp` / `CATGeoOperatorStartUp` | 不存在这些类。StartUp 类型由目录条目的工厂/late type 决定 |
| `CATAttribute(Class, "Name", Type, member)` 宏 | 不存在此宏。属性经 `CATISpecAttribute` + `CATIAttrDictionary`/`CATIAttrDescription` 定义 |
| `CATNull` 宏 | B28 头文件中查无此宏。`CATImplementClass` 第 4 参是 **late type 名**（见官方样例） |
| `CATIContainerOfDocument::CreateFeature(name, &spFeature)` | 无此方法。Feature 实例化走 StartUp 路径 |

## 什么是 CAA Feature

Feature 是 CATIA 的持久化数据单元，由 `CATISpecObject` 承载。自定义 Feature 需要：

1. **Extension 类**：实现自定义接口，用 `CATImplementClass(X, DataExtension, CATBaseUnknown, LateType)` 挂到 late type 上
2. **StartUp**：定义在**目录 (.CATfct)** 中的 Feature 模板（类型 + 默认属性值），在字典 (.dico) 中登记
3. **Factory**：运行时用 `CATOsmSUHandler` 从目录取 StartUp 并实例化

## Feature 基本结构

### Interface (PublicInterfaces/IATTimeTable.h)

```cpp
#ifndef AT_FEATURE_IATTimeTable_H
#define AT_FEATURE_IATTimeTable_H

#include "CATBaseUnknown.h"

#ifndef ExportedByAT_Feature
#define ExportedByAT_Feature
#endif

extern ExportedByAT_Feature IID IID_IATTimeTable;

class ExportedByAT_Feature IATTimeTable : public CATBaseUnknown {
    CATDeclareInterface;
public:
    virtual HRESULT SetTimestamp(const CATUnicodeString &iTime) = 0;
    virtual HRESULT GetTimestamp(CATUnicodeString &oTime) = 0;
    virtual HRESULT SetDuration(int iSeconds) = 0;
    virtual int GetDuration() = 0;
};
#endif
```

### Extension Class (LocalInterfaces/ATTimeTable.h)

```cpp
#include "CATBaseUnknown.h"
#include "IATTimeTable.h"

class ATTimeTable : public CATBaseUnknown {
    CATDeclareClass;
public:
    ATTimeTable();
    virtual ~ATTimeTable();

    // IATTimeTable
    HRESULT SetTimestamp(const CATUnicodeString &iTime);
    HRESULT GetTimestamp(CATUnicodeString &oTime);
    HRESULT SetDuration(int iSeconds);
    int GetDuration();

private:
    CATUnicodeString _timestamp;
    int _duration;
};
```

### Extension 实现 (src/ATTimeTable.cpp)

官方样例（CAAObjectSpecsModeler.edu）真实写法——第 2 参 `DataExtension`，第 4 参是 **late type 名**：

```cpp
// 真实官方样例：
// CATImplementClass(CAAOsmSquareOp,
//                   DataExtension,
//                   CATBaseUnknown,
//                   CAAOsmSquare);
CATImplementClass(ATTimeTable,
                  DataExtension,
                  CATBaseUnknown,
                  ATTimeTable);          // ← late type，不是 CATNull

// TIE 绑定：把 IATTimeTable 接口实现绑到扩展上
CATImplementBOA(IATTimeTable, ATTimeTable);
```

## StartUp 与目录（Catalog）

StartUp **不是代码宏**，而是目录文件（`.CATfct`）中的一条 Feature 模板记录，包含 late type、默认属性、图标等。目录在模块的 dictionary (.dico) 中登记。

### 运行时实例化（真实 API：CATOsmSUHandler）

`CATOsmSUHandler`（ObjectSpecsLegacy）按 `"StartUpId@Catalog.CATfct"` 或 `(lateType, clientId, catalogName)` 定位 StartUp 并实例化：

```cpp
#include "CATOsmSUHandler.h"
#include "CATIContainer.h"
#include "CATISpecObject.h"

CATIContainer *piRootContainer = ...;   // 文档根容器

// 按 late type + 目录定位 StartUp
CATOsmSUHandler suHandler("ATTimeTable", "ATClientId", "ATCatalogSU.CATfct");

CATISpecObject_var spNewInst;
HRESULT rc = suHandler.Instanciate(spNewInst, piRootContainer, "ATTimeTable1");
if (SUCCEEDED(rc)) {
    // spNewInst 即新 Feature 实例
}
```

### 从已有 Feature 反查 StartUp

```cpp
CATISpecObject_var spObj = ...;
CATISpecObject_var spStartUp;
spObj->GetStartUp(spStartUp);    // CATISpecObject::GetStartUp 真实存在
```

相关真实 API：`CATFmStartUpFacade`（FeatureModelerExt，StartUp 门面）、`CATICkeParmFactory::InitStartUps()`。

## Attribute（属性）

属性**不是宏声明的成员变量**，而是 StartUp 模板里的命名字段，经 spec 接口读写：

```cpp
// 读属性
CATISpecObject_var spObj = ...;
CATISpecAttribute_var spAttr;
spObj->GetAttrKey("Timestamp", spAttr);        // 按名取属性
if (NULL_var != spAttr) {
    CATUnicodeString val;
    // 经 CATISpecAttribute 的值访问方法读写（见 ObjectSpecsLegacy 头文件）
}
```

属性定义（名称/类型/默认值）在 StartUp 目录条目中，或用 `CATIAttrDictionary`/`CATIAttrDescription`（ObjectSpecsLegacy）编程定义。扩展类里的 `_timestamp`/`_duration` 成员只是接口实现的缓存，持久化由 StartUp 属性机制负责。

## Factory 模式

### Factory (LocalInterfaces/ATTimeTableFactory.h)

```cpp
class ATTimeTableFactory : public CATBaseUnknown {
    CATDeclareClass;
public:
    ATTimeTableFactory();
    virtual ~ATTimeTableFactory();

    HRESULT CreateTimeTable(CATISpecObject *&oFeature);
};
```

### Factory 实现 (src/ATTimeTableFactory.cpp)

```cpp
CATImplementClass(ATTimeTableFactory, Implementation, CATBaseUnknown, ATTimeTableFactory);

HRESULT ATTimeTableFactory::CreateTimeTable(CATISpecObject *&oFeature) {
    // 1. 取当前文档与根容器
    CATFrmEditor *pEditor = CATFrmEditor::GetCurrentEditor();
    CATDocument *pDoc = pEditor->GetDocument();

    CATIContainerOfDocument_var spContOfDoc;
    HRESULT hr = pDoc->QueryInterface(IID_CATIContainerOfDocument,
                                      (void**)&spContOfDoc);
    if (FAILED(hr)) return hr;

    CATIContainer *pRootCont = NULL;
    hr = spContOfDoc->GetSpecContainer(pRootCont);   // MecModInterfaces，已核实
    if (FAILED(hr)) return hr;
    pRootCont->Release();   // 用毕释放（GetSpecContainer 返回 AddRef 指针）

    // 2. 经 CATOsmSUHandler 从目录实例化 StartUp
    CATOsmSUHandler suHandler("ATTimeTable", "ATClientId", "ATCatalogSU.CATfct");
    CATISpecObject_var spFeature;
    hr = suHandler.Instanciate(spFeature, pRootCont, "ATTimeTable1");
    if (FAILED(hr)) return hr;

    oFeature = spFeature;
    oFeature->AddRef();
    return S_OK;
}
```

> 注：`CATIContainerOfDocument` 位于 **MecModInterfaces**（非 ObjectSpecsLegacy），`GetSpecContainer` 已核实真实存在。

## 持久化流程

```
Factory → CATOsmSUHandler.Instanciate → CATISpecObject 实例
    ↓
写属性（CATISpecAttribute）→ StartUp 属性机制自动持久化
    ↓
Save document → Feature 数据保存到 CATPart
```

## AI 生成规则

- [ ] Interface 放在 `PublicInterfaces/`
- [ ] Extension 类放在 `LocalInterfaces/`
- [ ] **禁止发明** `CATImplementStartUp`/`CATFeatureStartUp`/`CATAttribute`/`CATNull` 宏
- [ ] `CATImplementClass(X, DataExtension, CATBaseUnknown, LateType)` 第 4 参写 late type 名
- [ ] Feature 实例化走 `CATOsmSUHandler::Instanciate`（目录路径），不是容器 `CreateFeature`
- [ ] 属性经 `CATISpecAttribute` 访问；定义在目录 StartUp 条目或 `CATIAttrDictionary`
- [ ] TIE 绑定用 `CATImplementBOA(Interface, ExtensionClass)`
