#ifndef ComponentName_H
#define ComponentName_H

// COPYRIGHT DASSAULT SYSTEMES YYYY

// System Framework
#include "CATBaseUnknown.h"
#include "CATUnicodeString.h"

// Local Framework
#include "IInterfaceName.h"

/**
 * @brief Component implementation class
 */
class ComponentName : public CATBaseUnknown
{
    // Used in conjunction with CATImplementClass in the .cpp file
    CATDeclareClass;

public:
    ComponentName();
    virtual ~ComponentName();

    // IInterfaceName implementation
    virtual HRESULT Execute(const CATUnicodeString& iParam, CATUnicodeString& oResult);

private:
    // Private data members
    
    // Copy constructor, not implemented
    // Set as private to prevent from compiler automatic creation as public.
    ComponentName(const ComponentName &iObjectToCopy);

    // Assignment operator, not implemented
    // Set as private to prevent from compiler automatic creation as public.
    ComponentName & operator = (const ComponentName &iObjectToCopy);
};

#endif
