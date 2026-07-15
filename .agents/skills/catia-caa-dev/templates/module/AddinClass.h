//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <ModuleName>.h
// Workbench addin for framework <FrameworkName>
//===================================================================

#ifndef <ModuleName>_H
#define <ModuleName>_H

#include "CATBaseUnknown.h"
#include "CATCmdContainer.h"

class <ModuleName> : public CATBaseUnknown
{
    CATDeclareClass;

public:
    <ModuleName>();
    virtual ~<ModuleName>();

    void CreateCommands();
    CATCmdContainer* CreateToolbars();

private:
    <ModuleName>(<ModuleName> &);
    <ModuleName>& operator=(<ModuleName>&);
};

#endif
