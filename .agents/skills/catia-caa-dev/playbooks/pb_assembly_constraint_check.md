---
id: pb.assembly_constraint_check
title: Assembly Constraint Check / 装配约束检查
category: playbook
domain: product
keywords: [constraint, assembly, check, verify, contact, offset, angle, fix, status]
capabilities: [cap.assembly_tree, cap.geometry_query, cap.parameter_system]
apis: [CATIProduct, CATAsmConstraintServices, CATICst, CATMathTransformation]
frameworks: [CATAssemblyInterfaces, ConstraintModelerInterfaces, MecModInterfaces]
difficulty: intermediate
effort: medium
release: [R19, R28]
tags: [playbook, constraint, assembly, check, verification]
---

# Assembly Constraint Check (装配约束检查)

系统性检查装配约束健康状况：按类型统计约束、找出失效/未满足的约束。

## ⚠️ 已核实修正（重要）

本文档早期版本假设存在 `CATIProduct::ListConstraints()`（实例方法）和
`CATIPrtContainer::ListChildren()`，并试图基于"6-DOF自由度计数"给出精确的
过约束/欠约束判定。经对照本地 CAADoc（`ConstraintModelerInterfaces`、
`CATAssemblyInterfaces`、`MecModInterfaces` 框架 + `.cpp` 官方样例
`CAAAuiRefreshCsts.cpp`/`CAAAuiCreateFixConstraintInPart.cpp`）核实：

- `CATIConstraint`、`CATIMechanicalConstraint`：**CAADoc 全局零匹配，均为虚构接口**。
  真实约束接口只有单数的 `CATICst`（数据接口，`ConstraintModelerInterfaces`）。
- `ListConstraints` **不是 `CATIProduct` 的实例方法**，而是两个不同工具类的
  **静态方法**：
  - `CATAsmConstraintServices::ListConstraints(CATIProduct*, CATLISTV(CATICst_var)&)`
    （`CATAssemblyInterfaces` 框架，按装配层级递归取约束）
  - `CATConstraintServices::ListConstraints(CATBaseUnknown_var&, CATLISTV(CATICst_var)&)`
    （`ConstraintModeler` 框架，官方样例 `CAAAuiCreateFixConstraintInPart.cpp` 中对单个
    Part 调用；注意样例里用的类名是 `CATConstraintServices`，不要与
    `CATAsmConstraintServices` 混淆，二者是不同的类，分别位于不同框架）
- `CATIPrtContainer::ListChildren()` 不存在。`CATIPrtContainer` 只有
  `GetGeometricContainer()`/`GetPart()` 两个方法，跟遍历装配子节点无关。
  遍历装配子节点应使用 `CATIProduct::GetChildren()`/`GetAllChildren()`。
- **"剩余自由度(DOF)精确计数"这个设计假设本身没有官方 API 支撑**。真实的
  `CATICst::ReadStatus()` 返回的是 `CATCstStatus` 枚举（约束当前是否生效/为何失效），
  不是一个可以线性累加成"0~6"自由度数值的量；`Fix` 约束(`CstType_Reference`)锁定
  全部自由度，但 `Contact`/`Coincidence`/`Offset`/`Angle` 等约束锁定的自由度数量
  取决于具体几何元素组合（点/线/面/轴），CAADoc 未提供直接返回"锁定了几个 DOF"的
  API。因此本文档把"6-DOF 计数"降级为"按约束状态做健康检查"（见下文），
  这是官方 API 能够直接支撑的方案。

## 目标

按装配层级枚举所有约束 → 按类型统计（Fix/Distance/On/Concentric/Angle/…）→
找出状态非正常（`ReadStatus()` != `CstStatus_True`）的约束 → 生成报告，
标注哪些实例缺少任何约束引用（潜在欠约束零件）。

## 前置条件

