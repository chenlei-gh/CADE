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

## ⚠️ 跨层污染陷阱（已核实的捏造）

CATIA 有**两套 API 体系**，对象模型高度相似但接口名不同，AI 极易把 Automation 层的对象“翻译”成看似合规的 CAA 接口：

| | Automation / COM 层 | CAA C++ 层 |
|---|---|---|
| 前缀 | `CATIA*`（如 `CATIAOriginElements`） | `CATI*`（如 `CATIPrtPart`） |
| 方法风格 | COM 属性 `get_PlaneXY()` | 普通方法 `GetReferencePlanes()` |
| 位置 | `PublicGenerated/`（IDL 生成） | `PublicInterfaces/` |
| 调用方式 | VBA / COM 互操作 | C++ 直接调用 |

**已核实的捏造**（2026-07-27）：`CATIPrtOriginElements` 和 `GetPlaneXY/YZ/ZX()` 在 CAA C++ 层**不存在**——它们是把 Automation 层真实存在的 `CATIAOriginElements::get_PlaneXY()`（`MecModInterfaces/PublicGenerated/win_b64/CATIAOriginElements.h:31`）去掉 `A`、加上 `Get` 前缀“翻译”出来的。MethodIndex `has_type('CATIPrtOriginElements')` = False，`owners_of('GetPlaneXY')` = 空。

**正确路径**：`CATIPrtContainer::GetPart()` → `CATIPrtPart::GetReferencePlanes()`（返回列表，非单个命名 getter）。教训：`CATIA*` 前缀是 Automation 层信号，看到它就知道**不能直接当 CAA 接口用**；命名相似不代表跨层存在，落代码前必须过 MethodIndex / HeaderMap 验证。

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
