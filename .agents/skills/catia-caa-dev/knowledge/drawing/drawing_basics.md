---
id: drawing.basics
title: Drawing Basics
category: knowledge
domain: drawing
keywords: [drawing, sheet, view, CATDrawing, CATIDftView, projection, section]
apis: [CATIDftDrawing, CATIDftSheet, CATIDftView, CATIDrwFactory]
requires: [infra.selection]
patterns: [drawing.batch]
examples: []
release: [R19, R28]
tags: [drawing, engineering, 2D]
---

# CAA Drawing (工程图)

CATIA 工程图通过 Drawing 文档对象操作，核心是 View（视图）和 Sheet（图纸）。

## ⚠️ 重要修正

本文档早期版本使用了虚构的 `CATIDrw*` 接口体系（`CATIDrwSheet`/`CATIDrwView`/`CATIDrwViewFactory`/`CATIDftDrawingBag`/`CATDrwProjDirection`/`CATIDrwGenGeometry`），经本地 CAADoc（`DraftingInterfaces` 框架 SDK 头文件 + refman 交叉核实）确认这些类型**全部不存在**。真实的图纸对象模型前缀是 `CATIDft*`（Drafting），详细对照见 [pb.batch_drawing](../../playbooks/pb_batch_drawing.md)：

| 错误写法 | 正确写法 |
|------|---------|
| `CATIDftDrawingBag::CreateDrawingBag()` | 不存在这个便捷入口。新建用 `CATIDrwFactory::CreateDrawing(IID&, void**, wchar_t* iStandardName=NULL)`；打开已有 `.CATDrawing` 用 `CATDocumentServices::OpenDocument()` + `QueryInterface`/`CATInit::GetRootContainer(IID_CATIDftDrawing)` |
| `CATIDrwSheet` | `CATIDftSheet`（组件 `Sheet`/`Sheet2DL` 实现） |
| `CATIDrwView` | `CATIDftView`（组件 `DrwDetail`/`View`/`View2DL` 实现） |
| `CATIDrwViewFactory::CreateFrontView()`（"一键创建视图"） | **整个便捷工厂不存在**，没有 `CreateFrontView`/`CreateTopView` 这类一键方法。见下方"创建视图"小节的真实链条 |
| `CATDrwProjDirection` | 不存在独立枚举，视图类型统一用 `CATDftViewType`（`DraftingInterfaces`） |
| `pDrawing->GetCurrentSheet()`/`GetSheet(idx)` | `CATIDftDrawing::GetActiveSheet(CATIDftSheet**)`；按索引需先 `GetSheets(CATIUnknownList**)` 再遍历 |
| `pView->SetScale(scale)` | `CATIDftView` 没有 `SetScale`。比例是**图纸页**的属性：`CATIDftSheet::SetScale(double)`/`GetScale(double*)` |
| `pView->GetGeometry(oGeom)` / `CATIDrwGenGeometry` | 不存在。`CATIDftView::GetComponents(const IID&, CATIUnknownList**)` 可按接口类型枚举视图内的子对象 |

## Drawing 对象层级

```
CATDocument (.CATDrawing 文档)
  └── CATIDftDrawing (工程图根；组件 DrwDrawing / Layout2DL)
       ├── CATIDftSheet (图纸页；组件 Sheet / Sheet2DL)
       │    ├── CATIDftView (视图；组件 DrwDetail / View / View2DL)
       │    │    ├── CATIGenerSpec (视图的生成式规格：投影/剖面/详图来源)
       │    │    └── CATIDrwAnnotationFactory (标注/文本/尺寸工厂，见 drawing.annotations)
       │    └── Sheet 2 ...
       └── ...
```

## 基本操作

### 打开已有工程图

```cpp
// 打开 .CATDrawing 文档，取得 CATIDftDrawing
HRESULT OpenDrawingDocument(const CATUnicodeString &iPath,
                             CATDocument *&oDrwDoc,
                             CATIDftDrawing_var &oDrawing) {
    HRESULT hr = CATDocumentServices::OpenDocument(
        const_cast<CATUnicodeString&>(iPath), oDrwDoc, FALSE);
    if (FAILED(hr) || NULL == oDrwDoc) return E_FAIL;

    CATInit *pInit = NULL;
    hr = oDrwDoc->QueryInterface(IID_CATInit, (void **)&pInit);
    if (FAILED(hr) || NULL == pInit) return E_FAIL;

    CATBaseUnknown *pRoot = pInit->GetRootContainer(IID_CATIDftDrawing);
    pInit->Release();
    oDrawing = pRoot;
    return (NULL_var != oDrawing) ? S_OK : E_FAIL;
}
```

### 新建空白工程图

`CATIDrwFactory`（挂在 `CATDrwCont`/`CAT2DLCont`/`DrwDrawing`/`Layout2DL` 组件上）提供从零创建的方法：

```cpp
// oid: 传出创建的 CATIDftDrawing（通过 QueryInterface 转换）
HRESULT CreateBlankDrawing(CATIDrwFactory *pFactory,
                            CATIDftDrawing **oDrawing) {
    if (NULL == pFactory) return E_FAIL;
    return pFactory->CreateDrawing(IID_CATIDftDrawing, (void**)oDrawing, NULL);
}
```

`CATIDrwFactory` 通常从已打开的空白 `.CATDrawing` 文档容器上 `QueryInterface` 获取；也提供 `CreateSheet(IID&, void**)` 单独创建图纸页、`CreateViewWithMakeUp(IID&, void**)` 创建视图骨架（见下）。

### 创建视图

