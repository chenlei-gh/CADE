# CATIA Command Quick Reference

> Quick lookup for Command development patterns and syntax

---

## 🎯 Command Class Template

```cpp
// Header (.h)
class MyCommand : public CATStateCommand
{
    CATDeclareClass;

public:
    MyCommand();
    virtual ~MyCommand();
    virtual void BuildGraph();

private:
    CATPathElementAgent* _pAgent;
    
    CATBoolean CheckCondition(void* iData);
    CATBoolean ExecuteAction(void* iData);
};

// Implementation (.cpp)
CATImplementClass(MyCommand, Implementation, CATStateCommand, CATNull);

MyCommand::MyCommand()
    : CATStateCommand("MyCommand"),
      _pAgent(NULL)
{
}

MyCommand::~MyCommand()
{
    _pAgent = NULL;  // Framework deletes agents
}
```

---

## 🤖 Agent Types Cheat Sheet

### CATPathElementAgent - Select Model Elements

```cpp
// Create
_pAgent = new CATPathElementAgent("AgentName");

// Set filter (what types can be selected)
_pAgent->SetElementType("CATISpecObject");     // Any object
_pAgent->SetElementType("CATIGSMGeometry");    // Geometry
_pAgent->SetElementType("CATISurface");        // Surfaces only
_pAgent->SetElementType("CATILine");           // Lines only
_pAgent->SetElementType("CATIPoint");          // Points only

// Set behavior
_pAgent->SetBehavior(CATDlgEngOneShot);        // Single selection
_pAgent->SetBehavior(CATDlgEngRepeat);         // Multiple selections
_pAgent->SetBehavior(CATDlgEngAcceptOnNotify); // Accumulate
_pAgent->SetBehavior(CATDlgEngWithPrevalue);   // Allow preselection

// Set prompt
_pAgent->SetPrompt("MyCommand.SelectPrompt");  // From .CATNls

// Get selected elements
CATSO* pList = _pAgent->GetListOfValues();
int count = pList->GetSize();
CATPathElement* pPath = (CATPathElement*)(*pList)[0];

// Extract object from path
CATISpecObject* pObj = NULL;
pPath->FindElement(IID_CATISpecObject, (void**)&pObj);
```

---

### CATIndicationAgent - Capture Mouse Clicks

```cpp
// Create
_pAgent = new CATIndicationAgent("ClickAgent");

// Set behavior
_pAgent->SetBehavior(CATDlgEngOneShot);    // Single click
_pAgent->SetBehavior(CATDlgEngRepeat);     // Multiple clicks

// Get click position
CATMathPoint2D point = _pAgent->GetValue();

// Get 3D position
CATMathPoint point3D = _pAgent->GetMathPoint();
```

---

### CATDialogAgent - Trigger on UI Events

```cpp
// Create
_pAgent = new CATDialogAgent("DialogAgent");

// Typically triggered by dialog button
// Used with AddAnalyseNotificationCB in dialogs
```

---

## 🔄 BuildGraph() Pattern

### Basic Single-Step Selection

```cpp
void MyCommand::BuildGraph()
{
    // 1. Create agent
    _pAgent = new CATPathElementAgent("Select");
    _pAgent->SetElementType("CATISpecObject");
    AddCSOClient(_pAgent);
    
    // 2. Create states
    CATDialogState* pSelectState = GetInitialState("Selecting");
    pSelectState->AddDialogAgent(_pAgent);
    
    CATDialogState* pProcessState = AddDialogState("Processing");
    
    // 3. Create transition
    CATDialogTransition* pTrans = AddTransition(
        pSelectState,                              // From
        pProcessState,                             // To
        IsLastModifiedAgentCondition(_pAgent),     // Trigger
        CheckCondition(CheckSelection)             // Validation
    );
    
    // 4. Add action
    pTrans->AddAction(ExecuteAction(ProcessSelection));
    
    // 5. Set prompt
    _pAgent->SetPrompt("MyCommand.Prompt");
}
```

---

### Two-Step Selection

