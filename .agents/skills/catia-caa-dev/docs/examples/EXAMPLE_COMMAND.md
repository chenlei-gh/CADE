# CATIA Command Development - Complete Tutorial

> Complete guide to developing interactive CATIA CAA Commands with state machines

**Version**: 1.0  
**Framework**: InteractiveInterfaces, ApplicationFrame  
**Target**: CATIA V5R28 (B28)

---

## 📋 Overview

This tutorial demonstrates how to create interactive CATIA Commands using:
- ✅ **CATStateCommand** state machine pattern
- ✅ **CATPathElementAgent** for element selection
- ✅ **BuildGraph()** state transition logic
- ✅ **Condition** and **Action** methods
- ✅ **CommandHeader** creation and toolbar integration
- ✅ Undo/Redo support
- ✅ User prompts and feedback

---

## 🎯 What is a Command?

A **Command** in CATIA is an interactive tool that:
1. Waits for user input (selections, clicks)
2. Validates the input
3. Performs operations on the model
4. Provides visual feedback

**Example Commands:**
- Select two points → Create line
- Select surface → Extract boundary
- Select elements → Apply transformation

---

## 📁 File Structure

```
Framework.edu/
├── IdentityCard/
│   └── IdentityCard.h                    # Framework dependencies
├── PublicInterfaces/
│   └── MySelectCommand.h                 # Command class declaration
├── MyCommandModule.m/
│   ├── Imakefile.mk                      # Build configuration
│   ├── src/
│   │   ├── MySelectCommand.cpp           # Command implementation
│   │   └── MyCommandHeader.cpp           # CommandHeader factory
│   └── LocalInterfaces/
│       └── CATCommandHeader.h            # (auto-generated)
└── CNext/
    └── resources/
        └── msgcatalog/
            └── MyFramework.CATNls         # String resources
```

---

## 🔄 Command State Machine

### State Machine Concept

Commands use a **state machine** pattern:
```
    [Initial State]
         |
         v
    [Select Element] ──(valid?)──> [Process]
         |                              |
         └────(invalid)─────────────────┘
```

**Key Components:**
1. **States** - Different stages of the command
2. **Agents** - Capture user input (selections, clicks)
3. **Transitions** - Move between states based on conditions
4. **Actions** - Execute code when entering/leaving states

---

## 📝 Step-by-Step Implementation

### Step 1: IdentityCard.h

```cpp
// Framework.edu/IdentityCard/IdentityCard.h

AddPrereqComponent("System", Public);
AddPrereqComponent("ObjectModelerBase", Public);
AddPrereqComponent("ApplicationFrame", Public);
AddPrereqComponent("InteractiveInterfaces", Public);
AddPrereqComponent("Visualization", Public);
AddPrereqComponent("GeometricObjects", Public);
```

**Required Dependencies:**
- `InteractiveInterfaces` - For CATStateCommand, agents
- `ApplicationFrame` - For CommandHeader
- `Visualization` - For visual feedback

---

### Step 2: Command Header (MySelectCommand.h)

