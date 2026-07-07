// COPYRIGHT DASSAULT SYSTEMES YYYY
#ifndef AddinName_h
#define AddinName_h

// System Framework
#include "CATBaseUnknown.h"
#include "CATCreateWorkshop.h"

/**
 * @brief AddinName - Workbench Addin
 * 
 * Workbench Addins are responsible for:
 * - Adding commands to an existing workbench
 * - Creating toolbars with command buttons
 * - Setting up menu items
 * 
 * Lifecycle:
 *   Created when CATIA starts the target workbench
 *   Destroyed when workbench is closed
 */
class AddinName : public CATBaseUnknown
{
    CATDeclareClass;

public:
    /**
     * @brief Constructor
     */
    AddinName();

    /**
     * @brief Destructor
     */
    virtual ~AddinName();

    /**
     * @brief CreateCommands - Register commands with workbench
     * Called automatically when addin is loaded
     */
    void CreateCommands();

    /**
     * @brief CreateToolbars - Create toolbar groups
     * Called automatically when addin is loaded
     */
    void CreateToolbars();

private:
    // Workbench reference
    CATBaseUnknown* _pWorkbench;

    // Copy constructor, not implemented
    AddinName(const AddinName& iObjectToCopy);

    // Assignment operator, not implemented
    AddinName& operator=(const AddinName& iObjectToCopy);
};

#endif
