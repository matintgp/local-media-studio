param([ValidateSet('mock','real')][string]$Mode='mock',[string]$DataRoot='B:\MediaStudio',[int]$Port=8787)
$ErrorActionPreference='Stop'
if (-not (Test-Path -LiteralPath $DataRoot -PathType Container)) { throw "Data root $DataRoot missing. Create/approve it first; will not fall back to C:." }
$Repo=Split-Path -Parent $PSScriptRoot
$EnvDir=Join-Path $DataRoot 'studio-venv'
if (-not (Test-Path "$EnvDir\Scripts\python.exe")) { py -3.11 -m venv $EnvDir }
$Python=Join-Path $EnvDir 'Scripts\python.exe'
if (-not (Test-Path (Join-Path $Repo 'frontend\dist\index.html'))) { throw 'Frontend is not built. Run npm ci and npm run build inside frontend first.' }
$env:STUDIO_DATA_ROOT=$DataRoot
$env:STUDIO_MODE=$Mode
$env:STUDIO_RESERVE_GIB=if($Mode -eq 'mock') {'0'} else {'60'}
$env:PYTHONPATH=Join-Path $Repo 'backend'
Write-Host "MODE: $Mode; Data: $DataRoot; http://127.0.0.1:$Port (Ctrl+C to stop)"
& $Python -m uvicorn studio.app:app --host 127.0.0.1 --port $Port --workers 1
