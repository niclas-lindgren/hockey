<#
.SYNOPSIS
  Builds the RVV Miniputt Python backend into a standalone .exe with PyInstaller.
.DESCRIPTION
  Run this on Windows before packaging the Electron app.
  Requires: Python 3.12, pip, and the committed requirements.lock file.

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

if (-not (Test-Path "$RootDir\requirements.lock")) {
  Write-Error "requirements.lock is missing. Run scripts/refresh-python-lock.sh intentionally before packaging."
  exit 1
}

# Install the locked Python dependency set, including desktop packaging tools.
& $Python -m pip install --require-hashes -r requirements.lock
if ($LASTEXITCODE -ne 0) {
  Write-Error "locked dependency install failed"
  exit 1
}

& $Python -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) {
  Write-Error "editable project install failed"
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
