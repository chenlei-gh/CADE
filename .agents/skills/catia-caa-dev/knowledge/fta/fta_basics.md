---
id: fta.basics
title: FTA / 3D Annotation Basics
category: knowledge
domain: fta
keywords: [FTA, 3D annotation, PMI, tolerance, capture, view, TPS]
apis: [CATITPSSet, CATITPSFactoryElementary, CATITPSFactoryTTRS, CATITPSCaptureFactory, CATITPSViewFactory, CATITPSDimensionLimits]
requires: [mecmod.feature]
patterns: [fta.auto_annotate]
examples: []
release: [R19, R28]
tags: [fta, annotation, PMI, 3D]
---

# CAA FTA (3D Functional Tolerancing & Annotation)

FTA / FT&A 用于在 3D 模型上直接创建标注，替代传统二维工程图。

## ⚠️ 重要修正

旧版本文档整篇几乎全部为虚构接口（`CATITPSFactory`/`GetFactory()`/`CATITPSFactoryDim`/`CATITPSFactoryTol`/`GetAllFaces` 均不存在）。以下内容已对照 `cap.annotation`（TPS 真实对象模型，经 SDK 头文件 + 发布产品字典交叉核实）重写：

| 旧写法（虚构） | 真实情况 |
|---------------|---------|
| `CATITPSFactory`（单一工厂） | 不存在。见下方"核心对象层级"，创建能力拆分在多个接口上 |
| `iSet->GetFactory(&pFactory)` | `CATITPSSet` 没有 `GetFactory()`。真实获取方式：对 `CATITPSSet` 做 `QueryInterface` 到具体的工厂接口（`CATITPSFactoryElementary`/`CATITPSCaptureFactory`/`CATITPSViewFactory`） |
| `pFactory->CreateView(name, direction, &pView)` | `CATITPSViewFactory::CreateView()` 真实签名远比这复杂（8 个参数，含 `CATMathPlane*`/`CATDftViewType`/`CATITTRSList*` 等），且没有"View 名字+方向"这种便捷签名 |
| `CATITPSFactoryDim`/`iView->GetDimensionFactory()` | 不存在。尺寸创建在 `CATITPSFactoryElementary::CreateSemanticDimension()`/`CreateNonSemanticDimension()` 上，不挂在 View 上 |
| `pFactory->CreateDistanceDim(elem1, elem2, pos, &pDim)` | 不存在这种便捷签名。真实流程需先把几何选择包装成 `CATITTRS`（`CATITPSFactoryTTRS::GetTTRS()`），再调用 `CreateSemanticDimension()` |
| `CATITPSFactoryTol`/`iView->GetToleranceFactory()` | 不存在。公差创建也在 `CATITPSFactoryElementary::CreateToleranceWithDRF()`/`CreateToleranceWithoutDRF()` 上 |
| `pFactory->CreateDimensionTolerance(dim, upper, lower, &pTol)` | 不存在。尺寸公差数值不是通过创建新对象设置的，而是对已创建的 `CATITPSDimension` QueryInterface 到 `CATITPSDimensionLimits`，调用 `SetLimits(lower, upper)` |
| `CATITPSAnnotation`（公共基接口） | 不存在。真正的多态基接口是 `CATITPSComponent`（纯标记接口） |
| `CATITPSDatum`（直接创建的对象） | `CreateDatum()` 返回的是 `CATITPSDatumSimple`，`CATITPSDatum` 本身是纯类型标记接口 |
| `CATListValCATFace faces; GetAllFaces(iPart, faces)` | 不存在这种模板列表和全局函数。真实遍历方式：`CATIMfBRep::GetBody()` 拿到 `CATBody`，再 `GetAllCells(list, 2)` + `IsATypeOf(CATFaceType)` 筛选面（见 `cap.geometry_query`） |
| `CATITPSView` 创建后调用 `SetActiveView` | 应在 `CATITPSSet` 上调用 `SetActiveView()`（View 是 Set 的下级对象，不是自己激活自己） |

## 核心对象层级

