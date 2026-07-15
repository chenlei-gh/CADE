// COPYRIGHT DASSAULT SYSTEMES YYYY

#include "WorkshopAddinName.h"

// C++ standard library
#include <iostream>
using namespace std;

CATImplementClass(WorkshopAddinName, DataExtension, CATBaseUnknown, CATNull);

WorkshopAddinName::WorkshopAddinName()
    : _pWorkshop(NULL)
{
    cout << "WorkshopAddinName::WorkshopAddinName" << endl;
}

WorkshopAddinName::~WorkshopAddinName()
{
    cout << "WorkshopAddinName::~WorkshopAddinName" << endl;
    if (_pWorkshop) { _pWorkshop->Release(); _pWorkshop = NULL; }
}

HRESULT WorkshopAddinName::InitWorkshop(CATIWorkshop* iWorkshop)
{
    cout << "WorkshopAddinName::InitWorkshop" << endl;
    _pWorkshop = iWorkshop;
    if (_pWorkshop) _pWorkshop->AddRef();
    
    AddWorkshopPages();
    RegisterDocumentTypes();
    
    return S_OK;
}

void WorkshopAddinName::AddWorkshopPages()
{
    cout << "WorkshopAddinName::AddWorkshopPages" << endl;
    // Add custom pages to workshop
}

void WorkshopAddinName::RegisterDocumentTypes()
{
    cout << "WorkshopAddinName::RegisterDocumentTypes" << endl;
    // Register custom document types
}
