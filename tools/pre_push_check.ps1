# Pre-push checks for CryptidCompanion (run from repository root).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "=== CryptidCompanion pre-push checks ===" -ForegroundColor Cyan

Write-Host "`n[1/3] pytest (unit + integration)..." -ForegroundColor Yellow
python -m pip install -q -r requirements-dev.txt
python -m pytest tests/unit tests/integration -v --tb=short
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[2/3] Map validation script..." -ForegroundColor Yellow
python tests/validate_maps_intersections.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[3/3] Smoke import (app entry)..." -ForegroundColor Yellow
$env:PYTHONPATH = "src\cryptid"
python -c "from ui.shared.custom_map_save import ensure_custom_maps_json; ensure_custom_maps_json(); import app"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`nAll checks passed." -ForegroundColor Green
