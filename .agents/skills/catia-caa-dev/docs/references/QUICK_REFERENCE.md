# CAA Quick Reference Cheat Sheet

## Essential Macros

### Component Declaration (in .h)
```cpp
class MyComponent : public CATBaseUnknown
{
    CATDeclareClass;  // Always in component class
    // ...
};
```

### Component Implementation (in .cpp)
```cpp
// Syntax: CATImplementClass(ClassName, CodeExtension, BaseClass, Interfaces)
CATImplementClass(MyComponent, Implementation, CATBaseUnknown, CATNull);
```

### Interface Declaration (in .h)
```cpp
class IMyInterface : public CATBaseUnknown
{
    CATDeclareInterface;  // Always in interface class
    // ...
};
```

### Interface Binding (in component .cpp)
```cpp
CATImplementBOA(IMyInterface, MyComponent);
```

### Interface Implementation (in interface .cpp)
```cpp
CATImplementInterface(IMyInterface, CATBaseUnknown);
```

### Interface IID Definition (in interface .cpp)
```cpp
IID IID_IMyInterface = { 
    0x12345678, 0x1234, 0x1234, 
    { 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0 } 
};
```

---

## Standard Includes

### Component Headers
```cpp
#include "CATBaseUnknown.h"      // Always needed
#include "CATUnicodeString.h"    // For strings
#include "CATErrorDef.h"         // For error codes
#include "iostream.h"            // NOT <iostream>
```

### Common System Headers
```cpp
#include "CATListOfInt.h"
#include "CATListOfCATString.h"
#include "CATMathPoint.h"
#include "CATMathVector.h"
```

---

## Return Types

### HRESULT Values
```cpp
S_OK        // Success
E_FAIL      // General failure
E_INVALIDARG // Invalid argument
E_NOTIMPL   // Not implemented
E_POINTER   // Null pointer
```

### Usage
```cpp
HRESULT MyMethod()
{
    if (error_condition)
        return E_FAIL;
    
    return S_OK;
}
```

---

## Parameter Naming Conventions

| Prefix | Meaning | Example |
|--------|---------|---------|
| `i` | Input parameter | `iLength` |
| `o` | Output parameter | `oResult` |
| `io` | Input/Output parameter | `ioData` |
| `_` | Private member | `_length` |

### Example
```cpp
HRESULT Calculate(const int iValue, double& oResult);
```

---

## Memory Management

### Creating Objects
```cpp
// NEVER use new directly!
// Use CATInstantiateComponent or factories

MyComponent* pComp = NULL;
HRESULT hr = ::CATInstantiateComponent(
    "MyComponent",
    IID_IMyInterface,
    (void**)&pComp
);
```

### Reference Counting
```cpp
// AddRef when storing pointer
pInterface->AddRef();

// Release when done
pInterface->Release();
pInterface = NULL;

// Smart pointers handle this automatically
CATBaseUnknown_var spInterface = pInterface;
```

---

## Common Patterns

### Query Interface
```cpp
IMyInterface* pInterface = NULL;
HRESULT hr = pComponent->QueryInterface(
    IID_IMyInterface,
    (void**)&pInterface
);
if (SUCCEEDED(hr))
{
    // Use pInterface
    pInterface->Release();
}
```

### Extension Pattern
```cpp
// Extension class name format: XXXEYyyZzz
class CAAECreateInstance : public CATBaseUnknown
{
    CATDeclareClass;
public:
    // Extension of base class
};

// In .cpp
CATImplementClass(
    CAAECreateInstance,
    DataExtension,        // Extension type
    CATBaseUnknown,
    BaseClass             // Class being extended
);
```

---

## Build Configuration

### Imakefile.mk Structure
```makefile
# Header
# COPYRIGHT DASSAULT SYSTEMES YYYY
#======================================================================

# Type
BUILT_OBJECT_TYPE = SHARED LIBRARY

# Dependencies
LINK_WITH= JS0GROUP Library1 Library2
```

### Common Libraries
```
JS0GROUP        # Core system (always needed)
JS0FM           # Framework management
JS0CORBA        # CORBA support
JS0MT           # Multi-threading
```

---

## Debugging Output

### Console Output
```cpp
#include "iostream.h"

cout << "Debug message: " << value << endl;
cerr << "Error message" << endl;
```

### Tracing
```cpp
#include "CATTrace.h"

CATTrace(1, "MyComponent::MyMethod called");
```

---

## String Handling

### CATUnicodeString
```cpp
#include "CATUnicodeString.h"

CATUnicodeString str = "Hello";
str.Append(" World");

// Convert to char*
const char* pChar = str.ConvertToChar();

// Build from parts
CATUnicodeString path;
path.BuildFromPath(dir, file);
```

---

## File Structure Template

### Minimal Component Files

**1. IdentityCard/IdentityCard.h**
```cpp
//
// COPYRIGHT DASSAULT SYSTEMES YYYY
//
   AddPrereqComponent("System",Public);
```

**2. PublicInterfaces/IMyInterface.h**
```cpp
#ifndef IMyInterface_h
#define IMyInterface_h
// ... (see template)
#endif
```

**3. Module.m/Imakefile.mk**
```makefile
BUILT_OBJECT_TYPE = SHARED LIBRARY
LINK_WITH= JS0GROUP
```

**4. Module.m/LocalInterfaces/MyComponent.h**
```cpp
#ifndef MyComponent_H
#define MyComponent_H
// ... (see template)
#endif
```

