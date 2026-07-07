// COPYRIGHT DASSAULT SYSTEMES 2026
#include "<DialogClassName>.h"

// Dialog framework includes
#include "CATDlgFrame.h"
#include "CATDlgLabel.h"
#include "CATDlgEditor.h"
#include "CATDlgPushButton.h"
#include "CATDlgCombo.h"
#include "CATDlgCheckButton.h"
#include "CATDlgRadioButton.h"
#include "CATDlgSeparator.h"
#include "CATDlgGridConstraints.h"

// Notification includes
#include "CATDlgNotification.h"

// String handling
#include "CATUnicodeString.h"

// Standard I/O (CAA classic style)
#include <iostream.h>

// Implement class metadata
CATImplementClass(<DialogClassName>, Implementation, CATDlgDialog, CATNull);

//-----------------------------------------------------------------------------
// Constructor
//-----------------------------------------------------------------------------
<DialogClassName>::<DialogClassName>(CATDialog* iParent, const CATString& iName)
    : CATDlgDialog(iParent, iName, CATDlgWndModal | CATDlgGridLayout),
      _pMainFrame(NULL),
      _pInputFrame(NULL),
      _pButtonFrame(NULL),
      _pTitleLabel(NULL),
      _pInputLabel(NULL),
      _pInputEditor(NULL),
      _pTypeCombo(NULL),
      _pOptionCheck(NULL),
      _pOKButton(NULL),
      _pCancelButton(NULL),
      _pApplyButton(NULL)
{
    cout << "<DialogClassName> constructor" << endl;
}

//-----------------------------------------------------------------------------
// Destructor
//-----------------------------------------------------------------------------
<DialogClassName>::~<DialogClassName>()
{
    cout << "<DialogClassName> destructor" << endl;
    
    // Note: Dialog framework automatically deletes child controls
    // No need to manually delete _pMainFrame, _pOKButton, etc.
}

