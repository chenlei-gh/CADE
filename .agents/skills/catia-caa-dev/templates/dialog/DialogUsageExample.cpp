// COPYRIGHT DASSAULT SYSTEMES 2026
// Example: How to create and show the dialog

#include "<DialogClassName>.h"
#include "CATApplicationFrame.h"
#include <iostream.h>

/**
 * Function to create and display the dialog
 * Call this from a Command or other entry point
 */
void ShowMyDialog()
{
    // Get application frame as parent (optional, can be NULL)
    CATApplicationFrame* pAppFrame = CATApplicationFrame::GetFrame();
    
    // Create dialog instance
    <DialogClassName>* pDialog = new <DialogClassName>(pAppFrame, "<DialogClassName>");
    
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
    CATApplicationFrame* pAppFrame = CATApplicationFrame::GetFrame();
    
    // Create with CATDlgWndNoModal flag (modify constructor in .h/.cpp)
    <DialogClassName>* pDialog = new <DialogClassName>(pAppFrame, "<DialogClassName>");
    
    if (pDialog) {
        pDialog->Build();
        
        // Show as non-modal (doesn't block, returns immediately)
        pDialog->SetVisibility(CATDlgShow);
        
        cout << "Non-modal dialog displayed" << endl;
        
        // Important: Keep pointer if you need to interact with dialog later
        // Don't delete manually - dialog manages its own lifetime
    }
}
