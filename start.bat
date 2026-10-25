@echo off
REM Poker Trainer: double-click to run. Sets up Python packages on first run,
REM starts the server, and opens the app in your browser. Close this window to stop.
cd /d "%~dp0"
title Poker Trainer

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer, then run this again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo First run: creating the Python environment ^(about a minute^)...
  python -m venv .venv || (echo Could not create .venv & pause & exit /b 1)
)

REM Install or update packages only when requirements.txt changed since last time.
set NEED_INSTALL=1
if exist ".venv\installed.txt" (
  fc /b requirements.txt .venv\installed.txt >nul 2>nul && set NEED_INSTALL=0
)
if "%NEED_INSTALL%"=="1" (
  echo Installing packages...
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || (echo Package install failed & pause & exit /b 1)
  copy /y requirements.txt .venv\installed.txt >nul
)

echo.
echo Starting Poker Trainer. Keep this window open while you drill.
echo The phone address is printed below. Close this window to stop.
echo.
start "" /b cmd /c "timeout /t 3 >nul & start http://localhost:8000"
".venv\Scripts\python.exe" -m trainer
pause
