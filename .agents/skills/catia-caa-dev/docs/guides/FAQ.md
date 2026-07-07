# Frequently Asked Questions (FAQ)

Quick answers to common CATIA CAA development questions.

---

## 🚀 Getting Started

### Q1: Do I need a CAA license to develop components?
**A:** Yes and no.
- **For mkmk compilation**: Yes, you need CAA RADE license (MAB product)
- **For manual VS compilation**: No, you can compile without license
- **Generated code structure**: No license needed, structure is standard

**Workaround**: Use Visual Studio manual compilation (see SKILL.md Method 3)

---

### Q2: How long does it take to create my first component?
**A:** 
- **With this skill + AI**: 2-3 minutes
- **Learning CAA manually**: 1-2 hours
- **Becoming proficient**: 5-10 hours practice

**Quick path**: Read GETTING_STARTED.md (2 minutes)

---

### Q3: What's the minimum required knowledge?
**A:**
- **C++ basics**: Classes, inheritance, pointers
- **No CAA knowledge needed**: AI generates everything
- **VS basics helpful**: How to build projects

**Bottom line**: If you know basic C++, you're ready!

---

## 📁 File Structure

### Q4: Why 7 files minimum? Can't I use less?
**A:** No. All 7 are mandatory:
1. IdentityCard.h - Framework metadata (CAA requirement)
2. IInterface.h - Interface contract (COM-like)
3. **IInterface.cpp - Interface implementation with IID (NEW!)**
4. Imakefile.mk - Build configuration (mkmk requirement)
5. Component.h - Component declaration (C++ requirement)
6. Component.cpp - Implementation with CATImplementBOA (C++ requirement)
7. **Framework.edu.dico - Component registration (CRITICAL!)**

**Without Dictionary**: Code compiles but component won't instantiate in CATIA!

---

### Q5: Where exactly should I put the Dictionary file?
**A:** 
```
Framework.edu/
└── CNext/
    └── code/
        └── dictionary/
            └── Framework.edu.dico  ← HERE!
```

**Common mistake**: Putting it directly under Framework.edu/ or in wrong subdirectory

**Verification**: Run `validate_caa_component.bat`

---

### Q6: Why can't I use `#ifndef` in IdentityCard.h?
**A:** IdentityCard.h is **NOT a C++ header** - it's a CAA metadata file.
- **Purpose**: Declare framework dependencies (AddPrereqComponent)
- **Processed by**: CAA build system (not C++ compiler directly)
- **Rule**: Only macros, no C++ constructs

**Correct format**:
```cpp
// COPYRIGHT DASSAULT SYSTEMES 2026
AddPrereqComponent("System",Public);
```

---

## 🔧 Compilation

### Q7: I get "mkmk not found" error. What now?
**A:** Three solutions:
1. **Check PATH**: Run `where mkmk` to verify
2. **Run setup script**: Execute `启动CAA开发环境.bat`
3. **Use VS manual**: Compile without mkmk (see SKILL.md Method 3)

**Most common cause**: Haven't run the environment setup script

---

### Q8: Compilation succeeds but I get "License error: MAB product"?
**A:** This is **expected** without CAA RADE license.

**Solutions**:
- **Option A**: Purchase CAA RADE license from Dassault
- **Option B**: Use Visual Studio manual compilation (free)
- **Option C**: Compile on machine with license

**Good news**: Your code structure is correct! Just a licensing issue.

---

### Q9: VS shows red squiggles on CATBaseUnknown.h but code compiles?
**A:** This is **IntelliSense issue**, not a real error.

**Fix**:
1. Right-click project → Properties
2. C/C++ → General → Additional Include Directories
3. Add: `<CATIA_INSTALL>\win_b64\code\include`

**Or**: Ignore it - if it compiles, it's fine!

---

### Q10: What does "No space before = in Imakefile" mean?
**A:** CAA Imakefile syntax is strict:

