// COPYRIGHT DASSAULT SYSTEMES YYYY

// Local Framework
#include "ComponentName.h"

// C++ standard library
#include "iostream.h"

//-----------------------------------------------------------------------------

// To declare that the class is a component main class
CATImplementClass(ComponentName, Implementation, CATBaseUnknown, CATNull);

// Bind the interface using BOA (Basic Object Adapter)
CATImplementBOA(IInterfaceName, ComponentName);

//-----------------------------------------------------------------------------
// Constructor
//-----------------------------------------------------------------------------
ComponentName::ComponentName()
{
    cout << "ComponentName::ComponentName" << endl;
}

//-----------------------------------------------------------------------------
// Destructor
//-----------------------------------------------------------------------------
ComponentName::~ComponentName()
{
    cout << "ComponentName::~ComponentName" << endl;
}

//-----------------------------------------------------------------------------
// MethodName - Implementation
//-----------------------------------------------------------------------------
HRESULT ComponentName::MethodName(const Type iParam, Type& oParam)
{
    // Implementation here
    cout << "ComponentName::MethodName" << endl;
    
    return S_OK;
}
