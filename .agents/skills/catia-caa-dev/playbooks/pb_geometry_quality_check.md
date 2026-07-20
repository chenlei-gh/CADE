---
id: pb.geometry_quality_check
title: Geometry Quality Check / 几何质量检查
category: playbook
domain: part
keywords: [geometry, check, quality, topology, feature, body, edge, face, verify, validate, diameter, radius, thickness]
capabilities: [cap.geometry_query, cap.feature_recognition, cap.parameter_system]
apis: [CATBody, CATFace, CATEdge, CATVertex, CATISpecObject, CATIGeometricalElement, CATIEdgeFillet, CATINewHole, CATIChamfer]
frameworks: [CATMecModUseItf, ObjectModelerBase, KnowledgeInterfaces, PartInterfaces]
difficulty: advanced
effort: medium
release: [R19, R28]
tags: [playbook, geometry, quality, check, analysis]
---

# Geometry Quality Check (几何质量检查)

对零件中的所有几何特征进行系统性质量检查：圆角半径、孔径、倒角角度、壁厚等。

## ⚠️ 重要修正

本文档早期版本存在多处虚构或错误的 API，已按官方本地 CAADoc 核实并修正（与 `pb.batch_feature_check` 的既有修复结论一致）：

| 旧写法（虚构/错误） | 真实情况 |
|---------------|---------|
| `CATIPrtPart::GetMainBody()` | 不存在。`CATIPrtPart` 没有 `GetMainBody()`，真实的主几何体访问方法是 `GetSolid()`（返回 `CATBody_var`）；但遍历 Feature 树本身不需要它，直接从根 `CATISpecObject`（如 Part 文档的 `GetSpecContainer()` 中挑出根特征）开始递归即可 |
| `CATISpecObject::ListChildren()` | 不存在。真实方法是 `ListComponents()`（返回堆分配的 `CATListValCATISpecObject_var*`，调用方负责 `delete`） |
| `IsATypeOf("CATIFillet")` / `IsATypeOf("CATIHole")` | `CATISpecObject` 没有 `IsATypeOf(char*)`；真实方法是 `IsSubTypeOf(CATUnicodeString&)`，且类型名不带 `CATI` 前缀，是不带前缀的 StartUp 名：`"EdgeFillet"`、`"Hole"`、`"Chamfer"` |
| `CATIFillet_var spFillet = iFeature; spFillet->GetRadius()` | `CATIFillet` 是空标记接口（14 个方法全部关于 Parting Element/Workshop/Orientation，**没有** `GetRadius()`）。真实带半径方法的接口是继承自它的 `CATIEdgeFillet`：`GetRadius()`、`ModifyRadius(double)` |
| `CATIHole_var spHole = iFeature; spHole->GetDiameter(dia)` | `CATIHole` 在 `.dic` 里能查到实现声明，但**没有对应的 SDK 头文件/refman 文档**，不要使用。真实、有完整文档的接口是 `CATINewHole`：`GetDiameter(double&)`、`GetHoleType(int&)`、`IsThreaded(int&)` 等 |
| 倒角检查「角度」 | `CATIChamfer` 没有 `GetAngle()`。真实方法是 `GetLength1()`/`GetLength2()`（`double`，直接返回值）+ `GetMode()`（`CATPrtChamferMode`，区分是两长度模式还是长度+角度模式）+ `GetAngleParm()`（角度以 `CATICkeParm_var` 装箱返回，需要 `AsReal()` 才能取出数值，见 `capabilities/parameter-system.md`） |

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

1. **从根 Feature 开始递归遍历 Feature 树**：`CATISpecObject::ListComponents()`（返回堆分配列表，需 `delete`）
2. **类型识别**：`IsSubTypeOf("EdgeFillet")` / `IsSubTypeOf("Hole")` / `IsSubTypeOf("Chamfer")`（StartUp 名不带 `CATI` 前缀）
3. **参数检查**：
   - Fillet → `CATIEdgeFillet::GetRadius()` 检查半径是否 >= 最小半径
   - Hole → `CATINewHole::GetDiameter(double&)` 检查直径公差、深度
   - Chamfer → `CATIChamfer::GetLength1()`/`GetLength2()` 检查长度，`GetMode()` 区分模式
   - Pad/Pocket → 检查壁厚（需具体 Feature 接口，无通用便捷方法）
4. **生成报告**：按严重程度分类（PASS/WARN/FAIL）
5. **可视化标记**：高亮不合格 Feature

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
void CheckFeature(CATISpecObject_var iFeature,
                   std::vector<GeometryCheckItem> &oResults) {
    // 先用 IsSubTypeOf 确定类型（StartUp 名不带 CATI 前缀），再 QueryInterface 到具体接口
    if (iFeature->IsSubTypeOf("EdgeFillet")) {
        CATIEdgeFillet_var spFillet = iFeature;
        if (NULL_var != spFillet) {
            double radius = spFillet->GetRadius();   // 直接返回 double，不是传出参数
            CheckRange(oResults, iFeature, "Radius", radius, 1.0, 100.0);
        }
    } else if (iFeature->IsSubTypeOf("Hole")) {
        CATINewHole_var spHole = iFeature;
        if (NULL_var != spHole) {
            double dia = 0.0;
            spHole->GetDiameter(dia);                // 传出参数（与 Fillet 不同）
            CheckRange(oResults, iFeature, "Diameter", dia, 0.5, 500.0);
        }
    } else if (iFeature->IsSubTypeOf("Chamfer")) {
        CATIChamfer_var spChamfer = iFeature;
        if (NULL_var != spChamfer) {
            double len1 = spChamfer->GetLength1();   // 直接返回 double
            CheckRange(oResults, iFeature, "Length1", len1, 0.5, 20.0);
        }
    }
}
```

## 注意事项

- `IsSubTypeOf(CATUnicodeString&)` 是 CATIA 标准类型查询方式，比 `dynamic_cast` 更安全；没有 `IsATypeOf(char*)` 这个重载
- Late Type 派生链：具体实例（如 `EdgeFillet` 组件）实现 `CATISpecObject` + `CATIEdgeFillet`（不是 `CATIFillet`），`iFeature` 直接 QueryInterface 到 `CATIEdgeFillet_var` 即可，不需要经过 `CATIFillet`
- **API 签名不对称**：`CATIEdgeFillet::GetRadius()` 无参数直接返回 `double`，而 `CATINewHole::GetDiameter(double&)` 是传出参数形式，两者调用方式不同，写代码时不要凭命名相似度猜测签名，先 `--query` 确认
- 大零件（1000+ Feature）遍历建议缓存类型判断结果
- 建议配合 `pb.batch_feature_check` 复用 Feature 遍历逻辑

## 相关 Playbook

- `pb.batch_feature_check` — 批量特征检查的基础遍历框架
