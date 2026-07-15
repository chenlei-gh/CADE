// COPYRIGHT DASSAULT SYSTEMES YYYY

// Interface header
#include "IInterfaceName.h"

// C++ standard library
#include <iostream>
using namespace std;

// Define the Interface IID
// In production, use guidgen.exe to generate unique GUID
IID IID_IInterfaceName = { 
    0x12345678, 0x1234, 0x1234, 
    { 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0 } 
};

// Implement the interface meta-object
// Provides MetaObject() -- required for linking
CATImplementInterface(IInterfaceName, CATBaseUnknown);