```
CATITPSSet (标注集，文档级容器)
  ├── CATITPSCapture (捕获视图：一份标注子集的3D快照/相机/剪切面)
  ├── CATITPSView (标注视图：绑定到2D工程图视图的支撑面)
  └── CATITPS-派生标注 (通过 CATITPSFactoryElementary 创建，挂在 CATITTRS 上)
       ├── CATITPSDimension (尺寸类型标记接口 → 数据在 CATITPSDimensionLimits)
       ├── CATITPSForm (形位公差类型标记接口 → 数据在 CATITPSDimensionLimits)
       └── CATITPSDatumSimple (基准，本身即数据接口)
```

`CATITPSFactoryElementary`/`CATITPSCaptureFactory`/`CATITPSViewFactory` 三者都不是全局单例，而是**挂在 `CATITPSSet` 实例上、需要 QueryInterface 才能拿到**的接口；`CATITPSFactoryTTRS`/`CATITPSFactoryAdvanced` 才是通过全局函数 `CATTPSInstantiateComponent()` 获取的单例。详见 `capabilities/annotation.md`。

## 基本操作

### 获取标注集与工厂接口

```cpp
CATITPSSet* GetTPSSet(CATITPSDocument* iDoc) {
    // 真实入口是 CATITPSDocument::GetSets()，不是对 Part 做 QueryInterface；
    // 返回值是 CATITPSList**，不是 CATListValCATBaseUnknown_var
    CATITPSList* pSets = NULL;
    iDoc->GetSets(&pSets);
    unsigned int count = 0;
    pSets->Count(&count);
    if (count < 1) return NULL;
    CATITPSComponent* pItem = NULL;
    pSets->Item(0, &pItem);  // 0-based
    CATITPSSet* pSet = NULL;
    pItem->QueryInterface(IID_CATITPSSet, (void**)&pSet);
    return pSet;
}

// CATITPSFactoryElementary/CATITPSCaptureFactory/CATITPSViewFactory
// are implemented ON the Set -- obtained via QueryInterface, not a
// GetFactory() accessor and not CATTPSInstantiateComponent()
CATITPSFactoryElementary* GetElementaryFactory(CATITPSSet* iSet) {
    CATITPSFactoryElementary* pFactElem = NULL;
    iSet->QueryInterface(IID_CATITPSFactoryElementary, (void**)&pFactElem);
    return pFactElem;
}
```

### 创建尺寸标注

```cpp
CATITPSDimension* CreateDimension(CATITPSSet* iSet,
                                   CATSO* iGeometrySelected,
                                   double lowerTol, double upperTol) {
    // 1) 全局单例工厂，把几何选择包装成 CATITTRS
    CATITPSFactoryTTRS* pFactTTRS = NULL;
    CATTPSInstantiateComponent(DfTPS_ItfTPSFactoryTTRS, (void**)&pFactTTRS);
    CATITTRS* pTTRS = NULL;
    pFactTTRS->GetTTRS(iGeometrySelected, &pTTRS);

    // 2) 挂在 Set 上的工厂，创建标注
    CATITPSFactoryElementary* pFactElem = GetElementaryFactory(iSet);
    CATITPSDimension* pDim = NULL;
    pFactElem->CreateSemanticDimension(pTTRS, CATTPSLinearDimension,
                                        CATTPSDistanceDimension, &pDim);

    // 3) CATITPSDimension 本身无数据方法 -- QueryInterface 到数据接口
    CATITPSDimensionLimits* pLimits = NULL;
    pDim->QueryInterface(IID_CATITPSDimensionLimits, (void**)&pLimits);
    if (pLimits) {
        pLimits->SetLimits(lowerTol, upperTol);
        pLimits->Release();
    }

    pTTRS->Release();
    pFactElem->Release();
    pFactTTRS->Release();
    return pDim;
}
```

### 创建基准 (Datum)

```cpp
CATITPSDatumSimple* CreateDatum(CATITPSSet* iSet,
                                 CATSO* iPlaneSelected,
                                 const wchar_t* iLabel) {
    CATITPSFactoryTTRS* pFactTTRS = NULL;
    CATTPSInstantiateComponent(DfTPS_ItfTPSFactoryTTRS, (void**)&pFactTTRS);
    CATITTRS* pTTRS = NULL;
    pFactTTRS->GetTTRS(iPlaneSelected, &pTTRS);

    CATITPSFactoryElementary* pFactElem = GetElementaryFactory(iSet);
    CATITPSDatumSimple* pDatum = NULL;
    pFactElem->CreateDatum(pTTRS, &pDatum);
    pDatum->SetLabel(iLabel);  // wchar_t*, not CATUnicodeString

    pTTRS->Release();
    pFactElem->Release();
    pFactTTRS->Release();
    return pDatum;
}
```

