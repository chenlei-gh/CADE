---
id: drawing.basics
title: Drawing Basics
category: knowledge
domain: drawing
keywords: [drawing, sheet, view, CATDrawing, CATDrwView, projection, section]
apis: [CATIDrwView, CATIDrwSheet, CATIDftDrawing]
requires: [infra.selection]
patterns: [drawing.batch]
examples: []
release: [R19, R28]
tags: [drawing, engineering, 2D]
---

# CAA Drawing (工程图)

CATIA 工程图通过 Drawing 文档对象操作，核心是 View（视图）和 Sheet（图纸）。

## Drawing 对象层级

```
CATIDoc (文档)
  └── CATIDftDrawing (工程图根)
       ├── CATIDrwSheet (图纸页)
       │    ├── CATIDrwView (视图)
       │    │    ├── CATIDrwDim (尺寸标注)
       │    │    ├── CATIDrwText (文本注释)
       │    │    ├── CATIDrwTable (表格)
       │    │    └── CATIDrwGeometry (几何元素)
       │    └── CATIDrwFrame (图框)
       └── Sheet 2 ...
```

## 基本操作

### 打开/创建工程图

```cpp
// 从 Part/Product 创建 Drawing
HRESULT CreateDrawingFromPart(CATISpecObject *iPart) {
    CATIDftDrawingBag *pBag = NULL;
    HRESULT hr = CATIDftDrawingBag::CreateDrawingBag(
        iPart, &pBag);
    if (FAILED(hr)) return hr;

    CATIDftDrawing *pDrawing = NULL;
    hr = pBag->GetDrawing(&pDrawing);
    pBag->Release();
    return hr;
}
```

### 创建视图

```cpp
// 主视图（Front View）
CATIDrwView *CreateFrontView(CATIDftDrawing *pDrawing,
                               CATISpecObject *iPart) {
    CATIDrwViewFactory *pFactory = NULL;
    HRESULT hr = pDrawing->QueryInterface(
        IID_CATIDrwViewFactory, (void**)&pFactory);
    if (FAILED(hr)) return NULL;

    CATIDrwView *pView = NULL;
    hr = pFactory->CreateFrontView(iPart,
        CATMathPoint(100, 200, 0), &pView);
    pFactory->Release();
    return pView;
}

// 投影视图
CATIDrwView *CreateProjectionView(CATIDrwView *pParent,
                                    CATDrwProjDirection iDir) {
    CATIDrwViewFactory *pFactory = NULL;
    // ... similar pattern ...
    return pView;
}

// 剖面视图
CATIDrwView *CreateSectionView(CATIDrwView *pParent,
                                CATMathLine &iSectionLine) {
    // ...
}
```

### 获取图纸页

```cpp
CATIDrwSheet *GetActiveSheet(CATIDftDrawing *pDrawing) {
    CATIDrwSheet *pSheet = NULL;
    pDrawing->GetCurrentSheet(&pSheet);
    return pSheet;
}

CATIDrwSheet *GetSheetByIndex(CATIDftDrawing *pDrawing, int idx) {
    CATIDrwSheet *pSheet = NULL;
    pDrawing->GetSheet(idx, &pSheet);
    return pSheet;
}
```

## 视图属性

```cpp
// 设置视图比例
HRESULT SetViewScale(CATIDrwView *pView, double scale) {
    return pView->SetScale(scale);
}

// 设置视图名称
CATUnicodeString GetViewName(CATIDrwView *pView) {
    CATUnicodeString name;
    pView->GetViewName(name);
    return name;
}

// 获取视图几何
HRESULT GetViewGeometry(CATIDrwView *pView,
                         CATIDrwGenGeometry **oGeom) {
    return pView->GetGeometry(oGeom);
}
```

## AI 生成规则

- [ ] 使用 `CATIDftDrawing` 操作工程图文档
- [ ] 视图通过 `CATIDrwViewFactory` 创建
- [ ] 每张图纸是 `CATIDrwSheet`
- [ ] 视图创建需要位置参数 `CATMathPoint`
- [ ] 投影视图需要父视图 + 方向枚举
- [ ] 操作 Drawing 前必须先加载到 Session
