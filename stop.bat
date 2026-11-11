@echo off
title AI-Native CRM - Stop

REM Find and kill the process listening on port 8888
set "FOUND="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r ":8888 .*LISTENING"') do (
    taskkill /f /pid %%a >nul 2>nul && (
        echo [OK] Server stopped. PID=%%a
        set "FOUND=1"
    )
)
if not defined FOUND echo [i] Server is not running (no listener on port 8888)
pause
