// COPYRIGHT DASSAULT SYSTEMES 2026
#ifndef {PREFIX}{FEATURE_NAME}_IdentityCard_H
#define {PREFIX}{FEATURE_NAME}_IdentityCard_H

//=============================================================================
// FRAMEWORK IDENTITY CARD
//=============================================================================
// This file declares all interface implementations for the feature
// It serves as a central dependency declaration for the Dictionary
//
// ⚠️ 2026-07 对 B28 全目录核实：CATIMmiResultFeature.h / CATIMmiUseMechFeat.h
// 不存在，已从本文件移除（原注释声称的这两个接口为捏造）。
// 证据：knowledge/failure_patterns/fp_template_feature_apis.md

// System Framework
#include "CATBaseUnknown.h"

// ObjectModelerBase Framework - Core interfaces
#include "CATISpecObject.h"
#include "CATIFmFeatureBehaviorCustomization.h"

// Feature Modeler - Build and Update
#include "CATIBuild.h"
#include "CATIReplace.h"

// MechanicalModeler Framework - Mechanical feature interfaces
// ⚠️ 已删除捏造头文件：CATIMmiResultFeature.h / CATIMmiUseMechFeat.h（B28 不存在）
#include "CATIMmiMechanicalFeature.h"

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
// ⚠️ CATIMmiResultFeature / CATIMmiUseMechFeat 接口不存在于 B28（2026-07 全目录核实）
// 原模版此处的 Dictionary 声明为捏造，已移除。
// 读取结果几何的真实接口：CATIGeometricalElement::GetBodyResult()
// （头文件 MecModInterfaces/PublicInterfaces/CATIGeometricalElement.h）。
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
// ⚠️ 已修正捏造名：CATTopBooleanOperator.h→CATTopOperator.h，CATTopRevolve.h→CATTopRevol.h
/*
#include "CATTopOperator.h"
#include "CATTopExtrude.h"
#include "CATTopRevol.h"
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
