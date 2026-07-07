// COPYRIGHT DASSAULT SYSTEMES {{YEAR}}
//===================================================================
// {{PREFIX}}IdentityCard.h
// Framework identity card - declares module dependencies
//===================================================================

/**
 * Module Identity Card
 * 
 * Declares framework dependencies and interface implementations for:
 * - {{PREFIX}}Workbench: Custom workbench
 * - {{PREFIX}}Addin: Addin for existing workbenches
 * 
 * Syntax:
 * - AddHeaderAddin: Declares addin for specific workbench
 *   Format: AddHeaderAddin("WorkbenchGUID", "AddinClass", "TargetWorkbenchName")
 * 
 * - AddHeaderWorkshop: Declares custom workbench
 *   Format: AddHeaderWorkshop("WorkbenchGUID", "WorkbenchClass", "WorkbenchName")
 * 
 * Standard CATIA Workbench GUIDs:
 * - Part Design:     PrtWks
 * - Assembly Design: AsmWks  
 * - Drafting:        DftWks
 * - Generative Shape Design: GSD
 * - Wireframe:       WireframeWks
 */

#include "CATFrmIdentityCard.h"

//-----------------------------------------------------------------------
// Addin Declaration - Integrate into existing workbenches
//-----------------------------------------------------------------------
// Add toolbar/commands to Part Design workbench
AddHeaderAddin("CAA2", "{{PREFIX}}Addin", "PrtWks");

// Add toolbar/commands to Assembly Design workbench
// AddHeaderAddin("CAA2", "{{PREFIX}}Addin", "AsmWks");

// Add toolbar/commands to other workbenches as needed
// AddHeaderAddin("CAA2", "{{PREFIX}}Addin", "GSD");

//-----------------------------------------------------------------------
// Custom Workbench Declaration (optional)
//-----------------------------------------------------------------------
// Declare custom workbench (uncomment if using standalone workbench)
// AddHeaderWorkshop("CAA2", "{{PREFIX}}Workbench", "{{PREFIX}}Wks");

//-----------------------------------------------------------------------
// Workshop Access Point (optional)
//-----------------------------------------------------------------------
// Define how to access the workbench (start menu, toolbar button, etc.)
// Requires additional configuration in CATRsc file
