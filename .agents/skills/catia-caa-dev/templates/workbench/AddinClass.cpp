// COPYRIGHT DASSAULT SYSTEMES {{YEAR}}
//===================================================================
// {{PREFIX}}Addin.cpp
// Addin implementation
//===================================================================
#include "{{PREFIX}}Addin.h"

// Application Frame
#include "CATCommandHeader.h"
#include "CATCmdContainer.h"
#include "CATCmdStarter.h"
#include "CATCreateWorkshop.h"

// Interface TIE includes
#include "TIE_CATIAfrGeneralWksAddin.h"

// Expose interfaces via TIE
TIE_CATIAfrGeneralWksAddin({{PREFIX}}Addin);

// Implement IID for class identification
CATImplementClass({{PREFIX}}Addin,
                  DataExtension,
                  CATBaseUnknown,
                  CATNull);

//-----------------------------------------------------------------------
// Constructor
//-----------------------------------------------------------------------
{{PREFIX}}Addin::{{PREFIX}}Addin()
    : CATBaseUnknown()
{
    // Constructor - register command headers here if needed
    // Or defer to CreateToolbars() for lazy initialization
}

//-----------------------------------------------------------------------
// Destructor
//-----------------------------------------------------------------------
{{PREFIX}}Addin::~{{PREFIX}}Addin()
{
    // Destructor - framework handles cleanup
}

//-----------------------------------------------------------------------
// CreateCommands - Register commands
//-----------------------------------------------------------------------
void {{PREFIX}}Addin::CreateCommands()
{
    // Register command headers here
    // new MyCmdHeader("MyCmd", "MyModule", "MyCmd", (void*)NULL);
}

//-----------------------------------------------------------------------
// CreateToolbars - Create addin toolbars
//-----------------------------------------------------------------------
CATCmdContainer* {{PREFIX}}Addin::CreateToolbars()
{
    // Register commands first (if not done in constructor)
    // Pattern: new CATCommandHeader(HeaderID, ClassName, MethodName, Options)
    
    // Example command registration:
    // new CATCommandHeader("{{PREFIX}}AddinCmdHdr",
    //                      "{{PREFIX}}AddinCmd",
    //                      "{{PREFIX}}AddinCmd",
    //                      (void*)NULL,
    //                      "{{PREFIX}}Addin",  // Resource file prefix
    //                      CATCommandHeaderTypeExclusive);
    
    // Create toolbar container
    NewAccess(CATCmdContainer, pToolbarStarter, {{PREFIX}}AddinTlbStarter);
    
    if (pToolbarStarter)
    {
        // Create addin toolbar
        NewAccess(CATCmdContainer, pAddinToolbar, {{PREFIX}}AddinTlb);
        
        if (pAddinToolbar)
        {
            // Make toolbar visible
            SetAccessChild(pToolbarStarter, pAddinToolbar);
            
            // Add commands to toolbar
            // SetAccessNext("{{PREFIX}}AddinCmdHdr");
            // SetAccessCommand("{{PREFIX}}AddinTlb", "{{PREFIX}}AddinCmdHdr");
            
            // Add separator if needed
            // SetAccessNext("Separator");
            
            // TODO: Add your addin toolbar commands here
        }
    }
    
    return pToolbarStarter;
}

//-----------------------------------------------------------------------
// CreateMenus - Create addin menus (optional)
//-----------------------------------------------------------------------
CATCmdContainer* {{PREFIX}}Addin::CreateMenus()
{
    // Most addins use toolbars only
    // Uncomment if custom menus are needed
    
    return NULL;
}
