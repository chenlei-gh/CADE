// COPYRIGHT DASSAULT SYSTEMES 2026
#ifndef {PREFIX}{FEATURE_NAME}_H
#define {PREFIX}{FEATURE_NAME}_H

// System Framework
#include "CATBaseUnknown.h"

// ObjectModelerBase Framework
#include "CATISpecObject.h"

// Feature class declaration
// This class represents a mechanical feature with CATIBuild and CATIReplace capabilities
class {PREFIX}{FEATURE_NAME} : public CATBaseUnknown
{
  // Declares the class as an implementation extension
  CATDeclareClass;

public:
  // Constructor
  {PREFIX}{FEATURE_NAME}();
  
  // Destructor
  virtual ~{PREFIX}{FEATURE_NAME}();

  // CATIBuild interface implementation
  // ====================================
  // Build method - performs the geometric construction
  // Called during Update operation
  virtual HRESULT Build();
  
  // CATIReplace interface implementation
  // =====================================
  // ReplaceAdvise method - handles input replacement
  // Called when an input feature is replaced or modified
  virtual HRESULT ReplaceAdvise(CATISpecObject* iOldInput,
                                CATISpecObject* iNewInput);

private:
  // Copy constructor (not implemented)
  {PREFIX}{FEATURE_NAME}(const {PREFIX}{FEATURE_NAME}& iOneOf);
  
  // Assignment operator (not implemented)
  {PREFIX}{FEATURE_NAME}& operator=(const {PREFIX}{FEATURE_NAME}& iOneOf);

  // Private methods
  // ===============
  
  // Retrieves input specifications from the feature
  HRESULT GetInputSpecs(CATISpecObject*& oInputSpec1,
                        CATISpecObject*& oInputSpec2);
  
  // Performs the geometric build logic
  HRESULT PerformGeometricBuild(CATISpecObject* iInputSpec1,
                                CATISpecObject* iInputSpec2);
  
  // Updates the result geometry
  HRESULT UpdateResult(CATBaseUnknown* iGeometry);
};

#endif // {PREFIX}{FEATURE_NAME}_H
