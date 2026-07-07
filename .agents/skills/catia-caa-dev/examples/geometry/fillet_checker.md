---
id: geo.fillet_checker
title: Fillet Checker
category: example
domain: geometry
keywords: [fillet, check, analyzer, example, full project, dialog, listview]
apis: [CATIFillet, CATISpecObject, CATIPrtPart, CATDlgDialog, CATDlgList, CATFrmEditor, CATPathElement]
requires: [part.fillet, mecmod.feature, ui.dialog, infra.selection]
patterns: [analyzer.geometry, analyzer.rule, ui.result_dialog, block.visitor, block.locator]
examples: []
release: [R19, R28]
tags: [example, geometry, check, full-project]
difficulty: intermediate
---

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
#include "CATIFillet.h"
#include "CATICkeParm.h"

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

    CATIFillet_var pFillet = pFeature;
    double radius = pFillet->GetRadius()->Value();

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

```cpp
void FilletCheckerDlg::ShowResults() {
    m_pList->ClearLine();

    for (int i = 0; i < m_analyzer.GetResultCount(); i++) {
        FilletResult r = m_analyzer.GetResult(i);
        char* cols[4] = {
            (char*)(r.status == "PASS" ? "✓" : "✗"),
            (char*)r.name.ConvertToChar(),
            (char*)(CATUnicodeString::FromDouble(r.radius) + "mm").ConvertToChar(),
            (char*)r.problem.ConvertToChar()
        };
        m_pList->SetLine(i + 1, cols, 4);
    }
}

void FilletCheckerDlg::OnDoubleClick(int line) {
    FilletResult r = m_analyzer.GetResult(line - 1);
    CATPathElement path(r.feature);

    CATFrmEditor* pEditor = CATFrmEditor::GetCurrentEditor();
    pEditor->GetSelection()->Clear();
    pEditor->GetSelection()->SelectElement(path);
    pEditor->GetISO()->ReframeOnObject(path);
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
