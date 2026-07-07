# Extension Pattern Example

Complete example of extending an existing CATIA component without modifying its source.

---

## Use Case

Add `ICalculator` interface to existing `CATDocument` class, allowing documents to perform calculations.

**Advantage**: No need to modify CATIA source code!

---

## Extension Types

| Type | Purpose | Example |
|------|---------|---------|
| **Code Extension** | Add interface (behavior) | Add `ICalculator` to `CATDocument` |
| **Data Extension** | Add data members (state) | Add custom metadata to `CATDocument` |

---

## Code Extension Example

### File Structure

```
<workspace>\
└── DocumentExtensions.edu/
    ├── IdentityCard/
    │   └── IdentityCard.h
    ├── PublicInterfaces/
    │   └── ICalculator.h
    └── Extensions.m/
        ├── Imakefile.mk
        ├── LocalInterfaces/
        │   └── CAAECalculator.h
        └── src/
            ├── ICalculator.cpp
            └── CAAECalculator.cpp
```

---

### File: IdentityCard/IdentityCard.h

```cpp
//
// COPYRIGHT DASSAULT SYSTEMES 2026
//
// -->Prereq Components Declaration
   AddPrereqComponent("System",Public);
   AddPrereqComponent("ObjectModelerBase",Public);
```

---

### File: PublicInterfaces/ICalculator.h

```cpp
#ifndef ICalculator_h
#define ICalculator_h

// COPYRIGHT DASSAULT SYSTEMES 2026

#include "CATBaseUnknown.h"

#ifndef ExportedByExtensions
#define ExportedByExtensions
#endif

extern ExportedByExtensions IID IID_ICalculator;

class ExportedByExtensions ICalculator : public CATBaseUnknown
{
    CATDeclareInterface;

public:
    virtual HRESULT Add(double a, double b, double *result) = 0;
    virtual HRESULT Subtract(double a, double b, double *result) = 0;
};

#endif
```

---

### File: src/ICalculator.cpp

```cpp
// COPYRIGHT DASSAULT SYSTEMES 2026

#include "ICalculator.h"

IID IID_ICalculator = {
    0x12345678, 0x1234, 0x1234,
    { 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0 }
};

CATImplementInterface(ICalculator, CATBaseUnknown);
```

---

### File: LocalInterfaces/CAAECalculator.h

**Naming Convention**: `XXXEYyyZzz`
- `XXX` = Framework prefix (e.g., `CAA`)
- `E` = Extension marker
- `YyyZzz` = Interface name without `I` (e.g., `Calculator`)

```cpp
#ifndef CAAECalculator_H
#define CAAECalculator_H

// COPYRIGHT DASSAULT SYSTEMES 2026

#include "CATBaseUnknown.h"
#include "ICalculator.h"

/**
 * @brief Code extension adding ICalculator to CATDocument
 * 
 * Extension naming: CAAECalculator
 * - CAA = Framework prefix
 * - E = Extension marker
 * - Calculator = Interface name without 'I'
 */
class CAAECalculator : public CATBaseUnknown
{
    CATDeclareClass;

public:
    CAAECalculator();
    virtual ~CAAECalculator();

    // ICalculator implementation
    virtual HRESULT Add(double a, double b, double *result);
    virtual HRESULT Subtract(double a, double b, double *result);

private:
    CAAECalculator(const CAAECalculator &iObjectToCopy);
    CAAECalculator & operator = (const CAAECalculator &iObjectToCopy);
};

#endif
```

---

### File: src/CAAECalculator.cpp

```cpp
// COPYRIGHT DASSAULT SYSTEMES 2026

#include "CAAECalculator.h"
#include "iostream.h"

//-----------------------------------------------------------------------------
// Code Extension Declaration
//-----------------------------------------------------------------------------
// Syntax: CATImplementClass(
//     ExtensionClassName,
//     CodeExtension,        ← Extension type
//     CATBaseUnknown,
//     ExtendedClassName     ← Class being extended
// )
CATImplementClass(CAAECalculator, CodeExtension, CATBaseUnknown, CATDocument);
//                                 ^^^^^^^^^^^^^                  ^^^^^^^^^^^
//                                 Extension type                 Extended class

//-----------------------------------------------------------------------------
// Bind interface to extension
//-----------------------------------------------------------------------------
CATImplementBOA(ICalculator, CAAECalculator);

//-----------------------------------------------------------------------------
// Constructor
//-----------------------------------------------------------------------------
CAAECalculator::CAAECalculator()
{
    cout << "CAAECalculator::CAAECalculator - Extension created" << endl;
}

//-----------------------------------------------------------------------------
// Destructor
//-----------------------------------------------------------------------------
CAAECalculator::~CAAECalculator()
{
    cout << "CAAECalculator::~CAAECalculator - Extension destroyed" << endl;
}

//-----------------------------------------------------------------------------
// ICalculator::Add implementation
//-----------------------------------------------------------------------------
HRESULT CAAECalculator::Add(double a, double b, double *result)
{
    if (!result) return E_POINTER;
    
    *result = a + b;
    cout << "Extension: " << a << " + " << b << " = " << *result << endl;
    return S_OK;
}

//-----------------------------------------------------------------------------
// ICalculator::Subtract implementation
//-----------------------------------------------------------------------------
HRESULT CAAECalculator::Subtract(double a, double b, double *result)
{
    if (!result) return E_POINTER;
    
    *result = a - b;
    cout << "Extension: " << a << " - " << b << " = " << *result << endl;
    return S_OK;
}
```

