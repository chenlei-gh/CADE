# AI Agent Guide for CATIA CAA Development

This guide helps AI agents correctly generate CAA code.

---

## Rule 0: ALWAYS consult CAA official documentation first for unknown issues

**Before asking or making assumptions, CHECK:**

1. **API Reference** (most authoritative):
   ```
   <CATIA_INSTALL>/CAADoc/Doc/docs/api/index.html
   ```
   - Class definitions, method signatures
   - Interface inheritance hierarchy
   - Return types and parameters

2. **Reference Manual** (framework-by-framework):
   ```
   <CATIA_INSTALL>/CAADoc/Doc/generated/refman/
   ```
   - Framework.htm files (e.g., System.htm, ObjectModelerBase.htm)
   - Complete API documentation per framework

3. **Use Cases & Technical Articles**:
   ```
   <CATIA_INSTALL>/CAADoc/Doc/online/
   ```
   - CAA*UseCases/ - Working examples
   - CAA*TechArticles/ - Architecture explanations
   - CAA*Base/ - Foundation concepts

**Example Workflow**:
```
Q: How do I use CATListOfInt?

Step 1: Check API reference
  → <CATIA_INSTALL>/CAADoc/Doc/docs/api/index.html
  → Search "CATListOfInt"
  → Find class definition, methods

Step 2: Check reference manual
  → <CATIA_INSTALL>/CAADoc/Doc/generated/refman/System.htm
  → Find framework containing CATListOfInt

Step 3: Check use cases
  → <CATIA_INSTALL>/CAADoc/Doc/online/CAASysUseCases/
  → Find example code

Step 4: ONLY if not found, generate based on CAA patterns
```

**Critical**: Official documentation is **always** more accurate than this skill for:
- Exact method signatures
- Framework dependencies
- Version-specific behavior
- Deprecated APIs

**This skill provides**: General patterns, structure, best practices.  
**Official docs provide**: Exact API details, parameters, return types.

---

## Critical Rules

### Rule 1: Code Reuse — Check Before Creating

**Before generating ANY component:**

1. **Ask user**: "Have you verified CAA doesn't already provide this?"
2. **Search official docs**: `<CATIA_INSTALL>/CAADoc/Doc/docs/api/index.html`
3. **Search workspace**: check for similar components in `*.edu` frameworks
4. **Anti-pattern check**: never create custom collections, math, strings, geometry, or UI

**Common anti-patterns to avoid**:
```
❌ Custom list → Use CATListOfInt, CATListOfDouble, CATListOf<T>
❌ Custom string → Use CATUnicodeString
❌ Custom math → Use CATMathVector, CATMathPoint, CATMathTransformation
❌ Custom geometry → Use CATBody, CATFace, CATEdge (CGM)
❌ Custom UI → Use CATDlgDialog, CATDlgPushButton, CATDlgLabel
```

---

### Rule 2: NEVER use `#ifndef` in IdentityCard.h

```cpp
// ❌ WRONG
#ifndef IdentityCard_h
#define IdentityCard_h
#define FRAMEWORK_NAME "MyFramework"
#endif

// ✅ CORRECT
//
// COPYRIGHT DASSAULT SYSTEMES 2026
//
// -->Prereq Components Declaration
   AddPrereqComponent("System",Public);
```

**Why**: CAA build system includes IdentityCard.h in a special way. Header guards break this mechanism.

---

### Rule 3: NEVER use standard C++ includes

```cpp
// ❌ WRONG
#include <iostream>
std::cout << "message" << std::endl;

// ✅ CORRECT
#include "iostream.h"
cout << "message" << endl;
```

**Why**: CAA predates C++11 and uses classic iostream without namespace.

---

### Rule 4: NEVER forget CAA macros

```cpp
// ❌ WRONG
class MyComponent : public CATBaseUnknown { };

// ✅ CORRECT
class MyComponent : public CATBaseUnknown
{
    CATDeclareClass;  // REQUIRED!
};
```

