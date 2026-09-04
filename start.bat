@echo off
setlocal EnableDelayedExpansion
REM ============================================================
REM  Unilead Platform - One-Click Launcher
REM ============================================================

set "PROJECT_ROOT=%~dp0"
set "API_DIR=!PROJECT_ROOT!apps\api"
set "WEB_DIR=!PROJECT_ROOT!apps\web"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"
set "BACKEND_URL=http://localhost:!BACKEND_PORT!"
set "FRONTEND_URL=http://localhost:!FRONTEND_PORT!"

echo.
echo ============================================================
echo  Unilead Platform - Starting...
echo ============================================================
echo  Backend: !BACKEND_URL!
echo  Frontend: !FRONTEND_URL!
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 goto :ERR_PYTHON

where node >nul 2>nul
if errorlevel 1 goto :ERR_NODE

if not exist "!API_DIR!\app\main.py" goto :ERR_NO_BACKEND
if not exist "!WEB_DIR!\package.json" goto :ERR_NO_FRONTEND

if exist "!API_DIR!\.venv\Scripts\python.exe" goto :CHECK_DEPS
echo [SETUP] Creating Python virtual environment...
pushd "!API_DIR!"
python -m venv .venv
set VENV_OK=!errorlevel!
popd
if not "!VENV_OK!" == "0" goto :ERR_VENV
echo [SETUP] Python venv created.

:CHECK_DEPS
if exist "!API_DIR!\.venv\Lib\site-packages\fastapi" goto :CHECK_NPM
echo [SETUP] Installing backend Python deps - may take 1-2 min...
pushd "!API_DIR!"
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e ".[dev]"
set PIP_OK=!errorlevel!
popd
if not "!PIP_OK!" == "0" goto :ERR_PIP
pushd "!API_DIR!"
call .venv\Scripts\activate.bat
pip install -e ..\..\services\ai_education
popd
echo [SETUP] Backend dependencies installed.

:CHECK_NPM
if exist "!WEB_DIR!\node_modules\vite" goto :RUN_MIGRATIONS
echo [SETUP] Installing frontend npm deps - may take 1-2 min...
pushd "!WEB_DIR!"
call npm install --no-audit --no-fund
set NPM_OK=!errorlevel!
popd
if not "!NPM_OK!" == "0" goto :ERR_NPM
echo [SETUP] Frontend dependencies installed.

:RUN_MIGRATIONS
echo [SETUP] Running DB migrations...
pushd "!API_DIR!"
call .venv\Scripts\activate.bat
alembic upgrade head >nul 2>nul
popd
echo [OK] DB ready.

echo [START] Launching backend on !BACKEND_URL! ...
pushd "!API_DIR!"
start "Unilead Backend" cmd /k "call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 127.0.0.1 --port !BACKEND_PORT!"
popd

echo [WAIT] Waiting for backend to start...
set /a TRIES=0
:WAIT_BACKEND
timeout /t 2 /nobreak >nul
powershell -Command "try { (Invoke-WebRequest -Uri 'http://localhost:!BACKEND_PORT!/' -UseBasicParsing -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 goto :BACKEND_UP
set /a TRIES+=1
echo   ...still waiting !TRIES!/15
if !TRIES! lss 15 goto :WAIT_BACKEND
echo [WARNING] Backend did not respond after 30 seconds.

:BACKEND_UP
echo [OK] Backend is up.

echo [START] Launching frontend on !FRONTEND_URL! ...
pushd "!WEB_DIR!"
start "Unilead Frontend" cmd /k "npm run dev -- --port !FRONTEND_PORT!"
popd

echo [WAIT] Waiting for frontend to start...
set /a TRIES=0
:WAIT_FRONTEND
timeout /t 2 /nobreak >nul
powershell -Command "try { (Invoke-WebRequest -Uri 'http://localhost:!FRONTEND_PORT!/' -UseBasicParsing -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 goto :FRONTEND_UP
set /a TRIES+=1
echo   ...still waiting !TRIES!/15
if !TRIES! lss 15 goto :WAIT_FRONTEND
echo [WARNING] Frontend did not respond after 30 seconds.

:FRONTEND_UP
echo [OK] Frontend is up.

echo [OPEN] Opening browser at !FRONTEND_URL! ...
start "" "!FRONTEND_URL!"

echo.
echo ============================================================
echo  Done! Two windows are running:
echo    - Backend  (!BACKEND_URL!)
echo    - Frontend (!FRONTEND_URL!)
echo.
echo  To stop: close both windows.
echo.
echo  Sign up at !FRONTEND_URL!/signup to create an account.
echo  Or log in if you already have one.
echo ============================================================
echo.
pause
exit /b 0

:ERR_PYTHON
echo [ERROR] Python is not installed or not in PATH.
echo Download from: https://www.python.org/downloads/
pause
exit /b 1

:ERR_NODE
echo [ERROR] Node.js is not installed or not in PATH.
echo Download from: https://nodejs.org/
pause
exit /b 1

:ERR_NO_BACKEND
echo [ERROR] Backend folder not found at: !API_DIR!\app\main.py
pause
exit /b 1

:ERR_NO_FRONTEND
echo [ERROR] Frontend folder not found at: !WEB_DIR!\package.json
pause
exit /b 1

:ERR_VENV
echo [ERROR] Failed to create Python venv.
pause
exit /b 1

:ERR_PIP
echo [ERROR] Failed to install backend Python dependencies.
pause
exit /b 1

:ERR_NPM
echo [ERROR] Failed to install npm dependencies.
pause
exit /b 1
