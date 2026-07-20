---
id: pb.batch_drawing
title: Batch Drawing Generation / 批量工程图生成
category: playbook
domain: drawing
keywords: [drawing, batch, sheet, view, projection, section, BOM, title block, template]
capabilities: [cap.document_export, cap.assembly_tree, cap.parameter_system, cap.annotation]
apis: [CATIDftDrawing, CATIDftSheet, CATIDftView, CATIDftGenViewFactory, CATIDrwFactory, CATIGenerSpec, CATITPSViewFactory, CATIProduct]
frameworks: [DraftingInterfaces, CATTPSInterfaces, CATAssemblyInterfaces, AutomationInterfaces]
difficulty: advanced
effort: large
release: [R19, R28]
tags: [playbook, drawing, batch, automation]
---

# Batch Drawing Generation (批量工程图生成)

对装配体中每个零件或子装配自动生成工程图：视图 + BOM数据 + 标题栏信息。

## ⚠️ 重要修正

本文档早期版本大量使用了虚构的 `CATIDrw*` 接口体系（`CATIDrwView`/`CATIDrwSheet`/`CATIDrwDim`/`CATIDrwTable`/`CATIDrwDocument`/`CATIDrwViewFactory`/`CATIDrwTitleBlock`），经本地 CAADoc（`DraftingInterfaces`/`CATTPSInterfaces` 框架）核实，这些类型**全部不存在**（CAADoc 零匹配）。真实的图纸对象模型前缀是 `CATIDft*`（Drafting），且视图创建体系比"一键便捷方法"设想的复杂得多：

| 错误写法 | 问题 | 正确写法 |
|------|------|---------|
| `CATIDrwDocument::Open()` | 接口不存在 | 用 `CATDocumentServices::OpenDocument()`（见 [cap.document_export](../capabilities/document-export.md)）打开 `.CATDrawing` 文档，再 `QueryInterface`/`GetRootContainer` 拿到 `CATIDftDrawing` |
| `CATIDrwSheet::AddSheet()` | `CATIDrwSheet` 不存在 | 真实接口是 `CATIDftDrawing::AddSheet(CATIDftSheet** oSheet, wchar_t* iName=NULL, ...)` |
| `CATIDrwViewFactory::CreateView()`（"Front/Top/Right/ISO 一键创建"） | **整个便捷工厂不存在**，CAADoc 无任何匹配。真实的视图创建体系没有 `CreateFrontView`/`CreateTopView` 这类一键方法 | 见下方"视图创建的真实链条" |
| `AddFrontView(spSheet, spChild)` 等自定义"一键视图"函数 | 这些函数名是虚构的封装，底层调用的 API 全部不存在 | 需要手工组装：`CATITPSViewFactory::CreateView()` 或 `CATIDftGenViewFactory::CreateViewFrom3D()` 创建 View，再 `CATIDftSheet::AddView()` 挂到 Sheet 上 |
| `CATIDrwTable::BuildBOM()` | 不存在 | 图纸内 BOM 表格的真实接口是 `CATIAnnBOM`/`CATIAnnBOMs`/`CATIAnnBOMRepresentation`（组件 `AnnBOM`/`DrwDrawing` 在 `.dic` 中确认实现），但**本地 SDK 头文件和 refman 文档都没有公开这几个接口的方法签名**（已知文档缺口，见下方说明），不能凭空臆造方法名 |
| 标题栏用 `CATDrwText` 填充，`CATIDrwTitleBlock` | 两者都不存在（CAADoc 零匹配） | 标题栏通常随图纸模板自带，内容用发布参数（Knowledgeware `CATICkeParm`）关联，或走 Automation 层 |
| `spDrw->SaveAs(outPath)` | `CATIDftDrawing`/`CATDocument` 都没有 `SaveAs` 成员方法 | 用静态方法 `CATDocumentServices::SaveAs(CATDocument&, CATUnicodeString& iName, CATUnicodeString& iType, CATBoolean)` |
| `CATIPrtContainer::ListChildren()` 遍历装配 | `CATIPrtContainer` 是 Part 文档容器接口，与装配树无关；且没有 `ListChildren` 方法 | 装配遍历用 `CATIProduct::GetChildren()`（见 [cap.assembly_tree](../capabilities/assembly-tree.md)） |