---

### File: Imakefile.mk

```makefile
# COPYRIGHT DASSAULT SYSTEMES 2026
#======================================================================
# Imakefile for module Extensions.m
#======================================================================
#
# SHARED LIBRARY
#
BUILT_OBJECT_TYPE = SHARED LIBRARY

# Link with required libraries
LINK_WITH= JS0GROUP
```

---

### File: CNext/code/dictionary/DocumentExtensions.edu.dico

**Critical Format**: `ExtendedClass  InterfaceAdded  libModuleName`

```
CATDocument  ICalculator  libExtensions
```

**Explanation**:
- `CATDocument` - The existing class being extended
- `ICalculator` - The interface being added
- `libExtensions` - The module containing the extension

---

## Usage Example

```cpp
// Example: Using the extended CATDocument

#include "CATDocument.h"
#include "ICalculator.h"

void TestDocumentExtension()
{
    // Get existing CATDocument (from CATIA session)
    CATDocument* pDoc = ...;  // Assume we have a document
    
    // Query for ICalculator interface (added by extension!)
    ICalculator* pCalc = NULL;
    HRESULT hr = pDoc->QueryInterface(IID_ICalculator, (void**)&pCalc);
    
    if (SUCCEEDED(hr) && pCalc)
    {
        cout << "Success! CATDocument now supports ICalculator" << endl;
        
        // Use calculator methods on document
        double result = 0;
        pCalc->Add(10.0, 5.0, &result);
        // Output: Extension: 10 + 5 = 15
        
        pCalc->Subtract(20.0, 8.0, &result);
        // Output: Extension: 20 - 8 = 12
        
        // Release interface
        pCalc->Release();
        pCalc = NULL;
    }
    else
    {
        cout << "Extension not loaded or registered" << endl;
    }
}
```

---

## Data Extension Example

### Use Case: Store Custom Metadata

```cpp
// File: LocalInterfaces/CAAEDocumentData.h

#ifndef CAAEDocumentData_H
#define CAAEDocumentData_H

#include "CATBaseUnknown.h"
#include "CATUnicodeString.h"

/**
 * @brief Data extension adding custom storage to CATDocument
 */
class CAAEDocumentData : public CATBaseUnknown
{
    CATDeclareClass;

public:
    CAAEDocumentData();
    virtual ~CAAEDocumentData();

    // Custom data members
    int _revisionNumber;
    CATUnicodeString _authorName;
    CATUnicodeString _projectCode;
    double _lastModifiedTimestamp;

private:
    CAAEDocumentData(const CAAEDocumentData &iObjectToCopy);
    CAAEDocumentData & operator = (const CAAEDocumentData &iObjectToCopy);
};

#endif
```

```cpp
// File: src/CAAEDocumentData.cpp

#include "CAAEDocumentData.h"
#include "iostream.h"

//-----------------------------------------------------------------------------
// Data Extension Declaration
//-----------------------------------------------------------------------------
CATImplementClass(CAAEDocumentData, DataExtension, CATBaseUnknown, CATDocument);
//                                   ^^^^^^^^^^^^^                  ^^^^^^^^^^^
//                                   Data extension                 Extended class

CAAEDocumentData::CAAEDocumentData()
    : _revisionNumber(0), _lastModifiedTimestamp(0.0)
{
    cout << "CAAEDocumentData::Constructor - Data storage initialized" << endl;
}

CAAEDocumentData::~CAAEDocumentData()
{
    cout << "CAAEDocumentData::Destructor" << endl;
}
```

**Dictionary:**
```
CATDocument  CAAEDocumentData  libExtensions
```

**Usage:**
```cpp
CATDocument* pDoc = ...;
CAAEDocumentData* pData = NULL;
HRESULT hr = pDoc->QueryInterface(IID_CAAEDocumentData, (void**)&pData);

if (SUCCEEDED(hr) && pData)
{
    // Access custom data
    pData->_revisionNumber = 5;
    pData->_authorName = "John Doe";
    pData->_projectCode = "PROJ-2026";
    
    cout << "Revision: " << pData->_revisionNumber << endl;
    
    pData->Release();
}
```

