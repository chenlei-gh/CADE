---
id: pb.assembly_stats
title: Assembly Statistics / 装配统计
category: playbook
domain: product
keywords: [assembly, statistics, count, mass, volume, summary, product tree]
capabilities: [cap.assembly_tree, cap.parameter_system, cap.update_mechanism]
apis: [CATIProduct, CATIPrtContainer, CATIMeasurable, CATIChildren, CATIProductOccurrence]
frameworks: [CATAssemblyInterfaces, CATMecModUseItf, CATProductStructure]
difficulty: intermediate
effort: medium
release: [R19, R28]
tags: [playbook, assembly, statistics]
---
# Assembly Statistics (装配统计)

遍历装配体，统计零件数、质量、体积等汇总信息，输出到对话框或文件。

## 目标

- 零件总数 / 唯一零件数
- 总质量 / 总体积
- 按类型（零件/子装配/标准件）分类统计
- 属性汇总（材料分布、供应商统计）

## 实现步骤

1. **获取根 Product** → `CATISpecObject_var spRoot`
2. **递归遍历** → 使用 Visitor 或递归遍历 Children
3. **识别类型** → `IsATypeOf("CATPart")` vs `IsATypeOf("CATProduct")`
4. **收集属性** → PartNumber, InstanceName, Material
5. **获取物理属性** → `CATIMeasurable::GetMass()`, `GetVolume()`
6. **展示结果** → Dialog List + 导出 CSV

## 关键代码骨架

```cpp
struct AssemblyStats {
    int partCount = 0;
    int productCount = 0;
    double totalMass = 0.0;
    double totalVolume = 0.0;
};

HRESULT CollectStats(CATISpecObject *iProduct, AssemblyStats &oStats) {
    CATIPrtContainer_var spContainer = iProduct;
    if (NULL_var == spContainer) return S_OK;

    CATListValCATISpecObject children;
    spContainer->ListChildren(children);

    for (int i = 1; i <= children.Size(); i++) {
        CATISpecObject_var spChild = children[i];

        // 收集物理属性
        CATIMeasurable_var spMeasurable = spChild;
        if (NULL_var != spMeasurable) {
            double mass = 0.0;
            spMeasurable->GetMass(mass);
            oStats.totalMass += mass;
        }

        // 递归处理子装配
        CollectStats(spChild, oStats);
    }
    return S_OK;
}
```

## 注意事项

- 大装配用 `CATIModelEvents::SetContext()` 暂停 Update
- Instance 和 Reference 分开统计
- 物理属性计算耗时——考虑用户取消操作
- 使用进度条（`CATIProgress`）提升用户体验
