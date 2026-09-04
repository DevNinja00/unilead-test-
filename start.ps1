# ============================================================
#  Unilead Platform - One-Click Launcher (PowerShell version)
#  Right-click this file → "Run with PowerShell"
#  Or: double-click start.bat (which calls this script).
# ============================================================

$ErrorActionPreference = "Continue"

# --- Configuration ---
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ApiDir      = Join-Path $ProjectRoot "apps\api"
$WebDir      = Join-Path $ProjectRoot "apps\web"
$BackendPort  = 8000
$FrontendPort = 5173
$BackendUrl   = "http://localhost:$BackendPort"
$FrontendUrl  = "http://localhost:$FrontendPort"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Unilead Platform - Starting..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Project:  $ProjectRoot"
Write-Host "  Backend:  $BackendUrl"
Write-Host "  Frontend: $FrontendUrl"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# --- 0) Check Python ---
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/"
    Read-Host "Press Enter to exit"
    exit 1
}

# --- 1) Check Node.js ---
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Host "[ERROR] Node.js is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Download from: https://nodejs.org/"
    Read-Host "Press Enter to exit"
    exit 1
}

# --- 2) Check project folders ---
if (-not (Test-Path "$ApiDir\app\main.py")) {
    Write-Host "[ERROR] Backend not found at: $ApiDir\app\main.py" -ForegroundColor Red
    Write-Host "Make sure this .ps1 file is in the project root (next to apps\)."
    Read-Host "Press Enter to exit"
    exit 1
}
if (-not (Test-Path "$WebDir\package.json")) {
    Write-Host "[ERROR] Frontend not found at: $WebDir\package.json" -ForegroundColor Red
    Write-Host "Make sure this .ps1 file is in the project root (next to apps\)."
    Read-Host "Press Enter to exit"
    exit 1
}

# --- 3) Setup Python venv ---
if (-not (Test-Path "$ApiDir\.venv\Scripts\python.exe")) {
    Write-Host "[SETUP] Creating Python virtual environment..." -ForegroundColor Yellow
    Push-Location $ApiDir
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create venv." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        Pop-Location
        exit 1
    }
    Pop-Location
    Write-Host "[OK] Python venv created." -ForegroundColor Green
} else {
    Write-Host "[OK] Python venv already exists." -ForegroundColor Green
}

# --- 4) Install Python dependencies ---
if (-not (Test-Path "$ApiDir\.venv\Lib\site-packages\fastapi")) {
    Write-Host "[SETUP] Installing backend Python deps (1-2 min)..." -ForegroundColor Yellow
    Push-Location $ApiDir
    & .venv\Scripts\python.exe -m pip install --upgrade pip
    & .venv\Scripts\pip.exe install -e ".[dev]"
    & .venv\Scripts\pip.exe install -e ..\..\services\ai_education
    Pop-Location
    Write-Host "[OK] Backend deps installed." -ForegroundColor Green
} else {
    Write-Host "[OK] Backend deps already installed." -ForegroundColor Green
}

# --- 5) Install Node.js dependencies ---
if (-not (Test-Path "$WebDir\node_modules\vite")) {
    Write-Host "[SETUP] Installing frontend npm deps (1-2 min)..." -ForegroundColor Yellow
    Push-Location $WebDir
    npm install --no-audit --no-fund
    Pop-Location
    Write-Host "[OK] Frontend deps installed." -ForegroundColor Green
} else {
    Write-Host "[OK] Frontend deps already installed." -ForegroundColor Green
}

# --- 6) Run DB migrations ---
Write-Host "[SETUP] Running DB migrations..." -ForegroundColor Yellow
Push-Location $ApiDir
& .venv\Scripts\alembic.exe upgrade head 2>$null
Pop-Location
Write-Host "[OK] DB ready." -ForegroundColor Green

# --- 7) Start backend in a new window ---
Write-Host "[START] Launching backend on $BackendUrl ..." -ForegroundColor Cyan
Start-Process -FilePath "cmd" -ArgumentList "/k", ".venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 127.0.0.1 --port $BackendPort" -WorkingDirectory $ApiDir -WindowStyle Normal

# --- 8) Wait for backend ---
Write-Host "[WAIT] Waiting for backend..." -ForegroundColor Yellow
$tries = 0
$maxTries = 15
$up = $false
while ($tries -lt $maxTries) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "$BackendUrl/" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) {
            $up = $true
            break
        }
    } catch {
        $tries++
        Write-Host "  ...still waiting ($tries/$maxTries)"
    }
}
if ($up) {
    Write-Host "[OK] Backend is up." -ForegroundColor Green
} else {
    Write-Host "[WARNING] Backend did not respond after 30s. Check its window." -ForegroundColor Yellow
}

# --- 9) Start frontend in a new window ---
Write-Host "[START] Launching frontend on $FrontendUrl ..." -ForegroundColor Cyan
Start-Process -FilePath "cmd" -ArgumentList "/k", "npm run dev -- --port $FrontendPort" -WorkingDirectory $WebDir -WindowStyle Normal

# --- 10) Wait for frontend ---
Write-Host "[WAIT] Waiting for frontend..." -ForegroundColor Yellow
$tries = 0
$up = $false
while ($tries -lt $maxTries) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "$FrontendUrl/" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) {
            $up = $true
            break
        }
    } catch {
        $tries++
        Write-Host "  ...still waiting ($tries/$maxTries)"
    }
}
if ($up) {
    Write-Host "[OK] Frontend is up." -ForegroundColor Green
} else {
    Write-Host "[WARNING] Frontend did not respond after 30s. Check its window." -ForegroundColor Yellow
}

# --- 11) Open the browser ---
Write-Host "[OPEN] Opening browser at $FrontendUrl ..." -ForegroundColor Cyan
Start-Process $FrontendUrl

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Done! Two windows are running:" -ForegroundColor Green
Write-Host "    - Backend  ($BackendUrl)  - keep open"
Write-Host "    - Frontend ($FrontendUrl) - keep open"
Write-Host ""
Write-Host "  To stop: close both windows."
Write-Host ""
Write-Host "  Demo login:"
Write-Host "    Email:    mariam@student.aiu.edu.eg"
Write-Host "    Password: demo1234"
Write-Host ""
Write-Host "  (Or sign up with a new email to start fresh.)"
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  This window will close in 10 seconds..."
Start-Sleep -Seconds 10
