// COPYRIGHT DASSAULT SYSTEMES 2026
//
// FeatureBuild.cpp
// ⚠️ KNOWN-FABRICATED（2026-07 对 B28 全目录核实）：本模版引用的
// CATIMmiResultFeature.h 不存在；CATIMmiMechanicalFeature 上没有
// GetBodyResult——真实的是 CATIGeometricalElement::GetBodyResult()
// 返回 CATBody_var（MecModInterfaces）。SetResult 不存在。
// 证据与替代方案：knowledge/failure_patterns/fp_template_feature_apis.md
//
// Dedicated file for CATIBuild interface implementation
// This separation allows better code organization for complex build logic

// Local Framework
#include "{PREFIX}{FEATURE_NAME}.h"

// System Framework
#include "CATErrorDef.h"

// ObjectModelerBase Framework
#include "CATISpecObject.h"
#include "CATISpecAttrAccess.h"
#include "CATISpecAttrKey.h"

// MechanicalModeler Framework
// ⚠️ 已删除捏造头文件 CATIMmiResultFeature.h（B28 不存在）
#include "CATIMmiMechanicalFeature.h"
#include "CATIGeometricalElement.h"  // GetBodyResult 真实所在接口

// GeometricObjects Framework
// CATBody_var 由 CATBody.h 引入（_var 类型无独立头文件）
#include "CATBody.h"

// NOTE: This is an alternative implementation file
// If you prefer to keep Build() in the main .cpp file,
// you can delete this file and use the implementation in FeatureClass.cpp