```cpp
// Framework.edu/PublicInterfaces/MySelectCommand.h

#ifndef MySelectCommand_H
#define MySelectCommand_H

#include "CATStateCommand.h"

class CATPathElementAgent;
class CATIndicationAgent;

/**
 * Interactive command to select geometric elements
 * 
 * State machine:
 * 1. Wait for user to select an element
 * 2. Validate selection
 * 3. Process the element
 */
class MySelectCommand : public CATStateCommand
{
    CATDeclareClass;

public:
    /**
     * Constructor
     * Creates the command and initializes agents
     */
    MySelectCommand();
    
    /**
     * Destructor
     * Cleans up agents and resources
     */
    virtual ~MySelectCommand();

    /**
     * Build the state machine graph
     * Called automatically before command activation
     */
    virtual void BuildGraph();

    /**
     * Activate the command
     * Called when command starts
     */
    virtual CATStatusChangeRC Activate(CATCommand* iFromClient,
                                               CATNotification* iNotification);

    /**
     * Deactivate the command
     * Called when command ends
     */
    virtual CATStatusChangeRC Desactivate(CATCommand* iFromClient,
                                                   CATNotification* iNotification);

    /**
     * Cancel the command
     * Called when user presses ESC
     */
    virtual CATStatusChangeRC Cancel(CATCommand* iFromClient,
                                             CATNotification* iNotification);

private:
    // ===== Agents =====
    /**
     * Agent to capture element selection
     * Filters geometric elements only
     */
    CATPathElementAgent* _pSelectAgent;

    // ===== Condition Methods =====
    /**
     * Check if selected element is valid
     * @return TRUE if valid, FALSE otherwise
     */
    CATBoolean CheckSelection(void* iData);

    // ===== Action Methods =====
    /**
     * Process the selected element
     * Called when valid selection is made
     * @return TRUE if successful
     */
    CATBoolean ProcessSelection(void* iData);

    /**
     * Undo action - restore previous state
     * @return TRUE if undo successful
     */
    CATBoolean UndoSelection(void* iData);

    /**
     * Redo action - reapply operation
     * @return TRUE if redo successful
     */
    CATBoolean RedoSelection(void* iData);

    // Copy constructor and assignment operator (not implemented)
    MySelectCommand(const MySelectCommand&);
    MySelectCommand& operator=(const MySelectCommand&);
};

#endif // MySelectCommand_H
```

**Key Points:**
- Inherit from `CATStateCommand`
- `BuildGraph()` defines state transitions
- Agents capture user input
- Condition methods validate input
- Action methods process data

---

### Step 3: Command Implementation (MySelectCommand.cpp)

#### Includes and Macros

```cpp
// Framework.edu/MyCommandModule.m/src/MySelectCommand.cpp

#include "MySelectCommand.h"

// Agents
#include "CATPathElementAgent.h"
#include "CATIndicationAgent.h"

// State machine
#include "CATDialogAgent.h"
#include "CATDialogState.h"
#include "CATDialogTransition.h"

// Model access
#include "CATPathElement.h"
#include "CATISpecObject.h"

// Geometry
#include "CATMathPoint.h"

// Standard
#include <iostream>
using namespace std;

// ===== OM Macros =====
CATImplementClass(MySelectCommand, Implementation, CATStateCommand, CATNull);

// ===== Condition Method Signature =====
#define CheckCondition(method) \
    (CATStateCommand::ConditionMethod)&MySelectCommand::method, NULL

// ===== Action Method Signature =====
#define ExecuteAction(method) \
    (CATStateCommand::ActionMethod)&MySelectCommand::method, NULL
```

---

#### Constructor

```cpp
MySelectCommand::MySelectCommand()
    : CATStateCommand("MySelectCommand"),
      _pSelectAgent(NULL)
{
    // Command will be exclusive (deactivates other commands)
    // User can cancel with ESC
}
```

**Constructor Behavior:**
- Pass command name to base class
- Initialize all pointers to NULL
- Command is **exclusive** by default (only one active)

---

#### Destructor

```cpp
MySelectCommand::~MySelectCommand()
{
    // Agents are automatically deleted by framework
    _pSelectAgent = NULL;
}
```

**Important:** Don't manually delete agents! Framework handles cleanup.

---

#### BuildGraph() - The Heart of the Command

```cpp
void MySelectCommand::BuildGraph()
{
    // ========================================
    // Step 1: Create Selection Agent
    // ========================================
    _pSelectAgent = new CATPathElementAgent("SelectElement");
    
    // Set filter - only accept geometric elements
    _pSelectAgent->SetElementType("CATISpecObject");
    
    // Allow multiple selections
    _pSelectAgent->SetBehavior(CATDlgEngRepeat);
    
    // Add agent to command
    AddCSOClient(_pSelectAgent);

    // ========================================
    // Step 2: Define States
    // ========================================
    
    // Initial state - waiting for selection
    CATDialogState* pSelectState = GetInitialState("SelectState");
    pSelectState->AddDialogAgent(_pSelectAgent);

    // Processing state - after valid selection
    CATDialogState* pProcessState = AddDialogState("ProcessState");

    // ========================================
    // Step 3: Define Transitions
    // ========================================
    
    // Transition: SelectState -> ProcessState
    // When: User selects element AND validation passes
    CATDialogTransition* pTransition1 = AddTransition(
        pSelectState,           // From state
        pProcessState,          // To state
        IsLastModifiedAgentCondition(_pSelectAgent),  // Trigger
        CheckCondition(CheckSelection)  // Validation
    );
    
    // Action: Execute when entering ProcessState
    pTransition1->AddAction(ExecuteAction(ProcessSelection));

    // Transition: ProcessState -> SelectState (loop back)
    // Allow user to select another element
    AddTransition(
        pProcessState,
        pSelectState,
        NULL  // No condition, immediate transition
    );

    // ========================================
    // Step 4: Set User Prompts
    // ========================================
    
    // Read from .CATNls file
    CATString promptKey = "MySelectCommand.SelectPrompt";
    _pSelectAgent->SetPrompt(promptKey);
}
```

