# CATIA Dialog Development - Complete Example

> Complete working example of a CATIA CAA Dialog with all controls

**Version**: 1.0  
**Framework**: Dialog, ApplicationFrame  
**Target**: CATIA V5R28 (B28)

---

## 📋 Overview

This example demonstrates a complete Dialog implementation with:
- ✅ Input fields (CATDlgEditor)
- ✅ Dropdown lists (CATDlgCombo)
- ✅ Checkboxes (CATDlgCheckButton)
- ✅ Buttons with callbacks
- ✅ Grid layout management
- ✅ Resource files (NLS/RSC)
- ✅ Input validation

---

## 📁 File Structure

```
Framework.edu/
├── IdentityCard/
│   └── IdentityCard.h                    # Framework dependencies
├── PublicInterfaces/
│   └── MyDialog.h                        # Dialog class declaration
├── MyDialogModule.m/
│   ├── Imakefile.mk                      # Build configuration
│   ├── src/
│   │   └── MyDialog.cpp                  # Dialog implementation
│   └── LocalInterfaces/
│       └── (none for dialogs)
└── CNext/
    └── resources/
        └── msgcatalog/
            ├── MyFramework.CATNls         # English strings
            ├── MyFramework.CATRsc         # Visual styles
            └── Chinese/                   # Optional
                └── MyFramework.CATNls     # Chinese strings
```

---

## 📝 Step-by-Step Implementation

### Step 1: IdentityCard.h

```cpp
// Framework.edu/IdentityCard/IdentityCard.h

AddPrereqComponent("System", Public);
AddPrereqComponent("ObjectModelerBase", Public);
AddPrereqComponent("Dialog", Public);
AddPrereqComponent("ApplicationFrame", Public);
AddPrereqComponent("Visualization", Public);
```

**Why these dependencies?**
- `Dialog` - Required for all CATDlg* classes
- `ApplicationFrame` - For CATApplicationFrame parent
- `Visualization` - For visual components

---

### Step 2: Dialog Header (MyDialog.h)

Key points in the header:
1. **Inherit from CATDlgDialog**
2. **Use CATDeclareClass macro**
3. **Store pointers to all controls as private members**
4. **Declare callback methods**

```cpp
class MyDialog : public CATDlgDialog
{
    CATDeclareClass;  // Required!

public:
    MyDialog(CATDialog* iParent, const CATString& iName);
    virtual ~MyDialog();
    void Build();

private:
    // UI components
    CATDlgFrame*        _pMainFrame;
    CATDlgEditor*       _pInputEditor;
    CATDlgPushButton*   _pOKButton;
    
    // Callbacks
    void OnOKClicked(CATCommand*, CATNotification*, CATCommandClientData);
};
```

---

### Step 3: Dialog Implementation (MyDialog.cpp)

#### Constructor
```cpp
MyDialog::MyDialog(CATDialog* iParent, const CATString& iName)
    : CATDlgDialog(iParent, iName, CATDlgWndModal | CATDlgGridLayout),
      _pMainFrame(NULL),
      _pInputEditor(NULL),
      _pOKButton(NULL)
{
    // Initialize all pointers to NULL
}
```

**Constructor flags:**
- `CATDlgWndModal` - Blocks until closed (use `CATDlgWndNoModal` for non-blocking)
- `CATDlgGridLayout` - Use grid layout manager

---

#### Build Method
```cpp
void MyDialog::Build()
{
    // 1. Set title (reads from .CATNls)
    SetTitle("MyDialog.Title");
    
    // 2. Create main container
    _pMainFrame = new CATDlgFrame(this, "MainFrame", CATDlgGridLayout);
    
    // 3. Create input editor
    _pInputEditor = new CATDlgEditor(_pMainFrame, "Input", CATDlgEdtString);
    _pInputEditor->SetVisibleTextWidth(30);
    
    // 4. Position editor in grid (row 0, col 0)
    CATDlgGridConstraints editorConstraints(0, 0, 1, 1, CATGRID_4SIDES);
    _pMainFrame->SetGridConstraints(_pInputEditor, editorConstraints);
    
    // 5. Create OK button
    _pOKButton = new CATDlgPushButton(_pMainFrame, "OK");
    _pOKButton->SetTitle("MyDialog.OKButton");
    
    // 6. Position button (row 1, col 0)
    CATDlgGridConstraints buttonConstraints(1, 0, 1, 1, CATGRID_CENTER);
    _pMainFrame->SetGridConstraints(_pOKButton, buttonConstraints);
    
    // 7. Register callback
    AddAnalyseNotificationCB(
        _pOKButton,
        _pOKButton->GetPushBActivateNotification(),
        (CATCommand::CATCommandMethod)&MyDialog::OnOKClicked,
        NULL
    );
    
    // 8. Set main frame layout
    CATDlgGridConstraints mainConstraints(0, 0, 1, 1, CATGRID_4SIDES);
    SetGridConstraints(_pMainFrame, mainConstraints);
}
```

---

#### Grid Layout Explained

**CATDlgGridConstraints Parameters:**
```cpp
CATDlgGridConstraints(row, col, rowSpan, colSpan, sides)
```

