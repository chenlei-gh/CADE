// COPYRIGHT DASSAULT SYSTEMES YYYY
#ifndef WorkshopAddinName_h
#define WorkshopAddinName_h

// System Framework
#include "CATBaseUnknown.h"
#include "CATIWorkbench.h"
#include "CATIWorkshop.h"

/**
 * @brief WorkshopAddinName - Workshop Addin
 * 
 * Workshop Addins extend a workshop with custom functionality.
 * More advanced than Workbench Addins - they can modify the workshop itself.
 * 
 * Capabilities:
 * - Add new pages/tabs to workshop
 * - Modify existing workshop behavior
 * - Register custom document types
 * - Extend workshop commands
 */
class WorkshopAddinName : public CATBaseUnknown
{
    CATDeclareClass;

public:
    WorkshopAddinName();
    virtual ~WorkshopAddinName();

    /**
     * @brief InitWorkshop - Initialize workshop extension
     * @param iWorkshop The workshop being extended
     * @return HRESULT S_OK on success
     */
    HRESULT InitWorkshop(CATIWorkshop* iWorkshop);

    /**
     * @brief AddWorkshopPages - Add custom pages to workshop
     */
    void AddWorkshopPages();

    /**
     * @brief RegisterDocumentTypes - Register custom document types
     */
    void RegisterDocumentTypes();

private:
    CATIWorkshop* _pWorkshop;

    WorkshopAddinName(const WorkshopAddinName&);
    WorkshopAddinName& operator=(const WorkshopAddinName&);
};

#endif
