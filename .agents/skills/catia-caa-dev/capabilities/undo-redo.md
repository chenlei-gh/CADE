---
id: cap.undo_redo
title: Undo/Redo Capability / 撤销重做能力
category: capability
domain: infrastructure
keywords: [undo, redo, transaction, rollback, CATStateCommand, CATCommandGlobalUndo, CATDiaAction, CATIUndoTransaction]
apis: [CATStateCommand, CATCommandGlobalUndo, CATDiaAction, CATIUndoTransaction]
frameworks: [DialogEngine, System]
difficulty: intermediate
release: [R19, R28]
tags: [capability]
---
# Undo/Redo Capability

使 CAA 命令支持 CATIA 的 Ctrl+Z / Ctrl+Y 撤销重做。

> ⚠️ `CATIUndoRedoCommand` 接口不存在（CAADoc 零匹配），已修正为真实机制，详见下文。真实框架是 `DialogEngine`（`CATStateCommand`/`CATDiaAction`）与 `System`（`CATCommandGlobalUndo`），不是 `ApplicationFrame`。

## ⚠️ 重要修正

| 旧写法（虚构） | 真实情况 |
|---------------|---------|
| `CATIUndoRedoCommand` | **不存在**（CAADoc 零匹配）。命令级 undo/redo 通过重写 `CATStateCommand::GetGlobalUndo()` 返回一个 **`CATCommandGlobalUndo`** 对象实现 |
| Framework `ApplicationFrame` | Undo/Redo 撤销重做的核心机制类属于 **`DialogEngine`**（`CATStateCommand`、`CATDiaAction`）和 **`System`**（`CATCommandGlobalUndo`）框架；`ApplicationFrame` 只提供少量全局辅助函数（如 `CATAfrLockUndoRedoTransactions`），并非撤销重做的主体 API |
| Undo/redo 分为"两级"是准确概念，但旧文档没有说明具体承载对象 | 官方明确区分 **Input undo/redo**（当前命令内，逐个输入撤销，靠 `CATDiaAction` 的 Before/AfterUndo/Redo 方法对）和 **Command undo/redo**（命令完成后整体撤销/重做，靠 `CATStateCommand::GetGlobalUndo()` 返回的 `CATCommandGlobalUndo`） |

## 应用场景

- 修改 Feature 属性（长度、角度、类型）
- 几何操作（移动、旋转、缩放）
- 批量修改（多选后统一操作）

## 核心机制

- **两级撤销体系**：Input undo/redo（命令执行中，撤销上一次的对话输入/状态迁移）与 Command undo/redo（命令完成后，撤销整个命令的效果）
- **Object undo/redo（对象自管理）**：如果命令创建/修改的对象实现了 `CATIUndoTransaction` 接口，该对象自己管理自己的撤销重做；命令提供的方法只需在对象撤销/重做前后（`BeforeUndo`/`AfterUndo`/`BeforeRedo`/`AfterRedo`）做辅助处理，绝不能重复修改该对象
- **Input undo/redo**：每个 `CATDiaAction`（通过 `Action()` 方法创建）可以携带一对撤销/重做方法（`Action()` 的第2、3参数，或 `SetExecuteMethod`/`SetBeforeUndoMethod`/`SetBeforeRedoMethod`/`SetAfterUndoMethod`/`SetAfterRedoMethod`）；这些方法在状态迁移被撤销/重做时自动调用
- **Command undo/redo**：重写 `CATStateCommand::GetGlobalUndo()`，在命令完成前返回一个 `CATCommandGlobalUndo` 对象（携带 undo 方法地址、redo 方法地址、命令产出的对象指针、释放该对象的方法地址）；由于命令已被删除，这些方法必须是 `static`
- **显式局部撤销步骤**：`CATStateCommand::AddLocalUndo(CATCommandGlobalUndo*, title, behavior)` 可以在非用户操作触发的迁移中（例如代码显式赋值一个采集代理）手动插入一个撤销栈步骤

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATStateCommand::GetGlobalUndo()` | 命令级撤销：重写此方法，命令结束前返回携带 undo/redo/deallocate 方法的 `CATCommandGlobalUndo` |
| `CATStateCommand::AddLocalUndo()` | 显式在撤销栈中插入一个局部撤销步骤（非用户操作触发迁移时使用） |
| `CATStateCommand::ExecuteUndoAtEnd()` | 命令结束时请求立即执行一次全局撤销（不推荐，官方建议改用 Cancel 状态迁移） |
| `CATCommandGlobalUndo` | 命令级撤销/重做对象：构造时传入 `BeforeUndo`/`BeforeRedo` 静态方法地址、携带数据指针、`Deallocate` 方法地址；也可派生并重写 `BeforeUndo`/`AfterUndo`/`BeforeRedo`/`AfterRedo` |
| `CATDiaAction` | 输入级撤销/重做：由 `CATStateCommand::Action()` 创建，通过 `SetBeforeUndoMethod`/`SetAfterUndoMethod`/`SetBeforeRedoMethod`/`SetAfterRedoMethod` 挂接撤销/重做方法 |
| `CATIUndoTransaction` | 由文档模型对象（非 CAA 开发者自行实现）实现的接口；实现该接口的对象自行管理自身的撤销/重做，命令的 undo/redo 方法不得重复修改它 |

## 4. Common Patterns

### 4.1 Command-Level Undo/Redo (Non-Transactional Object)

```cpp
// Header
class CAACreateTriangleCmd : public CATStateCommand {
public:
    CATCommandGlobalUndo* GetGlobalUndo();
    static void UndoCreateTriangle(void* iUsefulData);
    static void RedoCreateTriangle(void* iUsefulData);
    static void DeallocateTriangle(void* iUsefulData);
private:
    CATBaseUnknown* _EltTriangle;
};

