# CAA Dictionary File - Critical Missing Component

## ⚠️ IMPORTANT DISCOVERY

**Dictionary files (.dico) are ESSENTIAL for CAA components but were MISSING from the original skill!**

Without a dictionary file, your component:
- ❌ Cannot be instantiated by CATIA
- ❌ Won't be found by `CATInstantiateComponent()`
- ❌ Interfaces won't be resolvable via `QueryInterface()`

## What is a Dictionary File?

**Purpose**: Maps component names to their implementations and interfaces

**Location**: `Framework.edu/CNext/code/dictionary/Framework.edu.dico`

**Format**: Plain text file with component registrations

---

## Dictionary File Format

### Basic Structure (B28 BOA format)

```
# COPYRIGHT DASSAULT SYSTEMES YYYY

#===========================================================================
# Dictionary for Framework.edu
#===========================================================================

ComponentName    libModuleName    ComponentName
```

### Format Explanation

Each line has **3 columns** (tab or space separated):

1. **Component Name** — The C++ class name (e.g., `Calculator`)
2. **Library Name** — `lib` + module name, the DLL providing the component (e.g., `libCalculator`)
3. **Class Name** — Same as column 1, the implement class name

> **Note for B28 BOA**: Interface binding is handled by `CATImplementBOA` macro, NOT by the dico file.
> The dico maps component → DLL, while BOA handles component → interface.

### Adding CATICreateInstance (Factory Support)

If you need `CATInstantiateComponent()` to work, add an extra line:

```
ComponentName    libModuleName    ComponentName
ComponentName    CATICreateInstance    libModuleName
```

---

## Complete Example: Calculator Component

### File: MathFramework.edu/CNext/code/dictionary/MathFramework.edu.dico

```
# COPYRIGHT DASSAULT SYSTEMES 2026

#===========================================================================
# Dictionary for MathFramework.edu
#===========================================================================

# Calculator Component
Calculator       libCalculator        Calculator
Calculator       CATICreateInstance    libCalculator

# If component has multiple interfaces
Calculator       libCalculator        Calculator
Calculator       CATICreateInstance    libCalculator
```

### Explanation

1. **Column 1**: Component name — same as `CATImplementClass` first argument
2. **Column 2**: `lib` + module name — the DLL file name
3. **Column 3**: Component name again
4. Factory instantiation (`CATCreateInstance` line) is optional but recommended

---

## Library Naming Convention

**Important**: Library name in dictionary = Module name with `lib` prefix

| Module Name | Dictionary Entry |
|-------------|------------------|
| `Calculator.m` | `libCalculator` |
| `HelloComponent.m` | `libHelloComponent` |
| `DataProcessor.m` | `libDataProcessor` |

**Rule**: `lib` + ModuleName (without `.m`)

---

## Directory Structure (CORRECTED)

```
Framework.edu/
├── IdentityCard/
│   └── IdentityCard.h
├── PublicInterfaces/
│   └── ICalculator.h
├── Module.m/
│   ├── Imakefile.mk
│   ├── LocalInterfaces/
│   │   └── Calculator.h
│   └── src/
│       ├── ICalculator.cpp
│       └── Calculator.cpp
└── CNext/                          ⚠️ CRITICAL - Often forgotten!
    └── code/
        └── dictionary/
            └── Framework.edu.dico  ⚠️ REQUIRED!
```

---

## When Dictionary is Missing

### Symptoms

```cpp
// Try to create component
ICalculator* pCalc = NULL;
HRESULT hr = ::CATInstantiateComponent(
    "Calculator",
    IID_ICalculator,
    (void**)&pCalc
);

// Result: hr = E_FAIL
// Error: Component not found in dictionary
```

### Fix

1. Create `CNext/code/dictionary/` directories
2. Create `.dico` file
3. Add component registration
4. Rebuild
5. Copy DLL to CATIA's `code\bin\`
6. Copy `.dico` to CATIA's `code\dictionary\`

---

## Multiple Components in One Framework

### Example: Framework with 2 Components

```
# MathFramework.edu.dico

#===========================================================================
# Calculator Component
Calculator       libCalculator        Calculator
Calculator       CATICreateInstance    libCalculator

#===========================================================================
# Geometry Component  
#===========================================================================
GeometryProcessor    libGeometry            GeometryProcessor
GeometryProcessor    CATICreateInstance      libGeometry
```

---

## Component Extension Pattern

When extending an existing component from another framework:

```
# Extend CAAComponent with MyExtension
# In B28 BOA, CATImplementBOA handles interface binding

# Register your extension
CAAComponent    libMyExtension    CAAComponent
CAAComponent    CATICreateInstance    libMyExtension
```

**Note**: Component name stays the same, the BOA macro in your extension .cpp binds the new interface.

---

## Factory Components

For components that create other components:

```
# Factory pattern
CalculatorFactory    libCalculatorFactory    CalculatorFactory
CalculatorFactory    CATICreateInstance       libCalculatorFactory

# The component it creates
Calculator           libCalculator              Calculator
Calculator           CATICreateInstance         libCalculator
```

---

## Automation Components (VBA Support)

For components accessible from VBA/macros:

```
# Automation interface
# B28 BOA: interface binding via CATImplementBOA, dico maps component→DLL
Calculator    libCalculator         Calculator
Calculator    CATICreateInstance    libCalculator      # Factory

# For VBA/automation support, add IDispatch
Calculator    IDispatch             libCalculator
```

