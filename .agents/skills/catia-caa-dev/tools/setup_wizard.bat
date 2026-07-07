@echo off
REM ================================================================================
REM CATIA CAA Environment Setup Wizard - For Users
REM ================================================================================
REM Purpose: Interactive CATIA environment configuration
REM Audience: New users, manual configuration needed
REM Output: caa_env_config.txt
REM Version: 2.4.5
REM ================================================================================

setlocal enabledelayedexpansion

echo.
echo ========================================================
echo   CATIA CAA Environment Setup Wizard
echo ========================================================
echo.
echo This wizard will help you configure your CAA development
echo environment for use with the Zed AI Skill.
echo.
pause

REM --- Step 1: Auto-detect CATIA ---
echo.
echo [Step 1/4] Detecting CATIA installation...
echo.

set "AUTO_DETECTED="
set "CATIA_VERSION="

REM Try registry first (with timeout)
for /f "tokens=2*" %%a in ('reg query "HKLM\Software\Dassault Systemes\CATIA" /s 2^>nul ^| findstr /i "InstallDir" 2^>nul') do (
    set "TEMP_PATH=%%b"
    set "TEMP_PATH=!TEMP_PATH:"=!"
    if "!TEMP_PATH:~-1!"=="\" set "TEMP_PATH=!TEMP_PATH:~0,-1!"

    if exist "!TEMP_PATH!\CAADoc\Doc" (
        set "AUTO_DETECTED=!TEMP_PATH!"
        goto :detected
    )
)

REM Try common paths
for %%d in (
    "C:\Program Files\Dassault Systemes\B28"
    "C:\Program Files\Dassault Systemes\B29"
    "C:\Program Files\Dassault Systemes\B30"
    "C:\Program Files (x86)\Dassault Systemes\B28"
    "D:\CATIA\B28"
    "D:\CATIA\B29"
    "E:\CATIA\B28"
) do (
    if exist "%%~d\CAADoc\Doc" (
        set "AUTO_DETECTED=%%~d"
        goto :detected
    )
)

:detected
if defined AUTO_DETECTED (
    echo   ^[Auto-detected^] !AUTO_DETECTED!
    echo.
    set /p confirm="   Use this path? (Y/n): "
    if /i "!confirm!"=="n" goto :manual_input
    if /i "!confirm!"=="no" goto :manual_input
    set "CATIA_PATH=!AUTO_DETECTED!"
    goto :validate_path
) else (
    echo   No CATIA installation detected automatically.
    goto :manual_input
)

:manual_input
echo.
echo   Please select your CATIA installation:
echo.
echo   Common paths:
echo     1. C:\Program Files\Dassault Systemes\B28
echo     2. C:\Program Files\Dassault Systemes\B29
echo     3. C:\Program Files\Dassault Systemes\B30
echo     4. D:\CATIA\B28
echo     5. E:\CATIA\B28
echo     6. Custom path (manual input)
echo.
set /p choice="   Select (1-6): "

if "%choice%"=="1" set "CATIA_PATH=C:\Program Files\Dassault Systemes\B28"
if "%choice%"=="2" set "CATIA_PATH=C:\Program Files\Dassault Systemes\B29"
if "%choice%"=="3" set "CATIA_PATH=C:\Program Files\Dassault Systemes\B30"
if "%choice%"=="4" set "CATIA_PATH=D:\CATIA\B28"
if "%choice%"=="5" set "CATIA_PATH=E:\CATIA\B28"
if "%choice%"=="6" (
    echo.
    set /p "CATIA_PATH=   Enter full CATIA path: "
)

if not defined CATIA_PATH (
    echo.
    echo   ERROR: Invalid selection. Please try again.
    timeout /t 2 >nul
    goto :manual_input
)

:validate_path
echo.
echo [Step 2/4] Validating path...
echo.

REM Remove quotes if present
set "CATIA_PATH=%CATIA_PATH:"=%"

REM Remove trailing backslash
if "%CATIA_PATH:~-1%"=="\" set "CATIA_PATH=%CATIA_PATH:~0,-1%"

REM Check path exists
if not exist "%CATIA_PATH%" (
    echo   ERROR: Path does not exist: %CATIA_PATH%
    echo.
    set /p retry="   Try again? (Y/n): "
    if /i "!retry!"=="y" goto :manual_input
    if /i "!retry!"=="" goto :manual_input
    echo.
    echo   Setup cancelled.
    pause
    exit /b 1
)

REM Check CAA components
if not exist "%CATIA_PATH%\CAADoc\Doc" (
    echo   ERROR: Not a valid CATIA CAA installation
    echo   Missing: CAADoc\Doc
    echo.
    set /p retry="   Try again? (Y/n): "
    if /i "!retry!"=="y" goto :manual_input
    if /i "!retry!"=="" goto :manual_input
    echo.
    echo   Setup cancelled.
    pause
    exit /b 1
)

echo   ^[OK^] Valid CATIA CAA installation found

REM --- Step 3: Detect Version ---
echo.
echo [Step 3/4] Detecting version...
echo.

set "VERSION=Unknown"
set "PATTERN=BOA"
set "VERSION_WARNING="

REM Check for B-series
echo %CATIA_PATH% | findstr /i "B28" >nul && set "VERSION=B28"
echo %CATIA_PATH% | findstr /i "B29" >nul && set "VERSION=B29"
echo %CATIA_PATH% | findstr /i "B30" >nul && set "VERSION=B30"

