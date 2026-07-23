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
    // ⚠️ 不要在这里调用 SetTitle("英文文本")——硬编码字符串会覆盖 CATIA 的
    // 自动 NLS 查找，导致中文环境下仍显示英文。
    //
    // 正确做法（官方模式，见 CAAAfrBoundingElementCmd 样例）：
    // 控件只用对象名创建，显示文本全部走 msgcatalog 资源：
    //   <DialogClassName>.CATNls                          （英文/默认）
    //   Simplified_Chinese/<DialogClassName>.CATNls       （中文）
    // catalog 文件名必须等于对话框 C++ 类名（默认资源名），
    // key = 控件对象名路径 + 属性，例如：
    //   Title = "My Dialog";                    （对话框窗口标题）
    //   FrameId.LabelId.Title = "Value:";       （FrameId 下 LabelId 的标题）
    // CATIA 在 Build 时按当前语言自动解析，无需任何代码。

    _pFrame = new CATDlgFrame(this, "FrameId", CATDlgFraNoTitle | CATDlgGridLayout);

    _pLabel = new CATDlgLabel(_pFrame, "LabelId");

    _pEditor = new CATDlgEditor(_pFrame, "EditorId");
    _pEditor->SetVisibleTextWidth(20);
}