### 视图创建的真实链条（无一键便捷方法，需诚实说明）

核实结论：CATIA 没有公开文档化的"一键创建标准三视图/等轴测图"方法。实际能拼出的真实链条有两条，都比想象中复杂：

1. **`CATITPSViewFactory::CreateView()`**（`CATTPSInterfaces` 框架，挂在 `CATITPSSet` 实例上，需 `QueryInterface` 获取，用法与 [cap.annotation](../capabilities/annotation.md) 中标注工厂的获取模式一致）：
   ```
   CreateView(CATITPSView** oTPSView, CATMathPlane* iViewPlane, CATDftViewType iViewType,
              CATITTRSList* ipiTTRSList=NULL, CATMathTransformation* ipViewTransf=NULL,
              CATTPSViewAssociativity iAssocAtCreation=CATTPSViewAssocAsSetting,
              CATITPSView* ipiTPSMotherView=NULL, double iZFromMotherView=0.0)
   ```
   产出 `CATITPSView`（3D 标注视图），可用 `CATITPSView::GetDraftingView(CATIDftView**)` 反查关联的 Drafting 视图对象。
2. **`CATIDftGenViewFactory::CreateViewFrom3D(double* iptOrigin, IUnknown* ipiTPSView, CATIDftView** opiDftView)`**（挂在 `Sheet`/`Sheet2DL` 组件上）——把上一步的 `CATITPSView` 转成 Sheet 上的 `CATIDftView`。该工厂还有 `CreateSectionView()`/`CreateStandAloneSectionView()`，专门用于剖视图，同样没有"正视图/俯视图/等轴测"这种预设封装。
3. 视图创建后用 `CATIDftSheet::AddView(CATIDftView* iView, double iPosition[2])` 把它放置到图纸页面上的指定坐标。
4. `CATDftViewType` 枚举（无接口名前缀，成员**带** `Dft` 前缀）用于告知系统这是哪类视图：`DftFrontView`/`DftTopView`/`DftLeftView`/`DftRightView`/`DftBottomView`/`DftRearView`/`DftIsomView`/`DftSectionView`/`DftDetailView`/`DftAuxiliaryView` 等。

实践中，很多团队并不走这条底层 C++ API 链条批量出图，而是：
- 用 `CATIDrwFactory::CreateViewWithMakeUp(IID&, void**)`（`DraftingInterfaces`，挂在 `DrwDrawing`/`Layout2DL` 组件；SDK 头文件标注旧方法 `CreateView()`/`CreateViewName()` 为 `@nodoc` 且已被此方法取代）创建视图骨架，再用 `CATIGenerSpec::AddProjection()`/`AddSection()`（挂在 `View`/`View2DL` 组件，对**已存在的 View** 追加生成式派生几何）补全内容；
- 或者用 CATIA 宏录制 / Automation 层 `CATIADrawingViews`（VBA 兼容接口）驱动批量出图，绕开手工组装 TPS/Dft 底层链条。

本 Playbook 展示可编译的骨架代码（创建 Drawing / Sheet / 挂载已有 View / 保存），视图内容生成部分保留为需要结合具体项目几何选择补充的接口调用点，不臆造不存在的封装方法。

### 图纸内 BOM 表格 — 已知文档缺口

`CATIAnnBOM`（组件 `AnnBOM` 实现）/`CATIAnnBOMs`（组件 `DrwDrawing` 实现，用于管理图纸上的 BOM 表格集合）/`CATIAnnBOMRepresentation`（组件 `DrwTable` 实现，表格的可视化表现）三个接口在发布产品字典（`.dic`，ground truth）中确认真实存在，但**本地 SDK 头文件目录（`DraftingInterfaces/PublicInterfaces/`）和 refman htm 文档中都找不到它们的方法签名**——这是一个文档缺口，不是虚构 API，但目前无法给出经过核实的具体方法调用代码。

