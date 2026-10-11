@echo off
setlocal EnableExtensions

rem ============================================================
rem Portable Simulink local run script.
rem Expected location:
rem   <repo_root>\tools\agent\agent_silhelper\run_local_quick.bat
rem ============================================================

set "SCRIPT_DIR=%~dp0"

for %%D in ("%SCRIPT_DIR%..\..\..") do set "REPO_ROOT=%%~fD"

set "DEFAULT_MODEL_PATH=D:\WorkDocuments\Github\MotorAI\Output\test\project\simulate\MCS_STD_PMSM_MODEL.slx"
set "MODEL_PATH=%DEFAULT_MODEL_PATH%"
set "GMP_ROOT=%~2"
set "EXPECTED_ID=%~3"
set "GMP_ARGS="
if not "%GMP_ROOT%"=="" set GMP_ARGS=--gmp-root "%GMP_ROOT%"

if not "%~1"=="" (
    set "MODEL_PATH=%~1"
) else (
    if not "%GMP_LOCAL_MODEL_PATH%"=="" (
        set "MODEL_PATH=%GMP_LOCAL_MODEL_PATH%"
    )
)

if not exist "%MODEL_PATH%" (
    echo [ERROR] Simulink model not found:
    echo "%MODEL_PATH%"
    exit /b 20
)

python "%SCRIPT_DIR%run_local_job.py" --batch --model-path "%MODEL_PATH%" %GMP_ARGS% --expected-connection-id "%EXPECTED_ID%" --scope-map "%SCRIPT_DIR%..\log\simulation\scope_channel_map.json"
exit /b %ERRORLEVEL%
