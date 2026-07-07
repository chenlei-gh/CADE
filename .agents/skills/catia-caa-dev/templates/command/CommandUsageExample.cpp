// COPYRIGHT DASSAULT SYSTEMES 2026
// Example: How to use the command

#include "<CommandClassName>.h"
#include "<CommandHeaderClassName>.h"
#include "CATCommandHeader.h"

/**
 * Example 1: Create and activate command programmatically
 */
void ActivateMyCommand()
{
    // Create command instance
    <CommandClassName>* pCmd = new <CommandClassName>();
    
    // The command will activate automatically when created
    // BuildGraph() will be called
    // User can start selecting elements
}

/**
 * Example 2: Register command in workbench
 * Call this in your workbench's CreateCommands() method
 */
void RegisterCommandInWorkbench()
{
    // Create command header
    <CommandHeaderClassName>::CreateCommandHeader();
    
    // Now the command is available in CATIA
    // Can be added to toolbar, menu, etc.
}

/**
 * Example 3: Add command to toolbar
 * Call this in your workbench's CreateToolbars() method
 */
void AddCommandToToolbar()
{
    // Get or create toolbar
    CATCmdContainer* pToolbar = GetToolbar("MyToolbar");
    
    if (pToolbar) {
        // Add command starter
        CATCmdStarter* pStarter = new CATCmdStarter(
            "<CommandHeaderName>",  // Command header name
            pToolbar                // Parent toolbar
        );
    }
}

/**
 * Example 4: Command with dialog panel
 * If you want a dialog during command execution
 */
/*
void <CommandClassName>::BuildGraph()
{
    // Create dialog
    _pDialogAgent = new CATDialogAgent("DialogAgent");
    MyDialog* pDialog = new MyDialog(NULL, "MyDialog");
    _pDialogAgent->SetBehavior(CATDlgEngOneShot);
    _pDialogAgent->SetDialog(pDialog);
    
    // Add dialog to state
    CATDialogState* pState = GetInitialState("StateWithDialog");
    pState->AddDialogAgent(_pDialogAgent);
    
    // Transition when dialog closes
    AddTransition(
        pState,
        NULL,
        IsOutputSetCondition(_pDialogAgent),
        Action((ActionMethod)&<CommandClassName>::ProcessDialog)
    );
}
*/
