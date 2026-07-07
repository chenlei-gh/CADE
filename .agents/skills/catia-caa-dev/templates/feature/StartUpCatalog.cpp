// COPYRIGHT DASSAULT SYSTEMES 2026
//
// StartUpCatalog.cpp
// Creates and configures Feature StartUp and Catalog

// System Framework
#include "CATUnicodeString.h"
#include "CATErrorDef.h"

// ObjectModelerBase Framework
#include "CATOsmSUHandler.h"
#include "CATISpecObject.h"
#include "CATISpecAttrAccess.h"
#include "CATISpecAttrKey.h"
#include "CATICatalog.h"
#include "CATICatalogChapterFactory.h"
#include "CATICatalogChapter.h"
#include "CATICatalogDescription.h"

// FeatureModeler Framework
#include "CATFeatCont.h"

//=============================================================================
// GLOBAL CONFIGURATION
//=============================================================================
// Catalog and StartUp names - modify as needed
static const CATUnicodeString CATALOG_NAME = "{FRAMEWORK_NAME}";
static const CATUnicodeString STARTUP_NAME = "{STARTUP_NAME}";
static const CATUnicodeString STARTUP_TYPE = "MechanicalFeature";  // or "Feature"

//=============================================================================
// CreateFeatureCatalog
//=============================================================================
// Purpose: Creates a new catalog file (.CATfct) with the feature StartUp
// Context: Called once during framework setup or on-demand
// Parameters:
//   iCatalogStoragePath - Full path where catalog file will be saved
// Return: S_OK if successful, error code otherwise
//
// Usage Example:
//   CATUnicodeString path = "E:\\MyFramework\\CNext\\resources\\graphic\\";
//   HRESULT hr = CreateFeatureCatalog(path);
//=============================================================================
HRESULT CreateFeatureCatalog(const CATUnicodeString& iCatalogStoragePath)
{
  HRESULT hr = E_FAIL;

  // =========================================================================
  // STEP 1: Create the Catalog Document
  // =========================================================================
  CATICatalog* piCatalog = NULL;
  hr = ::<CreateCatalog(&piCatalog);
  if (FAILED(hr) || piCatalog == NULL)
  {
    return E_FAIL;
  }

  // =========================================================================
  // STEP 2: Set Catalog Client ID
  // =========================================================================
  // The client ID identifies your framework - should be unique
  CATUnicodeString clientId = "{FRAMEWORK_NAME}";
  piCatalog->SetClientId(&clientId);

  // =========================================================================
  // STEP 3: Create Chapter Factory
  // =========================================================================
  CATICatalogChapterFactory* piChapterFactory = NULL;
  hr = piCatalog->QueryInterface(IID_CATICatalogChapterFactory,
                                 (void**)&piChapterFactory);
  if (FAILED(hr) || piChapterFactory == NULL)
  {
    piCatalog->Release();
    return E_FAIL;
  }

  // =========================================================================
  // STEP 4: Create a Chapter for Features
  // =========================================================================
  CATICatalogChapter* piChapter = NULL;
  CATUnicodeString chapterName = "Features";
  
  hr = piChapterFactory->CreateChapter(chapterName, &piChapter);
  piChapterFactory->Release();
  piChapterFactory = NULL;
  
  if (FAILED(hr) || piChapter == NULL)
  {
    piCatalog->Release();
    return E_FAIL;
  }

  // =========================================================================
  // STEP 5: Create the Feature StartUp
  // =========================================================================
  CATISpecObject* piStartUp = NULL;
  
  // Create StartUp from a base type
  // Common base types:
  //   - "MechanicalFeature" for solid features
  //   - "GSMGeom" for surfacic features
  //   - "Feature" for generic features
  hr = piChapter->CreateStartUp(STARTUP_NAME,
                                STARTUP_TYPE,
                                &piStartUp);
  if (FAILED(hr) || piStartUp == NULL)
  {
    piChapter->Release();
    piCatalog->Release();
    return E_FAIL;
  }

  // =========================================================================
  // STEP 6: Configure StartUp Attributes
  // =========================================================================
  CATISpecAttrAccess* piAttrAccess = NULL;
  hr = piStartUp->QueryInterface(IID_CATISpecAttrAccess,
                                 (void**)&piAttrAccess);
  if (SUCCEEDED(hr) && piAttrAccess != NULL)
  {
    // ---------------------------------------------------------------------
    // Define Input Specification Attributes
    // ---------------------------------------------------------------------
    // These hold references to other features (inputs to this feature)
    
    // First input (mandatory)
    CATISpecAttrKey* piAttrKey = piAttrAccess->AddAttribute("InputSpec1",
                                                            tk_specobject);
    if (piAttrKey != NULL)
    {
      piAttrKey->Release();
      piAttrKey = NULL;
    }

    // Second input (optional)
    piAttrKey = piAttrAccess->AddAttribute("InputSpec2", tk_specobject);
    if (piAttrKey != NULL)
    {
      piAttrKey->Release();
      piAttrKey = NULL;
    }

    // ---------------------------------------------------------------------
    // Define Parameter Attributes
    // ---------------------------------------------------------------------
    // Length parameter (double)
    piAttrKey = piAttrAccess->AddAttribute("Length", tk_double);
    if (piAttrKey != NULL)
    {
      // Set default value
      piAttrAccess->SetDouble(piAttrKey, 10.0);
      piAttrKey->Release();
      piAttrKey = NULL;
    }

    // Radius parameter (double)
    piAttrKey = piAttrAccess->AddAttribute("Radius", tk_double);
    if (piAttrKey != NULL)
    {
      piAttrAccess->SetDouble(piAttrKey, 5.0);
      piAttrKey->Release();
      piAttrKey = NULL;
    }

    // Option parameter (integer)
    piAttrKey = piAttrAccess->AddAttribute("Option", tk_integer);
    if (piAttrKey != NULL)
    {
      piAttrAccess->SetInteger(piAttrKey, 0);
      piAttrKey->Release();
      piAttrKey = NULL;
    }

    // ---------------------------------------------------------------------
    // Define String Attributes (optional)
    // ---------------------------------------------------------------------
    // Name or description
    piAttrKey = piAttrAccess->AddAttribute("Description", tk_string);
    if (piAttrKey != NULL)
    {
      CATUnicodeString defaultDesc = "";
      piAttrAccess->SetString(piAttrKey, defaultDesc);
      piAttrKey->Release();
      piAttrKey = NULL;
    }

    // ---------------------------------------------------------------------
    // Define List Attributes (optional)
    // ---------------------------------------------------------------------
    // Example: List of input specifications
    /*
    piAttrKey = piAttrAccess->AddAttribute("InputList", tk_list);
    if (piAttrKey != NULL)
    {
      // Configure list element type
      piAttrKey->SetElementType(tk_specobject);
      piAttrKey->Release();
      piAttrKey = NULL;
    }
    */

    piAttrAccess->Release();
    piAttrAccess = NULL;
  }

  // =========================================================================
  // STEP 7: Set StartUp Description (Optional)
  // =========================================================================
  CATICatalogDescription* piDescription = NULL;
  hr = piStartUp->QueryInterface(IID_CATICatalogDescription,
                                 (void**)&piDescription);
  if (SUCCEEDED(hr) && piDescription != NULL)
  {
    CATUnicodeString description = "Custom mechanical feature";
    piDescription->SetDescription(description);
    piDescription->Release();
    piDescription = NULL;
  }

  // =========================================================================
  // STEP 8: Save the Catalog
  // =========================================================================
  // Construct full catalog path
  CATUnicodeString catalogPath = iCatalogStoragePath;
  if (!catalogPath.EndsWith("\\") && !catalogPath.EndsWith("/"))
  {
    catalogPath += "\\";
  }
  catalogPath += CATALOG_NAME;
  catalogPath += ".CATfct";

  hr = piCatalog->SaveAs(&catalogPath);

  // =========================================================================
  // STEP 9: Clean Up
  // =========================================================================
  piStartUp->Release();
  piStartUp = NULL;
  piChapter->Release();
  piChapter = NULL;
  piCatalog->Release();
  piCatalog = NULL;

  return hr;
}

