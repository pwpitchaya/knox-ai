$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$knoxEnv = Join-Path $PSScriptRoot '.venv'
if (-not (Test-Path -LiteralPath (Join-Path $knoxEnv 'Scripts\python.exe'))) {
    py -3.13 -m venv $knoxEnv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.13, then run this installer again.' }
}
$knoxPython = Join-Path $knoxEnv 'Scripts\python.exe'
& $knoxPython -m pip install -r backend/requirements-local.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the network and retry.' }
if (-not (Test-Path -LiteralPath 'backend/.env')) {
    Copy-Item -LiteralPath 'backend/.env.example' -Destination 'backend/.env'
    Write-Host 'Created backend/.env. Set ADMIN_USER and ADMIN_PASSWORD before starting KNOX AI.'
}
Write-Host 'Base installation complete. Run .\START_KNOX.ps1.'
Write-Host 'E5 is optional: .\.venv\Scripts\python.exe -m pip install -r backend/requirements-semantic.txt'
