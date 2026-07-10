---
id: drawing.annotations
title: Drawing Annotations
category: knowledge
domain: drawing
keywords: [annotation, dimension, table, title block, BOM, text, GD&T]
apis: [CATIDrwDim, CATIDrwText, CATIDrwTable, CATIDrwAnnotation]
requires: [drawing.basics]
patterns: [drawing.batch]
examples: []
release: [R19, R28]
tags: [drawing, annotation, dimension]
---

# CAA Drawing Annotations

标注（Annotations）是工程图的输出内容：尺寸、文字、表格、标题栏。

## 尺寸标注

```cpp
// 线性尺寸
HRESULT CreateLinearDimension(CATIDrwView *pView,
                                CATMathPoint &p1, CATMathPoint &p2,
                                CATMathPoint &textPos) {
    CATIDrwDimFactory *pFactory = NULL;
    pView->GetDimFactory(&pFactory);
    
    CATIDrwDim *pDim = NULL;
    pFactory->CreateLinearDimension(p1, p2, textPos, &pDim);
    pFactory->Release();
    return S_OK;
}

// 直径/半径标注
HRESULT CreateDiameterDim(CATIDrwView *pView,
                           CATMathPoint &center, double radius,
                           CATMathPoint &textPos) {
    // ...
}
```

## 文本标注

```cpp
// 简单文本
CATIDrwText *CreateText(CATIDrwView *pView,
                          const CATUnicodeString &iText,
                          CATMathPoint &position) {
    CATIDrwTextFactory *pFactory = NULL;
    pView->GetTextFactory(&pFactory);
    
    CATIDrwText *pText = NULL;
    pFactory->CreateText(iText, position, &pText);
    pFactory->Release();
    return pText;
}

// 带引线的文本
CATIDrwText *CreateTextWithLeader(CATIDrwView *pView,
                                    const CATUnicodeString &iText,
                                    CATMathPoint &anchor,
                                    CATMathPoint &textPos) {
    // ...
}
```

## 表格 / BOM

```cpp
// 创建表格
CATIDrwTable *CreateTable(CATIDrwSheet *pSheet,
                           int rows, int columns,
                           CATMathPoint &position,
                           double rowHeight, double colWidth) {
    CATIDrwTableFactory *pFactory = NULL;
    pSheet->GetTableFactory(&pFactory);
    
    CATIDrwTable *pTable = NULL;
    pFactory->CreateTable(rows, columns,
        position, rowHeight, colWidth, &pTable);
    pFactory->Release();
    return pTable;
}

// 填充表格
void FillTable(CATIDrwTable *pTable, int row, int col,
               const CATUnicodeString &text) {
    pTable->SetCellText(row, col, text);
}

// 合并单元格
void MergeCells(CATIDrwTable *pTable,
                int startRow, int startCol,
                int endRow, int endCol) {
    pTable->MergeCells(startRow, startCol, endRow, endCol);
}
```

## 标题栏

```cpp
// 填充标准标题栏字段
void FillTitleBlock(CATIDrwSheet *pSheet,
                    const CATUnicodeString &partName,
                    const CATUnicodeString &partNumber,
                    const CATUnicodeString &material,
                    const CATUnicodeString &scale) {
    CATIDrwTitleBlock *pTitle = NULL;
    pSheet->GetTitleBlock(&pTitle);
    
    pTitle->SetField("PartName",   partName);
    pTitle->SetField("PartNumber", partNumber);
    pTitle->SetField("Material",   material);
    pTitle->SetField("Scale",      scale);
    pTitle->Release();
}
```

## 批量输出

```cpp
// 批量输出多个 Part 的工程图
HRESULT BatchCreateDrawings(CATListValCATISpecObject &parts,
                              const CATUnicodeString &drawingTemplate) {
    for (int i = 1; i <= parts.Size(); i++) {
        CATISpecObject *pPart = parts[i];
        CATUnicodeString drawingPath = GetOutputPath(pPart);
        
        // 创建 Drawing
        CATIDftDrawing *pDrawing = NULL;
        HRESULT hr = CreateDrawingFromTemplate(pPart,
            drawingTemplate, &pDrawing);
        if (FAILED(hr)) continue;
        
        // 生成视图
        CreateFrontView(pDrawing, pPart);
        CreateTopView(pDrawing, pPart);
        
        // 填充标题栏
        FillTitleBlock(pDrawing->GetCurrentSheet(),
            GetPartName(pPart), GetPartNumber(pPart), ...);
        
        // 保存
        pDrawing->SaveAs(drawingPath);
        pDrawing->Release();
    }
    return S_OK;
}
```

## AI 生成规则

- [ ] 尺寸用 `CATIDrwDimFactory`，文本用 `CATIDrwTextFactory`
- [ ] 表格用 `CATIDrwTableFactory` → `CreateTable`
- [ ] 合并单元格用 `MergeCells`，填充用 `SetCellText`
- [ ] 标题栏用 `CATIDrwTitleBlock` → `SetField`
- [ ] 批量操作先检查 Part 是否存在
- [ ] 输出路径提前创建父目录
