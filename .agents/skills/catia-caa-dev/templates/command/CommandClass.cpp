//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <CommandClassName>.cpp
//===================================================================

#include "<CommandClassName>.h"
#include "CATCommandGlobalUndo.h"
#include "CATCreateExternalObject.h"

CATCreateClass(<CommandClassName>);

<CommandClassName>::<CommandClassName>()
    : CATStateCommand("<CommandClassName>")
    , _pSelAgent(NULL)
    , _pDlgAgent(NULL)
    , _pIndAgent(NULL)
    , _pGlobalUndo(NULL)
{
}

<CommandClassName>::~<CommandClassName>()
{
}

void <CommandClassName>::BuildGraph()
{
    // Step 1: Create dialog state (if dialog class is included)
    //   CATDialogState *pDlgState = AddDialogState("DlgStateId");
    //   CATDialogAgent *pDlgAgent = new CATDialogAgent("DlgAgentId");
    //   pDlgState->AddDialogAgent(pDlgAgent);

    // Step 2: Create selection state (if picking elements)
    //   CATDialogState *pSelState = AddDialogState("SelStateId");
    //   _pSelAgent = new CATPathElementAgent("SelAgentId");
    //   _pSelAgent->AddElementType("CATPoint");  // filter by type
    //   pSelState->AddDialogAgent(_pSelAgent);

    // Step 3: Create indication state (if clicking in 3D view)
    //   CATDialogState *pIndState = AddDialogState("IndStateId");
    //   _pIndAgent = new CATIndicationAgent("IndAgentId");
    //   pIndState->AddDialogAgent(_pIndAgent);

    // Step 4: Create transitions
    //   CATDialogTransition *pT1 = AddTransition(GetInitialState(), pSelState);
    //   pT1->AddCondition(new CATStateCondition("Selected"));
    //   AddTransition(pSelState, NULL,
    //       new CATStateCondition("OkCondition"),
    //       new CATDiaAction("OkAction"));

    // Step 5: Context menu (right-click)
    //   CATCmdContainer *pMenu = new CATCmdContainer("ContextMenuId");
    //   new CATCommandHeader("MenuCmdHdr","Module","CmdClass",(void*)NULL);
    //   SetAccessCommand(pMenu, "MenuCmdHdr");

    // Step 6: Undo/Redo initialization
    //   _pGlobalUndo = GetGlobalUndo();
    //   if (_pGlobalUndo) _pGlobalUndo->Begin();
}

CATStatusChangeRC <CommandClassName>::Activate(CATCommand *iFromClient, CATNotification *iNotif)
{
    // Initialize resources, set up UI, register listeners
    return CATStatusChangeRCCompleted;
}

CATStatusChangeRC <CommandClassName>::Desactivate(CATCommand *iFromClient, CATNotification *iNotif)
{
    // Clean up resources, remove listeners
    return CATStatusChangeRCCompleted;
}

CATStatusChangeRC <CommandClassName>::Cancel(CATCommand *iFromClient, CATNotification *iNotif)
{
    // Rollback any partial changes
    return CATStatusChangeRCCompleted;
}

void <CommandClassName>::Undo()
{
    // Reverse the last operation using stored undo data
    if (_pGlobalUndo)
        _pGlobalUndo->Undo();
}

void <CommandClassName>::Redo()
{
    // Re-apply the last undone operation
    if (_pGlobalUndo)
        _pGlobalUndo->Redo();
}
