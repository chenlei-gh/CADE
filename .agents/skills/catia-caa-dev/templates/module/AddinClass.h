//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <ClassName>.h
// Workbench addin for framework <FrameworkName>
//===================================================================

#ifndef <ClassName>_H
#define <ClassName>_H

#include "CATBaseUnknown.h"
#include "CATCmdContainer.h"

class <ClassName> : public CATBaseUnknown
{
    CATDeclareClass;

public:
    <ClassName>();
    virtual ~<ClassName>();

    void CreateCommands();
    CATCmdContainer* CreateToolbars();

private:
    <ClassName>(<ClassName> &);
    <ClassName>& operator=(<ClassName>&);
};

#endif