建议：
- 如果只需要 BOM **数据**（零件号/数量/层级），直接复用 [pb.export_bom](pb_export_bom.md) 已核实的 `CATIProduct` 遍历模式，导出为独立的 CSV/Excel/JSON，不依赖图纸内表格对象；
- 如果确实需要把表格**嵌入图纸页面**，CAA C++ 层暂无可核实的文档化 API，可考虑改用 Automation 层的 `CATIADrawingTables`/`CATIADrawingTable`（VBA/COM 接口，`.idl` 中确认存在：`CATIADrawingTables::Add(iPositionX, iPositionY, iNumberOfRow, iNumberOfColumn, iRowHeight, iColumnWidth, out CATIADrawingTable)`），但这是与 CAA C++ 完全不同的编程模型（Automation/IDispatch），不能在 CAA C++ 代码里直接调用，需要通过 COM 互操作或宏桥接。

## 目标

选中装配体 → 遍历所有子零件 → 为每个零件创建/更新工程图 Sheet → 挂载已生成的视图 → 输出 BOM 数据 → 保存文档。

## 前置条件

- 已加载 CATProduct 及所有 CATPart
- 工程图模板（.CATDrawing）存在，且已包含所需的 3D 标注视图（`CATITPSView`）或已知如何为每个零件生成
- 可选：输出目录

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.assembly_tree` | 遍历装配获取所有子零件 |
| `cap.parameter_system` | 读取零件属性用于标题栏/BOM |
| `cap.document_export` | 打开模板文档、保存输出文档 |
| `cap.annotation` | 通过 `CATITPSSet`/`CATITPSViewFactory` 创建 3D 标注视图，供转成 Drafting 视图 |

## 实现步骤

1. **打开工程图模板**：`CATDocumentServices::OpenDocument()` 打开 `.CATDrawing`，`QueryInterface`/`CATInit::GetRootContainer(IID_CATIDftDrawing)` 拿到 `CATIDftDrawing`
2. **遍历装配树**：`CATIProduct::GetChildren()` 递归获取每个 Leaf Part（见 [cap.assembly_tree](../capabilities/assembly-tree.md)）
3. **创建/获取 Sheet**：`CATIDftDrawing::AddSheet(CATIDftSheet**, wchar_t* iName)` 或 `GetActiveSheet()`
4. **挂载视图**：对已经生成好的 `CATIDftView`（通过 `CATITPSViewFactory`/`CATIDftGenViewFactory` 链条产出，或模板中已存在），调用 `CATIDftSheet::AddView(view, position)`
5. **收集 BOM 数据**：复用 `pb.export_bom` 的遍历模式，独立导出，不写入图纸表格对象
6. **保存**：`CATDocumentServices::SaveAs(*pDrwDoc, outPath, "CATDrawing", FALSE)`

## 关键代码

```cpp
// 遍历装配子零件，收集需要出图的叶子节点
// （复用 cap.assembly_tree 已核实的 CATIProduct::GetChildren 直接返回值模式）
void CollectLeafParts(CATIProduct_var iProduct,
                       CATListValCATBaseUnknown_var &oLeafParts) {
    CATListValCATBaseUnknown_var *pChildren = iProduct->GetChildren();
    if (NULL == pChildren || pChildren->Size() == 0) {
        oLeafParts.Append(iProduct);   // 无子节点，视为叶子零件
        if (NULL != pChildren) delete pChildren;
        return;
    }
    for (int i = 1; i <= pChildren->Size(); i++) {
        CATIProduct_var spChild = (*pChildren)[i];
        if (NULL_var != spChild) {
            CollectLeafParts(spChild, oLeafParts);
        }
    }
    delete pChildren;
}

