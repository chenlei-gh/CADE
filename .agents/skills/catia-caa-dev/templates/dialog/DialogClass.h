//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <DialogClassName>.h
//===================================================================

#ifndef <DialogClassName>_H
#define <DialogClassName>_H

#include "CATDlgDialog.h"

class CATDlgFrame;
class CATDlgLabel;
class CATDlgEditor;

class <DialogClassName> : public CATDlgDialog
{
    CATDeclareClass;

public:
    <DialogClassName>(CATDialog *iParent, const CATString &iName);
    virtual ~<DialogClassName>();

    void Build();
    void GetValue(CATUnicodeString &oValue) const;

private:
    CATDlgFrame  *_pFrame;
    CATDlgLabel  *_pLabel;
    CATDlgEditor *_pEditor;
};

#endif
