# CATIA Dialog Quick Reference

> Quick lookup for common Dialog controls and patterns

---

## 🎨 Common Controls Cheat Sheet

### CATDlgEditor (Text Input)
```cpp
// Create
_pEditor = new CATDlgEditor(parent, "Name", CATDlgEdtString);
_pEditor->SetVisibleTextWidth(30);

// Set/Get value
_pEditor->SetText("Initial text");
CATUnicodeString text = _pEditor->GetText();
```

**Types:** `CATDlgEdtString`, `CATDlgEdtInteger`, `CATDlgEdtReal`, `CATDlgEdtPassword`

---

### CATDlgPushButton (Button)
```cpp
// Create
_pButton = new CATDlgPushButton(parent, "Name");
_pButton->SetTitle("MyDialog.ButtonLabel");

// Register callback
AddAnalyseNotificationCB(
    _pButton,
    _pButton->GetPushBActivateNotification(),
    (CATCommand::CATCommandMethod)&MyClass::OnButtonClicked,
    NULL
);

// Callback signature
void OnButtonClicked(CATCommand*, CATNotification*, CATCommandClientData);
```

---

### CATDlgCombo (Dropdown)
```cpp
// Create
_pCombo = new CATDlgCombo(parent, "Name", CATDlgCmbDropDown);
_pCombo->SetVisibleTextWidth(20);

// Add items
_pCombo->SetLine("Item 1", 0);
_pCombo->SetLine("Item 2", 1);
_pCombo->SetLine("Item 3", 2);

// Set/Get selection
_pCombo->SetSelect(0);
int selected = _pCombo->GetSelect();

// Callback
AddAnalyseNotificationCB(
    _pCombo,
    _pCombo->GetComboSelectNotification(),
    (CATCommand::CATCommandMethod)&MyClass::OnComboChanged,
    NULL
);
```

**Styles:** `CATDlgCmbDropDown` (select only), `CATDlgCmbEntry` (with text input)

---

### CATDlgCheckButton (Checkbox)
```cpp
// Create
_pCheck = new CATDlgCheckButton(parent, "Name");
_pCheck->SetTitle("MyDialog.CheckLabel");

// Set/Get state
_pCheck->SetState(CATDlgCheck);    // Checked
_pCheck->SetState(CATDlgUncheck);  // Unchecked
bool checked = (_pCheck->GetState() == CATDlgCheck);

// Callback
AddAnalyseNotificationCB(
    _pCheck,
    _pCheck->GetCheckBModifyNotification(),
    (CATCommand::CATCommandMethod)&MyClass::OnCheckChanged,
    NULL
);
```

---

### CATDlgRadioButton (Radio Button)
```cpp
// Create group (only one can be selected)
_pRadio1 = new CATDlgRadioButton(parent, "Radio1");
_pRadio1->SetTitle("Option 1");
_pRadio2 = new CATDlgRadioButton(parent, "Radio2");
_pRadio2->SetTitle("Option 2");

// Set selection
_pRadio1->SetState(CATDlgCheck);

// Check which is selected
if (_pRadio1->GetState() == CATDlgCheck) {
    // Option 1 selected
}
```

---

### CATDlgLabel (Text Label)
```cpp
_pLabel = new CATDlgLabel(parent, "Name");
_pLabel->SetTitle("MyDialog.LabelText");
```

---

### CATDlgFrame (Container)
```cpp
_pFrame = new CATDlgFrame(parent, "Name", CATDlgGridLayout);
```

**Layouts:** `CATDlgGridLayout`, `CATDlgFillLayout`, `CATDlgBorderLayout`

---

### CATDlgSeparator (Visual Line)
```cpp
_pSeparator = new CATDlgSeparator(parent, "Name", CATDlgCtrHorizontal);
```

**Orientations:** `CATDlgCtrHorizontal`, `CATDlgCtrVertical`

---

## 📐 Grid Layout

### Set Grid Constraints
```cpp
CATDlgGridConstraints constraints(row, col, rowSpan, colSpan, sides);
parentFrame->SetGridConstraints(control, constraints);
```

