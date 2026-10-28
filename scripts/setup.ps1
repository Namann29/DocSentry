# One-time setup on Windows. Run from the repository root:  powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location (Join-Path $Root "backend")
if (-not (Test-Path ".venv")) { python -m pip install virtualenv; python -m virtualenv .venv }
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (-not (Test-Path ".env")) { Copy-Item .env.example .env }
python corpus\generate.py
python corpus\make_tampered.py
python corpus\make_images.py
python corpus\make_demo_set.py
Set-Location (Join-Path $Root "frontend")
npm install
Write-Host "Setup complete. Optional OCR: winget install UB-Mannheim.TesseractOCR ; pip install -r backend\requirements-ocr.txt"
Write-Host "Start: backend -> uvicorn app.main:app --reload --port 8000 | frontend -> npm run dev"