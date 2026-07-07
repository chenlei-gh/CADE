// COPYRIGHT DASSAULT SYSTEMES 2026
#ifndef <CommandHeaderClassName>_h
#define <CommandHeaderClassName>_h

#include "CATCommandHeader.h"

/**
 * @brief Command header for toolbar/menu integration
 * 
 * This class registers the command with CATIA's command infrastructure:
 * - Creates toolbar button
 * - Defines icon
 * - Sets tooltip/help text
 * - Manages command lifecycle
 */
class <CommandHeaderClassName>
{
public:
    /**
     * @brief Create and register command header
     * Call this during workbench initialization
     */
    static void CreateCommandHeader();

private:
    // Prevent instantiation
    <CommandHeaderClassName>();
    ~<CommandHeaderClassName>();
};

#endif
