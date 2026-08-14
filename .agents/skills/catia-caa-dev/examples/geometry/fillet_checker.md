---
id: geo.fillet_checker
title: Fillet Checker
category: example
domain: geometry
keywords: [fillet, check, analyzer, example, full project, dialog, listview]
apis: [CATIEdgeFillet, CATISpecObject, CATIPrtPart, CATDlgDialog, CATDlgSelectorList, CATFrmEditor, CATPathElement, CATCSO]
requires: [part.fillet, mecmod.feature, ui.dialog, infra.selection]
patterns: [analyzer.geometry, analyzer.rule, ui.result_dialog, block.visitor, block.locator]
examples: []
release: [R19, R28]
tags: [example, geometry, check, full-project]
difficulty: intermediate
---

> **⚠️ 重要修正（2026-08-14）**：本示例已经过虚构 API 审计并重写，以下虚构/过时 API 已替换为已核实真实 API（依据 `knowledge/`、`patterns/` 已核实文件及 `tools/build_caadoc_index.py --query` 复核）：
>
> | 虚构 / 过时 | 真实 API | 出处 |
> |---|---|---|
> | `CATDlgList` | `CATDlgSelectorList`（简单列表；多列需求用 `CATDlgTableView`） | [ui.dialog](../../knowledge/ui/dialog.md) |
> | `SetLine(i, cols, n)` 多列签名 | `SetLine(CATUnicodeString, -1)` 单行文本追加 | [ui.dialog](../../knowledge/ui/dialog.md) |
> | `CATUnicodeString::FromDouble(x)` | `CATUnicodeString::BuildFromNum(x)` | `build_caadoc_index.py --query CATUnicodeString` |
> | `CATFrmEditor::GetSelection()->SelectElement(path)` | `CATFrmEditor::GetCSO()` + `CATCSO::AddElement(new CATPathElement(...))` | [infra.selection](../../knowledge/infrastructure/selection.md) |
> | `CATFrmEditor::GetSelection()->Clear()` | `CATCSO::Empty()` | [infra.selection](../../knowledge/infrastructure/selection.md) |
> | `CATISO::ReframeOnObject(path)` | `CAT3DViewer::ReframeOn(CAT3DBoundingSphere&)` | [infra.selection](../../knowledge/infrastructure/selection.md)、[block.locator](../../patterns/blocks/locator.md) |
> | `CATIFillet_var` + `GetRadius()->Value()` | `CATIEdgeFillet_var` + `GetRadius()`（直接返回 double） | [part.fillet](../../knowledge/part/fillet.md) |
>
> 结构与思路不变；API 细节以 `knowledge/`、`patterns/` 已核实文件为准。

# Fillet Checker Example (圆角规范检查工具)

完整的 CAA 插件示例 —— 扫描当前 Part 的所有圆角，根据规范检查半径，结果显示在 Dialog 中，支持双击定位。

## 需求

1. 扫描所有 EdgeFillet
2. 检查半径是否在 [2mm, 20mm] 范围内
3. 在 Dialog 中显示结果（✓/✗、名称、半径）
4. 双击定位到对应圆角

## 项目结构

```
FilletChecker.framework
│
├── IdentityCard
│
├── FilletCheckerModule
│   │
│   ├── Imakefile
│   ├── PublicInterfaces/
│   ├── ProtectedInterfaces/
│   ├── LocalInterfaces/
│   │     ├── FilletAnalyzer.h       (分析逻辑)
│   │     └── FilletCheckerDlg.h     (对话框)
│   │
│   ├── src/
│   │     ├── FilletCheckerCmd.cpp   (命令入口)
│   │     ├── FilletCheckerHeader.cpp(命令注册)
│   │     ├── FilletAnalyzer.cpp     (分析实现)
│   │     └── FilletCheckerDlg.cpp   (对话框实现)
│   │
│   └── Resources/
│
├── Catalog
├── Dictionary
├── NLS
└── Icons
```

## 核心代码

### FilletAnalyzer.h

```cpp
#ifndef FilletAnalyzer_h
#define FilletAnalyzer_h

#include "CATBaseUnknown.h"
#include "CATLISTV_CATISpecObject.h"

struct FilletResult {
    CATISpecObject_var feature;
    CATUnicodeString name;
    double radius;
    CATUnicodeString status;
    CATUnicodeString problem;
};

class FilletAnalyzer {
public:
    FilletAnalyzer(double minR = 2.0, double maxR = 20.0);

    void Analyze(CATIPrtPart_var pPart);
    int GetResultCount() const;
    FilletResult GetResult(int index) const;

private:
    void Traverse(CATISpecObject_var pParent);
    void CheckFillet(CATISpecObject_var pFeature);

    double m_minRadius;
    double m_maxRadius;
    CATListOfFilletResult m_results;
};

#endif
```

### FilletAnalyzer.cpp

