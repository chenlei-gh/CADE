#ifndef IInterfaceName_h
#define IInterfaceName_h

// COPYRIGHT DASSAULT SYSTEMES YYYY

// System Framework
#include "CATBaseUnknown.h"
#include "CATUnicodeString.h"

// Export from this module
#ifndef ExportedByModuleName
#define ExportedByModuleName
#endif

// Global Unique IDentifier defined in .cpp
extern ExportedByModuleName IID IID_IInterfaceName;

/**
 * @brief Interface description
 */
class ExportedByModuleName IInterfaceName : public CATBaseUnknown
{
    // Used in conjunction with CATImplementInterface in the .cpp file
    CATDeclareInterface;

public:
    /**
     * @brief Method description
     * @param iParam Input parameter
     * @param oParam Output parameter
     * @return HRESULT S_OK if successful, E_FAIL otherwise
     */
    virtual HRESULT Execute(const CATUnicodeString& iParam, CATUnicodeString& oResult) = 0;
};

#endif
