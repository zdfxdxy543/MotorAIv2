@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem ============================================================
rem Start generated SIL exe for GMP motor simulation.
rem This script assumes build_sln.bat has already succeeded.
rem
rem The exe will wait for Simulink. Therefore agent.py should start
rem this script asynchronously, then start run_local_quick.bat.
rem
rem Logs are written to:
rem   <repo_root>\tools\agent\log\run_exe.log
rem
rem Usage:
rem   start_exe.bat
rem   start_exe.bat H:\WorkSpace\GMPmaster
rem ============================================================

set "SCRIPT_DIR=%~dp0"

rem Optional: allow user to pass repo root manually.
if not "%~1"=="" (
    set "SEARCH_START=%~1"
) else (
    set "SEARCH_START=%SCRIPT_DIR%"
)

call :FIND_REPO_ROOT "%SEARCH_START%"
if errorlevel 1 goto ERR_REPO_ROOT

set "GMP_PRO_LOCATION=%REPO_ROOT%"

rem Activate the configured GMP environment in this calling script.
if exist "%GMP_PRO_LOCATION%\tools\gmp_installer\ensure_gmp_environment.bat" (
    call "%GMP_PRO_LOCATION%\tools\gmp_installer\ensure_gmp_environment.bat"
    if errorlevel 1 exit /b 20
)

set "SLN_DIR=%REPO_ROOT%\ctl\suite\mcs_pmsm_nt\project\simulate"
set "LOG_DIR=%REPO_ROOT%\tools\agent\log\build"
set "RUN_LOG=%LOG_DIR%\run_exe.log"

set "CONFIGURATION=Release"
set "PLATFORM=x64"
set "EXE_PATH=%SLN_DIR%\%PLATFORM%\%CONFIGURATION%\Motor_Control_Suite_SIL_Env.exe"

rem Optional environment variable for your exe.
rem If your exe source checks this env var, it can skip pause in automation.
set "SIL_NO_PAUSE=1"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%EXE_PATH%" goto ERR_EXE_NOT_FOUND

echo [INFO] Repo root: "%REPO_ROOT%"
echo [INFO] Solution dir: "%SLN_DIR%"
echo [INFO] Exe: "%EXE_PATH%"
echo [INFO] Run log: "%RUN_LOG%"
echo [INFO] SIL_NO_PAUSE=%SIL_NO_PAUSE%
echo [INFO] Starting exe. It may block until Simulink finishes.

pushd "%SLN_DIR%"

rem ------------------------------------------------------------
rem Run exe in automation mode.
rem echo. sends one Enter to avoid simple pause/getchar blocking.
rem stdout and stderr are written to run_exe.log.
rem ------------------------------------------------------------

echo [INFO] Running exe at %DATE% %TIME% > "%RUN_LOG%"
echo [INFO] Exe: "%EXE_PATH%" >> "%RUN_LOG%"
echo [INFO] Working dir: "%SLN_DIR%" >> "%RUN_LOG%"
echo. | "%EXE_PATH%" >> "%RUN_LOG%" 2>&1

set "RUN_RESULT=%ERRORLEVEL%"

popd

echo [INFO] Exe exit code: %RUN_RESULT%
echo [INFO] Exe run log: "%RUN_LOG%"

exit /b %RUN_RESULT%


:FIND_REPO_ROOT
set "CURRENT=%~f1"

:FIND_REPO_ROOT_LOOP
if exist "%CURRENT%\tools\facilities_generator\src_mgr\framework_sync_src_v3.py" (
    if exist "%CURRENT%\gmp_core.h" (
        set "REPO_ROOT=%CURRENT%"
        exit /b 0
    )
)

for %%P in ("%CURRENT%\..") do set "PARENT=%%~fP"

if /i "%PARENT%"=="%CURRENT%" (
    exit /b 1
)

set "CURRENT=%PARENT%"
goto FIND_REPO_ROOT_LOOP


:ERR_REPO_ROOT
echo [ERROR] Repo root not found.
echo Search started from:
echo "%SEARCH_START%"
echo Expected to find both:
echo tools\facilities_generator\src_mgr\framework_sync_src_v3.py
echo gmp_core.h
exit /b 10


:ERR_EXE_NOT_FOUND
echo [ERROR] Exe was not found:
echo "%EXE_PATH%"
echo Please run build_sln.bat first, and check Configuration, Platform, or executable name.
exit /b 18
