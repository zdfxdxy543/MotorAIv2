@echo off
setlocal

if "%~1"=="" (
    echo Usage: %~nx0 path\to\tuning_job.json
    exit /b 2
)

if not "%~2"=="" if not "%~2"=="--resume" (
    echo Error: optional second argument must be --resume
    exit /b 2
)
if not "%~3"=="" exit /b 2

set "JOB_FILE=%~1"

if not exist "%JOB_FILE%" (
    echo Error: job file not found: %JOB_FILE%
    exit /b 2
)

cd /d "%~dp0"
set "PYTHONUTF8=1"
if not defined MOTORAI_AGENT_PYTHON set "MOTORAI_AGENT_PYTHON=python"
"%MOTORAI_AGENT_PYTHON%" agent_modified.py --job-file "%JOB_FILE%" %~2
exit /b %ERRORLEVEL%
