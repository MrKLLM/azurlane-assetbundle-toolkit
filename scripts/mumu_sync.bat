@echo off
chcp 65001 >nul 2>&1
set "PY=C:\Users\KLLM\.workbuddy\binaries\python\versions\3.13.12\python.exe"
set "SCRIPT=%~dp0mumu_sync.py"

if not exist "%PY%" (
    echo [ERROR] Python not found: %PY%
    pause
    exit /b 1
)

if "%~1"=="" (
    echo Running: diff
    "%PY%" "%SCRIPT%" diff
) else (
    "%PY%" "%SCRIPT%" %*
)

echo.
pause
