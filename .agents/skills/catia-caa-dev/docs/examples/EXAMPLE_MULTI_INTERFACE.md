# Multi-Interface Component Example

Complete example of a component implementing multiple interfaces.

---

## Use Case

Create an `AdvancedCalculator` component that implements three interfaces:
1. `ICalculator` - Basic arithmetic (Add, Subtract)
2. `IScientificCalculator` - Scientific functions (Sin, Cos, Tan)
3. `IStatistics` - Statistical functions (Mean, StandardDeviation)

---

## File Structure

```
<workspace>\
└── MathFramework.edu/
    ├── IdentityCard/
    │   └── IdentityCard.h
    ├── PublicInterfaces/
    │   ├── ICalculator.h
    │   ├── IScientificCalculator.h
    │   └── IStatistics.h
    └── AdvancedCalculator.m/
        ├── Imakefile.mk
        ├── LocalInterfaces/
        │   └── AdvancedCalculator.h
        └── src/
            ├── ICalculator.cpp
            ├── IScientificCalculator.cpp
            ├── IStatistics.cpp
            └── AdvancedCalculator.cpp
```

---

## File: PublicInterfaces/ICalculator.h

```cpp
#ifndef ICalculator_h
#define ICalculator_h

// COPYRIGHT DASSAULT SYSTEMES 2026

#include "CATBaseUnknown.h"

#ifndef ExportedByAdvancedCalculator
#define ExportedByAdvancedCalculator
#endif

extern ExportedByAdvancedCalculator IID IID_ICalculator;

class ExportedByAdvancedCalculator ICalculator : public CATBaseUnknown
{
    CATDeclareInterface;

public:
    virtual HRESULT Add(double a, double b, double *result) = 0;
    virtual HRESULT Subtract(double a, double b, double *result) = 0;
};

#endif
```

---

## File: PublicInterfaces/IScientificCalculator.h

```cpp
#ifndef IScientificCalculator_h
#define IScientificCalculator_h

// COPYRIGHT DASSAULT SYSTEMES 2026

#include "CATBaseUnknown.h"

#ifndef ExportedByAdvancedCalculator
#define ExportedByAdvancedCalculator
#endif

extern ExportedByAdvancedCalculator IID IID_IScientificCalculator;

class ExportedByAdvancedCalculator IScientificCalculator : public CATBaseUnknown
{
    CATDeclareInterface;

public:
    virtual HRESULT Sin(double angle, double *result) = 0;
    virtual HRESULT Cos(double angle, double *result) = 0;
    virtual HRESULT Tan(double angle, double *result) = 0;
};

#endif
```

---

## File: PublicInterfaces/IStatistics.h

```cpp
#ifndef IStatistics_h
#define IStatistics_h

// COPYRIGHT DASSAULT SYSTEMES 2026

#include "CATBaseUnknown.h"

#ifndef ExportedByAdvancedCalculator
#define ExportedByAdvancedCalculator
#endif

extern ExportedByAdvancedCalculator IID IID_IStatistics;

class ExportedByAdvancedCalculator IStatistics : public CATBaseUnknown
{
    CATDeclareInterface;

public:
    virtual HRESULT Mean(double *values, int count, double *result) = 0;
    virtual HRESULT StandardDeviation(double *values, int count, double *result) = 0;
};

#endif
```

---

## File: src/ICalculator.cpp

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

## File: src/IScientificCalculator.cpp

```cpp
// COPYRIGHT DASSAULT SYSTEMES 2026

#include "IScientificCalculator.h"

IID IID_IScientificCalculator = {
    0x23456789, 0x2345, 0x2345,
    { 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF, 0x01 }
};

CATImplementInterface(IScientificCalculator, CATBaseUnknown);
```

---

## File: src/IStatistics.cpp

```cpp
// COPYRIGHT DASSAULT SYSTEMES 2026

#include "IStatistics.h"

IID IID_IStatistics = {
    0x3456789A, 0x3456, 0x3456,
    { 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0, 0x12 }
};

CATImplementInterface(IStatistics, CATBaseUnknown);
```

---

## File: LocalInterfaces/AdvancedCalculator.h

```cpp
#ifndef AdvancedCalculator_H
#define AdvancedCalculator_H

// COPYRIGHT DASSAULT SYSTEMES 2026

#include "CATBaseUnknown.h"
#include "ICalculator.h"
#include "IScientificCalculator.h"
#include "IStatistics.h"

class AdvancedCalculator : public CATBaseUnknown
{
    CATDeclareClass;

public:
    AdvancedCalculator();
    virtual ~AdvancedCalculator();

    // ICalculator implementation
    virtual HRESULT Add(double a, double b, double *result);
    virtual HRESULT Subtract(double a, double b, double *result);

    // IScientificCalculator implementation
    virtual HRESULT Sin(double angle, double *result);
    virtual HRESULT Cos(double angle, double *result);
    virtual HRESULT Tan(double angle, double *result);

    // IStatistics implementation
    virtual HRESULT Mean(double *values, int count, double *result);
    virtual HRESULT StandardDeviation(double *values, int count, double *result);

private:
    AdvancedCalculator(const AdvancedCalculator &iObjectToCopy);
    AdvancedCalculator & operator = (const AdvancedCalculator &iObjectToCopy);
};

#endif
```

