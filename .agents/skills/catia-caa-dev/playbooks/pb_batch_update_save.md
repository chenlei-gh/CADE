---
id: pb.batch_update_save
title: Batch Update & Save / 批量更新保存
category: playbook
domain: product
keywords: [update, save, batch, multi-document, persistence, dirty, NeedToBeSaved]
capabilities: [cap.update_mechanism, cap.persistence, cap.assembly_tree]
apis: [CATISpecObject, CATIxPDMItem, CATDocumentServices, CATIProduct, CATILinkableObject]
frameworks: [ObjectSpecsLegacy, ObjectModelerBase, CATxPDMInterfaces, ProductStructure]
difficulty: intermediate
effort: medium
release: [R19, R28]
tags: [playbook, update, save, batch, automation]
---

# Batch Update & Save (批量更新保存)

对装配体或大量零件执行批量 Update 后统一 Save，避免逐个手动操作。

## ⚠️ 重要修正

早期版本存在多处虚构 API，已按 [knowledge/philosophy/updates.md](../knowledge/philosophy/updates.md)、
[capabilities/document-export.md](../capabilities/document-export.md) 核实修正：

| 旧写法（虚构/错误） | 真实情况 |
|---------------|---------|
| `CATIModelEvents::Dispatch(CATModelUpdate)` | `CATModelUpdate` 是虚构枚举（CAADoc 零匹配）。触发 Update 的真实入口是 `CATISpecObject::Update(CATIDomain_var iDomain=NULL_var)`，`CATISpecObject` 自带该方法，无需转接口，直接返回 `int` |
| `CATISaveObject` | 整个接口不存在（CAADoc 零匹配） |
| `spSave->IsModified()` | 不存在。`CATIPersistent::Dirty()` 虽然存在，但官方文档明确注明"不要使用该方法，请改用 `CATIxPDMItem::NeedToBeSaved`"。真实推荐做法：QueryInterface `CATDocument` 到 `CATIxPDMItem`，调用 `NeedToBeSaved(CATBoolean& oNeedToBeSaved)` |
| `spSave->Save()` / `pDoc->SaveAs()` | `CATDocument` 本身没有 `Save()`/`SaveAs()` 方法。真实是静态方法 `CATDocumentServices::Save(CATDocument&, CATBoolean iInteractive)` / `SaveAs(CATDocument&, CATUnicodeString& iName, CATUnicodeString& iType, CATBoolean)` |
| `CATSetPtrCATDocument` | 该容器类型不存在。真实的文档指针列表容器是 `CATLISTP(CATDocument)`（`ObjectModelerBase` 框架） |
| `CATIDocument::IsReadOnly()` | 不存在这个便捷方法。只读状态同样通过 `CATIxPDMItem::GetReadOnlyStatus(CATBoolean& oIsReadOnly)` 获取 |
| 从 `CATIProduct` 拿不到所属文档 | `CATIProduct` 的实现组件（如 `ASMPRODUCT`）同时实现 `CATILinkableObject`，QueryInterface 到它即可调用 `GetDocument()` 拿到该节点所属的 `CATDocument*`（注意：该方法不 AddRef 返回值，不要 Release） |

## 目标

一键触发装配树中所有 Feature 的 Update，然后批量保存所有修改过的文档。

## 前置条件

- 已加载 CATProduct 及其子 CATPart 文档
- 部分 Feature 处于未更新（dirty）状态
- 有写权限的文档路径

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.update_mechanism` | 触发 Update 传播链 |
| `cap.assembly_tree` | 遍历装配获取所有文档 |
| `cap.persistence` | 执行 Save 操作 |

## 实现步骤

1. **获取根 Product**：通过当前编辑器或 selection，得到 `CATIProduct_var spRoot`
2. **递归遍历，收集所有子文档**：对每个 `CATIProduct` 节点 QI 到 `CATILinkableObject`，用 `GetDocument()` 取所属 `CATDocument*`，去重后放入 `CATLISTP(CATDocument)`
3. **触发 Update**：对根节点（或每个需要重算的 Feature）调用 `CATISpecObject::Update()`，让整棵树自上而下重算
4. **检查是否需要保存**：QI `CATDocument` 到 `CATIxPDMItem`，调用 `NeedToBeSaved(CATBoolean&)`，只保存真正被标记为需要保存的文档
5. **批量 Save**：对需要保存的文档调用 `CATDocumentServices::Save(CATDocument&, CATBoolean)` 静态方法
6. **进度反馈**：对大装配显示进度条

## 关键代码

```cpp
#include "CATDocumentServices.h"
#include "CATIxPDMItem.h"
#include "CATILinkableObject.h"
#include "CATIProduct.h"
#include "CATISpecObject.h"
#include "CATLISTP.h"

