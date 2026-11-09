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
#include "CATUnicodeString.h"

class CATDlgFrame;
class CATDlgLabel;
class CATDlgEditor;

class <DialogClassName> : public CATDlgDialog
{
    DeclareResource(<DialogClassName>, CATDlgDialog);

public:
    // 构造函数仅做成员初始化，严禁在构造函数中创建子控件
    <DialogClassName>(CATDialog *iParent);
    virtual ~<DialogClassName>();

    // 两阶段构造核心：在外部（如 StateCommand::BuildGraph）显式调用 Build() 实例化控件与 NLS 绑定
    void Build();

    // MVP View 层数据访问接口（避免外部直接耦合内部控件树）
    CATUnicodeString GetInputValue() const;
    void SetInputValue(const CATUnicodeString &iValue);

private:
    CATDlgFrame  *_pFrame;
    CATDlgLabel  *_pLabel;
    CATDlgEditor *_pEditor;

    // 禁用拷贝构造与赋值
    <DialogClassName>(const <DialogClassName> &iObjectToCopy);
    <DialogClassName>& operator=(const <DialogClassName> &iObjectToCopy);
};

#endif
