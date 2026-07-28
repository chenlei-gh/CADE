---
id: fp.startup_interface_qi
title: Operation Interface on StartUp not Feature / 操作类接口在 StartUp 上 QI 而非特征本体
category: knowledge
domain: failure_patterns
severity: error
apis: [CATISpecObject, CATIIsolate, CATIOsmUpdate]
frameworks: [MecModInterfaces, ObjectSpecsLegacy]
keywords: [GetStartUp, StartUp, QI, QueryInterface, CATIIsolate, CATIOsmUpdate, Isolate, Update, 隔离, 规格定义层, feature]
tags: [failure_pattern, mecmod, object_modeler, startup, query_interface]
release: [R28]
automation: manual
not_automatable_because: "能否在 StartUp 上 QI 某个接口取决于该 StartUp 的 Late Type 实现了哪些接口——这是运行时的对象模型语义，静态检查无法从调用点判断 receiver 应该是 feature 本体还是其 StartUp。部分可规则化方向：verifier 检测到『对 feature 本体 QI 一个 MethodIndex 显示不属于本体的接口』时提示改从 GetStartUp() QI，但需先建立『接口实现层级（本体/StartUp）』数据，目前 MethodIndex 只记录接口方法归属，不记录接口挂在哪一层对象上。见『预防规则』。"
---

# Operation Interface on StartUp not Feature / 操作类接口在 StartUp 上 QI 而非特征本体

## 症状

对一个 feature 对象直接 QI（QueryInterface）操作类接口——如 `CATIIsolate`、`CATIOsmUpdate`——拿到的接口指针调用后**行为异常或操作不生效**（典型：对 feature 本体 QI `CATIIsolate` 后调用 `Isolate()` 返回失败或无效果）。改从 `GetStartUp()` 返回的 StartUp 对象上 QI 同一接口，操作正常。

## 原因

CAA 的对象模型把 feature 分成两层：

- **Feature 本体**：几何/树中的实例，暴露 `CATISpecObject`、可视化、选择等"实例层"接口
- **StartUp（规格定义层）**：`CATISpecObject::GetStartUp()` 返回的原型对象，承载该 feature 类型的**规格与操作定义**

很多**操作类/规格类接口**（`CATIIsolate`、`CATIOsmUpdate` 等）是**实现在 StartUp 上，而不是 feature 本体上**。在 feature 本体上 QI 这些接口，要么 QI 失败，要么拿到一个不连接到真实规格实现的空壳，调用后不产生预期效果。

实测（B28 MethodIndex / CAADoc refman，权威数据）：

| 接口::方法 | 存在性 | 所在框架 |
|---|---|---|
| `CATISpecObject::GetStartUp` | ✅ 真实（GetStartUp 唯一 owner = CATISpecObject） | ObjectSpecsLegacy |
| `CATIIsolate::Isolate(CATLISTV(CATBaseUnknown_var)* = 0)` | ✅ 真实（CATIIsolate 唯一方法，**无 `GetIsolateStatus`**） | MecModInterfaces |
| `CATIOsmUpdate::Update` / `IsUpToDate` | ✅ 真实 | ObjectSpecsLegacy |

## 修复

调用操作类接口前，先取 StartUp 再 QI：

```cpp
CATISpecObject_var spFeat = ...;          // feature 本体

// 1. 取规格定义层
CATISpecObject_var spStartUp;
spFeat->GetStartUp(spStartUp);

// 2. 操作类接口从 StartUp 上 QI（不是从 spFeat）
CATIIsolate_var spIsolate = spStartUp;    // QI CATIIsolate
if (NULL_var != spIsolate) {
    CATLISTV(CATBaseUnknown_var) generated;
    HRESULT rc = spIsolate->Isolate(&generated);
}
```

> 注：`CATIOsmUpdate` 在 `knowledge/philosophy/updates.md` 中记录的是 **Late Type 实现方**在 StartUp 上**实现**该接口以覆写默认 Update 行为；本条 FP 是**调用方**视角——调用 StartUp 承载的操作接口时，QI 目标同样是 StartUp 而非本体。两者是同一对象模型事实的两面。

## 预防规则

- [ ] 对一个 feature 调用"操作/规格"语义的方法前，先问：这个接口实现在本体还是 StartUp？操作类（Isolate/Update 类）默认假设在 **StartUp**
- [ ] 在 feature 本体上 QI 某接口失败或调用无效时，第一排查动作：改为 `GetStartUp()` 后在该 StartUp 上 QI 同一接口重试
- [ ] 用 MethodIndex `owners_of(method)` / `method_exists(iface, method)` 核实接口与方法真实存在及归属，**禁止凭命名规律推断方法名**（实测 `CATIIsolate` 无 `GetIsolateStatus`）
- [ ] 接口"存在"不等于"QI 目标正确"——目标层级（本体 vs StartUp）错误时编译通过、运行无效，只有实机调用能暴露

## 边界与局限

- "操作类接口在 StartUp"是**常见模式而非铁律**：并非所有接口都在 StartUp 上（实例层接口如可视化/选择仍在本体）。本条只覆盖 Isolate/Update 这类**规格操作**接口的 QI 目标选择
- 静态判定"某接口挂在哪一层"目前无现成数据（MethodIndex 只记录接口→方法归属，不记录接口→对象层级），故本条暂为 manual；建立该层级数据后可升级为 verifier 规则
- 实测上下文为 MecMod feature（R28）。其他 Object Modeler feature 的 StartUp 接口分布以各自 CAADoc 为准
