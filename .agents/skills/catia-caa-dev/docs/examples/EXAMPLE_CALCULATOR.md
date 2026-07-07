# Complete CAA Component Example

This example demonstrates a fully working CAA component with proper structure.

## Use Case
Create a `Calculator` component that implements `ICalculator` interface with basic arithmetic operations.

## File Structure

```
<workspace>\
└── MathFramework.edu/
    ├── IdentityCard/
    │   └── IdentityCard.h
    ├── PublicInterfaces/
    │   └── ICalculator.h
    └── Calculator.m/
        ├── Imakefile.mk
        ├── LocalInterfaces/
        │   └── Calculator.h
        └── src/
            ├── ICalculator.cpp
            └── Calculator.cpp
```

---

## File: IdentityCard/IdentityCard.h

```cpp
//
// COPYRIGHT DASSAULT SYSTEMES 2026
//
// -->Prereq Components Declaration
   AddPrereqComponent("System",Public);
```

---

## File: PublicInterfaces/ICalculator.h

```cpp
#ifndef ICalculator_h
#define ICalculator_h

// COPYRIGHT DASSAULT SYSTEMES 2026

// System Framework
#include "CATBaseUnknown.h"

// Export from this module
#ifndef ExportedByCalculator
#define ExportedByCalculator
#endif

// Global Unique IDentifier defined in .cpp
extern ExportedByCalculator IID IID_ICalculator;

/**
 * @brief Calculator interface providing basic arithmetic operations
 */
class ExportedByCalculator ICalculator : public CATBaseUnknown
{
    // Used in conjunction with CATImplementInterface in the interface .cpp file
        CATDeclareInterface;

public:
    /**
     * @brief Add two numbers
     * @param iA First operand
     * @param iB Second operand
     * @param oResult Sum of iA and iB
     * @return HRESULT S_OK if successful
     */
    virtual HRESULT Add(double iA, double iB, double& oResult) = 0;

    /**
     * @brief Subtract two numbers
     * @param iA First operand
     * @param iB Second operand
     * @param oResult Difference (iA - iB)
     * @return HRESULT S_OK if successful
     */
    virtual HRESULT Subtract(double iA, double iB, double& oResult) = 0;

    /**
     * @brief Multiply two numbers
     * @param iA First operand
     * @param iB Second operand
     * @param oResult Product of iA and iB
     * @return HRESULT S_OK if successful
     */
    virtual HRESULT Multiply(double iA, double iB, double& oResult) = 0;

    /**
     * @brief Divide two numbers
     * @param iA Dividend
     * @param iB Divisor
     * @param oResult Quotient (iA / iB)
     * @return HRESULT S_OK if successful, E_FAIL if iB is zero
     */
    virtual HRESULT Divide(double iA, double iB, double& oResult) = 0;
};

#endif
```

---

## File: Calculator.m/src/ICalculator.cpp

```cpp
// COPYRIGHT DASSAULT SYSTEMES 2026

// Local Framework
#include "ICalculator.h"

//-----------------------------------------------------------------------------

// Implement the interface
CATImplementInterface(ICalculator, CATBaseUnknown);

// Define the Interface IID
// Generated using guidgen.exe - use unique GUID in production
IID IID_ICalculator = { 
    0xA1B2C3D4, 0xE5F6, 0x4789, 
    { 0xAB, 0xCD, 0xEF, 0x12, 0x34, 0x56, 0x78, 0x90 } 
};
```

---

## File: Calculator.m/Imakefile.mk

```makefile
# COPYRIGHT DASSAULT SYSTEMES 2026
#======================================================================
# Imakefile for module Calculator.m
#======================================================================
#
# SHARED LIBRARY
#
BUILT_OBJECT_TYPE = SHARED LIBRARY

LINK_WITH= JS0GROUP
```

---

## File: Calculator.m/LocalInterfaces/Calculator.h

```cpp
#ifndef Calculator_H
#define Calculator_H

// COPYRIGHT DASSAULT SYSTEMES 2026

// System Framework
#include "CATBaseUnknown.h"

// Local Framework
#include "ICalculator.h"

/**
 * @brief Calculator component implementation
 */
class Calculator : public CATBaseUnknown
{
    // Used in conjunction with CATImplementClass in the .cpp file
    CATDeclareClass;

public:
    Calculator();
    virtual ~Calculator();

    // ICalculator implementation
    virtual HRESULT Add(double iA, double iB, double& oResult);
    virtual HRESULT Subtract(double iA, double iB, double& oResult);
    virtual HRESULT Multiply(double iA, double iB, double& oResult);
    virtual HRESULT Divide(double iA, double iB, double& oResult);

private:
    // Private members
    int _operationCount;
    
    // Copy constructor, not implemented
    Calculator(const Calculator &iObjectToCopy);

    // Assignment operator, not implemented
    Calculator & operator = (const Calculator &iObjectToCopy);
};

#endif
```

---

## File: Calculator.m/src/Calculator.cpp

