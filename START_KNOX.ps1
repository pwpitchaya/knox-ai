$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$knoxPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $knoxPython)) {
    throw 'Run INSTALL_KNOX.ps1 first to create the project-local .venv. See README.md.'
}
Write-Host 'KNOX AI: http://127.0.0.1:8000 — press Ctrl+C to stop'
& $knoxPython -m uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8000
