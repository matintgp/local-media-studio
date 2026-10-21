param([ValidateSet('mock','real')][string]$Mode='mock',[string]$DataRoot='B:\MediaStudio',[int]$Port=8787)
$ErrorActionPreference='Stop'
if (-not (Test-Path -LiteralPath $DataRoot -PathType Container)) { throw "Data root $DataRoot missing. Create/approve it first; will not fall back to C:." }
$Repo=Split-Path -Parent $PSScriptRoot
$LocalConfig=Join-Path $DataRoot 'studio.local.json'
if (Test-Path -LiteralPath $LocalConfig) {
 $Settings=Get-Content -LiteralPath $LocalConfig -Raw | ConvertFrom-Json
 foreach($Entry in $Settings.PSObject.Properties) {
  if ($Entry.Name -in @('STUDIO_COMFY_OUTPUT_ROOT','STUDIO_WAN_OUTPUT_ROOT','STUDIO_COMFY_URL','STUDIO_WAN_URL','STUDIO_RESERVE_GIB','STUDIO_FFMPEG','STUDIO_FFPROBE')) {
   [Environment]::SetEnvironmentVariable($Entry.Name,[string]$Entry.Value,'Process')
  }
 }
}
$EnvDir=Join-Path $DataRoot '.venv'
if (-not (Test-Path "$EnvDir\Scripts\python.exe")) { throw 'App environment missing. Run scripts/install-windows.ps1 explicitly first.' }
$Python=Join-Path $EnvDir 'Scripts\python.exe'
if (-not (Test-Path (Join-Path $Repo 'frontend\dist\index.html'))) { throw 'Frontend is not built. Run npm ci and npm run build inside frontend first.' }
$env:STUDIO_DATA_ROOT=$DataRoot
$env:STUDIO_MODE=$Mode
if (!$env:STUDIO_RESERVE_GIB) { $env:STUDIO_RESERVE_GIB=if($Mode -eq 'mock') {'0'} else {'60'} }
$Cache=Join-Path $DataRoot 'cache\temp'
New-Item -ItemType Directory -Path $Cache -Force | Out-Null
$env:TEMP=$Cache
$env:TMP=$Cache
$env:PYTHONPATH=Join-Path $Repo 'backend'
Write-Host "MODE: $Mode; Data: $DataRoot; http://127.0.0.1:$Port (Ctrl+C to stop)"
& $Python -m uvicorn studio.app:app --host 127.0.0.1 --port $Port --workers 1 --no-access-log
