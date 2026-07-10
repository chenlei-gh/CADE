---
id: philo.undo_redo
title: Undo/Redo Command Pattern / 撤销重做哲学
category: knowledge
domain: philosophy
keywords: [undo, redo, CATIUndoRedoCommand, transaction, rollback, state]
apis: [CATIUndoRedoCommand, CATCommand, CATStateCommand, CATCommandHeader]
frameworks: [ApplicationFrame, DialogEngine]
release: [R19, R28]
tags: [philosophy, undo, redo, command, core]
---
# Undo/Redo Command Pattern

CAA 的 Undo/Redo 机制基于 Command 模式。如果不正确实现，用户在 CATIA 中按 Ctrl+Z 不会撤销你的命令。

## 核心接口

```cpp
class MyUndoableCmd : public CATStateCommand, public CATIUndoRedoCommand {
public:
    // CATIUndoRedoCommand 必须实现
    HRESULT Undo();   // 撤销操作
    HRESULT Redo();   // 重做操作

    // 在 BuildGraph 中执行实际操作
    // CATIA 自动调用 Undo/Redo
};
```

## 实现模式

```cpp
HRESULT MyUndoableCmd::Undo() {
    // 1. 恢复属性
    _spFeature->SetAttribute("Length", _oldValue);

    // 2. 如果有几何修改，重新 Update
    CATIMechanicalUpdate_var spUpdate = _spFeature;
    spUpdate->Update();

    return S_OK;
}

HRESULT MyUndoableCmd::Redo() {
    _spFeature->SetAttribute("Length", _newValue);
    CATIMechanicalUpdate_var spUpdate = _spFeature;
    spUpdate->Update();
    return S_OK;
}
```

## 何时需要 Undo

| 操作类型 | 需要 Undo？ | 原因 |
|---------|------------|------|
| 修改属性 | ✅ 是 | 用户可能想撤销修改 |
| 修改几何 | ✅ 是 | Ctrl+Z 预期行为 |
| 查看/分析 | ❌ 否 | 只读操作 |
| 导出文件 | ❌ 否 | 外部文件不影响 CATIA 状态 |

## AI 生成规则

- [ ] 修改属性的 Command 必须实现 `CATIUndoRedoCommand`
- [ ] 在 `BuildGraph` 中保存修改前的状态
- [ ] `Undo()` 必须完全恢复到修改前的状态
- [ ] `Redo()` 必须重新应用所有修改
- [ ] 复杂修改（多步骤）使用 Command Stack 模式
