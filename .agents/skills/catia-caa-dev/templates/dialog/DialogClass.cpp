//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// <DialogClassName>.cpp
// [CADE] 本文件由 CADE 模板生成。创建新对话框请调 develop() 重新生成，
//        不要复制本文件改名——否则会继承旧骨架的历史 bug 并错过模板更新。
//===================================================================

#include "<DialogClassName>.h"
#include "CATDlgFrame.h"
#include "CATDlgLabel.h"
#include "CATDlgEditor.h"
#include "CATMsgCatalog.h"

//-------------------------------------------------------------------
// NLS helper: read message from the framework catalog with fallback.
//
// 模式（生产实证，优于零代码控制路径）：
//   SetTitle(NLS("<DialogClassName>.LabelId", "Value:"));
//   - key 用语义名（类名前缀），可读性高、不受控件对象名约束
//   - fallback 保底：catalog 丢失/缺 key 时仍显示英文，不会空白
//   - 动态文本（列标题、模式切换）天然支持
// catalog 文件（GBK 编码的中文版放 Simplified_Chinese/ 子目录）：
//   CNext/resources/msgcatalog/<FrameworkName>.CATNls                    (英文)
//   CNext/resources/msgcatalog/Simplified_Chinese/<FrameworkName>.CATNls (中文)
//   条目示例: <DialogClassName>.LabelId = "Value:";
//-------------------------------------------------------------------
static CATUnicodeString NLS(const CATString &iKey, const char *iFallback)
{
    return CATMsgCatalog::BuildMessage(
        "<FrameworkName>", iKey, NULL, 0, iFallback);
}

<DialogClassName>::<DialogClassName>(CATDialog *iParent)
    // 布局选型（生产实证，详见 knowledge/ui/dialog_layout.md）：
    //   - 单一表单 → CATDlgGridLayout（本模板默认）
    //   - 多区域垂直堆叠/动态显隐面板 → 去掉 GridLayout，用 attachment 布局：
    //       窗口风格 CATDlgWndAutoResize|CATDlgWndBtnOKCancel|CATDlgWndNoResize
    //       SetHorizontalAttachment(0, CATDlgTopOrLeft, pCtrl, NULL) 逐行堆叠
    //       动态面板用 ResetAttachment(pCtrl) 摘除（不占空间，窗口自动收缩）
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
    // 窗口标题也走 NLS（catalog key: <DialogClassName>.Title）
    SetTitle(NLS("<DialogClassName>.Title", "<DialogClassName>"));

    _pFrame = new CATDlgFrame(this, "FrameId", CATDlgFraNoTitle | CATDlgGridLayout);

    _pLabel = new CATDlgLabel(_pFrame, "LabelId");
    _pLabel->SetTitle(NLS("<DialogClassName>.LabelId", "Value:"));
    _pLabel->SetGridConstraints(0, 0, 1, 1, CATGRID_RIGHT);

    _pEditor = new CATDlgEditor(_pFrame, "EditorId");
    _pEditor->SetVisibleTextWidth(20);   // 可见字符数定宽，不用像素
    _pEditor->SetGridConstraints(0, 1, 1, 1, CATGRID_LEFT | CATGRID_RIGHT);
}
