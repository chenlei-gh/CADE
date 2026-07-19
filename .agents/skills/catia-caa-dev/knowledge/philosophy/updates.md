---
id: philo.updates
title: CATIA Update Mechanism / Update 机制哲学
category: knowledge
domain: philosophy
keywords: [update, CATISpecObject, dirty, model_events, compute, propagation, top-down, CATIOsmUpdate]
apis: [CATISpecObject, CATIOsmUpdate, CATIModelEvents, CATIUpdateProvider]
frameworks: [ObjectSpecsLegacy, Visualization]
release: [R19, R28]
tags: [philosophy, update, core]
---
# CATIA Update Mechanism

Update 是 CATIA 最核心也是最容易被误解的机制。它不是"刷新界面"——它是"重新计算整个特征树"。

## ⚠️ 重要修正

早期版本文档中的 `CATIUpdate` 和 `CATIMechanicalUpdate` 接口经核实**均不存在**（CAADoc 中无任何匹配）。真正的 Update 入口和覆写机制如下：

| 错误写法 | 问题 | 正确写法 |
|------|------|------|
| `CATIUpdate_var spUpdate = spFeature; spUpdate->Update();` | 接口不存在 | `CATISpecObject::Update(CATIDomain_var iDomain=NULL_var)`，直接返回 `int`，无需转接口 |
| `CATIMechanicalUpdate_var spMechUpdate = spFeature; spMechUpdate->Update();` | 接口不存在 | 机械特征没有单独的"确保几何体更新"接口；默认 Update 机制本身就会重算几何体，除非通过 `CATIOsmUpdate` 被显式覆写 |
| 覆写默认 Update 行为 | 未提及正确机制 | 在 Feature 的 StartUp 上实现 `CATIOsmUpdate`（内部接口，仅供实现，不供外部调用），提供 `Update()`/`IsUpToDate()`/`SetUpToDate()`/`IsInactive()` |

## 核心原则

1. **Update 是 Top-Down（自上而下）** — 从根节点开始，重新计算所有子节点
2. **Update 是懒加载** — CATIA 不会主动 Update，需要显式调用
3. **Update 失败会阻断整个树** — 一个特征 Update 失败，其所有子特征都不会被 Update

## CATISpecObject::Update

```cpp
// CATISpecObject 本身就带 Update 方法，无需转接口
CATISpecObject_var spFeature = ...;
int rc = spFeature->Update();  // 默认参数 iDomain = NULL_var
```

**覆写默认行为**：如果 Feature 的 StartUp 实现了 `CATIOsmUpdate`（内部机制，仅供 Late Type 实现方覆写），
`CATISpecObject::Update()` 会转发调用到 `CATIOsmUpdate::Update()`。应用程序代码永远只调用
`CATISpecObject::Update()`，不应直接使用 `CATIOsmUpdate`。

## Update 触发时机

| 触发方式 | 何时使用 |
|---------|---------|
| `CATIModelEvents::Dispatch(CATNotification&)` | 通知可视化世界某个对象发生了变化 |
| `CATISpecObject::Update(iDomain=NULL_var)` | 单个特征 Update，返回 `int` |
| `CATISpecObject::IsUpToDate(iDomain=NULL_var)` | 查询是否需要重算 |
| `CATISpecObject::SetUpToDate(CATBoolean)` | 手动标记状态（一般由 Update 机制自动管理） |

## AI 生成规则（checklist）

- [ ] 修改属性后调用 `spFeature->Update()`（`CATISpecObject` 上的方法，不是独立接口）
- [ ] 需要覆写默认 Update 行为时，在 StartUp 上实现 `CATIOsmUpdate`，不要虚构 `CATIMechanicalUpdate`
- [ ] 需要通知可视化层时使用 `CATIModelEvents::Dispatch()`
- [ ] Update 在消息循环中执行——批量操作后需要让 CATIA 处理消息队列
- [ ] Update 失败时检查父特征是否正确 Update
