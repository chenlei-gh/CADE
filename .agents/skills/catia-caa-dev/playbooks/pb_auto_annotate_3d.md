---
id: pb.auto_annotate_3d
title: Auto 3D Annotation / 自动3D标注
category: playbook
domain: fta
keywords: [FTA, 3D annotation, PMI, tolerance, dimension, capture, annotate, auto, GD&T]
capabilities: [cap.annotation, cap.geometry_query, cap.selection]
apis: [CATITPSSet, CATITPSFactoryElementary, CATITPSFactoryTTRS, CATITPSCaptureFactory, CATITPSDimensionLimits, CATIMfBRep, CATBody, CATFace]
frameworks: [CATTPSInterfaces, MecModInterfaces, GMModelInterfaces]
difficulty: advanced
effort: large
release: [R19, R28]
tags: [playbook, FTA, annotation, 3D, PMI, automation]
---

# Auto 3D Annotation (自动3D标注)

自动为零件几何特征生成 3D 标注（PMI）：尺寸、公差、基准、表面粗糙度。

## ⚠️ 重要修正

旧版本文档的实现步骤和关键代码基本全是虚构接口（`CATITPSFactory`/`CATITPSAnnotation`/`CATBody::GetAllFaces`/`CATIPrtPart::GetMainBody` 均不存在）。已对照 `cap.annotation`（TPS 真实对象模型）与 `cap.geometry_query`（几何遍历真实 API）重写，核实方式见文末对应表格：

| 旧写法（虚构） | 真实情况 |
|---------------|---------|
| `CATITPSFactory::CreateView("Auto Annotations")` | `CATITPSFactory` 不存在；创建 View 需先拿到一个 `CATITPSSet`，对其 `QueryInterface` 到 `CATITPSViewFactory`，再调用其 `CreateView(...)`（详见 `cap.annotation`） |
| `CATIPrtPart_var spPrt = iPart; spPrt->GetMainBody()` | `CATIPrtPart` 没有 `GetMainBody()`。真实获取主实体的方式是 `CATIPartRequest::GetMainBody(iViewContext, oBody)`（`MecModInterfaces` 框架） |
| `spBody->GetAllFaces(faces)` 返回 `CATListPtrCATFace` | 不存在这种签名/列表类型。真实方法是 `CATBody::GetAllCells(CATListOfCATCells&, dimension)`（`dimension=2` 表示面），元素需 `IsATypeOf(CATFaceType)` 判断后转型为 `CATFace*`（详见 `cap.geometry_query`） |
| `spFactory->CreateDimension("Diameter", point, normal)` | 不存在这种便捷签名。真实创建尺寸标注需先用 `CATITPSFactoryTTRS::GetTTRS()` 把几何选择包装成 `CATITTRS`，再用 `CATITPSFactoryElementary::CreateSemanticDimension(ttrs, CATTPSDimensionType, CATTPSLinearDimensionSubType, &dim)` 创建。两个枚举参数的真实成员无 `Type`/`SubType` 前缀，如直径尺寸需传 `CATTPSLinearDimension` + `CATTPSDiameterDimension`（而不是 `CATTPSDimensionTypeDiameter`） |
| `spDim->SetNominalValue()`/`SetTolerance()` | `CATITPSDimension` 本身无数据方法（纯类型标记接口）。真实数值方法在 `CATITPSDimensionLimits`（QueryInterface 得到）上：`SetLimits(lower, upper)` |
| `spView->AddAnnotation(spDim)` | `CATITPSView` 没有此方法。标注列表管理是在 `CATITPSCapture`（不是 View）上，用 `SetTPSs(CATITPSList*)` 整体替换 |
| `spView->Update()` | 不存在。3D 标注对象随文档 Update 机制自动刷新，无需显式调用 |

## 目标

选中零件 → 识别关键几何特征（孔、槽、曲面） → 自动创建对应的 3D 标注 → 组织到 Capture 中。

## 前置条件

- 已加载 CATPart（含实体几何）
- FTA 工作台已激活，文档内已存在（或已创建）`CATITPSSet`
- 可选：标注规范（公差标准、精度等级）

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.annotation` | 创建 3D 标注对象（尺寸/公差/基准），获取 TPS 工厂接口的真实方式 |
| `cap.geometry_query` | 获取几何体的拓扑元素（`CATBody::GetAllCells`/`CATFace::CalcArea` 等） |
| `cap.selection` | 定位标注附着点 |

## 实现步骤

1. **获取主实体**：`CATIPartRequest::GetMainBody(viewContext, oBody)` 得到 `CATBody`
2. **遍历几何特征**：`CATBody::GetAllCells(cells, 2)` 取所有面，用 `IsATypeOf(CATFaceType)` 筛选，识别圆柱面（孔）/平面/自由曲面
3. **获取 TPS 工厂**：拿到文档的 `CATITPSSet`（如 `CATITPSDocument::GetSets()`），QueryInterface 到 `CATITPSFactoryElementary`；全局单例 `CATITPSFactoryTTRS` 通过 `CATTPSInstantiateComponent()` 获取
4. **生成标注**：
   - 圆柱面（孔） → 用 `GetTTRS()` 包装几何 → `CreateSemanticDimension(ttrs, CATTPSLinearDimension, CATTPSDiameterDimension, &dim)` 直径尺寸
   - 平面 → `CreateDatum(ttrs, &datum)` 基准符号
   - 自由曲面 → `CreateToleranceWithoutDRF(CATTPSWithOutDRFTypeProfileOfASurface, ttrs, &tol)` 轮廓度公差
5. **写入公差数值**：对创建出的标注 QueryInterface 到 `CATITPSDimensionLimits`，调用 `SetLimits(lower, upper)`/`SetSingleLimit(value)`
6. **组织到 Capture**：对同一个 `CATITPSSet` QueryInterface 到 `CATITPSCaptureFactory`，调用 `CreateCapture(&capture)`，再用 `capture->SetTPSs(tpsList)` 把新建的标注整体写入

## 标注结构

```cpp
struct AnnotationDef {
    CATUnicodeString type;       // "diameter", "flatness", "datum"...
    CATFace*          pFace;     // 附着的拓扑面（用于构造 CATSO/CATITTRS）
    double            nominalValue;  // 公称值（直径/长度）
    double            lowerTolerance;
    double            upperTolerance;
};
```

## 关键代码

```cpp
#include "CATTPSInstantiateComponent.h"
#include "CATITPSFactoryTTRS.h"
#include "CATITPSFactoryElementary.h"
#include "CATITPSCaptureFactory.h"
#include "CATITPSDimensionLimits.h"
#include "CATIPartRequest.h"

