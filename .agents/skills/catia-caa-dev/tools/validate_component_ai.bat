@echo off
REM ================================================================================
REM CAA Component Validation - AI Tool (Enhanced)
REM ================================================================================
REM Purpose: Validate 7-file CAA structure and output machine-readable results
REM Caller:  Zed AI Agent (via Skill)
REM Output:  Structured validation report
REM Version: 2.4.4 - Enhanced with GUID and Dictionary format checks
REM ================================================================================

setlocal enabledelayedexpansion

REM --- Check Arguments ---
if "%~1"=="" (
    echo ERROR=Missing framework path argument
    echo USAGE=validate_component_ai.bat ^<framework_path^>
    exit /b 1
)

set "FRAMEWORK_PATH=%~1"

if not exist "%FRAMEWORK_PATH%" (
    echo ERROR=Framework path not found: %FRAMEWORK_PATH%
    exit /b 1
)

REM --- Extract Framework Name ---
for %%F in ("%FRAMEWORK_PATH%") do set "FRAMEWORK_NAME=%%~nxF"

REM --- Initialize Counters ---
set "ERROR_COUNT=0"
set "WARNING_COUNT=0"
set "CHECKS_PASSED=0"
set "CHECKS_TOTAL=9"
set "FIX_SUGGESTIONS="

REM --- Check 1: IdentityCard.h ---
set "CHECK1_STATUS=FAIL"
set "CHECK1_MSG="
if exist "%FRAMEWORK_PATH%\IdentityCard\IdentityCard.h" (
    findstr /C:"#ifndef" "%FRAMEWORK_PATH%\IdentityCard\IdentityCard.h" >nul 2>&1
    if not errorlevel 1 (
        set "CHECK1_STATUS=WARN"
        set "CHECK1_MSG=IdentityCard.h should NOT have header guards"
        set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX1:Remove #ifndef/#define/#endif from IdentityCard.h;"
        set /a WARNING_COUNT+=1
    ) else (
        set "CHECK1_STATUS=PASS"
        set /a CHECKS_PASSED+=1
    )

    findstr /C:"AddPrereqComponent" "%FRAMEWORK_PATH%\IdentityCard\IdentityCard.h" >nul 2>&1
    if errorlevel 1 (
        if "!CHECK1_STATUS!"=="PASS" set "CHECK1_STATUS=WARN"
        set "CHECK1_MSG=!CHECK1_MSG! No AddPrereqComponent found"
        set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX1b:Add AddPrereqComponent(System,Public) to IdentityCard.h;"
        set /a WARNING_COUNT+=1
    )
) else (
    set "CHECK1_MSG=IdentityCard.h not found"
    set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX1:Create IdentityCard/IdentityCard.h;"
    set /a ERROR_COUNT+=1
)

REM --- Check 2: PublicInterfaces ---
set "CHECK2_STATUS=FAIL"
set "CHECK2_MSG="
if exist "%FRAMEWORK_PATH%\PublicInterfaces\" (
    dir /b "%FRAMEWORK_PATH%\PublicInterfaces\I*.h" >nul 2>&1
    if errorlevel 1 (
        set "CHECK2_STATUS=WARN"
        set "CHECK2_MSG=No interface files (I*.h) found"
        set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX2:Create interface header IYourInterface.h in PublicInterfaces/;"
        set /a WARNING_COUNT+=1
    ) else (
        set "CHECK2_STATUS=PASS"
        set /a CHECKS_PASSED+=1
    )
) else (
    set "CHECK2_MSG=PublicInterfaces directory not found"
    set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX2:Create PublicInterfaces/ directory;"
    set /a ERROR_COUNT+=1
)

REM --- Check 3: Interface Implementation (.cpp) with GUID validation ---
set "CHECK3_STATUS=FAIL"
set "CHECK3_MSG="
set "INTERFACE_CPP_FOUND=0"
set "INTERFACE_CPP_FILE="
for /r "%FRAMEWORK_PATH%" %%F in (I*.cpp) do (
    findstr /C:"CATImplementInterface" "%%F" >nul 2>&1
    if not errorlevel 1 (
        set "INTERFACE_CPP_FOUND=1"
        set "INTERFACE_CPP_FILE=%%F"

        REM Check GUID format (basic validation)
        findstr /R "0x[0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F]" "%%F" >nul 2>&1
        if errorlevel 1 (
            set "CHECK3_STATUS=WARN"
            set "CHECK3_MSG=IID GUID format may be incorrect in %%~nxF"
            set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX3:Use generate_guid_ai.bat to create valid IID;"
            set /a WARNING_COUNT+=1
        ) else (
            set "CHECK3_STATUS=PASS"
            set /a CHECKS_PASSED+=1
        )
        goto :check3_done
    )
)
:check3_done
if "!INTERFACE_CPP_FOUND!"=="0" (
    set "CHECK3_MSG=No Interface.cpp with CATImplementInterface found"
    set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX3:Create IYourInterface.cpp with IID and CATImplementInterface;"
    set /a ERROR_COUNT+=1
)