**BuildGraph() Breakdown:**

1. **Create Agents** - Define what user can interact with
2. **Define States** - Different stages of command
3. **Add Transitions** - Define how to move between states
4. **Set Prompts** - Guide the user

---

#### Agent Types Reference

**CATPathElementAgent** - Select model elements
```cpp
_pAgent = new CATPathElementAgent("Name");
_pAgent->SetElementType("CATISpecObject");  // Filter type
_pAgent->SetBehavior(CATDlgEngRepeat);      // Allow multiple
```

**CATIndicationAgent** - Capture mouse clicks
```cpp
_pAgent = new CATIndicationAgent("Name");
_pAgent->SetBehavior(CATDlgEngRepeat);
```

**CATDialogAgent** - Trigger on UI events
```cpp
_pAgent = new CATDialogAgent("Name");
```

---

#### Agent Behaviors

```cpp
// Single selection then stop
_pAgent->SetBehavior(CATDlgEngOneShot);

// Multiple selections (default)
_pAgent->SetBehavior(CATDlgEngRepeat);

// Accumulate selections
_pAgent->SetBehavior(CATDlgEngAcceptOnNotify);
```

---

#### Condition Method - Validate Input

```cpp
CATBoolean MySelectCommand::CheckSelection(void* iData)
{
    // Get selected elements
    CATSO* pSelectedObjects = _pSelectAgent->GetListOfValues();
    
    if (!pSelectedObjects) {
        cout << "No selection" << endl;
        return FALSE;  // Invalid
    }
    
    int count = pSelectedObjects->GetSize();
    if (count == 0) {
        cout << "Empty selection" << endl;
        return FALSE;
    }
    
    // Validate first element
    CATPathElement* pPath = (CATPathElement*)(*pSelectedObjects)[0];
    if (!pPath) {
        cout << "Invalid path" << endl;
        return FALSE;
    }
    
    // Get the actual object
    CATBaseUnknown* pElement = pPath->FindElement(IID_CATISpecObject);
    if (!pElement) {
        cout << "Not a spec object" << endl;
        return FALSE;
    }
    
    pElement->Release();
    
    cout << "Selection valid: " << count << " elements" << endl;
    return TRUE;  // Valid!
}
```

**Return Values:**
- `TRUE` - Condition passes, transition occurs
- `FALSE` - Condition fails, stay in current state

---

#### Action Method - Process Data

```cpp
CATBoolean MySelectCommand::ProcessSelection(void* iData)
{
    cout << "Processing selection..." << endl;
    
    // Get selected elements
    CATSO* pSelectedObjects = _pSelectAgent->GetListOfValues();
    if (!pSelectedObjects) return FALSE;
    
    int count = pSelectedObjects->GetSize();
    
    for (int i = 0; i < count; i++) {
        CATPathElement* pPath = (CATPathElement*)(*pSelectedObjects)[i];
        if (!pPath) continue;
        
        // Get spec object
        CATISpecObject* pSpecObj = NULL;
        HRESULT hr = pPath->FindElement(IID_CATISpecObject, (void**)&pSpecObj);
        
        if (SUCCEEDED(hr) && pSpecObj) {
            // Get object name
            CATUnicodeString name = pSpecObj->GetDisplayName();
            cout << "Selected: " << name.ConvertToChar() << endl;
            
            // ===== YOUR PROCESSING HERE =====
            // Modify geometry, create features, etc.
            
            pSpecObj->Release();
        }
    }
    
    // Clear selection for next iteration
    _pSelectAgent->InitializeAcquisition();
    
    return TRUE;
}
```