// 1. 递归收集装配树中所有唯一的 CATDocument*（每个 Product 节点通过
//    CATILinkableObject::GetDocument() 反查其所属文档；该方法不 AddRef 返回值）
void CollectAllDocuments(CATIProduct_var iProduct, CATLISTP(CATDocument) &ioDocs) {
    if (NULL_var == iProduct) return;

    CATILinkableObject_var spLinkable = iProduct;
    if (NULL_var != spLinkable) {
        CATDocument *pDoc = spLinkable->GetDocument();
        if (pDoc != NULL && ioDocs.Locate(pDoc) == 0) {   // 去重
            ioDocs.Append(pDoc);
        }
    }

    CATListValCATBaseUnknown_var *pChildren = iProduct->GetChildren();
    if (pChildren != NULL) {
        for (int i = 1; i <= pChildren->Size(); i++) {
            CATIProduct_var child = (*pChildren)[i];
            if (NULL_var != child) {
                CollectAllDocuments(child, ioDocs);
            }
        }
        delete pChildren;
    }
}

// 2. 触发整棵特征树的 Update（CATISpecObject 自带该方法，无需转接口）
HRESULT UpdateWholeTree(CATISpecObject_var iRoot) {
    if (NULL_var == iRoot) return E_FAIL;
    int rc = iRoot->Update();   // 默认 iDomain = NULL_var，自上而下重算
    return (rc == 0) ? S_OK : E_FAIL;
}

// 3. 只保存真正需要保存的文档：CATIPersistent::Dirty() 官方文档标注为
//    不推荐使用，改用 CATIxPDMItem::NeedToBeSaved()
HRESULT SaveDirtyDocuments(const CATLISTP(CATDocument) &iDocs) {
    HRESULT hrAll = S_OK;
    for (int i = 1; i <= iDocs.Size(); i++) {
        CATDocument *pDoc = iDocs[i];
        if (pDoc == NULL) continue;

        CATIxPDMItem *pPdmItem = NULL;
        pDoc->QueryInterface(IID_CATIxPDMItem, (void**)&pPdmItem);
        if (pPdmItem == NULL) continue;   // 未纳入 xPDM 管理，跳过

        CATBoolean needSave = FALSE;
        pPdmItem->NeedToBeSaved(needSave);

        CATBoolean isReadOnly = FALSE;
        pPdmItem->GetReadOnlyStatus(isReadOnly);

        if (needSave && !isReadOnly) {
            HRESULT hr = CATDocumentServices::Save(*pDoc, FALSE);  // FALSE = 非交互
            if (FAILED(hr)) {
                hrAll = hr;   // 记录失败但继续处理其余文档
            }
        }
        pPdmItem->Release();
    }
    return hrAll;
}

// 4. 组合入口
HRESULT BatchUpdateAndSave(CATIProduct_var iRoot) {
    if (NULL_var == iRoot) return E_FAIL;

    CATISpecObject_var spRootSpec = iRoot;   // CATIProduct 同时是 CATISpecObject
    HRESULT hr = UpdateWholeTree(spRootSpec);
    if (FAILED(hr)) return hr;

    CATLISTP(CATDocument) docs;
    CollectAllDocuments(iRoot, docs);

    return SaveDirtyDocuments(docs);
}
```

## 注意事项

- `CATISpecObject::Update()` 是懒加载机制，CATIA 不会自动调用；批量操作后必须显式触发，且失败会阻断整棵子树的后续 Update（见 [philo.updates](../knowledge/philosophy/updates.md)）
- Reference/Instance 关系：Update 一个 Reference 会影响所有引用它的 Instance
- 保存前用 `CATIxPDMItem::GetReadOnlyStatus()` 确认文档未只读，不要用不存在的 `CATIDocument::IsReadOnly()`
- `CATILinkableObject::GetDocument()` 不 AddRef 返回值，不要对返回的 `CATDocument*` 调用 `Release()`
- 批量操作建议记录日志，方便排查哪个文档保存失败（`CATDocumentServices::Save()` 返回 `HRESULT`，失败时应记录 `pDoc->StorageName()`）

## 相关 Failure Pattern

- `fp.undeclared_class` — Update 后可能暴露未声明的接口引用错误

## 相关 Playbook

- `pb.assembly_stats` — 可先统计装配规模，决定是否分批 Update