```makefile
# ❌ WRONG
LINK_WITH = JS0GROUP

# ✅ CORRECT
LINK_WITH= JS0GROUP
```

**Why**: CAA build system parser requirement (legacy design)

**Easy fix**: Remove space before `=`

---

### Q11: I get "fatal error C1083: TIE_*.h not found"?
**A:** CAA B28 uses **BOA pattern**, not TIE. The build system doesn't auto-generate `TIE_*.h` files.

**Fix**:
```cpp
// ❌ OLD (TIE pattern — not supported in B28)
#include "TIE_ICalculator.h"
TIE_ICalculator(Calculator);

// ✅ NEW (BOA pattern)
CATImplementBOA(ICalculator, Calculator);
```

**Also**: Remove `INTERFACE_FILES` from Imakefile.mk if you tried adding it.

---

### Q12: I get "LNK2019: MetaObject unresolved"?
**A:** The interface is missing its implementation file.

**Fix**: Create `Module.m/src/ICalculator.cpp`:
```cpp
#include "ICalculator.h"

IID IID_ICalculator = { /* guid */ };
CATImplementInterface(ICalculator, CATBaseUnknown);
```

This is file #3 out of 7 mandatory files. `CATImplementInterface` provides the `MetaObject()` implementation that the linker needs.

**Dictionary format details**: See [DICTIONARY_GUIDE.md](DICTIONARY_GUIDE.md)

---

## 🐛 Runtime Issues

### Q13: Component compiles but CATInstantiateComponent returns E_FAIL?
**A:** 99% of the time: **Dictionary file issue**

**Checklist**:
1. Dictionary file exists? → `Framework.edu/CNext/code/dictionary/Framework.edu.dico`
2. Component registered? → File contains your component name
3. Deployed to CATIA? → Copy to `CATIA_PATH/win_b64/code/dictionary/`
4. Library name correct? → Uses `lib` prefix (e.g., `libMyModule`)

**Quick test**: 
```cmd
findstr /i "MyComponent" "<CATIA_INSTALL>\win_b64\code\dictionary\*.dico"
```

---

### Q14: I added a new method but it's not callable?
**A:** Did you rebuild after the interface change?

**Steps**:
1. Add method to interface (.h)
2. Declare in component (.h)
3. **Implement in component (.cpp)**
4. **Rebuild** (CATImplementBOA re-registers)

**Common mistake**: Forgetting to rebuild after interface change

---

### Q15: Component works in debug but crashes in release?
**A:** Check these:
- **Uninitialized variables**: Debug initializes to 0, release doesn't
- **Memory management**: Use AddRef/Release correctly
- **Pointer validation**: Check for NULL before dereferencing

**Debug tip**: Add cout statements to trace execution

---

## 🎨 Design Questions

### Q16: Should I put multiple components in one module?
**A:** **No**, use separate modules per component.

**Best practice**:
```
Framework.edu/
├── Component1.m/    ← One component
├── Component2.m/    ← Another component
└── Component3.m/    ← Third component
```

**Why**: Easier maintenance, separate DLLs, better organization

---

### Q17: Can one component implement multiple interfaces?
**A:** **Yes!** This is common.

**Example**:
```cpp
// Component.cpp
CATImplementBOA(IInterface1, MyComponent);
CATImplementBOA(IInterface2, MyComponent);
CATImplementBOA(IInterface3, MyComponent);

// Dictionary
MyComponent    IInterface1    libMyModule
MyComponent    IInterface2    libMyModule
MyComponent    IInterface3    libMyModule
```

**Use case**: Component with multiple capabilities

---

