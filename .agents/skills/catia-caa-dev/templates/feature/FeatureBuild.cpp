// COPYRIGHT DASSAULT SYSTEMES 2026
//
// FeatureBuild.cpp
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
#include "CATIMmiMechanicalFeature.h"
#include "CATIMmiResultFeature.h"

// GeometricObjects Framework
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
  CATIMmiMechanicalFeature* piMechFeat1 = NULL;
  hr = piInputSpec1->QueryInterface(IID_CATIMmiMechanicalFeature,
                                    (void**)&piMechFeat1);
  if (SUCCEEDED(hr) && piMechFeat1 != NULL)
  {
    piInputBody1 = piMechFeat1->GetBodyResult();
    piMechFeat1->Release();
    piMechFeat1 = NULL;
  }

  // Get geometry from second input (if exists)
  if (piInputSpec2 != NULL)
  {
    CATIMmiMechanicalFeature* piMechFeat2 = NULL;
    hr = piInputSpec2->QueryInterface(IID_CATIMmiMechanicalFeature,
                                      (void**)&piMechFeat2);
    if (SUCCEEDED(hr) && piMechFeat2 != NULL)
    {
      piInputBody2 = piMechFeat2->GetBodyResult();
      piMechFeat2->Release();
      piMechFeat2 = NULL;
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
  if (piResultBody != NULL)
  {
    CATIMmiResultFeature* piResultFeature = NULL;
    hr = QueryInterface(IID_CATIMmiResultFeature, (void**)&piResultFeature);
    if (SUCCEEDED(hr) && piResultFeature != NULL)
    {
      hr = piResultFeature->SetResult(piResultBody);
      piResultFeature->Release();
      piResultFeature = NULL;
    }
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
