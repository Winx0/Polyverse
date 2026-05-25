# ============================================
# POLYMARKET BTC UP/DOWN BOT - RUN SCRIPT
# Run in PowerShell: .\run.ps1
# ============================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  STARTING POLYMARKET BTC BOT..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check venv exists
if (-Not (Test-Path "venv")) {
    Write-Host "[ERROR] Virtual environment not found!" -ForegroundColor Red
    Write-Host "        Run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Activate virtual environment
& .\venv\Scripts\Activate.ps1

# Check .env.bot exists
if (-Not (Test-Path ".env.bot")) {
    Write-Host "[ERROR] .env.bot not found!" -ForegroundColor Red
    Write-Host "        Create .env.bot from the template." -ForegroundColor Red
    exit 1
}

# Run the bot
Write-Host "[INFO] Press Ctrl+C to stop the bot" -ForegroundColor Yellow
Write-Host ""

python -m bot.main