REM Check for R-series
for %%v in (R19 R20 R21 R22 R23 R24 R25 R26 R27 R28 R29 R30) do (
    echo %CATIA_PATH% | findstr /i "%%v" >nul
    if !errorlevel!==0 (
        set "VERSION=%%v"
        if "%%v"=="R19" (
            set "PATTERN=TIE"
            set "VERSION_WARNING=WARNING: R19 requires TIE pattern (not supported by this skill)"
        )
        if "%%v"=="R20" (
            set "PATTERN=TIE"
            set "VERSION_WARNING=WARNING: R20 requires TIE pattern (not supported by this skill)"
        )
        if "%%v"=="R21" (
            set "PATTERN=TIE"
            set "VERSION_WARNING=WARNING: R21 requires TIE pattern (not supported by this skill)"
        )
        if "%%v"=="R22" set "PATTERN=BOA"
        if "%%v"=="R23" set "PATTERN=BOA"
        if "%%v"=="R24" set "PATTERN=BOA"
        if "%%v"=="R25" set "PATTERN=BOA"
        if "%%v"=="R26" set "PATTERN=BOA"
        if "%%v"=="R27" set "PATTERN=BOA"
        if "%%v"=="R28" set "PATTERN=BOA"
        if "%%v"=="R29" set "PATTERN=BOA"
        if "%%v"=="R30" set "PATTERN=BOA"
    )
)

echo   Version: %VERSION%
echo   Recommended Pattern: %PATTERN%

if defined VERSION_WARNING (
    echo.
    echo   ^!^! %VERSION_WARNING%
    echo.
    set /p continue="   Continue anyway? (y/N): "
    if /i not "!continue!"=="y" (
        echo.
        echo   Setup cancelled.
        pause
        exit /b 1
    )
)

REM --- Step 4: Verify Build Tools ---
echo.
echo [Step 4/4] Checking build tools...
echo.

set "MKMK_FOUND=0"
if exist "%CATIA_PATH%\intel_a\code\bin\mkmk.exe" (
    echo   ^[OK^] mkmk.exe found at intel_a\code\bin\
    set "MKMK_PATH=%CATIA_PATH%\intel_a\code\bin\mkmk.exe"
    set "MKMK_FOUND=1"
) else if exist "%CATIA_PATH%\win_b64\code\bin\mkmk.exe" (
    echo   ^[OK^] mkmk.exe found at win_b64\code\bin\
    set "MKMK_PATH=%CATIA_PATH%\win_b64\code\bin\mkmk.exe"
    set "MKMK_FOUND=1"
) else (
    echo   ^[WARNING^] mkmk.exe not found
    echo   You may need to install CAA RADE tools
)

if exist "%CATIA_PATH%\CAADoc\Doc\online" (
    echo   ^[OK^] CAA documentation found
) else (
    echo   ^[WARNING^] CAA documentation not found
)

REM --- Generate Configuration File ---
echo.
echo Generating configuration file...
echo.

set "CONFIG_FILE=%~dp0caa_env_config.txt"

(
    echo # CATIA CAA Environment Configuration
    echo # Generated by Setup Wizard
    echo # Date: %DATE% %TIME%
    echo # Machine: %COMPUTERNAME%
    echo #
    echo # DO NOT EDIT MANUALLY - Use setup_wizard.bat to regenerate
    echo.
    echo CATIA_INSTALL=%CATIA_PATH%
    echo CATIA_VERSION=%VERSION%
    echo RECOMMENDED_PATTERN=%PATTERN%
    echo WORKSPACE=%CD%
    echo.
    echo # Documentation Paths
    echo DOC_API=%CATIA_PATH%\CAADoc\Doc\generated\refman
    echo DOC_QUICKREF=%CATIA_PATH%\CAADoc\Doc\online\CAASysQuickRefs\CAASysToc.htm
    echo DOC_SAMPLES=%CATIA_PATH%\CAADoc\CAADocJavaScript\generated\samples
    echo.
    echo # Build Tools
    echo TCK_INIT=%CATIA_PATH%\CAADoc\CNext\code\command\tck_init.bat
    if %MKMK_FOUND%==1 echo MKMK=%MKMK_PATH%
    echo.
    echo # Detection Info
    echo DETECTED_AT=%DATE% %TIME%
    echo DETECTED_BY=setup_wizard.bat
) > "%CONFIG_FILE%"

echo   ^[OK^] Configuration saved to:
echo        %CONFIG_FILE%

REM --- Summary ---
echo.
echo ========================================================
echo   Setup Complete!
echo ========================================================
echo.
echo Configuration Summary:
echo   CATIA Path: %CATIA_PATH%
echo   Version:    %VERSION%
echo   Pattern:    %PATTERN%
echo   Config:     %CONFIG_FILE%
echo.
echo Next Steps:
echo   1. Return to Zed Editor
echo   2. Ask AI to create a CAA component
echo   3. AI will automatically use this configuration
echo.

if defined VERSION_WARNING (
    echo IMPORTANT:
    echo   %VERSION_WARNING%
    echo   Consider upgrading to R22+ or B28+ for full support.
    echo.
)

echo ========================================================
echo.
pause
