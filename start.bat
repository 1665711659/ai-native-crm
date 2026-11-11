@echo off
title AI-Native CRM
cd /d "%~dp0"

echo ==================================================
echo         AI-Native CRM - One-Click Startup
echo ==================================================

REM ---------- 1. Locate Python 3 ----------
REM Pass 1: prefer a launcher/path whose dependencies are ALREADY installed
set "PY="
where py >nul 2>nul && py -3 -c "import tornado, numpy, httpx, aiosqlite, dotenv" >nul 2>nul && set "PY=py"
if not defined PY (
    for %%v in (315 314 313 312 311 310) do (
        if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" -c "import tornado, numpy, httpx, aiosqlite, dotenv" >nul 2>nul && set "PY=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe"
        if not defined PY if exist "C:\Program Files\Python%%v\python.exe" "C:\Program Files\Python%%v\python.exe" -c "import tornado, numpy, httpx, aiosqlite, dotenv" >nul 2>nul && set "PY=C:\Program Files\Python%%v\python.exe"
    )
)
REM Pass 2: any Python 3 found on disk (deps will be auto-installed)
if not defined PY (
    for %%v in (315 314 313 312 311 310) do (
        if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe"
        if not defined PY if exist "C:\Program Files\Python%%v\python.exe" set "PY=C:\Program Files\Python%%v\python.exe"
    )
)
if not defined PY where py >nul 2>nul && set "PY=py"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo [X] Python not found. Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM ---------- 2. Verify it is Python 3.x ----------
"%PY%" -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >nul 2>nul
if errorlevel 1 (
    echo [X] [%PY%] is not Python 3. Please install Python 3.10+ and retry.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('"%PY%" -c "import sys; print(sys.version.split()[0])" 2^>nul') do echo [OK] Python %%v

REM ---------- 3. Install core dependencies if missing ----------
"%PY%" -c "import tornado, numpy, httpx, aiosqlite, dotenv" >nul 2>nul
if errorlevel 1 (
    echo [!] Core dependencies missing, installing requirements.txt ...
    "%PY%" -m pip install -r requirements.txt --disable-pip-version-check -q
    if errorlevel 1 (
        echo [!] Retrying with --user option ...
        "%PY%" -m pip install -r requirements.txt --user --disable-pip-version-check -q
        if errorlevel 1 (
            echo [X] Dependency install failed. Check your network/permissions and retry.
            pause
            exit /b 1
        )
    )
)
echo [OK] Dependencies ready

REM ---------- 4. Create .env on first run ----------
if not exist .env (
    copy .env.example .env >nul
    echo [OK] Created .env from template - offline demo mode by default.
    echo      Edit .env and set LLM_API_KEY to enable a real LLM.
)

REM ---------- 5. Start server ----------
echo [OK] Starting server: http://127.0.0.1:8888
echo      (Close this window or run stop.bat to stop)
echo.
"%PY%" main.py
pause