**Action Return Values:**
- `TRUE` - Action successful
- `FALSE` - Action failed (command may cancel)

---

#### Activate/Desactivate/Cancel

```cpp
CATStatusChangeRC MySelectCommand::Activate(
    CATCommand* iFromClient,
    CATNotification* iNotification)
{
    cout << "Command activated" << endl;
    
    // Perform initialization
    // ...
    
    return CATStatusChangeRCCompleted;
}

CATStatusChangeRC MySelectCommand::Desactivate(
    CATCommand* iFromClient,
    CATNotification* iNotification)
{
    cout << "Command deactivated" << endl;
    
    // Cleanup resources
    // ...
    
    return CATStatusChangeRCCompleted;
}

CATStatusChangeRC MySelectCommand::Cancel(
    CATCommand* iFromClient,
    CATNotification* iNotification)
{
    cout << "Command cancelled" << endl;
    
    // User pressed ESC
    // Clean up and exit
    
    RequestDelayedDestruction();
    return CATStatusChangeRCCompleted;
}
```

---

### Step 4: CommandHeader Creation

CommandHeaders register commands with CATIA's UI.

#### MyCommandHeader.cpp

```cpp
// Framework.edu/MyCommandModule.m/src/MyCommandHeader.cpp

#include "CATCreateExternalObject.h"
#include "CATCommandHeader.h"
#include "MySelectCommand.h"

/**
 * Create CommandHeader for MySelectCommand
 * This factory function is called by CATIA to create the command
 */
CATCreateClass(MySelectCommandHeader);

/**
 * Constructor - Register the command
 */
MySelectCommandHeader::MySelectCommandHeader()
    : CATCommandHeader("MySelectCommandHeader",
                       "MyFramework",
                       "MySelectCommand",
                       (void*)NULL)
{
}

/**
 * Destructor
 */
MySelectCommandHeader::~MySelectCommandHeader()
{
}
```

---

### Step 5: CommandHeader Declaration

```cpp
// Framework.edu/MyCommandModule.m/LocalInterfaces/CATCommandHeader.h

#ifndef CATCommandHeader_H
#define CATCommandHeader_H

#include "CATCommandHeader.h"

/**
 * CommandHeader for MySelectCommand
 */
class MySelectCommandHeader : public CATCommandHeader
{
public:
    CATDeclareClass;
    
    MySelectCommandHeader();
    virtual ~MySelectCommandHeader();
};

#endif
```

---

### Step 6: Add to Workbench Toolbar

```cpp
// In your workbench class (MyWorkbench.cpp)

void MyWorkbench::CreateCommands()
{
    // Create CommandHeader
    new MySelectCommandHeader();
    
    // Add to toolbar
    AddAccessToCmd("MySelectCommandHeader", "MyToolbar");
    
    // Set icon and help
    SetAccessCommand("MySelectCommandHeader", 
                     "MySelectCommand",  // Command name
                     "MySelectCommand.ShortHelp",  // Tooltip
                     "MySelectCommand.LongHelp");   // Status bar help
}
```

---

### Step 7: Resource Files

#### MyFramework.CATNls

```
# Command prompts
MySelectCommand.SelectPrompt = "Select a geometric element";

# Help text
MySelectCommand.ShortHelp = "Select Element";
MySelectCommand.LongHelp = "Interactive command to select geometric elements";

# Messages
MySelectCommand.Success = "Element processed successfully";
MySelectCommand.Error = "Invalid selection";
```

---

## 🎛️ Advanced State Machine Patterns

### Pattern 1: Two-Step Selection

Select two elements in sequence:

