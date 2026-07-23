---
id: philo.undo_redo
title: Undo/Redo Command Pattern / 撤销重做哲学
category: knowledge
domain: philosophy
keywords: [undo, redo, CATCommandGlobalUndo, transaction, rollback, state]
apis: [CATCommandGlobalUndo, CATCommand, CATStateCommand, CATCommandHeader, CATISpecAttrAccess]
frameworks: [System, ApplicationFrame, DialogEngine]
release: [R19, R28]
tags: [philosophy, undo, redo, command, core]
---
# Undo/Redo Command Pattern

CAA 的 Undo/Redo 机制基于 `CATCommandGlobalUndo` 类。如果不正确实现，用户在 CATIA 中按 Ctrl+Z 不会撤销你的命令。

## 核心类

```cpp
#include "CATCommandGlobalUndo.h"

class MyUndoableCmd : public CATStateCommand {
public:
    // 在命令完成后创建 CATCommandGlobalUndo 对象
    // 用于注册撤销/重做回调
};

// 撤销/重做对象——命令删除后仍保留
class MyGlobalUndo : public CATCommandGlobalUndo {
public:
    MyGlobalUndo(void *iData) : CATCommandGlobalUndo() { SetData(iData); }

    // 在事务性 undo 之前调用
    HRESULT BeforeUndo() override;
    // 在事务性 redo 之前调用
    HRESULT BeforeRedo() override;
    // 在事务性 undo 之后调用
    HRESULT AfterUndo() override;
    // 在事务性 redo 之后调用
    HRESULT AfterRedo() override;
};
```

## 实现模式

```cpp
HRESULT MyGlobalUndo::BeforeUndo() {
    // 1. 恢复属性（通过 CATISpecAttrAccess）
    CATISpecAttrAccess_var spAttrAccess = _spFeature;
    if (NULL_var != spAttrAccess) {
        spAttrAccess->SetDouble("Length", _oldValue);
    }

    // 2. 如果有几何修改，重新 Update
    CATISpecObject_var spSpec = _spFeature;
    if (NULL_var != spSpec) {
        spSpec->Update();
    }

    return S_OK;
}

HRESULT MyGlobalUndo::BeforeRedo() {
    CATISpecAttrAccess_var spAttrAccess = _spFeature;
    if (NULL_var != spAttrAccess) {
        spAttrAccess->SetDouble("Length", _newValue);
    }
    CATISpecObject_var spSpec = _spFeature;
    if (NULL_var != spSpec) {
        spSpec->Update();
    }
    return S_OK;
}
```

## 事务管理

```cpp
#include "CATAfrUndoRedoServices.h"

// 创建新事务（在命令开始时）
int transactionIndex = 0;
HRESULT hr = CATAfrNewTransaction(pEditor, "MyCommand", TRUE, transactionIndex);

// 锁定/解锁 Undo/Redo（批量操作时）
CATAfrLockUndoRedoTransactions(TRUE);
// ... 执行批量修改 ...
CATAfrUnlockUndoRedoTransactions();
```

## 何时需要 Undo

| 操作类型 | 需要 Undo？ | 原因 |
|---------|------------|------|
| 修改属性 | ✅ 是 | 用户可能想撤销修改 |
| 修改几何 | ✅ 是 | Ctrl+Z 预期行为 |
| 查看/分析 | ❌ 否 | 只读操作 |
| 导出文件 | ❌ 否 | 外部文件不影响 CATIA 状态 |

## AI 生成规则

- [ ] 修改属性的 Command 必须创建 `CATCommandGlobalUndo` 派生对象
- [ ] 在 `BuildGraph` 中保存修改前的状态
- [ ] `BeforeUndo()` / `AfterUndo()` 必须完全恢复到修改前的状态
- [ ] `BeforeRedo()` / `AfterRedo()` 必须重新应用所有修改
- [ ] 属性修改通过 `CATISpecAttrAccess` 接口（SetDouble / SetInteger / SetString）
- [ ] 复杂修改（多步骤）使用 `CATAfrNewTransaction` 创建事务