**Required macros**:
- **Interface**: `CATDeclareInterface`
- **Component**: `CATDeclareClass`, `CATImplementClass`, `CATImplementBOA`
- **Interface .cpp**: `CATImplementInterface`

---

### Rule 5: NEVER use wrong Imakefile syntax

```makefile
# ❌ WRONG
LINK_WITH = JS0GROUP

# ✅ CORRECT
LINK_WITH=JS0GROUP
```

**Why**: mkmk parser is strict. No space before `=`.

---

### Rule 6: NEVER put ToolsData inside framework

```
❌ WRONG: <workspace>/MyFramework.edu/ToolsData/
✅ CORRECT: <workspace>/ToolsData/
```

**Why**: Visual Studio integration expects ToolsData at workspace root.

---

### Rule 7: NEVER forget the Dictionary file

`CNext/code/dictionary/Framework.edu.dico` is the **7th mandatory file**. 

**Format** (Tab-separated):
```
ComponentName	libModuleName	ComponentName
```

**Why**: Without dictionary, component won't instantiate in CATIA → "Component not found" error.

---

### Rule 8: NEVER forget the Interface Implementation file

Every interface needs its own `.cpp` file with `CATImplementInterface`.

```cpp
// IMyInterface.cpp
#include "IMyInterface.h"

IID IID_IMyInterface = {
    0x12345678, 0x1234, 0x1234,
    { 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0 }
};

CATImplementInterface(IMyInterface, CATBaseUnknown);
```

**Why**: Provides `MetaObject()` implementation required for linking. IID is defined here, NOT in component .cpp.

---

### Rule 9: NEVER use `new` to create CAA components

```cpp
// ❌ WRONG
MyComponent* p = new MyComponent();

// ✅ CORRECT
IMyInterface* p = NULL;
HRESULT hr = ::CATInstantiateComponent("MyComponent", IID_IMyInterface, (void**)&p);
if (SUCCEEDED(hr) && p)
{
    // Use p
    p->Release();  // CRITICAL!
    p = NULL;
}
```

**Why**: CAA components must be created through component framework for proper lifecycle management.

---

### Rule 10: NEVER forget to Release() interface pointers

```cpp
// ❌ MEMORY LEAK
IMyInterface* p = NULL;
::CATInstantiateComponent("MyComp", IID_IMyInterface, (void**)&p);
p->DoWork();
// Forgot p->Release() → LEAK!

// ✅ CORRECT
IMyInterface* p = NULL;
HRESULT hr = ::CATInstantiateComponent("MyComp", IID_IMyInterface, (void**)&p);
if (SUCCEEDED(hr) && p)
{
    p->DoWork();
    p->Release();  // Always release!
    p = NULL;
}
```

**Why**: QueryInterface and CATInstantiateComponent increase reference count. Must call Release() to avoid memory leak.

---

### Rule 11: NEVER forget AddRef() when storing pointers

```cpp
// ❌ WRONG
class MyClass {
    IMyInterface* m_stored;
public:
    void Store(IMyInterface* p) {
        m_stored = p;  // Forgot AddRef!
    }
};

// ✅ CORRECT
class MyClass {
    IMyInterface* m_stored;
public:
    MyClass() : m_stored(NULL) {}
    
    void Store(IMyInterface* p) {
        if (m_stored) m_stored->Release();
        m_stored = p;
        if (m_stored) m_stored->AddRef();  // MUST call AddRef!
    }
    
    ~MyClass() {
        if (m_stored) m_stored->Release();
        m_stored = NULL;
    }
};
```

**Why**: Storing pointer extends object lifetime. Must increase refcount with AddRef().

---

## Generation Workflow

### Phase 1: Pre-Generation (MANDATORY)

**Execute BEFORE writing code:**

