---
id: cap.persistence
title: Data Persistence / 数据持久化能力
category: capability
domain: infrastructure
keywords: [persistence, stream, storage, save, load, serialize, CATIPersistent, CATIStreamMsg]
apis: [CATIPersistent, CATIStreamMsg, CATIBBStreamer, CATStreamArea, CATUnicodeString]
frameworks: [ObjectModelerBase, System]
difficulty: advanced
release: [R19, R28]
tags: [capability]
---
# Data Persistence Capability

CAA 的持久化机制——将数据保存/加载到 CATIA 文档中，或在应用间传递消息数据。

## ⚠️ 重要修正

旧版本文档列出的 `CATIStream`、`CATStorage` 接口在 CAADoc 中**均无法找到**（不存在），系统地
将 `JS0GROUP`（这是 Imakefile 的 `LINK_WITH` 链接库名，不是 framework 名）错误地放进了
`frameworks` 字段。以下为核实后的真实情况。

## 核心接口（按用途区分，注意不要混用）

| 接口 | Framework | 用途 |
|------|-----------|------|
| `CATIPersistent` | ObjectModelerBase | **文档级**持久化：`Load`/`Save`/`SaveAs`/`Dirty`。官方文档建议优先使用 `CATDocumentServices` 服务，而不是直接调用该接口 |
| `CATIStreamMsg` | System | **Backbone 消息**（跨进程/跨应用通信）的流化接口，需实现 `StreamData`/`UnstreamData`/`SetMessageSpecifications`/`FreeStreamData`，与文档持久化无关 |
| `CATIBBStreamer` | System | 由系统提供的实现（不要重新实现），配合 `CATIStreamMsg` 对简单数据类型做流化/反流化，方法如 `StreamDouble`/`StreamByte`/`BeginStream`/`EndStream` 等 |
| `CATStreamArea` | ObjectModelerBase | 简单的字节缓冲区容器类，仅有 `Put(void*)`/`length()` |
| `CATUnicodeString` | System | 字符串序列化的基础类型，可作为流化内容之一 |

`CATIStream`、`CATStorage` 两个名称在 CAADoc 全文检索中**零匹配**，为虚构接口，已从本文档移除。

## 应用场景与对应方案

- **保存自定义 Feature/DataExtension 的额外数据**：CAA 官方文档中没有找到通用的
  "任意对象附加流数据" 接口。实践中的标准做法是通过 **Late Type + DataExtension 字典机制**
  实现（参见 `philo.late_types`），而不是依赖某个通用 Stream 接口。
- **保存命令状态/配置到文档**：应通过文档级的 `CATIPersistent`（或更推荐的
  `CATDocumentServices`）在文档保存时序列化，而不是逐个 Feature 手动流化。
- **跨应用/跨进程传递消息数据（Backbone Message）**：使用 `CATIStreamMsg` +
  `CATIBBStreamer`，这是官方样例（`CAASysBBMessage`、`CAADlgBBMessage`）中验证过的真实模式，
  但这属于**消息传递**场景，不是文档持久化场景，不要混淆二者。

## 关联

| 类型 | ID | 说明 |
|------|-----|------|
| Philosophy | `philo.late_types` | Late Type 序列化 / DataExtension 数据持久化的真实机制 |
| Knowledge | `mecmod.feature_patterns` | Feature 属性存储 |
