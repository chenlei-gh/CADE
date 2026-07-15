//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <DialogClassName>.cpp
//===================================================================

#include "<DialogClassName>.h"
#include "CATDlgFrame.h"
#include "CATDlgLabel.h"
#include "CATDlgEditor.h"
#include "CATUnicodeString.h"

CATImplementClass(<DialogClassName>, DataExtension, CATDlgDialog, <ModuleName>);

<DialogClassName>::<DialogClassName>(CATDialog *iParent, const CATString &iName)
    : CATDlgDialog(iParent, iName, CATDlgWndModal | CATDlgWndOKCancel)
    , _pFrame(NULL)
    , _pLabel(NULL)
    , _pEditor(NULL)
{
}

<DialogClassName>::~<DialogClassName>()
{
}

void <DialogClassName>::Build()
{
    _pFrame = new CATDlgFrame(this, "Frame", CATDlgFraNoFrame | CATDlgGridLayout);

    _pLabel = new CATDlgLabel(_pFrame, "Label");
    _pLabel->SetTitle("Value:");

    _pEditor = new CATDlgEditor(_pFrame, "Editor");
    _pEditor->SetVisibleTextWidth(20);
}

void <DialogClassName>::GetValue(CATUnicodeString &oValue) const
{
    if (_pEditor)
        _pEditor->GetTitle(oValue);
}