HRESULT AutoAnnotatePart(CATISpecObject* iPart, CATITPSSet* pTPSSet) {
    // 1. Get the part's main body (real API: CATIPartRequest, not CATIPrtPart::GetMainBody)
    CATIPartRequest* pPartRequest = NULL;
    iPart->QueryInterface(IID_CATIPartRequest, (void**)&pPartRequest);
    if (!pPartRequest) return E_FAIL;

    CATBaseUnknown_var spBodyUnk;
    pPartRequest->GetMainBody("", spBodyUnk);
    CATBody* pBody = (CATBody*)((CATBaseUnknown*)spBodyUnk);
    pPartRequest->Release();
    if (!pBody) return E_FAIL;

    // 2. Get TPS factories: CATITPSFactoryTTRS is a global singleton;
    //    CATITPSFactoryElementary is obtained via QueryInterface on the Set
    CATITPSFactoryTTRS* pFactTTRS = NULL;
    CATTPSInstantiateComponent(DfTPS_ItfTPSFactoryTTRS, (void**)&pFactTTRS);

    CATITPSFactoryElementary* pFactElem = NULL;
    pTPSSet->QueryInterface(IID_CATITPSFactoryElementary, (void**)&pFactElem);

    // 3. Walk all faces (real API: GetAllCells + IsATypeOf, not GetAllFaces)
    CATListOfCATCells faces;
    pBody->GetAllCells(faces, 2);  // dimension 2 = faces

    for (int i = 1; i <= faces.Size(); i++) {
        CATCell* pCell = faces[i];
        if (!pCell->IsATypeOf(CATFaceType)) continue;
        CATFace* pFace = (CATFace*)pCell;

        if (!IsCylindrical(pFace)) continue;  // application-specific classifier

        // 4. Wrap the face selection into a CATITTRS reference
        CATSO* pGeomSelected = BuildCATSOFromFace(pFace);  // application-specific
        CATITTRS* pTTRS = NULL;
        pFactTTRS->GetTTRS(pGeomSelected, &pTTRS);

        // 5. Create the diameter dimension
        // (real enum members carry no Type/SubType prefix -- see cap.annotation)
        CATITPSDimension* pDimension = NULL;
        pFactElem->CreateSemanticDimension(pTTRS, CATTPSLinearDimension,
                                            CATTPSDiameterDimension,
                                            &pDimension);

        // 6. CATITPSDimension itself has no data methods -- query the data interface
        CATITPSDimensionLimits* pLimits = NULL;
        pDimension->QueryInterface(IID_CATITPSDimensionLimits, (void**)&pLimits);
        if (pLimits) {
            pLimits->SetLimits(0.0, 0.1);  // H7-fit style tolerance in millimeters
            pLimits->Release();
        }

        pTTRS->Release();
        pDimension->Release();
    }

    // 7. Organize the new annotations into a capture
    //    (CATITPSSet has no CreateCapture() of its own)
    CATITPSCaptureFactory* pCaptureFactory = NULL;
    pTPSSet->QueryInterface(IID_CATITPSCaptureFactory, (void**)&pCaptureFactory);

    CATITPSCapture* pCapture = NULL;
    pCaptureFactory->CreateCapture(&pCapture);
    pCapture->SetCurrent(TRUE);
    // Populate pCapture->SetTPSs(pTPSList) with the created annotations here

    pCaptureFactory->Release();
    pCapture->Release();
    pFactElem->Release();
    pFactTTRS->Release();
    return S_OK;
}
```

## 注意事项

- FTA 标注依赖 `CATITPSSet` 和 `CATITPSCapture` 层级结构；`CATITPSSet` 本身没有创建方法，必须先 QueryInterface 到对应工厂
- `CATITPSFactoryElementary`/`CATITPSCaptureFactory`/`CATITPSViewFactory` 都是挂在 Set 上的接口，与全局单例工厂（`CATITPSFactoryTTRS`/`CATITPSFactoryAdvanced`）获取方式不同——见 `cap.annotation`
- 遍历几何面时用 `CATBody::GetAllCells(list, 2)` + `IsATypeOf(CATFaceType)`，不是不存在的 `GetAllFaces()`
- 标注附着点必须先包装成 `CATITTRS`（通过 `CATITPSFactoryTTRS::GetTTRS()`），不能直接传几何指针
- 公差标准（ISO/ASME）影响标注符号样式
- 大批量标注建议设置合理的标注间距避免重叠

## 相关 Playbook

- `pb.geometry_quality_check` — 可与质量检查结合，不合格特征标红