CATIA **没有公开文档化的"一键创建标准三视图/等轴测图"方法**。真实链条比想象中复杂，有两条路径：

**路径一（3D 标注视图转 Drafting 视图）：**

```cpp
// 1) 用 CATITPSViewFactory::CreateView() 在 CATITPSSet 上创建 3D 标注视图
//    （CATTPSInterfaces 框架，获取方式与 drawing.annotations 中标注工厂一致）
HRESULT hr = pTPSViewFactory->CreateView(
    &pTPSView, &iViewPlane, DftFrontView,
    NULL /*ipiTTRSList*/, NULL /*ipViewTransf*/,
    CATTPSViewAssocAsSetting, NULL /*ipiTPSMotherView*/, 0.0);

// 2) 用 CATIDftGenViewFactory::CreateViewFrom3D() 把 CATITPSView 转成 Sheet 上的 CATIDftView
//    （挂在 Sheet/Sheet2DL 组件上）
double origin[3] = {0.0, 0.0, 0.0};
CATIDftView *pDftView = NULL;
hr = pGenViewFactory->CreateViewFrom3D(origin, pTPSView, &pDftView);
```

`CATIDftGenViewFactory` 还提供 `CreateSectionView()`/`CreateStandAloneSectionView()` 专门创建剖视图，同样没有"正视图/俯视图"这种预设封装。

**路径二（骨架 + 生成式规格补全，更常用于批量场景）：**

```cpp
// 用 CATIDrwFactory::CreateViewWithMakeUp() 创建视图骨架
CATIDftView *pView = NULL;
HRESULT hr = pDrwFactory->CreateViewWithMakeUp(IID_CATIDftView, (void**)&pView);

// 再用 CATIGenerSpec::AddProjection()/AddSection() 对该视图追加生成式派生几何
CATIGenerSpec *pGenerSpec = NULL;
pView->GetGenerSpec(&pGenerSpec);
// pGenerSpec->AddProjection(iSketch, iDirection, iMotherView);
```

视图创建后用 `CATIDftSheet::AddView(CATIDftView *iView, double iPosition[2])` 把它放置到图纸页面指定坐标。

`CATDftViewType` 枚举（成员带 `Dft` 前缀）标识视图类型：`DftFrontView`/`DftTopView`/`DftLeftView`/`DftRightView`/`DftBottomView`/`DftRearView`/`DftAuxiliaryView`/`DftIsomView`/`DftSectionView`/`DftSectionCutView`/`DftDetailView`/`DftUnfoldedView`/`DftAxonometricView`/`DftMainView`/`DftBackgroundView`/`DftPureSketch`/`DftUntypedView`。

### 获取图纸页

```cpp
// 活动图纸页
CATIDftSheet_var GetActiveSheet(CATIDftDrawing_var iDrawing) {
    CATIDftSheet_var spSheet;
    iDrawing->GetActiveSheet(&spSheet);
    return spSheet;
}

// 遍历所有图纸页（没有按索引直接取的方法，需先取列表再遍历）
HRESULT ListAllSheets(CATIDftDrawing_var iDrawing,
                       CATLISTV(CATBaseUnknown_var) &oSheets) {
    CATIUnknownList *pList = NULL;
    HRESULT hr = iDrawing->GetSheets(&pList);
    if (FAILED(hr) || NULL == pList) return E_FAIL;
    for (int i = 0; i < pList->Size(); i++) {
        oSheets.Append(pList->GetElement(i));
    }
    pList->Release();
    return S_OK;
}
```

## 视图 / 图纸属性

```cpp
// 图纸页比例（注意：比例是 Sheet 的属性，不是 View 的）
HRESULT SetSheetScale(CATIDftSheet *pSheet, double scale) {
    return pSheet->SetScale(scale);
}

// 视图名称
CATUnicodeString GetViewName(CATIDftView *pView) {
    wchar_t *pName = NULL;
    pView->GetViewName(&pName);
    CATUnicodeString name(pName);
    return name;
}

// 视图类型
CATDftViewType GetViewType(CATIDftView *pView) {
    CATDftViewType type;
    pView->GetViewType(&type);
    return type;
}

// 按接口类型枚举视图内的子对象（没有统一的 "GetGeometry" 方法）
HRESULT GetViewSubObjects(CATIDftView *pView, const IID &iInterfaceID,
                           CATIUnknownList **oElems) {
    return pView->GetComponents(iInterfaceID, oElems);
}
```

## AI 生成规则

- [ ] 使用 `CATIDftDrawing` 操作工程图文档根，`CATIDftSheet` 是图纸页，`CATIDftView` 是视图
- [ ] 没有"一键创建标准视图"的便捷方法，需要走 `CATITPSViewFactory`+`CATIDftGenViewFactory` 或 `CATIDrwFactory::CreateViewWithMakeUp`+`CATIGenerSpec` 两条真实链条之一
- [ ] 比例（Scale）是 `CATIDftSheet` 的属性，不要误加到 `CATIDftView` 上
- [ ] 视图放置到图纸用 `CATIDftSheet::AddView(view, position[2])`
- [ ] 打开已有图纸走 `CATDocumentServices::OpenDocument()` + `GetRootContainer`；新建空白图纸走 `CATIDrwFactory::CreateDrawing()`
- [ ] 操作 Drawing 前必须先加载到 Session
- [ ] 不要臆造 `CATIDrw*` 前缀的类型名，本框架真实前缀是 `CATIDft*`（对象）+ `CATIDrwFactory`/`CATIDrwAnnotationFactory`（工厂，历史遗留命名）