**Parameters:**
- `row` - Grid row (0-based)
- `col` - Grid column (0-based)
- `rowSpan` - Number of rows to span
- `colSpan` - Number of columns to span
- `sides` - Attachment:
  - `CATGRID_4SIDES` - Fill cell
  - `CATGRID_LEFT` - Align left
  - `CATGRID_RIGHT` - Align right
  - `CATGRID_TOP` - Align top
  - `CATGRID_BOTTOM` - Align bottom
  - `CATGRID_CENTER` - Center

### Example Layout
```cpp
// Row 0: Label | Editor
_pLabel = new CATDlgLabel(frame, "Label");
CATDlgGridConstraints(0, 0, 1, 1, CATGRID_LEFT);
frame->SetGridConstraints(_pLabel, ...);

_pEditor = new CATDlgEditor(frame, "Editor", CATDlgEdtString);
CATDlgGridConstraints(0, 1, 1, 1, CATGRID_4SIDES);
frame->SetGridConstraints(_pEditor, ...);

// Row 1: Button spanning 2 columns
_pButton = new CATDlgPushButton(frame, "Button");
CATDlgGridConstraints(1, 0, 1, 2, CATGRID_CENTER);
frame->SetGridConstraints(_pButton, ...);
```

---

## 🏗️ Dialog Structure Pattern

### Constructor
```cpp
MyDialog::MyDialog(CATDialog* iParent, const CATString& iName)
    : CATDlgDialog(iParent, iName, CATDlgWndModal | CATDlgGridLayout),
      _pMainFrame(NULL),
      _pEditor(NULL),
      _pButton(NULL)
{
    // Initialize all pointers to NULL
}
```

**Flags:**
- `CATDlgWndModal` - Blocks until closed
- `CATDlgWndNoModal` - Non-blocking
- `CATDlgGridLayout` - Use grid layout

---

### Build Method
```cpp
void MyDialog::Build()
{
    // 1. Set title
    SetTitle("MyDialog.Title");
    
    // 2. Create main frame
    _pMainFrame = new CATDlgFrame(this, "MainFrame", CATDlgGridLayout);
    
    // 3. Create controls
    _pEditor = new CATDlgEditor(_pMainFrame, "Editor", CATDlgEdtString);
    
    // 4. Set layout
    CATDlgGridConstraints constraints(0, 0, 1, 1, CATGRID_4SIDES);
    _pMainFrame->SetGridConstraints(_pEditor, constraints);
    
    // 5. Register callbacks
    AddAnalyseNotificationCB(...);
    
    // 6. Set main frame layout
    CATDlgGridConstraints mainConstraints(0, 0, 1, 1, CATGRID_4SIDES);
    SetGridConstraints(_pMainFrame, mainConstraints);
}
```

---

### Callback Pattern
```cpp
void MyDialog::OnOKClicked(CATCommand* iFrom, 
                           CATNotification* iNotification, 
                           CATCommandClientData iData)
{
    // 1. Get values from controls
    CATUnicodeString text = _pEditor->GetText();
    
    // 2. Validate
    if (text.GetLengthInChar() == 0) {
        return; // Show error
    }
    
    // 3. Process data
    // ... your logic here ...
    
    // 4. Close dialog
    SetVisibility(CATDlgHide);
    RequestDelayedDestruction();
}
```

---

### Destructor
```cpp
MyDialog::~MyDialog()
{
    // No need to delete controls - framework handles it
}
```

---

## 📝 Resource Files

### .CATNls (String Resources)
```
# Location: Framework.edu/CNext/resources/msgcatalog/MyFramework.CATNls

MyDialog.Title = "My Dialog Title";
MyDialog.OKButton = "OK";
MyDialog.CancelButton = "Cancel";
MyDialog.InputLabel = "Enter value:";
```

### .CATRsc (Visual Resources)
```
# Location: Framework.edu/CNext/resources/msgcatalog/MyFramework.CATRsc

MyDialog.Width = 400;
MyDialog.Height = 300;
```

