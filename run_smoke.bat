@echo off
title AI-Native CRM - Smoke Test
cd /d "%~dp0"

REM ---------- 1. Locate Python 3 (prefer one with deps installed) ----------
set "PY="
where py >nul 2>nul && py -3 -c "import tornado, numpy, httpx, aiosqlite, dotenv" >nul 2>nul && set "PY=py"
if not defined PY (
    for %%v in (315 314 313 312 311 310) do (
        if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" -c "import tornado, numpy, httpx, aiosqlite, dotenv" >nul 2>nul && set "PY=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe"
        if not defined PY if exist "C:\Program Files\Python%%v\python.exe" "C:\Program Files\Python%%v\python.exe" -c "import tornado, numpy, httpx, aiosqlite, dotenv" >nul 2>nul && set "PY=C:\Program Files\Python%%v\python.exe"
    )
)
if not defined PY (
    for %%v in (315 314 313 312 311 310) do (
        if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe"
        if not defined PY if exist "C:\Program Files\Python%%v\python.exe" set "PY=C:\Program Files\Python%%v\python.exe"
    )
)
if not defined PY where py >nul 2>nul && set "PY=py"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo [X] Python not found. Please install Python 3.10+ first.
    pause
    exit /b 1
)

REM ---------- 2. Start server in background if not running ----------
netstat -ano | findstr /r ":8888 .*LISTENING" >nul
if errorlevel 1 (
    echo [i] Server not running, starting it in background ...
    start "AI-Native CRM Server" /min "%PY%" main.py
    timeout /t 8 /nobreak >nul
)

REM ---------- 3. Run smoke tests ----------
echo ==================================================
echo   Smoke Tests: CRUD / RAG / Agent / Workflow
echo ==================================================
"%PY%" tests\smoke_test.py
set "RC=%errorlevel%"

echo.
if "%RC%"=="0" (
    echo [OK] ALL TESTS PASSED
) else (
    echo [X] SOME TESTS FAILED ^(exit code %RC%^). Check server console or .env config.
)
pause
exit /b %RC%
