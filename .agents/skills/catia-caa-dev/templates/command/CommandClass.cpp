//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <CommandClassName>.cpp
//===================================================================

#include "<CommandClassName>.h"
#include "CATCreateExternalObject.h"

CATCreateClass(<CommandClassName>);

<CommandClassName>::<CommandClassName>()
    : CATStateCommand("<CommandClassName>")
    , _pSelAgent(NULL)
    , _pDlgAgent(NULL)
    , _pIndAgent(NULL)
{
}

<CommandClassName>::~<CommandClassName>()
{
}

void <CommandClassName>::BuildGraph()
{
    // Step 1: Create dialog state (if dialog class is included)
    //   CATDialogState *pDlgState = AddDialogState("DlgStateId");
    //   pDlgState->AddDialogAgent(new CATDialogAgent("DlgAgentId"));

    // Step 2: Create selection state (if picking elements)
    //   CATDialogState *pSelState = AddDialogState("SelStateId");
    //   pSelState->AddDialogAgent(new CATPathElementAgent("SelAgentId"));

    // Step 3: Create transitions
    //   AddTransition(GetInitialState(), pSelState);
    //   AddTransition(pSelState, NULL,
    //       new CATStateCondition("OkCondition"),
    //       new CATDiaAction("OkAction"));
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
