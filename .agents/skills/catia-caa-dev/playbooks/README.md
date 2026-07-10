# Playbooks (解决方案)

围绕业务目标组织的可执行方案。每个 playbook 回答：**"怎么完成这件事？"**

## 格式规范

```yaml
---
id: pb.[slug]
title: [中文标题 / English Title]
category: playbook
domain: [domain]
keywords: [5-10 keywords]
capabilities: [涉及的 capability IDs]
apis: [涉及的 API 列表]
frameworks: [涉及的 Framework]
difficulty: beginner | intermediate | advanced
effort: small | medium | large
release: [R19, R28]
tags: [playbook]
---

# [标题]

## 目标
一句话描述业务目标

## 前置条件
- 需要的环境/数据/权限

## 涉及能力
| Capability | 用途 |
|-----------|------|

## 实现步骤
1. Step 1: 描述 + 关键 API
2. Step 2: ...

## 完整代码
关键代码片段

## 注意事项
常见陷阱和优化建议

## 相关 Playbook
```

## 检索优先级

```
用户需求 → playbook (有没有成熟方案?)
         → capability (涉及哪些能力?)
         → knowledge (具体 API 代码)
         → CAADoc (查缺补漏)
```

---

**当前数量**: 待补充
**最后更新**: 2026-07-10
