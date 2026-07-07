# CATIA CGM (Component Geometric Modeler) Reference

> Quick reference for geometry operations in CAA development

**Purpose**: Code snippets for CGM operations used in Commands, Features, and Dialogs  
**Not a standalone component**: CGM is used within your Commands/Features, not as separate modules

---

## 📋 CGM Architecture Overview

### Hierarchy
```
CATGeoFactory (Container)
└── CATBody (Topological body)
    ├── CATDomain (Group of cells)
    │   ├── CATFace (2D surface)
    │   ├── CATEdge (1D curve)
    │   └── CATVertex (0D point)
    └── CATGeometry (Underlying geometry)
        ├── CATSurface
        ├── CATCurve
        └── CATPoint
```

### Key Concepts
- **CATGeoFactory**: Container for all geometric objects
- **CATBody**: Topological body (solid, surface, wireframe)
- **CATFace**: Bounded surface (trimmed)
- **CATEdge**: Bounded curve
- **CATVertex**: Point on topology
- **CATGeometry**: Infinite geometric definition

---

## 🔍 Body Traversal

### Get All Faces
```cpp
#include "CATBody.h"
#include "CATFace.h"
#include "CATListPV.h"

void GetAllFaces(CATBody* iBody, CATListPV& oFaces)
{
    if (!iBody) return;
    
    // Create cell iterator
    CATBodyRequest request(iBody);
    
    // Iterate through faces
    for (request.InitCell(2); !request.IsExhausted(); request.NextCell())
    {
        CATFace* pFace = (CATFace*)request.GetCell();
        if (pFace) {
            oFaces.Append(pFace);
        }
    }
}
```

**Parameters**:
- `InitCell(0)` - Vertices
- `InitCell(1)` - Edges
- `InitCell(2)` - Faces
- `InitCell(3)` - Volumes

---

### Get All Edges
```cpp
#include "CATEdge.h"

void GetAllEdges(CATBody* iBody, CATListPV& oEdges)
{
    if (!iBody) return;
    
    CATBodyRequest request(iBody);
    
    for (request.InitCell(1); !request.IsExhausted(); request.NextCell())
    {
        CATEdge* pEdge = (CATEdge*)request.GetCell();
        if (pEdge) {
            oEdges.Append(pEdge);
        }
    }
}
```

---

### Get Face Edges
```cpp
#include "CATFace.h"
#include "CATLoop.h"

void GetFaceEdges(CATFace* iFace, CATListPV& oEdges)
{
    if (!iFace) return;
    
    // Get loops of the face
    CATLISTP(CATLoop) loops;
    iFace->GetLoops(loops);
    
    // Iterate through loops
    for (int i = 1; i <= loops.Size(); i++)
    {
        CATLoop* pLoop = loops[i];
        
        // Get edges in loop
        CATLISTP(CATEdge) loopEdges;
        pLoop->GetEdges(loopEdges);
        
        for (int j = 1; j <= loopEdges.Size(); j++)
        {
            oEdges.Append(loopEdges[j]);
        }
    }
}
```

---

### Get Vertex Point
```cpp
#include "CATVertex.h"
#include "CATMathPoint.h"

void GetVertexPoint(CATVertex* iVertex, CATMathPoint& oPoint)
{
    if (!iVertex) return;
    
    CATPoint* pPoint = iVertex->GetPoint();
    if (pPoint) {
        pPoint->GetCoord(oPoint);
    }
}
```

---

## 📏 Measurement Operations

### Edge Length
```cpp
#include "CATEdge.h"
#include "CATICGMTopoCurve.h"

double ComputeEdgeLength(CATEdge* iEdge)
{
    if (!iEdge) return 0.0;
    
    CATICGMTopoCurve* pTopoCurve = NULL;
    HRESULT hr = iEdge->QueryInterface(IID_CATICGMTopoCurve, (void**)&pTopoCurve);
    
    if (SUCCEEDED(hr) && pTopoCurve)
    {
        double length = pTopoCurve->GetLength();
        pTopoCurve->Release();
        return length;
    }
    
    return 0.0;
}
```

---

### Face Area
```cpp
#include "CATFace.h"
#include "CATICGMTopoSurface.h"

double ComputeFaceArea(CATFace* iFace)
{
    if (!iFace) return 0.0;
    
    CATICGMTopoSurface* pTopoSurface = NULL;
    HRESULT hr = iFace->QueryInterface(IID_CATICGMTopoSurface, (void**)&pTopoSurface);
    
    if (SUCCEEDED(hr) && pTopoSurface)
    {
        double area = pTopoSurface->GetArea();
        pTopoSurface->Release();
        return area;
    }
    
    return 0.0;
}
```

