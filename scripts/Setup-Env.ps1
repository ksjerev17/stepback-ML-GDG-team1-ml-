# Windows PowerShell environment setup
# Usage: . .\scripts\Setup-Env.ps1
# All output is ASCII to avoid cp949/UTF-8 encoding issues.

# 1) Force UTF-8 console (prevents Korean garbled output)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 > $null

# 2) Python UTF-8 mode
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# 3) ADMIN_TOKEN for admin endpoints
if (-not $env:ADMIN_TOKEN) {
    $env:ADMIN_TOKEN = "dev_token_local"
    Write-Host "[Setup] ADMIN_TOKEN = dev_token_local (dev only)" -ForegroundColor DarkGray
}

# 4) Mock fallback safe default
if (-not $env:FORCE_MOCK) {
    $env:FORCE_MOCK = "true"
}

# 5) Activate .venv (if present)
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot
$venvActivate = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    & $venvActivate
    Write-Host "[Setup] .venv activated" -ForegroundColor Green
} else {
    Write-Host "[Setup] No .venv found - using global Python" -ForegroundColor Yellow
}

# NOTE: Auto-cd into ml_service removed (was causing path duplication confusion).
#       User stays in repo root. All command examples use 'ml_service\...' prefix.

Write-Host "[Setup] Environment ready (UTF-8 + ADMIN_TOKEN + FORCE_MOCK)" -ForegroundColor Green
Write-Host ""
Write-Host "Current directory: $(Get-Location)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Available commands:" -ForegroundColor Cyan
Write-Host "  python -X utf8 -m pytest ml_service\tests\ -q"
Write-Host "  python -X utf8 ml_service\scripts\test_gemini_e2e.py --skip-llm"
Write-Host "  python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir ml_service"
Write-Host "  . .\scripts\Call-Api.ps1   # load API helpers (Test-Health, Call-Label, Run-Demo)"
