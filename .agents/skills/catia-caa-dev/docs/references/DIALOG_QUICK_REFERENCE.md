# CATIA Dialog Quick Reference

> **⚠️ 重要修正（2026-08-14）**：本速查表经虚构 API 审计后已整体重写。以下虚构/错误名字已全部替换为经 `knowledge/ui/*`、`patterns/ui/*`（2026-07-23 审计通过）与 SDK 头文件交叉验证的真实 API：
>
> | 虚构 / 错误 | 真实 API | 依据 |
> |---|---|---|
> | `CATDlgEdtString` / `CATDlgEdtInteger` / `CATDlgEdtReal` / `CATDlgEdtPassword` | 不存在。`CATDlgEditor(parent, name)` 不加类型风格位；取数值用 `GetIntegerValue()` / `GetFloatValue()`，密码掩码用编辑器自身风格位（见 `CATDlgEditor.h`） | SDK 枚举零匹配 + dialog.md |
> | `CATDlgCmbDropDown` / `CATDlgCmbEntry` | 不存在。`CATDlgCombo(parent, name)` 默认即下拉；追加项 `SetLine(text, -1)`，可见行数 `SetVisibleTextHeight(n)` | SDK 枚举零匹配 + dialog_layout.md §Combo |
> | `CATDlgCtrHorizontal` / `CATDlgCtrVertical` | 不存在。`CATDlgSeparator(parent, name)` 构造无方向参数，方向由 grid 约束决定 | SDK 枚举零匹配 + dialog_layout.md §Separator |
> | `CATDlgNfyError` + `DisplayBlocked(msg)` | 不存在。真实是 `CATDlgNotify(this, "Error")` + `SetText(...)` + `SetVisibility(CATDlgShow)` | dialog_layout.md §验证输入 |
> | `CATDlgFillLayout` / `CATDlgBorderLayout` | 不存在。Frame 布局风格只有 `CATDlgGridLayout`；外观风格只有 `CATDlgFraNoTitle` / `CATDlgFraNoFrame` / `CATDlgFraNoMargin` | dialog_layout.md §重要修正 |
> | `CATNull`（`CATImplementClass` 第4参） | 虚构宏族，用 `NULL` | 本项目 mecmod 审计结论 |
> | `GetCheckBModifyNotification()` | 虚构方法名，真实是 `GetChkBModifyNotification()` | SDK 头文件 |
> | `GetEditorModifyNotification()` / `GetEditorFocusInNotification()` / `GetEditorFocusOutNotification()` | 虚构方法名，真实是 `GetEditModifyNotification()` / `GetEditFocusInNotification()` / `GetEditFocusOutNotification()` | SDK 头文件 |
> | `GetRadioBModifyNotification()` | 虚构方法名，真实是 `GetRadBModifyNotification()` | SDK 头文件 |
> | `parentFrame->SetGridConstraints(child, gc)` 两参形式 | 不存在。真实是**子控件自己调** `child->SetGridConstraints(CATDlgGridConstraints(...))` 单参，或 `child->SetGridConstraints(row, col, rspan, cspan, anchor)` 5 参重载 | dialog_layout.md §GridConstraints（CATDialog.h L577/L606） |
> | `CATDlgWndNoModal` | 不存在。**非模态 = 不传 `CATDlgWndModal` 位**，不是换一个常量 | SDK 枚举零匹配 |
> | `.CATRsc` 设 `MyDialog.Width/Height` | 虚构惯用法。`.CATRsc` 只用于图标；dialog 初始大小用 `SetRectDimensions(x, y, height, width)`（注意 h/w 顺序）或 `CATDlgWndAutoResize` | dialog_layout.md §对话框初始大小 |
> | 硬编码 `SetTitle("...")` 英文 | 真实惯用法：`CATMsgCatalog::BuildMessage(catalog, key, NULL, 0, fallback)`，英文 fallback 编译进二进制 | dialog_dataflow.md §NLS |
>
> **误报已复核（工具 NOT-FOUND 但真实存在，予以保留）**：`CATDlgWndModal`、`CATDlgGridLayout`、`CATGRID_LEFT`、`CATGRID_RIGHT`、`CATGRID_CENTER`、`CATGRID_4SIDES`、`CATDlgShow`、`CATDlgHide`、`CATDlgCheck`、`CATDlgUncheck`、`CATDlgEnable`、`CATDlgDisable`。这些是枚举成员/宏常量，不在工具索引内，但在已审计知识文件（dialog.md L58/L80/L104、dialog_layout.md L26/L186-211/L413-418 等）与生产项目中有实证。
>
> **示例自有方法（非 CAA API，误报）**：`MyDialog` / `OnOKClicked` / `ValidateInput` / `ShowError`。

