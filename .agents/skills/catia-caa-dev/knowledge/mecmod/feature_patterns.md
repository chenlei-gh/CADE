# CAA Feature & Attribute Patterns

## 什么是 CAA Feature

Feature 是 CATIA 的持久化数据单元，由 `CATISpecObject` 承载。自定义 Feature 需要：
1. 定义 **StartUp**（启动类型）
2. 声明 **Attribute**（属性）
3. 实现 **Factory**（工厂）

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

### Feature Class (LocalInterfaces/ATTimeTable.h)

```cpp
#include "CATBaseUnknown.h"
#include "IATTimeTable.h"
#include "CATISpecObject.h"

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

### Attribute 声明 (src/ATTimeTable.cpp)

```cpp
CATImplementClass(ATTimeTable, Implementation, CATBaseUnknown, CATNull);

// TIE 绑定
CATImplementBOA(IATTimeTable, CATBaseUnknown);

// StartUp 定义（必须在 CATImplementClass 之后）
CATImplementStartUp(
    ATTimeTable,
    CATFeatureStartUp);     // 作为 Feature 启动

// Attribute 声明
CATAttribute(ATTimeTable, "Timestamp", CATUnicodeString, _timestamp);
CATAttribute(ATTimeTable, "Duration",    int,                _duration);
```

### StartUp 类型

| StartUp | 用途 | 何时用 |
|---------|------|--------|
| `CATFeatureStartUp` | 标准 Feature | 持久化 Feature |
| `CATFeatureNoCatalogStartUp` | 无 Catalog Feature | 不需要出现在目录中 |
| `CATGeoOperatorStartUp` | 几何操作器 | 输入几何+参数→输出几何 |

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
CATImplementClass(ATTimeTableFactory, Implementation, CATBaseUnknown, CATNull);

ATTimeTableFactory::ATTimeTableFactory() {}
ATTimeTableFactory::~ATTimeTableFactory() {}

HRESULT ATTimeTableFactory::CreateTimeTable(CATISpecObject *&oFeature) {
    // 通过 CATIContainerOfDocument 获取 Container
    CATFrmEditor *pEditor = CATFrmEditor::GetCurrentEditor();
    CATDocument *pDoc = pEditor->GetDocument();
    
    CATIContainerOfDocument_var spContainer = NULL_var;
    HRESULT hr = pDoc->QueryInterface(IID_CATIContainerOfDocument,
                                       (void**)&spContainer);
    if (FAILED(hr)) return hr;

    // 创建 Feature 实例
    CATISpecObject_var spFeature = NULL_var;
    hr = spContainer->CreateFeature("ATTimeTable", &spFeature);
    if (FAILED(hr)) return hr;

    oFeature = spFeature;
    oFeature->AddRef();
    return S_OK;
}
```

## Catalog 注册

```
ATTimeTable  CATFeatureStartUp  libAT_Feature
```

## 持久化流程

```
用户创建 Feature
    ↓
Factory::CreateFeature → CATIContainerOfDocument → CATISpecObject
    ↓
Set Attribute 值 → CATAttribute 自动持久化
    ↓
Save document → Feature 数据保存到 CATPart
```

## AI 生成规则

- [ ] Interface 放在 `PublicInterfaces/`
- [ ] Feature 类放在 `LocalInterfaces/`
- [ ] 使用 `CATImplementStartUp` 声明启动类型
- [ ] 每个 Attribute 用 `CATAttribute` 宏声明
- [ ] 属性类型：`CATUnicodeString`, `int`, `double`, `CATBoolean`
- [ ] Factory 通过 `CATIContainerOfDocument::CreateFeature` 创建
- [ ] Catalog 条目写 `CATFeatureStartUp`
