---
id: pb.export_bom
title: Export BOM / 导出物料清单
category: playbook
domain: product
keywords: [BOM, export, Excel, JSON, CSV, product tree, assembly, instance, reference]
capabilities: [cap.assembly_tree, cap.document_export, cap.parameter_system]
apis: [CATIProduct, CATIPrtContainer, CATIChildren, CATIProductOccurrence]
frameworks: [CATAssemblyInterfaces, CATProductStructure]
difficulty: intermediate
effort: medium
release: [R19, R28]
tags: [playbook, BOM, export]
---

# Export BOM (导出物料清单)

从 CATIA 装配体提取多层 BOM 结构，导出为 Excel/JSON/CSV。

## 目标

遍历装配树，提取每个节点的层级、名称、零件号、数量、属性，输出为结构化文件。

## 前置条件

- 已加载 CATProduct 文档
- 零件属性已填写（PartNumber、Description、Material 等）
- 输出目录存在

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.assembly_tree` | 遍历多层装配结构 |
| `cap.parameter_system` | 读取零件属性和参数 |
| `cap.document_export` | 输出 Excel/JSON/CSV |

## 实现步骤

1. **获取根 Product**
2. **递归遍历**：区分 Instance（子装配）和 Leaf（零件）
3. **收集属性**：PartNumber, InstanceName, Description, Quantity
4. **构建 BOM 表**：层级缩进、数量汇总
5. **导出**：CSV 写文件，或 JSON 构建对象

## BOM 结构

```cpp
struct BOMRow {
    int level;              // 缩进层级
    CATUnicodeString name;  // Instance Name
    CATUnicodeString partNumber; // Part Number
    int quantity;           // 数量
    CATUnicodeString material;
};
```

## 关键代码

```cpp
void TraverseBOM(CATISpecObject *iProduct, int level, CATListValBOMRow &oRows) {
    BOMRow row;
    row.level = level;
    row.name = GetInstanceName(iProduct);
    row.partNumber = GetAttribute(iProduct, "PartNumber");
    oRows.Append(row);

    // 遍历子节点
    CATIPrtContainer_var spContainer = iProduct;
    CATListValCATISpecObject children;
    spContainer->ListChildren(children);

    for (int i = 1; i <= children.Size(); i++) {
        TraverseBOM(children[i], level + 1, oRows);
    }
}

HRESULT ExportToCSV(CATListValBOMRow &rows, const CATUnicodeString &path) {
    FILE *f = fopen(path.ConvertToChar(), "w");
    fprintf(f, "Level,Name,PartNumber,Quantity\n");
    for (int i = 1; i <= rows.Size(); i++) {
        BOMRow &r = rows[i];
        fprintf(f, "%d,%s,%s,%d\n",
            r.level, r.name.ConvertToChar(),
            r.partNumber.ConvertToChar(), r.quantity);
    }
    fclose(f);
    return S_OK;
}
```

## 注意事项

- Instance 和 Reference 的区别：Instance 数 ≠ 零件种类数
- 大装配（>1000 节点）注意递归深度和性能
- CATUnicodeString → char* 转换注意编码
- 报价表通常需要固定格式，建议用模板 JSON 定义列映射

## 相关 Playbook

- `pb.auto_color` — BOM 导出后可同时输出颜色信息
