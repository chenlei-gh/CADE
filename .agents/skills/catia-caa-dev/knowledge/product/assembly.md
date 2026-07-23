---
id: product.assembly
title: Assembly
category: knowledge
domain: product
keywords: [assembly, product, component, instance, position, constraints, CATIProduct, CATIDocRoots, CATInit]
apis: [CATIProduct, CATIDocRoots, CATInit, CATIMovable, CATAsmConstraintServices, CATICst]
requires: [mecmod.feature]
patterns: [block.visitor]
examples: []
release: [R19, R28]
tags: [assembly, product, structure]
---

# Assembly (装配)

CATIA 装配设计（Assembly Design）通过 Product 和 Component 模型组织。

## ⚠️ 重要修正

本文档早期版本存在多处虚构 API，已按官方本地 CAADoc 核实并修正：

| 错误写法 | 问题 | 正确写法 |
|------|------|------|
| `CATIPrtContainer::GetRootProduct()` | `CATIPrtContainer` 是 **Part** 文档容器接口（仅有 `GetGeometricContainer()`/`GetPart()` 两个方法），根本没有 `GetRootProduct()`，且和 Product/装配文档无关 | `CATIDocRoots::GiveDocRoots()`（旧接口，需 QueryInterface）或官方推荐的 `CATInit::GetRootContainer()` |
| `CATIProduct::GetChildren(children)`（输出参数） | 签名错误 | `GetChildren()` 是**直接返回** `CATListValCATBaseUnknown_var*`，不是输出参数 |
| `CATListValCATIProduct_var` | 该类型不存在 | 应为 `CATListValCATBaseUnknown_var`，取出的元素需要 cast/QI 到 `CATIProduct_var` |
| `CATIProduct::GetInstanceName()` | 方法名虚构 | `GetPrdInstanceName(CATUnicodeString& oName)`，`HRESULT` 返回 + 输出参数 |
| `CATIProduct::GetName()` | `CATIProduct` 接口本身没有 `GetName()` | 参考名称用 `GetPartNumber()`（直接返回 `CATUnicodeString`） |
| `CATIConstraints` 接口 | 整个接口不存在（CAADoc 无任何匹配） | 装配约束通过静态服务类 `CATAsmConstraintServices::ListConstraints(CATIProduct*, CATLISTV(CATICst_var)&)` 获取，约束对象类型是 `CATICst`，不是 `CATISpecObject` |
| `CATIPosition` 接口 | 整个接口不存在，唯一相关的是不相关的材质接口 `CATIPositionedMaterial` | 父子实例间的相对位置用 `CATIMovable::GetPosition()`/`SetPosition()` |
| `GetPartContainer()` / `IsPart()` | 均为虚构方法，CAADoc 无任何匹配 | 已删除，无对应替代 |

## 核心 API

### 获取 Product 根

```cpp
// 方式一（官方推荐，来自 CATInit 文档说明）：
CATDocument* pDoc = ...;
CATInit* pInit = NULL;
pDoc->QueryInterface(IID_CATInit, (void**)&pInit);
CATBaseUnknown* pRoot = pInit->GetRootContainer(IID_CATIProduct);
CATIProduct_var pRootProduct = pRoot;
pInit->Release();

// 方式二（旧接口，仍被官方示例代码使用，如 CAAAsmCstSet）：
CATIDocRoots* piDocRootsOnDoc = NULL;
pDoc->QueryInterface(IID_CATIDocRoots, (void**)&piDocRootsOnDoc);
CATListValCATBaseUnknown_var* pRootProducts = piDocRootsOnDoc->GiveDocRoots();
CATIProduct_var pRootProduct = NULL_var;
if (pRootProducts != NULL && pRootProducts->Size() != 0) {
    pRootProduct = (*pRootProducts)[1];   // 索引从 1 开始
    delete pRootProducts;
}
piDocRootsOnDoc->Release();
```

### 遍历子组件

```cpp
#include "CATLISTV_CATBaseUnknown.h"  // CATListValCATBaseUnknown_var 的头文件（注意命名：类型名 ≠ 头文件名）

CATIProduct_var pRoot = ...;
// GetChildren() 是直接返回值，不是输出参数；
// 返回类型是 CATListValCATBaseUnknown_var*，需要逐个 cast 到 CATIProduct_var
CATListValCATBaseUnknown_var* pChildren = pRoot->GetChildren();

if (pChildren != NULL) {
    for (int i = 1; i <= pChildren->Size(); i++) {
        CATIProduct_var child = (*pChildren)[i];
        if (child != NULL_var) {
            // 处理子组件...
        }
    }
    delete pChildren;
}

// GetAllChildren() 用法相同，但返回所有层级（深度遍历）而不仅是直接子级
// GetChildrenCount() 直接返回 int，用于快速判断子组件数量
```

### 获取组件实例名称 / 参考名称

```cpp
CATIProduct_var pProduct = ...;

// 实例名称（同一 Reference 的不同 Instance 各自不同）
CATUnicodeString instanceName;
HRESULT hr = pProduct->GetPrdInstanceName(instanceName);

// 参考名称 / Part Number（同一 Reference 下所有 Instance 共享）
CATUnicodeString partNumber = pProduct->GetPartNumber();

// Reference <-> Instance 关系
CATBoolean isRef = pProduct->IsReference();
CATIProduct_var pReference = pProduct->GetReferenceProduct();
CATIProduct_var pFather = pProduct->GetFatherProduct();
```

### 获取组件位置

```cpp
CATIMovable_var pMovable = pProduct;

// 绝对位置（世界坐标系下的变换矩阵）
CATMathTransformation absPos;
pMovable->GetAbsPosition(absPos);

// 相对位置（相对于某个父级/上下文对象）
CATMathTransformation relPos = pMovable->GetPosition(pParentMovable);
```

### 获取组件约束

装配约束不是通过某个 `CATIProduct` 上的接口获得，而是通过 `CATAssemblyInterfaces` 框架提供的**静态服务类**：

```cpp
#include "CATAsmConstraintServices.h"
#include "CATICst.h"

CATIProduct_var pReferenceProduct = ...;   // 必须是参考产品（reference），不能是实例
CATLISTV(CATICst_var) constraints;
HRESULT hr = CATAsmConstraintServices::ListConstraints(pReferenceProduct, constraints);

for (int i = 1; i <= constraints.Size(); i++) {
    CATICst_var pCst = constraints[i];
    CATLONG32 cstType = pCst->GetCstType();
    // 处理约束...
}
```

## 常用判断

| 场景 | 方式 |
|------|------|
| 获取根 Product | `CATInit::GetRootContainer(IID_CATIProduct)` 或 `CATIDocRoots::GiveDocRoots()` |
| 遍历子组件 | `CATIProduct::GetChildren()`（直接子级）/ `GetAllChildren()`（全部层级） |
| 获取子组件数量 | `CATIProduct::GetChildrenCount()` |
| 获取实例名 | `CATIProduct::GetPrdInstanceName(oName)` |
| 获取参考名称 | `CATIProduct::GetPartNumber()` |
| 获取绝对位置 | `CATIMovable::GetAbsPosition(oPos)` |
| 获取相对位置 | `CATIMovable::GetPosition(iPosObj)` |
| 获取约束 | `CATAsmConstraintServices::ListConstraints(iProduct, oConstraintsList)` |
