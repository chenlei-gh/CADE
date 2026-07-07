// COPYRIGHT DASSAULT SYSTEMES YYYY

#include "AddinName.h"

// System Framework
#include "CATCommandHeader.h"

// C++ standard library
#include <iostream>
using namespace std;

//-----------------------------------------------------------------------------
// Component declaration
//-----------------------------------------------------------------------------
CATImplementClass(AddinName, Implementation, CATBaseUnknown, CATNull);

//-----------------------------------------------------------------------------
// Constructor
//-----------------------------------------------------------------------------
AddinName::AddinName()
    : _pWorkbench(NULL)
{
    cout << "AddinName::AddinName" << endl;
}

//-----------------------------------------------------------------------------
// Destructor
//-----------------------------------------------------------------------------
AddinName::~AddinName()
{
    cout << "AddinName::~AddinName" << endl;
    
    if (_pWorkbench != NULL)
    {
        _pWorkbench->Release();
        _pWorkbench = NULL;
    }
}

//-----------------------------------------------------------------------------
// CreateCommands - Register commands with the workbench
//-----------------------------------------------------------------------------
void AddinName::CreateCommands()
{
    cout << "AddinName::CreateCommands" << endl;
    
    // Example: Register command headers
    // new CommandHeader1("Command1", "ModuleName");
    // new CommandHeader2("Command2", "ModuleName");
    
    // Commands are registered via macro in command header file
    // No manual registration needed if using macros
}

//-----------------------------------------------------------------------------
// CreateToolbars - Create toolbar configurations
//-----------------------------------------------------------------------------
void AddinName::CreateToolbars()
{
    cout << "AddinName::CreateToolbars" << endl;
    
    // Example: Create a new toolbar
    // CATCommandHeader* pHeader = new CommandHeader("ToolbarName");
    // 
    // Add buttons to toolbar:
    // pHeader->AddCommand("CommandName1");
    // pHeader->AddCommand("CommandName2");
    // pHeader->AddSeparator();
    // pHeader->AddCommand("CommandName3");
}