---

## File: src/AdvancedCalculator.cpp

```cpp
// COPYRIGHT DASSAULT SYSTEMES 2026

#include "AdvancedCalculator.h"
#include "iostream.h"
#include "math.h"

//-----------------------------------------------------------------------------
// Component declaration
//-----------------------------------------------------------------------------
CATImplementClass(AdvancedCalculator, Implementation, CATBaseUnknown, CATNull);

//-----------------------------------------------------------------------------
// Bind ALL interfaces
//-----------------------------------------------------------------------------
CATImplementBOA(ICalculator, AdvancedCalculator);
CATImplementBOA(IScientificCalculator, AdvancedCalculator);
CATImplementBOA(IStatistics, AdvancedCalculator);

//-----------------------------------------------------------------------------
// Constructor
//-----------------------------------------------------------------------------
AdvancedCalculator::AdvancedCalculator()
{
    cout << "AdvancedCalculator::AdvancedCalculator" << endl;
}

//-----------------------------------------------------------------------------
// Destructor
//-----------------------------------------------------------------------------
AdvancedCalculator::~AdvancedCalculator()
{
    cout << "AdvancedCalculator::~AdvancedCalculator" << endl;
}

//-----------------------------------------------------------------------------
// ICalculator implementation
//-----------------------------------------------------------------------------
HRESULT AdvancedCalculator::Add(double a, double b, double *result)
{
    if (!result) return E_POINTER;
    
    *result = a + b;
    cout << "Add: " << a << " + " << b << " = " << *result << endl;
    return S_OK;
}

HRESULT AdvancedCalculator::Subtract(double a, double b, double *result)
{
    if (!result) return E_POINTER;
    
    *result = a - b;
    cout << "Subtract: " << a << " - " << b << " = " << *result << endl;
    return S_OK;
}

//-----------------------------------------------------------------------------
// IScientificCalculator implementation
//-----------------------------------------------------------------------------
HRESULT AdvancedCalculator::Sin(double angle, double *result)
{
    if (!result) return E_POINTER;
    
    *result = sin(angle);
    cout << "Sin(" << angle << ") = " << *result << endl;
    return S_OK;
}

HRESULT AdvancedCalculator::Cos(double angle, double *result)
{
    if (!result) return E_POINTER;
    
    *result = cos(angle);
    cout << "Cos(" << angle << ") = " << *result << endl;
    return S_OK;
}

HRESULT AdvancedCalculator::Tan(double angle, double *result)
{
    if (!result) return E_POINTER;
    
    *result = tan(angle);
    cout << "Tan(" << angle << ") = " << *result << endl;
    return S_OK;
}

//-----------------------------------------------------------------------------
// IStatistics implementation
//-----------------------------------------------------------------------------
HRESULT AdvancedCalculator::Mean(double *values, int count, double *result)
{
    if (!values || !result) return E_POINTER;
    if (count <= 0) return E_INVALIDARG;
    
    double sum = 0;
    for (int i = 0; i < count; i++)
    {
        sum += values[i];
    }
    
    *result = sum / count;
    cout << "Mean = " << *result << endl;
    return S_OK;
}

HRESULT AdvancedCalculator::StandardDeviation(double *values, int count, double *result)
{
    if (!values || !result) return E_POINTER;
    if (count <= 0) return E_INVALIDARG;
    
    // Calculate mean
    double mean = 0;
    HRESULT hr = Mean(values, count, &mean);
    if (FAILED(hr)) return hr;
    
    // Calculate variance
    double variance = 0;
    for (int i = 0; i < count; i++)
    {
        double diff = values[i] - mean;
        variance += diff * diff;
    }
    variance /= count;
    
    // Standard deviation is square root of variance
    *result = sqrt(variance);
    cout << "StandardDeviation = " << *result << endl;
    return S_OK;
}
```

---

## File: CNext/code/dictionary/MathFramework.edu.dico

```
AdvancedCalculator  libAdvancedCalculator  AdvancedCalculator
AdvancedCalculator  ICalculator  libAdvancedCalculator
AdvancedCalculator  IScientificCalculator  libAdvancedCalculator
AdvancedCalculator  IStatistics  libAdvancedCalculator
AdvancedCalculator  CATICreateInstance  libAdvancedCalculator
```

**Critical**: All interfaces must be registered!

---

## Usage Example

