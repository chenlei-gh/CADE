// COPYRIGHT DASSAULT SYSTEMES YYYY

#include "EventListenerName.h"

#include "CATEventSubscriber.h"
#include <iostream>
using namespace std;

EventListenerName::EventListenerName()
    : _isSubscribed(FALSE)
{
    cout << "EventListenerName::EventListenerName" << endl;
}

EventListenerName::~EventListenerName()
{
    Unsubscribe();
    cout << "EventListenerName::~EventListenerName" << endl;
}

HRESULT EventListenerName::OnEvent(CATNotification* iEvent)
{
    cout << "EventListenerName::OnEvent" << endl;
    // Handle event
    return S_OK;
}

void EventListenerName::Subscribe()
{
    if (_isSubscribed) return;
    cout << "EventListenerName::Subscribe" << endl;
    // Register for events via CATEventSubscriber
    _isSubscribed = TRUE;
}

void EventListenerName::Unsubscribe()
{
    if (!_isSubscribed) return;
    cout << "EventListenerName::Unsubscribe" << endl;
    _isSubscribed = FALSE;
}
