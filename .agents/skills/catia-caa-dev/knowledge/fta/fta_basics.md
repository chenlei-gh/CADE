---
id: fta.basics
title: FTA / 3D Annotation Basics
category: knowledge
domain: fta
keywords: [FTA, 3D annotation, PMI, tolerance, capture, view, TPS]
apis: [CATITPSView, CATITPSCapture, CATITPSAnnotation, CATITPSTolerance]
requires: [mecmod.feature]
patterns: [fta.auto_annotate]
examples: []
release: [R19, R28]
tags: [fta, annotation, PMI, 3D]
---

# CAA FTA (3D Functional Tolerancing & Annotation)

FTA / FT&A 用于在 3D 模型上直接创建标注，替代传统二维工程图。

## 核心对象层级

```
CATITPSSet (标注集)
  └── CATITPSCapture (捕获视图)
       ├── CATITPSView (标注视图)
       │    ├── CATITPSAnnotation (标注)
       │    │    ├── CATITPSDimension (尺寸)
       │    │    ├── CATITPSTolerance (公差)
       │    │    └── CATITPSText (文本)
       │    └── CATITPSDatum (基准)
       └── CATITPSCapture (子捕获)
```

## 基本操作

### 创建标注集

```cpp
CATITPSSet *GetOrCreateTPSSet(CATISpecObject *iPart) {
    CATITPSSet *pSet = NULL;
    HRESULT hr = iPart->QueryInterface(
        IID_CATITPSSet, (void**)&pSet);
    if (FAILED(hr)) {
        // 创建新的 TPS Set
        CATITPSFactory *pFactory = NULL;
        // ...
    }
    return pSet;
}
```

### 创建标注视图

```cpp
CATITPSView *CreateAnnotationView(CATITPSSet *iSet,
                                    const CATUnicodeString &iViewName,
                                    CATMathDirection &iDirection) {
    CATITPSFactory *pFactory = NULL;
    iSet->GetFactory(&pFactory);
    
    CATITPSView *pView = NULL;
    pFactory->CreateView(iViewName, iDirection, &pView);
    pFactory->Release();
    return pView;
}
```

### 创建尺寸标注

```cpp
CATITPSDimension *CreateDimension(CATITPSView *iView,
                                    CATISpecObject *iElement1,
                                    CATISpecObject *iElement2,
                                    CATMathPoint &iTextPosition) {
    CATITPSFactoryDim *pFactory = NULL;
    iView->GetDimensionFactory(&pFactory);
    
    CATITPSDimension *pDim = NULL;
    pFactory->CreateDistanceDim(iElement1, iElement2,
        iTextPosition, &pDim);
    pFactory->Release();
    return pDim;
}
```

### 创建基准 (Datum)

```cpp
CATITPSDatum *CreateDatum(CATITPSView *iView,
                            CATISpecObject *iPlane,
                            const CATUnicodeString &iLabel) {
    CATITPSFactory *pFactory = NULL;
    iView->GetFactory(&pFactory);
    
    CATITPSDatum *pDatum = NULL;
    pFactory->CreateDatum(iPlane, iLabel, &pDatum);
    pFactory->Release();
    return pDatum;
}
```

### 创建公差标注

```cpp
CATITPSTolerance *CreateTolerance(CATITPSView *iView,
                                    CATITPSDimension *iDimension,
                                    double upperTol, double lowerTol) {
    CATITPSFactoryTol *pFactory = NULL;
    iView->GetToleranceFactory(&pFactory);
    
    CATITPSTolerance *pTol = NULL;
    pFactory->CreateDimensionTolerance(iDimension,
        upperTol, lowerTol, &pTol);
    pFactory->Release();
    return pTol;
}
```

## 自动标注策略

```cpp
// 基于间隙检测自动标注
HRESULT AutoAnnotateGaps(CATISpecObject *iPart, double gapThreshold) {
    CATITPSSet *pSet = GetOrCreateTPSSet(iPart);
    CATITPSView *pView = CreateMainView(pSet);
    
    // 1. 遍历所有面和边
    CATListValCATFace faces;
    GetAllFaces(iPart, faces);
    
    // 2. 检测间隙
    for (int i = 1; i <= faces.Size(); i++) {
        for (int j = i + 1; j <= faces.Size(); j++) {
            double gap = MeasureGap(faces[i], faces[j]);
            if (gap < gapThreshold && gap > 0.001) {
                // 3. 创建标注
                CATMathPoint midPt = GetMidPoint(faces[i], faces[j]);
                CreateDimension(pView, faces[i], faces[j], midPt);
            }
        }
    }
    return S_OK;
}
```

## AI 生成规则

- [ ] FTA 标注通过 `CATITPSSet` → `CATITPSView` → `CATITPSAnnotation` 层级创建
- [ ] 尺寸标注用 `CATITPSFactoryDim`
- [ ] 公差用 `CATITPSFactoryTol`
- [ ] 基准面/基准轴用 `CATITPSDatum`
- [ ] 每个标注视图有独立的法向方向
- [ ] 标注 View 创建后需调用 `SetActiveView`
