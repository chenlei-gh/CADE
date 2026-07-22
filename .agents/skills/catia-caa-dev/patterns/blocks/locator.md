---
id: block.locator
title: Selection Locator
category: pattern
domain: blocks
keywords: [locate, select, highlight, reframe, double click, zoom, find, navigate]
apis: [CATCSO, CATFrmEditor, CATPathElement, CATIVisProperties]
requires: [infra.selection]
patterns: [ui.result_dialog]
examples: [geo.fillet_checker]
release: [R19, R28]
tags: [block, locate, selection, ui]
---

# Selection Locator (双击定位积木)

可复用的"选中+定位到 Feature"的最小代码块。几乎所有结果展示工具都需要它。

## ⚠️ 重要修正

之前版本使用的 `CATFrmEditor::GetSelection()`、`SelectElement()`、`CATISO::ReframeOnObject()`、`CATVisProperties::SetHighlight()` 经核实**均不存在**。真实 API：选择集是 `CATCSO`（`GetCSO()`），高亮/变色用 `CATIVisProperties::SetPropertiesAtt`，相机定位用 `CAT3DViewer::ReframeOn(CAT3DBoundingSphere&)`。详见 [infra.selection](../../knowledge/infrastructure/selection.md)。

## 核心代码

```cpp
#include "CATFrmEditor.h"
#include "CATCSO.h"
#include "CATPathElement.h"

void LocateFeature(CATISpecObject_var iFeature) {
    CATFrmEditor *pEditor = CATFrmEditor::GetCurrentEditor();
    if (!pEditor) return;

    CATCSO *pCSO = pEditor->GetCSO();
    if (!pCSO) return;

    // 1. 清除当前选择
    pCSO->Empty();

    // 2. 选中目标（CATCSO::AddElement 收 CATBaseUnknown*，通常传 CATPathElement*）
    CATPathElement *pPath = new CATPathElement(iFeature);
    pCSO->AddElement(pPath);

    // 3. 相机定位：没有 ReframeOnObject；
    //    全景定位用 pViewer->Reframe()，对指定包围球定位用
    //    CAT3DViewer::ReframeOn(CAT3DBoundingSphere&)
    CAT3DViewer *pViewer = ...;   // 从 editor/窗口取得
    if (pViewer) {
        CAT3DBoundingSphere bs = GetBoundingSphereOf(iFeature);  // 按 rep 求包围球
        pViewer->ReframeOn(bs);
    }
}
```

## 用法

```cpp
// 双击回调（示例方法名，自定义）
void MyDialog::OnListDoubleClick(int line) {
    CATISpecObject_var spFeature = m_results[line].feature;
    LocateFeature(spFeature);   // ← Block: Locator
}

// Select All 中定位第一个
void OnSelectAll() {
    if (m_results.Size() > 0) {
        LocateFeature(m_results[1].feature);   // ← Block: Locator
    }
}
```

## 变体

```cpp
// 持久变色（真实高亮机制：CATIVisProperties）
void MarkFeature(CATISpecObject_var iFeature,
                 unsigned char r, unsigned char g, unsigned char b) {
    CATIVisProperties *pIProps = NULL;
    HRESULT rc = iFeature->QueryInterface(IID_CATIVisProperties, (void**)&pIProps);
    if (FAILED(rc) || !pIProps) return;

    CATVisPropertiesValues props;
    props.SetColor(r, g, b);
    // GeomType 真实取值：CATVPGlobalType/CATVPMesh/CATVPEdge/CATVPLine/CATVPPoint/CATVPAsm
    pIProps->SetPropertiesAtt(props, CATVPColor, CATVPAsm);
    pIProps->Release();
}

// 恢复标准显示：ResetPropertiesAtt 重置为默认值
void UnmarkFeature(CATISpecObject_var iFeature) {
    CATIVisProperties *pIProps = NULL;
    HRESULT rc = iFeature->QueryInterface(IID_CATIVisProperties, (void**)&pIProps);
    if (FAILED(rc) || !pIProps) return;

    pIProps->ResetPropertiesAtt(CATVPColor, CATVPAsm);   // 恢复标准色
    pIProps->Release();
}
```

> 注意：**禁止 `Sleep()` 循环造"闪烁"**——CAA UI 单线程，Sleep 会冻结整个 CATIA。闪烁效果用选择集切换（CSO 增删）由渲染循环自然呈现。
