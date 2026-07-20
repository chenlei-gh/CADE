---
id: pb.assembly_stats
title: Assembly Statistics / 装配统计
category: playbook
domain: product
keywords: [assembly, statistics, count, mass, volume, summary, product tree]
capabilities: [cap.assembly_tree, cap.parameter_system, cap.update_mechanism]
apis: [CATIProduct, CATICGMDynMassProperties3D, CATBody]
frameworks: [ProductStructure, GMOperatorsInterfaces, CATAssemblyInterfaces]
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

1. **获取根 Product** → `CATIProduct_var spRoot`（通过 `CATInit::GetRootContainer()` 或 `CATIDocRoots::GiveDocRoots()`）
2. **递归遍历** → 使用 `CATIProduct::GetChildren()`/`GetAllChildren()`
3. **识别类型** → 对子节点 QI 到 `CATIPrtContainer`（`MecModInterfaces`）：成功即为 Part 叶子节点，
   失败则视为子装配（Product）（见下方修正说明）
4. **收集属性** → `GetPartNumber()`, `GetPrdInstanceName()`, Material
5. **获取物理属性** → 通过几何层的 `CATICGMDynMassProperties3D` 操作符（见下方说明），而非 Product 接口本身
6. **展示结果** → Dialog List + 导出 CSV

> ⚠️ **修正 1**：`CATIMeasurable` 接口（`MeasureGeometryInterfaces`）**没有** `GetMass()`/`GetVolume()`
> 方法（CAADoc 核实：该接口仅有 `Angle`/`GetAxisSystem`/`GetEntityType`/`GetShapeName` 等，且多数
> 已在 V5R16 废弃）。真正计算质量/体积的是几何层操作符 `CATICGMDynMassProperties3D`
> （`GMOperatorsInterfaces` 框架），通过全局函数 `CATCGMDynCreateMassProperties3D` 创建，
> 作用对象是 `CATBody`（几何体），而不是 `CATIProduct`/`CATISpecObject`。要统计整个装配的质量，
> 需先拿到每个零件的几何 `CATBody`，再逐个调用该操作符，使用后必须 `Release()`。
>
> ⚠️ **修正 2**：`IsATypeOf("CATPart")`/`IsATypeOf("CATProduct")` 这种写法是错误的——
> `CATBaseUnknown::IsATypeOf()` 的参数是 `CATClassId` 类型常量（如 `CATCylinderType`/`CATFaceType`），
> 不能传字符串；`IsSubTypeOf(CATUnicodeString&)` 才接受字符串，但它比较的是 CAA 组件/Feature
> 的类型名（如官方样例中 `spec->IsSubTypeOf("Solid")`），并不存在名为 `"CATPart"`/`"CATProduct"`
> 的类型字符串。CAADoc 官方样例（`CAAAuiCreateFixConstraintInPart.cpp`）区分
> "这是 Part 文档还是装配"的真实做法是：对该节点的规格容器 QI 到 `CATIPrtContainer`——
> 成功则说明它是 Part（可继续 `GetPart()` 拿到 `CATIPrtPart`），失败则是装配/子产品。

## 关键代码骨架

```cpp
struct AssemblyStats {
    int partCount = 0;
    int productCount = 0;
    double totalMass = 0.0;
    double totalVolume = 0.0;
};

HRESULT CollectStats(CATIProduct *iProduct, AssemblyStats &oStats) {
    if (NULL == iProduct) return S_OK;

    CATListValCATBaseUnknown_var *pChildren = iProduct->GetChildren();
    if (NULL != pChildren) {
        for (int i = 1; i <= pChildren->Size(); i++) {
            CATIProduct_var spChild = (*pChildren)[i];
            if (NULL_var == spChild) continue;

            // 几何质量属性需从零件的 CATBody 获取，参见上方说明
            // 这里仅示意计数逻辑；GetMass/GetVolume 需通过
            // CATICGMDynMassProperties3D 操作符对 CATBody 计算

            // 递归处理子装配
            CollectStats(spChild, oStats);
        }
        delete pChildren;
    }
    return S_OK;
}
```

## 注意事项

- 大装配建议先关闭自动 Update（参见 `philo.updates`）再递归遍历，避免递归过程中反复触发重计算
  （注意：`CATIModelEvents` 没有 `SetContext()` 方法，它只有 `ConnectTo`/`DeconnectFrom`/`Dispatch`/`Receive`）
- Instance 和 Reference 分开统计
- 物理属性计算耗时——考虑用户取消操作
- 使用进度条（`CATIProgress`）提升用户体验
