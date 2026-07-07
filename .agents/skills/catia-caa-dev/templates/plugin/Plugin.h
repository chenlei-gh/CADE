// COPYRIGHT DASSAULT SYSTEMES YYYY
#ifndef PluginName_h
#define PluginName_h

// System Framework
#include "CATBaseUnknown.h"
#include "CATIPlugin.h"

/**
 * @brief PluginName - CATIA Plugin
 * 
 * Plugins provide a standard mechanism for extending CATIA functionality.
 * They are loaded dynamically by the plugin framework.
 * 
 * Lifecycle:
 *   Loaded   → CATIA discovers and loads the plugin DLL
 *   Init     → Plugin initializes and registers extensions
 *   Run      → Plugin executes its main functionality  
 *   Unload   → Plugin cleans up resources
 */
class PluginName : public CATBaseUnknown, public CATIPlugin
{
    CATDeclareClass;

public:
    PluginName();
    virtual ~PluginName();

    /**
     * @brief Init - Initialize plugin
     * Called when plugin is first loaded
     * @return HRESULT
     */
    virtual HRESULT Init();

    /**
     * @brief Run - Execute plugin logic
     * @return HRESULT
     */
    virtual HRESULT Run();

    /**
     * @brief Uninit - Cleanup before unload
     * @return HRESULT
     */
    virtual HRESULT Uninit();

    /**
     * @brief GetPluginInfo - Return plugin metadata
     * @return Plugin information string
     */
    virtual CATString GetPluginInfo();

private:
    CATBoolean _isInitialized;

    PluginName(const PluginName&);
    PluginName& operator=(const PluginName&);
};

#endif
