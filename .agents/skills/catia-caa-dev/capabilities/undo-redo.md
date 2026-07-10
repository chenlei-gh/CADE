---
id: cap.undo_redo
title: Undo/Redo Capability / 撤销重做能力
category: capability
domain: infrastructure
keywords: [undo, redo, transaction, rollback, CATIUndoRedoCommand]
apis: [CATIUndoRedoCommand, CATStateCommand, CATCommand]
frameworks: [ApplicationFrame]
difficulty: intermediate
release: [R19, R28]
tags: [capability]
---
# Undo/Redo Capability

使 CAA 命令支持 CATIA 的 Ctrl+Z / Ctrl+Y 撤销重做。

## 应用场景

- 修改 Feature 属性（长度、角度、类型）
- 几何操作（移动、旋转、缩放）
- 批量修改（多选后统一操作）

## 关联

| 类型 | ID | 说明 |
|------|-----|------|
| Philosophy | `philo.undo_redo` | Undo 设计哲学 |
| Knowledge | `infra.state_commands` | StateCommand 开发 |
| Pattern | `ui.master_detail` | 列表-详情编辑模式 |
