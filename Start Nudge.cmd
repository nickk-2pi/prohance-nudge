@echo off
rem Double-click to open Nudge. Starts it if it isn't running, then opens the browser.
rem Problems are shown in this window instead of failing silently.
setlocal
cd /d "%~dp0"
set "URL=http://localhost:8770/"
rem Checks use 127.0.0.1: "localhost" tries IPv6 first, which can take over a second.
set "PROBE=http://127.0.0.1:8770/"

call :up 2
if not errorlevel 1 goto open

rem Find a real Python 3.9+ (the Microsoft Store "python" placeholder doesn't count).
set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>nul && set "PY=python"
if not defined PY (
  echo.
  echo  Nudge needs Python 3.9 or newer, and none was found.
  echo.
  echo  1. Install it from https://www.python.org/downloads/
  echo     and tick "Add python.exe to PATH" on the first screen.
  echo  2. If Python is installed but this still appears: Windows Settings ^> Apps ^>
  echo     Advanced app settings ^> App execution aliases, and turn OFF both "python.exe"
  echo     and "python3.exe" ^(App Installer^).
  echo  3. Close this window and double-click Start Nudge again.
  echo.
  pause
  exit /b 1
)

rem The server runs in its own minimized window; closing that window stops Nudge.
rem If the server fails to start, that window stays open with the error.
start "Nudge server - keep this open" /min cmd /c "%PY% server.py || (echo. & echo Nudge stopped with the error above. & pause)"

call :up 40
if errorlevel 1 (
  echo.
  echo  Nudge didn't start. Open the "Nudge server" window on the taskbar to see why.
  echo  If it says the address is in use, another program has port 8770: run
  echo     %PY% server.py --port 8771
  echo  in this folder and open http://localhost:8771/ instead.
  echo.
  pause
  exit /b 1
)

:open
start "" "%URL%"
exit /b 0

rem :up N  waits up to N quarter-seconds for Nudge to answer; errorlevel 0 when it does.
:up
powershell -NoProfile -Command "for ($i=0; $i -lt %1; $i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%PROBE%' | Out-Null; exit 0 } catch { Start-Sleep -Milliseconds 250 } }; exit 1"
exit /b %errorlevel%
