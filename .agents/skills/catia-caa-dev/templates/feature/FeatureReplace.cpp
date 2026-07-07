// COPYRIGHT DASSAULT SYSTEMES 2026
//
// FeatureReplace.cpp
// Dedicated file for CATIReplace interface implementation
// Handles input replacement scenarios

// Local Framework
#include "{PREFIX}{FEATURE_NAME}.h"

// System Framework
#include "CATErrorDef.h"

// ObjectModelerBase Framework
#include "CATISpecObject.h"
#include "CATISpecAttrAccess.h"
#include "CATISpecAttrKey.h"

// NOTE: This is an alternative implementation file
// If you prefer to keep ReplaceAdvise() in the main .cpp file,
// you can delete this file and use the implementation in FeatureClass.cpp

//-----------------------------------------------------------------------------
// ReplaceAdvise - Alternative detailed implementation
//-----------------------------------------------------------------------------
// Purpose: Manages input replacement when upstream features change
// Context: Called by Replace mechanism when an input is being replaced
// Parameters:
//   iOldInput - The input specification being replaced
//   iNewInput - The new input specification to use
// Return: S_OK if replacement successful, error code otherwise
//-----------------------------------------------------------------------------
HRESULT {PREFIX}{FEATURE_NAME}::ReplaceAdvise(CATISpecObject* iOldInput,
                                               CATISpecObject* iNewInput)
{
  // =========================================================================
  // STEP 1: Validate Input Parameters
  // =========================================================================
  if (iOldInput == NULL || iNewInput == NULL)
  {
    return E_INVALIDARG;
  }

  HRESULT hr = S_OK;

  // =========================================================================
  // STEP 2: Get Feature Specification Object
  // =========================================================================
  CATISpecObject* piSpecObject = NULL;
  hr = QueryInterface(IID_CATISpecObject, (void**)&piSpecObject);
  if (FAILED(hr) || piSpecObject == NULL)
  {
    return E_FAIL;
  }

  // =========================================================================
  // STEP 3: Get Attribute Access Interface
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
  // STEP 4: Check and Replace Input Attributes
  // =========================================================================
  HRESULT hrReplace = S_OK;
  int replacementCount = 0;

  // -------------------------------------------------------------------------
  // Check InputSpec1
  // -------------------------------------------------------------------------
  CATISpecAttrKey* piAttrKey = piSpecAttrAccess->GetAttrKey("InputSpec1");
  if (piAttrKey != NULL)
  {
    CATISpecObject* piCurrentInput = NULL;
    hr = piSpecAttrAccess->GetSpecObject(piAttrKey, piCurrentInput);
    
    if (SUCCEEDED(hr) && piCurrentInput != NULL)
    {
      // Check if this attribute points to the old input
      if (piCurrentInput == iOldInput)
      {
        // Replace with new input
        hr = piSpecAttrAccess->SetSpecObject(piAttrKey, iNewInput);
        if (SUCCEEDED(hr))
        {
          replacementCount++;
        }
        else
        {
          hrReplace = hr;  // Store error for later return
        }
      }
      piCurrentInput->Release();
      piCurrentInput = NULL;
    }
    piAttrKey->Release();
    piAttrKey = NULL;
  }

  // -------------------------------------------------------------------------
  // Check InputSpec2
  // -------------------------------------------------------------------------
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
        if (SUCCEEDED(hr))
        {
          replacementCount++;
        }
        else
        {
          hrReplace = hr;
        }
      }
      piCurrentInput->Release();
      piCurrentInput = NULL;
    }
    piAttrKey->Release();
    piAttrKey = NULL;
  }

  // -------------------------------------------------------------------------
  // Check additional input attributes (if any)
  // Add similar blocks for other input attributes like:
  // - InputSpec3, InputSpec4, etc.
  // - InputList (if using list attributes)
  // -------------------------------------------------------------------------

  // =========================================================================
  // STEP 5: Handle Replacement Results
  // =========================================================================
  if (replacementCount == 0)
  {
    // Old input was not found in any attribute
    // This might be normal if the input is not directly referenced
    hrReplace = S_FALSE;
  }
  else if (FAILED(hrReplace))
  {
    // At least one replacement failed
    // Return the error
  }
  else
  {
    // All replacements successful
    hrReplace = S_OK;
  }

  // =========================================================================
  // STEP 6: Optional - Perform Additional Actions
  // =========================================================================
  // You can add custom logic here if needed:
  // - Validate that the new input is compatible
  // - Update derived parameters based on new input
  // - Trigger a rebuild if necessary
  
  // Example: Check if new input is compatible
  /*
  if (SUCCEEDED(hrReplace) && iNewInput != NULL)
  {
    // Validate new input type or properties
    CATISpecObject* piNewSpec = iNewInput;
    // ... validation logic ...
  }
  */

  // =========================================================================
  // STEP 7: Clean Up
  // =========================================================================
  piSpecAttrAccess->Release();
  piSpecAttrAccess = NULL;
  piSpecObject->Release();
  piSpecObject = NULL;

  return hrReplace;
}

//-----------------------------------------------------------------------------
// Helper function: ValidateInputCompatibility (Optional)
//-----------------------------------------------------------------------------
// Purpose: Validates that a new input is compatible with feature requirements
// This can be called from ReplaceAdvise to ensure input validity
//-----------------------------------------------------------------------------
/*
HRESULT {PREFIX}{FEATURE_NAME}::ValidateInputCompatibility(CATISpecObject* iInput)
{
  if (iInput == NULL)
  {
    return E_INVALIDARG;
  }

  HRESULT hr = S_OK;

  // Example validation: Check if input is a specific feature type
  // CATUnicodeString inputType;
  // hr = GetFeatureType(iInput, inputType);
  // if (FAILED(hr) || inputType != "ExpectedType")
  // {
  //   return E_FAIL;
  // }

  // Example validation: Check if input has required geometry
  // CATIMmiMechanicalFeature* piMechFeat = NULL;
  // hr = iInput->QueryInterface(IID_CATIMmiMechanicalFeature,
  //                             (void**)&piMechFeat);
  // if (SUCCEEDED(hr) && piMechFeat != NULL)
  // {
  //   CATBody* piBody = piMechFeat->GetBodyResult();
  //   if (piBody == NULL)
  //   {
  //     hr = E_FAIL;  // Input has no geometry
  //   }
  //   piMechFeat->Release();
  // }

  return hr;
}
*/
