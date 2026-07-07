// COPYRIGHT DASSAULT SYSTEMES 2026
#include "<CommandClassName>.h"

// Dialog agents
#include "CATPathElementAgent.h"
#include "CATDialogAgent.h"
#include "CATIndicationAgent.h"

// Path and selection
#include "CATPathElement.h"

// State command
#include "CATCreateExternalObject.h"

// Standard I/O
#include <iostream.h>

// Create command as external object
CATCreateClass(<CommandClassName>);

//-----------------------------------------------------------------------------
// Constructor
//-----------------------------------------------------------------------------
<CommandClassName>::<CommandClassName>()
    : CATStateCommand("CommandName"),
      _pFirstSelectionAgent(NULL),
      _pSecondSelectionAgent(NULL),
      _pDialogAgent(NULL)
{
    cout << "<CommandClassName> constructor" << endl;
}

//-----------------------------------------------------------------------------
// Destructor
//-----------------------------------------------------------------------------
<CommandClassName>::~<CommandClassName>()
{
    cout << "<CommandClassName> destructor" << endl;
    
    // Agents are deleted automatically by state command framework
    _pFirstSelectionAgent = NULL;
    _pSecondSelectionAgent = NULL;
    _pDialogAgent = NULL;
}

//-----------------------------------------------------------------------------
// Build State Graph
//-----------------------------------------------------------------------------
void <CommandClassName>::BuildGraph()
{
    cout << "Building state graph..." << endl;

    // Create acquisition agents
    _pFirstSelectionAgent = new CATPathElementAgent("FirstSelection");
    _pFirstSelectionAgent->SetBehavior(
        CATDlgEngWithPrevaluation |  // Validate before accepting
        CATDlgEngRepeat              // Allow multiple selections
    );
    
    // Set element filter (e.g., only accept certain types)
    // _pFirstSelectionAgent->SetElementType("CATIGSMLine");
    
    _pFirstSelectionAgent->AddElementType("CATIGSMPoint");
    _pFirstSelectionAgent->AddElementType("CATIGSMLine");
    
    _pSecondSelectionAgent = new CATPathElementAgent("SecondSelection");
    _pSecondSelectionAgent->SetBehavior(
        CATDlgEngWithPrevaluation |
        CATDlgEngRepeat
    );
    _pSecondSelectionAgent->AddElementType("CATIGSMPoint");
    _pSecondSelectionAgent->AddElementType("CATIGSMLine");

    // Build state graph
    // State 1: Initial state -> Select first element
    CATDialogState* pState1 = GetInitialState("State1");
    pState1->AddDialogAgent(_pFirstSelectionAgent);

    // State 2: Select second element
    CATDialogState* pState2 = AddDialogState("State2");
    pState2->AddDialogAgent(_pSecondSelectionAgent);

    // State 3: Final processing
    CATDialogState* pState3 = AddDialogState("State3");

    // Transitions
    // State1 -> State2: When first element selected
    AddTransition(
        pState1,
        pState2,
        IsOutputSetCondition(_pFirstSelectionAgent),
        Action((ActionMethod)&<CommandClassName>::ActionOnFirstSelection)
    );

    // State2 -> State3: When second element selected
    AddTransition(
        pState2,
        pState3,
        IsOutputSetCondition(_pSecondSelectionAgent),
        Action((ActionMethod)&<CommandClassName>::ActionOnSecondSelection)
    );

    // State3 -> State1: Loop back for another operation (optional)
    // Or State3 -> NULL: End command
    AddTransition(
        pState3,
        NULL,  // NULL = end command
        Condition(NULL),
        Action((ActionMethod)&<CommandClassName>::ActionComplete)
    );

    cout << "State graph built successfully" << endl;
}

//-----------------------------------------------------------------------------
// Activate Command
//-----------------------------------------------------------------------------
CATBoolean <CommandClassName>::Activate(CATCommand* iFromClient, 
                                         CATNotification* iNotification)
{
    cout << "Command activated" << endl;

    // Show prompt to user
    // SendNotification(GetFather(), this, "StatusMessage", 
    //                  CATUnicodeString("Select first element"));

    return TRUE;
}

//-----------------------------------------------------------------------------
// Desactivate Command
//-----------------------------------------------------------------------------
CATBoolean <CommandClassName>::Desactivate(CATCommand* iFromClient, 
                                            CATNotification* iNotification)
{
    cout << "Command deactivated" << endl;
    
    ClearFeedback();
    
    return TRUE;
}

//-----------------------------------------------------------------------------
// Cancel Command
//-----------------------------------------------------------------------------
CATBoolean <CommandClassName>::Cancel(CATCommand* iFromClient, 
                                       CATNotification* iNotification)
{
    cout << "Command cancelled" << endl;
    
    ClearFeedback();
    
    // Request command completion
    RequestDelayedDestruction();
    
    return TRUE;
}

