@echo off
REM ================================================================================
REM CADE Workspace Environment Setup
REM ================================================================================
REM Automatically configure workspace environment (CATIA paths and settings)

echo.
echo ========================================================
echo   CADE Workspace Environment Setup
echo ========================================================
echo.

python "%~dp0setup_environment.py" %*

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