```cpp
void MyTwoStepCommand::BuildGraph()
{
    // Agent 1: Select first element
    _pFirstAgent = new CATPathElementAgent("FirstElement");
    _pFirstAgent->SetElementType("CATISpecObject");
    AddCSOClient(_pFirstAgent);
    
    // Agent 2: Select second element
    _pSecondAgent = new CATPathElementAgent("SecondElement");
    _pSecondAgent->SetElementType("CATISpecObject");
    AddCSOClient(_pSecondAgent);
    
    // State 1: Select first
    CATDialogState* pState1 = GetInitialState("SelectFirst");
    pState1->AddDialogAgent(_pFirstAgent);
    
    // State 2: Select second
    CATDialogState* pState2 = AddDialogState("SelectSecond");
    pState2->AddDialogAgent(_pSecondAgent);
    
    // State 3: Process
    CATDialogState* pState3 = AddDialogState("Process");
    
    // Transition: State1 -> State2
    AddTransition(
        pState1,
        pState2,
        IsLastModifiedAgentCondition(_pFirstAgent),
        CheckCondition(CheckFirst)
    );
    
    // Transition: State2 -> State3
    CATDialogTransition* pTrans = AddTransition(
        pState2,
        pState3,
        IsLastModifiedAgentCondition(_pSecondAgent),
        CheckCondition(CheckSecond)
    );
    pTrans->AddAction(ExecuteAction(ProcessBoth));
    
    // Set prompts
    _pFirstAgent->SetPrompt("MyCmd.SelectFirst");
    _pSecondAgent->SetPrompt("MyCmd.SelectSecond");
}
```

---

### Pattern 2: Optional Dialog

Show dialog with optional confirmation:

```cpp
void MyDialogCommand::BuildGraph()
{
    // Selection agent
    _pSelectAgent = new CATPathElementAgent("Select");
    AddCSOClient(_pSelectAgent);
    
    // Dialog agent (triggered by button)
    _pDialogAgent = new CATDialogAgent("Dialog");
    _pDialogAgent->SetBehavior(CATDlgEngOneShot);
    AddCSOClient(_pDialogAgent);
    
    // States
    CATDialogState* pSelectState = GetInitialState("Select");
    pSelectState->AddDialogAgent(_pSelectAgent);
    
    CATDialogState* pDialogState = AddDialogState("ShowDialog");
    pDialogState->AddDialogAgent(_pDialogAgent);
    
    CATDialogState* pProcessState = AddDialogState("Process");
    
    // Select -> Dialog
    CATDialogTransition* pTrans1 = AddTransition(
        pSelectState,
        pDialogState,
        IsLastModifiedAgentCondition(_pSelectAgent)
    );
    pTrans1->AddAction(ExecuteAction(ShowDialog));
    
    // Dialog -> Process (on OK)
    CATDialogTransition* pTrans2 = AddTransition(
        pDialogState,
        pProcessState,
        IsLastModifiedAgentCondition(_pDialogAgent),
        CheckCondition(CheckDialogOK)
    );
    pTrans2->AddAction(ExecuteAction(ProcessWithDialog));
    
    // Dialog -> Select (on Cancel)
    AddTransition(
        pDialogState,
        pSelectState,
        NULL  // Cancel returns to selection
    );
}
```

---

### Pattern 3: Repeat Until Complete

Continue selecting until user explicitly finishes:

```cpp
void MyRepeatCommand::BuildGraph()
{
    _pSelectAgent = new CATPathElementAgent("Select");
    _pSelectAgent->SetBehavior(CATDlgEngRepeat);  // Allow multiple
    AddCSOClient(_pSelectAgent);
    
    // Finish button agent
    _pFinishAgent = new CATDialogAgent("Finish");
    AddCSOClient(_pFinishAgent);
    
    // Select state (initial, repeatable)
    CATDialogState* pSelectState = GetInitialState("Selecting");
    pSelectState->AddDialogAgent(_pSelectAgent);
    pSelectState->AddDialogAgent(_pFinishAgent);
    
    // Process state (final)
    CATDialogState* pProcessState = AddDialogState("Process");
    
    // Loop: Select -> Select (keep selecting)
    CATDialogTransition* pLoop = AddTransition(
        pSelectState,
        pSelectState,
        IsLastModifiedAgentCondition(_pSelectAgent)
    );
    pLoop->AddAction(ExecuteAction(AddToSelection));
    
    // Finish: Select -> Process
    CATDialogTransition* pFinish = AddTransition(
        pSelectState,
        pProcessState,
        IsLastModifiedAgentCondition(_pFinishAgent)
    );
    pFinish->AddAction(ExecuteAction(ProcessAll));
}
```

