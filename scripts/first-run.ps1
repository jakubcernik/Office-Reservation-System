param(
    [switch]$SkipSuperuser
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    Write-Host 'Creating virtual environment...'
    py -m venv .venv
}

Write-Host 'Installing dependencies...'
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

Write-Host 'Running database migrations...'
& $venvPython manage.py migrate

if (-not $SkipSuperuser) {
    $createSuperuser = Read-Host 'Create a superuser now? (y/n)'
    if ($createSuperuser -match '^(y|yes)$') {
        & $venvPython manage.py createsuperuser
    }
}

Write-Host ''
Write-Host 'Initial setup is done.' -ForegroundColor Green
Write-Host 'To start the app next time, run: .\scripts\run.ps1' -ForegroundColor Cyan

