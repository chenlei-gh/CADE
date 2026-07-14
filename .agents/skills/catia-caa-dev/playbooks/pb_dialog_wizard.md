---
id: pb.dialog_wizard
title: Dialog Wizard Pattern / 对话框向导模式
category: playbook
domain: ui
keywords: [wizard, dialog, step, back, next, finish, state command, multi-step, form]
capabilities: [cap.selection, cap.parameter_system]
apis: [CATStateCommand, CATDialogState, CATDlgDialog, CATDlgFrame, CATDlgPushButton]
frameworks: [ApplicationFrame, DialogEngine, KnowledgeInterfaces]
difficulty: intermediate
effort: medium
release: [R19, R28]
tags: [playbook, dialog, wizard, state command, UI]
---

# Dialog Wizard Pattern (对话框向导模式)

实现多步骤向导对话框：Back/Next/Finish/Cancel，每个步骤独立状态，数据跨步骤传递。

## 目标

创建一个标准的 CAA 多步骤向导：步骤1选对象 → 步骤2设参数 → 步骤3预览 → Finish 执行。

## 前置条件

- 已创建 StateCommand 骨架
- 每个步骤对应一个 `CATDialogState`

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.selection` | 步骤1：用户在3D中选择对象 |
| `cap.parameter_system` | 步骤2：读取/设置参数值 |

## 实现步骤

1. **定义状态枚举**：`STEP_SELECT`, `STEP_CONFIGURE`, `STEP_PREVIEW`, `STEP_FINISH`
2. **创建 StateCommand**：`CATStateCommand` 管理状态转换
3. **实现各状态的 BuildGraph**：
   - `STEP_SELECT` → 激活选择过滤，显示"Next>"
   - `STEP_CONFIGURE` → 显示参数编辑面板，"<Back" + "Next>"
   - `STEP_PREVIEW` → 预览结果，"<Back" + "Finish"
4. **数据传递**：使用 Command 成员变量在状态间共享数据
5. **条件转换**：验证当前步骤数据后才能进入下一步

## 状态转换图

```text
[Start] → STEP_SELECT
              │ (valid selection)
              ▼
         STEP_CONFIGURE
              │ (valid params)
              ▼
         STEP_PREVIEW
              │ (Finish)
              ▼
           [Execute]
```

## 关键代码

```cpp
CATBoolean MyWizardCmd::BuildGraph() {
    CATDialogState *pState = GetCurrentState();
    
    if (pState == GetState(STEP_SELECT)) {
        // Show selection agent
        CATISelectionAgent_var spAgent = ...;
        spAgent->SetFilter(CATPartType);
        AddTransition(STEP_CONFIGURE, IsSelectionValid, 
                      new CATDlgPushButton("Next>"));
    }
    else if (pState == GetState(STEP_CONFIGURE)) {
        // Show parameter dialog
        BuildParameterPanel(pState);
        AddTransition(STEP_SELECT, AlwaysTrue, 
                      new CATDlgPushButton("<Back"));
        AddTransition(STEP_PREVIEW, AreParamsValid, 
                      new CATDlgPushButton("Next>"));
    }
    else if (pState == GetState(STEP_PREVIEW)) {
        ShowPreview(pState);
        AddTransition(STEP_CONFIGURE, AlwaysTrue, 
                      new CATDlgPushButton("<Back"));
        AddTransition(STEP_FINISH, AlwaysTrue, 
                      new CATDlgPushButton("Finish"));
    }
    return TRUE;
}
```

## 注意事项

- 每个状态独立管理 `CATDlgDialog` 内容，避免状态间 UI 残留
- 状态数据通过 Command 成员变量传递，不要使用全局变量
- Back 返回时保留上一步的用户输入（缓存而非重置）
- Cancel 在所有步骤都应可用
- Finish 执行后调用 `CATIModelEvents::Dispatch()` 触发 Update

## 相关 Playbook

- `pb.create_context_menu` — Wizard 第一步可通过右键菜单触发