```cpp
// Example client code using the multi-interface component

#include "ICalculator.h"
#include "IScientificCalculator.h"
#include "IStatistics.h"

void TestAdvancedCalculator()
{
    // Create component via ICalculator interface
    ICalculator* pCalc = NULL;
    HRESULT hr = ::CATInstantiateComponent(
        "AdvancedCalculator",
        IID_ICalculator,
        (void**)&pCalc
    );
    
    if (SUCCEEDED(hr) && pCalc)
    {
        // Use ICalculator methods
        double result = 0;
        pCalc->Add(10.0, 5.0, &result);
        // Output: Add: 10 + 5 = 15
        
        // Query for IScientificCalculator interface
        IScientificCalculator* pSci = NULL;
        hr = pCalc->QueryInterface(IID_IScientificCalculator, (void**)&pSci);
        
        if (SUCCEEDED(hr) && pSci)
        {
            // Use scientific methods
            double sinValue = 0;
            pSci->Sin(3.14159 / 2, &sinValue);
            // Output: Sin(1.5708) = 1
            
            pSci->Release();
            pSci = NULL;
        }
        
        // Query for IStatistics interface
        IStatistics* pStat = NULL;
        hr = pCalc->QueryInterface(IID_IStatistics, (void**)&pStat);
        
        if (SUCCEEDED(hr) && pStat)
        {
            // Use statistics methods
            double values[] = {1.0, 2.0, 3.0, 4.0, 5.0};
            double mean = 0;
            pStat->Mean(values, 5, &mean);
            // Output: Mean = 3
            
            double stddev = 0;
            pStat->StandardDeviation(values, 5, &stddev);
            // Output: StandardDeviation = 1.41421
            
            pStat->Release();
            pStat = NULL;
        }
        
        // Release original interface
        pCalc->Release();
        pCalc = NULL;
    }
}
```

---

## Key Points

### 1. Multiple `CATImplementBOA` Macros
```cpp
CATImplementBOA(ICalculator, AdvancedCalculator);
CATImplementBOA(IScientificCalculator, AdvancedCalculator);
CATImplementBOA(IStatistics, AdvancedCalculator);
```
One macro per interface.

### 2. Dictionary Lists All Interfaces
```
AdvancedCalculator  ICalculator  libAdvancedCalculator
AdvancedCalculator  IScientificCalculator  libAdvancedCalculator
AdvancedCalculator  IStatistics  libAdvancedCalculator
```
All interfaces must be registered for `QueryInterface` to work.

### 3. Implement ALL Interface Methods
Component class must implement every method from every interface.

### 4. QueryInterface Switches Between Interfaces
```cpp
ICalculator* p1 = ...; // Create via ICalculator
IScientificCalculator* p2 = NULL;
p1->QueryInterface(IID_IScientificCalculator, (void**)&p2);
// Now have access to scientific functions
```

### 5. Memory Management
```cpp
// QueryInterface increments refcount
p1->QueryInterface(..., (void**)&p2);  // refcount = 2

// Must release BOTH
p2->Release();  // refcount = 1
p1->Release();  // refcount = 0 → object deleted
```

---

## Compilation

**Build**: `python skills/build.py Framework.edu/Module.m` | **Run**: `python skills/run.py`

**Quick command**:
```bash
python skills/build.py Framework.edu/AdvancedCalculator.m
```

**Output**: `win_b64\code\bin\AdvancedCalculator.m.dll`

---

## Testing

1. Copy DLL to CATIA: `<CATIA_INSTALL>\win_b64\code\bin\`
2. Copy .dico to CATIA: `<CATIA_INSTALL>\win_b64\code\dictionary\`
3. Restart CATIA
4. Test component creation and interface switching

---

## Benefits of Multi-Interface Pattern

| Benefit | Description |
|---------|-------------|
| **Single object** | One component, multiple capabilities |
| **Type safety** | Each interface enforces its contract |
| **Flexibility** | Clients use only interfaces they need |
| **QueryInterface** | Runtime discovery of capabilities |
| **Memory efficient** | Shared data across interfaces |

---

## Common Mistakes

### ❌ Forgot to register interface in dictionary
```
AdvancedCalculator  libAdvancedCalculator  AdvancedCalculator
AdvancedCalculator  ICalculator  libAdvancedCalculator
# Missing: IScientificCalculator, IStatistics
```
**Result**: QueryInterface returns E_NOINTERFACE

### ❌ Forgot CATImplementBOA for one interface
```cpp
CATImplementBOA(ICalculator, AdvancedCalculator);
// Missing: CATImplementBOA(IScientificCalculator, ...)
```
**Result**: Compile error (unimplemented methods)

### ❌ Forgot to release after QueryInterface
```cpp
p1->QueryInterface(..., (void**)&p2);
p2->DoWork();
// Forgot p2->Release() → MEMORY LEAK!
```

---

**Version**: 1.0  
**Created**: 2026-07-04  
**Complexity**: Intermediate  
**Build Time**: 3-5 minutes