---

## 🚀 Display Dialog

### Modal (Blocks)
```cpp
#include "MyDialog.h"
#include "CATApplicationFrame.h"

void ShowDialog()
{
    CATApplicationFrame* pFrame = CATApplicationFrame::GetFrame();
    
    MyDialog* pDialog = new MyDialog(pFrame, "MyDialog");
    pDialog->Build();
    pDialog->SetVisibility(CATDlgShow);  // Blocks here
    
    // Dialog deletes itself when closed
}
```

### Non-Modal (Doesn't Block)
```cpp
void ShowDialogNonModal()
{
    CATApplicationFrame* pFrame = CATApplicationFrame::GetFrame();
    
    // Change constructor to use CATDlgWndNoModal
    MyDialog* pDialog = new MyDialog(pFrame, "MyDialog");
    pDialog->Build();
    pDialog->SetVisibility(CATDlgShow);  // Returns immediately
}
```

---

## 🔧 Common Patterns

### Get Multiple Values
```cpp
void MyDialog::GetValues(CATUnicodeString& oText, int& oType, bool& oChecked)
{
    oText = _pEditor->GetText();
    oType = _pCombo->GetSelect();
    oChecked = (_pCheck->GetState() == CATDlgCheck);
}
```

### Validate Input
```cpp
bool MyDialog::ValidateInput()
{
    if (_pEditor->GetText().GetLengthInChar() == 0) {
        // Show error
        return false;
    }
    return true;
}
```

### Show Error Message
```cpp
void MyDialog::ShowError(const char* message)
{
    CATDlgNotify* pNotify = new CATDlgNotify(
        this, 
        "Error", 
        CATDlgNfyError
    );
    pNotify->DisplayBlocked(message);
    pNotify->RequestDelayedDestruction();
}
```

### Enable/Disable Controls
```cpp
_pButton->SetSensitivity(CATDlgEnable);   // Enable
_pButton->SetSensitivity(CATDlgDisable);  // Disable (greyed out)
```

### Show/Hide Controls
```cpp
_pFrame->SetVisibility(CATDlgShow);  // Show
_pFrame->SetVisibility(CATDlgHide);  // Hide
```

---

## 📚 Notification Types Reference

| Control | Notification | Get Method |
|---------|-------------|------------|
| CATDlgPushButton | Button clicked | `GetPushBActivateNotification()` |
| CATDlgCombo | Selection changed | `GetComboSelectNotification()` |
| CATDlgEditor | Text modified | `GetEditorModifyNotification()` |
| CATDlgEditor | Got focus | `GetEditorFocusInNotification()` |
| CATDlgEditor | Lost focus | `GetEditorFocusOutNotification()` |
| CATDlgCheckButton | State changed | `GetCheckBModifyNotification()` |
| CATDlgRadioButton | State changed | `GetRadioBModifyNotification()` |

---

## ⚠️ Common Mistakes

### ❌ Not calling Build()
```cpp
MyDialog* p = new MyDialog(NULL, "Dlg");
p->SetVisibility(CATDlgShow);  // WRONG! UI not created
```
**✅ Must call `Build()` first!**

---

### ❌ Manual deletion
```cpp
delete pDialog;  // WRONG! Will crash
```
**✅ Use `RequestDelayedDestruction()`**

---

### ❌ Wrong callback signature
```cpp
void OnClick();  // WRONG!
```
**✅ Must be:** `void OnClick(CATCommand*, CATNotification*, CATCommandClientData)`

---

### ❌ Forgetting CATImplementClass
```cpp
// Missing in .cpp:
CATImplementClass(MyDialog, Implementation, CATDlgDialog, CATNull);
```

---

## 🔗 Full Documentation

- **EXAMPLE_DIALOG.md** - Complete tutorial with explanations
- **templates/dialog/** - Ready-to-use template files
- **AI_GUIDE.md** - Generation rules for AI

---

**Quick Start:** Copy templates from `templates/dialog/`, replace `<DialogClassName>` placeholders, compile!
