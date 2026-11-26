<#
.SYNOPSIS
Creates a private zip bundle (`JanSahayak_Private_Team_Bundle.zip`, gitignored) containing:
  - .env (IIT KGP API keys + Gmail SMTP config)
  - certs/ (TLS CA certificates)
  - data/jansahayak.db (SQLite catalog + FAQs + pre-seeded tables)
  - data/index/ (embeddings.npy, bm25.pkl, index_manifest.json)
Share this zip privately with your capstone teammates so they can run JanSahayak AI in 2 minutes
without waiting 9 minutes to re-embed all 6,059 chunks!
NEVER commit or upload this zip to GitHub.
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$OutZip = Join-Path $Root "JanSahayak_Private_Team_Bundle.zip"
$StageDir = Join-Path $env:TEMP ("jansahayak_bundle_" + [guid]::NewGuid().ToString("N").Substring(0, 8))

New-Item -ItemType Directory -Path $StageDir -Force | Out-Null
try {
    $copied = @()

    if (Test-Path ".env") {
        Copy-Item ".env" (Join-Path $StageDir ".env")
        $copied += ".env"
    } else {
        Write-Warning ".env not found — teammates will need to configure .env manually."
    }

    if (Test-Path "certs") {
        Copy-Item "certs" (Join-Path $StageDir "certs") -Recurse
        $copied += "certs/"
    }

    # Include VM02 cert if referenced from Capstone_Overview_resources
    $vm02Cert = "Capstone_Overview_resources\API\VM02_Embeddings_Access\vm02-ca.crt"
    if (Test-Path $vm02Cert) {
        $vm02Dest = Join-Path $StageDir "Capstone_Overview_resources\API\VM02_Embeddings_Access"
        New-Item -ItemType Directory -Path $vm02Dest -Force | Out-Null
        Copy-Item $vm02Cert (Join-Path $vm02Dest "vm02-ca.crt")
        $copied += "vm02-ca.crt"
    }

    if (Test-Path "data\jansahayak.db") {
        New-Item -ItemType Directory -Path (Join-Path $StageDir "data") -Force | Out-Null
        Copy-Item "data\jansahayak.db" (Join-Path $StageDir "data\jansahayak.db")
        $copied += "data/jansahayak.db"
    }

    if (Test-Path "data\index") {
        New-Item -ItemType Directory -Path (Join-Path $StageDir "data\index") -Force | Out-Null
        Copy-Item "data\index\*" (Join-Path $StageDir "data\index") -Recurse
        $copied += "data/index/ (embeddings.npy + bm25.pkl + manifest)"
    }

    if (Test-Path $OutZip) { Remove-Item $OutZip -Force }
    Compress-Archive -Path (Join-Path $StageDir "*") -DestinationPath $OutZip -CompressionLevel Optimal

    $sizeMb = [math]::Round((Get-Item $OutZip).Length / 1MB, 2)
    Write-Host "[OK] Created private team bundle: $OutZip ($sizeMb MB)" -ForegroundColor Green
    Write-Host "Included: $($copied -join ', ')" -ForegroundColor Cyan
    Write-Host "Share this ZIP privately (Google Drive / OneDrive / Teams / WhatsApp) — NEVER push it to GitHub!" -ForegroundColor Yellow
} finally {
    if (Test-Path $StageDir) { Remove-Item $StageDir -Recurse -Force -ErrorAction SilentlyContinue }
}