REM --- Check 4: Component Implementation ---
set "CHECK4_STATUS=FAIL"
set "CHECK4_MSG="
set "COMPONENT_CPP_FOUND=0"
for /r "%FRAMEWORK_PATH%" %%F in (*.cpp) do (
    findstr /C:"CATImplementClass" "%%F" >nul 2>&1
    if not errorlevel 1 (
        findstr /C:"CATImplementBOA" "%%F" >nul 2>&1
        if not errorlevel 1 (
            set "COMPONENT_CPP_FOUND=1"
            set "CHECK4_STATUS=PASS"
            set /a CHECKS_PASSED+=1
            goto :check4_done
        ) else (
            REM Has CATImplementClass but not CATImplementBOA
            set "CHECK4_MSG=Component.cpp missing CATImplementBOA (found CATImplementClass)"
            set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX4:Add CATImplementBOA(IYourInterface,YourComponent) after CATImplementClass;"
            set /a WARNING_COUNT+=1
            goto :check4_done
        )
    )
)
:check4_done
if "!COMPONENT_CPP_FOUND!"=="0" (
    set "CHECK4_MSG=No Component.cpp with CATImplementClass+CATImplementBOA found"
    set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX4:Create Component.cpp with both CATImplementClass and CATImplementBOA;"
    set /a ERROR_COUNT+=1
)

REM --- Check 5: Imakefile.mk ---
set "CHECK5_STATUS=FAIL"
set "CHECK5_MSG="
set "IMAKEFILE_FOUND=0"
set "IMAKEFILE_PATH="
for /d %%D in ("%FRAMEWORK_PATH%\*.m") do (
    if exist "%%D\Imakefile.mk" (
        set "IMAKEFILE_FOUND=1"
        set "IMAKEFILE_PATH=%%D\Imakefile.mk"

        REM Check for space before =
        findstr /r "LINK_WITH[ ][ ]*=" "%%D\Imakefile.mk" >nul 2>&1
        if not errorlevel 1 (
            set "CHECK5_STATUS=WARN"
            set "CHECK5_MSG=Space before = in LINK_WITH (should be LINK_WITH=)"
            set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX5:Change 'LINK_WITH =' to 'LINK_WITH=' in Imakefile.mk;"
            set /a WARNING_COUNT+=1
        ) else (
            REM Check if LINK_WITH exists at all
            findstr /C:"LINK_WITH" "%%D\Imakefile.mk" >nul 2>&1
            if errorlevel 1 (
                set "CHECK5_STATUS=WARN"
                set "CHECK5_MSG=No LINK_WITH found in Imakefile.mk"
                set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX5:Add 'LINK_WITH=JS0GROUP' to Imakefile.mk;"
                set /a WARNING_COUNT+=1
            ) else (
                set "CHECK5_STATUS=PASS"
                set /a CHECKS_PASSED+=1
            )
        )
        goto :check5_done
    )
)
:check5_done
if "!IMAKEFILE_FOUND!"=="0" (
    set "CHECK5_MSG=Imakefile.mk not found in any module"
    set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX5:Create Imakefile.mk in Module.m/ directory;"
    set /a ERROR_COUNT+=1
)

REM --- Check 6: Dictionary File (CRITICAL) with format validation ---
set "CHECK6_STATUS=FAIL"
set "CHECK6_MSG="
set "DICO_FILE=%FRAMEWORK_PATH%\CNext\code\dictionary\%FRAMEWORK_NAME%.dico"
if exist "!DICO_FILE!" (
    for %%A in ("!DICO_FILE!") do set "DICO_SIZE=%%~zA"
    if !DICO_SIZE! LEQ 50 (
        set "CHECK6_STATUS=WARN"
        set "CHECK6_MSG=Dictionary file is too small (!DICO_SIZE! bytes)"
        set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX6:Add component mappings to Dictionary file;"
        set /a WARNING_COUNT+=1
    ) else (
        REM Check for spaces instead of tabs (common error)
        findstr /R "^[^	]*[ ][^	]*" "!DICO_FILE!" >nul 2>&1
        if not errorlevel 1 (
            set "CHECK6_STATUS=WARN"
            set "CHECK6_MSG=Dictionary file uses spaces instead of tabs (CRITICAL)"
            set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX6:Replace spaces with TAB characters in Dictionary file;"
            set /a WARNING_COUNT+=1
        ) else (
            set "CHECK6_STATUS=PASS"
            set /a CHECKS_PASSED+=1
        )
    )
) else (
    set "CHECK6_MSG=Dictionary file not found - CRITICAL (component won't instantiate)"
    set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX6:Create CNext/code/dictionary/%FRAMEWORK_NAME%.dico with TAB-separated format;"
    set /a ERROR_COUNT+=1
)

