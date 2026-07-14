---
id: pb.batch_update_save
title: Batch Update & Save / 批量更新保存
category: playbook
domain: product
keywords: [update, save, batch, multi-document, dispatch, model events, persistence, dirty]
capabilities: [cap.update_mechanism, cap.persistence, cap.assembly_tree]
apis: [CATIModelEvents, CATISaveObject, CATIDocument, CATIProduct]
frameworks: [ObjectModelerBase, CATAssemblyInterfaces, System]
difficulty: intermediate
effort: medium
release: [R19, R28]
tags: [playbook, update, save, batch, automation]
---

# Batch Update & Save (批量更新保存)

对装配体或大量零件执行批量 Update 后统一 Save，避免逐个手动操作。

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

1. **获取根 Product**：通过当前编辑器或 selection
2. **递归收集所有子文档**：区分 Part/Product，去重
3. **触发 Update**：`CATIModelEvents::Dispatch()` 或每个 Feature 逐个 Update
4. **检查 Dirty 状态**：只保存实际修改过的文档
5. **批量 Save**：使用 `CATISaveObject::Save()` 或 `CATDocument::SaveAs()`
6. **进度反馈**：对大装配显示进度条

## 关键代码

```cpp
HRESULT BatchUpdateAndSave(CATISpecObject *iRoot) {
    // 1. Update all
    CATIModelEvents_var spEvents = iRoot;
    if (NULL_var != spEvents) {
        spEvents->Dispatch(CATModelUpdate);  // 触发全树 Update
    }

    // 2. Collect all documents
    CATSetPtrCATDocument docs;
    CollectAllDocuments(iRoot, docs);

    // 3. Save only dirty documents
    for (int i = 0; i < docs.Size(); i++) {
        CATIDocument *pDoc = docs[i];
        CATISaveObject_var spSave = pDoc;
        if (NULL_var != spSave && spSave->IsModified()) {
            spSave->Save();  // 或 SaveAs() 如果需要指定路径
        }
    }
    return S_OK;
}
```

## 注意事项

- `CATModelUpdate` 会触发全树 Update，大装配可能很慢 — 建议用进度条
- Reference/Instance 关系：Update 一个 Reference 会影响所有 Instance
- 保存前确认文档未只读（`CATIDocument::IsReadOnly()`）
- 批量操作建议记录日志，方便排查哪个文档保存失败

## 相关 Failure Pattern

- `fp.undeclared_class` — Update 后可能暴露未声明的接口引用错误

## 相关 Playbook

- `pb.assembly_stats` — 可先统计装配规模，决定是否分批 Update