//=============================================================================
// LoadFeatureCatalog
//=============================================================================
// Purpose: Loads an existing catalog and retrieves the StartUp
// Context: Called before instantiating features
// Parameters:
//   iCatalogPath - Full path to the catalog file (.CATfct)
//   oStartUp - Output parameter receiving the StartUp object
// Return: S_OK if successful, error code otherwise
//=============================================================================
HRESULT LoadFeatureCatalog(const CATUnicodeString& iCatalogPath,
                           CATISpecObject*& oStartUp)
{
  oStartUp = NULL;
  HRESULT hr = E_FAIL;

  // =========================================================================
  // STEP 1: Access Catalog
  // =========================================================================
  CATICatalog* piCatalog = NULL;
  hr = ::AccessCatalog(&iCatalogPath, &piCatalog);
  if (FAILED(hr) || piCatalog == NULL)
  {
    return E_FAIL;
  }

  // =========================================================================
  // STEP 2: Get Chapter
  // =========================================================================
  CATICatalogChapter* piChapter = NULL;
  CATUnicodeString chapterName = "Features";
  
  hr = piCatalog->GetChapter(chapterName, &piChapter);
  if (FAILED(hr) || piChapter == NULL)
  {
    piCatalog->Release();
    return E_FAIL;
  }

  // =========================================================================
  // STEP 3: Retrieve StartUp
  // =========================================================================
  hr = piChapter->GetStartUp(STARTUP_NAME, &oStartUp);

  // =========================================================================
  // STEP 4: Clean Up
  // =========================================================================
  piChapter->Release();
  piChapter = NULL;
  piCatalog->Release();
  piCatalog = NULL;

  return hr;
}

