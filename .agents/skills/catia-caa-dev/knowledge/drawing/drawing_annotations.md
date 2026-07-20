---
id: drawing.annotations
title: Drawing Annotations
category: knowledge
domain: drawing
keywords: [annotation, dimension, table, title block, BOM, text, GD&T]
apis: [CATIDrwAnnotationFactory, CATIDftText, CATDrwDimType]
requires: [drawing.basics]
patterns: [drawing.batch]
examples: []
release: [R19, R28]
tags: [drawing, annotation, dimension]
---

# CAA Drawing Annotations

标注（Annotations）是工程图的输出内容：尺寸、文字、表格、标题栏。

## ⚠️ 重要修正

本文档早期版本使用了虚构的 `CATIDrw*` 接口体系（`CATIDrwDimFactory`/`CATIDrwDim`/`CATIDrwTextFactory`/`CATIDrwTable`/`CATIDrwTableFactory`/`CATIDrwTitleBlock`），经本地 CAADoc（`DraftingInterfaces` 框架 SDK 头文件 + refman 交叉核实）确认这些类型**全部不存在**。详细调研过程见 [pb.batch_drawing](../../playbooks/pb_batch_drawing.md)：

| 错误写法 | 正确写法 |
|------|---------|
| `pView->GetDimFactory(&pFactory)` 拿 `CATIDrwDimFactory` | 尺寸/文本/GD&T 标注统一由 `CATIDrwAnnotationFactory` 提供（`QueryInterface` 从 `View`/`View2DL`/`DrwDetail` 组件获取，用法与其它工厂一致） |
| `CATIDrwDimFactory::CreateLinearDimension(p1, p2, textPos, &pDim)` | `CATIDrwAnnotationFactory::CreateDimension(CATAnnAnnotable** iAnnSelections, int iAnnSelectionNbr, CATDrwDimType iDimType, double *iPosition=NULL, ...)`，线性尺寸对应 `iDimType = DrwDimDistance` 或 `DrwDimLength` |
| `pView->GetTextFactory(&pFactory)` 拿 `CATIDrwTextFactory` | 同样在 `CATIDrwAnnotationFactory` 上：`CreateDftText(double iPosition[2], CATIDftText **oText)` |
| `CATIDrwText` | `CATIDftText`（组件 `DftBalloon`/`DrwBalloon`/`DrwText` 实现），内容用 `SetString(const wchar_t*)`/`GetString(wchar_t**)` |
| `CATIDrwTableFactory::CreateTable()`、`SetCellText`、`MergeCells` | **全部不存在。已知文档缺口**，见下方"表格 / BOM"小节 |
| `CATIDrwTitleBlock::GetTitleBlock()`/`SetField()` | 不存在。标题栏随图纸模板自带，见下方"标题栏"小节 |

## 尺寸标注

真实的尺寸/标注工厂是 `CATIDrwAnnotationFactory`（挂在 `DrwDetail`/`View`/`View2DL` 组件上，从视图对象 `QueryInterface` 获取）。尺寸类型用真实枚举 `CATDrwDimType`（`DraftingInterfaces`，部分成员）：`DrwDimDistance`/`DrwDimLength`/`DrwDimAngle`/`DrwDimRadius`/`DrwDimDiameter`/`DrwDimChamfer`/`DrwDimSlope`/`DrwDimGDT`/`DrwDimDatumFeature`/`DrwDimBalloon` 等。

```cpp
// 通用尺寸创建：iDimType 决定线性/角度/半径/直径等具体含义
// 注意：CreateDimension 返回值是 CATIDrwDimDimension_var，不是 HRESULT
CATIDrwDimDimension_var CreateDimension(CATIDftView *pView,
                         CATAnnAnnotable **iSelections, int iSelectionNbr,
                         CATDrwDimType iDimType,
                         double *iPosition /* [2], 可为 NULL 自动放置 */) {
    CATIDrwAnnotationFactory *pFactory = NULL;
    HRESULT hr = pView->QueryInterface(
        IID_CATIDrwAnnotationFactory, (void**)&pFactory);
    if (FAILED(hr)) return NULL_var;

    CATIDrwDimDimension_var spDim = pFactory->CreateDimension(
        iSelections, iSelectionNbr, iDimType, iPosition);
    pFactory->Release();
    return spDim;
}

// 线性尺寸示例：DrwDimDistance
// CreateDimension(pView, selections, 2, DrwDimDistance, NULL);

// 直径标注示例：DrwDimDiameter
// CreateDimension(pView, selections, 1, DrwDimDiameter, NULL);
```

注意：refman 与 SDK 头文件对 `CreateDimension` 的重载参数列表存在差异（SDK 头文件更全，以其为准），实际项目中要用 `--query CATIDrwAnnotationFactory` 核对当前 CATIA 版本的确切签名。

## 文本标注

