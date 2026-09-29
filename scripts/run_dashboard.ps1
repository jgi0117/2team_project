[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$envPath = Join-Path $projectRoot ".env"

if (-not (Test-Path -LiteralPath $venvPython) -or -not (Test-Path -LiteralPath $envPath)) {
    throw "Local setup is incomplete. Run .\scripts\setup_local_db.ps1 first."
}

Set-Location -LiteralPath $projectRoot
try {
    & $venvPython -m src.ui.app
} finally {
    & $venvPython -m src.database.runtime_reset
}