**5. Module.m/src/MyComponent.cpp**
```cpp
// COPYRIGHT ...
// CATImplementClass...
// CATImplementBOA...
// Implementation
```

**6. Module.m/src/IMyInterface.cpp**
```cpp
// COPYRIGHT ...
// IID definition
// CATImplementInterface...
```

---

## Compilation Commands

### Using Python Skills (recommended)
```bash
# Build a module
python skills/build.py Framework.edu/Module.m

# Build all modules in framework
python skills/build.py Framework.edu

# Check workspace
python skills/workspace.py Framework.edu
```

### Using mkmk (manual)
```cmd
mkmk -u Module.m       # Incremental build
mkmk -a Module.m       # Rebuild all
mkmk -g -u Module.m    # Debug build
```

---

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `CATBaseUnknown.h not found` | Missing include path | Add PublicInterfaces to include directories |
| `Unresolved external` | Missing library | Add JS0GROUP.lib to linker |
| `CATDeclareClass not found` | Wrong include | Include CATBaseUnknown.h |
| `Licensing error MAB` | No CAA license | Use VS manual compilation |
| `mkmk not found` | PATH not set | Add command directory to PATH |

---

## GUIDs

### Generate New GUID
1. Run Visual Studio's `guidgen.exe`
2. Select format 3 (static const)
3. Copy and adapt to CAA format

### CAA Format
```cpp
IID IID_IMyInterface = { 
    0x12345678, 0x1234, 0x1234,
    { 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0 } 
};
```

---

## Testing in CATIA

### Load DLL
1. Copy DLL to `$(CATIA_PATH)\win_b64\code\bin`
2. Restart CATIA
3. DLL loads automatically

### Create Component Instance
```cpp
// In CATIA macro or another component
IMyInterface* pInterface = NULL;
HRESULT hr = ::CATInstantiateComponent(
    "MyComponent",
    IID_IMyInterface,
    (void**)&pInterface
);
```

---

## Documentation Location

### Official CAA Documentation

**API Reference** (search classes/interfaces):
```
<CATIA_INSTALL>/CAADoc/Doc/docs/api/index.html
```

**Reference Manual** (framework docs):
```
<CATIA_INSTALL>/CAADoc/Doc/generated/refman/
```
- System.htm - Core framework
- ObjectModelerBase.htm - Object model
- [Framework].htm - Specific frameworks

**Use Cases** (examples):
```
<CATIA_INSTALL>/CAADoc/Doc/online/CAA*UseCases/
```

**Technical Articles** (concepts):
```
<CATIA_INSTALL>/CAADoc/Doc/online/CAA*TechArticles/
```

**When to Use**:
- Unknown class/interface → API Reference
- Framework dependencies → Reference Manual  
- Implementation patterns → Use Cases
- Architecture questions → Technical Articles

**Pro Tip**: Bookmark API reference for quick lookups!

---

## Version
Based on CATIA V5R28

---

## Component Lifecycle

### Creating Components
```cpp
// NEVER use new!
IMyInterface* p = NULL;
HRESULT hr = ::CATInstantiateComponent(
    "ComponentName",    // From .dico
    IID_IMyInterface,   // Interface to get
    (void**)&p          // Output
);

if (SUCCEEDED(hr) && p)
{
    p->DoWork();
    p->Release();  // CRITICAL!
    p = NULL;
}
```

### Memory Management
```cpp
// Reference counting rules
p->AddRef();   // When storing pointer
p->Release();  // When done with pointer

// QueryInterface adds reference
IAnotherInterface* p2 = NULL;
p1->QueryInterface(IID_IAnotherInterface, (void**)&p2);
// Must call p2->Release() later!
```

---

## Extension Patterns

### Code Extension
```cpp
// Add interface to existing class
class CAAEMyExtension : public CATBaseUnknown
{
    CATDeclareClass;
    // Interface methods
};

// In .cpp
CATImplementClass(
    CAAEMyExtension,
    CodeExtension,      // Extension type
    CATBaseUnknown,
    ExistingClass       // Class being extended
);

CATImplementBOA(IMyInterface, CAAEMyExtension);

// Dictionary
ExistingClass  IMyInterface  libMyModule
```

### Data Extension
```cpp
// Add data to existing class
CATImplementClass(
    CAAEDataStorage,
    DataExtension,      // Data extension
    CATBaseUnknown,
    ExistingClass
);

// Dictionary
ExistingClass  CAAEDataStorage  libMyModule
```

---

## Multi-Interface Components

```cpp
// Component implementing multiple interfaces
CATImplementClass(MyComponent, Implementation, CATBaseUnknown, CATNull);

// Bind all interfaces
CATImplementBOA(IInterface1, MyComponent);
CATImplementBOA(IInterface2, MyComponent);
CATImplementBOA(IInterface3, MyComponent);

// Dictionary lists all
MyComponent  libMyModule  MyComponent
MyComponent  IInterface1  libMyModule
MyComponent  IInterface2  libMyModule
MyComponent  IInterface3  libMyModule
```

---

## Interface Visibility

```
Framework.edu/
├── PublicInterfaces/       # External frameworks
├── ProtectedInterfaces/    # Derived frameworks only
└── Module.m/
    └── LocalInterfaces/    # Module-private
```

```cpp
// IdentityCard.h declares visibility
AddPrereqComponent("System", Public);      # Public access
AddPrereqComponent("Helper", Protected);   # Protected access
AddPrereqComponent("Utils", Private);      # Private access
```
