param([string]$DataRoot='B:\MediaStudio',[string]$PythonVersion='3.12')
$ErrorActionPreference='Stop'
$Repo=Split-Path -Parent $PSScriptRoot
if (!(Test-Path -LiteralPath $DataRoot -PathType Container)) { throw 'Create and approve the data root explicitly before installing.' }
$EnvDir=Join-Path $DataRoot '.venv'
$env:UV_CACHE_DIR=Join-Path $DataRoot 'cache\uv'
$env:npm_config_cache=Join-Path $DataRoot 'cache\npm'
$env:TEMP=Join-Path $DataRoot 'cache\temp'
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Path $env:TEMP,$env:UV_CACHE_DIR,$env:npm_config_cache -Force | Out-Null
if (!(Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install/configure uv first. This script does not install a Python runtime or models.' }
if (!(Test-Path -LiteralPath (Join-Path $EnvDir 'Scripts\python.exe'))) {
 uv venv --no-python-downloads --python $PythonVersion $EnvDir
 if ($LASTEXITCODE) { throw 'Could not create isolated app environment with installed Python.' }
}
uv pip install --no-cache --python (Join-Path $EnvDir 'Scripts\python.exe') -r (Join-Path $Repo 'backend\requirements.lock')
if ($LASTEXITCODE) { throw 'Backend installation failed.' }
Push-Location (Join-Path $Repo 'frontend')
try {
 npm.cmd ci --ignore-scripts --no-audit --no-fund
 if ($LASTEXITCODE) { throw 'Frontend installation failed.' }
 npm.cmd run build
 if ($LASTEXITCODE) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host 'App installed separately from model engines. No engine packages or weights were installed.'
