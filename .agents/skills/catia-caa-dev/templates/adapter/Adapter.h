// COPYRIGHT DASSAULT SYSTEMES YYYY
#ifndef AdapterName_h
#define AdapterName_h

// System Framework
#include "CATBaseUnknown.h"
#include "IAdaptedInterface.h"

#ifndef ExportedByModuleName
#define ExportedByModuleName
#endif

/**
 * @brief AdapterName - 3DS Adapter
 * 
 * Bridges between two incompatible interfaces.
 * Adapter Pattern implementation for CAA components.
 */
class ExportedByModuleName AdapterName : public IAdaptedInterface
{
public:
    AdapterName(CATBaseUnknown* iAdaptedObject);
    virtual ~AdapterName();

    virtual HRESULT AdaptedMethod(const Type iParam, Type& oParam);

private:
    CATBaseUnknown* _pAdaptedObject;

    AdapterName(const AdapterName&);
    AdapterName& operator=(const AdapterName&);
};

#endif
