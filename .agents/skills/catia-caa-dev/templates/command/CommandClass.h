//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <CommandClassName>.h
//===================================================================

#ifndef <CommandClassName>_H
#define <CommandClassName>_H

#include "CATStateCommand.h"

class CATPathElementAgent;
class CATDialogAgent;
class CATIndicationAgent;

class <CommandClassName> : public CATStateCommand
{
public:
    <CommandClassName>();
    virtual ~<CommandClassName>();

    void BuildGraph();
    CATStatusChangeRC Activate(CATCommand *iFromClient, CATNotification *iNotif);
    CATStatusChangeRC Desactivate(CATCommand *iFromClient, CATNotification *iNotif);
    CATStatusChangeRC Cancel(CATCommand *iFromClient, CATNotification *iNotif);

    // Undo/Redo support
    void Undo();
    void Redo();

private:
    // Agents (created in BuildGraph)
    CATPathElementAgent *_pSelAgent;
    CATDialogAgent      *_pDlgAgent;
    CATIndicationAgent  *_pIndAgent;

    // Undo/Redo state
    CATCommandGlobalUndo *_pGlobalUndo;
};

#endif
