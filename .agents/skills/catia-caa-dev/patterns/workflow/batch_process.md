---
id: workflow.batch
title: Batch Process
category: pattern
domain: workflow
keywords: [batch, process, loop, document, iterate, automation, progress, cancel]
apis: [CATIProgressTask, CATIProgressTaskUI, CATFrmEditor, CATIPrtContainer, CATIPrtPart]
requires: [mecmod.feature, ui.dialog]
patterns: []
examples: []
release: [R19, R28]
tags: [pattern, workflow, batch, automation]
---

# Batch Process Pattern (批量处理模式)

对当前打开的 Document 或一组输入文件进行批量处理，包含进度反馈和错误处理。

## ⚠️ 重要修正

之前版本以下 API 经核实**不存在**：

| 虚构 | 真实 API |
|------|---------|
| `CATSessionServices` / `GetActiveDocument()` | 不存在。当前文档经 `CATFrmEditor::GetCurrentEditor()->GetDocument()` 获取 |
| `CATIDocument` / `pDoc->GetPartContainer()` | 不存在。Part 容器经 `CATIContainerOfDocument::GetSpecContainer()` → QI `CATIPrtContainer`（MecModInterfaces） |
| `CATIProgressBar` + `Begin/SetCurrentPosition/SetMessage/IsCancelled/End` | 不存在。真实进度机制是 **`CATIProgressTask`**（实现 `PerformTask` 回调）+ **`CATIProgressTaskUI`**（`SetRange/SetProgress/SetComment/IsInterrupted`），ApplicationFrame |

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
  ├── Progress (CATIProgressTask / CATIProgressTaskUI)
  │
  └── Result
        ├── Success Count
        ├── Error List
        └── Summary Report
```

## 实现步骤

### Step 1: 获取当前 Document 与 Part 容器

```cpp
#include "CATFrmEditor.h"
#include "CATDocument.h"
#include "CATIContainerOfDocument.h"
#include "CATIPrtContainer.h"
#include "CATIPrtPart.h"

CATFrmEditor *pEditor = CATFrmEditor::GetCurrentEditor();
if (!pEditor) return E_FAIL;
CATDocument *pDoc = pEditor->GetDocument();

CATIContainerOfDocument_var spContOfDoc;
HRESULT hr = pDoc->QueryInterface(IID_CATIContainerOfDocument,
                                  (void**)&spContOfDoc);
if (FAILED(hr)) return hr;

CATIContainer *pSpecCont = NULL;
hr = spContOfDoc->GetSpecContainer(pSpecCont);
if (FAILED(hr)) return hr;

CATIPrtContainer_var spPrtCont;
hr = pSpecCont->QueryInterface(IID_CATIPrtContainer, (void**)&spPrtCont);
pSpecCont->Release();
if (FAILED(hr)) return hr;

CATISpecObject_var spPart = spPrtCont->GetPart();
// 需要 CATIPrtPart 方法时对 spPart 再 QueryInterface(IID_CATIPrtPart)
```

### Step 2: 进度反馈（真实机制：CATIProgressTask）

CATIA 的进度对话框是**任务式**：实现 `CATIProgressTask::PerformTask(ui, userData)`，框架在后台/模态进度框中调用它，经 `CATIProgressTaskUI` 回报进度：

```cpp
class ATBatchTask : public CATIProgressTask {
public:
    HRESULT PerformTask(CATIProgressTaskUI *iUI, void *iUserData) override {
        iUI->SetRange(0, (long)_items.Size());
        iUI->Interruptible(TRUE);              // 允许用户取消

        for (int i = 1; i <= _items.Size(); i++) {
            CATBoolean interrupted = FALSE;
            iUI->IsInterrupted(&interrupted);  // 用户点了取消？
            if (interrupted) break;

            iUI->SetComment(CATUnicodeString("Processing ") + _items[i].name);
            iUI->SetProgress(i);

            ProcessItem(_items[i]);
        }
        iUI->Flush();
        return S_OK;
    }
    // GetCatalogName / GetIcon 按接口要求实现
private:
    ItemList _items;
};
```

`CATIProgressTaskUI` 真实方法（ApplicationFrame 头文件已核实）：`SetRange(min,max)`、`SetProgress(value)`、`IsInterrupted(&bool)`、`SetComment(str)`、`SetObject(str)`、`Interruptible(bool)`、`Flush()`。

### Step 3: 错误收集

```cpp
struct BatchResult {
    int total;
    int succeeded;
    int failed;
    CATListValCATUnicodeString errors;   // 存错误描述
};

BatchResult result;
result.total = items.Size();
result.succeeded = 0;
result.failed = 0;

for (int i = 1; i <= items.Size(); i++) {
    HRESULT hr = ProcessItem(items[i]);  // 用 HRESULT 而不是 try/catch（CAA 惯例）
    if (SUCCEEDED(hr)) {
        result.succeeded++;
    } else {
        result.errors.Append(CATUnicodeString("Item ") + items[i].name + " failed");
        result.failed++;
    }
}
```

## 关键点

1. **进度反馈必须有** —— 批量任务没有进度用户会以为死机；用 `CATIProgressTask` 而不是对话框里手绘进度条
2. **支持取消** —— 每轮先 `IsInterrupted()`
3. **错误不阻断流程** —— 单个失败记 HRESULT 继续，不抛异常
4. **最终报告** —— 处理完毕用 `CATDlgNotify` 显示 Summary
5. **内存管理** —— `_var` 智能指针自动释放；原始指针（如 `GetSpecContainer` 返回的）用毕 `Release()`
