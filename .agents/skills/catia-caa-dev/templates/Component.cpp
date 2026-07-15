// COPYRIGHT DASSAULT SYSTEMES YYYY

// Local Framework
#include "ComponentName.h"

// C++ standard library
#include <iostream>
using namespace std;

//-----------------------------------------------------------------------------

// To declare that the class is a component main class
CATImplementClass(ComponentName, DataExtension, CATBaseUnknown, CATNull);

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
// Execute - Implementation
//-----------------------------------------------------------------------------
HRESULT ComponentName::Execute(const CATUnicodeString& iParam, CATUnicodeString& oResult)
{
    cout << "ComponentName::Execute" << endl;
    oResult = "ComponentName executed";
    return S_OK;
}