//-----------------------------------------------------------------------------
// Build - Alternative detailed implementation
//-----------------------------------------------------------------------------
// Purpose: Constructs the feature geometry based on inputs and parameters
// Context: Called by Update mechanism when feature needs reconstruction
// Return: S_OK if successful, error code otherwise
//-----------------------------------------------------------------------------
HRESULT {PREFIX}{FEATURE_NAME}::Build()
{
  HRESULT hr = E_FAIL;

  // =========================================================================
  // STEP 1: Get Feature Specification Object
  // =========================================================================
  CATISpecObject* piSpecObject = NULL;
  hr = QueryInterface(IID_CATISpecObject, (void**)&piSpecObject);
  if (FAILED(hr) || piSpecObject == NULL)
  {
    // Cannot proceed without specification object
    return E_FAIL;
  }

  // =========================================================================
  // STEP 2: Get Attribute Access Interface
  // =========================================================================
  CATISpecAttrAccess* piSpecAttrAccess = NULL;
  hr = piSpecObject->QueryInterface(IID_CATISpecAttrAccess,
                                    (void**)&piSpecAttrAccess);
  if (FAILED(hr) || piSpecAttrAccess == NULL)
  {
    piSpecObject->Release();
    return E_FAIL;
  }

  // =========================================================================
  // STEP 3: Retrieve Input Specifications
  // =========================================================================
  CATISpecObject* piInputSpec1 = NULL;
  CATISpecObject* piInputSpec2 = NULL;

  // Get first input (mandatory)
  CATISpecAttrKey* piAttrKey = piSpecAttrAccess->GetAttrKey("InputSpec1");
  if (piAttrKey != NULL)
  {
    piSpecAttrAccess->GetSpecObject(piAttrKey, piInputSpec1);
    piAttrKey->Release();
    piAttrKey = NULL;
  }

  // Get second input (optional)
  piAttrKey = piSpecAttrAccess->GetAttrKey("InputSpec2");
  if (piAttrKey != NULL)
  {
    piSpecAttrAccess->GetSpecObject(piAttrKey, piInputSpec2);
    piAttrKey->Release();
    piAttrKey = NULL;
  }

  // Validate mandatory input
  if (piInputSpec1 == NULL)
  {
    // Clean up and return error
    piSpecAttrAccess->Release();
    piSpecObject->Release();
    return E_FAIL;
  }

  // =========================================================================
  // STEP 4: Retrieve Parameters
  // =========================================================================
  double length = 10.0;  // Default value
  double radius = 5.0;   // Default value
  int option = 0;        // Default value

  // Get length parameter
  piAttrKey = piSpecAttrAccess->GetAttrKey("Length");
  if (piAttrKey != NULL)
  {
    piSpecAttrAccess->GetDouble(piAttrKey, length);
    piAttrKey->Release();
    piAttrKey = NULL;
  }

  // Get radius parameter
  piAttrKey = piSpecAttrAccess->GetAttrKey("Radius");
  if (piAttrKey != NULL)
  {
    piSpecAttrAccess->GetDouble(piAttrKey, radius);
    piAttrKey->Release();
    piAttrKey = NULL;
  }

  // Get option parameter
  piAttrKey = piSpecAttrAccess->GetAttrKey("Option");
  if (piAttrKey != NULL)
  {
    piSpecAttrAccess->GetInteger(piAttrKey, option);
    piAttrKey->Release();
    piAttrKey = NULL;
  }

  // =========================================================================
  // STEP 5: Get Input Geometries
  // =========================================================================
  CATBody* piInputBody1 = NULL;
  CATBody* piInputBody2 = NULL;

  // Get geometry from first input
  // GetBodyResult 在 CATIGeometricalElement 上（返回 CATBody_var），
  // 不在 CATIMmiMechanicalFeature 上。
  CATIGeometricalElement* piGeoElem1 = NULL;
  hr = piInputSpec1->QueryInterface(IID_CATIGeometricalElement,
                                    (void**)&piGeoElem1);
  if (SUCCEEDED(hr) && piGeoElem1 != NULL)
  {
    CATBody_var spBody1 = piGeoElem1->GetBodyResult();
    piInputBody1 = (CATBody*)spBody1;
    piGeoElem1->Release();
    piGeoElem1 = NULL;
  }

  // Get geometry from second input (if exists)
  if (piInputSpec2 != NULL)
  {
    CATIGeometricalElement* piGeoElem2 = NULL;
    hr = piInputSpec2->QueryInterface(IID_CATIGeometricalElement,
                                      (void**)&piGeoElem2);
    if (SUCCEEDED(hr) && piGeoElem2 != NULL)
    {
      CATBody_var spBody2 = piGeoElem2->GetBodyResult();
      piInputBody2 = (CATBody*)spBody2;
      piGeoElem2->Release();
      piGeoElem2 = NULL;
    }
  }

  // =========================================================================
  // STEP 6: Perform Geometric Construction
  // =========================================================================
  CATBody* piResultBody = NULL;

  // TODO: Implement your geometric operations here
  // Examples:
  // - Boolean operations (add, remove, intersect)
  // - Transformations (translate, rotate, scale)
  // - Topological operations (fillet, chamfer, draft)
  // - Surface operations (extrude, revolve, sweep)
  
  // Placeholder for your geometric logic
  if (piInputBody1 != NULL)
  {
    // Example: Create result based on input and parameters
    // piResultBody = PerformYourOperation(piInputBody1, piInputBody2, 
    //                                     length, radius, option);
  }

  // =========================================================================
  // STEP 7: Update Feature Result
  // =========================================================================
  // ⚠️ 原模版的 CATIMmiResultFeature::SetResult 不存在于 B28。
  // 自定义特征结果写入无公开 SetResult API，此处留空待基于
  // CATMecModUseItf 教程重写（见 fp_template_feature_apis.md）。
  if (piResultBody != NULL)
  {
    hr = E_NOTIMPL;  // TODO: rewrite against real result-association API
  }
  else
  {
    hr = E_FAIL;  // No result geometry created
  }

  // =========================================================================
  // STEP 8: Clean Up
  // =========================================================================
  if (piInputSpec1 != NULL)
  {
    piInputSpec1->Release();
    piInputSpec1 = NULL;
  }
  if (piInputSpec2 != NULL)
  {
    piInputSpec2->Release();
    piInputSpec2 = NULL;
  }
  piSpecAttrAccess->Release();
  piSpecAttrAccess = NULL;
  piSpecObject->Release();
  piSpecObject = NULL;

  return hr;
}
