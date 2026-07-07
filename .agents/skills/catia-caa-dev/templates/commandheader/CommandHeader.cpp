// COPYRIGHT DASSAULT SYSTEMES YYYY

#include "CommandHeaderName.h"
#include "CommandClassName.h"

// C++ standard library
#include <iostream>
using namespace std;

//-----------------------------------------------------------------------------
// Constructor
//-----------------------------------------------------------------------------
CommandHeaderName::CommandHeaderName(const CATString& iHeaderName)
    : CATCommandHeader(iHeaderName)
    , _headerName(iHeaderName)
    , _commandName("CommandClassName")
    , _iconPath("Icons/CommandClassName.bmp")
{
    cout << "CommandHeaderName::CommandHeaderName" << endl;
}

//-----------------------------------------------------------------------------
// Destructor
//-----------------------------------------------------------------------------
CommandHeaderName::~CommandHeaderName()
{
    cout << "CommandHeaderName::~CommandHeaderName" << endl;
}

//-----------------------------------------------------------------------------
// CreateCommand - Factory method
// Called when user clicks the command button/menu item
//-----------------------------------------------------------------------------
CATCommand* CommandHeaderName::CreateCommand()
{
    cout << "CommandHeaderName::CreateCommand" << endl;
    
    // Create and return a new instance of the command
    return new CommandClassName();
}

//-----------------------------------------------------------------------------
// GetCommandName - Display name for menus/toolbars
//-----------------------------------------------------------------------------
CATString CommandHeaderName::GetCommandName()
{
    return _commandName;
}

//-----------------------------------------------------------------------------
// GetCommandIcon - Path to icon resource
//-----------------------------------------------------------------------------
CATString CommandHeaderName::GetCommandIcon()
{
    return _iconPath;
}

//-----------------------------------------------------------------------------
// IsCommandEnabled - Check if command should be available
//-----------------------------------------------------------------------------
CATBoolean CommandHeaderName::IsCommandEnabled()
{
    // Always available by default
    // Override with context-sensitive logic if needed
    return TRUE;
}
