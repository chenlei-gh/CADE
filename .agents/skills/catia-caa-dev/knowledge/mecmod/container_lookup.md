---
id: mecmod.container_lookup
title: Container Member Lookup (容器成员查找)
category: knowledge
domain: mecmod
keywords: [container, CATIContainer, ListMembersHere, GeometricalSet, OrderedGeometricalSet, CATIAlias, find by name, 遍历容器, 几何集]
apis: [CATIContainer, CATIAlias, CATISpecObject, CATIPrtContainer]
requires: [mecmod.feature]
patterns: []
examples: []
release: [R19, R28]
tags: [core, container, traversal]
---

# Container Member Lookup (容器成员查找)

## ⚠️ 重要修正

| 虚构/错误写法 | 问题 | 正确写法 |
|---|---|---|
| `pCATIContainer->GetAllChildren()` | **`CATIContainer` 没有 `GetAllChildren()`**。该方法是 `CATIProduct`（装配树）和 `CATIParmPublisher`（参数树）的，不能平移到容器接口上 | `CATIContainer::ListMembersHere(interfaceID, seq)` |
| `pCATIContainer->GetChildren()` | 同样不存在于 `CATIContainer` | 同上 |
| `pCATIContainer->FindObject(name)` / `GetMember(name)` | 均不存在 | `ListMembersHere("CATIAlias", seq)` + 逐个比对 `CATIAlias::GetAlias()` |

**`GetAllChildren` 的合法主人只有两个**：`CATIProduct::GetAllChildren()`（装配树深度遍历）和 `CATIParmPublisher::GetAllChildren()`（已发布参数树）。看到"容器找子对象"就写 `GetAllChildren` 是典型的模式错配。

## CATIContainer 的真实成员遍历 API（B28 头文件核实）

`CATIContainer`（ObjectModelerBase）只有两个成员列举方法：

```cpp
// 递归列举：返回实现指定接口的所有成员（含子容器内），返回新分配的 SEQUENCE，调用方负责释放
virtual SEQUENCE(CATBaseUnknown_ptr) ListMembers(const CATIdent interfaceID) = 0;

// 仅本层：填充实现指定接口的成员到输出序列，返回个数
// ⚠️ 序列中每个对象用后必须 Release()
virtual CATLONG32 ListMembersHere(const CATIdent interfaceID,
                                  SEQUENCE(CATBaseUnknown_ptr)& ioListObj) = 0;
```

`interfaceID` 是**接口名字符串**（如 `"CATIAlias"`、`"CATISpecObject"`），不是 IID。

## 场景 1：按名称查找 GeometricalSet / 任意成员

容器成员没有统一的"按名查找"方法，标准通路是：列出实现 `CATIAlias` 的成员 → 比对 `GetAlias()`：

```cpp
#include "CATIContainer.h"
#include "CATIAlias.h"
#include "CATISpecObject.h"

// 在 Part 规格容器里按名称找 GeometricalSet / OrderedGeometricalSet
CATISpecObject* FindGeometricalSet(CATIContainer* iCont,
                                   const CATUnicodeString& iName) {
    if (!iCont) return NULL;
    SEQUENCE(CATBaseUnknown_ptr) seq;
    CATLONG32 n = iCont->ListMembersHere("CATIAlias", seq);
    CATISpecObject* pFound = NULL;
    for (int i = 0; i < n && !pFound; i++) {
        CATBaseUnknown* pObj = seq[i];
        if (pObj) {
            CATIAlias* pAlias = NULL;
            if (SUCCEEDED(pObj->QueryInterface(IID_CATIAlias, (void**)&pAlias)) && pAlias) {
                CATISpecObject_var spSpec = pObj;
                if (spSpec != NULL_var
                    && (spSpec->IsATypeOf("GeometricalSet")
                        || spSpec->IsATypeOf("OrderedGeometricalSet"))
                    && pAlias->GetAlias() == iName) {
                    pFound = spSpec;
                    if (pFound) pFound->AddRef();  // 返回前 +1，调用方管理
                }
                pAlias->Release();
            }
            pObj->Release();  // ListMembersHere 序列元素必须逐个 Release
        }
    }
    return pFound;
}
```

要点：
- `IsATypeOf("GeometricalSet")` 判断 late type，无需专门接口
- 序列元素**必须逐个 `Release()`**（头文件明确要求），泄漏是高频坑
- 只找本层用 `ListMembersHere`；要递归进子容器才用 `ListMembers`

## 场景 2：列举 Part 下所有几何集（不限名称）

```cpp
SEQUENCE(CATBaseUnknown_ptr) seq;
CATLONG32 n = pSpecContainer->ListMembersHere("CATISpecObject", seq);
for (int i = 0; i < n; i++) {
    CATISpecObject_var spSpec = seq[i];
    if (spSpec != NULL_var && spSpec->IsATypeOf("OrderedGeometricalSet")) {
        // 处理几何集...
    }
    if (seq[i]) seq[i]->Release();
}
```

## 场景辨析速查

| 需求 | 正确 API | 所属接口 |
|---|---|---|
| 遍历装配子组件 | `GetChildren()` / `GetAllChildren()` | `CATIProduct` |
| 遍历已发布参数树 | `GetAllChildren()` / `GetDirectChildren()` | `CATIParmPublisher` |
| 遍历/查找容器成员（几何集、Feature 等） | `ListMembersHere()` / `ListMembers()` | `CATIContainer` |
| Feature 树父子遍历 | `CATINavigateObject::GetChildren()` | `CATINavigateObject`（QI 自 CATISpecObject） |

四个"树"各有自己的遍历 API，**互不通用**——写之前先确认手里的变量是哪种接口。
