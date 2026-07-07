@echo off
REM ========================================
REM Code Reuse Checker for CATIA CAA
REM Prevents "reinventing the wheel"
REM ========================================

setlocal enabledelayedexpansion

if "%1"=="" (
    echo Usage: check_code_reuse.bat [ComponentName] [InterfaceName]
    echo Example: check_code_reuse.bat Calculator ICalculator
    exit /b 1
)

set COMPONENT_NAME=%1
set INTERFACE_NAME=%2
REM Derive workspace from script location (go up 4 levels from tools/)
set WORKSPACE=%~dp0..\..\..\..\..

echo ========================================
echo Code Reuse Analysis
echo ========================================
echo.
echo Checking for: %COMPONENT_NAME%
if not "%INTERFACE_NAME%"=="" echo Interface: %INTERFACE_NAME%
echo.

REM Check 1: Search existing components
echo [1/5] Searching existing components...
set FOUND_COMPONENTS=0
for /r "%WORKSPACE%" %%f in (*%COMPONENT_NAME%.cpp) do (
    echo   FOUND: %%f
    set /a FOUND_COMPONENTS+=1
)
if %FOUND_COMPONENTS% gtr 0 (
    echo   WARNING: %FOUND_COMPONENTS% similar component(s) found!
    echo   Consider reusing existing code.
    echo.
) else (
    echo   OK: No duplicate components found
    echo.
)

REM Check 2: Search similar interfaces
if not "%INTERFACE_NAME%"=="" (
    echo [2/5] Searching similar interfaces...
    set FOUND_INTERFACES=0
    for /r "%WORKSPACE%" %%f in (%INTERFACE_NAME%.h) do (
        echo   FOUND: %%f
        set /a FOUND_INTERFACES+=1
    )
    if !FOUND_INTERFACES! gtr 0 (
        echo   WARNING: !FOUND_INTERFACES! similar interface(s) found!
        echo.
    ) else (
        echo   OK: No duplicate interfaces found
        echo.
    )
)

REM Check 3: Search in CAASystem.edu samples
echo [3/5] Checking CAASystem.edu samples...
if exist "%WORKSPACE%\CAASystem.edu" (
    dir /b /s "%WORKSPACE%\CAASystem.edu\*%COMPONENT_NAME%*" 2>nul | findstr /i ".h .cpp" >nul
    if !errorlevel! equ 0 (
        echo   INFO: Similar examples found in CAASystem.edu
        dir /b /s "%WORKSPACE%\CAASystem.edu\*%COMPONENT_NAME%*" 2>nul | findstr /i ".h .cpp"
        echo.
    ) else (
        echo   OK: No examples in CAASystem.edu
        echo.
    )
) else (
    echo   WARNING: CAASystem.edu not found
    echo.
)

REM Check 4: Common anti-patterns
echo [4/5] Checking for anti-patterns...
set WARNINGS=0

REM Check if creating custom collection
echo %COMPONENT_NAME% | findstr /i "List Array Vector Map" >nul
if !errorlevel! equ 0 (
    echo   WARNING: Component name suggests custom collection
    echo   Consider using CATListOf instead!
    set /a WARNINGS+=1
)

REM Check if creating custom math
echo %COMPONENT_NAME% | findstr /i "Math Point Vector Matrix Transform" >nul
if !errorlevel! equ 0 (
    echo   WARNING: Component name suggests custom math
    echo   Consider using CATMath* classes instead!
    set /a WARNINGS+=1
)

REM Check if creating custom string
echo %COMPONENT_NAME% | findstr /i "String Text" >nul
if !errorlevel! equ 0 (
    echo   WARNING: Component name suggests custom string handling
    echo   Consider using CATUnicodeString instead!
    set /a WARNINGS+=1
)

if %WARNINGS% equ 0 (
    echo   OK: No anti-patterns detected
)
echo.

REM Check 5: Suggest CAA libraries
echo [5/5] Suggested CAA libraries:
echo   - System (always required)
if not "%WARNINGS%"=="0" (
    echo %COMPONENT_NAME% | findstr /i "Math Point Vector Matrix" >nul
    if !errorlevel! equ 0 echo   - Mathematics (for math operations)

    echo %COMPONENT_NAME% | findstr /i "Geometry Surface Curve" >nul
    if !errorlevel! equ 0 echo   - GeometricObjects (for geometry)

    echo %COMPONENT_NAME% | findstr /i "Dialog UI Button" >nul
    if !errorlevel! equ 0 echo   - CATDialogEngine (for UI)
)
echo   - JS0GROUP (core services)
echo.

REM Summary
echo ========================================
echo Summary
echo ========================================
if %FOUND_COMPONENTS% gtr 0 (
    echo [!] DUPLICATE COMPONENTS FOUND - Review before creating!
    exit /b 2
)
if %WARNINGS% gtr 0 (
    echo [!] POTENTIAL ANTI-PATTERN - Consider using CAA libraries!
    exit /b 1
)
echo [OK] No issues detected - proceed with creation
exit /b 0
