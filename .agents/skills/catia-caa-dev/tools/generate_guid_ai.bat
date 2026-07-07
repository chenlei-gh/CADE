@echo off
REM ================================================================================
REM GUID Generator for CAA Components - AI Tool
REM ================================================================================
REM Purpose: Generate unique IID GUID for CAA interfaces
REM Caller:  Zed AI Agent (via Skill)
REM Output:  Machine-readable IID declaration
REM ================================================================================

setlocal enabledelayedexpansion

REM --- Check Arguments ---
if "%~1"=="" (
    echo ERROR=Missing interface name argument
    echo USAGE=generate_guid_ai.bat ^<InterfaceName^>
    exit /b 1
)

set "INTERFACE_NAME=%~1"

REM --- Validate Interface Name ---
echo %INTERFACE_NAME% | findstr /r "^I" >nul
if errorlevel 1 (
    echo WARNING=Interface name should start with I (e.g., ICalculator)
)

REM --- Check PowerShell Availability ---
powershell -Command "exit 0" >nul 2>&1
if errorlevel 1 (
    echo ERROR=PowerShell not available - cannot generate GUID
    echo SOLUTION=Use online GUID generator or install PowerShell
    exit /b 1
)

REM --- Generate GUID ---
for /f "delims=" %%G in ('powershell -Command "[guid]::NewGuid().ToString().ToUpper()"') do set "GUID=%%G"

REM --- Parse GUID Components ---
for /f "tokens=1,2,3,4,5 delims=-" %%A in ("!GUID!") do (
    set "PART1=%%A"
    set "PART2=%%B"
    set "PART3=%%C"
    set "PART4=%%D"
    set "PART5=%%E"
)

REM --- Convert to Byte Array ---
set "BYTE1=!PART4:~0,2!"
set "BYTE2=!PART4:~2,2!"
set "BYTE3=!PART5:~0,2!"
set "BYTE4=!PART5:~2,2!"
set "BYTE5=!PART5:~4,2!"
set "BYTE6=!PART5:~6,2!"
set "BYTE7=!PART5:~8,2!"
set "BYTE8=!PART5:~10,2!"

REM --- Output Machine-Readable Format ---
echo INTERFACE_NAME=%INTERFACE_NAME%
echo GUID_STANDARD=%GUID%
echo.
echo IID_DECLARATION_START
echo IID IID_%INTERFACE_NAME% = {
echo     0x%PART1%, 0x%PART2%, 0x%PART3%,
echo     { 0x%BYTE1%, 0x%BYTE2%, 0x%BYTE3%, 0x%BYTE4%, 0x%BYTE5%, 0x%BYTE6%, 0x%BYTE7%, 0x%BYTE8% }
echo };
echo IID_DECLARATION_END
echo.
echo IID_EXTERN_START
echo extern IID IID_%INTERFACE_NAME%;
echo IID_EXTERN_END

exit /b 0
