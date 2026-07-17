//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <ClassName>.cpp
// Workbench addin -- registers commands with CATIA toolbars
//===================================================================

#include "<ClassName>.h"
#include "CATIAfrGeneralWksAddin.h"
#include "CATCreateWorkshop.h"

// ⭐ CommandHeader — MacDeclareHeader in .cpp (not .h!) to avoid linker errors
#include "CATCommandHeader.h"
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
