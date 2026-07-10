# Knowledge Gaps（知识缺口）

本目录跟踪 AI 从 CAADoc/官方文档解决但尚未沉淀到 CADE knowledge/ 的知识点。

## 沉淀流程

```
AI 从 CAADoc 学到新知识
    ↓
在这里创建一个 .md gap 文件（记录：来源、知识点、建议文件路径）
    ↓
用户确认后，AI 将其转为正式的 knowledge/ 或 patterns/ 文件
    ↓
删除 gap 文件
```

## Gap 文件格式

```markdown
# Gap: [知识点名称]

- **来源**: CAADoc/Doc/online/xxx 或 API 参考
- **发现时间**: 2026-07-10
- **建议路径**: knowledge/[domain]/[filename].md
- **涉及 API**: CATIxxx, CATIyyy
- **优先级**: high/medium/low

## 知识点概要

[三句话描述这个知识点是什么]
```

## 规则

1. **禁止空目录**：如果本目录有文件，说明存在未沉淀的知识缺口
2. **测试检查**：CI 会检查本目录，有文件 = 警告
3. **沉淀即删除**：转为正式文件后立即删除 gap 文件

---

**当前缺口**: 0
**最后检查**: 2026-07-10
