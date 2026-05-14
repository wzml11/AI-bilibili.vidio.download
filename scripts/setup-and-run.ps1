$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Checking Python..." -ForegroundColor Cyan
try {
    $py = py -3 --version
    Write-Host $py
} catch {
    throw "Python Launcher is not available. Please install Python 3.10+ first."
}

try {
    py -3 -c "import sys; print(sys.executable)" | Out-Null
} catch {
    throw "No installed Python interpreter was found for py -3. Please install Python 3.10+ first."
}

Write-Host "Checking yt-dlp..." -ForegroundColor Cyan
$ydlpOk = $false
try {
    py -3 -c "import yt_dlp" | Out-Null
    $ydlpOk = $true
} catch {
    $ydlpOk = $false
}

if (-not $ydlpOk) {
    Write-Host "Installing yt-dlp..." -ForegroundColor Yellow
    py -3 -m pip install yt-dlp
}

Write-Host "Checking ffmpeg..." -ForegroundColor Cyan`n$localFfmpeg = Join-Path $root "tools\\bin\\ffmpeg.exe"
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg -and -not (Test-Path $localFfmpeg)) {
    Write-Host "ffmpeg not found in PATH, but a local copy may be available in tools\\bin." -ForegroundColor Yellow
}

Write-Host "Starting backend..." -ForegroundColor Cyan
py -3 backend/app.py
