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
    ATAutoRenameCmd();
    virtual ~ATAutoRenameCmd();
    
    // 生命周期（从 CATStateCommand 继承）
    virtual CATStatusChangeRC GetState(CATNotification*, CATCommandCompletion*);
    virtual CATBoolean Condition();
    virtual CATStatusChangeRC Activate(CATCommand*, CATNotification*);
    virtual CATStatusChangeRC Desactivate(CATCommand*, CATNotification*);
    virtual CATStatusChangeRC Cancel(CATCommand*, CATNotification*);
    
    // 自定义回调
    CATStatusChangeRC OnSelect(void *iData, CATNotification *iNotif,
                                CATCommandClientInfo *iInfo);
    CATStatusChangeRC OnApply(void *iData, CATNotification *iNotif,
                               CATCommandClientInfo *iInfo);
private:
    CATFeatureImportAgent *_pAgent;
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
Activate → Agent.Start → 用户选择特征 → OnSelect回调 → 执行操作 → Desactivate
```

适用于：几何分析、批量属性修改

```cpp
CATStatusChangeRC ATAutoRenameCmd::OnSelect(void *iData, CATNotification *iNotif,
                                              CATCommandClientInfo *iInfo) {
    if (!_pAgent) return CATStatusChangeError;
    
    // 获取选中的对象
    CATPathElement *pPath = _pAgent->GetPathElement();
    CATISpecObject_var spObj = NULL_var;
    HRESULT hr = pPath->FindElement(IID_CATISpecObject, (void**)&spObj);
    if (FAILED(hr)) return CATStatusChangeContinue;
    
    // 执行操作
    hr = Rename(spObj, _newName);
    if (FAILED(hr)) {
        CATError("ATCmd", "OnSelect", "Rename failed");
    }
    
    return CATStatusChangeContinue;  // 继续等待下一次选择
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

## 状态报告

```cpp
CATStatusChangeRC ATAutoRenameCmd::GetState(CATNotification *iNotif,
                                              CATCommandCompletion *iCompl) {
    CATFrmEditor *pEditor = CATFrmEditor::GetCurrentEditor();
    
    if (!pEditor) {
        iCompl->SetCompletion(CATMultiCompletion, "No active document");
        return CATStaDisable;
    }
    
    CATDocument *pDoc = pEditor->GetDocument();
    if (!pDoc) {
        iCompl->SetCompletion(CATMultiCompletion, "No document");
        return CATStaDisable;
    }
    
    // 仅在 Part 环境下激活
    CATUnicodeString docType = pDoc->GetType();
    if (docType != "CATPart") {
        iCompl->SetCompletion(CATMultiCompletion, "Only for Part documents");
        return CATStaDisable;
    }
    
    return CATStaEnable;
}
```

## AI 生成规则

- [ ] 继承 `CATStateCommand`
- [ ] 添加 `CATDeclareClass` 宏
- [ ] 实现全部 5 个生命周期方法
- [ ] 注册 Header 文件（`{Name}Header.cpp`）
- [ ] Catalog 条目写 `CATStateCommand`（非 `CATCommand`）
- [ ] Agent 使用 `CATFeatureImportAgent`（选择特征用）
- [ ] Agent 使用 `CATIndicationAgent`（点击位置用）
