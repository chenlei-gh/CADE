// COPYRIGHT DASSAULT SYSTEMES YYYY

#include "UserExitName.h"
#include <iostream>
using namespace std;

CATImplementClass(UserExitName, Implementation, CATBaseUnknown, CATNull);

UserExitName::UserExitName()
    : _priority(100)
    , _exitPoint("StandardExit")
{
    cout << "UserExitName::UserExitName" << endl;
}

UserExitName::~UserExitName()
{
    cout << "UserExitName::~UserExitName" << endl;
}

HRESULT UserExitName::Execute(void* iContext)
{
    cout << "UserExitName::Execute" << endl;
    // Custom processing at exit point
    return S_OK;
}

int UserExitName::GetPriority()
{
    return _priority;
}

CATString UserExitName::GetExitPoint()
{
    return _exitPoint;
}
