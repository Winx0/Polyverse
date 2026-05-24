# ============================================
# POLYMARKET BTC UP/DOWN BOT - SETUP SCRIPT
# Run in PowerShell: .\setup.ps1
# ============================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  POLYMARKET BTC UP/DOWN BOT - SETUP" -ForegroundColor Cyan
Write-Host "  Modal: `$2 | Target: `$10,000" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[1/4] Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "       Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "       Python not found!" -ForegroundColor Red
    Write-Host "       Download from: https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "       Make sure to check 'Add Python to PATH' during install!" -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host "[2/4] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "       venv already exists, skipping..." -ForegroundColor Gray
} else {
    python -m venv venv
    Write-Host "       Created venv/" -ForegroundColor Green
}

# Activate venv and install dependencies
Write-Host "[3/4] Installing dependencies..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
pip install -r requirements.txt --quiet
Write-Host "       All packages installed!" -ForegroundColor Green

# Setup .env.bot if not exists
Write-Host "[4/4] Checking config..." -ForegroundColor Yellow
if (-Not (Test-Path ".env.bot")) {
    Write-Host "       .env.bot not found - this shouldn't happen." -ForegroundColor Red
    Write-Host "       Make sure .env.bot is in the project root." -ForegroundColor Red
} else {
    Write-Host "       .env.bot found!" -ForegroundColor Green
}

# Create data directory
if (-Not (Test-Path "data/journal")) {
    New-Item -ItemType Directory -Path "data/journal" -Force | Out-Null
    Write-Host "       Created data/journal/ for trade logs" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  SETUP COMPLETE!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Edit .env.bot with your settings" -ForegroundColor White
Write-Host "  2. Run: .\run.ps1" -ForegroundColor White
Write-Host "     (starts in DRY_RUN mode by default)" -ForegroundColor Gray
Write-Host ""
