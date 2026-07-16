//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <ClassName>.cpp
// Workbench addin -- registers commands with CATIA toolbars
//===================================================================

#include "<ClassName>.h"
#include "CATIAfrGeneralWksAddin.h"
#include "CATCommandHeader.h"
#include "CATCreateWorkshop.h"

// Command header macro for our command
MacDeclareHeader(<CommandClassName>Hdr);

CATImplementClass(<ClassName>,DataExtension,CATBaseUnknown,<ClassName>);

#include <TIE_CATIAfrGeneralWksAddin.h>
TIE_CATIAfrGeneralWksAddin(<ClassName>);

<ClassName>::<ClassName>() : CATBaseUnknown()
{
}

<ClassName>::~<ClassName>()
{
}

void <ClassName>::CreateCommands()
{
    new <CommandClassName>Hdr(
        "<ModuleName>.<CommandClassName>",
        "<ModuleName>",
        "<CommandClassName>",
        (void*)NULL
    );
}

CATCmdContainer* <ClassName>::CreateToolbars()
{
    NewAccess(CATCmdContainer, pToolbar, <ModuleName>Tlb);
    AddToolbarView(pToolbar, <ToolbarPriority>, <ToolbarPosition>);

    NewAccess(CATCmdStarter, pCmd, <CommandClassName>);
    SetAccessCommand(pCmd, "<ModuleName>.<CommandClassName>");
    SetAccessChild(pToolbar, pCmd);

    return pToolbar;
}
