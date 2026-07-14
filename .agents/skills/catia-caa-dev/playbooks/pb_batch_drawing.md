---
id: pb.batch_drawing
title: Batch Drawing Generation / 批量工程图生成
category: playbook
domain: drawing
keywords: [drawing, batch, sheet, view, projection, section, BOM, title block, template]
capabilities: [cap.document_export, cap.assembly_tree, cap.parameter_system]
apis: [CATIDrwView, CATIDrwSheet, CATIDrwDim, CATIDrwTable, CATIProduct]
frameworks: [CATDrwInterfaces, CATAssemblyInterfaces, AutomationInterfaces]
difficulty: advanced
effort: large
release: [R19, R28]
tags: [playbook, drawing, batch, automation]
---

# Batch Drawing Generation (批量工程图生成)

对装配体中每个零件或子装配自动生成工程图：三视图 + BOM表 + 标题栏。

## 目标

选中装配体 → 遍历所有子零件 → 为每个零件创建工程图 → 自动布置视图 → 输出为 DWG/PDF。

## 前置条件

- 已加载 CATProduct 及所有 CATPart
- 工程图模板（.CATDrawing）存在
- 可选：视图配置（前视图/俯视图/右视图/等轴测）
- 可选：输出目录

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.assembly_tree` | 遍历装配获取所有子零件 |
| `cap.parameter_system` | 读取零件属性填入标题栏 |
| `cap.document_export` | 导出 DWG/PDF |

## 实现步骤

1. **加载工程图模板**：`CATIDrwDocument::Open()`
2. **遍历装配树**：获取每个 Leaf Part
3. **创建 Sheet**：`CATIDrwSheet::AddSheet()`
4. **布置视图**：`CATIDrwViewFactory::CreateView()` — Front/Top/Right/ISO
5. **填充标题栏**：PartNumber, Material, Scale, Date
6. **生成 BOM 表**：`CATIDrwTable::BuildBOM()`
7. **导出**：`CATIDrwDocument::SaveAs("PDF")` 或 `ExportToDWG()`

## 关键代码

```cpp
HRESULT BatchGenerateDrawings(CATISpecObject *iRoot,
                               const CATUnicodeString &outputDir) {
    CATIPrtContainer_var spContainer = iRoot;
    CATListValCATISpecObject children;
    spContainer->ListChildren(children);

    for (int i = 1; i <= children.Size(); i++) {
        CATISpecObject_var spChild = children[i];
        CATUnicodeString partName = GetPartNumber(spChild);
        
        // Create drawing for this part
        CATIDrwDocument_var spDrw = CreateDrawingFromTemplate();
        CATIDrwSheet_var spSheet = spDrw->GetActiveSheet();
        
        // Add views
        AddFrontView(spSheet, spChild);
        AddTopView(spSheet, spChild);
        AddRightView(spSheet, spChild);
        AddIsometricView(spSheet, spChild);
        
        // Fill title block
        FillTitleBlock(spSheet, spChild);
        
        // Save
        CATUnicodeString outPath = outputDir + "/" + partName + ".CATDrawing";
        spDrw->SaveAs(outPath);
    }
    return S_OK;
}
```

## 注意事项

- 大装配建议分批生成，每批 10-20 个零件
- 视图比例自适应：根据零件包围盒自动计算合适的 Scale
- BOM 表生成依赖装配结构，单零件工程图不需要 BOM
- 标题栏文字用 CATDrwText 而非 CATDlgLabel

## 相关 Playbook

- `pb.export_bom` — 可先导出 BOM 确认零件列表再批量出图
