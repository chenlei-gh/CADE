---
id: cap.update_mechanism
title: Update Mechanism / CATIA 更新机制
category: capability
domain: infrastructure
keywords: [update, compute, build, dirty, CATIUpdate, model_events, dispatch]
apis: [CATIUpdate, CATIModelEvents, CATIMechanicalUpdate, Dispatch]
frameworks: [ObjectModelerBase, CATMecModInterfaces]
difficulty: intermediate
release: [R19, R28]
tags: [capability]
---
# Update Mechanism Capability

控制 CATIA 的增量更新和计算传播。

## 应用场景

- 修改 Feature 属性后触发几何更新
- 批量操作中暂停/恢复更新
- 自定义 Feature 的 Compute 实现

## 关联

| 类型 | ID | 说明 |
|------|-----|------|
| Philosophy | `philo.updates` | Update 设计哲学 |
| Knowledge | `mecmod.feature` | Feature 模型 |
| Playbook | `pb_assembly_stats` | 装配统计（需要控制 Update） |
