# ============================================
# QUICK DRY RUN TEST - 5 minutes
# Run: .\run_drytest.ps1
# ============================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  DRY RUN TEST (5 minutes)" -ForegroundColor Cyan
Write-Host "  No real money - simulation only" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check venv
if (-Not (Test-Path "venv")) {
    Write-Host "[ERROR] Run .\setup.ps1 first!" -ForegroundColor Red
    exit 1
}

# Activate
& .\venv\Scripts\Activate.ps1

# Force DRY_RUN and short interval for testing
$env:DRY_RUN = "true"
$env:BANKROLL = "2.00"
$env:MIN_BET = "0.50"
$env:MAX_BET = "2.00"
$env:LOOP_INTERVAL = "15"
$env:MIN_PROB = "0.60"
$env:MIN_EDGE = "0.03"

Write-Host "[INFO] Running with relaxed thresholds for testing" -ForegroundColor Yellow
Write-Host "[INFO] LOOP_INTERVAL=15s, MIN_PROB=0.60, MIN_EDGE=0.03" -ForegroundColor Yellow
Write-Host "[INFO] Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

python -m bot.main