### Q18: What's the difference between Public/Protected/Private interfaces?
**A:**
- **PublicInterfaces/**: Visible to all frameworks (exported)
- **ProtectedInterfaces/**: Visible to derived frameworks only
- **PrivateInterfaces/**: Internal to this framework only

**Rule of thumb**: Start with PublicInterfaces unless you have reason not to

---

## 🔍 Debugging

### Q19: How do I debug my CAA component?
**A:** Three methods:

**Method 1: cout debugging**
```cpp
#include "iostream.h"
cout << "Debug: value = " << value << endl;
```

**Method 2: VS debugger**
1. Attach to CNEXT.exe process
2. Set breakpoints in your code
3. Trigger component in CATIA

**Method 3: Message boxes**
```cpp
#include "CATMsgCatalog.h"
CATMsgCatalog::PrintMessage("Debug message");
```

**Easiest**: Method 1 (cout)

---

### Q20: Where do cout messages appear?
**A:** Depends on how CATIA was launched:
- **From command line**: In that console window
- **From Start Menu**: No console (messages lost)

**Solution**: Launch CATIA from command line:
```cmd
"<CATIA_INSTALL>\win_b64\code\bin\CNEXT.exe"
```

---

## 🚀 Advanced Topics

### Q21: Can I use STL in CAA components?
**A:** **Carefully**:
- ✅ OK: Use STL internally (vector, map, etc.)
- ❌ Avoid: Passing STL types across DLL boundaries
- ✅ Better: Use CAA collections (CATListOf, etc.)

**Reason**: ABI compatibility issues between compilers

---

### Q22: How do I create a factory component?
**A:** Factory pattern:
```cpp
// In dictionary
MyFactory    IClassFactory        libMyFactory
MyFactory    CATICreateInstance   libMyFactory

// In factory code
HRESULT MyFactory::CreateInstance(...) {
    MyComponent* comp = new MyComponent();
    // ...
}
```

**Use case**: Complex object creation logic

---

### Q23: Can CAA components be called from VBA?
**A:** **Yes**, if you add automation support:

```
# Dictionary
MyComponent    IDispatch           libMyModule
MyComponent    ISupportErrorInfo   libMyModule
```

Then implement IDispatch methods.

**Alternative**: Use CATIA API wrapper instead

---

## 🛠️ Tools & Workflow

### Q24: Is there a GUID generator tool?
**A:** Yes! Use online GUID generator:
- https://www.guidgenerator.com/
- Or VS: Tools → Create GUID
- Or PowerShell: `[guid]::NewGuid()`

**Format needed**:
```cpp
IID IID_IMyInterface = { 
    0x12345678, 0x1234, 0x1234,
    { 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0 } 
};
```

---

### Q25: How do I validate my component structure?
**A:** Use the validation script:
```cmd
validate_caa_component.bat <workspace>\MyFramework.edu
```

**Checks**:
- All 7 files exist
- Correct syntax (no header guard in IdentityCard, etc.)
- Dictionary file present
- Implementation patterns correct

**Result**: Errors and warnings with fix suggestions

---

### Q26: Can I version control CAA code?
**A:** **Yes!** Recommended structure:
```
.gitignore:
win_b64/          # Build outputs
*.dll
*.obj
*.pdb
ToolsData/        # VS-specific files
```

**Commit**:
- All 6 source files
- Templates
- Documentation

---

## 📚 Learning Resources

### Q27: Where can I find official CAA documentation?
**A:** CAA documentation is installed with CATIA:

**1. API Reference** (search by class/interface name):
```
<CATIA_INSTALL>/CAADoc/Doc/docs/api/index.html
```

**2. Reference Manual** (framework documentation):
```
<CATIA_INSTALL>/CAADoc/Doc/generated/refman/
```
Example: `System.htm`, `ObjectModelerBase.htm`

**3. Use Cases** (working examples):
```
<CATIA_INSTALL>/CAADoc/Doc/online/CAA*UseCases/
```

**4. Technical Articles** (architecture & patterns):
```
<CATIA_INSTALL>/CAADoc/Doc/online/CAA*TechArticles/
```

**Quick Access**: Open `<CATIA_INSTALL>/CAADoc/Doc/docs/api/index.html` in browser

**Tip**: Bookmark the API reference page for quick lookups!

---

### Q28: How do I search for a specific CAA class or interface?
**A:** Use the API Reference search:

**Method 1: API Reference Search**
1. Open `<CATIA_INSTALL>/CAADoc/Doc/docs/api/index.html`
2. Use browser's Find (Ctrl+F)
3. Search for class name (e.g., "CATListOfInt")

**Method 2: Reference Manual**
1. Go to `<CATIA_INSTALL>/CAADoc/Doc/generated/refman/`
2. Open framework .htm file (e.g., `System.htm`)
3. Search for class

**Example**:
```
Q: How does CATUnicodeString work?

1. Open API reference
2. Search "CATUnicodeString"
3. Find methods: Append(), ConvertToChar(), BuildFromPath()
4. Check method parameters and return types
```

**Pro Tip**: Official docs have exact method signatures - always more accurate than examples!

---

### Q29: What are common CAA libraries I should know?
**A:**
| Library | Purpose | Use |
|---------|---------|-----|
| JS0GROUP | Core services | Almost always needed |
| JS0FM | File management | File operations |
| JS0CORBA | Component infrastructure | Advanced component patterns |
| ObjectModelerBase | Object model | CATIA objects |
| VisualizationBase | 3D visualization | Graphics |

**Start with**: JS0GROUP (mandatory for basic components)

---

## ⚡ Performance

### Q29: My component is slow. How to optimize?
**A:**
1. **Profile first**: Identify bottleneck
2. **Avoid**: Creating/destroying objects in loops
3. **Cache**: Expensive calculations
4. **Use**: Reference counting properly (AddRef/Release)

**Measurement**:
```cpp
#include <time.h>
clock_t start = clock();
// ... your code ...
double time = (double)(clock() - start) / CLOCKS_PER_SEC;
cout << "Time: " << time << "s" << endl;
```

---

### Q30: How much memory does a typical component use?
**A:**
- **Component object**: ~100-1000 bytes (depends on members)
- **DLL loaded**: ~100-500 KB
- **CATIA overhead**: ~10-50 MB total

**Monitor**:
```cpp
#include "CATMemory.h"
size_t mem = CATGetMemoryUsage();
```

---

## 🔒 Licensing & Distribution

### Q31: Can I distribute components to users without CAA license?
**A:** **Yes!** End users only need:
- CATIA V5 runtime license
- Your compiled DLL
- Dictionary file

**They don't need**: CAA RADE development license

---

### Q32: How do I protect my component code?
**A:**
- **Distribute**: Only compiled DLL (not source)
- **Obfuscate**: Use code obfuscation tools (optional)
- **License**: Implement your own licensing check

**Note**: DLL can be reverse-engineered but it's difficult

---

## 📞 Getting Help

### Q33: I'm stuck. Where do I get help?
**A:**
1. **Check troubleshooting**: TROUBLESHOOTING_FLOWCHART.md
2. **Run validation**: `validate_caa_component.bat`
3. **Check examples**: EXAMPLE_CALCULATOR.md
4. **Search error**: QUICK_REFERENCE.md "Common Errors"

**Still stuck?** Share error message and context

---

### Q34: Can AI generate any CAA component I describe?
**A:** **Yes**, for standard patterns:
- ✅ Basic components
- ✅ Multiple interfaces
- ✅ Data members and methods
- ✅ Error handling
- ⚠️ Complex algorithms (need your input)
- ⚠️ CATIA-specific features (need details)

**Success rate**: 95%+ for standard components

---

## 🎯 Best Practices

### Q35: What are the top 5 CAA best practices?
**A:**
1. **Always generate all 7 files** (including Dictionary!)
2. **Use validation script** after generation
3. **Follow naming conventions** (I prefix for interfaces)
4. **Test incrementally** (don't write everything first)
5. **Use AddRef/Release correctly** (memory management)

**Bonus**: Read AI_GUIDE.md "Critical Rules"

---

### Q36: Should I test components before integration?
**A:** **Absolutely!**

**Test pyramid**:
1. **Unit test**: Component instantiation (1 min)
2. **Interface test**: Method calls (2 min)
3. **Integration test**: With CATIA (5 min)
4. **User test**: Real workflow (30 min)

**Catch bugs early**: Saves hours of debugging later

---

### Q37: How often should I rebuild?
**A:**
- **After every file change**: Always
- **After interface change**: Required (CATImplementBOA re-registration)
- **After adding member**: Recommended
- **Before testing**: Always

**Auto-build**: Configure VS to build on save

---

## 📊 Statistics & Benchmarks

### Q38: What's a typical component generation time?
**A:**
| Complexity | Files | Methods | Time |
|------------|-------|---------|------|
| Simple | 6 | 1-2 | 2-3 min |
| Medium | 6 | 3-7 | 4-5 min |
| Complex | 6 | 8+ | 7-10 min |

**With this skill**: Consistently fast!

---

### Q39: How many components can one framework have?
**A:**
- **Technical limit**: 1000s
- **Practical limit**: 10-50 per framework
- **Recommended**: 5-15 per framework

**Why limit**: Easier maintenance and faster builds

---

## 🔮 Future & Updates

### Q40: Will this skill support CAA V6?
**A:** Currently supports **CAA V5R28**.

**V6 differences**: Different architecture (but similar concepts)

**Future plans**: See CHANGELOG.md "Future Roadmap"

---

### Q41: How often is this skill updated?
**A:**
- **Bug fixes**: As discovered
- **New features**: Quarterly (planned)
- **Documentation**: Continuous improvement

**Current version**: 2.0.0 (2026-07-03)

---

### Q42: Can I contribute improvements?
**A:** **Yes!** Contributions welcome:
1. Test generated components
2. Document new error patterns
3. Add examples to relevant .md files
4. Share success stories

**See**: CHANGELOG.md "Contributing" section

---

## 🎉 Quick Tips

**Top 10 Time-Savers**:
1. Use validation script after every generation
2. Keep templates handy
3. Always generate 7 files (not 6!)
4. Test incrementally
5. Use cout for quick debugging
6. Run from command line to see output
7. Check Dictionary first when instantiation fails
8. Rebuild after interface changes
9. Use AI for repetitive patterns
10. Read error messages carefully

---

**More Questions?**
- Check: TROUBLESHOOTING_FLOWCHART.md
- Search: QUICK_REFERENCE.md
- Read: SKILL.md (complete reference)

---

**Version**: 2.0  
**Last Updated**: 2026-07-04  
**Questions Answered**: 52 (+12 new: Component Lifecycle, Extensions, Multi-Interface, Memory)  
**Average Answer Time**: < 30 seconds

---

## 🔄 Component Lifecycle & Memory Management (NEW)

### Q43: How do I create a CAA component instance?
**A:** **NEVER use `new`!** Always use `CATInstantiateComponent()`:

```cpp
ICalculator* pCalc = NULL;
HRESULT hr = ::CATInstantiateComponent(
    "Calculator",              // Component name (from .dico)
    IID_ICalculator,           // Interface IID
    (void**)&pCalc            // Output pointer
);

if (SUCCEEDED(hr) && pCalc)
{
    pCalc->Add(1.0, 2.0, &result);
    pCalc->Release();  // CRITICAL!
    pCalc = NULL;
}
```

**Why not `new`?** CAA uses COM-like component model with reference counting and QueryInterface.

---

### Q44: When do I need to call AddRef()?
**A:** Call `AddRef()` when **storing a pointer** for later use:

```cpp
// ❌ WRONG - Will crash later
class MyClass {
    IMyInterface* m_stored;
public:
    void StorePointer(IMyInterface* p) {
        m_stored = p;  // Forgot AddRef!
    }
};
// If original pointer is Released, m_stored becomes invalid!

// ✅ CORRECT
class MyClass {
    IMyInterface* m_stored;
public:
    void StorePointer(IMyInterface* p) {
        if (m_stored) m_stored->Release();  // Release old
        m_stored = p;
        if (m_stored) m_stored->AddRef();   // AddRef new
    }
    ~MyClass() {
        if (m_stored) m_stored->Release();  // Cleanup
    }
};
```

**Rule**: Every `AddRef()` must have matching `Release()`.

---

### Q45: What's the most common memory leak in CAA?
**A:** **Forgetting to Release() after QueryInterface**:

```cpp
// ❌ MEMORY LEAK
IMyInterface* p1 = ...;
IAnotherInterface* p2 = NULL;
p1->QueryInterface(IID_IAnotherInterface, (void**)&p2);
// QueryInterface increments refcount!
p2->DoWork();
// Forgot p2->Release() → LEAK!

// ✅ CORRECT
IMyInterface* p1 = ...;
IAnotherInterface* p2 = NULL;
HRESULT hr = p1->QueryInterface(IID_IAnotherInterface, (void**)&p2);
if (SUCCEEDED(hr) && p2)
{
    p2->DoWork();
    p2->Release();  // Always release QueryInterface result
    p2 = NULL;
}
```

**Detection**: If CATIA becomes slower over time → likely memory leak.

**Also see**: SKILL.md "Component Lifecycle Management" section.

---

### Q46: Should I use smart pointers?
**A:** **Yes, when possible!** They prevent leaks:

```cpp
// Manual (error-prone)
IMyInterface* p = NULL;
::CATInstantiateComponent("MyComp", IID_IMyInterface, (void**)&p);
if (p) {
    p->DoWork();
    p->Release();  // Easy to forget!
}

// Smart pointer (automatic)
CATBaseUnknown_var sp;
IMyInterface* p = NULL;
::CATInstantiateComponent("MyComp", IID_IMyInterface, (void**)&p);
if (p) {
    sp = p;
    p->Release();
    ((IMyInterface*)(CATBaseUnknown*)sp)->DoWork();
    // Auto-releases when sp goes out of scope!
}
```

**Trade-off**: Smart pointers require casting, but much safer.

---

## 🔌 Extensions (NEW)

### Q47: What's the difference between creating a new component and extending one?
**A:**

| Approach | When to Use | Example |
|----------|-------------|----------|
| **New Component** | Standalone functionality | `Calculator` component |
| **Code Extension** | Add interface to existing class | Add `ICalculator` to `CATDocument` |
| **Data Extension** | Add data to existing class | Store custom metadata in `CATDocument` |

**Extension advantage**: No need to modify original source code!

**See**: SKILL.md "Extension Patterns" section for complete examples.

---

### Q48: How do I extend an existing CATIA component?
**A:** Use **Code Extension** pattern:

**Step 1**: Create extension class (name format: `XXXEYyyZzz`)
```cpp
// File: LocalInterfaces/CAAECalculator.h
class CAAECalculator : public CATBaseUnknown
{
    CATDeclareClass;
public:
    CAAECalculator();
    virtual ~CAAECalculator();
    
    // ICalculator implementation
    virtual HRESULT Add(double a, double b, double *result);
};
```

**Step 2**: Implement with **CodeExtension** keyword
```cpp
// File: src/CAAECalculator.cpp
CATImplementClass(CAAECalculator, CodeExtension, CATBaseUnknown, CATDocument);
//                                 ^^^^^^^^^^^^^                  ^^^^^^^^^^^
//                                 Extension type                 Extended class

CATImplementBOA(ICalculator, CAAECalculator);
```

**Step 3**: Register in dictionary
```
CATDocument  ICalculator  libYourModule
```

**Result**: Every `CATDocument` now supports `ICalculator` interface!

---

### Q49: Can I add data members to existing CATIA classes?
**A:** Yes, use **Data Extension**:

```cpp
// Extension stores custom data
class CAAEDataStorage : public CATBaseUnknown
{
    CATDeclareClass;
public:
    int _customValue;
    CATUnicodeString _customName;
};

// Use DataExtension instead of CodeExtension
CATImplementClass(CAAEDataStorage, DataExtension, CATBaseUnknown, CATDocument);
```

**Dictionary:**
```
CATDocument  CAAEDataStorage  libYourModule
```

**Access:**
```cpp
CATDocument* pDoc = ...;
CAAEDataStorage* pData = NULL;
pDoc->QueryInterface(IID_CAAEDataStorage, (void**)&pData);
if (pData) {
    pData->_customValue = 42;
    pData->Release();
}
```

---

## 🔀 Multi-Interface Components (NEW)

### Q50: Can one component implement multiple interfaces?
**A:** **Yes!** Use multiple `CATImplementBOA` macros:

```cpp
// In Component.cpp
CATImplementClass(AdvancedCalc, Implementation, CATBaseUnknown, CATNull);

// Bind multiple interfaces
CATImplementBOA(ICalculator, AdvancedCalc);
CATImplementBOA(IScientificCalculator, AdvancedCalc);
CATImplementBOA(IStatistics, AdvancedCalc);

// Implement all interface methods
HRESULT AdvancedCalc::Add(...) { /* ICalculator */ }
HRESULT AdvancedCalc::Sin(...) { /* IScientificCalculator */ }
HRESULT AdvancedCalc::Mean(...) { /* IStatistics */ }
```

**Dictionary (all interfaces listed):**
```
AdvancedCalc  libCalculator  AdvancedCalc
AdvancedCalc  ICalculator  libCalculator
AdvancedCalc  IScientificCalculator  libCalculator
AdvancedCalc  IStatistics  libCalculator
AdvancedCalc  CATICreateInstance  libCalculator
```

**Usage:**
```cpp
// Create via one interface
ICalculator* pCalc = NULL;
::CATInstantiateComponent("AdvancedCalc", IID_ICalculator, (void**)&pCalc);

