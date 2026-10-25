@echo off
REM Poker Trainer: double-click to run. Checks GitHub for updates, sets up Python
REM packages on first run, starts the server, and opens the app in your browser.
REM Close this window to stop (or use "Stop the trainer" at the bottom of any page).
REM
REM "Poker Trainer.vbs" runs this same file hidden (start.bat --quiet): no window,
REM output goes to trainer.log, and errors show as a pop-up instead of a pause.
cd /d "%~dp0"
title Poker Trainer
set QUIET=0
if /i "%~1"=="--quiet" set QUIET=1
if "%QUIET%"=="1" (
  call :run >> trainer.log 2>&1
  exit /b %errorlevel%
)
call :run
echo.
echo The server stopped. If there is an error above, send a screenshot of this window.
pause
exit /b 0

:run
echo ==== %date% %time% ====
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer, then run this again.
  if "%QUIET%"=="0" pause
  exit /b 1
)

REM Get the latest version from GitHub first (see update.ps1). Never blocks the start.
if exist "update.ps1" powershell -NoProfile -ExecutionPolicy Bypass -File "update.ps1"

if not exist ".venv\Scripts\python.exe" (
  echo First run: creating the Python environment ^(about a minute^)...
  python -m venv .venv || (echo Could not create .venv & if "%QUIET%"=="0" pause & exit /b 1)
)

REM Install or update packages only when requirements.txt changed since last time.
set NEED_INSTALL=1
if exist ".venv\installed.txt" (
  fc /b requirements.txt .venv\installed.txt >nul 2>nul && set NEED_INSTALL=0
)
if "%NEED_INSTALL%"=="1" (
  echo Installing packages...
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || (echo Package install failed & if "%QUIET%"=="0" pause & exit /b 1)
  copy /y requirements.txt .venv\installed.txt >nul
)

echo.
echo Starting Poker Trainer. Keep this window open while you drill.
echo The phone address is printed below. Close this window to stop.
echo.
REM The app opens the browser itself once the server is ready. If a Poker Trainer is
REM already running (an earlier window), it opens that one or replaces it if it is older.
".venv\Scripts\python.exe" -m trainer
exit /b %errorlevel%
