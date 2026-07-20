---
id: cap.document_export
title: Document I/O and Export
category: capability
domain: infrastructure
keywords: [export, Excel, CSV, JSON, file, read, write, CATDocument, save, load, lifecycle, storage]
apis: [CATDocument, CATDocumentServices, CATIPrtContainer, CATIPrtPart, CATInit]
frameworks: [ObjectModelerBase, MecModInterfaces, System]
playbooks: [workflow.batch, analyzer.rule, ui.result_dialog]
requires: [mecmod.feature]
release: [R19, R28]
tags: [capability]
---

# Document I/O and Export (文档读写与导出)

Managing the CATIA document lifecycle — open, save, close — and exporting feature/parameter/topology data to external formats (Excel, CSV, JSON) for reporting and integration.

## ⚠️ 重要修正

旧版本文档虚构了 `CATDocument` 自带的生命周期方法和几个不存在的接口，经 CAADoc（`ObjectModelerBase`/`MecModInterfaces` 框架）核实修正：

| 旧写法（虚构） | 真实情况 |
|---------------|---------|
| `pDoc->Close()` | **不存在**。`CATDocument` 类本身只有 3 个方法：`DisplayName()`、`GetDocId()`、`StorageName()`。关闭/移除文档的真实方法是 **`CATDocumentServices::Remove(CATDocument& iDoc, short iEmptyClipboardIfNecessary=TRUE)`**（静态方法） |
| `pDoc->Save()`/`SaveAs()` | 不存在于 `CATDocument` 上。真实是静态方法 **`CATDocumentServices::Save(CATDocument&, CATBoolean)`** 和 **`CATDocumentServices::SaveAs(CATDocument&, CATUnicodeString& iName, CATUnicodeString& iType, CATBoolean)`** |
| `pDoc->BeginTransaction()`/`EndTransaction()`/`UndoTransaction()` | **完全不存在**（CAADoc 零匹配，`CATDocument` 没有事务方法）。CATIA 没有"文档级事务回滚"这个编程模型；错误处理应通过检查每次调用的 `HRESULT` 返回值，必要时用 `CATError`/`CATSignalOn`/`CATSignalOff` 或直接放弃保存 |
| `CATDocumentServices::Open()`（两参数，无只读参数） | 真实方法名是 **`OpenDocument`**（不是 `Open`），签名 `OpenDocument(CATUnicodeString& iStorageName, CATDocument*& oOpenedDoc, CATBoolean iReadOnly=FALSE)` |
| `CATDocumentServices::RemoveFromList()` | 不存在。移除文档的方法名是 **`Remove()`** |
| `CATIDoc` | **不存在**（CAADoc 零匹配）。文档标识信息通过 **`CATIDocId`**（`CATDocument::GetDocId()` 获取）表达，不是叫 `CATIDoc` |
| `CATIStorage` | **不存在**（CAADoc 零匹配）。没有独立的"持久化存储"接口；文档持久化完全由 `CATDocumentServices` 静态方法（`Save`/`SaveAs`/`OpenDocument`/`New`）驱动 |
| `pPart->GetPartBodyFeature()`（Part 入口方法） | 不存在。真实入口是先取根容器的 `CATIPrtContainer`（`GetPart()` 返回 `CATISpecObject_var` 的 MechanicalPart），再从 `CATIPrtPart`（同一对象的另一接口）用 `GetCurrentFeature()`/`GetElectedFeature()`/`GetReferencePlanes()` 等方法定位具体特征 |
| `CATFile::ListFiles(dir, pattern, files)` | **不存在**这种便捷 API。目录遍历用 `System` 框架的全局函数 **`CATOpenDirectory()`** → 循环 **`CATReadDirectory()`** → **`CATCloseDirectory()`**（C 风格句柄，非 C++ 类） |
| `pParam->Value()` 直接当作 `double` 使用 | `CATICkeParm::Value()` 返回的是 **boxed** 的 `CATICkeInst_var`，必须再调用 `AsReal()`/`AsInteger()`/`AsString()` 取具体值（详见 [cap.parameter_system](parameter-system.md)） |

## 1. Summary

