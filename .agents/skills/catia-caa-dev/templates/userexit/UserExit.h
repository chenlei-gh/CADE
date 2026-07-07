// COPYRIGHT DASSAULT SYSTEMES YYYY
#ifndef UserExitName_h
#define UserExitName_h

// System Framework
#include "CATBaseUnknown.h"
#include "CATIUserExit.h"

/**
 * @brief UserExitName - CATIA User Exit
 * 
 * User exits allow custom code execution at specific points in CATIA's workflow.
 * 
 * Common use cases:
 * - Intercept document save/load
 * - Validate data before operations
 * - Custom processing hooks
 * - Integration with external systems
 */
class UserExitName : public CATBaseUnknown, public CATIUserExit
{
    CATDeclareClass;

public:
    UserExitName();
    virtual ~UserExitName();

    /**
     * @brief Execute - Called when user exit point is reached
     * @param iContext Context data for the exit point
     * @return HRESULT
     */
    virtual HRESULT Execute(void* iContext);

    /**
     * @brief GetPriority - Return execution priority
     * Lower numbers execute first
     * @return Priority value
     */
    virtual int GetPriority();

    /**
     * @brief GetExitPoint - Return exit point identifier
     * @return Exit point name
     */
    virtual CATString GetExitPoint();

private:
    int _priority;
    CATString _exitPoint;

    UserExitName(const UserExitName&);
    UserExitName& operator=(const UserExitName&);
};

#endif