//-----------------------------------------------------------------------------
// Action: First Selection
//-----------------------------------------------------------------------------
CATBoolean <CommandClassName>::ActionOnFirstSelection(void* iData)
{
    cout << "First element selected" << endl;

    // Get selected element
    CATBaseUnknown* pElement = GetSelectedElement(_pFirstSelectionAgent);
    if (!pElement) {
        cout << "Error: No element selected" << endl;
        return FALSE;
    }

    // Validate selection
    if (!CheckFirstSelection(NULL)) {
        cout << "First selection invalid" << endl;
        return FALSE;
    }

    // Show feedback
    ShowFeedback();

    // Update prompt
    // SendNotification(..., "Select second element");

    cout << "Proceeding to state 2" << endl;
    return TRUE;
}

//-----------------------------------------------------------------------------
// Action: Second Selection
//-----------------------------------------------------------------------------
CATBoolean <CommandClassName>::ActionOnSecondSelection(void* iData)
{
    cout << "Second element selected" << endl;

    // Get selected element
    CATBaseUnknown* pElement = GetSelectedElement(_pSecondSelectionAgent);
    if (!pElement) {
        cout << "Error: No element selected" << endl;
        return FALSE;
    }

    // Validate selection
    if (!CheckSecondSelection(NULL)) {
        cout << "Second selection invalid" << endl;
        return FALSE;
    }

    // Update feedback
    ShowFeedback();

    cout << "Proceeding to state 3" << endl;
    return TRUE;
}

//-----------------------------------------------------------------------------
// Action: Complete
//-----------------------------------------------------------------------------
CATBoolean <CommandClassName>::ActionComplete(void* iData)
{
    cout << "Completing command..." << endl;

    // Process the selections
    HRESULT hr = ProcessElements();
    if (FAILED(hr)) {
        cout << "Error: Processing failed" << endl;
        ClearFeedback();
        return FALSE;
    }

    cout << "Command completed successfully" << endl;
    
    ClearFeedback();
    
    // End command (transition to NULL state)
    return TRUE;
}

//-----------------------------------------------------------------------------
// Check First Selection
//-----------------------------------------------------------------------------
CATBoolean <CommandClassName>::CheckFirstSelection(void* iData)
{
    CATBaseUnknown* pElement = GetSelectedElement(_pFirstSelectionAgent);
    if (!pElement) {
        return FALSE;
    }

    // Add validation logic here
    // Example: Check if element type is correct
    // Example: Check if element is not null geometry

    return TRUE;
}

//-----------------------------------------------------------------------------
// Check Second Selection
//-----------------------------------------------------------------------------
CATBoolean <CommandClassName>::CheckSecondSelection(void* iData)
{
    CATBaseUnknown* pElement = GetSelectedElement(_pSecondSelectionAgent);
    if (!pElement) {
        return FALSE;
    }

    // Add validation logic here
    // Example: Check if second element is different from first
    // Example: Check compatibility between elements

    return TRUE;
}

//-----------------------------------------------------------------------------
// Get Selected Element
//-----------------------------------------------------------------------------
CATBaseUnknown* <CommandClassName>::GetSelectedElement(CATPathElementAgent* iAgent)
{
    if (!iAgent) {
        return NULL;
    }

    // Get path element list
    CATSO* pObjSet = iAgent->GetListOfValues();
    if (!pObjSet || pObjSet->GetSize() == 0) {
        return NULL;
    }

    // Get first element
    CATPathElement* pPath = (CATPathElement*)(*pObjSet)[0];
    if (!pPath) {
        return NULL;
    }

    // Get leaf object from path
    CATBaseUnknown* pElement = pPath->FindElement(IID_CATBaseUnknown);
    
    return pElement;
}

//-----------------------------------------------------------------------------
// Show Feedback
//-----------------------------------------------------------------------------
void <CommandClassName>::ShowFeedback()
{
    // TODO: Create temporary 3D graphics to show preview
    // Example: Draw line between selected points
    // Example: Highlight selected elements
    
    cout << "Showing feedback..." << endl;
}

//-----------------------------------------------------------------------------
// Clear Feedback
//-----------------------------------------------------------------------------
void <CommandClassName>::ClearFeedback()
{
    // TODO: Remove temporary graphics
    
    cout << "Clearing feedback..." << endl;
}

//-----------------------------------------------------------------------------
// Process Elements
//-----------------------------------------------------------------------------
HRESULT <CommandClassName>::ProcessElements()
{
    cout << "Processing selected elements..." << endl;

    // Get both selected elements
    CATBaseUnknown* pFirst = GetSelectedElement(_pFirstSelectionAgent);
    CATBaseUnknown* pSecond = GetSelectedElement(_pSecondSelectionAgent);

    if (!pFirst || !pSecond) {
        cout << "Error: Missing selections" << endl;
        return E_FAIL;
    }

    // TODO: Implement your processing logic here
    // Example: Create new geometry based on selections
    // Example: Modify existing elements
    // Example: Compute distance, angle, etc.

    cout << "Processing completed" << endl;
    return S_OK;
}
