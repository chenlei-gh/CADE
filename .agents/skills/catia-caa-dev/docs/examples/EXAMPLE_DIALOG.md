# CATIA Dialog Development - Complete Example

> **⚠️ 重要修正（2026-08-14）**：本示例经虚构 API 审计后已整体重写。以下虚构/错误名字已全部替换为经 `knowledge/ui/*`、`patterns/ui/*`（2026-07-23 审计通过）与 SDK 头文件交叉验证的真实 API：
>
> | 虚构 / 错误 | 真实 API | 依据 |
> |---|---|---|
> | `CATDlgEdtString` / `CATDlgEdtInteger` / `CATDlgEdtReal` / `CATDlgEdtPassword` | 不存在。`CATDlgEditor(parent, name)` 不加类型风格位；取数值用 `GetIntegerValue()` / `GetFloatValue()`，密码掩码用编辑器自身风格位（见 `CATDlgEditor.h`） | SDK 枚举零匹配 + dialog.md |
> | `CATDlgCmbDropDown` / `CATDlgCmbEntry` | 不存在。`CATDlgCombo(parent, name)` 默认即下拉；追加项 `SetLine(text, -1)`，可见行数 `SetVisibleTextHeight(n)` | SDK 枚举零匹配 + dialog_layout.md §Combo |
> | `CATDlgCtrHorizontal` / `CATDlgCtrVertical` | 不存在。`CATDlgSeparator(parent, name)` 构造无方向参数 | SDK 枚举零匹配 + dialog_layout.md §Separator |
> | `CATDlgNfyError` + `DisplayBlocked(msg)` | 不存在。真实是 `CATDlgNotify(this, "Warning")` + `SetText(...)` + `SetVisibility(CATDlgShow)` | dialog_layout.md §验证输入 |
> | `CATDlgFillLayout` / `CATDlgBorderLayout` | 不存在。Frame 布局风格只有 `CATDlgGridLayout`；外观风格只有 `CATDlgFraNoTitle` / `CATDlgFraNoFrame` / `CATDlgFraNoMargin` | dialog_layout.md §重要修正 |
> | `CATNull`（`CATImplementClass` 第4参） | 虚构宏族，用 `NULL` | 本项目 mecmod 审计结论 |
> | `GetCheckBModifyNotification()` | 虚构方法名，真实是 `GetChkBModifyNotification()` | SDK 头文件 |
> | `GetEditorModifyNotification()` / `GetEditorFocusInNotification()` / `GetEditorFocusOutNotification()` | 虚构方法名，真实是 `GetEditModifyNotification()` / `GetEditFocusInNotification()` / `GetEditFocusOutNotification()` | SDK 头文件 |
> | `GetRadioBModifyNotification()` | 虚构方法名，真实是 `GetRadBModifyNotification()` | SDK 头文件 |
> | `pContainer->SetGridConstraints(child, gc)` 两参形式 | 不存在。真实是**子控件自己调** `child->SetGridConstraints(CATDlgGridConstraints(...))` 单参，或 `child->SetGridConstraints(row, col, rspan, cspan, anchor)` 5 参重载 | dialog_layout.md §GridConstraints（CATDialog.h L577/L606） |
> | `CATDlgWndNoModal` | 不存在。**非模态 = 不传 `CATDlgWndModal` 位**，不是换一个常量 | SDK 枚举零匹配 |
> | 中文 catalog 目录 `Chinese/` | 真实目录是 `Simplified_Chinese/`（GBK 编码，不能含 emoji） | dialog_dataflow.md §NLS |
>
> **误报已复核（工具 NOT-FOUND 但真实存在，予以保留）**：`CATDlgWndModal`、`CATDlgGridLayout`、`CATGRID_4SIDES`、`CATGRID_CENTER`、`CATGRID_LEFT`、`CATGRID_RIGHT`、`CATDlgShow`、`CATDlgHide`、`CATDlgCheck`、`CATDlgUncheck`、`CATMsgCatalog::BuildMessage`。这些是枚举成员/宏常量，不在工具索引内，但在已审计知识文件与 SDK 头文件中有实证。
>
> **示例自有方法（非 CAA API，误报）**：`MyDialog` / `OnOKClicked` / `ValidateInput` / `ShowErrorMessage`。

> Complete working example of a CATIA CAA Dialog with all controls

