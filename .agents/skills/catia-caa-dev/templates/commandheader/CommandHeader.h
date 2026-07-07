// COPYRIGHT DASSAULT SYSTEMES YYYY
#ifndef CommandHeaderName_h
#define CommandHeaderName_h

// System Framework
#include "CATCommandHeader.h"

/**
 * @brief CommandHeaderName - Command header for CommandClassName
 * 
 * Command headers are responsible for:
 * - Registering commands with CATIA
 * - Binding commands to menus/toolbars
 * - Creating command instances on demand
 * 
 * Registration:
 *   Command header is instantiated automatically when CATIA starts.
 *   No manual creation needed.
 */
class CommandHeaderName : public CATCommandHeader
{
public:
    /**
     * @brief Constructor
     * @param iHeaderName Header identifier string
     */
    CommandHeaderName(const CATString& iHeaderName);

    /**
     * @brief Destructor
     */
    virtual ~CommandHeaderName();

    /**
     * @brief CreateCommand - Factory method
     * Creates the actual command instance when user triggers it
     * @return New command object
     */
    virtual CATCommand* CreateCommand();

    /**
     * @brief GetCommandName - Return command name for menus
     * @return Command name string
     */
    virtual CATString GetCommandName();

    /**
     * @brief GetCommandIcon - Return path to command icon
     * @return Icon resource path
     */
    virtual CATString GetCommandIcon();

    /**
     * @brief IsCommandEnabled - Check if command is available
     * @return TRUE if enabled
     */
    virtual CATBoolean IsCommandEnabled();

private:
    CATString _headerName;
    CATString _commandName;
    CATString _iconPath;

    // Copy constructor, not implemented
    CommandHeaderName(const CommandHeaderName& iObjectToCopy);

    // Assignment operator, not implemented
    CommandHeaderName& operator=(const CommandHeaderName& iObjectToCopy);
};

#endif
