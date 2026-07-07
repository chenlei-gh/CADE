// COPYRIGHT DASSAULT SYSTEMES YYYY
#ifndef EventListenerName_h
#define EventListenerName_h

// System Framework
#include "CATEventListener.h"

/**
 * @brief EventListenerName - CATIA Event Listener
 * 
 * Listens to specific CATIA events and reacts accordingly.
 * 
 * Common events:
 * - Document open/close
 * - Selection change
 * - Feature modification
 * - Workbench activation
 */
class EventListenerName : public CATEventListener
{
public:
    EventListenerName();
    virtual ~EventListenerName();

    /**
     * @brief OnEvent - React to subscribed events
     * @param iEvent Event notification
     * @return HRESULT
     */
    virtual HRESULT OnEvent(CATNotification* iEvent);

    /**
     * @brief Subscribe - Register for specific events
     */
    void Subscribe();

    /**
     * @brief Unsubscribe - Unregister from events
     */
    void Unsubscribe();

private:
    CATBoolean _isSubscribed;

    EventListenerName(const EventListenerName&);
    EventListenerName& operator=(const EventListenerName&);
};

#endif