```cpp
// 简单文本（CATIDftText）
CATIDftText *CreateDftText(CATIDftView *pView,
                            const CATUnicodeString &iText,
                            double iPosition[2]) {
    CATIDrwAnnotationFactory *pFactory = NULL;
    HRESULT hr = pView->QueryInterface(
        IID_CATIDrwAnnotationFactory, (void**)&pFactory);
    if (FAILED(hr)) return NULL;

    CATIDftText *pText = NULL;
    hr = pFactory->CreateDftText(iPosition, &pText);
    pFactory->Release();
    if (FAILED(hr) || NULL == pText) return NULL;

    pText->SetString(iText.ConvertToWChar());
    return pText;
}

// 读取/修改已有文本内容
void SetTextContent(CATIDftText *pText, const CATUnicodeString &iNewText) {
    pText->SetString(iNewText.ConvertToWChar());
}
```

带引线的标注（气泡/球标）用 `CATIDrwAnnotationFactory::CreateDftBalloon(double iLeaderPos[2], double iPos[2], CATUnicodeString &iText, CATIDftBalloon **oBalloon)`。

## 表格 / BOM — 已知文档缺口

图纸内表格/BOM 的真实接口是 `CATIAnnBOM`（组件 `AnnBOM` 实现）/`CATIAnnBOMs`（组件 `DrwDrawing` 实现）/`CATIAnnBOMRepresentation`（组件 `DrwTable` 实现），三者在发布产品字典（`.dic`，ground truth）中确认真实存在，但**本地 SDK 头文件目录和 refman htm 文档都没有公开它们的方法签名**——这是文档缺口，不是虚构 API，不能凭空编造 `CreateTable`/`SetCellText`/`MergeCells` 这类方法名。

建议降级方案：
- 只需要 BOM **数据**（零件号/数量/层级）：直接复用 [pb.export_bom](../../playbooks/pb_export_bom.md) 已核实的 `CATIProduct` 遍历模式，独立导出为 CSV/Excel/JSON，不依赖图纸内表格对象
- 确实需要把表格**嵌入图纸页面**：CAA C++ 层暂无可核实的文档化 API，可考虑改用 Automation 层的 `CATIADrawingTables`/`CATIADrawingTable`（VBA/COM 接口，`.idl` 中确认存在：`CATIADrawingTables::Add(iPositionX, iPositionY, iNumberOfRow, iNumberOfColumn, iRowHeight, iColumnWidth, out CATIADrawingTable)`），但这是与 CAA C++ 完全不同的编程模型，需要 COM 互操作或宏桥接，不能在 CAA C++ 代码里直接调用

## 标题栏

标题栏（Title Block）**没有独立的 CAA C++ 编程接口**：它随图纸模板（`.CATDrawing` 模板文件）自带，是模板内预置的文本/表格对象。动态填充内容的标准做法是通过 Knowledgeware 发布参数（`CATICkeParm`，见 [cap.parameter_system](../../capabilities/parameter-system.md)）把 Part/Product 属性关联到模板中预置的公式驱动文本上，而不是程序化调用一个"设置字段"的方法。

```cpp
// 标题栏字段填充的真实做法：走参数发布 + 公式关联，
// 不是虚构的 CATIDrwTitleBlock::SetField()
// 1. 在模板中，标题栏文本预先关联到已发布参数（例如 "PartNumber_Param"）
// 2. 运行时只需要设置该发布参数的值，模板自带的公式会自动刷新显示文本
// 具体发布参数读写方法见 cap.parameter_system（CATICkeParm::ValuateFromString 等）
```

若确实需要跳过模板机制直接操作标题栏内的文本对象，本质上它们也是 `CATIDftText`，可以按前面"文本标注"小节的方式定位后 `SetString()`，但需要先通过选择/遍历找到具体的文本对象实例（没有 `GetTitleBlock()` 这样的直达方法）。

## AI 生成规则

- [ ] 尺寸、文本、GD&T 统一由 `CATIDrwAnnotationFactory` 创建（从视图 `QueryInterface` 获取），没有分离的 DimFactory/TextFactory
- [ ] 尺寸类型用真实枚举 `CATDrwDimType`（`DrwDimDistance`/`DrwDimLength`/`DrwDimAngle`/`DrwDimRadius`/`DrwDimDiameter` 等），不要发明枚举名
- [ ] 文本对象是 `CATIDftText`，内容用 `SetString`/`GetString`（`wchar_t*`，注意编码转换）
- [ ] 图纸表格/BOM 是已知文档缺口：数据导出走 `pb.export_bom`，嵌入表格走 Automation 层 `CATIADrawingTables`，CAA C++ 层不要编造 `CreateTable`/`SetCellText` 之类方法
- [ ] 标题栏没有编程接口，通过模板 + Knowledgeware 发布参数关联实现动态填充
- [ ] 批量操作先检查 Part 是否存在
- [ ] 输出路径提前创建父目录
