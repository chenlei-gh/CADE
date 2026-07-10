---
id: cap.document_export
title: Document I/O and Export
category: capability
domain: infrastructure
keywords: [export, Excel, CSV, JSON, file, read, write, CATDocument, save, load, lifecycle, storage]
apis: [CATIDoc, CATDocument, CATDocumentServices, CATIStorage, CATUnicodeString, file I/O]
frameworks: [AutomationInterfaces, System]
playbooks: [workflow.batch, analyzer.rule, ui.result_dialog]
requires: [mecmod.feature]
release: [R19, R28]
tags: [capability]
---

# Document I/O and Export (文档读写与导出)

Managing the CATIA document lifecycle — open, save, close — and exporting feature/parameter/topology data to external formats (Excel, CSV, JSON) for reporting and integration.

## 1. Summary

The document I/O and export capability covers CATIA document lifecycle operations (open, save, save-as, close) and the extraction of engineering data — feature parameters, BOM rows, analysis results — to flat-file formats (Excel via COM automation, CSV, JSON) for reporting, PLM integration, and downstream consumption.

## 2. Core Concepts

- **CATDocument lifecycle**: `CATDocumentServices::Open()` loads a document; `CATDocument::Save()` persists changes; `CATDocument::Close()` releases memory
- **Document types**: `CATPart`, `CATProduct`, `CATDrawing` — each has a distinct container interface (`CATIPrtPart`, `CATIPrtContainer`, etc.)
- **Storage vs. document**: `CATIStorage` represents the persistent data store; `CATDocument` is the in-memory representation
- **File path resolution**: `CATUnicodeString` handles path strings; use `CATFile` / `CATPathBuilder` for platform-independent path construction
- **Excel export**: Excel COM automation (`IDispatch` on `Excel.Application`) enables writing data into workbooks, sheets, and cells
- **CSV export**: Simple text file I/O using C++ standard library (`ofstream`) or `CATFile` utilities for structured delimiter-separated output
- **JSON export**: Manual JSON string construction or lightweight JSON library for hierarchical data serialization
- **Batch processing**: Iterate over multiple documents in a directory, extracting data from each and aggregating into a single report
- **Transaction safety**: Always wrap document modifications in `CATDocument::BeginTransaction()` / `EndTransaction()` / `UndoTransaction()` for rollback on failure
- **Read-only access**: Open documents in read mode when only extraction is needed to avoid locking and modification side effects

## 3. Key APIs

| API | Purpose |
|-----|---------|
| `CATDocument` | Core document object; open, save, save-as, close, transaction management |
| `CATDocumentServices` | Static services for opening documents by path, creating new documents, and session management |
| `CATIDoc` | COM interface on the document session; provides root container and document ID |
| `CATIStorage` | Persistent storage interface; read/write raw data streams to/from the document store |
| `CATIPrtContainer` | Entry point for CATProduct documents; provides `GetRootProduct()` for assembly tree traversal |
| `CATIPrtPart` | Entry point for CATPart documents; provides `GetMainBody()`, feature containers, and parameters |
| `CATFile` | Platform-independent file system utilities: path construction, exists check, directory creation |
| `CATUnicodeString` | Unicode-aware string class for file paths, data values, and identifier names |

## 4. Common Patterns

### 4.1 Open a Document and Extract Feature Parameters

```cpp
CATDocument* pDoc = NULL;
HRESULT hr = CATDocumentServices::Open(
    "E:\\Data\\MyPart.CATPart",
    pDoc, FALSE);  // read-only

if (SUCCEEDED(hr) && pDoc) {
    CATIPrtPart_var pPart = GetPartFromDoc(pDoc);
    CATISpecObject_var pFeature = pPart->GetPartBodyFeature();

    // Extract parameters...
    ExtractFeatureParameters(pFeature);

    pDoc->Close();
    CATDocumentServices::RemoveFromList(pDoc);
}
```

### 4.2 Export Parameter Data to CSV

```cpp
#include <fstream>

void ExportToCSV(CATListValCATISpecObject& features,
                const CATUnicodeString& filePath) {
    std::ofstream csvFile(filePath.ConvertToChar());

    // Header row
    csvFile << "Feature,Parameter,Value,Unit" << std::endl;

    for (int i = 1; i <= features.Size(); i++) {
        CATUnicodeString featName = features[i]->GetName();
        CATListValCATISpecObject_var params;
        features[i]->GetParameters(params);

        for (int j = 1; j <= params.Size(); j++) {
            CATICkeParm_var pParam = params[j];
            csvFile << featName.ConvertToChar() << ","
                    << pParam->GetName().ConvertToChar() << ","
                    << pParam->Value() << ","
                    << pParam->GetUnit().ConvertToChar()
                    << std::endl;
        }
    }
    csvFile.close();
}
```

### 4.3 Export BOM Data to Excel via COM

```cpp
void ExportBOMToExcel(CATListValCATUnicodeString& partNumbers,
                      CATListOfInt& counts) {
    // Create Excel application via COM
    CLSID clsid;
    CLSIDFromProgID(L"Excel.Application", &clsid);
    IDispatch* pExcel = NULL;
    CoCreateInstance(clsid, NULL, CLSCTX_LOCAL_SERVER,
                     IID_IDispatch, (void**)&pExcel);

    // Make Excel visible, add workbook
    // ... set cell values for part numbers and counts ...

    // Save and close
    // pExcel->Invoke(...) to SaveAs and Quit
    pExcel->Release();
}
```

### 4.4 Transaction-Safe Document Save

```cpp
CATDocument* pDoc = ...;

pDoc->BeginTransaction();
// ... make modifications ...
pDoc->EndTransaction();

// Persist to disk
HRESULT hr = pDoc->Save();
if (FAILED(hr)) {
    pDoc->UndoTransaction();  // Roll back if save fails
}
```

### 4.5 Batch Process All Part Documents in a Directory

```cpp
void BatchProcessDirectory(const CATUnicodeString& dirPath) {
    CATListOfCATUnicodeString files;
    CATFile::ListFiles(dirPath, "*.CATPart", files);

    for (int i = 1; i <= files.Size(); i++) {
        CATDocument* pDoc = NULL;
        CATDocumentServices::Open(files[i], pDoc, TRUE);

        // Process document...
        AnalyzePart(pDoc);

        pDoc->Close();
        CATDocumentServices::RemoveFromList(pDoc);
    }
}
```

## 5. Related Capabilities

- **[cap.assembly_tree](assembly-tree.md)** — Traverse product structure for BOM data extraction
- **[cap.parameter_system](parameter-system.md)** — Read parameter values for export to Excel/CSV
- **[cap.feature_recognition](feature-recognition.md)** — Filter features by type before exporting their data
- **[cap.geometry_query](geometry-query.md)** — Export geometric measurements (area, length, volume) to reports