---

## Key Differences: Code vs Data Extension

| Aspect | Code Extension | Data Extension |
|--------|----------------|----------------|
| **Purpose** | Add interface (behavior) | Add data members (state) |
| **CATImplementClass 2nd param** | `CodeExtension` | `DataExtension` |
| **Has CATImplementBOA** | Yes | No |
| **Public interface** | Yes (IXxx.h) | No (direct member access) |
| **Dictionary entry** | `ExtendedClass Interface libModule` | `ExtendedClass ExtensionClass libModule` |
| **Example** | Add `ICalculator` to `CATDocument` | Add metadata to `CATDocument` |

---

## Extension Naming Convention

### Code Extension Class Name

**Format**: `XXXEYyyZzz`

| Part | Meaning | Example |
|------|---------|---------|
| `XXX` | Framework prefix | `CAA` |
| `E` | Extension marker | `E` |
| `YyyZzz` | Interface without `I` | `Calculator` (from `ICalculator`) |

**Examples**:
- `ICalculator` → `CAAECalculator`
- `IPrinter` → `CAAEPrinter`
- `IDataExport` → `CAAEDataExport`

### Data Extension Class Name

**Format**: `XXXEDescriptiveName`

**Examples**:
- `CAAEDocumentData`
- `CAAEMetadata`
- `CAAECustomStorage`

---

## Compilation

**Build**: `python skills/build.py Framework.edu/Module.m` | **Run**: `python skills/run.py`

**Quick command**:
```bash
python skills/build.py Framework.edu/Extensions.m
```

**Output**: `win_b64\code\bin\Extensions.m.dll`

---

## Deployment

1. Copy DLL:
   ```
   <workspace>\win_b64\code\bin\Extensions.m.dll
   → <CATIA_INSTALL>\win_b64\code\bin\
   ```

2. Copy dictionary:
   ```
   <workspace>\DocumentExtensions.edu\CNext\code\dictionary\DocumentExtensions.edu.dico
   → <CATIA_INSTALL>\win_b64\code\dictionary\
   ```

3. Restart CATIA

---

## Benefits of Extension Pattern

| Benefit | Description |
|---------|-------------|
| **No source modification** | Extend CATIA classes without changing them |
| **Modular** | Extensions in separate DLLs |
| **Runtime discovery** | `QueryInterface` checks if extension loaded |
| **Multiple extensions** | Different modules can extend same class |
| **Version safe** | Works across CATIA updates |

---

## Common Mistakes

### ❌ Wrong CATImplementClass syntax
```cpp
// WRONG - Missing CodeExtension keyword
CATImplementClass(CAAECalculator, Implementation, CATBaseUnknown, CATNull);

// CORRECT
CATImplementClass(CAAECalculator, CodeExtension, CATBaseUnknown, CATDocument);
```

### ❌ Wrong dictionary format
```
# WRONG - Using extension class name
CAAECalculator  ICalculator  libExtensions

# CORRECT - Using extended class name
CATDocument  ICalculator  libExtensions
```

### ❌ Forgot to include ObjectModelerBase
```cpp
// IdentityCard.h - Need this for CATDocument
AddPrereqComponent("ObjectModelerBase", Public);
```

### ❌ Wrong naming convention
```cpp
// WRONG
class MyCalculatorExtension : public CATBaseUnknown { };

// CORRECT
class CAAECalculator : public CATBaseUnknown { };
```

---

## Advanced: Multiple Extensions on Same Class

```
# Dictionary file
CATDocument  ICalculator  libExtensions1
CATDocument  IPrinter     libExtensions2
CATDocument  IDataExport  libExtensions3
```

**Result**: `CATDocument` now supports all three interfaces!

```cpp
CATDocument* pDoc = ...;

// Query for different extensions
ICalculator* pCalc = NULL;
pDoc->QueryInterface(IID_ICalculator, (void**)&pCalc);

IPrinter* pPrint = NULL;
pDoc->QueryInterface(IID_IPrinter, (void**)&pPrint);

IDataExport* pExport = NULL;
pDoc->QueryInterface(IID_IDataExport, (void**)&pExport);
```

---

## Testing Checklist

- [ ] Extension DLL compiles successfully
- [ ] Dictionary file created in correct location
- [ ] Dictionary copied to CATIA directory
- [ ] DLL copied to CATIA bin directory
- [ ] CATIA restarted after deployment
- [ ] `QueryInterface` returns S_OK
- [ ] Interface methods callable
- [ ] No memory leaks (all `Release()` called)

---

**Version**: 1.0  
**Created**: 2026-07-04  
**Complexity**: Intermediate  
**Use Case**: Extend existing CATIA components  
**Build Time**: 3-5 minutes
