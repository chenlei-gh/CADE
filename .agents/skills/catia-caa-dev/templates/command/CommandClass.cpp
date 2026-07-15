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
{
}

<CommandClassName>::~<CommandClassName>()
{
}

void <CommandClassName>::BuildGraph()
{
    // TODO: Add dialog states and transitions here
}

CATStatusChangeRC <CommandClassName>::Activate(CATCommand *iFromClient, CATNotification *iNotif)
{
    return CATStatusChangeRCCompleted;
}

CATStatusChangeRC <CommandClassName>::Desactivate(CATCommand *iFromClient, CATNotification *iNotif)
{
    return CATStatusChangeRCCompleted;
}

CATStatusChangeRC <CommandClassName>::Cancel(CATCommand *iFromClient, CATNotification *iNotif)
{
    return CATStatusChangeRCCompleted;
}
