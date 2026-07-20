---
id: drawing.batch
title: Batch Drawing Generation
category: pattern
domain: drawing
keywords: [batch, drawing, template, title block, BOM, export, PDF]
apis: [CATIDftDrawing, CATIDftSheet, CATIProgressTaskUI]
requires: [drawing.basics, drawing.annotations]
patterns: [workflow.batch]
examples: []
release: [R19, R28]
tags: [pattern, drawing, batch]
---

# Batch Drawing Pattern (批量工程图生成)

根据模板批量生成 Part/Product 的工程图，自动填充标题栏、明细表。

完整的已核实实现骨架见 [pb.batch_drawing](../../playbooks/pb_batch_drawing.md)；本文档只给出流程概览与设计要点。

## ⚠️ 重要修正

本文档早期版本使用了虚构的 `CATIDrwSheet`/`CATIProgressCallback`，经核实：

| 错误写法 | 正确写法 |
|------|---------|
| `CATIDrwSheet` | `CATIDftSheet`（组件 `Sheet`/`Sheet2DL` 实现，见 [drawing.basics](../../knowledge/drawing/drawing_basics.md)） |
| `CATIProgressCallback`（虚构的进度回调接口） | 不存在。真实的批量任务进度报告体系是 `CATIProgressTask`/`CATIProgressTaskUI`（`ApplicationFrame` 框架）：把批量任务实现为 `CATIProgressTask::PerformTask(CATIProgressTaskUI *ipiProgressUI, void *iData)`，框架在执行期间通过 `ipiProgressUI` 回调 `SetRange(min,max)`/`SetProgress(value)`/`SetComment(text)` 更新进度条，并可用 `IsInterrupted()` 检查用户是否取消 |
| `pDrawing->SaveAs(outPath)` | `CATIDftDrawing`/`CATDocument` 没有 `SaveAs` 成员方法，用静态方法 `CATDocumentServices::SaveAs(CATDocument&, CATUnicodeString& iName, CATUnicodeString& iType, CATBoolean)` |

## 适用场景

- 标准化零件图纸批量输出
- 组件图纸带 BOM 表
- 内部图纸规范统一

## 流程

```
Product Tree
    ↓
遍历所有 Part/Product（CATIProduct::GetChildren）
    ↓
打开/新建 Drawing Template (.CATDrawing)
    ↓
├── 挂载/生成视图（CATITPSViewFactory + CATIDftGenViewFactory，或 CreateViewWithMakeUp + CATIGenerSpec）
├── 收集 BOM 数据（独立导出，图纸内表格是已知文档缺口，见 drawing.annotations）
├── 标题栏走模板 + 发布参数关联（不是程序化 SetField）
├── 应用公司标准样式
└── 保存为 .CATDrawing（CATDocumentServices::SaveAs）
    ↓
汇总报告（可选：包装为 CATIProgressTask 供 UI 显示进度）
```

## 关键设计点

1. **模板优先** — 所有图纸从 .CATDrawing 模板派生，确保一致
2. **视图生成没有一键 API** — 需要走 `CATITPSViewFactory`/`CATIDftGenViewFactory` 或 `CATIDrwFactory::CreateViewWithMakeUp`+`CATIGenerSpec` 两条真实链条之一（见 drawing.basics）
3. **标题栏映射** — 通过 Knowledgeware 发布参数关联到模板预置文本对象，不是"设置字段"式 API
4. **BOM 表生成** — 图纸内嵌表格是已知文档缺口；数据本身独立导出更可靠（见 `pb.export_bom`）
5. **进度报告** — 大批量处理时，把整体任务实现为 `CATIProgressTask`，交给框架驱动 UI 进度条（`CATIProgressTaskUI`），而不是自定义回调接口

## AI 生成规则

- [ ] 先检查模板文件是否存在
- [ ] 创建/修改 Drawing 后必须 `CATDocumentServices::SaveAs`/`Save`
- [ ] 视图创建没有一键方法，按 drawing.basics 中真实链条组装
- [ ] 标题栏字段通过发布参数关联填充，不要臆造 `SetField` 类方法
- [ ] 批量操作如需进度反馈，实现 `CATIProgressTask::PerformTask`，不要自定义 `CATIProgressCallback`
- [ ] 支持 CATDrawing / PDF / DXF 导出时，走 `CATDocumentServices::SaveAs` 的对应格式参数或专用导出接口，不要假设 Drawing 对象自带导出方法