```cpp
void MyCommand::BuildGraph()
{
    // Create both agents
    _pAgent1 = new CATPathElementAgent("First");
    _pAgent1->SetElementType("CATISpecObject");
    AddCSOClient(_pAgent1);
    
    _pAgent2 = new CATPathElementAgent("Second");
    _pAgent2->SetElementType("CATISpecObject");
    AddCSOClient(_pAgent2);
    
    // Three states: Select1 -> Select2 -> Process
    CATDialogState* pState1 = GetInitialState("SelectFirst");
    pState1->AddDialogAgent(_pAgent1);
    
    CATDialogState* pState2 = AddDialogState("SelectSecond");
    pState2->AddDialogAgent(_pAgent2);
    
    CATDialogState* pState3 = AddDialogState("Process");
    
    // First transition
    AddTransition(
        pState1, pState2,
        IsLastModifiedAgentCondition(_pAgent1),
        CheckCondition(CheckFirst)
    );
    
    // Second transition with action
    CATDialogTransition* pTrans = AddTransition(
        pState2, pState3,
        IsLastModifiedAgentCondition(_pAgent2),
        CheckCondition(CheckSecond)
    );
    pTrans->AddAction(ExecuteAction(ProcessBoth));
    
    // Prompts
    _pAgent1->SetPrompt("Select first element");
    _pAgent2->SetPrompt("Select second element");
}
```

---

### Repeating Selection Loop

```cpp
void MyCommand::BuildGraph()
{
    _pAgent = new CATPathElementAgent("Select");
    _pAgent->SetBehavior(CATDlgEngRepeat);  // Allow multiple
    AddCSOClient(_pAgent);
    
    // Single state that loops to itself
    CATDialogState* pState = GetInitialState("Selecting");
    pState->AddDialogAgent(_pAgent);
    
    // Self-loop: State -> State
    CATDialogTransition* pLoop = AddTransition(
        pState,
        pState,
        IsLastModifiedAgentCondition(_pAgent)
    );
    pLoop->AddAction(ExecuteAction(AddToSelection));
    
    _pAgent->SetPrompt("Select elements (ESC to finish)");
}
```

---

### Selection with Optional Dialog

```cpp
void MyCommand::BuildGraph()
{
    _pSelectAgent = new CATPathElementAgent("Select");
    AddCSOClient(_pSelectAgent);
    
    _pDialogAgent = new CATDialogAgent("Dialog");
    AddCSOClient(_pDialogAgent);
    
    CATDialogState* pSelectState = GetInitialState("Select");
    pSelectState->AddDialogAgent(_pSelectAgent);
    
    CATDialogState* pDialogState = AddDialogState("ShowDialog");
    pDialogState->AddDialogAgent(_pDialogAgent);
    
    CATDialogState* pProcessState = AddDialogState("Process");
    
    // Select -> Dialog
    CATDialogTransition* pTrans1 = AddTransition(
        pSelectState, pDialogState,
        IsLastModifiedAgentCondition(_pSelectAgent)
    );
    pTrans1->AddAction(ExecuteAction(ShowDialog));
    
    // Dialog -> Process (OK)
    CATDialogTransition* pTrans2 = AddTransition(
        pDialogState, pProcessState,
        IsLastModifiedAgentCondition(_pDialogAgent),
        CheckCondition(CheckDialogOK)
    );
    pTrans2->AddAction(ExecuteAction(ProcessWithDialog));
    
    // Dialog -> Select (Cancel)
    AddTransition(pDialogState, pSelectState, NULL);
}
```

---

## 📋 Transition Syntax

### Basic Transition

```cpp
AddTransition(
    fromState,           // Source state
    toState,             // Destination state
    condition,           // Trigger condition (or NULL)
    validationCondition  // Validation (or NULL)
);
```

---

### With Action

```cpp
CATDialogTransition* pTrans = AddTransition(
    fromState,
    toState,
    IsLastModifiedAgentCondition(_pAgent),
    CheckCondition(MyValidation)
);

// Add action to execute on transition
pTrans->AddAction(ExecuteAction(MyAction));
```

---

### Multiple Actions

```cpp
CATDialogTransition* pTrans = AddTransition(...);
pTrans->AddAction(ExecuteAction(Action1));
pTrans->AddAction(ExecuteAction(Action2));
pTrans->AddAction(ExecuteAction(Action3));
// Actions execute in order
```

---

## ✅ Condition Methods

### Signature

```cpp
CATBoolean MethodName(void* iData);
```

### Usage in BuildGraph

```cpp
// Define macro for convenience
#define CheckCondition(method) \
    (CATStateCommand::ConditionMethod)&MyCommand::method, NULL

// Use in transition
AddTransition(
    fromState, toState,
    trigger,
    CheckCondition(MyCheckMethod)
);
```

### Standard Conditions

```cpp
// Agent was modified
IsLastModifiedAgentCondition(_pAgent)

// Agent has output
IsOutputSetCondition(_pAgent)

// Custom method
CheckCondition(MyMethod)

// Combine with AND
Condition1 && Condition2

// Combine with OR  
Condition1 || Condition2

// No condition (always true)
NULL
```

