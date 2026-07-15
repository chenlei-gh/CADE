// COPYRIGHT DASSAULT SYSTEMES 2026
#ifndef <CommandClassName>_h
#define <CommandClassName>_h

#include "CATStateCommand.h"

// Forward declarations
class CATIndicationAgent;
class CATDialogAgent;
class CATPathElement;
class CATPathElementAgent;

/**
 * @brief State command for <Description>
 * 
 * This command uses a state machine to guide user through interactive selection:
 * - State 1: Select first element
 * - State 2: Select second element
 * - State 3: Process and complete
 * 
 * Supports:
 * - Interactive 3D selection
 * - Undo/Redo
 * - Right-click context menu
 * - Escape to cancel
 */
class <CommandClassName> : public CATStateCommand
{
public:
    /**
     * @brief Constructor
     */
    <CommandClassName>();

    /**
     * @brief Destructor
     */
    virtual ~<CommandClassName>();

    /**
     * @brief Build the state graph
     * Called once at command activation
     */
    virtual void BuildGraph();

    /**
     * @brief Command activation
     * @return TRUE to continue, FALSE to cancel
     */
    virtual CATStatusChangeRC Activate(CATCommand* iFromClient, CATNotification* iNotification);

    /**
     * @brief Command deactivation
     * @return TRUE if deactivation successful
     */
    virtual CATStatusChangeRC Desactivate(CATCommand* iFromClient, CATNotification* iNotification);

    /**
     * @brief Cancel command
     * @return TRUE if cancel successful
     */
    virtual CATStatusChangeRC Cancel(CATCommand* iFromClient, CATNotification* iNotification);

private:
    // --- Acquisition Agents ---
    CATPathElementAgent*  _pFirstSelectionAgent;   // First element selector
    CATPathElementAgent*  _pSecondSelectionAgent;  // Second element selector
    CATDialogAgent*       _pDialogAgent;           // Dialog interaction (optional)

    // --- State Transition Actions ---
    /**
     * @brief Action when first element is selected
     * @return TRUE to proceed to next state
     */
    CATBoolean ActionOnFirstSelection(void* iData);

    /**
     * @brief Action when second element is selected
     * @return TRUE to proceed to next state
     */
    CATBoolean ActionOnSecondSelection(void* iData);

    /**
     * @brief Final action to complete command
     * @return TRUE if successful
     */
    CATBoolean ActionComplete(void* iData);

    // --- Condition Methods ---
    /**
     * @brief Check if first selection is valid
     * @return TRUE if valid
     */
    CATBoolean CheckFirstSelection(void* iData);

    /**
     * @brief Check if second selection is valid
     * @return TRUE if valid
     */
    CATBoolean CheckSecondSelection(void* iData);

    // --- Helper Methods ---
    /**
     * @brief Get selected element from agent
     */
    CATBaseUnknown* GetSelectedElement(CATPathElementAgent* iAgent);

    /**
     * @brief Show feedback in 3D (temporary graphics)
     */
    void ShowFeedback();

    /**
     * @brief Clear temporary feedback
     */
    void ClearFeedback();

    /**
     * @brief Process the selected elements
     */
    HRESULT ProcessElements();

    // Prevent copy
    <CommandClassName>(const <CommandClassName>&);
    <CommandClassName>& operator=(const <CommandClassName>&);
};

#endif
