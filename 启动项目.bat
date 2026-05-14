@echo off
setlocal

set "ROOT=%~dp0"
pushd "%ROOT%"

if exist "tools\bin\yt-dlp.exe" (
  echo Found local yt-dlp: tools\bin\yt-dlp.exe
) else (
  echo Local yt-dlp not found in tools\bin.
)

if exist "tools\bin\ffmpeg.exe" (
  echo Found local ffmpeg: tools\bin\ffmpeg.exe
) else (
  echo Local ffmpeg not found in tools\bin.
)

set "PYTHON_EXE=C:\Users\wzml\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Python 3.13 executable was not found at:
  echo %PYTHON_EXE%
  echo Please reopen the terminal or update the launcher path if Python moved.
  pause
  popd
  exit /b 1
)

echo Using Python: %PYTHON_EXE%
echo Starting backend at project root...
"%PYTHON_EXE%" backend\app.py
popd