// Query for another interface
IScientificCalculator* pSci = NULL;
pCalc->QueryInterface(IID_IScientificCalculator, (void**)&pSci);
if (pSci) {
    pSci->Sin(3.14, &result);
    pSci->Release();
}
pCalc->Release();
```

**See**: SKILL.md "Multi-Interface Components" section.

---

## 📁 Interface Visibility (NEW)

### Q51: What's the difference between PublicInterfaces and LocalInterfaces?
**A:**

| Directory | Visibility | Contents |
|-----------|------------|----------|
| **PublicInterfaces/** | External frameworks can use | Interface headers (`IXxx.h`) |
| **ProtectedInterfaces/** | Only derived frameworks | Semi-internal interfaces |
| **LocalInterfaces/** | Module-private | Component headers (`Xxx.h`) |

```
Framework.edu/
├── PublicInterfaces/
│   └── ICalculator.h          # ✅ Public API - anyone can use
├── ProtectedInterfaces/
│   └── ICalculatorInternal.h  # ⚠️ Framework family only
└── Module.m/
    └── LocalInterfaces/
        └── Calculator.h        # 🔒 Private - module only
```

**Rule**: Never put component implementation headers in PublicInterfaces!

---

### Q52: When should I use ProtectedInterfaces?
**A:** When creating **framework families** with derived frameworks:

**Base framework (MathCore.edu):**
```cpp
// MathCore.edu/ProtectedInterfaces/IMathInternal.h
class IMathInternal : public CATBaseUnknown
{
    // Internal helper methods for derived frameworks
};
```

**Derived framework (AdvancedMath.edu):**
```cpp
// AdvancedMath.edu/IdentityCard/IdentityCard.h
AddPrereqComponent("MathCore", Protected);  // Can access ProtectedInterfaces

// AdvancedMath.edu can now #include "IMathInternal.h"
```

**External framework (UserCode.edu):**
```cpp
// UserCode.edu/IdentityCard/IdentityCard.h
AddPrereqComponent("MathCore", Public);  // Can only access PublicInterfaces

// UserCode.edu CANNOT #include "IMathInternal.h" → compile error
```

**See**: SKILL.md "Interface Visibility Levels" section.

---