> Quick lookup for common Dialog controls and patterns

---

## 🎨 Common Controls Cheat Sheet

All controls share the same constructor shape: `(CATDialog* iParent, const CATString& iName, CATDlgStyle iStyle=NULL)`.
**There is no title/text constructor argument** — visible text comes from NLS or `SetTitle()`.

Text is always set via `CATMsgCatalog::BuildMessage` with an English fallback compiled into the binary:

```cpp
static CATUnicodeString NLS(const char* iKey, const char* iFallback)
{
    return CATMsgCatalog::BuildMessage("MyFramework", iKey, NULL, 0, iFallback);
}
```

### CATDlgEditor (Text Input)
```cpp
// Create — no CATDlgEdtString / CATDlgEdtInteger / ... constants exist.
_pEditor = new CATDlgEditor(parent, "Name");
_pEditor->SetVisibleTextWidth(30);

// Set/Get value
_pEditor->SetText(CATUnicodeString("Initial text"));
CATUnicodeString text = _pEditor->GetText();
```

**Reading typed values (real methods):** `GetText()` → `CATUnicodeString`; `GetIntegerValue()` / `SetIntegerValue(int)`; `GetFloatValue()` / `SetFloatValue(double)`. Password masking is an editor *style bit* documented in `CATDlgEditor.h`, not a `CATDlgEdt*` constant.

---

### CATDlgPushButton (Button)
```cpp
// Create
_pButton = new CATDlgPushButton(parent, "Name");
_pButton->SetTitle(NLS("MyDialog.ButtonLabel", "Apply"));

// Register callback
AddAnalyseNotificationCB(
    _pButton,
    _pButton->GetPushBActivateNotification(),
    (CATCommandMethod)&MyClass::OnButtonClicked,
    NULL
);

// Callback signature
void OnButtonClicked(CATCommand*, CATNotification*, CATCommandClientData);
```

---

### CATDlgCombo (Dropdown)
```cpp
// Create — no CATDlgCmbDropDown / CATDlgCmbEntry constants; default ctor is a dropdown.
_pCombo = new CATDlgCombo(parent, "Name");
_pCombo->SetVisibleTextWidth(20);
_pCombo->SetVisibleTextHeight(5);   // visible rows in the drop-down

// Add items: -1 = append
_pCombo->SetLine(CATUnicodeString("Item 1"), -1);
_pCombo->SetLine(CATUnicodeString("Item 2"), -1);
_pCombo->SetLine(CATUnicodeString("Item 3"), -1);

// Set/Get selection
_pCombo->SetSelect(0);
int selected = _pCombo->GetSelect();   // -1 = nothing selected

// Callback
AddAnalyseNotificationCB(
    _pCombo,
    _pCombo->GetComboSelectNotification(),
    (CATCommandMethod)&MyClass::OnComboChanged,
    NULL
);
```

---

### CATDlgCheckButton (Checkbox)
```cpp
// Create
_pCheck = new CATDlgCheckButton(parent, "Name");
_pCheck->SetTitle(NLS("MyDialog.CheckLabel", "Enable Option"));

// Set/Get state (CATDlgCheck / CATDlgUncheck are real state constants)
_pCheck->SetState(CATDlgCheck);    // Checked
_pCheck->SetState(CATDlgUncheck);  // Unchecked
bool checked = (_pCheck->GetState() == CATDlgCheck);

// Callback — real method name is GetChkBModifyNotification (ChkB, not CheckB)
AddAnalyseNotificationCB(
    _pCheck,
    _pCheck->GetChkBModifyNotification(),
    (CATCommandMethod)&MyClass::OnCheckChanged,
    NULL
);
```

---

