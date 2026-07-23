//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <DialogClassName>.h
// [CADE] 本文件由 CADE 模板生成。创建新对话框请调 develop() 重新生成，
//        不要复制本文件改名——否则会继承旧骨架的历史 bug 并错过模板更新。
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
