---
id: infra.state_commands
title: State Command Guide
category: knowledge
domain: infrastructure
keywords: [state command, CATStateCommand, BuildGraph, dialog state, agent, transition, wizard]
apis: [CATStateCommand, CATDialogState, AddDialogState, AddTransition, CATPathElementAgent, BuildGraph, Action, Condition, CATStatusChangeRC]
requires: []
patterns: [ui.wizard]
examples: []
release: [R19, R28]
tags: [infrastructure, command, state]
---

# CAA State Command Guide

## 什么是 StateCommand

`CATStateCommand` 是 CAA 中**有状态的交互式命令**基类。区别于一次性命令（点一下就执行），状态命令有交互序列。

### 状态机

```
UNDEFINED → READY → ACQUIRED → VALIDATED → READY...
    ↑                               ↓
    └─────── 用户取消 (Cancel) ←───-┘
```

## 基本结构

```cpp
class ATAutoRenameCmd : public CATStateCommand {
    CATDeclareClass;  // 声明为组件类
    
public:
    // 构造函数：对应 CATStateCommand(CATString&, CATDlgEngBehavior, CATCommandMode)
    ATAutoRenameCmd();
    virtual ~ATAutoRenameCmd();
    
    // 生命周期（从 CATCommand 继承，返回值只有 CATStatusChangeRCCompleted / CATStatusChangeRCAborted）
    virtual CATStatusChangeRC Activate(CATCommand*, CATNotification*);
    virtual CATStatusChangeRC Desactivate(CATCommand*, CATNotification*);
    virtual CATStatusChangeRC Cancel(CATCommand*, CATNotification*);
    
    // 状态机构建（从 CATStateCommand 继承，每个主命令必须重写）
    virtual void BuildGraph();
    
    // Action / Condition 回调（必须是 CATBoolean (CATCommand::*)(void*) 签名，通过 Action()/Condition() 包装后交给 AddTransition 使用）
    CATBoolean OnApply(void *iUsefulData);
    CATBoolean CheckSelectionValid(void *iUsefulData);
private:
    CATPathElementAgent *_pAgent;
    ATAutoRenameDlg *_pDlg;
};
```

## 注册与 Catalog

Imakefile.mk:
```makefile
SOURCES += \
    src/ATAutoRenameCmd.cpp \
    src/ATAutoRenameCmdHeader.cpp \
    src/ATAutoRenameDlg.cpp
```

Catalog 条目 (Framework.edu/CNext/code/dictionary/Framework.dico):
```
ATAutoRenameCmd  CATStateCommand  libAT_UI
```

Header 注册文件 (`src/ATAutoRenameCmdHeader.cpp`):
```cpp
#include "ATAutoRenameCmd.h"
#include "TIE_CATISelectNotification.h"
#include <CATCommandHeader.h>
MacDeclareHeader(ATAutoRenameCmdHeader);
```

## 常见状态命令模式

### 模式 1：选择→执行

```
Activate → BuildGraph 创建 CATPathElementAgent → 用户选择特征（命中转移） → Action 回调执行操作 → Desactivate
```

适用于：几何分析、批量属性修改

> ⚠️ **重要修正**：旧版本的 `OnSelect(void*, CATNotification*, CATCommandClientInfo*)` 签名是虚构的——`CATCommandClientInfo` 在 CAADoc 官方参考中不存在。`CATStateCommand` 的选择响应不是通过重写回调方法实现的，而是通过 `BuildGraph()` 中用 `IsOutputSetCondition(pAgent)` 作为转移条件，并用 `Action()` 包装一个 `CATBoolean (CATCommand::*)(void*)` 签名的成员方法作为转移执行动作（参考官方样例 `CAADegAnalysisNumericCmd.cpp`）：