//-----------------------------------------------------------------------------
// Build UI
//-----------------------------------------------------------------------------
void <DialogClassName>::Build()
{
    // Set dialog title (reads from .CATNls resource file)
    SetTitle("<DialogClassName>.Title");

    // Create main frame (container for all controls)
    _pMainFrame = new CATDlgFrame(this, "MainFrame", CATDlgGridLayout);

    //-------------------------------------------------------------------------
    // Title Label
    //-------------------------------------------------------------------------
    _pTitleLabel = new CATDlgLabel(_pMainFrame, "TitleLabel");
    _pTitleLabel->SetTitle("<DialogClassName>.TitleLabel");

    CATDlgGridConstraints titleConstraints(0, 0, 1, 1, CATGRID_4SIDES);
    _pMainFrame->SetGridConstraints(_pTitleLabel, titleConstraints);

    //-------------------------------------------------------------------------
    // Input Frame (contains input controls)
    //-------------------------------------------------------------------------
    _pInputFrame = new CATDlgFrame(_pMainFrame, "InputFrame", CATDlgGridLayout);

    CATDlgGridConstraints inputFrameConstraints(1, 0, 1, 1, CATGRID_4SIDES);
    _pMainFrame->SetGridConstraints(_pInputFrame, inputFrameConstraints);

    // Input label
    _pInputLabel = new CATDlgLabel(_pInputFrame, "InputLabel");
    _pInputLabel->SetTitle("<DialogClassName>.InputLabel");
    CATDlgGridConstraints labelConstraints(0, 0, 1, 1, CATGRID_LEFT);
    _pInputFrame->SetGridConstraints(_pInputLabel, labelConstraints);

    // Input editor (text field)
    _pInputEditor = new CATDlgEditor(_pInputFrame, "InputEditor", CATDlgEdtString);
    _pInputEditor->SetVisibleTextWidth(30); // 30 characters wide
    CATDlgGridConstraints editorConstraints(0, 1, 1, 1, CATGRID_4SIDES);
    _pInputFrame->SetGridConstraints(_pInputEditor, editorConstraints);

    // Type combo (dropdown)
    _pTypeCombo = new CATDlgCombo(_pInputFrame, "TypeCombo", CATDlgCmbDropDown);
    _pTypeCombo->SetVisibleTextWidth(20);
    
    // Add combo items (reads from .CATNls)
    _pTypeCombo->SetLine("Type1", 0);
    _pTypeCombo->SetLine("Type2", 1);
    _pTypeCombo->SetLine("Type3", 2);
    _pTypeCombo->SetSelect(0); // Select first item by default
    
    CATDlgGridConstraints comboConstraints(1, 1, 1, 1, CATGRID_4SIDES);
    _pInputFrame->SetGridConstraints(_pTypeCombo, comboConstraints);

    // Register callback for combo selection change
    AddAnalyseNotificationCB(
        _pTypeCombo,
        _pTypeCombo->GetComboSelectNotification(),
        (CATCommand::CATCommandMethod)&<DialogClassName>::OnComboSelectionChanged,
        NULL
    );

    // Option checkbox
    _pOptionCheck = new CATDlgCheckButton(_pInputFrame, "OptionCheck");
    _pOptionCheck->SetTitle("<DialogClassName>.OptionCheck");
    _pOptionCheck->SetState(CATDlgUncheck); // Unchecked by default
    
    CATDlgGridConstraints checkConstraints(2, 0, 1, 2, CATGRID_LEFT);
    _pInputFrame->SetGridConstraints(_pOptionCheck, checkConstraints);

    //-------------------------------------------------------------------------
    // Button Frame (OK, Cancel, Apply)
    //-------------------------------------------------------------------------
    _pButtonFrame = new CATDlgFrame(_pMainFrame, "ButtonFrame", CATDlgGridLayout);
    
    CATDlgGridConstraints buttonFrameConstraints(2, 0, 1, 1, CATGRID_BOTTOM);
    _pMainFrame->SetGridConstraints(_pButtonFrame, buttonFrameConstraints);

    // OK Button
    _pOKButton = new CATDlgPushButton(_pButtonFrame, "OKButton");
    _pOKButton->SetTitle("<DialogClassName>.OKButton");
    
    CATDlgGridConstraints okConstraints(0, 0, 1, 1, CATGRID_CENTER);
    _pButtonFrame->SetGridConstraints(_pOKButton, okConstraints);

    AddAnalyseNotificationCB(
        _pOKButton,
        _pOKButton->GetPushBActivateNotification(),
        (CATCommand::CATCommandMethod)&<DialogClassName>::OnOKClicked,
        NULL
    );

    // Cancel Button
    _pCancelButton = new CATDlgPushButton(_pButtonFrame, "CancelButton");
    _pCancelButton->SetTitle("<DialogClassName>.CancelButton");
    
    CATDlgGridConstraints cancelConstraints(0, 1, 1, 1, CATGRID_CENTER);
    _pButtonFrame->SetGridConstraints(_pCancelButton, cancelConstraints);

    AddAnalyseNotificationCB(
        _pCancelButton,
        _pCancelButton->GetPushBActivateNotification(),
        (CATCommand::CATCommandMethod)&<DialogClassName>::OnCancelClicked,
        NULL
    );

    // Apply Button
    _pApplyButton = new CATDlgPushButton(_pButtonFrame, "ApplyButton");
    _pApplyButton->SetTitle("<DialogClassName>.ApplyButton");
    
    CATDlgGridConstraints applyConstraints(0, 2, 1, 1, CATGRID_CENTER);
    _pButtonFrame->SetGridConstraints(_pApplyButton, applyConstraints);

    AddAnalyseNotificationCB(
        _pApplyButton,
        _pApplyButton->GetPushBActivateNotification(),
        (CATCommand::CATCommandMethod)&<DialogClassName>::OnApplyClicked,
        NULL
    );

    // Set main frame layout
    CATDlgGridConstraints mainConstraints(0, 0, 1, 1, CATGRID_4SIDES);
    SetGridConstraints(_pMainFrame, mainConstraints);

    cout << "<DialogClassName> Build completed" << endl;
}