The document I/O and export capability covers CATIA document lifecycle operations (open, save, save-as, remove) — all driven through the static `CATDocumentServices` class, since `CATDocument` itself exposes almost no lifecycle methods — and the extraction of engineering data to flat-file formats (CSV, JSON, Excel via COM automation) for reporting, PLM integration, and downstream consumption.

## 2. Core Concepts

- **CATDocument is a thin data holder**: it only exposes `DisplayName()`, `StorageName()`, and `GetDocId()`. All lifecycle operations (open/save/save-as/remove/create) live on the **static** `CATDocumentServices` class instead
- **CATDocumentServices lifecycle**: `OpenDocument()` loads a document from disk; `New()`/`NewFrom()` create documents; `Save()`/`SaveAs()`/`SaveAsNew()` persist; `Remove()` releases a document from session/memory
- **Document types**: `CATPart`, `CATProduct`, `CATDrawing` — each is reached through a distinct root container interface (`CATIPrtContainer` for Part, `CATIProduct`/`CATIDocRoots` for Product; see [cap.assembly_tree](assembly-tree.md))
- **Part entry points**: `CATIPrtContainer::GetPart()` returns the MechanicalPart feature (`CATISpecObject_var`); QueryInterface that same object to `CATIPrtPart` for `GetCurrentFeature()`, `GetElectedFeature()`, `GetReferencePlanes()`, `GetCurrentTool()`
- **No transaction API**: CATIA's document model has no `BeginTransaction`/`EndTransaction`/`UndoTransaction` on `CATDocument`. Robustness comes from checking `HRESULT` at every step, not from a rollback API
- **Directory traversal**: Uses the C-style `System` framework global functions `CATOpenDirectory()` / `CATReadDirectory()` / `CATCloseDirectory()`, not a `CATFile` utility class
- **Excel export**: Excel COM automation (`IDispatch` on `Excel.Application`) enables writing data into workbooks, sheets, and cells — unrelated to CATIA's own document APIs
- **CSV/JSON export**: Plain text file I/O (`ofstream` or equivalent), independent of the CATIA document model
- **Read-only access**: Pass `iReadOnly=TRUE` to `OpenDocument()` when only extraction is needed, to avoid locking and modification side effects

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATDocumentServices::OpenDocument(path, doc, readOnly=FALSE)` | Opens a document from disk (static method) |
| `CATDocumentServices::Save(doc, interactive)` / `SaveAs(doc, name, type, interactive)` | Persists a document to disk (static methods) |
| `CATDocumentServices::Remove(doc, emptyClipboardIfNecessary=TRUE)` | Removes/closes a document from session (static method) |
| `CATDocumentServices::New(type, doc)` / `NewFrom(...)` | Creates a new document, optionally from an existing file |
| `CATDocument::GetDocId()` / `StorageName()` / `DisplayName()` | Document identity and path/display name accessors |
| `CATIPrtContainer::GetPart()` | Entry point for a CATPart document; returns the MechanicalPart feature |
| `CATIPrtPart` | Feature navigation on a MechanicalPart: `GetCurrentFeature()`, `GetElectedFeature()`, `GetReferencePlanes()`, `GetCurrentTool()`, `SetCurrentFeature()` |
| `CATInit::GetRootContainer(iid)` / `CATIDocRoots::GiveDocRoots()` | Entry point for CATProduct documents (see [cap.assembly_tree](assembly-tree.md)) |
| `CATOpenDirectory()` / `CATReadDirectory()` / `CATCloseDirectory()` | System-framework directory enumeration (C-style handles, `CATLib.h`) |

## 4. Common Patterns

### 4.1 Open a Document and Extract Feature Parameters

```cpp
CATDocument* pDoc = NULL;
HRESULT hr = CATDocumentServices::OpenDocument(
    "E:\\Data\\MyPart.CATPart", pDoc, TRUE);  // TRUE = read-only

if (SUCCEEDED(hr) && pDoc) {
    CATInit* pInit = NULL;
    pDoc->QueryInterface(IID_CATInit, (void**)&pInit);

    CATIPrtContainer* pPrtContainer =
        (CATIPrtContainer*)pInit->GetRootContainer("CATIPrtContainer");
    pInit->Release();

    CATISpecObject_var spMechanicalPart = pPrtContainer->GetPart();

    CATIPrtPart_var spPrtPart = spMechanicalPart;
    CATISpecObject_var spCurrentFeature = spPrtPart->GetCurrentFeature();

    // Extract parameters from spCurrentFeature ...
    ExtractFeatureParameters(spCurrentFeature);

    pPrtContainer->Release();
    CATDocumentServices::Remove(*pDoc);
}
```

### 4.2 Export Parameter Data to CSV

```cpp
#include <fstream>

