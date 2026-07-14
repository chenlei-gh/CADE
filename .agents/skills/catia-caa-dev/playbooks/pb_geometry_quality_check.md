---
id: pb.geometry_quality_check
title: Geometry Quality Check / 几何质量检查
category: playbook
domain: part
keywords: [geometry, check, quality, topology, feature, body, edge, face, verify, validate, diameter, radius, thickness]
capabilities: [cap.geometry_query, cap.feature_recognition, cap.parameter_system]
apis: [CATBody, CATFace, CATEdge, CATVertex, CATISpecObject, CATIGeometricalElement]
frameworks: [CATMecModUseItf, ObjectModelerBase, KnowledgeInterfaces]
difficulty: advanced
effort: medium
release: [R19, R28]
tags: [playbook, geometry, quality, check, analysis]
---

# Geometry Quality Check (几何质量检查)

对零件中的所有几何特征进行系统性质量检查：圆角半径、孔径、倒角角度、壁厚等。

## 目标

遍历零件中的每个 Feature，按类型分组检查关键参数是否符合规范（如最小圆角半径、最大孔径偏差）。

## 前置条件

- 已加载 CATPart 文档
- 可选：企业规范文件（规则表/JSON）
- 可选：报告输出路径

## 涉及能力

| Capability | 用途 |
|-----------|------|
| `cap.geometry_query` | 获取 Feature 的拓扑元素（Body/Face/Edge） |
| `cap.feature_recognition` | 识别 Feature 类型（Fillet/Hole/Chamfer/Pad） |
| `cap.parameter_system` | 读取 Feature 的参数值 |

## 实现步骤

1. **获取 Part 根 Feature**：`CATIPrtPart::GetMainBody()`
2. **递归遍历 Feature 树**：`CATISpecObject::ListChildren()`
3. **类型识别**：`IsATypeOf("CATIFillet")` / `IsATypeOf("CATIHole")` 等
4. **参数检查**：
   - Fillet → 检查半径是否 >= 最小半径
   - Hole → 检查直径公差、深度
   - Chamfer → 检查角度、长度
   - Pad/Pocket → 检查壁厚
5. **生成报告**：按严重程度分类（PASS/WARN/FAIL）
6. **可视化标记**：高亮不合格 Feature

## 检查表结构

```cpp
struct GeometryCheckItem {
    CATUnicodeString featureName;
    CATUnicodeString featureType;   // Fillet, Hole, Chamfer...
    CATUnicodeString parameterName; // Radius, Diameter...
    double actualValue;
    double minValue;
    double maxValue;
    CATUnicodeString status;        // PASS, WARN, FAIL
};
```

## 关键代码

```cpp
HRESULT CheckFeature(CATISpecObject *iFeature, 
                     CATListValGeometryCheckItem &results) {
    // 识别类型
    CATIFillet_var spFillet = iFeature;
    if (NULL_var != spFillet) {
        double radius = 0;
        spFillet->GetRadius(radius);
        CheckRange(results, iFeature, "Radius", radius, 1.0, 100.0);
    }

    CATIHole_var spHole = iFeature;
    if (NULL_var != spHole) {
        double dia = 0;
        spHole->GetDiameter(dia);
        CheckRange(results, iFeature, "Diameter", dia, 0.5, 500.0);
    }
    return S_OK;
}
```

## 注意事项

- `IsATypeOf` 是 CATIA 标准接口查询方式，比 `dynamic_cast` 更安全
- Late Type 派生链：`CATISpecObject` → `CATIFillet`，确保 QueryInterface 正确
- 大零件（1000+ Feature）遍历建议缓存类型判断结果
- 建议配合 `pb.batch_feature_check` 复用 Feature 遍历逻辑

## 相关 Playbook

- `pb.batch_feature_check` — 批量特征检查的基础遍历框架