---

### Example Condition

```cpp
CATBoolean MyCommand::CheckSelection(void* iData)
{
    // Get selected elements
    CATSO* pList = _pAgent->GetListOfValues();
    
    // Validate
    if (!pList || pList->GetSize() == 0) {
        cout << "No selection" << endl;
        return FALSE;  // Condition fails
    }
    
    // Check element type
    CATPathElement* pPath = (CATPathElement*)(*pList)[0];
    CATBaseUnknown* pElement = pPath->FindElement(IID_CATISpecObject);
    
    if (!pElement) {
        return FALSE;
    }
    
    pElement->Release();
    return TRUE;  // Condition passes
}
```

**Return Values:**
- `TRUE` - Condition passes, transition occurs
- `FALSE` - Condition fails, stay in current state

---

## ⚙️ Action Methods

### Signature

```cpp
CATBoolean MethodName(void* iData);
```

### Usage in BuildGraph

```cpp
// Define macro
#define ExecuteAction(method) \
    (CATStateCommand::ActionMethod)&MyCommand::method, NULL

// Use in transition
CATDialogTransition* pTrans = AddTransition(...);
pTrans->AddAction(ExecuteAction(MyActionMethod));
```

---

### Example Action

```cpp
CATBoolean MyCommand::ProcessSelection(void* iData)
{
    cout << "Processing selection..." << endl;
    
    // Get selected elements
    CATSO* pList = _pAgent->GetListOfValues();
    if (!pList) return FALSE;
    
    for (int i = 0; i < pList->GetSize(); i++) {
        CATPathElement* pPath = (CATPathElement*)(*pList)[i];
        
        // Get spec object
        CATISpecObject* pObj = NULL;
        pPath->FindElement(IID_CATISpecObject, (void**)&pObj);
        
        if (pObj) {
            // Process object
            CATUnicodeString name = pObj->GetDisplayName();
            cout << "Processing: " << name.ConvertToChar() << endl;
            
            // YOUR CODE HERE
            
            pObj->Release();
        }
    }
    
    // Clear selection for next iteration
    _pAgent->InitializeAcquisition();
    
    return TRUE;  // Action successful
}
```

**Return Values:**
- `TRUE` - Action successful
- `FALSE` - Action failed (may cancel command)

---

## 🎯 Common Action Patterns

### Extract Selected Object

```cpp
CATBoolean MyCommand::ProcessSelection(void* iData)
{
    CATSO* pList = _pAgent->GetListOfValues();
    if (!pList || pList->GetSize() == 0) return FALSE;
    
    CATPathElement* pPath = (CATPathElement*)(*pList)[0];
    
    // Method 1: Using FindElement
    CATISpecObject* pObj = NULL;
    HRESULT hr = pPath->FindElement(IID_CATISpecObject, (void**)&pObj);
    
    if (SUCCEEDED(hr) && pObj) {
        // Use object
        pObj->Release();
    }
    
    return TRUE;
}
```

---

### Process Multiple Selections

```cpp
CATBoolean MyCommand::ProcessMultiple(void* iData)
{
    CATSO* pList = _pAgent->GetListOfValues();
    int count = pList->GetSize();
    
    cout << "Processing " << count << " elements" << endl;
    
    for (int i = 0; i < count; i++) {
        CATPathElement* pPath = (CATPathElement*)(*pList)[i];
        
        // Process each element
        // ...
    }
    
    return TRUE;
}
```

---

### Clear Agent for Next Selection

```cpp
CATBoolean MyCommand::ClearAndContinue(void* iData)
{
    // Process current selection
    // ...
    
    // Clear agent for next selection
    _pAgent->InitializeAcquisition();
    
    return TRUE;
}
```

---

### Show Dialog from Action

```cpp
CATBoolean MyCommand::ShowDialog(void* iData)
{
    // Create and show dialog
    CATApplicationFrame* pFrame = CATApplicationFrame::GetFrame();
    
    MyDialog* pDlg = new MyDialog(pFrame, "MyDialog");
    pDlg->Build();
    pDlg->SetVisibility(CATDlgShow);
    
    // Dialog deletes itself when closed
    
    return TRUE;
}
```

---

## 📝 Prompt Messages

### Set Prompt from Resource File

```cpp
// In BuildGraph()
_pAgent->SetPrompt("MyCommand.SelectPrompt");

// In MyFramework.CATNls
MyCommand.SelectPrompt = "Select a geometric element";
```

---

### Dynamic Prompt (Runtime)

