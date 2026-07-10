---
id: cap.persistence
title: Data Persistence / 数据持久化能力
category: capability
domain: infrastructure
keywords: [persistence, stream, storage, save, load, serialize, CATIStream, CATStorage]
apis: [CATIStream, CATStorage, CATUnicodeString, CATIStreamMsg]
frameworks: [System, JS0GROUP]
difficulty: advanced
release: [R19, R28]
tags: [capability]
---
# Data Persistence Capability

CAA 的持久化机制——将自定义数据保存到 CATIA 文档中。

## 核心接口

| 接口 | 用途 |
|------|------|
| `CATIStream` | 二进制流读写 |
| `CATStorage` | 存储容器（类似文件系统） |
| `CATIStreamMsg` | 消息格式流（键值对） |
| `CATUnicodeString` | 字符串序列化 |

## 应用场景

- 保存自定义 Feature 的额外数据
- 保存命令状态/配置到文档
- DataExtension 的数据持久化

## 关联

| 类型 | ID | 说明 |
|------|-----|------|
| Philosophy | `philo.late_types` | Late Type 序列化 |
| Knowledge | `mecmod.feature_patterns` | Feature 属性存储 |