#### Step 1: Consult Official Documentation
**CHECK CAA DOCS FIRST** before generating:
```
1. API Reference: <CATIA_INSTALL>/CAADoc/Doc/docs/api/index.html
2. Reference Manual: <CATIA_INSTALL>/CAADoc/Doc/generated/refman/
3. Use Cases: <CATIA_INSTALL>/CAADoc/Doc/online/CAA*UseCases/
```

#### Step 2: Check with user
- What functionality is needed? What's the business purpose?
- Have they verified CAA doesn't provide this?
- Have they checked official CAA documentation?

#### Step 3: Search workspace
Search for similar component names and interfaces under the user's workspace `*.edu` frameworks. Check CAASystem.edu samples if present.

#### Step 4: Library identification
Confirm using CAA standard libraries:
- Collections: `CATListOf<T>` not custom arrays
- Strings: `CATUnicodeString` not `char*`
- Math: `CATMath*` not custom math

#### Step 5: Justification (if creating new)
If CAA doesn't provide it, document why a new component is necessary.

---

### Phase 2: Generation Checklist

#### File Structure
- [ ] Framework name ends with `.edu`
- [ ] Module name ends with `.m`
- [ ] Interface name starts with `I`
- [ ] ToolsData at workspace root (not in framework)
- [ ] Dictionary file present (7th file!)
- [ ] Interface .cpp present with CATImplementInterface (required for linking!)

#### IdentityCard.h
- [ ] No `#ifndef` guard
- [ ] Only `AddPrereqComponent()` macros
- [ ] Semicolons after each

#### Interface Header
- [ ] Inherits from `CATBaseUnknown`
- [ ] Has `CATDeclareInterface` macro
- [ ] `extern IID` declaration
- [ ] `ExportedByModuleName` macro
- [ ] All methods pure virtual (`= 0`)

#### Interface Implementation (Required!)
- [ ] Separate .cpp file for each interface
- [ ] Defines IID with GUID values
- [ ] `CATImplementInterface(Interface, CATBaseUnknown)` macro

#### Component Header
- [ ] Inherits from `CATBaseUnknown`
- [ ] Has `CATDeclareClass` macro
- [ ] Private copy constructor + assignment operator
- [ ] Header guard `_H` suffix (uppercase)

#### Component Implementation
- [ ] `CATImplementClass()` macro
- [ ] `CATImplementBOA(Interface, Component)` macro
- [ ] IID is in interface .cpp, NOT here
- [ ] Uses `iostream.h`, `cout` (not `<iostream>`, `std::cout`)

#### Imakefile.mk
- [ ] `BUILT_OBJECT_TYPE = SHARED LIBRARY`
- [ ] `LINK_WITH=` (no space before =)
- [ ] Includes `JS0GROUP`

#### Dictionary File
- [ ] Tab-separated (NOT spaces)
- [ ] Format: `ComponentName\tlibModuleName\tComponentName`
- [ ] File named `Framework.edu.dico`

---

## Code Templates

### 1. IdentityCard.h

```cpp
//
// COPYRIGHT DASSAULT SYSTEMES 2026
//
// -->Prereq Components Declaration
   AddPrereqComponent("System",Public);
```

### 2. Interface Header

```cpp
#ifndef IInterfaceName_h
#define IInterfaceName_h

// COPYRIGHT DASSAULT SYSTEMES 2026

#include "CATBaseUnknown.h"

#ifndef ExportedByModuleName
#define ExportedByModuleName
#endif

extern ExportedByModuleName IID IID_IInterfaceName;

class ExportedByModuleName IInterfaceName : public CATBaseUnknown
{
    CATDeclareInterface;

public:
    virtual HRESULT MethodName() = 0;
};

#endif
```

### 3. Interface Implementation (Required!)

```cpp
// COPYRIGHT DASSAULT SYSTEMES 2026

#include "IInterfaceName.h"

IID IID_IInterfaceName = {
    0x12345678, 0x1234, 0x1234,
    { 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0 }
};

CATImplementInterface(IInterfaceName, CATBaseUnknown);
```

