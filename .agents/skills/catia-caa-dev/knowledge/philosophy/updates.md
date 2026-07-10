---
id: philo.updates
title: CATIA Update Mechanism / Update 机制哲学
category: knowledge
domain: philosophy
keywords: [update, CATIUpdate, dirty, model_events, compute, propagation, top-down]
apis: [CATIUpdate, CATIModelEvents, CATIMechanicalUpdate, CATISpecObject]
frameworks: [ObjectModelerBase, CATMecModInterfaces]
release: [R19, R28]
tags: [philosophy, update, core]
---
# CATIA Update Mechanism

Update 是 CATIA 最核心也是最容易被误解的机制。它不是"刷新界面"——它是"重新计算整个特征树"。

## 核心原则

1. **Update 是 Top-Down（自上而下）** — 从根节点开始，重新计算所有子节点
2. **Update 是懒加载** — CATIA 不会主动 Update，需要显式调用
3. **Update 失败会阻断整个树** — 一个特征 Update 失败，其所有子特征都不会被 Update

## CATIUpdate vs CATIMechanicalUpdate

```cpp
// CATIUpdate — 通用 Update 接口
CATIUpdate_var spUpdate = spFeature;
spUpdate->Update();  // 基础 Update，不保证机械特征完全计算

// CATIMechanicalUpdate — 机械特征专用
CATIMechanicalUpdate_var spMechUpdate = spFeature;
spMechUpdate->Update();  // 确保几何体也更新
```

**关键区别**: `CATIMechanicalUpdate` 会触发底层几何重算（CATGeoFactory），而 `CATIUpdate` 只更新属性树。

## Update 触发时机

| 触发方式 | 何时使用 |
|---------|---------|
| `CATIModelEvents::Dispatch()` | 批量通知所有依赖者 |
| `CATIUpdate::Update()` | 单个特征 Update |
| `CATIMechanicalUpdate::Update()` | 需要几何体重算 |
| `CATIModelEvents::SetContext()` | 设置 Update 上下文（如暂停通知） |

## AI 生成规则（checklist）

- [ ] 修改属性后调用 `CATIModelEvents::Dispatch()` 或 `spFeature->Update()`
- [ ] 机械特征（Pad/Pocket/Fillet）使用 `CATIMechanicalUpdate::Update()`
- [ ] 批量操作时使用 `CATIModelEvents::SetContext()` 暂停通知，完成后再 `Dispatch()`
- [ ] Update 在消息循环中执行——批量操作后需要让 CATIA 处理消息队列
- [ ] Update 失败时检查父特征是否正确 Update
