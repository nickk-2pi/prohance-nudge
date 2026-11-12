@echo off
rem Double-click to open Nudge. Starts it in the background if it isn't running, then opens the browser.
cd /d "%~dp0"
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Method Get http://localhost:8770/).StatusCode | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  where pythonw >nul 2>nul && (start "" pythonw server.py) || (start "Nudge" /min python server.py)
  powershell -NoProfile -Command "$ok=$false; for ($i=0; $i -lt 40 -and -not $ok; $i++) { Start-Sleep -Milliseconds 250; try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 http://localhost:8770/ | Out-Null; $ok=$true } catch {} }"
)
start "" http://localhost:8770/