### CATDlgRadioButton (Radio Button)
```cpp
// Create group (only one can be selected; mutual exclusion handled manually in callback)
_pRadio1 = new CATDlgRadioButton(parent, "Radio1");
_pRadio1->SetTitle(NLS("MyDialog.Option1", "Option 1"));
_pRadio2 = new CATDlgRadioButton(parent, "Radio2");
_pRadio2->SetTitle(NLS("MyDialog.Option2", "Option 2"));

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
_pLabel->SetTitle(NLS("MyDialog.LabelText", "Label Text"));
```

---

### CATDlgFrame (Container)
```cpp
_pFrame = new CATDlgFrame(parent, "Name", CATDlgGridLayout);
```

**Frame style bits (real, complete list):** `CATDlgGridLayout` (grid layout), `CATDlgFraNoTitle` (hide title bar), `CATDlgFraNoFrame` (no border), `CATDlgFraNoMargin` (no inner margin). A titled group box = default Frame (no `CATDlgFraNoTitle`) + `SetTitle(...)`. `CATDlgFillLayout` / `CATDlgBorderLayout` / `CATDlgFraGroupFrame` do **not** exist.

---

### CATDlgSeparator (Visual Line)
```cpp
// Constructor has NO orientation argument (CATDlgCtrHorizontal / CATDlgCtrVertical
// do not exist). Orientation/length is governed by the grid constraints.
_pSeparator = new CATDlgSeparator(parent, "Name");
_pSeparator->SetGridConstraints(
    CATDlgGridConstraints(row, 0, 1, 2, CATGRID_LEFT | CATGRID_RIGHT));
```

---

## 📐 Grid Layout

### Set Grid Constraints

`SetGridConstraints` is called **on the child control** (single-arg object or 5-arg overload — the two-arg `parent->SetGridConstraints(child, gc)` form does **not** exist):

```cpp
// single-arg object form
control->SetGridConstraints(CATDlgGridConstraints(row, col, rowSpan, colSpan, anchor));
// 5-arg overload (equally valid, more compact)
control->SetGridConstraints(row, col, rowSpan, colSpan, anchor);
```

**Parameters:**
- `row` - Grid row (0-based)
- `col` - Grid column (0-based)
- `rowSpan` - Number of rows to span
- `colSpan` - Number of columns to span
- `anchor` - Justification flags:
  - `CATGRID_4SIDES` - Fill entire cell
  - `CATGRID_LEFT` - Align left
  - `CATGRID_RIGHT` - Align right
  - `CATGRID_TOP` - Align top
  - `CATGRID_BOTTOM` - Align bottom
  - `CATGRID_CENTER` - Center
  - (also `CATGRID_CST_WIDTH` / `CATGRID_CST_HEIGHT` / `CATGRID_CST_SIZE` for fixed size)

Horizontal fill = `CATGRID_LEFT | CATGRID_RIGHT`; vertical fill = `CATGRID_TOP | CATGRID_BOTTOM`.

