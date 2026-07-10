---
id: drawing.batch
title: Batch Drawing Generation
category: pattern
domain: drawing
keywords: [batch, drawing, template, title block, BOM, export, PDF]
apis: [CATIDftDrawing, CATIDrwView, CATIDrwTable, CATIDrwTitleBlock]
requires: [drawing.basics, drawing.annotations]
patterns: [workflow.batch]
examples: []
release: [R19, R28]
tags: [pattern, drawing, batch]
---

# Batch Drawing Pattern (批量工程图生成)

根据模板批量生成 Part/Product 的工程图，自动填充标题栏、明细表。

## 适用场景

- 标准化零件图纸批量输出
- 组件图纸带 BOM 表
- 内部图纸规范统一

## 流程

```
Product Tree
    ↓
遍历所有 Part/Product
    ↓
加载 Drawing Template (.CATDrawing)
    ↓
├── 拷贝模板到目标路径
├── 创建三视图（Front/Top/Right）
├── 创建 BOM 表（如是 Product）
├── 填充标题栏
├── 应用公司标准样式
└── 保存为 .CATDrawing / 导出 PDF
    ↓
汇总报告
```

## 实现框架

```cpp
class ATBatchDrawingEngine {
public:
    HRESULT SetTemplate(const CATUnicodeString &iPath);
    HRESULT AddPart(CATISpecObject *iPart);
    HRESULT SetOutputDir(const CATUnicodeString &iDir);
    HRESULT SetExportFormat(ATExportFormat iFmt);  // CATDrawing, PDF, DXF
    HRESULT Execute(CATIProgressCallback *iProgress = NULL);
    
private:
    HRESULT ProcessSinglePart(CATISpecObject *iPart);
    HRESULT CreateViews(CATIDftDrawing *pDrw, CATISpecObject *iPart);
    HRESULT FillTitleBlock(CATIDrwSheet *pSheet, CATISpecObject *iPart);
    HRESULT FillBOM(CATIDrwSheet *pSheet, CATISpecObject *iProduct);
    HRESULT ExportToPDF(CATIDftDrawing *pDrw, const CATUnicodeString &iPath);
};
```

## 关键设计点

1. **模板优先** — 所有图纸从 .CATDrawing 模板派生，确保一致
2. **视图配置** — 支持自定义视图组合（三视图/轴测图/剖面）
3. **标题栏映射** — 从 Part 属性自动映射到标题栏字段
4. **BOM 表生成** — 遍历 Product 子节点，自动填充明细表
5. **进度报告** — 大模型批量处理时反馈进度

## AI 生成规则

- [ ] 先检查模板文件是否存在
- [ ] 创建 Drawing 后必须 Save
- [ ] 视图位置按比例自动分配
- [ ] 标题栏字段用 Part 的属性值填充
- [ ] 批量操作支持进度回调
- [ ] 支持 CATDrawing / PDF / DXF 三种导出
