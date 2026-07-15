// COPYRIGHT DASSAULT SYSTEMES {{YEAR}}
//===================================================================
// {{PREFIX}}Addin.h
// Addin class for integrating into existing workbenches
//===================================================================
#ifndef {{PREFIX}}Addin_H
#define {{PREFIX}}Addin_H

// Application Frame
#include "CATBaseUnknown.h"

// Interface includes
#include "CATIAfrGeneralWksAddin.h"

/**
 * @class {{PREFIX}}Addin
 * @brief Addin extension for integrating commands into existing workbenches
 * 
 * This addin allows adding custom toolbars and commands to standard CATIA workbenches.
 * Target workbenches are declared in IdentityCard (e.g., Part Design, Assembly Design)
 * 
 * Implementation pattern:
 * - Implements CATIAfrGeneralWksAddin for workbench integration
 * - Implements CATIWorkbenchAddin for toolbar/menu creation
 * - Uses TIE macro for interface exposure
 * 
 * @see CATIAfrGeneralWksAddin
 * @see CATIWorkbenchAddin
 */
class {{PREFIX}}Addin : public CATBaseUnknown
{
    // TIE implementation for CATIAfrGeneralWksAddin
    CATDeclareClass;

public:
    /**
     * Constructor
     */
    {{PREFIX}}Addin();

    /**
     * Destructor
     */
    virtual ~{{PREFIX}}Addin();

    /**
     * Creates command headers
     */
    void CreateCommands();

    /**
     * Creates toolbars for the addin
     * Called by framework when target workbench is activated
     * 
     * @param iParent Parent workbench
     * @return Toolbar container with commands
     */
    virtual CATCmdContainer* CreateToolbars();

    /**
     * Creates menus for the addin (optional)
     * 
     * @param iParent Parent workbench
     * @return Menu container or NULL
     */
    virtual CATCmdContainer* CreateMenus();

private:
    // Copy constructor and assignment operator (not implemented)
    {{PREFIX}}Addin(const {{PREFIX}}Addin&);
    {{PREFIX}}Addin& operator=(const {{PREFIX}}Addin&);
};

#endif // {{PREFIX}}Addin_H
