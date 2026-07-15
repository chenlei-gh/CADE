//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <CommandClassName>.h
//===================================================================

#ifndef <CommandClassName>_H
#define <CommandClassName>_H

#include "CATStateCommand.h"

class <CommandClassName> : public CATStateCommand
{
public:
    <CommandClassName>();
    virtual ~<CommandClassName>();

    void BuildGraph();
    CATStatusChangeRC Activate(CATCommand *iFromClient, CATNotification *iNotif);
    CATStatusChangeRC Desactivate(CATCommand *iFromClient, CATNotification *iNotif);
    CATStatusChangeRC Cancel(CATCommand *iFromClient, CATNotification *iNotif);
};

#endif
