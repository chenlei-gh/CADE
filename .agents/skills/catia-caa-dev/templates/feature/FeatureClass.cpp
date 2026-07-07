// COPYRIGHT DASSAULT SYSTEMES 2026

// Local Framework
#include "{PREFIX}{FEATURE_NAME}.h"

// System Framework
#include "CATErrorDef.h"

// ObjectModelerBase Framework
#include "CATISpecObject.h"
#include "CATISpecAttrAccess.h"
#include "CATISpecAttrKey.h"

// MechanicalModeler Framework
#include "CATMmrInterfaces.h"
#include "CATIMmiMechanicalFeature.h"
#include "CATIMmiResultFeature.h"

// Include TIE for interface implementation
#include "TIE_CATIBuild.h"
TIE_CATIBuild({PREFIX}{FEATURE_NAME});

#include "TIE_CATIReplace.h"
TIE_CATIReplace({PREFIX}{FEATURE_NAME});

// Declares the class implementation
CATImplementClass({PREFIX}{FEATURE_NAME},
                  DataExtension,
                  CATBaseUnknown,
                  {STARTUP_NAME});

// Constructor
{PREFIX}{FEATURE_NAME}::{PREFIX}{FEATURE_NAME}()
{
  // No specific initialization required
}

// Destructor
{PREFIX}{FEATURE_NAME}::~{PREFIX}{FEATURE_NAME}()
{
  // No specific cleanup required
}

//-----------------------------------------------------------------------------
// Build
//-----------------------------------------------------------------------------
// Purpose: Performs the geometric construction of the feature
// Called during Update operation
//-----------------------------------------------------------------------------
HRESULT {PREFIX}{FEATURE_NAME}::Build()
{
  HRESULT hr = E_FAIL;

  // Step 1: Get the feature's specification object
  CATISpecObject* piSpecObject = NULL;
  hr = QueryInterface(IID_CATISpecObject, (void**)&piSpecObject);
  if (FAILED(hr) || piSpecObject == NULL)
  {
    return E_FAIL;
  }

  // Step 2: Retrieve input specifications
  CATISpecObject* piInputSpec1 = NULL;
  CATISpecObject* piInputSpec2 = NULL;
  hr = GetInputSpecs(piInputSpec1, piInputSpec2);
  if (FAILED(hr))
  {
    piSpecObject->Release();
    piSpecObject = NULL;
    return hr;
  }

  // Step 3: Perform geometric build
  hr = PerformGeometricBuild(piInputSpec1, piInputSpec2);

  // Step 4: Clean up
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
  piSpecObject->Release();
  piSpecObject = NULL;

  return hr;
}

//-----------------------------------------------------------------------------
// ReplaceAdvise
//-----------------------------------------------------------------------------
// Purpose: Handles replacement of input features
// Called when an input is replaced or modified
//-----------------------------------------------------------------------------
HRESULT {PREFIX}{FEATURE_NAME}::ReplaceAdvise(CATISpecObject* iOldInput,
                                               CATISpecObject* iNewInput)
{
  if (iOldInput == NULL || iNewInput == NULL)
  {
    return E_INVALIDARG;
  }

  HRESULT hr = S_OK;

  // Get the feature's specification object
  CATISpecObject* piSpecObject = NULL;
  hr = QueryInterface(IID_CATISpecObject, (void**)&piSpecObject);
  if (FAILED(hr) || piSpecObject == NULL)
  {
    return E_FAIL;
  }

  // Get attribute access interface
  CATISpecAttrAccess* piSpecAttrAccess = NULL;
  hr = piSpecObject->QueryInterface(IID_CATISpecAttrAccess,
                                    (void**)&piSpecAttrAccess);
  if (SUCCEEDED(hr) && piSpecAttrAccess != NULL)
  {
    // Get attribute key for input specifications
    CATISpecAttrKey* piAttrKey = piSpecAttrAccess->GetAttrKey("InputSpec1");
    if (piAttrKey != NULL)
    {
      // Get current value
      CATISpecObject* piCurrentInput = NULL;
      hr = piSpecAttrAccess->GetSpecObject(piAttrKey, piCurrentInput);
      
      if (SUCCEEDED(hr) && piCurrentInput != NULL)
      {
        // Check if this is the input being replaced
        if (piCurrentInput == iOldInput)
        {
          // Replace with new input
          hr = piSpecAttrAccess->SetSpecObject(piAttrKey, iNewInput);
        }
        piCurrentInput->Release();
        piCurrentInput = NULL;
      }
      piAttrKey->Release();
      piAttrKey = NULL;
    }

    // Check second input if exists
    piAttrKey = piSpecAttrAccess->GetAttrKey("InputSpec2");
    if (piAttrKey != NULL)
    {
      CATISpecObject* piCurrentInput = NULL;
      hr = piSpecAttrAccess->GetSpecObject(piAttrKey, piCurrentInput);
      
      if (SUCCEEDED(hr) && piCurrentInput != NULL)
      {
        if (piCurrentInput == iOldInput)
        {
          hr = piSpecAttrAccess->SetSpecObject(piAttrKey, iNewInput);
        }
        piCurrentInput->Release();
        piCurrentInput = NULL;
      }
      piAttrKey->Release();
      piAttrKey = NULL;
    }

    piSpecAttrAccess->Release();
    piSpecAttrAccess = NULL;
  }

  piSpecObject->Release();
  piSpecObject = NULL;

  return hr;
}