### 4. Component Header

```cpp
#ifndef ComponentName_H
#define ComponentName_H

// COPYRIGHT DASSAULT SYSTEMES 2026

#include "CATBaseUnknown.h"
#include "IInterfaceName.h"

class ComponentName : public CATBaseUnknown
{
    CATDeclareClass;

public:
    ComponentName();
    virtual ~ComponentName();

    virtual HRESULT MethodName();

private:
    ComponentName(const ComponentName &iObjectToCopy);
    ComponentName & operator = (const ComponentName &iObjectToCopy);
};

#endif
```

### 5. Component Implementation

```cpp
// COPYRIGHT DASSAULT SYSTEMES 2026

#include "ComponentName.h"
#include "iostream.h"

CATImplementClass(ComponentName, Implementation, CATBaseUnknown, CATNull);

CATImplementBOA(IInterfaceName, ComponentName);

ComponentName::ComponentName()
{
    cout << "ComponentName::ComponentName" << endl;
}

ComponentName::~ComponentName()
{
    cout << "ComponentName::~ComponentName" << endl;
}

HRESULT ComponentName::MethodName()
{
    cout << "ComponentName::MethodName" << endl;
    return S_OK;
}
```

### 6. Imakefile.mk

```makefile
# COPYRIGHT DASSAULT SYSTEMES 2026
#======================================================================
# Imakefile for module ModuleName.m
#======================================================================
#
# SHARED LIBRARY
#
BUILT_OBJECT_TYPE = SHARED LIBRARY

LINK_WITH=JS0GROUP
```

### 7. Dictionary File

```
ComponentName	libModuleName	ComponentName
```

**CRITICAL**: Use Tab character (not spaces) between columns.

---

## Common AI Mistakes

| Mistake | Wrong | Correct |
|---------|-------|---------|
| C++11 features | `auto`, `unique_ptr` | Raw pointers, manual loops |
| Missing export macro | `class IMyInterface` | `class ExportedByModuleName IMyInterface` |
| Wrong header guard | `ComponentName_h` | `ComponentName_H` (uppercase) |
| Non-pure virtual | `virtual HRESULT M() { }` | `virtual HRESULT M() = 0;` |
| Missing BOA | No CATImplementBOA in .cpp | `CATImplementBOA(IMyInterface, MyComponent);` |
| Space in LINK_WITH | `LINK_WITH = JS0GROUP` | `LINK_WITH=JS0GROUP` |
| Missing Interface .cpp | Only .h file | Both .h and .cpp for interface |
| IID in component | IID in component.cpp | IID in interface.cpp |

---

## Response Format

When generating CAA code:

1. **Pre-generation report**: reuse check results, recommended libraries, justification
2. **File tree**: show complete structure
3. **Generate each file**: full content for all 7 files (including dictionary + interface .cpp!)
4. **Compilation instructions**:
   ```
   python skills/build.py Framework.edu/Module.m
   ```

---

## AI Capabilities

**CAN do**: Generate standard CAA code, create framework structures, write interfaces/components, generate Imakefile.mk and IdentityCard.h, compile via `skills/build.py`, start CATIA via `skills/run.py`, check workspace via `skills/workspace.py`.

**User must do**: Test CAA components in running CATIA.

---

## Summary Checklist

- [ ] All 7 files present (including dictionary + interface .cpp!)
- [ ] All macros present (`CATDeclareClass`, `CATImplementClass`, `CATDeclareInterface`, `CATImplementBOA`, `CATImplementInterface`)
- [ ] No C++11+ features
- [ ] No `std::` namespace
- [ ] IdentityCard.h has no header guard
- [ ] All interface methods pure virtual
- [ ] IID defined in interface .cpp
- [ ] `LINK_WITH=` no space
- [ ] ToolsData at workspace root
- [ ] Provided compilation instructions