### 组织到 Capture

```cpp
CATITPSCapture* CreateCapture(CATITPSSet* iSet) {
    // CATITPSSet 本身没有 CreateCapture() -- 需 QueryInterface 到 CaptureFactory
    CATITPSCaptureFactory* pCaptureFactory = NULL;
    iSet->QueryInterface(IID_CATITPSCaptureFactory, (void**)&pCaptureFactory);

    CATITPSCapture* pCapture = NULL;
    pCaptureFactory->CreateCapture(&pCapture);
    pCapture->SetCurrent(TRUE);

    pCaptureFactory->Release();
    return pCapture;
}
```

## 自动标注策略

```cpp
// 基于间隙检测自动标注
HRESULT AutoAnnotateGaps(CATISpecObject* iPart, CATITPSSet* iSet, double gapThreshold) {
    // 1. 遍历所有面：真实 API 是 CATIMfBRep::GetBody() + GetAllCells()，
    //    不是不存在的 GetAllFaces() 全局函数
    CATIMfBRep* pBRep = NULL;
    iPart->QueryInterface(IID_CATIMfBRep, (void**)&pBRep);
    if (!pBRep) return E_FAIL;
    CATBody* pBody = pBRep->GetBody();
    pBRep->Release();
    if (!pBody) return E_FAIL;

    CATListOfCATCells cells;
    pBody->GetAllCells(cells, 2);  // dimension 2 = faces

    // 2. 检测间隙并创建标注（先用 IsATypeOf(CATFaceType) 筛选面）
    for (int i = 1; i <= cells.Size(); i++) {
        if (!cells[i]->IsATypeOf(CATFaceType)) continue;
        for (int j = i + 1; j <= cells.Size(); j++) {
            if (!cells[j]->IsATypeOf(CATFaceType)) continue;
            double gap = MeasureGap((CATFace*)cells[i], (CATFace*)cells[j]);
            if (gap < gapThreshold && gap > 0.001) {
                CATSO* pGeomSelected = BuildCATSOFromFacePair(
                    (CATFace*)cells[i], (CATFace*)cells[j]);  // application-specific
                CreateDimension(iSet, pGeomSelected, 0.0, 0.1);
            }
        }
    }
    return S_OK;
}
```

## AI 生成规则

- [ ] FTA 标注通过 `CATITPSSet` 聚合；不存在单一的 `CATITPSFactory`
- [ ] `CATITPSFactoryElementary`/`CATITPSCaptureFactory`/`CATITPSViewFactory` 需对 `CATITPSSet` 做 `QueryInterface` 获取，不是 `GetFactory()`
- [ ] `CATITPSFactoryTTRS`/`CATITPSFactoryAdvanced` 是全局单例，通过 `CATTPSInstantiateComponent()` 获取
- [ ] 尺寸/公差创建统一走 `CATITPSFactoryElementary`（先用 `GetTTRS()` 把几何包装成 `CATITTRS`）
- [ ] `CATITPSDimension`/`CATITPSForm` 本身无数据方法，数值在 `CATITPSDimensionLimits`（QueryInterface 获取）上设置
- [ ] 基准用 `CreateDatum()` 返回 `CATITPSDatumSimple`（不是泛型 `CATITPSDatum`）
- [ ] Capture 的当前状态用 `SetCurrent(TRUE)`，不是 `SetActiveView`（`SetActiveView` 是 `CATITPSSet` 上管理 `CATITPSView` 的方法，与 Capture 无关）
- [ ] 遍历几何面用 `CATIMfBRep::GetBody()` + `CATBody::GetAllCells(list, 2)` + `IsATypeOf(CATFaceType)`

## 相关文档

- **[cap.annotation](../../capabilities/annotation.md)** — 完整的 TPS 对象模型与已核实的 API 签名
- **[cap.geometry_query](../../capabilities/geometry-query.md)** — 几何遍历真实 API
- **[pb.auto_annotate_3d](../../playbooks/pb_auto_annotate_3d.md)** — 完整的自动标注 playbook