```cpp
#include "FilletAnalyzer.h"
#include "CATIPrtPart.h"
#include "CATIEdgeFillet.h"

FilletAnalyzer::FilletAnalyzer(double minR, double maxR)
    : m_minRadius(minR), m_maxRadius(maxR) {}

void FilletAnalyzer::Analyze(CATIPrtPart_var pPart) {
    m_results.Clear();
    CATISpecObject_var pRoot = pPart;
    Traverse(pRoot);
}

void FilletAnalyzer::Traverse(CATISpecObject_var pParent) {
    CATListValCATISpecObject_var children;
    pParent->GetChildren(children);

    for (int i = 1; i <= children.Size(); i++) {
        CATISpecObject_var child = children[i];
        CheckFillet(child);
        Traverse(child);
    }
}

void FilletAnalyzer::CheckFillet(CATISpecObject_var pFeature) {
    if (!pFeature->IsATypeOf("EdgeFillet")) return;

    // CATIFillet 只是空标记接口；带 GetRadius() 的是 CATIEdgeFillet
    CATIEdgeFillet_var pFillet = pFeature;
    if (NULL_var == pFillet) return;

    // GetRadius() 直接返回 double（仅 CONSTANT 类型有效），不是 ->Value()
    double radius = pFillet->GetRadius();

    FilletResult result;
    result.feature = pFeature;
    result.name = pFeature->GetName();
    result.radius = radius;

    if (radius < m_minRadius) {
        result.status = "FAIL";
        result.problem = "Radius too small";
    } else if (radius > m_maxRadius) {
        result.status = "FAIL";
        result.problem = "Radius too large";
    } else {
        result.status = "PASS";
        result.problem = "";
    }

    m_results.Append(result);
}
```

### FilletCheckerDlg.cpp (核心部分)

结果列表用 `CATDlgSelectorList`（真实控件，单行文本；✓/✗、名称、半径、问题拼进一行）。真正的多列表格用 `CATDlgTableView`，见 [ui.dialog](../../knowledge/ui/dialog.md)。

```cpp
void FilletCheckerDlg::ShowResults() {
    m_pList->ClearLine();    // m_pList: CATDlgSelectorList*

    for (int i = 0; i < m_analyzer.GetResultCount(); i++) {
        FilletResult r = m_analyzer.GetResult(i);

        // 多列信息拼进单行文本（CATDlgSelectorList::SetLine 只收单行）
        CATUnicodeString line;
        line.Append(r.status == "PASS" ? "[OK]   " : "[FAIL] ");
        line.Append(r.name);
        line.Append("  ");
        // CATUnicodeString::FromDouble 不存在；数字转字符串用 BuildFromNum
        line.Append(CATUnicodeString::BuildFromNum(r.radius));
        line.Append("mm");
        if (r.problem.GetLengthInChar() > 0) {
            line.Append("  — ");
            line.Append(r.problem);
        }
        m_pList->SetLine(line, -1);      // -1 = 追加
    }
}

// 双击通知挂接（CATDlgSelectorList 的激活通知）：
//   AddAnalyseNotificationCB(m_pList,
//       m_pList->GetListActivateNotification(),
//       (CATCommandMethod)&FilletCheckerDlg::OnDoubleClick, NULL);
// 行号经 GetSelectCount()/GetSelect(int*,int) 取得，见 ui.dialog。
void FilletCheckerDlg::OnDoubleClick(int line) {
    FilletResult r = m_analyzer.GetResult(line - 1);

    CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
    if (!pEditor) return;

    // 没有 GetSelection()/SelectElement；当前选择集是 CATCSO（GetCSO()）
    CATCSO* pCSO = pEditor->GetCSO();
    if (!pCSO) return;
    pCSO->Empty();
    pCSO->AddElement(new CATPathElement(r.feature));

    // 没有 ReframeOnObject；相机定位对 viewer 的包围球操作
    // CAT3DViewer* pViewer = ...;                  // 从 editor/窗口取得
    // CAT3DBoundingSphere bs = GetBoundingSphereOf(r.feature);
    // pViewer->ReframeOn(bs);
}
```

## 使用 CADE 创建此项目

```python
# AI 调用 CADE API
ctx = ActionContext(workspace="D:/CAA/MyWorkspace")

# 1. 创建 Framework + Module
ctx.execute("create_framework", name="FilletChecker")
ctx.execute("create_module", name="FilletCheckerModule", framework="FilletChecker")

# 2. 创建 Command (带 Dialog)
ctx.execute("create_command",
    name="FilletCheckerCmd",
    module="FilletCheckerModule",
    workbench="PartDesign",
    stateful=False,
    dialog="FilletCheckerDlg"
)

# 3. 创建普通类 (Analyzer)
ctx.execute("create_class", name="FilletAnalyzer", module="FilletCheckerModule")

# 4. 编译
ctx.execute("build", target="FilletChecker")

# 5. 运行验证
ctx.execute("run", mode="interactive")
```

## 扩展方向

- 增加更多规则（角度、面圆角、倒角等）
- 导出结果为 CSV/Excel
- 支持批量检查多个 Part
- 增加规则配置面板
