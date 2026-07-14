// COPYRIGHT DASSAULT SYSTEMES 2026
#ifndef <DialogClassName>_h
#define <DialogClassName>_h

#include "CATDlgDialog.h"

// Forward declarations
class CATDlgFrame;
class CATDlgLabel;
class CATDlgEditor;
class CATDlgPushButton;
class CATDlgCombo;
class CATDlgCheckButton;
class CATDlgRadioButton;
class CATDlgSeparator;
class CATNotification;

/**
 * @brief Custom dialog window for <Description>
 * 
 * This dialog provides UI for user interaction with controls:
 * - Input fields (CATDlgEditor)
 * - Buttons (CATDlgPushButton)
 * - Dropdown lists (CATDlgCombo)
 * - Checkboxes (CATDlgCheckButton)
 * - Radio buttons (CATDlgRadioButton)
 */
class <DialogClassName> : public CATDlgDialog Dialog
{
    CATDeclareClass;

public:
    /**
     * @brief Constructor
     * @param iParent Parent window (can be NULL for standalone dialog)
     * @param iName Dialog identifier for resource loading
     */
    <DialogClassName>(CATDialog* iParent, const CATString& iName);

    /**
     * @brief Destructor
     */
    virtual ~<DialogClassName>();

    /**
     * @brief Build the dialog UI (called after constructor)
     * Must be called explicitly after dialog creation
     */
    void Build();

private:
    // --- UI Components ---
    CATDlgFrame*        _pMainFrame;      // Main container frame
    CATDlgFrame*        _pInputFrame;     // Frame for input controls
    CATDlgFrame*        _pButtonFrame;    // Frame for buttons
    
    CATDlgLabel*        _pTitleLabel;     // Title label
    CATDlgLabel*        _pInputLabel;     // Input field label
    
    CATDlgEditor*       _pInputEditor;    // Text input field
    CATDlgCombo*        _pTypeCombo;      // Dropdown list
    CATDlgCheckButton*  _pOptionCheck;    // Checkbox
    
    CATDlgPushButton*   _pOKButton;       // OK button
    CATDlgPushButton*   _pCancelButton;   // Cancel button
    CATDlgPushButton*   _pApplyButton;    // Apply button

    // --- Callback Methods ---
    /**
     * @brief Callback when OK button is clicked
     * @param iNotification Notification object
     */
    void OnOKClicked(CATCommand* iFrom, CATNotification* iNotification, CATCommandClientData iData);

    /**
     * @brief Callback when Cancel button is clicked
     */
    void OnCancelClicked(CATCommand* iFrom, CATNotification* iNotification, CATCommandClientData iData);

    /**
     * @brief Callback when Apply button is clicked
     */
    void OnApplyClicked(CATCommand* iFrom, CATNotification* iNotification, CATCommandClientData iData);

    /**
     * @brief Callback when combo selection changes
     */
    void OnComboSelectionChanged(CATCommand* iFrom, CATNotification* iNotification, CATCommandClientData iData);

    // --- Helper Methods ---
    /**
     * @brief Get current input value
     * @return Text from input editor
     */
    CATUnicodeString GetInputValue() const;

    /**
     * @brief Get selected combo item index
     * @return Selected index (0-based)
     */
    int GetSelectedType() const;

    /**
     * @brief Check if option checkbox is checked
     * @return true if checked
     */
    bool IsOptionChecked() const;

    /**
     * @brief Validate input data
     * @return true if valid
     */
    bool ValidateInput();

    // Prevent copy
    <DialogClassName>(const <DialogClassName>&);
    <DialogClassName>& operator=(const <DialogClassName>&);
};

#endif