- `row` - Grid row (0-based)
- `col` - Grid column (0-based)
- `rowSpan` - Number of rows to occupy
- `colSpan` - Number of columns to occupy
- `sides` - Attachment sides:
  - `CATGRID_4SIDES` - Fill entire cell
  - `CATGRID_LEFT` - Align left
  - `CATGRID_RIGHT` - Align right
  - `CATGRID_TOP` - Align top
  - `CATGRID_BOTTOM` - Align bottom
  - `CATGRID_CENTER` - Center in cell

**Example Layout:**
```
┌─────────────────────────┐
│ Label (0,0)  Editor(0,1)│  Row 0
├─────────────────────────┤
│     Button (1,0-1)      │  Row 1 (spans 2 cols)
└─────────────────────────┘
```

---

#### Callback Implementation
```cpp
void MyDialog::OnOKClicked(CATCommand* iFrom, 
                           CATNotification* iNotification, 
                           CATCommandClientData iData)
{
    // 1. Get input value
    CATUnicodeString input = _pInputEditor->GetText();
    
    // 2. Validate
    if (input.GetLengthInChar() == 0) {
        cout << "Error: Input is empty" << endl;
        return;
    }
    
    // 3. Process data
    cout << "User input: " << input.ConvertToChar() << endl;
    
    // 4. Close dialog
    SetVisibility(CATDlgHide);
    RequestDelayedDestruction();  // Safe deletion
}
```

---

### Step 4: Resource Files

#### English Strings (MyFramework.CATNls)
```
MyDialog.Title = "My Custom Dialog";
MyDialog.OKButton = "OK";
MyDialog.CancelButton = "Cancel";
```

**Location:** `Framework.edu/CNext/resources/msgcatalog/MyFramework.CATNls`

#### Chinese Strings (Optional)
```
MyDialog.Title = "我的自定义对话框";
MyDialog.OKButton = "确定";
MyDialog.CancelButton = "取消";
```

**Location:** `Framework.edu/CNext/resources/msgcatalog/Chinese/MyFramework.CATNls`

---

### Step 5: Imakefile.mk

```makefile
BUILT_OBJECT_TYPE=SHARED LIBRARY

LINK_WITH=JS0GROUP JS0CORBA JS0FM
LINK_WITH=$(LINK_WITH) ApplicationFrame Dialog Visualization
```

**Critical:** Must link with `Dialog` and `ApplicationFrame`!

---

## 🎯 Common Controls Reference

### Input Controls

#### CATDlgEditor (Text Input)
```cpp
_pEditor = new CATDlgEditor(parent, "Name", CATDlgEdtString);
_pEditor->SetVisibleTextWidth(30);  // Width in characters
_pEditor->SetText("Initial value");
CATUnicodeString value = _pEditor->GetText();
```

**Editor Types:**
- `CATDlgEdtString` - Text string
- `CATDlgEdtInteger` - Integer only
- `CATDlgEdtReal` - Floating point
- `CATDlgEdtPassword` - Masked input

---

#### CATDlgCombo (Dropdown List)
```cpp
_pCombo = new CATDlgCombo(parent, "Name", CATDlgCmbDropDown);
_pCombo->SetVisibleTextWidth(20);

// Add items
_pCombo->SetLine("Option 1", 0);
_pCombo->SetLine("Option 2", 1);
_pCombo->SetLine("Option 3", 2);

// Set/Get selection
_pCombo->SetSelect(0);  // Select first item
int selected = _pCombo->GetSelect();
```

**Combo Styles:**
- `CATDlgCmbDropDown` - Dropdown (select only)
- `CATDlgCmbEntry` - Dropdown with text entry

---

#### CATDlgCheckButton (Checkbox)
```cpp
_pCheck = new CATDlgCheckButton(parent, "Name");
_pCheck->SetTitle("Enable Option");

// Set/Get state
_pCheck->SetState(CATDlgCheck);    // Checked
_pCheck->SetState(CATDlgUncheck);  // Unchecked

CATDlgCheck state = _pCheck->GetState();
bool checked = (state == CATDlgCheck);
```

---

#### CATDlgRadioButton (Radio Button)
```cpp
// Create group
_pRadio1 = new CATDlgRadioButton(parent, "Radio1");
_pRadio1->SetTitle("Option 1");

_pRadio2 = new CATDlgRadioButton(parent, "Radio2");
_pRadio2->SetTitle("Option 2");

// Set selection (only one can be checked in a group)
_pRadio1->SetState(CATDlgCheck);

// Check which is selected
if (_pRadio1->GetState() == CATDlgCheck) {
    cout << "Option 1 selected" << endl;
}
```

---

### Display Controls

#### CATDlgLabel (Text Label)
```cpp
_pLabel = new CATDlgLabel(parent, "Name");
_pLabel->SetTitle("Label Text");
```

---

#### CATDlgSeparator (Visual Separator)
```cpp
_pSeparator = new CATDlgSeparator(parent, "Name", CATDlgCtrHorizontal);
```

