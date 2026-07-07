// COPYRIGHT DASSAULT SYSTEMES YYYY

#include "PluginName.h"
#include <iostream>
using namespace std;

CATImplementClass(PluginName, Implementation, CATBaseUnknown, CATNull);

PluginName::PluginName()
    : _isInitialized(FALSE)
{
    cout << "PluginName::PluginName" << endl;
}

PluginName::~PluginName()
{
    Uninit();
    cout << "PluginName::~PluginName" << endl;
}

HRESULT PluginName::Init()
{
    cout << "PluginName::Init" << endl;
    _isInitialized = TRUE;
    return S_OK;
}

HRESULT PluginName::Run()
{
    cout << "PluginName::Run" << endl;
    if (!_isInitialized) return E_FAIL;
    return S_OK;
}

HRESULT PluginName::Uninit()
{
    cout << "PluginName::Uninit" << endl;
    _isInitialized = FALSE;
    return S_OK;
}

CATString PluginName::GetPluginInfo()
{
    return "PluginName v1.0";
}