---

## Common Mistakes

### Mistake 1: Wrong Library Name

```
# ❌ WRONG - missing 'lib' prefix
Calculator    Calculator    Calculator

# ✅ CORRECT
Calculator    libCalculator    Calculator
```

### Mistake 2: Missing CATICreateInstance

```
# ⚠️ PARTIAL - compiles but CATInstantiateComponent() may fail
Calculator    libCalculator    Calculator

# ✅ CORRECT - full registration with factory support
Calculator    libCalculator         Calculator
Calculator    CATICreateInstance    libCalculator
```

### Mistake 3: Wrong File Location

```
❌ WRONG:
Framework.edu/
└── dictionary/
    └── Framework.edu.dico

✅ CORRECT:
Framework.edu/
└── CNext/
    └── code/
        └── dictionary/
            └── Framework.edu.dico
```

### Mistake 4: Wrong File Name

```
❌ WRONG: Framework.dico
❌ WRONG: Framework.dic
❌ WRONG: dictionary.dico

✅ CORRECT: Framework.edu.dico
```

---

## Deployment

### Build-time Location

```
<workspace>\Framework.edu\CNext\code\dictionary\Framework.edu.dico
```

### Runtime Location (Copy after build)

```
<CATIA_INSTALL>\win_b64\code\dictionary\Framework.edu.dico
```

**Critical**: Dictionary must be in CATIA's dictionary directory at runtime!

---

## Testing Dictionary Registration

### Method 1: Check File Exists

```cmd
dir "<CATIA_INSTALL>\win_b64\code\dictionary\YourFramework.edu.dico"
```

### Method 2: Search in Dictionary

```cmd
findstr /i "YourComponent" "<CATIA_INSTALL>\win_b64\code\dictionary\*.dico"
```

### Method 3: Try Instantiation

```cpp
IYourInterface* pInterface = NULL;
HRESULT hr = ::CATInstantiateComponent(
    "YourComponent",
    IID_IYourInterface,
    (void**)&pInterface
);

if (SUCCEEDED(hr))
    cout << "SUCCESS: Component found in dictionary!" << endl;
else
    cout << "FAIL: Component not in dictionary or DLL not found" << endl;
```

---

## Complete File Checklist (UPDATED)

### Minimum Files for Working Component

- [ ] `IdentityCard/IdentityCard.h`
- [ ] `PublicInterfaces/IInterface.h`
- [ ] `Module.m/Imakefile.mk`
- [ ] `Module.m/LocalInterfaces/Component.h`
- [ ] `Module.m/src/Component.cpp`
- [ ] `Module.m/src/IInterface.cpp`
- [ ] **`CNext/code/dictionary/Framework.edu.dico`** ⚠️ CRITICAL!

**Total: 7 files minimum (was 5, now 7!)**

---

## Integration with Build Process

### mkmk Automatically Handles Dictionary

When you run `mkmk`, it:
1. ✅ Compiles your code
2. ✅ Creates DLL
3. ✅ **Copies dictionary to runtime location**

**No manual copy needed if using mkmk!**

### Manual Build Requires Manual Copy

If using Visual Studio manual compilation:
```cmd
# After building DLL
copy Framework.edu\CNext\code\dictionary\Framework.edu.dico ^
     "<CATIA_INSTALL>\win_b64\code\dictionary\"
```

---

## Advanced: Late Type

For components that support **late binding** (automation):

```
# Component with late type
Calculator    libCalculator         Calculator
Calculator    CATICreateInstance    libCalculator

# Late type entry (for CreateObject)
Calculator    Calculator          CATScriptTypeLib
```

This allows VBA code:
```vb
Set calc = CATIA.CreateObject("Calculator")
```

---

## Template: Dictionary File

```
# COPYRIGHT DASSAULT SYSTEMES YYYY

#===========================================================================
# Dictionary for [FrameworkName].edu
#===========================================================================

# [ComponentName] Component
# Description: [Brief description]
#===========================================================================
[ComponentName]    lib[ModuleName]         [ComponentName]
[ComponentName]    CATICreateInstance      lib[ModuleName]
```

---

## Impact on Existing Skill

### Files to Update

1. **SKILL.md** - Add Dictionary section
2. **AI_GUIDE.md** - Add to file checklist
3. **templates/** - Add `Framework.edu.dico` template
4. **EXAMPLE_CALCULATOR.md** - Add dictionary file
5. **README.md** - Update file count (5→7 files)

### Critical Addition to Checklist

```
✅ Generation Checklist (UPDATED):
- [ ] IdentityCard.h
- [ ] Interface.h
- [ ] Imakefile.mk
- [ ] Component.h
- [ ] Component.cpp
- [ ] Framework.edu.dico  ⚠️ NEW - CRITICAL!
```

---

## Why This Was Missed

1. **Simple components might work without dictionary** (if only using direct linking)
2. **mkmk might auto-generate** dictionary in some cases
3. **Examples in CAASystem.edu had dictionary** but we didn't examine CNext directory
4. **Focus was on C++ code**, not deployment structure

---

## Conclusion

**Dictionary files are MANDATORY for production CAA components!**

Without dictionary:
- Component compiles ✅
- DLL is created ✅
- But component is **unusable in CATIA** ❌

**AI agents MUST generate dictionary file for every framework!**

---

## Version
1.0 - Critical addition to CAA skill based on documentation review