//-----------------------------------------------------------------------------
// OK Button Callback
//-----------------------------------------------------------------------------
void <DialogClassName>::OnOKClicked(CATCommand* iFrom, 
                                     CATNotification* iNotification, 
                                     CATCommandClientData iData)
{
    cout << "OK button clicked" << endl;

    // Validate input
    if (!ValidateInput()) {
        cout << "Validation failed" << endl;
        return;
    }

    // Get values
    CATUnicodeString inputValue = GetInputValue();
    int selectedType = GetSelectedType();
    bool optionChecked = IsOptionChecked();

    cout << "Input: " << inputValue.ConvertToChar() << endl;
    cout << "Type: " << selectedType << endl;
    cout << "Option: " << (optionChecked ? "Checked" : "Unchecked") << endl;

    // TODO: Process data here

    // Close dialog with OK status
    SetVisibility(CATDlgHide);
    RequestDelayedDestruction();
}

//-----------------------------------------------------------------------------
// Cancel Button Callback
//-----------------------------------------------------------------------------
void <DialogClassName>::OnCancelClicked(CATCommand* iFrom, 
                                         CATNotification* iNotification, 
                                         CATCommandClientData iData)
{
    cout << "Cancel button clicked" << endl;

    // Close dialog without processing
    SetVisibility(CATDlgHide);
    RequestDelayedDestruction();
}

//-----------------------------------------------------------------------------
// Apply Button Callback
//-----------------------------------------------------------------------------
void <DialogClassName>::OnApplyClicked(CATCommand* iFrom, 
                                        CATNotification* iNotification, 
                                        CATCommandClientData iData)
{
    cout << "Apply button clicked" << endl;

    // Validate input
    if (!ValidateInput()) {
        cout << "Validation failed" << endl;
        return;
    }

    // Get values and process (but keep dialog open)
    CATUnicodeString inputValue = GetInputValue();
    int selectedType = GetSelectedType();
    bool optionChecked = IsOptionChecked();

    cout << "Applying values..." << endl;
    cout << "Input: " << inputValue.ConvertToChar() << endl;
    cout << "Type: " << selectedType << endl;
    cout << "Option: " << (optionChecked ? "Checked" : "Unchecked") << endl;

    // TODO: Process data here (dialog remains open)
}

//-----------------------------------------------------------------------------
// Combo Selection Changed Callback
//-----------------------------------------------------------------------------
void <DialogClassName>::OnComboSelectionChanged(CATCommand* iFrom, 
                                                 CATNotification* iNotification, 
                                                 CATCommandClientData iData)
{
    int selectedIndex = GetSelectedType();
    cout << "Combo selection changed to: " << selectedIndex << endl;

    // TODO: React to combo change (e.g., update other controls)
}

//-----------------------------------------------------------------------------
// Get Input Value
//-----------------------------------------------------------------------------
CATUnicodeString <DialogClassName>::GetInputValue() const
{
    if (_pInputEditor) {
        return _pInputEditor->GetText();
    }
    return CATUnicodeString("");
}

//-----------------------------------------------------------------------------
// Get Selected Type
//-----------------------------------------------------------------------------
int <DialogClassName>::GetSelectedType() const
{
    if (_pTypeCombo) {
        return _pTypeCombo->GetSelect();
    }
    return -1;
}

//-----------------------------------------------------------------------------
// Is Option Checked
//-----------------------------------------------------------------------------
bool <DialogClassName>::IsOptionChecked() const
{
    if (_pOptionCheck) {
        return (_pOptionCheck->GetState() == CATDlgCheck);
    }
    return false;
}

//-----------------------------------------------------------------------------
// Validate Input
//-----------------------------------------------------------------------------
bool <DialogClassName>::ValidateInput()
{
    // Check if input is not empty
    CATUnicodeString inputValue = GetInputValue();
    if (inputValue.GetLengthInChar() == 0) {
        cout << "Error: Input field is empty" << endl;
        // TODO: Show error message dialog
        return false;
    }

    // Check if a type is selected
    int selectedType = GetSelectedType();
    if (selectedType < 0) {
        cout << "Error: No type selected" << endl;
        return false;
    }

    return true;
}
