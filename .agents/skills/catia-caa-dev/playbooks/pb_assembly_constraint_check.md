---
id: pb.assembly_constraint_check
title: Assembly Constraint Check / 装配约束检查
category: playbook
domain: product
keywords: [constraint, assembly, check, verify, contact, offset, angle, fix, degree of freedom, DOF]
capabilities: [cap.assembly_tree, cap.geometry_query, cap.parameter_system]
apis: [CATIProduct, CATIPrtContainer, CATIConstraint, CATIMechanicalConstraint, CATMathTransformation]
frameworks: [CATAssemblyInterfaces, CATMecModUseItf, KnowledgeInterfaces]
difficulty: intermediate
effort: medium
release: [R19, R28]
tags: [playbook, constraint, assembly, check, verification]
---

# Assembly Constraint Check (装配约束检查)

系统性检查装配约束完整性：未约束零件、过约束、冲突约束、自由度分析。

## 目标

扫描整个装配体 → 分析所有约束关系 → 生成约束报告（未约束/过约束/冲突）。

## 前置条件

- 已加载 CATProduct 装配文档
- 装配已添加约束（Coincidence/Contact/Offset/Angle/Fix）
- 可选：约束规则集（企业标准）

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.assembly_tree` | 遍历装配树获取所有零件和子装配 |
| `cap.geometry_query` | 分析约束涉及的几何元素 |
| `cap.parameter_system` | 读取约束参数（偏移值/角度值） |

## 实现步骤

1. **遍历装配**：获取所有 Instance 和约束
2. **分类约束**：Fix/Contact/Coincidence/Offset/Angle
3. **自由度检查**：
   - 无约束零件 → WARN（6 DOF）
   - 仅 Fix 约束 → OK（0 DOF）
   - 部分约束 → INFO（显示剩余 DOF）
4. **冲突检测**：同一自由度被多个约束限制 → FAIL
5. **生成报告**：按严重程度排序，标注问题零件

## 约束分析结构

```cpp
struct ConstraintReport {
    CATUnicodeString instanceName;
    int totalConstraints;
    int fixCount, contactCount, offsetCount, angleCount;
    int remainingDOF;           // 0=完全约束, 6=无约束
    CATUnicodeString status;    // OK, WARN, FAIL
    CATListValCATUnicodeString conflicts;
};
```

## 关键代码

```cpp
HRESULT CheckConstraints(CATISpecObject *iRoot,
                          CATListValConstraintReport &reports) {
    CATIPrtContainer_var spContainer = iRoot;
    
    // Get all constraints from the assembly connector
    CATIProduct_var spProduct = iRoot;
    CATListValCATISpecObject constraints;
    spProduct->ListConstraints(constraints);

    // Get all child instances
    CATListValCATISpecObject children;
    spContainer->ListChildren(children);

    for (int i = 1; i <= children.Size(); i++) {
        ConstraintReport report;
        report.instanceName = GetInstanceName(children[i]);
        
        // Count constraints per instance
        for (int j = 1; j <= constraints.Size(); j++) {
            CATIProduct_var spChild1, spChild2;
            GetConstrainedParts(constraints[j], spChild1, spChild2);
            if (spChild1 == children[i] || spChild2 == children[i]) {
                ClassifyConstraint(constraints[j], report);
            }
        }
        
        report.remainingDOF = 6 - (report.fixCount * 6 + /* ... */);
        report.status = report.remainingDOF == 0 ? "OK" :
                        report.remainingDOF == 6 ? "WARN" : "INFO";
        reports.Append(report);
    }
    return S_OK;
}
```

## 注意事项

- 子装配内的约束不直接出现在顶层装配的约束列表中
- Fix 约束锁定所有 6 个自由度，Contact/Coincidence 各锁定不同组合
- 过约束检测需要几何计算（约束方程求解），复杂模型可能耗时
- 建议结合可视化标记（高亮问题零件）

## 相关 Playbook

- `pb.assembly_stats` — 可先统计装配规模决定是否分批检查
