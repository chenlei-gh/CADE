// COPYRIGHT DASSAULT SYSTEMES {{YEAR}}
//===================================================================
// {{PREFIX}}Workbench.cpp
// Workbench implementation
//===================================================================
#include "{{PREFIX}}Workbench.h"

// Application Frame
#include "CATCommandHeader.h"
#include "CATCmdContainer.h"
#include "CATCmdStarter.h"

// Include your command headers here
// Example:
// #include "{{PREFIX}}SampleCmd.h"

//-----------------------------------------------------------------------
// Constructor
//-----------------------------------------------------------------------
{{PREFIX}}Workbench::{{PREFIX}}Workbench(const CATString& iWorkbenchName)
    : CATCmdWorkbench(iWorkbenchName)
{
    // Constructor - workbench name is set in base class
}

//-----------------------------------------------------------------------
// Destructor
//-----------------------------------------------------------------------
{{PREFIX}}Workbench::~{{PREFIX}}Workbench()
{
    // Destructor - framework handles command cleanup
}

//-----------------------------------------------------------------------
// CreateCommands - Register all workbench commands
//-----------------------------------------------------------------------
void {{PREFIX}}Workbench::CreateCommands()
{
    // Register each command with a unique header identifier
    // Pattern: new CATCommandHeader(HeaderID, ClassName, MethodName, Options)
    
    // Example command registration:
    // new CATCommandHeader("{{PREFIX}}SampleHdr",           // Header ID (used in .CATRsc)
    //                      "{{PREFIX}}SampleCmd",           // Command class name
    //                      "{{PREFIX}}SampleCmd",           // Constructor name
    //                      (void*)NULL,                     // Argument to constructor
    //                      "{{PREFIX}}Workbench",           // Resource file prefix
    //                      CATCommandHeaderTypeExclusive);  // Command mode
    
    // Command Header Types:
    // - CATCommandHeaderTypeExclusive: Only one active at a time (default)
    // - CATCommandHeaderTypeShared: Can coexist with others
    // - CATCommandHeaderTypeCheckButton: Toggle on/off
    
    // TODO: Add your command registrations here
}

//-----------------------------------------------------------------------
// CreateToolbars - Create toolbar containers and layouts
//-----------------------------------------------------------------------
CATCmdContainer* {{PREFIX}}Workbench::CreateToolbars()
{
    // Create toolbar starter (container manager)
    CATCmdContainer* pToolbarStarter = NULL;
    NewAccess(CATCmdContainer, pToolbarStarter, {{PREFIX}}TlbStarter);
    
    if (pToolbarStarter)
    {
        // Create main toolbar
        CATCmdContainer* pMainToolbar = NULL;
        NewAccess(CATCmdContainer, pMainToolbar, {{PREFIX}}MainTlb);
        
        if (pMainToolbar)
        {
            // Set toolbar as visible
            SetAccessChild({{PREFIX}}TlbStarter, {{PREFIX}}MainTlb);
            
            // Add command starters to toolbar
            // Pattern: SetAccessCommand(ParentID, CommandID)
            
            // Example: Add commands to toolbar
            // SetAccessNext("{{PREFIX}}SampleHdr");
            // SetAccessCommand("{{PREFIX}}MainTlb", "{{PREFIX}}SampleHdr");
            
            // Add separator (optional)
            // SetAccessNext("Separator");
            
            // TODO: Add your toolbar commands here
        }
        
        // Create additional toolbars if needed
        // Example:
        // CATCmdContainer* pSecondToolbar = NULL;
        // NewAccess(CATCmdContainer, pSecondToolbar, {{PREFIX}}SecondTlb);
        // if (pSecondToolbar)
        // {
        //     SetAccessChild({{PREFIX}}TlbStarter, {{PREFIX}}SecondTlb);
        //     // Add commands...
        // }
    }
    
    return pToolbarStarter;
}

//-----------------------------------------------------------------------
// CreateMenus - Create menu bar items (optional)
//-----------------------------------------------------------------------
CATCmdContainer* {{PREFIX}}Workbench::CreateMenus()
{
    // Create menu starter if custom menus are needed
    // Most workbenches use toolbars only
    
    // Example menu creation:
    // CATCmdContainer* pMenuStarter = NULL;
    // NewAccess(CATCmdContainer, pMenuStarter, {{PREFIX}}MenuStarter);
    // 
    // if (pMenuStarter)
    // {
    //     CATCmdContainer* pMainMenu = NULL;
    //     NewAccess(CATCmdContainer, pMainMenu, {{PREFIX}}MainMenu);
    //     
    //     if (pMainMenu)
    //     {
    //         SetAccessChild({{PREFIX}}MenuStarter, {{PREFIX}}MainMenu);
    //         SetAccessCommand("{{PREFIX}}MainMenu", "{{PREFIX}}SampleHdr");
    //     }
    // }
    // 
    // return pMenuStarter;
    
    return NULL; // No custom menus by default
}