---

### Distance Between Points
```cpp
#include "CATMathPoint.h"

double ComputeDistance(const CATMathPoint& iPoint1, const CATMathPoint& iPoint2)
{
    CATMathVector vector(iPoint1, iPoint2);
    return vector.Norm();
}
```

---

### Body Volume
```cpp
#include "CATBody.h"
#include "CATMassProperties1D.h"

double ComputeBodyVolume(CATBody* iBody)
{
    if (!iBody) return 0.0;
    
    // Create mass properties operator
    CATMassProperties1D* pMassProp = new CATMassProperties1D(iBody);
    
    if (pMassProp)
    {
        double volume = pMassProp->GetVolume();
        delete pMassProp;
        return volume;
    }
    
    return 0.0;
}
```

---

## 🛠️ Geometry Creation

### Create Point
```cpp
#include "CATGeoFactory.h"
#include "CATPoint.h"
#include "CATMathPoint.h"

CATPoint* CreatePoint(CATGeoFactory* iFactory, const CATMathPoint& iCoordinates)
{
    if (!iFactory) return NULL;
    
    CATPoint* pPoint = iFactory->CreatePoint(iCoordinates);
    return pPoint;
}
```

---

### Create Line
```cpp
#include "CATLine.h"
#include "CATMathDirection.h"

CATLine* CreateLine(CATGeoFactory* iFactory, 
                    const CATMathPoint& iOrigin,
                    const CATMathDirection& iDirection)
{
    if (!iFactory) return NULL;
    
    CATLine* pLine = iFactory->CreateLine(iOrigin, iDirection);
    return pLine;
}
```

---

### Create Line from Two Points
```cpp
CATLine* CreateLine(CATGeoFactory* iFactory,
                    const CATMathPoint& iStart,
                    const CATMathPoint& iEnd)
{
    if (!iFactory) return NULL;
    
    CATMathVector direction(iStart, iEnd);
    CATMathDirection dir(direction);
    
    CATLine* pLine = iFactory->CreateLine(iStart, dir);
    return pLine;
}
```

---

## 🔨 Common Patterns in Commands

### Pattern 1: Get Selected Body
```cpp
// In Command action method
CATPathElement* pPath = _pSelectionAgent->GetValue();
if (!pPath) return FALSE;

CATBody* pBody = NULL;
HRESULT hr = pPath->FindElement(IID_CATBody, (void**)&pBody);

if (SUCCEEDED(hr) && pBody)
{
    // Use body
    double volume = ComputeBodyVolume(pBody);
    cout << "Volume: " << volume << endl;
}
```

---

### Pattern 2: Iterate and Measure
```cpp
// Get all edges and compute total length
CATBody* pBody = GetSelectedBody();

CATListPV edges;
GetAllEdges(pBody, edges);

double totalLength = 0.0;
for (int i = 1; i <= edges.Size(); i++)
{
    CATEdge* pEdge = (CATEdge*)edges[i];
    totalLength += ComputeEdgeLength(pEdge);
}

cout << "Total edge length: " << totalLength << endl;
```

---

### Pattern 3: Find Specific Faces
```cpp
// Find all planar faces
CATListPV faces;
GetAllFaces(pBody, faces);

CATListPV planarFaces;
for (int i = 1; i <= faces.Size(); i++)
{
    CATFace* pFace = (CATFace*)faces[i];
    CATSurface* pSurface = pFace->GetSurface();
    
    if (pSurface && pSurface->IsATypeOf(CATPlaneType))
    {
        planarFaces.Append(pFace);
    }
}
```

---

## 🎯 Common Patterns in Features

### Pattern 1: Build Result Body
```cpp
// In CATIBuild::Build() method
HRESULT MyFeature::Build()
{
    // Get inputs
    CATBody* pInputBody = GetInputBody();
    if (!pInputBody) return E_FAIL;
    
    // Create result (example: offset)
    CATGeoFactory* pFactory = GetFactory();
    CATBody* pResult = CreateOffsetBody(pInputBody, 10.0, pFactory);
    
    if (!pResult) return E_FAIL;
    
    // Set result
    SetResult(pResult);
    
    return S_OK;
}
```

---

### Pattern 2: Update on Input Change
```cpp
// In CATIReplace::ReplaceAdvise() method
HRESULT MyFeature::ReplaceAdvise(CATBody* iOldBody, CATBody* iNewBody)
{
    if (!iNewBody) return E_FAIL;
    
    // Check if new body is valid
    double volume = ComputeBodyVolume(iNewBody);
    if (volume <= 0.0) {
        return E_FAIL; // Reject invalid input
    }
    
    // Accept replacement
    return S_OK;
}
```

