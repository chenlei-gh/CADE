# Pattern Library (开发模式库)

可复用的 CAA 开发架构模式。分为两层：

- **Coarse (配方)**: 完整工具架构（Analyzer、Rule Checker、Result Dialog、Batch Process）
- **Block (积木)**: 最小可复用代码块（Visitor、Locator），AI 自行组合

## 目录

| 层 | 目录 | 模式 |
|------|------|------|
| Coarse | `analyzer/` | Geometry Analyzer、Rule Checker |
| Coarse | `ui/` | Result Dialog |
| Coarse | `workflow/` | Batch Process |
| Block | `blocks/` | Feature Visitor、Selection Locator |