//-----------------------------------------------------------------------------
// GetInputSpecs (Private)
//-----------------------------------------------------------------------------
// Purpose: Retrieves input specifications from feature attributes
//-----------------------------------------------------------------------------
HRESULT {PREFIX}{FEATURE_NAME}::GetInputSpecs(CATISpecObject*& oInputSpec1,
                                               CATISpecObject*& oInputSpec2)
{
  oInputSpec1 = NULL;
  oInputSpec2 = NULL;

  HRESULT hr = E_FAIL;

  // Get the feature's specification object
  CATISpecObject* piSpecObject = NULL;
  hr = QueryInterface(IID_CATISpecObject, (void**)&piSpecObject);
  if (FAILED(hr) || piSpecObject == NULL)
  {
    return E_FAIL;
  }

  // Get attribute access
  CATISpecAttrAccess* piSpecAttrAccess = NULL;
  hr = piSpecObject->QueryInterface(IID_CATISpecAttrAccess,
                                    (void**)&piSpecAttrAccess);
  if (SUCCEEDED(hr) && piSpecAttrAccess != NULL)
  {
    // Get first input
    CATISpecAttrKey* piAttrKey1 = piSpecAttrAccess->GetAttrKey("InputSpec1");
    if (piAttrKey1 != NULL)
    {
      piSpecAttrAccess->GetSpecObject(piAttrKey1, oInputSpec1);
      piAttrKey1->Release();
      piAttrKey1 = NULL;
    }

    // Get second input
    CATISpecAttrKey* piAttrKey2 = piSpecAttrAccess->GetAttrKey("InputSpec2");
    if (piAttrKey2 != NULL)
    {
      piSpecAttrAccess->GetSpecObject(piAttrKey2, oInputSpec2);
      piAttrKey2->Release();
      piAttrKey2 = NULL;
    }

    piSpecAttrAccess->Release();
    piSpecAttrAccess = NULL;
  }

  piSpecObject->Release();
  piSpecObject = NULL;

  // At least one input should be retrieved
  if (oInputSpec1 != NULL)
  {
    hr = S_OK;
  }

  return hr;
}

//-----------------------------------------------------------------------------
// PerformGeometricBuild (Private)
//-----------------------------------------------------------------------------
// Purpose: Performs the actual geometric construction
//-----------------------------------------------------------------------------
HRESULT {PREFIX}{FEATURE_NAME}::PerformGeometricBuild(CATISpecObject* iInputSpec1,
                                                       CATISpecObject* iInputSpec2)
{
  if (iInputSpec1 == NULL)
  {
    return E_INVALIDARG;
  }

  HRESULT hr = E_FAIL;

  // TODO: Implement your geometric build logic here
  // Example:
  // 1. Get geometries from input specifications
  // 2. Perform geometric operations
  // 3. Create result geometry
  // 4. Update the feature's result

  // Placeholder for geometric operations
  CATBaseUnknown* piResultGeometry = NULL;
  
  // ... Your geometric construction code here ...

  // Update the result
  if (piResultGeometry != NULL)
  {
    hr = UpdateResult(piResultGeometry);
    piResultGeometry->Release();
    piResultGeometry = NULL;
  }

  return hr;
}

//-----------------------------------------------------------------------------
// UpdateResult (Private)
//-----------------------------------------------------------------------------
// Purpose: Updates the feature's result geometry
//-----------------------------------------------------------------------------
HRESULT {PREFIX}{FEATURE_NAME}::UpdateResult(CATBaseUnknown* iGeometry)
{
  if (iGeometry == NULL)
  {
    return E_INVALIDARG;
  }

  HRESULT hr = E_FAIL;

  // Get result feature interface
  CATIMmiResultFeature* piResultFeature = NULL;
  hr = QueryInterface(IID_CATIMmiResultFeature, (void**)&piResultFeature);
  if (SUCCEEDED(hr) && piResultFeature != NULL)
  {
    // Set the result geometry
    hr = piResultFeature->SetResult(iGeometry);
    piResultFeature->Release();
    piResultFeature = NULL;
  }

  return hr;
}