```cpp
// Create prompt string
CATUnicodeString prompt = "Select element (";
prompt += countStr;
prompt += " selected)";

// Set prompt
_pAgent->SetPrompt(prompt);
```

---

### Multi-Language Prompts

```
# MyFramework.CATNls (English)
MyCommand.Prompt1 = "Select first point";
MyCommand.Prompt2 = "Select second point";
MyCommand.Complete = "Operation complete";

# Chinese/MyFramework.CATNls (Chinese)
MyCommand.Prompt1 = "选择第一个点";
MyCommand.Prompt2 = "选择第二个点";
MyCommand.Complete = "操作完成";
```

---

## 🎨 Agent Registration

### Add Agent to Command

```cpp
// MUST call this for each agent
AddCSOClient(_pAgent);
```

### Add Agent to State

```cpp
// Agent only active in states where it's added
CATDialogState* pState = GetInitialState("State");
pState->AddDialogAgent(_pAgent);
```

**Both are required!**

---

## 🔧 State Management

### Get Initial State

```cpp
// First state of command
CATDialogState* pState = GetInitialState("StateName");
```

### Add New State

```cpp
// Add additional states
CATDialogState* pState2 = AddDialogState("State2");
CATDialogState* pState3 = AddDialogState("State3");
```

---

## 🎭 Command Lifecycle Methods

### Activate - Command Starts

```cpp
CATStatusChangeRC MyCommand::Activate(
    CATCommand* iFromClient,
    CATNotification* iNotification)
{
    cout << "Command activated" << endl;
    
    // Initialize resources
    // ...
    
    return CATStatusChangeRCCompleted;
}
```

---

### Desactivate - Command Ends

```cpp
CATStatusChangeRC MyCommand::Desactivate(
    CATCommand* iFromClient,
    CATNotification* iNotification)
{
    cout << "Command deactivated" << endl;
    
    // Cleanup
    // ...
    
    return CATStatusChangeRCCompleted;
}
```

---

### Cancel - User Presses ESC

```cpp
CATStatusChangeRC MyCommand::Cancel(
    CATCommand* iFromClient,
    CATNotification* iNotification)
{
    cout << "Command cancelled" << endl;
    
    // Cleanup and exit
    RequestDelayedDestruction();
    
    return CATStatusChangeRCCompleted;
}
```

---

## 🏗️ CommandHeader Creation

### Header Factory

```cpp
// MyCommandHeader.cpp
#include "CATCreateExternalObject.h"
#include "CATCommandHeader.h"
#include "MyCommand.h"

CATCreateClass(MyCommandHeader);

MyCommandHeader::MyCommandHeader()
    : CATCommandHeader(
        "MyCommandHeader",      // Header name
        "MyFramework",          // Framework name
        "MyCommand",            // Command class name
        (void*)NULL
      )
{
}

MyCommandHeader::~MyCommandHeader()
{
}
```

---

### Register in Workbench

```cpp
// In workbench CreateCommands() method
void MyWorkbench::CreateCommands()
{
    // Create header
    new MyCommandHeader();
    
    // Add to toolbar
    AddAccessToCmd("MyCommandHeader", "MyToolbar");
    
    // Set icon and help
    SetAccessCommand(
        "MyCommandHeader",
        "MyCommand",                    // Icon name
        "MyCommand.ShortHelp",          // Tooltip
        "MyCommand.LongHelp"            // Status bar text
    );
}
```

---

## 📚 Resource Files

### Command Strings (.CATNls)

```
# Prompts
MyCommand.SelectPrompt = "Select an element";
MyCommand.SelectPrompt2 = "Select second element";

# Help
MyCommand.ShortHelp = "My Command";
MyCommand.LongHelp = "Description of what this command does";

# Messages
MyCommand.Success = "Operation completed successfully";
MyCommand.Error = "Invalid selection";
```

**Location:** `Framework.edu/CNext/resources/msgcatalog/MyFramework.CATNls`

---

### Icons (.CATRsc)

```
# Icon path
MyCommand.Icon = "I_MyCommandIcon";

# Toolbar position
MyCommand.Category = "MyCategory";
```

---

## 🔍 Debugging Tips

### Print Agent Status

```cpp
void MyCommand::DebugAgent()
{
    CATSO* pList = _pAgent->GetListOfValues();
    
    if (!pList) {
        cout << "Agent has no values" << endl;
        return;
    }
    
    cout << "Agent has " << pList->GetSize() << " values" << endl;
}
```

---

### Print State Information

```cpp
CATBoolean MyCommand::MyAction(void* iData)
{
    cout << "=== Action Called ===" << endl;
    cout << "Current state: " << GetState()->GetName() << endl;
    
    // Your logic here
    
    return TRUE;
}
```

