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

// Interface TIE includes
#include "TIE_CATIAfrGeneralWksAddin.h"
#include "TIE_CATIWorkbenchAddin.h"

// Expose interfaces via TIE
TIE_CATIAfrGeneralWksAddin({{PREFIX}}Addin);
TIE_CATIWorkbenchAddin({{PREFIX}}Addin);

// Implement IID for class identification
CATImplementClass({{PREFIX}}Addin,
                  Implementation,
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
    CATCmdContainer* pToolbarStarter = NULL;
    NewAccess(CATCmdContainer, pToolbarStarter, {{PREFIX}}AddinTlbStarter);
    
    if (pToolbarStarter)
    {
        // Create addin toolbar
        CATCmdContainer* pAddinToolbar = NULL;
        NewAccess(CATCmdContainer, pAddinToolbar, {{PREFIX}}AddinTlb);
        
        if (pAddinToolbar)
        {
            // Make toolbar visible
            SetAccessChild({{PREFIX}}AddinTlbStarter, {{PREFIX}}AddinTlb);
            
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
