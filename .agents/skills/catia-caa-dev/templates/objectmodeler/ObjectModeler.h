// COPYRIGHT DASSAULT SYSTEMES YYYY
#ifndef ObjectModelerName_h
#define ObjectModelerName_h

// System Framework
#include "CATBaseUnknown.h"

// Object Modeler Framework
#include "CATIModelEvent.h"
#include "CATISpecObject.h"

/**
 * @brief ObjectModelerName - CAA Object Modeler
 * 
 * Object Modelers create new data objects in CATIA.
 * They define the data structure, behaviors, and persistence.
 * 
 * Key capabilities:
 * - Define new object types (Feature / Specification Object)
 * - Manage object attributes and lifecycle
 * - Handle persistence (save/load)
 * - React to model events
 * 
 * Parent class depends on object type:
 * - For Features:     inherit from CATFeature
 * - For Spec Objects: inherit from CATSpecObject
 * - For Data Objects: inherit from CATBaseUnknown
 */
class ObjectModelerName : public CATBaseUnknown
{
    CATDeclareClass;

public:
    ObjectModelerName();
    virtual ~ObjectModelerName();

    // --- Object Lifecycle ---

    /**
     * @brief Initialize - Set up initial state
     * Called when object is first created
     */
    void Initialize();

    /**
     * @brief Terminate - Clean up before destruction
     */
    void Terminate();

    // --- Data Access ---

    /**
     * @brief GetData - Retrieve object data
     * @param oData Output data
     * @return HRESULT
     */
    HRESULT GetData(Type& oData);

    /**
     * @brief SetData - Set object data
     * @param iData Input data
     * @return HRESULT
     */
    HRESULT SetData(const Type iData);

    // --- Object Operations ---

    /**
     * @brief Compute - Perform computation
     * Called when dependencies change
     */
    void Compute();

    /**
     * @brief Clone - Create a copy of this object
     * @return New object instance
     */
    ObjectModelerName* Clone();

private:
    // Object attributes
    Type _data;

    // State flags
    CATBoolean _isInitialized;
    CATBoolean _isDirty;

    ObjectModelerName(const ObjectModelerName&);
    ObjectModelerName& operator=(const ObjectModelerName&);
};

#endif