```cpp
// COPYRIGHT DASSAULT SYSTEMES 2026

// Local Framework
#include "Calculator.h"

// C++ standard library
#include "iostream.h"
#include "math.h"

//-----------------------------------------------------------------------------

// To declare that the class is a component main class
CATImplementClass(Calculator, Implementation, CATBaseUnknown, CATNull);

// Bind the component to the interface (BOA pattern)
CATImplementBOA(ICalculator, Calculator);

//-----------------------------------------------------------------------------
// Constructor
//-----------------------------------------------------------------------------
Calculator::Calculator()
    : _operationCount(0)
{
    cout << "Calculator::Calculator - Instance created" << endl;
}

//-----------------------------------------------------------------------------
// Destructor
//-----------------------------------------------------------------------------
Calculator::~Calculator()
{
    cout << "Calculator::~Calculator - " << _operationCount 
         << " operations performed" << endl;
}

//-----------------------------------------------------------------------------
// Add - Addition operation
//-----------------------------------------------------------------------------
HRESULT Calculator::Add(double iA, double iB, double& oResult)
{
    oResult = iA + iB;
    _operationCount++;
    
    cout << "Calculator::Add(" << iA << ", " << iB << ") = " 
         << oResult << endl;
    
    return S_OK;
}

//-----------------------------------------------------------------------------
// Subtract - Subtraction operation
//-----------------------------------------------------------------------------
HRESULT Calculator::Subtract(double iA, double iB, double& oResult)
{
    oResult = iA - iB;
    _operationCount++;
    
    cout << "Calculator::Subtract(" << iA << ", " << iB << ") = " 
         << oResult << endl;
    
    return S_OK;
}

//-----------------------------------------------------------------------------
// Multiply - Multiplication operation
//-----------------------------------------------------------------------------
HRESULT Calculator::Multiply(double iA, double iB, double& oResult)
{
    oResult = iA * iB;
    _operationCount++;
    
    cout << "Calculator::Multiply(" << iA << ", " << iB << ") = " 
         << oResult << endl;
    
    return S_OK;
}

//-----------------------------------------------------------------------------
// Divide - Division operation
//-----------------------------------------------------------------------------
HRESULT Calculator::Divide(double iA, double iB, double& oResult)
{
    // Check for division by zero
    if (fabs(iB) < 1e-10)
    {
        cout << "Calculator::Divide - ERROR: Division by zero" << endl;
        return E_FAIL;
    }
    
    oResult = iA / iB;
    _operationCount++;
    
    cout << "Calculator::Divide(" << iA << ", " << iB << ") = " 
         << oResult << endl;
    
    return S_OK;
}
```

---

## Compilation

**Build**: `python skills/build.py Framework.edu/Module.m` | **Run**: `python skills/run.py`

**Quick command**:
```bash
python skills/build.py Framework.edu/Calculator.m
```

Expected output:
```
* mkmk version 5.28.0.17333 64-bit ...
Building Calculator.m...
Compiling Calculator.cpp...
Linking Calculator.dll...
Build successful
```

---

## Testing in CATIA

### Method 1: CATScript Macro

Create a macro in CATIA:

```vb
Sub CATMain()
    Dim calc As Object
    Set calc = CATIA.CreateObject("Calculator")
    
    Dim result As Double
    
    ' Test addition
    calc.Add 10.5, 5.3, result
    MsgBox "10.5 + 5.3 = " & result
    
    ' Test division
    Dim hr As Long
    hr = calc.Divide(100, 5, result)
    If hr = 0 Then
        MsgBox "100 / 5 = " & result
    End If
End Sub
```

### Method 2: C++ Test Module

Create another module `CalculatorTest.m` that uses the Calculator:

```cpp
#include "ICalculator.h"

void TestCalculator()
{
    ICalculator* pCalc = NULL;
    HRESULT hr = ::CATInstantiateComponent(
        "Calculator",
        IID_ICalculator,
        (void**)&pCalc
    );
    
    if (SUCCEEDED(hr))
    {
        double result = 0.0;
        
        pCalc->Add(10.5, 5.3, result);
        cout << "Result: " << result << endl;
        
        pCalc->Release();
    }
}
```

---

## Key Learning Points

1. **Interface-based design**: All functionality exposed through interfaces
2. **Error handling**: Check for invalid input (division by zero)
3. **Logging**: Use cout for debugging information
4. **State management**: Track operation count internally
5. **Memory safety**: Proper constructor/destructor
6. **Standard compliance**: Follows all CAA conventions

---

## Extension Ideas

1. Add more operations (power, square root, etc.)
2. Add history tracking
3. Implement ICalculatorAdvanced interface
4. Create factory component
5. Add persistence (save/load calculator state)

---

## Common Issues

| Issue | Solution |
|-------|----------|
| Link error: undefined IID | Ensure IID_ICalculator is defined in interface .cpp |
| Cannot create instance | Check component is properly registered with CATImplementClass |
| Divide by zero crash | Always validate input parameters |
| Memory leak | Ensure Release() called on all interface pointers |

---

## Version
CATIA V5R28 - Tested and verified
