<#
.SYNOPSIS
  Builds the RVV Miniputt Python backend into a standalone .exe with PyInstaller.
.DESCRIPTION
  Run this on Windows before packaging the Electron app.
  Requires: Python 3.12, pip, and all requirements.txt dependencies installed.

  Usage:
    powershell -ExecutionPolicy Bypass -File scripts/package-desktop-backend.ps1

  Then:
    cd apps\desktop
    npm install
    npm run dist
#>

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $RootDir

# Discover Python
$Python = ""
if ($env:PYTHON_BIN) {
  $Python = $env:PYTHON_BIN
} elseif (Test-Path "$RootDir\venv\Scripts\python.exe") {
  $Python = "$RootDir\venv\Scripts\python.exe"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  $Python = "python"
} else {
  Write-Error "Python not found. Install Python 3.12 and try again."
  exit 1
}

Write-Host "Using Python: $Python"

# Ensure pyinstaller is installed
& $Python -m pip install --upgrade pyinstaller keyring
if ($LASTEXITCODE -ne 0) {
  Write-Error "pip install failed"
  exit 1
}

# Build with PyInstaller
& $Python -m PyInstaller `
  --name rvv-miniputt-backend `
  --clean `
  --noconfirm `
  --collect-all tournament_scheduler `
  --hidden-import keyring.backends.Windows `
  --hidden-import keyring.backends.macOS `
  --hidden-import keyring.backends.SecretService `
  --distpath dist\desktop-backend `
  --workpath build\desktop-backend `
  tournament_scheduler\desktop_server.py

if ($LASTEXITCODE -ne 0) {
  Write-Error "PyInstaller build failed"
  exit 1
}

Write-Host ""
Write-Host "Desktop backend built in dist\desktop-backend\rvv-miniputt-backend\"
Write-Host ""
Write-Host "Next:"
Write-Host "  cd apps\desktop"
Write-Host "  npm install"
Write-Host "  npm run dist"