**Orientations:**
- `CATDlgCtrHorizontal` - Horizontal line
- `CATDlgCtrVertical` - Vertical line

---

### Container Controls

#### CATDlgFrame (Container)
```cpp
_pFrame = new CATDlgFrame(parent, "Name", CATDlgGridLayout);
```

**Layout Types:**
- `CATDlgGridLayout` - Grid (recommended)
- `CATDlgFillLayout` - Single control fills frame
- `CATDlgBorderLayout` - North/South/East/West/Center

---

## 🔔 Notification Types

### Button Notifications
```cpp
GetPushBActivateNotification()  // Button clicked
```

### Combo Notifications
```cpp
GetComboSelectNotification()    // Selection changed
```

### Editor Notifications
```cpp
GetEditorModifyNotification()   // Text modified
GetEditorFocusInNotification()  // Got focus
GetEditorFocusOutNotification() // Lost focus
```

### CheckButton Notifications
```cpp
GetCheckBModifyNotification()   // State changed
```

---

## 🚀 How to Use the Dialog

### From a Command
```cpp
#include "MyDialog.h"
#include "CATApplicationFrame.h"

void MyCommand::Activate()
{
    CATApplicationFrame* pAppFrame = CATApplicationFrame::GetFrame();
    
    MyDialog* pDialog = new MyDialog(pAppFrame, "MyDialog");
    pDialog->Build();
    pDialog->SetVisibility(CATDlgShow);  // Show modal
    
    // Dialog will delete itself when closed
}
```

---

## 🐛 Common Mistakes

### ❌ Mistake 1: Not calling Build()
```cpp
MyDialog* pDlg = new MyDialog(NULL, "Dlg");
pDlg->SetVisibility(CATDlgShow);  // WRONG! UI not created
```

**✅ Correct:**
```cpp
MyDialog* pDlg = new MyDialog(NULL, "Dlg");
pDlg->Build();  // MUST call this!
pDlg->SetVisibility(CATDlgShow);
```

---

### ❌ Mistake 2: Manually deleting dialog
```cpp
MyDialog* pDlg = new MyDialog(NULL, "Dlg");
pDlg->Build();
pDlg->SetVisibility(CATDlgShow);
delete pDlg;  // WRONG! Will crash
```

**✅ Correct:**
```cpp
// In callback:
SetVisibility(CATDlgHide);
RequestDelayedDestruction();  // Safe deletion
```

---

### ❌ Mistake 3: Wrong callback signature
```cpp
void OnOKClicked();  // WRONG! Missing parameters
```

**✅ Correct:**
```cpp
void OnOKClicked(CATCommand*, CATNotification*, CATCommandClientData);
```

---

### ❌ Mistake 4: Forgetting CATImplementClass
```cpp
// MyDialog.cpp
// Missing: CATImplementClass(MyDialog, Implementation, CATDlgDialog, CATNull);
```

**✅ Correct:**
```cpp
CATImplementClass(MyDialog, Implementation, CATDlgDialog, CATNull);
```

---

## 📊 Dialog Styles

### Modal vs Non-Modal

**Modal (blocks):**
```cpp
CATDlgDialog(parent, name, CATDlgWndModal | CATDlgGridLayout)
```

**Non-Modal (doesn't block):**
```cpp
CATDlgDialog(parent, name, CATDlgWndNoModal | CATDlgGridLayout)
```

---

## 🎨 Advanced: Custom Validation

```cpp
bool MyDialog::ValidateInput()
{
    CATUnicodeString input = _pInputEditor->GetText();
    
    // Check length
    if (input.GetLengthInChar() < 3) {
        ShowErrorMessage("Input must be at least 3 characters");
        return false;
    }
    
    // Check numeric
    const char* cstr = input.ConvertToChar();
    for (int i = 0; cstr[i] != '\0'; i++) {
        if (!isdigit(cstr[i])) {
            ShowErrorMessage("Input must be numeric");
            return false;
        }
    }
    
    return true;
}

void MyDialog::ShowErrorMessage(const char* message)
{
    // Create simple error dialog
    CATDlgNotify* pNotify = new CATDlgNotify(
        this, 
        "ErrorDialog", 
        CATDlgNfyError
    );
    pNotify->DisplayBlocked(message);
    pNotify->RequestDelayedDestruction();
}
```

---

## ✅ Checklist

Before compiling your dialog:

- [ ] IdentityCard.h includes `Dialog` and `ApplicationFrame`
- [ ] Header declares `CATDeclareClass` macro
- [ ] Implementation has `CATImplementClass` macro
- [ ] Build() method creates all controls
- [ ] Grid constraints set for each control
- [ ] Callbacks registered with `AddAnalyseNotificationCB`
- [ ] Resource files created (.CATNls, .CATRsc)
- [ ] Imakefile.mk links with `Dialog` framework
- [ ] Callbacks use `RequestDelayedDestruction()` to close

---

## 🔗 See Also

- **AI_GUIDE.md** - AI generation rules
- **FAQ.md** - Common questions
- **TROUBLESHOOTING_FLOWCHART.md** - Fix compile errors

---

**Complete template files available in:** `templates/dialog/`
