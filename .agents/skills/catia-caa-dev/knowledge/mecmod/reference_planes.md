---
id: mecmod.reference_planes
title: Default Reference Planes (默认三基准面获取)
category: knowledge
domain: mecmod
keywords: [reference plane, datum plane, 基准面, 基准平面, xy plane, yz plane, zx plane, origin, CATIPrtPart, GetReferencePlanes]
apis: [CATIPrtPart, CATIPrtContainer, CATISpecObject]
requires: [mecmod.container_lookup]
patterns: []
examples: []
release: [R19, R28]
tags: [core, part, plane, origin]
---

# Default Reference Planes (默认三基准面获取)

## ⚠️ 检索陷阱

用 "plane" 做关键词检索，结果几乎全是 **GSD 平面创建接口**（`CATIGSMUsePlane*`、`CATGSMWFPlane*`、CATGSMUseItf 框架）。这些是**用户创建的平面特征**（GSD 工作台里的 offset/angle/normal 平面），和零件默认的三个基准面（xy / yz / zx）是两套完全不同的东西：

| | 默认基准面 | GSD 平面 |
|---|---|---|
| 来源 | 零件创建时自带（origin） | 用户/程序创建的特征 |
| 获取方式 | `CATIPrtPart::GetReferencePlanes()` | 遍历几何集 / 按名查找 |
| 创建接口 | 无（不可再创建） | `CATIGSMUseFactory::CreatePlane*()` |
| 所属框架 | MecModInterfaces | CATGSMUseItf / GSMInterfaces |

## ⚠️ 命名推导陷阱（已核实的捏造）

按 CAA 命名规律（`CATI + Domain + Object`）从 UI 树反推接口，容易“合理”地捏造出**根本不存在**的接口。以下两个已用 MethodIndex 核实为**捏造**（2026-07-27），不要生成：

| 捏造 | 为什么听起来合理 | 实况 |
|---|---|---|
| `CATIPrtOriginElements` | 对应 UI 的 Origin / 原点元素节点 | MethodIndex `has_type` = False，B28 无此接口 |
| `GetPlaneXY/YZ/ZX()` | 符合 `Get + 对象名` 命名习惯 | `owners_of` 为空，无任何接口拥有此方法 |

**正确路径**：`CATIPrtContainer::GetPart()` → `CATIPrtPart::GetReferencePlanes()`（返回列表，非单个命名 getter）。教训：命名规律只能当**假设**，落代码前必须过 MethodIndex / HeaderMap 验证。

## 正确 API（B28 头文件核实，2026-07-27）

```cpp
// MecModInterfaces/PublicInterfaces/CATIPrtPart.h:101
virtual CATListValCATISpecObject_var GetReferencePlanes() = 0;
```

返回三个基准面的 spec 对象列表（顺序通常为 xy、yz、zx——如需精确区分，遍历后用 `CATIAlias::GetAlias()` 比对名字，或取结果几何判断法向）。

## 调用链

```cpp
// CATDocument → CATIPrtContainer → CATIPrtPart → 基准面
CATIPrtContainer_var spPrtCont = /* 从文档获取 PrtContainer，见 mecmod.container_lookup */;
CATIPrtPart_var spPart = spPrtCont->GetPart();
if (spPart != NULL_var) {
    CATListValCATISpecObject_var planes = spPart->GetReferencePlanes();
    for (int i = 1; i <= planes.Size(); i++) {
        CATISpecObject_var plane = planes[i];
        // plane 即基准面特征，可作为草图参考、镜像平面等使用
    }
}
```

## 规则

- 需要"默认基准面"（草图定位、镜像参考、装配约束参考）→ 走 `CATIPrtPart::GetReferencePlanes()`，**不要**实例化任何 GSM 平面接口
- 需要"新建一个平面特征"（偏移面、角度面等）→ 才走 `CATIGSMUseFactory`（CATGSMUseItf）
- 基准面没有专属接口类型——它们是 type 为 "Plane" 的普通 spec 特征；操作其结果几何时用 `CATIGeometricalElement` 体系
