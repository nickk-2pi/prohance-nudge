# Optional: start Nudge silently whenever you sign in to Windows, and put a "Nudge" shortcut on the desktop.
# Run once:      powershell -ExecutionPolicy Bypass -File install-autostart.ps1
# To undo:       powershell -ExecutionPolicy Bypass -File install-autostart.ps1 -Remove
param([switch]$Remove)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$startup = [Environment]::GetFolderPath("Startup")
$desktop = [Environment]::GetFolderPath("Desktop")
$autoLink = Join-Path $startup "Nudge (background).lnk"
$deskLink = Join-Path $desktop "Nudge.lnk"

if ($Remove) {
    Remove-Item $autoLink, $deskLink -ErrorAction SilentlyContinue
    Write-Host "Removed the auto-start entry and the desktop shortcut."
    return
}

$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pythonw) { Write-Host "pythonw.exe wasn't found on PATH. Install Python from python.org first."; return }

$shell = New-Object -ComObject WScript.Shell
$s = $shell.CreateShortcut($autoLink)
$s.TargetPath = $pythonw
$s.Arguments = "`"$here\server.py`""
$s.WorkingDirectory = $here
$s.Description = "Nudge, running in the background on http://localhost:8770"
$s.Save()

$d = $shell.CreateShortcut($deskLink)
$d.TargetPath = Join-Path $here "Start Nudge.cmd"
$d.WorkingDirectory = $here
$d.WindowStyle = 7  # minimised: the console flashes away
$d.Description = "Open Nudge"
$d.Save()

Write-Host "Done. Nudge now starts silently when you sign in to Windows."
Write-Host "Open it any time with the 'Nudge' desktop shortcut or http://localhost:8770"
