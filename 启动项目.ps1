$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Checking local tools..." -ForegroundColor Cyan
$localYtDlp = Join-Path $root "tools\bin\yt-dlp.exe"
$localFfmpeg = Join-Path $root "tools\bin\ffmpeg.exe"
if (Test-Path $localYtDlp) {
    Write-Host "Found yt-dlp: $localYtDlp" -ForegroundColor Green
} else {
    Write-Host "Local yt-dlp not found in tools\bin." -ForegroundColor Yellow
}
if (Test-Path $localFfmpeg) {
    Write-Host "Found ffmpeg: $localFfmpeg" -ForegroundColor Green
} else {
    Write-Host "Local ffmpeg not found in tools\bin." -ForegroundColor Yellow
}

$pythonExe = "C:\Users\wzml\AppData\Local\Programs\Python\Python313\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe. Please reopen the terminal or update the launcher path."
}

Write-Host "Using Python: $pythonExe" -ForegroundColor Green
Write-Host "Starting backend..." -ForegroundColor Cyan
& $pythonExe "backend\app.py"
