// COPYRIGHT DASSAULT SYSTEMES 2026
// Example: How to create and show the dialog

#include "<DialogClassName>.h"
#include "CATApplicationFrame.h"
#include "CATFrmWindow.h"
#include <iostream.h>

/**
 * Function to create and display the dialog
 * Call this from a Command or other entry point
 */
void ShowMyDialog()
{
    // Parent MUST be the main window — a NULL or non-CATDialog parent makes
    // the dialog silently invisible (see knowledge/failure_patterns/fp_dialog_null_parent.md)
    CATFrmWindow* pMainWindow = CATApplicationFrame::GetFrame()->GetMainWindow();

    // Create dialog instance
    <DialogClassName>* pDialog = new <DialogClassName>(pMainWindow, "<DialogClassName>");
    
    if (pDialog) {
        // Build UI (must call after constructor)
        pDialog->Build();
        
        // Show dialog (modal - blocks until closed)
        pDialog->SetVisibility(CATDlgShow);
        
        cout << "Dialog displayed" << endl;
        
        // Note: Dialog will delete itself when closed (RequestDelayedDestruction)
    } else {
        cout << "Failed to create dialog" << endl;
    }
}

/**
 * Alternative: Non-modal dialog (doesn't block)
 */
void ShowMyDialogNonModal()
{
    // Same rule: never NULL parent (fp_dialog_null_parent)
    CATFrmWindow* pMainWindow = CATApplicationFrame::GetFrame()->GetMainWindow();

    // Create with CATDlgWndNoModal flag (modify constructor in .h/.cpp)
    <DialogClassName>* pDialog = new <DialogClassName>(pMainWindow, "<DialogClassName>");
    
    if (pDialog) {
        pDialog->Build();
        
        // Show as non-modal (doesn't block, returns immediately)
        pDialog->SetVisibility(CATDlgShow);
        
        cout << "Non-modal dialog displayed" << endl;
        
        // Important: Keep pointer if you need to interact with dialog later
        // Don't delete manually - dialog manages its own lifetime
    }
}