**Version**: 1.1
**Framework**: Dialog, ApplicationFrame
**Target**: CATIA V5R28 (B28)

---

## 📋 Overview

This example demonstrates a complete Dialog implementation with:
- ✅ Input fields (CATDlgEditor)
- ✅ Dropdown lists (CATDlgCombo)
- ✅ Checkboxes (CATDlgCheckButton)
- ✅ Buttons with callbacks
- ✅ Grid layout management (CATDlgGridLayout + CATDlgGridConstraints)
- ✅ Resource files (NLS via CATMsgCatalog::BuildMessage)
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
            ├── MyFramework.CATNls         # English strings (UTF-8)
            └── Simplified_Chinese/        # Optional
                └── MyFramework.CATNls     # Chinese strings (GBK, no emoji)
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
4. **Declare callback methods** (CATCommandMethod signature)

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

**Constructor style flags (all real, verified):**
- `CATDlgWndModal` - Blocks until closed. **There is no `CATDlgWndNoModal`**: a non-modal dialog is built by simply *omitting* the `CATDlgWndModal` bit.
- `CATDlgGridLayout` - Enables the grid layout manager on the dialog/frame.
- Standard button row: OR in `CATDlgWndBtnOKCancel` (or `CATDlgWndOK | CATDlgWndCANCEL`) to get built-in OK/Cancel buttons.

---

#### NLS Helper

All user-visible text goes through `CATMsgCatalog::BuildMessage` with an English
fallback compiled into the binary (production-proven pattern):

```cpp
static CATUnicodeString NLS(const char* iKey, const char* iFallback)
{
    return CATMsgCatalog::BuildMessage("MyFramework", iKey, NULL, 0, iFallback);
}
```

---

#### Build Method

```cpp
void MyDialog::Build()
{
    // 1. Set title (NLS with fallback)
    SetTitle(NLS("MyDialog.Title", "My Custom Dialog"));

    // 2. Create main container (grid layout, no border)
    _pMainFrame = new CATDlgFrame(this, "MainFrame",
        CATDlgFraNoFrame | CATDlgGridLayout);

    // 3. Create input editor (no "type" style constant exists)
    _pInputEditor = new CATDlgEditor(_pMainFrame, "Input");
    _pInputEditor->SetVisibleTextWidth(30);   // width in characters

    // 4. Position editor in grid (row 0, col 0).
    //    NOTE: SetGridConstraints is called ON THE CHILD, single-arg form.
    _pInputEditor->SetGridConstraints(
        CATDlgGridConstraints(0, 0, 1, 1, CATGRID_LEFT | CATGRID_RIGHT));

    // 5. Create OK button (text comes from NLS, not a ctor arg)
    _pOKButton = new CATDlgPushButton(_pMainFrame, "OK");
    _pOKButton->SetTitle(NLS("MyDialog.OKButton", "OK"));

    // 6. Position button (row 1, col 0), centered
    _pOKButton->SetGridConstraints(
        CATDlgGridConstraints(1, 0, 1, 1, CATGRID_CENTER));

    // 7. Register callback
    AddAnalyseNotificationCB(
        _pOKButton,
        _pOKButton->GetPushBActivateNotification(),
        (CATCommandMethod)&MyDialog::OnOKClicked,
        NULL
    );

    // 8. Set main frame layout in the dialog's own grid
    //    (5-arg overload is equally valid; both are real)
    _pMainFrame->SetGridConstraints(0, 0, 1, 1, CATGRID_4SIDES);
}
```

---

#### Grid Layout Explained

**CATDlgGridConstraints constructor (real signature):**
```cpp
CATDlgGridConstraints(
    short iTopRow,             // row (0-based)
    short iLeftColumn,         // column (0-based)
    short iRowSpan,            // number of rows to span
    short iColumnSpan,         // number of columns to span
    unsigned int iJustification // anchor/fill flags
);
// A no-arg ctor + public Row/Column members also exist.
```

**Anchor / justification constants (real, complete list):**

| Constant | Meaning |
|----------|---------|
| `CATGRID_LEFT` | Anchor left |
| `CATGRID_RIGHT` | Anchor right |
| `CATGRID_TOP` | Anchor top |
| `CATGRID_BOTTOM` | Anchor bottom |
| `CATGRID_4SIDES` | Fill the whole cell (= LEFT\|RIGHT\|TOP\|BOTTOM) |
| `CATGRID_CST_WIDTH` | Fixed width |
| `CATGRID_CST_HEIGHT` | Fixed height |
| `CATGRID_CST_SIZE` | Fixed width and height |
| `CATGRID_CENTER` | Center in cell |

