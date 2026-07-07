// COPYRIGHT DASSAULT SYSTEMES YYYY

#include "AdapterName.h"
#include <iostream>
using namespace std;

AdapterName::AdapterName(CATBaseUnknown* iAdaptedObject)
    : _pAdaptedObject(NULL)
{
    cout << "AdapterName::AdapterName" << endl;
    if (iAdaptedObject)
    {
        _pAdaptedObject = iAdaptedObject;
        _pAdaptedObject->AddRef();
    }
}

AdapterName::~AdapterName()
{
    cout << "AdapterName::~AdapterName" << endl;
    if (_pAdaptedObject) { _pAdaptedObject->Release(); _pAdaptedObject = NULL; }
}

HRESULT AdapterName::AdaptedMethod(const Type iParam, Type& oParam)
{
    cout << "AdapterName::AdaptedMethod" << endl;
    if (!_pAdaptedObject) return E_FAIL;
    // Delegate to adapted object
    return S_OK;
}
