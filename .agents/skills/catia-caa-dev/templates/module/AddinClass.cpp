//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <ModuleName>Addin.cpp
// Workbench addin — registers commands with CATIA toolbars
//===================================================================

#include "<ModuleName>Addin.h"
#include "CATIAfrGeneralWksAddin.h"
#include "CATCommandHeader.h"
#include "CATCreateWorkshop.h"

// Command header macro for our command
MacDeclareHeader(<CommandClassName>Hdr);

CATImplementClass(<ModuleName>Addin, Implementation, CATBaseUnknown, CATNull);

#include "TIE_CATIAfrGeneralWksAddin.h"
TIE_CATIAfrGeneralWksAddin(<ModuleName>Addin);

<ModuleName>Addin::<ModuleName>Addin() : CATBaseUnknown()
{
}

<ModuleName>Addin::~<ModuleName>Addin()
{
}

void <ModuleName>Addin::CreateCommands()
{
    new <CommandClassName>Hdr(
        "<ModuleName>.<CommandClassName>",
        "<ModuleName>",
        "<CommandClassName>",
        (void*)NULL
    );
}

CATCmdContainer* <ModuleName>Addin::CreateToolbars()
{
    NewAccess(CATCmdContainer, pToolbar, <ModuleName>Tlb);
    AddToolbarView(pToolbar, 1, Right);

    NewAccess(CATCmdStarter, pCmd, <CommandClassName>);
    SetAccessCommand(pCmd, "<ModuleName>.<CommandClassName>");
    SetAccessChild(pToolbar, pCmd);

    return pToolbar;
}
