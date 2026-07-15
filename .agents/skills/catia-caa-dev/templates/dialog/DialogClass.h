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
    DeclareResource(<DialogClassName>,CATDlgDialog);

public:
    <DialogClassName>(CATDialog *iParent);
    virtual ~<DialogClassName>();

    void Build();

private:
    CATDlgFrame  *_pFrame;
    CATDlgLabel  *_pLabel;
    CATDlgEditor *_pEditor;

    // Copy constructor and assignment operator, not implemented
    <DialogClassName>(const <DialogClassName> &iObjectToCopy);
    <DialogClassName>& operator=(const <DialogClassName> &iObjectToCopy);
};

#endif
