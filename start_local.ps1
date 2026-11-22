<#
.SYNOPSIS
One-command local launcher for JanSahayak AI (FastAPI single-worker backend + Vite React frontend).
Automatically clears any stale process on port 8000 so code updates always take effect cleanly.
#>

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Error "Python virtual environment (.venv) not found. Run: python -m venv .venv && .\.venv\Scripts\pip install -r requirements.txt"
}
if (-not (Test-Path "data\jansahayak.db") -or -not (Test-Path "data\index\embeddings.npy")) {
    Write-Host "[INFO] Hybrid index not found. Running data ingestion first..." -ForegroundColor Yellow
    & ".\.venv\Scripts\python.exe" "scripts\ingest_data.py" --scope central
}

# Stop any stale process already occupying port 8000 so the latest backend routes always load
$staleConns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($staleConns) {
    $stalePids = $staleConns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($stalePid in $stalePids) {
        if ($stalePid -and $stalePid -ne $PID) {
            Write-Host "[INFO] Stopping stale backend process (PID $stalePid) on port 8000..." -ForegroundColor Yellow
            Stop-Process -Id $stalePid -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 1
}

Write-Host "[1/2] Starting JanSahayak AI FastAPI backend (single worker, port 8000)..." -ForegroundColor Cyan
$backendProc = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1" `
    -PassThru -NoNewWindow

# Wait until the new backend confirms /api/auth/personas is live
$ready = $false
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Milliseconds 500
    if ($backendProc.HasExited) {
        Write-Error "FastAPI backend exited unexpectedly with code $($backendProc.ExitCode)."
    }
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/auth/personas" -TimeoutSec 2
        if ($resp.personas.Count -ge 1) {
            $ready = $true
            break
        }
    } catch {}
}
if (-not $ready) {
    Write-Warning "Backend took longer than expected to respond on /api/auth/personas; starting frontend anyway."
} else {
    Write-Host "[OK] Backend verified live on http://127.0.0.1:8000 (auth + RAG routes active)." -ForegroundColor Green
}

Write-Host "[2/2] Starting JanSahayak AI React + Vite frontend (port 5173)..." -ForegroundColor Cyan
Write-Host ""
Write-Host "  Open App:     http://localhost:5173" -ForegroundColor Green
Write-Host "  Backend API:  http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop both servers." -ForegroundColor DarkGray
Write-Host ""

try {
    Push-Location "frontend"
    npm run dev
} finally {
    Pop-Location
    if ($backendProc -and -not $backendProc.HasExited) {
        Write-Host "`nStopping FastAPI backend (PID $($backendProc.Id))..." -ForegroundColor Yellow
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
}
