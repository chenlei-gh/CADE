//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <CommandClassName>.cpp
// [CADE] 遵循 Dassault 官方 DialogEngine / CATStateCommand 规范架构
//===================================================================

#include "<CommandClassName>.h"
#include "<DialogClassName>.h"

#include "CATPanelState.h"
#include "CATPathElementAgent.h"
#include "CATApplicationFrame.h"
#include "CATCommandGlobalUndo.h"
#include "CATCreateExternalObject.h"

// 官方对象模型宏绑定
CATCreateClass(<CommandClassName>);
CATImplementClass(<CommandClassName>, Implementation, CATStateCommand, CATNull);

<CommandClassName>::<CommandClassName>()
    : CATStateCommand("<CommandClassName>")
    , _pDialog(NULL)
    , _pSelAgent(NULL)
{
}

<CommandClassName>::~<CommandClassName>()
{
    // 官方生命周期铁律：严禁 delete，必须调用 RequestDelayedDestruction 并置空
    if (_pSelAgent)
    {
        _pSelAgent->RequestDelayedDestruction();
        _pSelAgent = NULL;
    }
    if (_pDialog)
    {
        _pDialog->RequestDelayedDestruction();
        _pDialog = NULL;
    }
}

void <CommandClassName>::BuildGraph()
{
    // 1. 获取主框架顶层窗口作为 Dialog 父容器（带无头/批处理空指针防护）
    CATDialog *pParent = NULL;
    CATApplicationFrame *pFrame = CATApplicationFrame::GetFrame();
    if (pFrame)
    {
        pParent = pFrame->GetMainWindow();
    }

    // 2. 官方标准两阶段构造（Two-Phase Construction）：
    //    构造函数内不创建子控件，在 Build() 中完成控件树分配与 NLS 绑定
    _pDialog = new <DialogClassName>(pParent);
    if (_pDialog)
    {
        _pDialog->Build();
    }

    // 3. 官方标准 CATPanelState：自动管理 Dialog 的 OK、Cancel、Apply、Preview 状态转换
    CATPanelState *pPanelState = new CATPanelState(this, "PanelStateId", _pDialog);
    SetInitialState(pPanelState);

    // 4. 官方标准 3D 选择代理（CATPathElementAgent）：
    //    配置 CATDlgEngRepeat 支持连续拾取，添加显式类型过滤器
    _pSelAgent = new CATPathElementAgent("SelAgentId");
    if (_pSelAgent)
    {
        _pSelAgent->SetBehavior(CATDlgEngRepeat);
        _pSelAgent->AddElementType("CATISpecObject"); // 按需配置过滤类型，如 CATFace/CATLine
        pPanelState->AddDialogAgent(_pSelAgent);
    }

    // 5. 绑定 PanelState 的原生按钮动作
    if (pPanelState->GetOkTransition())
    {
        pPanelState->GetOkTransition()->SetAction(Action((ActionMethod)&<CommandClassName>::OnOkAction));
    }
    if (pPanelState->GetApplyTransition())
    {
        pPanelState->GetApplyTransition()->SetAction(Action((ActionMethod)&<CommandClassName>::OnApplyAction));
    }

    // 6. 绑定 3D 拾取转换 (Self Transition)
    if (_pSelAgent)
    {
        AddTransition(
            pPanelState,
            pPanelState,
            IsLastModifiedAgentCondition(_pSelAgent),
            Action((ActionMethod)&<CommandClassName>::OnElementSelected));
    }

    // 显式释放状态句柄（由 Command 树接管引用）
    pPanelState->Release();
    pPanelState = NULL;
}

CATStatusChangeRC <CommandClassName>::Activate(CATCommand *iFromClient, CATNotification *iNotif)
{
    // 命令获得焦点：仅在拥有有效主框架的交互环境下显示对话框（双模隔离：防止无头/批处理脚本阻断）
    if (_pDialog && CATApplicationFrame::GetFrame())
    {
        _pDialog->SetVisibility(CATDlgShow);
    }
    return CATStatusChangeRCCompleted;
}

CATStatusChangeRC <CommandClassName>::Desactivate(CATCommand *iFromClient, CATNotification *iNotif)
{
    // 命令挂起（用户切到其他互斥命令）：隐藏对话框，避免界面悬挂被误操作
    if (_pDialog)
    {
        _pDialog->SetVisibility(CATDlgHide);
    }
    return CATStatusChangeRCCompleted;
}

CATStatusChangeRC <CommandClassName>::Cancel(CATCommand *iFromClient, CATNotification *iNotif)
{
    // 命令退出或被 ESC 中断：隐藏并请求销毁
    if (_pDialog)
    {
        _pDialog->SetVisibility(CATDlgHide);
        _pDialog->RequestDelayedDestruction();
        _pDialog = NULL;
    }
    return CATStatusChangeRCCompleted;
}

CATBoolean <CommandClassName>::OnOkAction(void *iData)
{
    // 处理 OK 事件：执行核心业务计算并结束命令
    return TRUE;
}

CATBoolean <CommandClassName>::OnApplyAction(void *iData)
{
    // 处理 Apply / Preview 事件：更新计算但保持命令驻留
    return TRUE;
}

CATBoolean <CommandClassName>::OnElementSelected(void *iData)
{
    // 处理 3D 选择事件：从 _pSelAgent 提取选中的路径元素
    if (!_pSelAgent) return FALSE;

    CATPathElement *pPath = _pSelAgent->GetValue();
    if (!pPath) return FALSE;

    // 解析选中对象并同步更新对话框界面显示
    return TRUE;
}

CATCommandGlobalUndo *<CommandClassName>::GetGlobalUndo()
{
    // 命令级全局撤销事务。若无需自定义事务，返回 NULL 走默认处理
    return NULL;
}