// Implementation: called by the framework just before the command completes
CATCommandGlobalUndo* CAACreateTriangleCmd::GetGlobalUndo()
{
    CATCommandGlobalUndo* pGlobalUndo = NULL;
    if (_EltTriangle) {
        pGlobalUndo = new CATCommandGlobalUndo(
            (CATGlobalUndoMethod)&CAACreateTriangleCmd::UndoCreateTriangle,
            (CATGlobalUndoMethod)&CAACreateTriangleCmd::RedoCreateTriangle,
            (void*)_EltTriangle,
            (CATGlobalUndoMethod)&CAACreateTriangleCmd::DeallocateTriangle);
    }
    return pGlobalUndo;
}

// Undo/redo methods are static: the command instance no longer exists
void CAACreateTriangleCmd::UndoCreateTriangle(void* iUsefulData)
{
    CATBaseUnknown* pTriangle = (CATBaseUnknown*)iUsefulData;
    // ... remove pTriangle from the document
}

void CAACreateTriangleCmd::RedoCreateTriangle(void* iUsefulData)
{
    CATBaseUnknown* pTriangle = (CATBaseUnknown*)iUsefulData;
    // ... re-insert pTriangle into the document
}

void CAACreateTriangleCmd::DeallocateTriangle(void* iUsefulData)
{
    ((CATBaseUnknown*)iUsefulData)->Release();
}
```

### 4.2 Input-Level Undo/Redo for a State Transition

```cpp
void CAACreateTriangleCmd::BuildGraph()
{
    AddTransition(stStartState, stSecondState,
        AndCondition(
            IsOutputSetCondition(_daPathElement),
            Condition((ConditionMethod)&CAACreateTriangleCmd::CheckPoint1)),
        Action(
            (ActionMethod)&CAACreateTriangleCmd::CreatePoint,
            (ActionMethod)&CAACreateTriangleCmd::UndoCreatePoint,
            (ActionMethod)&CAACreateTriangleCmd::RedoCreatePoint));
}
```

### 4.3 Combining Object Undo/Redo (CATIUndoTransaction) with Command Hooks

```cpp
// The created/modified object implements CATIUndoTransaction itself,
// so BeforeUndo/AfterUndo/BeforeRedo run only auxiliary bookkeeping —
// they must NOT re-modify the transactional object.
CATDiaAction* pAction = Action((ActionMethod)&CAACreateTriangleCmd::CreatePoint);
pAction->SetBeforeUndoMethod((ActionMethod)&CAACreateTriangleCmd::BeforeUndoCreatePoint);
pAction->SetBeforeRedoMethod((ActionMethod)&CAACreateTriangleCmd::BeforeRedoCreatePoint);
pAction->SetAfterUndoMethod((ActionMethod)&CAACreateTriangleCmd::AfterUndoCreatePoint);
pAction->SetAfterRedoMethod((ActionMethod)&CAACreateTriangleCmd::AfterRedoCreatePoint);

AddTransition(stStartState, stSecondState,
    IsOutputSetCondition(_daPathElement), pAction);
```

### 4.4 Explicit Local Undo Step for a Non-User-Triggered Transition

```cpp
// Used when a dialog agent is explicitly valuated by code
// (e.g. reusing the current CSO content), which by default
// would not push an Undo step onto the stack.
CATCommandGlobalUndo* pLocalUndo = new CATCommandGlobalUndo();
AddLocalUndo(pLocalUndo, "MyStep");
pLocalUndo->Release();

_daPathElement->SetValue(pPathElement);
_daPathElement->SetValuation();
```

## 关联

| 类型 | ID | 说明 |
|------|-----|------|
| Philosophy | `philo.undo_redo` | Undo 设计哲学 |
| Knowledge | `infra.state_commands` | StateCommand 开发 |
| Pattern | `ui.master_detail` | 列表-详情编辑模式 |
