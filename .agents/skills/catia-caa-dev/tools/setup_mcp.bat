@echo off
REM ================================================================================
REM CADE MCP Auto-Setup — One-click MCP configuration for all editors
REM ================================================================================

echo.
echo ========================================================
echo   CADE MCP Auto-Setup
echo ========================================================
echo.
echo This will auto-detect your installed editors and configure
echo MCP (Model Context Protocol) for CADE integration.
echo.
echo Supported editors: Zed, Claude Desktop, Cursor, VS Code, Windsurf
echo.
pause

python "%~dp0setup_mcp.py" %*

echo.
pause
