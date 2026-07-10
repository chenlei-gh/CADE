---
id: surface.basics
title: Surface & GSD Basics
category: knowledge
domain: surface
keywords: [surface, GSD, Generative Shape Design, extrude, revolve, sweep, offset, trim, join]
apis: [CATIGSMFactory, CATIGSMSweep, CATIGSMOffset, CATIGSMTrim, CATIGSMJoin]
requires: [mecmod.feature, part.fillet]
patterns: [surface.analysis]
examples: []
release: [R19, R28]
tags: [surface, GSD, geometry]
---

# CAA Surface Design (GSD)

Generative Shape Design (GSD) 通过 `CATIGSMFactory` 创建曲面特征。

## 核心接口

| 接口 | 用途 |
|------|------|
| `CATIGSMFactory` | 所有曲面操作入口 |
| `CATIGSMExtrude` | 拉伸曲面 |
| `CATIGSMRevolve` | 旋转曲面 |
| `CATIGSMSweep` | 扫掠曲面 |
| `CATIGSMOffset` | 偏移曲面 |
| `CATIGSMTrim` | 修剪 |
| `CATIGSMJoin` | 缝合 |
| `CATIGSMSplit` | 分割 |
| `CATIGSMFill` | 填充 |

## 基本操作

### 拉伸曲面

```cpp
CATISpecObject *CreateExtrude(CATISpecObject *iProfile,
                                CATMathVector &iDirection,
                                double iLength) {
    CATIGSMFactory *pFactory = NULL;
    HRESULT hr = iProfile->QueryInterface(
        IID_CATIGSMFactory, (void**)&pFactory);
    
    CATISpecObject *pExtrude = NULL;
    hr = pFactory->CreateExtrude(iProfile, NULL,
        iDirection, iLength, iLength, &pExtrude);
    pFactory->Release();
    return pExtrude;
}
```

### 偏移曲面

```cpp
CATISpecObject *CreateOffset(CATISpecObject *iSurface,
                               double iOffset) {
    CATIGSMFactory *pFactory = NULL;
    iSurface->QueryInterface(IID_CATIGSMFactory,
        (void**)&pFactory);
    
    CATISpecObject *pOffset = NULL;
    pFactory->CreateOffset(iSurface, iOffset,
        CATBooleanTrue, &pOffset);  // both sides
    pFactory->Release();
    return pOffset;
}
```

### 缝合曲面

```cpp
CATISpecObject *JoinSurfaces(CATListValCATISpecObject &iSurfaces) {
    CATIGSMFactory *pFactory = CreateFactory(iSurfaces[1]);
    
    CATISpecObject *pJoin = NULL;
    pFactory->CreateJoin(iSurfaces, &pJoin);
    pFactory->Release();
    return pJoin;
}
```

### 修剪/分割

```cpp
// 修剪 (Trim) — 两个面互相修剪
CATISpecObject *TrimSurfaces(CATISpecObject *iSurf1,
                               CATISpecObject *iSurf2) {
    CATIGSMFactory *pFactory = CreateFactory(iSurf1);
    
    CATISpecObject *pTrim = NULL;
    pFactory->CreateTrim(iSurf1, iSurf2,
        CATBooleanFalse, CATBooleanFalse, &pTrim);
    //            side1?         side2?
    pFactory->Release();
    return pTrim;
}

// 分割 (Split) — 用工具面切目标面
CATISpecObject *SplitSurface(CATISpecObject *iTarget,
                               CATISpecObject *iTool) {
    // ...
}
```

## 曲面分析

```cpp
// 获取曲面面积
double GetSurfaceArea(CATISpecObject *iSurface) {
    CATBody *pBody = GetBody(iSurface);
    if (!pBody) return 0.0;
    
    double area = 0.0;
    pBody->GetSurfaceArea(area);
    return area;
}

// 检查曲面连续性
CATBoolean CheckContinuity(CATISpecObject *iSurf1,
                            CATISpecObject *iSurf2,
                            int continuityLevel) {
    // G0 = point, G1 = tangent, G2 = curvature
    // 通过 CATIGSMConnectChecker 检查
}

// 展平曲面（铺平）
CATISpecObject *FlattenSurface(CATISpecObject *iSurface,
                                 CATMathDirection &iDirection) {
    // CATIGSMDevelop 展平/展开
    CATIGSMFactory *pFactory = CreateFactory(iSurface);
    CATISpecObject *pFlattened = NULL;
    pFactory->CreateDevelop(iSurface, iDirection, &pFlattened);
    pFactory->Release();
    return pFlattened;
}
```

## AI 生成规则

- [ ] 所有曲面操作通过 `CATIGSMFactory`
- [ ] Profile（截面）必须是封闭或开放草图
- [ ] 偏移曲面检查自交
- [ ] 缝合前检查面之间的间隙（<0.001mm）
- [ ] 展平曲面注意不可展曲面（双曲率）会近似