---

## 🔍 Transition Conditions

### Standard Conditions

```cpp
// Agent was just modified
IsLastModifiedAgentCondition(_pAgent)

// Agent has value
IsOutputSetCondition(_pAgent)

// Custom condition method
CheckCondition(MyMethod)

// Combine conditions with AND
Condition1 && Condition2

// Combine with OR
Condition1 || Condition2
```

---

## ⚙️ Common Agent Settings

### Element Type Filters

```cpp
// Any spec object
_pAgent->SetElementType("CATISpecObject");

// Geometry only
_pAgent->SetElementType("CATIGSMGeometry");

// Surfaces only
_pAgent->SetElementType("CATISurface");

// Lines only
_pAgent->SetElementType("CATILine");

// Points only
_pAgent->SetElementType("CATIPoint");
```

---

### Selection Behaviors

```cpp
// Single selection
_pAgent->SetBehavior(CATDlgEngOneShot);

// Multiple (keep selecting)
_pAgent->SetBehavior(CATDlgEngRepeat);

// Accumulate until confirmed
_pAgent->SetBehavior(CATDlgEngAcceptOnNotify);

// With preselection support
_pAgent->SetBehavior(CATDlgEngWithPrevalue);
```

---

## 🎨 Visual Feedback

### Highlight Selected Elements

```cpp
void MyCommand::HighlightSelection()
{
    CATSO* pObjects = _pSelectAgent->GetListOfValues();
    if (!pObjects) return;
    
    for (int i = 0; i < pObjects->GetSize(); i++) {
        CATPathElement* pPath = (CATPathElement*)(*pObjects)[i];
        
        // Set highlight color
        CATVisProperties props;
        props.SetColor(255, 0, 0);  // Red
        props.SetLineType(2);       // Dashed
        
        // Apply to element
        // ... use CATIVisProperties
    }
}
```

---

### Show Temporary Geometry

```cpp
void MyCommand::ShowPreview()
{
    // Create temporary display
    // ... create CATGraphicPrimitive
    // ... add to temporary viewer
}
```

---

## 🔧 Undo/Redo Support

```cpp
CATBoolean MyCommand::UndoSelection(void* iData)
{
    cout << "Undo operation" << endl;
    
    // Restore previous state
    // Delete created features
    // Restore modified geometry
    
    return TRUE;
}

CATBoolean MyCommand::RedoSelection(void* iData)
{
    cout << "Redo operation" << endl;
    
    // Reapply operation
    // Recreate features
    
    return TRUE;
}
```

Register undo/redo:
```cpp
// In action method
SetUndoMode(UndoSelection, RedoSelection);
```

---

## 🐛 Common Errors and Solutions

### ❌ Error: Agent not triggered

**Problem:**
```cpp
// Agent created but not added to state
_pAgent = new CATPathElementAgent("Agent");
// Missing: pState->AddDialogAgent(_pAgent);
```

**Solution:**
```cpp
CATDialogState* pState = GetInitialState("State");
pState->AddDialogAgent(_pAgent);  // Must add!
```

---

### ❌ Error: Transition never fires

**Problem:**
```cpp
// Wrong condition
AddTransition(pState1, pState2, NULL);  // No trigger!
```

**Solution:**
```cpp
// Specify condition
AddTransition(
    pState1, 
    pState2,
    IsLastModifiedAgentCondition(_pAgent)
);
```

---

### ❌ Error: Command doesn't start

**Problem:**
```cpp
// BuildGraph() not called
// or missing CATImplementClass
```

**Solution:**
```cpp
// In .cpp file:
CATImplementClass(MyCommand, Implementation, CATStateCommand, CATNull);

// BuildGraph() is called automatically by framework
```

---

### ❌ Error: Selection returns NULL

**Problem:**
```cpp
// Agent not set up correctly
_pAgent->SetElementType("");  // Empty filter
```

**Solution:**
```cpp
_pAgent->SetElementType("CATISpecObject");  // Valid type
```

