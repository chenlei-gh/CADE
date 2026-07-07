---
id: workflow.batch
title: Batch Process
category: pattern
domain: workflow
keywords: [batch, process, loop, document, iterate, automation, progress bar, cancel]
apis: [CATSessionServices, CATIDocument, CATIPrtContainer, CATISpecObject]
requires: [mecmod.feature, ui.dialog]
patterns: []
examples: []
release: [R19, R28]
tags: [pattern, workflow, batch, automation]
---

# Batch Process Pattern (批量处理模式)

对当前打开的 Document 或一组输入文件进行批量处理，包含进度条和错误处理。

## 适用场景

- 批量导出 (STEP/IGES/STL)
- 批量规则检查
- 批量修改参数
- 批量生成报表

## 架构模式

```
Batch Processor
  │
  ├── Input (输入)
  │     ├── Current Document
  │     └── File List (可选)
  │
  ├── Processor (处理逻辑)
  │     ├── Init
  │     ├── Process Each Item
  │     ├── Progress Update
  │     └── Finalize
  │
  ├── Progress Bar (进度条)
  │     └── CATIProgressBar
  │
  └── Result
        ├── Success Count
        ├── Error List
        └── Summary Report
```

## 实现步骤

### Step 1: 获取当前 Document

```cpp
CATSessionServices* pSession = ...;
CATIDocument* pDoc = pSession->GetActiveDocument();
CATIPrtContainer* pContainer = pDoc->GetPartContainer();
CATIPrtPart_var pPart = pContainer->GetPart();
```

### Step 2: 进度条

```cpp
CATIProgressBar* pProgress = ...;
pProgress->Begin("Processing...", totalCount);

for (int i = 1; i <= totalCount; i++) {
    // 处理...
    pProgress->SetCurrentPosition(i);
    pProgress->SetMessage("Processing " + itemName);

    if (pProgress->IsCancelled()) {
        break; // 用户取消
    }
}

pProgress->End();
```

### Step 3: 错误收集

```cpp
struct BatchResult {
    int total;
    int succeeded;
    int failed;
    CATListValResult errors;
};

BatchResult result;
result.total = items.Size();

for (int i = 1; i <= items.Size(); i++) {
    try {
        ProcessItem(items[i]);
        result.succeeded++;
    } catch (...) {
        Result err;
        err.problem = "Processing failed";
        result.errors.Append(err);
        result.failed++;
    }
}
```

## 关键点

1. **进度条必须有** —— 批量任务没有进度条用户体验极差
2. **支持取消** —— `IsCancelled()` 允许用户中断
3. **错误不阻断流程** —— 单个失败不停止后续处理
4. **最终报告** —— 处理完毕显示 Summary
5. **内存管理** —— 大数据量分批处理，避免内存溢出
