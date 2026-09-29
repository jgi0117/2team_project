[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$envPath = Join-Path $projectRoot ".env"

function Read-WithDefault {
    param(
        [Parameter(Mandatory = $true)][string]$Prompt,
        [Parameter(Mandatory = $true)][string]$Default
    )
    $entered = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($entered)) { return $Default }
    return $entered.Trim()
}

Set-Location -LiteralPath $projectRoot

if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pythonLauncher) {
        & py -3.12 -m venv .venv
    } else {
        & python -m venv .venv
    }
}

& $venvPython -m pip install -r requirements.txt

$dbHost = Read-WithDefault -Prompt "MySQL host" -Default "127.0.0.1"
$dbPort = Read-WithDefault -Prompt "MySQL port" -Default "3306"
$dbName = Read-WithDefault -Prompt "Database name" -Default "maintenance_dashboard"
$credential = Get-Credential -UserName "root" -Message "Enter the local MySQL account"
$dbUser = $credential.UserName
$dbPassword = $credential.GetNetworkCredential().Password
$authSecret = (& $venvPython -c "import secrets; print(secrets.token_urlsafe(48))").Trim()
$encryptionKey = (& $venvPython -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())").Trim()

if ($dbName -notmatch '^[A-Za-z0-9_]+$') {
    throw "Database name may contain only letters, numbers, and underscores."
}
if ($dbPort -notmatch '^\d+$') {
    throw "MySQL port must be numeric."
}

function Quote-DotEnvValue([string]$value) {
    return '"' + $value.Replace('\', '\\').Replace('"', '\"') + '"'
}

$envContent = @(
    "DB_HOST=$(Quote-DotEnvValue $dbHost)"
    "DB_PORT=$dbPort"
    "DB_NAME=$(Quote-DotEnvValue $dbName)"
    "DB_USER=$(Quote-DotEnvValue $dbUser)"
    "DB_PASSWORD=$(Quote-DotEnvValue $dbPassword)"
    "DB_ENABLED=true"
    "DASH_HOST=0.0.0.0"
    "DASH_PORT=8050"
    "DASH_DEBUG=false"
    "AUTH_ENABLED=true"
    "AUTH_SECRET_KEY=$(Quote-DotEnvValue $authSecret)"
    "DATA_ENCRYPTION_KEY=$(Quote-DotEnvValue $encryptionKey)"
    "DB_RESET_ON_EXIT=true"
) -join [Environment]::NewLine

[System.IO.File]::WriteAllText(
    $envPath,
    $envContent + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)

& $venvPython -m src.database.bootstrap

$dashboardUser = Read-WithDefault -Prompt "Initial dashboard username" -Default "admin"
& $venvPython -m src.database.auth create-user --username $dashboardUser --admin

Write-Host ""
Write-Host "Local database setup complete: $dbName"
Write-Host "Run the dashboard with: .\scripts\run_dashboard.ps1"