Horizontal fill = `CATGRID_LEFT | CATGRID_RIGHT`; vertical fill = `CATGRID_TOP | CATGRID_BOTTOM`.
There is **no** `CATGRID_HORIZONTAL` / `CATGRID_VERTICAL`.

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

#### English Strings (MyFramework.CATNls, UTF-8)
```
MyDialog.Title = "My Custom Dialog";
MyDialog.OKButton = "OK";
MyDialog.CancelButton = "Cancel";
```

**Location:** `Framework.edu/CNext/resources/msgcatalog/MyFramework.CATNls`

#### Chinese Strings (Optional, GBK encoding, no emoji)
```
MyDialog.Title = "我的自定义对话框";
MyDialog.OKButton = "确定";
MyDialog.CancelButton = "取消";
```

**Location:** `Framework.edu/CNext/resources/msgcatalog/Simplified_Chinese/MyFramework.CATNls`

> ⚠️ The Chinese catalog directory must be named `Simplified_Chinese` and the file
> must be **GBK-encoded** (B28 official Chinese catalogs are GBK; UTF-8 renders as
> mojibake). A flat `Xxx_Chinese.CATNls` next to the English one is **not** loaded.

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

All controls share the same constructor shape: `(CATDialog* iParent, const CATString& iName, CATDlgStyle iStyle=NULL)`.
**There is no title/text constructor argument** — visible text comes from NLS or `SetTitle()`.

### Input Controls

#### CATDlgEditor (Text Input)

```cpp
// No CATDlgEdtString / CATDlgEdtInteger / ... constants exist.
_pEditor = new CATDlgEditor(parent, "Name");
_pEditor->SetVisibleTextWidth(30);            // Width in characters
_pEditor->SetText(CATUnicodeString("Init"));  // Set text

CATUnicodeString value = _pEditor->GetText(); // Get text
```

**Reading typed values (real methods on CATDlgEditor):**
- `GetText()` → `CATUnicodeString` (any text)
- `GetIntegerValue()` / `SetIntegerValue(int)` — integer
- `GetFloatValue()` / `SetFloatValue(double)` — floating point
- Password masking is an editor *style bit* documented in `CATDlgEditor.h`, not a `CATDlgEdt*` constant.

---

#### CATDlgCombo (Dropdown List)

```cpp
// No CATDlgCmbDropDown / CATDlgCmbEntry constants exist; default ctor is a dropdown.
_pCombo = new CATDlgCombo(parent, "Name");
_pCombo->SetVisibleTextWidth(20);
_pCombo->SetVisibleTextHeight(5);   // visible rows in the drop-down

// Add items: -1 = append
_pCombo->SetLine(CATUnicodeString("Option 1"), -1);
_pCombo->SetLine(CATUnicodeString("Option 2"), -1);
_pCombo->SetLine(CATUnicodeString("Option 3"), -1);

// Set/Get selection
_pCombo->SetSelect(0);              // Select first item
int selected = _pCombo->GetSelect(); // -1 = nothing selected
```

---

#### CATDlgCheckButton (Checkbox)

```cpp
_pCheck = new CATDlgCheckButton(parent, "Name");
_pCheck->SetTitle(NLS("MyDialog.EnableOption", "Enable Option"));

// Set/Get state (CATDlgCheck / CATDlgUncheck are real state constants)
_pCheck->SetState(CATDlgCheck);    // Checked
_pCheck->SetState(CATDlgUncheck);  // Unchecked

bool checked = (_pCheck->GetState() == CATDlgCheck);
```

---

#### CATDlgRadioButton (Radio Button)

```cpp
// Create group
_pRadio1 = new CATDlgRadioButton(parent, "Radio1");
_pRadio1->SetTitle(NLS("MyDialog.Option1", "Option 1"));

_pRadio2 = new CATDlgRadioButton(parent, "Radio2");
_pRadio2->SetTitle(NLS("MyDialog.Option2", "Option 2"));

// Set selection (mutual exclusion is handled manually in the callback)
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
_pLabel->SetTitle(NLS("MyDialog.LabelText", "Label Text"));
```

---

#### CATDlgSeparator (Visual Separator)

