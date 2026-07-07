// COPYRIGHT DASSAULT SYSTEMES YYYY

#include "ObjectModelerName.h"

// C++ standard library
#include <iostream>
using namespace std;

//-----------------------------------------------------------------------------
// Component registration
// For Features: CATImplementClass(ObjectModelerName, Implementation, CATFeature, CATNull);
// For Spec Objects: use CATSpecObject as parent
//-----------------------------------------------------------------------------
CATImplementClass(ObjectModelerName, Implementation, CATBaseUnknown, CATNull);

//-----------------------------------------------------------------------------
// Constructor
//-----------------------------------------------------------------------------
ObjectModelerName::ObjectModelerName()
    : _data(0)
    , _isInitialized(FALSE)
    , _isDirty(TRUE)
{
    cout << "ObjectModelerName::ObjectModelerName" << endl;
}

//-----------------------------------------------------------------------------
// Destructor
//-----------------------------------------------------------------------------
ObjectModelerName::~ObjectModelerName()
{
    cout << "ObjectModelerName::~ObjectModelerName" << endl;
}

//-----------------------------------------------------------------------------
// Initialize
//-----------------------------------------------------------------------------
void ObjectModelerName::Initialize()
{
    cout << "ObjectModelerName::Initialize" << endl;
    
    if (_isInitialized) return;
    
    // Set up initial data
    _data = Type();
    _isInitialized = TRUE;
    _isDirty = TRUE;
}

//-----------------------------------------------------------------------------
// Terminate
//-----------------------------------------------------------------------------
void ObjectModelerName::Terminate()
{
    cout << "ObjectModelerName::Terminate" << endl;
    
    _isInitialized = FALSE;
}

//-----------------------------------------------------------------------------
// GetData
//-----------------------------------------------------------------------------
HRESULT ObjectModelerName::GetData(Type& oData)
{
    cout << "ObjectModelerName::GetData" << endl;
    
    if (!_isInitialized) return E_FAIL;
    
    oData = _data;
    return S_OK;
}

//-----------------------------------------------------------------------------
// SetData
//-----------------------------------------------------------------------------
HRESULT ObjectModelerName::SetData(const Type iData)
{
    cout << "ObjectModelerName::SetData" << endl;
    
    _data = iData;
    _isDirty = TRUE;
    
    return S_OK;
}

//-----------------------------------------------------------------------------
// Compute
//-----------------------------------------------------------------------------
void ObjectModelerName::Compute()
{
    cout << "ObjectModelerName::Compute" << endl;
    
    if (!_isDirty) return;
    
    // Perform computation based on current data
    // ...
    
    _isDirty = FALSE;
}

//-----------------------------------------------------------------------------
// Clone
//-----------------------------------------------------------------------------
ObjectModelerName* ObjectModelerName::Clone()
{
    cout << "ObjectModelerName::Clone" << endl;
    
    ObjectModelerName* pClone = new ObjectModelerName();
    pClone->_data = this->_data;
    pClone->_isInitialized = TRUE;
    pClone->_isDirty = TRUE;
    
    return pClone;
}
