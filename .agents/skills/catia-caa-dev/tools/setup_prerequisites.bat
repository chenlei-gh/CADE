@echo off
REM ================================================================================
REM CADE Workspace Prerequisites Setup
REM ================================================================================
REM Automatically configure workspace prerequisites (replaces manual CATIA dialog)

echo.
echo ========================================================
echo   CADE Workspace Prerequisites Setup
echo ========================================================
echo.

python "%~dp0setup_prerequisites.py" %*

if errorlevel 1 (
    echo.
    echo Setup failed. See error above.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   Setup Complete!
echo ========================================================
echo.
pause
