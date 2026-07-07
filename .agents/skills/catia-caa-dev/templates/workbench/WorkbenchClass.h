// COPYRIGHT DASSAULT SYSTEMES {{YEAR}}
//===================================================================
// {{PREFIX}}Workbench.h
// Workbench class declaration
//===================================================================
#ifndef {{PREFIX}}Workbench_H
#define {{PREFIX}}Workbench_H

// Application Frame
#include "CATCmdWorkbench.h"

/**
 * @class {{PREFIX}}Workbench
 * @brief Custom workbench for {{DESCRIPTION}}
 * 
 * This workbench provides:
 * - Custom commands registration
 * - Toolbar creation and layout
 * - Menu integration
 * - Addin support for existing workbenches
 * 
 * @see CATCmdWorkbench
 * @see {{PREFIX}}Addin
 */
class {{PREFIX}}Workbench : public CATCmdWorkbench
{
public:
    /**
     * Constructor
     * @param iParent Parent command (typically NULL)
     */
    {{PREFIX}}Workbench(const CATString& iWorkbenchName);
    
    /**
     * Destructor
     */
    virtual ~{{PREFIX}}Workbench();

    /**
     * Creates all commands for this workbench
     * Called automatically by framework during workbench initialization
     * Register all CATCommand instances here
     */
    virtual void CreateCommands();

    /**
     * Creates toolbars for this workbench
     * Called automatically after CreateCommands()
     * Define toolbar layout and command organization
     * 
     * @see CATCmdContainer for toolbar creation API
     */
    virtual CATCmdContainer* CreateToolbars();

    /**
     * Creates menus for this workbench (optional)
     * Override if custom menu bar items are needed
     * 
     * @return Menu container or NULL
     */
    virtual CATCmdContainer* CreateMenus();

private:
    // Copy constructor and assignment operator (not implemented)
    {{PREFIX}}Workbench(const {{PREFIX}}Workbench&);
    {{PREFIX}}Workbench& operator=(const {{PREFIX}}Workbench&);
};

#endif // {{PREFIX}}Workbench_H
