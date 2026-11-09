//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <CommandClassName>.h
// [CADE] 遵循 Dassault 官方 DialogEngine / CATStateCommand 规范架构
//===================================================================

#ifndef <CommandClassName>_H
#define <CommandClassName>_H

#include "CATStateCommand.h"
#include "CATBoolean.h"

class CATPathElementAgent;
class CATDialogAgent;
class <DialogClassName>;
class CATCommandGlobalUndo;

class <CommandClassName> : public CATStateCommand
{
    CATDeclareClass;

public:
    <CommandClassName>();
    virtual ~<CommandClassName>();

    // 状态机图构建
    virtual void BuildGraph();

    // 状态生命周期管理（挂起与恢复）
    virtual CATStatusChangeRC Activate(CATCommand *iFromClient, CATNotification *iNotif);
    virtual CATStatusChangeRC Desactivate(CATCommand *iFromClient, CATNotification *iNotif);
    virtual CATStatusChangeRC Cancel(CATCommand *iFromClient, CATNotification *iNotif);

    // 官方标准状态机动作响应
    CATBoolean OnOkAction(void *iData);
    CATBoolean OnApplyAction(void *iData);
    CATBoolean OnElementSelected(void *iData);

    // 官方标准命令级 Undo/Redo 支持（如不需要全局事务可返回 NULL）
    virtual CATCommandGlobalUndo *GetGlobalUndo();

private:
    // 对话框与代理（生命周期由命令统一管理）
    <DialogClassName>   *_pDialog;
    CATPathElementAgent *_pSelAgent;
};

#endif
