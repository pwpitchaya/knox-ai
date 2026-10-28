$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$knoxPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $knoxPython)) { throw 'Run INSTALL_KNOX.ps1 first to create the project-local .venv.' }
& $knoxPython -m pip install --target backend/vendor --only-binary=:all: --no-deps tesserocr==2.12.0
if ($LASTEXITCODE -ne 0) { throw 'OCR package installation failed' }
New-Item -ItemType Directory -Path backend/ocr_models -Force | Out-Null
foreach ($knoxLang in @('tha', 'eng')) {
    Invoke-WebRequest -Uri "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/$knoxLang.traineddata" -OutFile "backend/ocr_models/$knoxLang.traineddata"
}
Write-Host 'Thai OCR ready. pdftoppm must also be available on PATH.'