---

## 📊 Complete Example: Line Creator

Create a line between two selected points:

```cpp
// MyLineCommand.h
class MyLineCommand : public CATStateCommand
{
    CATDeclareClass;
    
public:
    MyLineCommand();
    virtual ~MyLineCommand();
    virtual void BuildGraph();
    
private:
    CATPathElementAgent* _pPoint1Agent;
    CATPathElementAgent* _pPoint2Agent;
    
    CATBoolean CheckPoint1(void* iData);
    CATBoolean CheckPoint2(void* iData);
    CATBoolean CreateLine(void* iData);
    
    CATMathPoint _point1;
};

// MyLineCommand.cpp
void MyLineCommand::BuildGraph()
{
    // Create agents
    _pPoint1Agent = new CATPathElementAgent("Point1");
    _pPoint1Agent->SetElementType("CATIPoint");
    _pPoint1Agent->SetBehavior(CATDlgEngOneShot);
    AddCSOClient(_pPoint1Agent);
    
    _pPoint2Agent = new CATPathElementAgent("Point2");
    _pPoint2Agent->SetElementType("CATIPoint");
    _pPoint2Agent->SetBehavior(CATDlgEngOneShot);
    AddCSOClient(_pPoint2Agent);
    
    // States
    CATDialogState* pState1 = GetInitialState("SelectPoint1");
    pState1->AddDialogAgent(_pPoint1Agent);
    
    CATDialogState* pState2 = AddDialogState("SelectPoint2");
    pState2->AddDialogAgent(_pPoint2Agent);
    
    CATDialogState* pState3 = AddDialogState("CreateLine");
    
    // Transitions
    CATDialogTransition* pTrans1 = AddTransition(
        pState1, pState2,
        IsLastModifiedAgentCondition(_pPoint1Agent),
        CheckCondition(CheckPoint1)
    );
    
    CATDialogTransition* pTrans2 = AddTransition(
        pState2, pState3,
        IsLastModifiedAgentCondition(_pPoint2Agent),
        CheckCondition(CheckPoint2)
    );
    pTrans2->AddAction(ExecuteAction(CreateLine));
    
    // Prompts
    _pPoint1Agent->SetPrompt("Select first point");
    _pPoint2Agent->SetPrompt("Select second point");
}

CATBoolean MyLineCommand::CheckPoint1(void* iData)
{
    CATSO* pSO = _pPoint1Agent->GetListOfValues();
    if (!pSO || pSO->GetSize() == 0) return FALSE;
    
    CATPathElement* pPath = (CATPathElement*)(*pSO)[0];
    // Extract coordinates and store in _point1
    
    return TRUE;
}

CATBoolean MyLineCommand::CreateLine(void* iData)
{
    // Get second point
    CATSO* pSO = _pPoint2Agent->GetListOfValues();
    CATPathElement* pPath = (CATPathElement*)(*pSO)[0];
    
    // Extract point2 coordinates
    CATMathPoint point2;
    // ...
    
    // Create line feature between _point1 and point2
    // ... use geometry factory
    
    cout << "Line created successfully" << endl;
    return TRUE;
}
```

---

## ✅ Command Development Checklist

Before compiling:

- [ ] IdentityCard.h includes `InteractiveInterfaces`
- [ ] Header declares `CATDeclareClass`
- [ ] Implementation has `CATImplementClass`
- [ ] BuildGraph() creates all agents
- [ ] Agents added to states with `AddDialogAgent()`
- [ ] Agents added to command with `AddCSOClient()`
- [ ] Transitions defined between states
- [ ] Condition methods return CATBoolean
- [ ] Action methods return CATBoolean
- [ ] Prompts set for all agents
- [ ] CommandHeader created and registered
- [ ] Resource files created (.CATNls)

---

## 🔗 See Also

- **COMMAND_QUICK_REFERENCE.md** - Quick lookup for agents and patterns
- **EXAMPLE_DIALOG.md** - Dialog development tutorial
- **AI_GUIDE.md** - AI generation rules
- **TROUBLESHOOTING_FLOWCHART.md** - Fix compile errors

---

**Complete template files available in:** `templates/command/`
