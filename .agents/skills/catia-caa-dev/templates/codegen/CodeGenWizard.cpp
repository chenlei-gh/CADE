// COPYRIGHT DASSAULT SYSTEMES YYYY
// Code Generation Wizard - Auto-generate interface implementations
//
// Purpose:
//   Automatically generates boilerplate CAA code for interface implementations.
//
// Common use cases:
//   - Generate TIE objects for multi-interface components
//   - Generate QueryInterface switch statements
//   - Generate BOA binding code
//   - Generate extension class skeletons
//
// Generated code template:

#include "IInterfaceName.h"
#include "CATBaseUnknown.h"

// --- Auto-generated TIE object ---
#ifndef TIE_IInterfaceName
#define TIE_IInterfaceName

#include "TIE_IInterfaceName.h"
TIE_IInterfaceName(ComponentName);

#endif // TIE_IInterfaceName

// --- Auto-generated QueryInterface ---
#ifndef QUERYINTERFACE_ComponentName
#define QUERYINTERFACE_ComponentName

#if defined(__ComponentName)
CATImplementClass(ComponentName, Implementation, CATBaseUnknown, CATNull);

HRESULT __stdcall ComponentName::QueryInterface(const IID& iid, void** ppv)
{
    if (iid == IID_IInterfaceName)
    {
        *ppv = static_cast<IInterfaceName*>(this);
        AddRef();
        return S_OK;
    }
    return CATBaseUnknown::QueryInterface(iid, ppv);
}
#endif // __ComponentName

#endif // QUERYINTERFACE_ComponentName
