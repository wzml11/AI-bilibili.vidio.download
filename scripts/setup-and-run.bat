@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
pushd "%ROOT%"

echo Checking Python...
py -3 --version >nul 2>&1
if errorlevel 1 (
  echo Python Launcher is not available. Please install Python 3.10+ first.
  pause
  exit /b 1
)

py -3 -c "import sys; print(sys.executable)" >nul 2>&1
if errorlevel 1 (
  echo No installed Python interpreter was found for py -3.
  echo Please install Python 3.10+ from python.org or Microsoft Store, then rerun this script.
  pause
  exit /b 1
)

echo Checking yt-dlp...
py -3 -c "import yt_dlp" >nul 2>&1
if errorlevel 1 (
  echo Installing yt-dlp...
  py -3 -m pip install yt-dlp
  if errorlevel 1 (
    echo Failed to install yt-dlp.
    pause
    exit /b 1
  )
)

if exist "%ROOT%\\tools\\bin\\ffmpeg.exe" goto ffmpeg_ok`r`nwhere ffmpeg >nul 2>&1
if errorlevel 1 (
  if errorlevel 1 (\n  echo ffmpeg not found in PATH or tools\\bin. Video merge may fail for some downloads.\n)
)

echo Starting backend...
py -3 backend\app.py

pause
popd
