//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <DialogClassName>.cpp
//===================================================================

#include "<DialogClassName>.h"
#include "CATDlgFrame.h"
#include "CATDlgLabel.h"
#include "CATDlgEditor.h"

<DialogClassName>::<DialogClassName>(CATDialog *iParent)
    : CATDlgDialog(iParent, "<DialogClassName>Id", CATDlgWndBtnClose | CATDlgGridLayout)
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
    _pFrame = new CATDlgFrame(this, "FrameId", CATDlgFraNoTitle | CATDlgGridLayout);

    _pLabel = new CATDlgLabel(_pFrame, "LabelId");
    _pLabel->SetTitle("Value:");

    _pEditor = new CATDlgEditor(_pFrame, "EditorId");
    _pEditor->SetVisibleTextWidth(20);
}