REM --- Check 7: Module Structure ---
set "CHECK7_STATUS=FAIL"
set "CHECK7_MSG="
set "MODULE_FOUND=0"
for /d %%D in ("%FRAMEWORK_PATH%\*.m") do (
    set "MODULE_FOUND=1"
    if exist "%%D\src\" (
        dir /b "%%D\src\*.cpp" >nul 2>&1
        if not errorlevel 1 (
            set "CHECK7_STATUS=PASS"
            set /a CHECKS_PASSED+=1
        ) else (
            set "CHECK7_STATUS=WARN"
            set "CHECK7_MSG=Module found but no .cpp files in src/"
            set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX7:Add implementation .cpp files to Module.m/src/;"
            set /a WARNING_COUNT+=1
        )
    ) else (
        set "CHECK7_MSG=Module %%~nxD missing src/ directory"
        set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX7:Create src/ directory in Module.m/;"
        set /a ERROR_COUNT+=1
    )
    goto :check7_done
)
:check7_done
if "!MODULE_FOUND!"=="0" (
    set "CHECK7_MSG=No module directories (*.m) found"
    set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX7:Create YourModule.m directory;"
    set /a ERROR_COUNT+=1
)

REM --- Check 8: LocalInterfaces directory (NEW) ---
set "CHECK8_STATUS=FAIL"
set "CHECK8_MSG="
set "LOCAL_INT_FOUND=0"
for /d %%D in ("%FRAMEWORK_PATH%\*.m") do (
    if exist "%%D\LocalInterfaces\" (
        set "LOCAL_INT_FOUND=1"
        set "CHECK8_STATUS=PASS"
        set /a CHECKS_PASSED+=1
    ) else (
        set "CHECK8_MSG=LocalInterfaces directory not found in module"
        set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX8:Create LocalInterfaces/ in Module.m/;"
        set /a WARNING_COUNT+=1
    )
    goto :check8_done
)
:check8_done

REM --- Check 9: Component header in LocalInterfaces (NEW) ---
set "CHECK9_STATUS=FAIL"
set "CHECK9_MSG="
set "COMPONENT_H_FOUND=0"
for /d %%D in ("%FRAMEWORK_PATH%\*.m") do (
    if exist "%%D\LocalInterfaces\" (
        dir /b "%%D\LocalInterfaces\*.h" >nul 2>&1
        if not errorlevel 1 (
            set "COMPONENT_H_FOUND=1"
            set "CHECK9_STATUS=PASS"
            set /a CHECKS_PASSED+=1
        ) else (
            set "CHECK9_MSG=No component header found in LocalInterfaces/"
            set "FIX_SUGGESTIONS=!FIX_SUGGESTIONS! FIX9:Create Component.h in LocalInterfaces/;"
            set /a WARNING_COUNT+=1
        )
    )
    goto :check9_done
)
:check9_done

REM --- Output Machine-Readable Results ---
echo FRAMEWORK_PATH=%FRAMEWORK_PATH%
echo FRAMEWORK_NAME=%FRAMEWORK_NAME%
echo CHECKS_PASSED=%CHECKS_PASSED%
echo CHECKS_TOTAL=%CHECKS_TOTAL%
echo ERROR_COUNT=%ERROR_COUNT%
echo WARNING_COUNT=%WARNING_COUNT%
echo.
echo CHECK1_IDENTITYCARD=%CHECK1_STATUS%
if not "%CHECK1_MSG%"=="" echo CHECK1_MSG=%CHECK1_MSG%
echo.
echo CHECK2_PUBLICINTERFACES=%CHECK2_STATUS%
if not "%CHECK2_MSG%"=="" echo CHECK2_MSG=%CHECK2_MSG%
echo.
echo CHECK3_INTERFACE_CPP=%CHECK3_STATUS%
if not "%CHECK3_MSG%"=="" echo CHECK3_MSG=%CHECK3_MSG%
echo.
echo CHECK4_COMPONENT_CPP=%CHECK4_STATUS%
if not "%CHECK4_MSG%"==" echo CHECK4_MSG=%CHECK4_MSG%
echo.
echo CHECK5_IMAKEFILE=%CHECK5_STATUS%
if not "%CHECK5_MSG%"=="" echo CHECK5_MSG=%CHECK5_MSG%
echo.
echo CHECK6_DICTIONARY=%CHECK6_STATUS%
if not "%CHECK6_MSG%"=="" echo CHECK6_MSG=%CHECK6_MSG%
echo.
echo CHECK7_MODULE_STRUCTURE=%CHECK7_STATUS%
if not "%CHECK7_MSG%"=="" echo CHECK7_MSG=%CHECK7_MSG%
echo.
echo CHECK8_LOCALINTERFACES=%CHECK8_STATUS%
if not "%CHECK8_MSG%"=="" echo CHECK8_MSG=%CHECK8_MSG%
echo.
echo CHECK9_COMPONENT_HEADER=%CHECK9_STATUS%
if not "%CHECK9_MSG%"=="" echo CHECK9_MSG=%CHECK9_MSG%
echo.
if %ERROR_COUNT%==0 (
    echo VALIDATION_RESULT=PASS
    echo READY_TO_COMPILE=YES
) else (
    echo VALIDATION_RESULT=FAIL
    echo READY_TO_COMPILE=NO
)
echo.
if not "%FIX_SUGGESTIONS%"=="" echo FIX_SUGGESTIONS=%FIX_SUGGESTIONS%

REM --- Exit Code ---
exit /b %ERROR_COUNT%
