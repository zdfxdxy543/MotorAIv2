@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem ============================================================
rem Build Visual Studio solution for GMP motor simulation.
rem This script does not run the generated exe.
rem
rem Logs are written to:
rem   <repo_root>\tools\agent\log\build.log
rem
rem Usage:
rem   build_sln.bat
rem   build_sln.bat H:\WorkSpace\GMPmaster
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

set "SLN_PATH=%REPO_ROOT%\ctl\suite\mcs_pmsm_nt\project\simulate\GMP_Motor_Control_simulink.sln"
set "SLN_DIR=%REPO_ROOT%\ctl\suite\mcs_pmsm_nt\project\simulate"
set "FAC_DIR=%REPO_ROOT%\tools\facilities_generator"
set "GMP_PRO_LOCATION=%REPO_ROOT%"

rem Activate the configured GMP environment in this calling script.
if exist "%GMP_PRO_LOCATION%\tools\gmp_installer\ensure_gmp_environment.bat" (
    call "%GMP_PRO_LOCATION%\tools\gmp_installer\ensure_gmp_environment.bat"
    if errorlevel 1 exit /b 20
)


rem Log directory required by agent:
rem   <repo_root>\tools\agent\log\build
set "LOG_DIR=%REPO_ROOT%\tools\agent\log\build"
set "BUILD_LOG=%LOG_DIR%\build.log"

rem Important include directories.
set "XPLT_DIR=%SLN_DIR%\xplt"
for %%D in ("%SLN_DIR%\..\..\src") do set "CTL_SRC_DIR=%%~fD"

set "CONFIGURATION=Release"
set "PLATFORM=x64"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if not exist "%SLN_PATH%" goto ERR_SLN
if not exist "%FAC_DIR%" goto ERR_FAC_DIR
if not exist "%FAC_DIR%\src_mgr\framework_sync_src_v3.py" goto ERR_FAC_BAT

if not exist "%XPLT_DIR%\xplt.config.h" goto ERR_XPLT_CONFIG
if not exist "%CTL_SRC_DIR%\ctl_main.h" goto ERR_CTL_MAIN

rem Add facilities_generator to PATH so MSBuild pre-build steps can find generator scripts.
set "PATH=%FAC_DIR%;%PATH%"

rem Add include directories for cl.exe.
set "INCLUDE=%XPLT_DIR%;%CTL_SRC_DIR%;%INCLUDE%"
set "CL=/I"%XPLT_DIR%" /I"%CTL_SRC_DIR%" %CL%"

echo [INFO] Repo root: "%REPO_ROOT%"
echo [INFO] Solution: "%SLN_PATH%"
echo [INFO] Solution dir: "%SLN_DIR%"
echo [INFO] Facilities generator dir: "%FAC_DIR%"
echo [INFO] xplt include dir: "%XPLT_DIR%"
echo [INFO] ctl src include dir: "%CTL_SRC_DIR%"
echo [INFO] Log dir: "%LOG_DIR%"
echo [INFO] Build log: "%BUILD_LOG%"
echo [INFO] Configuration: %CONFIGURATION%
echo [INFO] Platform: %PLATFORM%
echo [INFO] Mode: build only


rem Generate before MSBuild evaluates wildcard source items.
if not exist "%SLN_DIR%\gmp_src_mgr\gmp_framework_config.json" exit /b 19
if not exist "%SLN_DIR%\gmp_src_mgr\gmp_generate_src.bat" exit /b 19
call "%SLN_DIR%\gmp_src_mgr\gmp_generate_src.bat"
if errorlevel 1 exit /b 19
if not exist "%SLN_DIR%\gmp_src_mgr\gmp_src\gmp_runtime.c" exit /b 19
if not exist "%SLN_DIR%\gmp_src_mgr\gmp_src\ctl_component_interface.c" exit /b 19

call :FIND_MSBUILD
if errorlevel 1 goto ERR_MSBUILD

echo [INFO] MSBuild: "%MSBUILD%"

pushd "%SLN_DIR%"

"%MSBUILD%" "%SLN_PATH%" ^
    /t:Build ^
    /p:Configuration=%CONFIGURATION% ^
    /p:Platform=%PLATFORM% ^
    /m ^
    /nr:false ^
    /v:m ^
    /fl ^
    /flp:logfile="%BUILD_LOG%";verbosity=normal

set "BUILD_RESULT=%ERRORLEVEL%"

popd

echo [INFO] Build exit code: %BUILD_RESULT%

if not "%BUILD_RESULT%"=="0" (
    echo [ERROR] Build failed. See build log:
    echo "%BUILD_LOG%"
    exit /b %BUILD_RESULT%
)

echo [INFO] Build succeeded. Exe is not started by this script.
exit /b 0


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


:FIND_MSBUILD
set "VSWHERE_DIR="

if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" set "VSWHERE_DIR=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"
if not defined VSWHERE_DIR if exist "%ProgramFiles%\Microsoft Visual Studio\Installer\vswhere.exe" set "VSWHERE_DIR=%ProgramFiles%\Microsoft Visual Studio\Installer"

if not defined VSWHERE_DIR exit /b 1

echo [INFO] vswhere dir: "%VSWHERE_DIR%"

set "MSBUILD="

pushd "%VSWHERE_DIR%"
for /f "delims=" %%i in ('vswhere.exe -latest -products * -requires Microsoft.Component.MSBuild -find MSBuild\**\Bin\MSBuild.exe') do set "MSBUILD=%%i"
popd

if not defined MSBUILD exit /b 1
if not exist "%MSBUILD%" exit /b 1

exit /b 0


:ERR_REPO_ROOT
echo [ERROR] Repo root not found.
echo Search started from:
echo "%SEARCH_START%"
echo Expected to find both:
echo tools\facilities_generator\src_mgr\framework_sync_src_v3.py
echo gmp_core.h
exit /b 10


:ERR_SLN
echo [ERROR] Solution file not found:
echo "%SLN_PATH%"
exit /b 11


:ERR_FAC_DIR
echo [ERROR] Facilities generator directory not found:
echo "%FAC_DIR%"
exit /b 12


:ERR_FAC_BAT
echo [ERROR] src_mgr\framework_sync_src_v3.py not found:
echo "%FAC_DIR%\src_mgr\framework_sync_src_v3.py"
exit /b 13


:ERR_FAC_BAT_NOT_IN_PATH
echo [ERROR] src_mgr\framework_sync_src_v3.py is not available in PATH.
echo Facilities generator dir:
echo "%FAC_DIR%"
exit /b 14


:ERR_MSBUILD
echo [ERROR] MSBuild.exe not found.
echo Please check Visual Studio installation and MSBuild component.
exit /b 15


:ERR_XPLT_CONFIG
echo [ERROR] xplt.config.h not found:
echo "%XPLT_DIR%\xplt.config.h"
echo Please check whether the xplt folder exists under solution directory.
exit /b 16


:ERR_CTL_MAIN
echo [ERROR] ctl_main.h not found:
echo "%CTL_SRC_DIR%\ctl_main.h"
echo Please check whether ctl_main.h exists under mcs_pmsm_nt\src.
exit /b 17