---

## 📚 Required Includes

### Essential Headers
```cpp
// Topology
#include "CATBody.h"
#include "CATFace.h"
#include "CATEdge.h"
#include "CATVertex.h"
#include "CATLoop.h"

// Geometry
#include "CATPoint.h"
#include "CATLine.h"
#include "CATSurface.h"
#include "CATCurve.h"

// Factory
#include "CATGeoFactory.h"

// Math
#include "CATMathPoint.h"
#include "CATMathVector.h"
#include "CATMathDirection.h"

// Measurement
#include "CATICGMTopoCurve.h"
#include "CATICGMTopoSurface.h"
#include "CATMassProperties1D.h"

// Traversal
#include "CATBodyRequest.h"

// Lists
#include "CATListPV.h"
#include "CATLISTP.h"
```

---

## 🔧 Required Frameworks

### Imakefile.mk
```makefile
LINK_WITH=JS0GROUP
LINK_WITH=$(LINK_WITH) GeometricObjects
LINK_WITH=$(LINK_WITH) Mathematics
LINK_WITH=$(LINK_WITH) NewTopologicalObjects
LINK_WITH=$(LINK_WITH) CATGMModelInterfaces
```

### IdentityCard.h
```cpp
AddPrereqComponent("GeometricObjects", Public);
AddPrereqComponent("Mathematics", Public);
AddPrereqComponent("NewTopologicalObjects", Public);
AddPrereqComponent("CATGMModelInterfaces", Public);
```

---

## ⚠️ Common Mistakes

### ❌ Not checking NULL pointers
```cpp
CATBody* pBody = GetBody();
CATFace* pFace = pBody->GetFace(0); // CRASH if pBody is NULL!
```

**✅ Always check:**
```cpp
CATBody* pBody = GetBody();
if (pBody) {
    CATFace* pFace = pBody->GetFace(0);
    if (pFace) {
        // Use face
    }
}
```

---

### ❌ Forgetting Release after QueryInterface
```cpp
CATICGMTopoCurve* pCurve = NULL;
iEdge->QueryInterface(IID_CATICGMTopoCurve, (void**)&pCurve);
// Missing Release! Memory leak
```

**✅ Always release:**
```cpp
CATICGMTopoCurve* pCurve = NULL;
if (SUCCEEDED(iEdge->QueryInterface(IID_CATICGMTopoCurve, (void**)&pCurve)))
{
    double length = pCurve->GetLength();
    pCurve->Release(); // MUST call this
}
```

---

### ❌ Wrong dimension in InitCell
```cpp
// Want edges, but using wrong dimension
request.InitCell(2); // This gets FACES, not edges!
```

**✅ Use correct dimension:**
```cpp
request.InitCell(1); // Edges (1D)
```

---

## 🔗 Integration Examples

### In Command
See **EXAMPLE_COMMAND.md** section "Geometry Operations"

### In Feature
See **EXAMPLE_FEATURE.md** section "Build Method with CGM"

### In Dialog
Display geometry properties in dialog fields:
```cpp
void MyDialog::UpdateGeometryInfo()
{
    CATBody* pBody = GetSelectedBody();
    if (!pBody) return;
    
    // Compute properties
    double volume = ComputeBodyVolume(pBody);
    int faceCount = CountFaces(pBody);
    
    // Update dialog
    _pVolumeEditor->SetText(CATUnicodeString(volume));
    _pFaceCountLabel->SetTitle(CATUnicodeString(faceCount));
}
```

---

## 📖 Official Documentation

**Always refer to CAA official docs first (Rule 0):**
```
<CATIA_INSTALL>/CAADoc/Doc/online/
├── CAACgmTechArticles/    - CGM technical articles
├── CAACgmUseCases/        - CGM use cases
└── CAACgmQuickRef/        - CGM API reference
```

**Key Topics:**
- Topological Modeler
- Geometric Modeler
- Body Operations
- Measurement APIs

---

## ✅ Best Practices

1. **Always check NULL** before accessing pointers
2. **Release interfaces** after QueryInterface
3. **Use CATBodyRequest** for efficient traversal
4. **Get CATGeoFactory** from document, not create new one
5. **Clean up temporary bodies** after use
6. **Validate inputs** before operations
7. **Handle errors** gracefully

---

**This is a reference document, not a template. Use these code snippets in your Commands, Features, and Dialogs as needed.**