---

### Trace State Transitions

```cpp
void MyCommand::BuildGraph()
{
    // Enable tracing
    SetCommandTraceMode(1);
    
    // Build graph as normal
    // ...
}
```

---

## ⚠️ Common Mistakes

### ❌ Agent not added to state

```cpp
// WRONG
_pAgent = new CATPathElementAgent("Agent");
AddCSOClient(_pAgent);
// Missing: pState->AddDialogAgent(_pAgent);
```

**✅ Correct:**
```cpp
_pAgent = new CATPathElementAgent("Agent");
AddCSOClient(_pAgent);
pState->AddDialogAgent(_pAgent);  // MUST add to state!
```

---

### ❌ Agent not added to command

```cpp
// WRONG
_pAgent = new CATPathElementAgent("Agent");
pState->AddDialogAgent(_pAgent);
// Missing: AddCSOClient(_pAgent);
```

**✅ Correct:**
```cpp
_pAgent = new CATPathElementAgent("Agent");
AddCSOClient(_pAgent);  // MUST register with command!
pState->AddDialogAgent(_pAgent);
```

---

### ❌ Wrong condition method signature

```cpp
// WRONG
bool CheckSelection();  // Wrong return type and parameters
```

**✅ Correct:**
```cpp
CATBoolean CheckSelection(void* iData);  // Correct signature
```

---

### ❌ Missing transition trigger

```cpp
// WRONG - No way to trigger transition
AddTransition(pState1, pState2, NULL, NULL);
```

**✅ Correct:**
```cpp
AddTransition(
    pState1, pState2,
    IsLastModifiedAgentCondition(_pAgent),  // Trigger!
    NULL
);
```

---

### ❌ Forgetting CATImplementClass

```cpp
// Missing in .cpp file:
CATImplementClass(MyCommand, Implementation, CATStateCommand, CATNull);
```

**✅ Must include this macro!**

---

## 📊 Complete Minimal Example

```cpp
// MySimpleCommand.h
#ifndef MySimpleCommand_H
#define MySimpleCommand_H

#include "CATStateCommand.h"
class CATPathElementAgent;

class MySimpleCommand : public CATStateCommand
{
    CATDeclareClass;

public:
    MySimpleCommand();
    virtual ~MySimpleCommand();
    virtual void BuildGraph();

private:
    CATPathElementAgent* _pAgent;
    CATBoolean ProcessSelection(void* iData);
};

#endif

// MySimpleCommand.cpp
#include "MySimpleCommand.h"
#include "CATPathElementAgent.h"

CATImplementClass(MySimpleCommand, Implementation, CATStateCommand, CATNull);

#define ExecuteAction(method) \
    (CATStateCommand::ActionMethod)&MySimpleCommand::method, NULL

MySimpleCommand::MySimpleCommand()
    : CATStateCommand("MySimpleCommand"),
      _pAgent(NULL)
{
}

MySimpleCommand::~MySimpleCommand()
{
    _pAgent = NULL;
}

void MySimpleCommand::BuildGraph()
{
    // Create agent
    _pAgent = new CATPathElementAgent("Select");
    _pAgent->SetElementType("CATISpecObject");
    _pAgent->SetBehavior(CATDlgEngOneShot);
    AddCSOClient(_pAgent);
    
    // States
    CATDialogState* pSelectState = GetInitialState("Select");
    pSelectState->AddDialogAgent(_pAgent);
    
    CATDialogState* pProcessState = AddDialogState("Process");
    
    // Transition
    CATDialogTransition* pTrans = AddTransition(
        pSelectState,
        pProcessState,
        IsLastModifiedAgentCondition(_pAgent)
    );
    pTrans->AddAction(ExecuteAction(ProcessSelection));
    
    // Prompt
    _pAgent->SetPrompt("Select an element");
}

CATBoolean MySimpleCommand::ProcessSelection(void* iData)
{
    CATSO* pList = _pAgent->GetListOfValues();
    if (!pList) return FALSE;
    
    cout << "Selected " << pList->GetSize() << " elements" << endl;
    
    return TRUE;
}
```

---

## 🔗 Full Documentation

- **EXAMPLE_COMMAND.md** - Complete tutorial with detailed explanations
- **EXAMPLE_DIALOG.md** - Dialog development
- **templates/command/** - Ready-to-use template files
- **AI_GUIDE.md** - Generation rules for AI

---

**Quick Start:** Copy templates from `templates/command/`, customize BuildGraph(), compile!