void ExportToCSV(CATListValCATISpecObject_var& features,
                const CATUnicodeString& filePath) {
    std::ofstream csvFile(filePath.ConvertToChar());
    csvFile << "Feature,Parameter,Value,Unit" << std::endl;

    for (int i = 1; i <= features.Size(); i++) {
        CATUnicodeString featName = features[i]->GetName();
        // ... retrieve the feature's CATICkeParm parameters ...
        CATICkeParm_var pParam = ...;

        // CATICkeParm::Value() returns a *boxed* CATICkeInst_var;
        // it must be unboxed via AsReal()/AsInteger()/AsString()
        CATICkeInst_var spBoxedValue = pParam->Value();
        double numericValue = spBoxedValue->AsReal();

        csvFile << featName.ConvertToChar() << ","
                << pParam->Name().ConvertToChar() << ","
                << numericValue << ","
                << pParam->Show().ConvertToChar()
                << std::endl;
    }
    csvFile.close();
}
```

### 4.3 Export BOM Data to Excel via COM

```cpp
void ExportBOMToExcel(CATListOfCATUnicodeString& partNumbers,
                      CATListOfInt& counts) {
    // Excel COM automation is entirely independent of CATIA's document
    // model -- it talks to a separate Excel.Application server process
    CLSID clsid;
    CLSIDFromProgID(L"Excel.Application", &clsid);
    IDispatch* pExcel = NULL;
    CoCreateInstance(clsid, NULL, CLSCTX_LOCAL_SERVER,
                     IID_IDispatch, (void**)&pExcel);

    // Make Excel visible, add workbook
    // ... set cell values for part numbers and counts via IDispatch::Invoke ...

    // Save and close
    // pExcel->Invoke(...) to SaveAs and Quit
    pExcel->Release();
}
```

### 4.4 Save a Document and Check the Result (No Transaction API)

```cpp
CATDocument* pDoc = ...;

// CATIA has no BeginTransaction/EndTransaction/UndoTransaction on
// CATDocument -- always check the HRESULT of each static call instead
HRESULT hr = CATDocumentServices::Save(*pDoc, FALSE);  // FALSE = non-interactive
if (FAILED(hr)) {
    // Report the failure; there is no document-level rollback to invoke
    cout << "ERROR: Save failed for " << pDoc->StorageName().ConvertToChar() << endl;
}
```

### 4.5 Batch Process All CATPart Files in a Directory

```cpp
#include "CATLib.h"

void BatchProcessDirectory(const char* iDirPath) {
    CATDirectory dirHandle;
    if (CATOpenDirectory(iDirPath, &dirHandle) != CATLibSuccess) return;

    int endOfDir = 0;
    while (!endOfDir) {
        CATDirectoryEntry entry;
        if (CATReadDirectory(&dirHandle, &entry, &endOfDir) != CATLibSuccess) break;
        if (endOfDir) break;

        CATUnicodeString fileName(entry.d_name);
        if (!fileName.Search(".CATPart")) continue;  // simple suffix filter

        CATUnicodeString fullPath = CATUnicodeString(iDirPath) + "\\" + fileName;

        CATDocument* pDoc = NULL;
        HRESULT hr = CATDocumentServices::OpenDocument(fullPath, pDoc, TRUE);
        if (SUCCEEDED(hr) && pDoc) {
            AnalyzePart(pDoc);
            CATDocumentServices::Remove(*pDoc);
        }
    }
    CATCloseDirectory(&dirHandle);
}
```

## 5. Related Capabilities

- **[cap.assembly_tree](assembly-tree.md)** — Traverse product structure for BOM data extraction
- **[cap.parameter_system](parameter-system.md)** — Read parameter values (via `CATICkeParm`/`CATICkeInst`) for export to Excel/CSV
- **[cap.feature_recognition](feature-recognition.md)** — Filter features by type before exporting their data
- **[cap.geometry_query](geometry-query.md)** — Export geometric measurements (area, length, volume) to reports