### Example Layout
```cpp
// Row 0: Label | Editor
_pLabel = new CATDlgLabel(frame, "Label");
_pLabel->SetGridConstraints(CATDlgGridConstraints(0, 0, 1, 1, CATGRID_LEFT));

_pEditor = new CATDlgEditor(frame, "Editor");
_pEditor->SetGridConstraints(CATDlgGridConstraints(0, 1, 1, 1,
    CATGRID_LEFT | CATGRID_RIGHT));

// Row 1: Button spanning 2 columns
_pButton = new CATDlgPushButton(frame, "Button");
_pButton->SetGridConstraints(CATDlgGridConstraints(1, 0, 1, 2, CATGRID_CENTER));
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
- `CATDlgWndModal` - Blocks until closed. **No `CATDlgWndNoModal` exists**: a non-modal dialog simply *omits* the `CATDlgWndModal` bit.
- `CATDlgGridLayout` - Use grid layout
- Standard button row: OR in `CATDlgWndBtnOKCancel` for built-in OK/Cancel buttons.

---

### Build Method
```cpp
void MyDialog::Build()
{
    // 1. Set title (NLS with fallback)
    SetTitle(NLS("MyDialog.Title", "My Dialog"));

    // 2. Create main frame
    _pMainFrame = new CATDlgFrame(this, "MainFrame",
        CATDlgFraNoFrame | CATDlgGridLayout);

    // 3. Create controls (no "type" style constant on the editor)
    _pEditor = new CATDlgEditor(_pMainFrame, "Editor");

    // 4. Set layout — called ON THE CHILD
    _pEditor->SetGridConstraints(
        CATDlgGridConstraints(0, 0, 1, 1, CATGRID_LEFT | CATGRID_RIGHT));

    // 5. Register callbacks
    AddAnalyseNotificationCB(...);

    // 6. Set main frame layout (5-arg overload; both forms are real)
    _pMainFrame->SetGridConstraints(0, 0, 1, 1, CATGRID_4SIDES);

    // 7. (optional) initial size — NOT via .CATRsc Width/Height
    // SetRectDimensions(1, 1, 300, 400);   // (x, y, height, width) mind h/w order!
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

### .CATNls (String Resources, English, UTF-8)
```
# Location: Framework.edu/CNext/resources/msgcatalog/MyFramework.CATNls

MyDialog.Title = "My Dialog Title";
MyDialog.OKButton = "OK";
MyDialog.CancelButton = "Cancel";
MyDialog.InputLabel = "Enter value:";
```

> Chinese translations go in `msgcatalog/Simplified_Chinese/MyFramework.CATNls` (**GBK-encoded, no emoji**). A flat `Xxx_Chinese.CATNls` next to the English file is **not** loaded.

### .CATRsc (Visual Resources — icons only, NOT dialog size)
```
# Location: Framework.edu/CNext/resources/msgcatalog/MyFramework.CATRsc
# .CATRsc carries icon references for command headers, e.g.:
# MyFramework.MyCmdHdr.Icon.Normal = "I_MyCmd";
```

> Dialog width/height is **not** set via `.CATRsc`. Use `SetRectDimensions(x, y, height, width)`
> in `Build()` (note the h/w argument order), or the `CATDlgWndAutoResize` window style to
> size the dialog to its content.

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
    pDialog->SetVisibility(CATDlgShow);  // Blocks here (constructed with CATDlgWndModal)

    // Dialog deletes itself when closed
}
```

### Non-Modal (Doesn't Block)
```cpp
void ShowDialogNonModal()
{
    CATApplicationFrame* pFrame = CATApplicationFrame::GetFrame();

    // Build the dialog WITHOUT the CATDlgWndModal style bit (no CATDlgWndNoModal exists)
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
    // Real notification dialog: CATDlgNotify + SetText, no CATDlgNfyError flag.
    CATDlgNotify* pNotify = new CATDlgNotify(this, "Error");
    pNotify->SetText(CATUnicodeString(message));
    pNotify->SetVisibility(CATDlgShow);
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

| Control | Notification | Get Method (real name) |
|---------|-------------|------------------------|
| CATDlgPushButton | Button clicked | `GetPushBActivateNotification()` |
| CATDlgCombo | Selection changed | `GetComboSelectNotification()` |
| CATDlgEditor | Text modified | `GetEditModifyNotification()` |
| CATDlgEditor | Got focus | `GetEditFocusInNotification()` |
| CATDlgEditor | Lost focus | `GetEditFocusOutNotification()` |
| CATDlgCheckButton | State changed | `GetChkBModifyNotification()` |
| CATDlgRadioButton | State changed | `GetRadBModifyNotification()` |
| CATDlgDialog | OK / Cancel | `GetDiaOKNotification()` / `GetDiaCANCELNotification()` |

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
CATImplementClass(MyDialog, Implementation, CATDlgDialog, NULL);
```

---

## 🔗 Full Documentation

- **EXAMPLE_DIALOG.md** - Complete tutorial with explanations
- **knowledge/ui/dialog.md** - Audited widget/notification facts
- **knowledge/ui/dialog_layout.md** - Audited grid layout and advanced controls
- **knowledge/ui/dialog_dataflow.md** - NLS / BuildMessage pattern
- **templates/dialog/** - Ready-to-use template files

---

**Quick Start:** Copy templates from `templates/dialog/`, replace `<DialogClassName>` placeholders, compile!
