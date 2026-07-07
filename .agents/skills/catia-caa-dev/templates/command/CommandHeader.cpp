// COPYRIGHT DASSAULT SYSTEMES 2026
#include "<CommandHeaderClassName>.h"
#include "CATCommandHeader.h"
#include "CATAfrCommandHeader.h"

// Command class
#include "<CommandClassName>.h"

//-----------------------------------------------------------------------------
// Create Command Header
//-----------------------------------------------------------------------------
void <CommandHeaderClassName>::CreateCommandHeader()
{
    // Create command header using macro
    // Syntax: MacDeclareHeader(HeaderName);
    MacDeclareHeader(<CommandHeaderName>);

    // Create header instance
    // Parameters:
    // 1. Header name (identifier)
    // 2. Command class name
    // 3. Command name (for resources)
    // 4. Mode flags (CATCommandModeExclusive, CATCommandModeShared, etc.)
    new CATAfrCommandHeader(
        "<CommandHeaderName>",                    // Header ID
        "<CommandClassName>",                     // Command class
        "<CommandClassName>",                     // Resource name (for NLS)
        (void*)NULL,                              // Argument (usually NULL)
        "<FrameworkName>",                        // Framework name (for icon path)
        CATFrmAvailable                           // Availability mode
    );
}

//-----------------------------------------------------------------------------
// Alternative: Using Macro (Simpler)
//-----------------------------------------------------------------------------
/*
// In your workbench CreateCommands() method:

#include "CATCommandHeader.h"

MacDeclareHeader(<CommandHeaderName>);

CATCommandHeader* pHeader = new CATAfrCommandHeader(
    "<CommandHeaderName>",
    "<CommandClassName>", 
    "<CommandClassName>",
    (void*)NULL,
    "<FrameworkName>",
    CATFrmAvailable
);

// Set icon (optional, reads from .CATRsc if not set)
// pHeader->SetIcon("IconName");

// Set help message (optional, reads from .CATNls if not set)
// pHeader->SetShortHelp("Command short help");
// pHeader->SetLongHelp("Command detailed help");

*/
