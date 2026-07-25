// COPYRIGHT DASSAULT SYSTEMES 2026
// [CADE] 模板生成文件。创建新命令请调 develop() 重新生成，勿复制改名。
#include "<CommandHeaderClassName>.h"
#include "CATCommandHeader.h"
// ⚠️ 2026-07 对 B28 全目录核实：CATAfrCommandHeader 类不存在（捏造），已移除。
// 官方推荐方式只有 MacDeclareHeader 宏（CATCommandHeader.h L1138 实证）。
// 需要自定义 header 时派生 CATAfrDialogCommandHeader（真实存在，见
// ApplicationFrame/PublicInterfaces/CATAfrDialogCommandHeader.h）。

// Command class
#include "<CommandClassName>.h"

//-----------------------------------------------------------------------------
// Create Command Header
//-----------------------------------------------------------------------------
void <CommandHeaderClassName>::CreateCommandHeader()
{
    // 官方推荐：MacDeclareHeader 宏同时声明+定义一个可用的 header 类，
    // 默认带按钮/菜单表示，绝大多数命令足够用（CATCommandHeader.h 文档原话：
    // "In most cases it is sufficient"）。
    MacDeclareHeader(<CommandHeaderName>);
}

//-----------------------------------------------------------------------------
// 需要自定义可用性/表示时：派生 CATAfrDialogCommandHeader
//-----------------------------------------------------------------------------
/*
// 自定义 header 必须（CATCommandHeader.h 文档）：
//   1. 派生 CATCommandHeader（自定义可用性）或 CATAfrDialogCommandHeader（自定义表示）
//   2. public: 调用基类构造的构造函数、析构、Clone()
//   3. private: 带 CATCommandHeader* 参数的构造函数（调基类对应构造）
//   4. 作为组件：.h 里 CATDeclareClass，.cpp 里 CATImplementClass
// 参考：ApplicationFrame/PublicInterfaces/CATAfrDialogCommandHeader.h
*/