- 已加载 CATProduct 装配文档
- 装配已添加约束（Fix/Distance/On/Concentric/Tangent/Angle/…）

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.assembly_tree` | 遍历装配树获取所有零件和子装配 |
| `cap.geometry_query` | 分析约束涉及的几何元素 |
| `cap.parameter_system` | 读取约束参数（偏移值/角度值） |

## 实现步骤

1. **取约束列表**：对装配根节点调用
   `CATAsmConstraintServices::ListConstraints(pRootProduct, CstList)`
   （递归返回该装配层级下所有约束）
2. **分类统计**：对每个 `CATICst_var`，调用 `GetCstType()` 按
   `CATCstType` 枚举值（`CstType_Reference`=Fix、`CstType_Distance`、
   `CstType_On`=Coincidence、`CstType_Concentric`、`CstType_Angle` 等）分类计数
3. **状态检查**：调用 `ReadStatus()`，非 `CstStatus_True` 的约束记为问题项
   （`CstStatus_False_*` 系列区分了失效原因：属性冲突/数值冲突/用户强制/断裂/可视化模式等）
4. **孤立零件检测**：遍历 `CATIProduct::GetChildren()` 得到的所有实例，
   与约束涉及的元素（`GetElement(1..3)` 或 `GetElements()`）比对，找出从未
   被任何约束引用的实例 → 标记为"无约束"警告
5. **生成报告**：按严重程度排序（FAIL: 状态异常 > WARN: 无约束引用 > INFO: 正常）

## 约束分析结构

```cpp
struct ConstraintReport {
    CATUnicodeString cstName;
    CATCstType cstType;
    CATCstStatus status;        // CstStatus_True / CstStatus_False_* / CstStatus_ERROR
    CATUnicodeString statusText;
    CATListValCATUnicodeString involvedInstances;
};

struct ConstraintSummary {
    int totalConstraints;
    int byType[/* indexed by CATCstType */];
    int failedCount;             // ReadStatus() != CstStatus_True
    CATListValCATUnicodeString unconstrainedInstances;
};
```

## 关键代码

```cpp
#include "CATAsmConstraintServices.h"   // CATAssemblyInterfaces
#include "CATICst.h"                    // ConstraintModelerInterfaces
#include "CATIProduct.h"                // ProductStructure

HRESULT CheckConstraints(CATIProduct *iRootProduct,
                          CATListValConstraintReport &oReports,
                          CATListValCATUnicodeString &oUnconstrained) {
    // 1. Get all constraints under this product (recursive)
    CATLISTV(CATICst_var) cstList;
    HRESULT rc = CATAsmConstraintServices::ListConstraints(iRootProduct, cstList);
    if (FAILED(rc)) return rc;

    // Track which instances are referenced by at least one constraint
    CATListValCATBaseUnknown_var referencedElements;

    for (int i = 1; i <= cstList.Size(); i++) {
        CATICst_var spCst = cstList[i];
        if (NULL_var == spCst) continue;

        ConstraintReport report;
        report.cstType  = spCst->GetCstType();
        report.status   = spCst->ReadStatus();
        report.statusText = StatusToText(report.status);   // helper: switch/case on CATCstStatus

        CATBaseUnknown_var e1, e2, e3;
        spCst->GetElements(e1, e2, e3);
        if (NULL_var != e1) referencedElements.Append(e1);
        if (NULL_var != e2) referencedElements.Append(e2);
        if (NULL_var != e3) referencedElements.Append(e3);

        oReports.Append(report);
    }

    // 2. Find instances never referenced by any constraint
    CATListValCATBaseUnknown_var *pChildren = iRootProduct->GetChildren();
    if (NULL != pChildren) {
        for (int j = 1; j <= pChildren->Size(); j++) {
            CATBaseUnknown_var spChild = (*pChildren)[j];
            if (!referencedElements.Locate(spChild)) {
                CATIProduct_var spChildPrd = spChild;
                if (NULL_var != spChildPrd) {
                    CATUnicodeString name;
                    spChildPrd->GetPrdInstanceName(name);
                    oUnconstrained.Append(name);
                }
            }
        }
        delete pChildren;
    }

    return S_OK;
}
```

## 注意事项

- `CATAsmConstraintServices::ListConstraints` 是递归的，会带出子装配内的约束；
  如果只想要当前层级，需要自行按 `GetElements()` 返回的元素所属产品过滤。
- `ReadStatus()` 反映的是"约束当前是否成功生效"，不是"该零件还剩几个自由度"；
  不要把这两个概念混为一谈。
- "无约束引用"只能说明该实例从未出现在任何约束的 `GetElements()` 里，
  不代表它在几何上真的是自由的（例如它可能通过其父级的固定关系间接被约束）。
- 过约束/欠约束的精确几何分析（真正的 DOF 求解）不是 CAADoc 公开 API 覆盖的范围，
  如需要，应通过 CATIA UI 里的 "Update Diagnosis"/约束求解器诊断信息辅助人工判断，
  不建议在 CAA 代码里自行重新实现约束求解。

## 相关 Playbook

- `pb.assembly_stats` — 可先统计装配规模决定是否分批检查
