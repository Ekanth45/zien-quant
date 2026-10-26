<#
.SYNOPSIS
    Zien Quant - Automated Setup Script (Windows PowerShell)
.DESCRIPTION
    Verifies Python >= 3.12, creates runtime directories, copies .env,
    runs database migrations, seeds stock master data, and checks Ollama.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

Write-Host "=== Zien Quant - Environment Setup ===" -ForegroundColor Cyan

# 1. Check Python version >= 3.12
$pythonCmd = "python"
try {
    $pyVerOutput = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
} catch {
    Write-Error "Python is not installed or not found in PATH."
    exit 1
}

$pyParts = $pyVerOutput.Trim().Split(".")
$pyMajor = [int]$pyParts[0]
$pyMinor = [int]$pyParts[1]

if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 12)) {
    Write-Error "Python 3.12 or higher is required. Found Python $pyVerOutput."
    exit 1
}
Write-Host "[OK] Python $pyVerOutput detected." -ForegroundColor Green

# 2. Create runtime directories
New-Item -ItemType Directory -Force -Path "work/runtime" | Out-Null
New-Item -ItemType Directory -Force -Path "work/backups" | Out-Null
Write-Host "[OK] Runtime directories created (work/runtime, work/backups)." -ForegroundColor Green

# 3. Copy .env.example -> .env if missing
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] Created .env from .env.example." -ForegroundColor Green
} else {
    Write-Host "[OK] Existing .env file found." -ForegroundColor Green
}

# 4. Initialize Database Schemas
Write-Host "Initializing database schemas..." -ForegroundColor Gray
& $pythonCmd -c "from marketscope.security import DatabaseManager; import os; db_path = os.environ.get('MS_DB_PATH', 'work/runtime/marketscope.db'); db = DatabaseManager(db_path); print('[OK] MarketScope database schema initialized.')"

# 5. Seed stock master database if missing
$stockDb = if ($env:MS_STOCK_DB) { $env:MS_STOCK_DB } else { "work/runtime/stock_master.db" }
if (-not (Test-Path $stockDb)) {
    Write-Host "Populating stock master database..." -ForegroundColor Gray
    try {
        & $pythonCmd manage.py import-stock-master
        Write-Host "[OK] Stock master database initialized." -ForegroundColor Green
    } catch {
        Write-Host "[WARN] Stock master import warning: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "[OK] Stock master database already exists." -ForegroundColor Green
}

# 6. Check Ollama reachability & model status
& $pythonCmd manage.py check-ollama

# 7. Print next steps
Write-Host ""
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  Setup Complete! Next steps:" -ForegroundColor Cyan
Write-Host "  1. Initialize terminal owner account:" -ForegroundColor White
Write-Host "     python manage.py init-owner" -ForegroundColor Yellow
Write-Host "  2. Start the terminal:" -ForegroundColor White
Write-Host "     .\scripts\run.ps1" -ForegroundColor Yellow
Write-Host "==================================================================" -ForegroundColor Cyan