```cpp
// Constructor has NO orientation argument (CATDlgCtrHorizontal / CATDlgCtrVertical
// do not exist). Orientation/length is governed by the grid constraints.
_pSeparator = new CATDlgSeparator(parent, "Name");
_pSeparator->SetGridConstraints(
    CATDlgGridConstraints(row, 0, 1, 2, CATGRID_LEFT | CATGRID_RIGHT));
```

---

### Container Controls

#### CATDlgFrame (Container)

```cpp
_pFrame = new CATDlgFrame(parent, "Name", CATDlgGridLayout);
```

**Frame style bits (real, complete list):**
- `CATDlgGridLayout` - Enable grid layout on the frame
- `CATDlgFraNoTitle` - Hide the title bar
- `CATDlgFraNoFrame` - No border
- `CATDlgFraNoMargin` - No inner margin

A titled group box = default Frame (do **not** add `CATDlgFraNoTitle`) + `SetTitle(...)`.
`CATDlgFillLayout` / `CATDlgBorderLayout` / `CATDlgFraGroupFrame` / `CATDlgFraSunkenFrame`
do **not** exist.

---

## 🔔 Notification Types

Each widget exposes `GetXxxNotification()` factory methods; hook them with `AddAnalyseNotificationCB`:

### Button Notifications
```cpp
GetPushBActivateNotification()    // Button clicked
```

### Combo Notifications
```cpp
GetComboSelectNotification()      // Selection changed
```

### Editor Notifications (real names — Edit, not Editor)
```cpp
GetEditModifyNotification()       // Text modified
GetEditFocusInNotification()      // Got focus
GetEditFocusOutNotification()     // Lost focus
```

### CheckButton Notifications (real name — ChkB, not CheckB)
```cpp
GetChkBModifyNotification()       // State changed
```

### RadioButton Notifications (real name — RadB, not RadioB)
```cpp
GetRadBModifyNotification()       // State changed
```

### CATDlgDialog itself
```cpp
GetDiaOKNotification()            // Standard OK button
GetDiaCANCELNotification()        // Standard Cancel button
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
// Missing: CATImplementClass(MyDialog, Implementation, CATDlgDialog, NULL);
```

**✅ Correct:**
```cpp
CATImplementClass(MyDialog, Implementation, CATDlgDialog, NULL);
```

---

## 📊 Dialog Styles

### Modal vs Non-Modal

**Modal (blocks):**
```cpp
CATDlgDialog(parent, name, CATDlgWndModal | CATDlgGridLayout)
```

**Non-Modal (doesn't block):** there is no `CATDlgWndNoModal` constant —
simply omit the `CATDlgWndModal` bit:
```cpp
CATDlgDialog(parent, name, CATDlgGridLayout)
```

Add `CATDlgWndBtnOKCancel` to either form to get the built-in OK/Cancel button row.

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
    // Real notification dialog: CATDlgNotify + SetText, no CATDlgNfyError flag.
    CATDlgNotify* pNotify = new CATDlgNotify(this, "ErrorDialog");
    pNotify->SetText(CATUnicodeString(message));
    pNotify->SetVisibility(CATDlgShow);
    pNotify->RequestDelayedDestruction();
}
```

---

## ✅ Checklist

Before compiling your dialog:

- [ ] IdentityCard.h includes `Dialog` and `ApplicationFrame`
- [ ] Header declares `CATDeclareClass` macro
- [ ] Implementation has `CATImplementClass(..., NULL)` macro
- [ ] Build() method creates all controls
- [ ] Grid constraints set on each child (`child->SetGridConstraints(...)`)
- [ ] Callbacks registered with `AddAnalyseNotificationCB`
- [ ] Resource files created (.CATNls; Chinese under `Simplified_Chinese/`, GBK)
- [ ] Imakefile.mk links with `Dialog` framework
- [ ] Callbacks use `RequestDelayedDestruction()` to close

---

## 🔗 See Also

- **knowledge/ui/dialog.md** — Audited widget/notification facts
- **knowledge/ui/dialog_layout.md** — Audited grid-layout and advanced controls
- **knowledge/ui/dialog_dataflow.md** — NLS / BuildMessage pattern
- **patterns/ui/dynamic_form.md**, **patterns/ui/master_detail.md** — Form dialog patterns

---

**Complete template files available in:** `templates/dialog/`
