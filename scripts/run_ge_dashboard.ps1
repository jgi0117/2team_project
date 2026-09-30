[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "가상환경이 없습니다. 먼저 python -m venv .venv 를 실행하세요."
}

Set-Location -LiteralPath $projectRoot
& $python app.py