// 打开图纸模板，返回 CATIDftDrawing
HRESULT OpenDrawingTemplate(const CATUnicodeString &iTemplatePath,
                             CATDocument *&oDrwDoc,
                             CATIDftDrawing_var &oDrawing) {
    HRESULT hr = CATDocumentServices::OpenDocument(
        const_cast<CATUnicodeString&>(iTemplatePath), oDrwDoc, FALSE);
    if (FAILED(hr) || NULL == oDrwDoc) return E_FAIL;

    CATInit *pInit = NULL;
    hr = oDrwDoc->QueryInterface(IID_CATInit, (void **)&pInit);
    if (FAILED(hr) || NULL == pInit) return E_FAIL;

    CATBaseUnknown *pRoot = pInit->GetRootContainer(IID_CATIDftDrawing);
    pInit->Release();
    oDrawing = pRoot;
    return (NULL_var != oDrawing) ? S_OK : E_FAIL;
}

// 把一个已经创建好的 CATIDftView 挂载到 Sheet 的指定位置
HRESULT PlaceViewOnSheet(CATIDftSheet_var iSheet, CATIDftView_var iView,
                          double iX, double iY) {
    if (NULL_var == iSheet || NULL_var == iView) return E_FAIL;
    double position[2] = { iX, iY };
    return iSheet->AddView(iView, position);
}

// 批量流程骨架：每个零件一张图纸，把该零件已生成的视图挂载后保存
// 注意：CreateViewForPart() 留空为接口调用点 —— 具体视图几何生成需要结合
// CATITPSViewFactory::CreateView()（见 cap.annotation 的 QueryInterface 获取模式）
// 和 CATIDftGenViewFactory::CreateViewFrom3D() 组装，或直接引用模板中已有的视图，
// 这里不再臆造 AddFrontView()/AddTopView() 之类不存在的便捷封装
HRESULT BatchGenerateDrawings(CATIProduct_var iRoot,
                               const CATUnicodeString &iTemplatePath,
                               const CATUnicodeString &iOutputDir) {
    CATListValCATBaseUnknown_var leafParts;
    CollectLeafParts(iRoot, leafParts);

    for (int i = 1; i <= leafParts.Size(); i++) {
        CATIProduct_var spPart = leafParts[i];
        if (NULL_var == spPart) continue;

        CATUnicodeString partNumber = spPart->GetPartNumber();

        CATDocument *pDrwDoc = NULL;
        CATIDftDrawing_var spDrawing;
        if (FAILED(OpenDrawingTemplate(iTemplatePath, pDrwDoc, spDrawing))) {
            continue;
        }

        CATIDftSheet_var spSheet;
        spDrawing->GetActiveSheet(&spSheet);
        if (NULL_var == spSheet) continue;

        // CreateViewForPart(spPart, spSheet) — 见上方说明，留给项目按需实现
        // PlaceViewOnSheet(spSheet, spView, 100.0, 150.0);

        CATUnicodeString outPath = iOutputDir + "/" + partNumber + ".CATDrawing";
        CATUnicodeString drawingType("CATDrawing");
        CATDocumentServices::SaveAs(*pDrwDoc, outPath, drawingType, FALSE);
        CATDocumentServices::Remove(*pDrwDoc);
    }
    return S_OK;
}
```

## 注意事项

- 大装配建议分批生成，每批 10-20 个零件
- **视图内容生成没有一键 API**：批量出图前需要先确认模板/零件是否已有可复用的 `CATITPSView`（3D 标注视图），或规划好 `CATITPSViewFactory::CreateView()` 的调用参数（视角平面 `CATMathPlane`、`CATDftViewType`）
- BOM 表格内容建议独立导出（见 `pb.export_bom`），不要假设存在 CAA C++ 层的一键 BOM 表格生成 API
- 标题栏内容随图纸模板自带，如需动态填充，通过 Knowledgeware 发布参数关联到模板中预置的文本对象，而不是虚构的 `CATDrwText`/`CATIDrwTitleBlock`
- `CATUnicodeString` → `char*` 转换注意编码

## 相关 Playbook

- `pb.export_bom` — BOM 数据提取，建议在批量出图前先单独导出确认零件列表

## 已知遗留风险（未在本 Playbook 范围内核实，供后续排查）

以下文档同样大量使用了本次修正中发现的虚构 `CATIDrw*` 接口体系，尚未核实修正：
- `knowledge/drawing/drawing_basics.md`
- `knowledge/drawing/drawing_annotations.md`
- `patterns/drawing/batch_drawing.md`