//=============================================================================
// CreateFeatureInstance
//=============================================================================
// Purpose: Creates an instance of the feature from the StartUp
// Context: Called when user creates a new feature
// Parameters:
//   iContainer - Feature container where instance will be created
//   iStartUp - The StartUp object
//   oFeatureInstance - Output parameter receiving the new feature instance
// Return: S_OK if successful, error code otherwise
//=============================================================================
HRESULT CreateFeatureInstance(CATFeatCont* iContainer,
                              CATISpecObject* iStartUp,
                              CATISpecObject*& oFeatureInstance)
{
  if (iContainer == NULL || iStartUp == NULL)
  {
    return E_INVALIDARG;
  }

  oFeatureInstance = NULL;
  HRESULT hr = E_FAIL;

  // =========================================================================
  // Instantiate Feature from StartUp
  // =========================================================================
  CATUnicodeString featureName = STARTUP_NAME;
  
  hr = iContainer->InstantiateFeature(iStartUp,
                                      featureName,
                                      &oFeatureInstance);

  // The feature is created but not yet configured
  // The caller should set input specifications and parameters

  return hr;
}

//=============================================================================
// GetStartUpHandler
//=============================================================================
// Purpose: Gets the StartUp handler for accessing catalog at runtime
// Context: Alternative method for catalog access
// Return: StartUp handler or NULL if failed
//=============================================================================
CATOsmSUHandler* GetStartUpHandler()
{
  CATOsmSUHandler* pHandler = NULL;

  // Create handler with catalog name
  CATUnicodeString catalogName = CATALOG_NAME;
  catalogName += ".CATfct";

  pHandler = new CATOsmSUHandler(&catalogName,
                                 &STARTUP_NAME,
                                 "");  // Empty client ID uses default

  return pHandler;
}
