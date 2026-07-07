// COPYRIGHT DASSAULT SYSTEMES 2026
#ifndef {PREFIX}{FEATURE_NAME}_IdentityCard_H
#define {PREFIX}{FEATURE_NAME}_IdentityCard_H

//=============================================================================
// FRAMEWORK IDENTITY CARD
//=============================================================================
// This file declares all interface implementations for the feature
// It serves as a central dependency declaration for the Dictionary

// System Framework
#include "CATBaseUnknown.h"

// ObjectModelerBase Framework - Core interfaces
#include "CATISpecObject.h"
#include "CATIFmFeatureBehaviorCustomization.h"

// Feature Modeler - Build and Update
#include "CATIBuild.h"
#include "CATIReplace.h"

// MechanicalModeler Framework - Mechanical feature interfaces
#include "CATIMmiMechanicalFeature.h"
#include "CATIMmiResultFeature.h"
#include "CATIMmiUseMechFeat.h"

// Feature Visualization (optional)
#include "CATI3DGeoVisu.h"
#include "CATIVisProperties.h"

//=============================================================================
// INTERFACE IMPLEMENTATION DECLARATIONS
//=============================================================================

// Forward declare the implementation class
class {PREFIX}{FEATURE_NAME};

//-----------------------------------------------------------------------------
// CATIBuild Interface
//-----------------------------------------------------------------------------
// Mandatory: Defines how the feature builds its geometry
// Method: Build()
//
// Include this line in your Dictionary file:
// {PREFIX}{FEATURE_NAME}  CATIBuild  lib{FRAMEWORK_NAME}
//-----------------------------------------------------------------------------

//-----------------------------------------------------------------------------
// CATIReplace Interface
//-----------------------------------------------------------------------------
// Mandatory: Handles input replacement scenarios
// Method: ReplaceAdvise(CATISpecObject* iOldInput, CATISpecObject* iNewInput)
//
// Include this line in your Dictionary file:
// {PREFIX}{FEATURE_NAME}  CATIReplace  lib{FRAMEWORK_NAME}
//-----------------------------------------------------------------------------

//-----------------------------------------------------------------------------
// CATIMmiMechanicalFeature Interface (Optional)
//-----------------------------------------------------------------------------
// Provides mechanical feature behavior
// Automatically inherited if StartUp derives from MechanicalFeature
//
// Include this line in your Dictionary file if implementing:
// {PREFIX}{FEATURE_NAME}  CATIMmiMechanicalFeature  lib{FRAMEWORK_NAME}
//-----------------------------------------------------------------------------

//-----------------------------------------------------------------------------
// CATIMmiResultFeature Interface (Optional)
//-----------------------------------------------------------------------------
// Manages the feature's result geometry (CATBody)
// Used to set and retrieve the geometric result
//
// Include this line in your Dictionary file if implementing:
// {PREFIX}{FEATURE_NAME}  CATIMmiResultFeature  lib{FRAMEWORK_NAME}
//-----------------------------------------------------------------------------

//-----------------------------------------------------------------------------
// CATIFmFeatureBehaviorCustomization Interface (Optional)
//-----------------------------------------------------------------------------
// Customizes feature behavior in the specification tree
// Controls:
//   - Feature name generation
//   - Copy/paste behavior
//   - Delete behavior
//   - Parent/child relationships
//
// Include this line in your Dictionary file if implementing:
// {PREFIX}{FEATURE_NAME}  CATIFmFeatureBehaviorCustomization  lib{FRAMEWORK_NAME}
//-----------------------------------------------------------------------------

//-----------------------------------------------------------------------------
// CATI3DGeoVisu Interface (Optional)
//-----------------------------------------------------------------------------
// Controls 3D visualization of the feature
// Use if you need custom visualization beyond default body display
//
// Include this line in your Dictionary file if implementing:
// {PREFIX}{FEATURE_NAME}  CATI3DGeoVisu  lib{FRAMEWORK_NAME}
//-----------------------------------------------------------------------------

//-----------------------------------------------------------------------------
// CATIVisProperties Interface (Optional)
//-----------------------------------------------------------------------------
// Manages visual properties (color, transparency, etc.)
// Use for custom visual property handling
//
// Include this line in your Dictionary file if implementing:
// {PREFIX}{FEATURE_NAME}  CATIVisProperties  lib{FRAMEWORK_NAME}
//-----------------------------------------------------------------------------

//=============================================================================
// ADDITIONAL DEPENDENCIES
//=============================================================================

// Geometric Modeler Dependencies (if using geometric operations)
/*
#include "CATTopOperator.h"
#include "CATTopBooleanOperator.h"
#include "CATTopExtrude.h"
#include "CATTopRevolve.h"
*/

// Topology Dependencies (if manipulating topology)
/*
#include "CATBody.h"
#include "CATCell.h"
#include "CATFace.h"
#include "CATEdge.h"
#include "CATVertex.h"
*/

// Math Dependencies (if using mathematical operations)
/*
#include "CATMathPoint.h"
#include "CATMathVector.h"
#include "CATMathDirection.h"
#include "CATMathTransformation.h"
*/

//=============================================================================
// FRAMEWORK PREREQUISITES
//=============================================================================
// Ensure your framework's IdentityCard.h includes all required frameworks:
//
// AddPrereqComponent("System", Public);
// AddPrereqComponent("ObjectModelerBase", Public);
// AddPrereqComponent("MechanicalModeler", Public);
// AddPrereqComponent("GeometricObjects", Protected);
// AddPrereqComponent("TopologicalObjects", Protected);
// AddPrereqComponent("Mathematics", Protected);

//=============================================================================
// USAGE NOTES
//=============================================================================
// 1. Update the Dictionary file ({FRAMEWORK_NAME}.dic) with interface mappings
// 2. Ensure all implemented interfaces are declared with TIE macros in .cpp
// 3. Use CATImplementClass macro to register the implementation class
// 4. Include this file in your implementation (.cpp) files for dependency tracking

#endif // {PREFIX}{FEATURE_NAME}_IdentityCard_H