```cpp
// 成员变量：CATPathElementAgent *_pAgent;

void ATAutoRenameCmd::BuildGraph() {
    CATDialogState *pReady = GetInitialState("ReadyState");
    CATDialogState *pDone  = AddDialogState("DoneState");

    _pAgent = new CATPathElementAgent("PathEltSelection");
    _pAgent->AddElementType(IID_CATISpecObject);
    pReady->AddDialogAgent(_pAgent);  // 注入选择器绑到初始状态，不是直接回调方法

    AddTransition(pReady, pDone,
        IsOutputSetCondition(_pAgent),
        Action((ActionMethod)&ATAutoRenameCmd::OnApply, NULL, NULL, NULL));
}

// Action 回调：必须是 CATBoolean (CATCommand::*)(void *iData)
// 注意：CATPathElement 的真实方法是 FindElement(IID&)，直接返回 CATBaseUnknown*，
// 并不存在 FindObject(IID, void**) 返回 HRESULT 的写法
CATBoolean ATAutoRenameCmd::OnApply(void *iUsefulData) {
    CATPathElement *pPath = _pAgent->GetValue();
    if (!pPath) return FALSE;

    CATBaseUnknown *pObj = pPath->FindElement(IID_CATISpecObject);
    if (!pObj) return FALSE;

    CATISpecObject_var spObj = pObj;
    if (NULL_var == spObj) return FALSE;

    HRESULT hr = Rename(spObj, _newName);
    if (FAILED(hr)) {
        CATError("ATCmd", "OnApply", "Rename failed");
        return FALSE;
    }
    return TRUE;
}
```

### 模式 2：Dialog→输入→执行

```
Activate → Show dialog → 用户输入参数 → OnApply → 执行 → Desactivate
```

适用于：批量重命名、参数化设置

### 模式 3：多步骤向导

```
Activate → Step1 (选择基准) → Step2 (选择目标) → Step3 (确认) → Execute → Desactivate
```

## 命令可用性控制

> ⚠️ **重要修正**：`CATCommand`/`CATStateCommand` 均**不存在** `GetState(CATNotification*, CATCommandCompletion*)` 方法，`CATCommandCompletion`、`CATMultiCompletion`、`CATStaEnable`、`CATStaDisable` 在 CAADoc 官方参考中均不存在，均为虚构 API。命令的启用/禁用（灰化图标）是通过 `CATCommandHeader` 实现的，不是命令类自身的虚方法：

```cpp
// 方式一：构造时指定初始状态（CATCommandHeader.h）
new CATCommandHeader(headerID, loadName, className, iArgument,
                      CATFrmUnavailable);  // 默认为 CATFrmAvailable

// 方式二：运行时动态切换（例如在 BuildGraph() 建立的状态图的 Action 回调中）
pHeader->BecomeAvailable();     // 图标从灰化变为正常
pHeader->BecomeUnavailable();   // 图标从正常变为灰化

// 方式三：按名称静态设置（ApplicationFrame 框架）
CATCmdHeaderSensitivityMngt::SetSensitivity(iPaletteName, iHeaderName,
                                              CATDlgDisable);  // 或 CATDlgEnable
```

若需要根据文档类型等上下文条件动态启用/禁用命令，应在 `BuildGraph()` 中用 `Condition()` 包装一个判断方法，并结合 `Action()` 在合适的状态转移上调用 `BecomeAvailable()`/`BecomeUnavailable()`，而不是重写不存在的 `GetState()`。

## AI 生成规则

- [ ] 继承 `CATStateCommand`
- [ ] 添加 `CATDeclareClass` 宏
- [ ] 实现 `Activate`/`Desactivate`/`Cancel`（返回 `CATStatusChangeRC`）与 `BuildGraph()`（构建状态图，无返回值）
- [ ] 注册 Header 文件（`{Name}Header.cpp`）
- [ ] Catalog 条目写 `CATStateCommand`（非 `CATCommand`）
- [ ] Agent 使用 `CATPathElementAgent`（选择元素用）
- [ ] Agent 使用 `CATIndicationAgent`（点击位置用）
