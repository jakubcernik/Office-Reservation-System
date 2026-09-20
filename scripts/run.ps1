param(
    [string]$Address = '127.0.0.1',
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    throw 'Virtual environment not found. Run .\scripts\first-run.ps1 first.'
}

& $venvPython manage.py runserver "$Address`:$Port"


