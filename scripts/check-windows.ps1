param([string]$DataRoot='B:\MediaStudio')
$ErrorActionPreference='Stop'
Write-Host 'Read-only Local Media Studio prerequisites'
Write-Host ('Data root exists: '+(Test-Path -LiteralPath $DataRoot -PathType Container))
foreach($tool in @('py','node','npm','ffmpeg','ffprobe')) {
 $found=Get-Command $tool -ErrorAction SilentlyContinue
 Write-Host "$tool : $(if ($found) { $found.Source } else { 'MISSING' })"
}
foreach($endpoint in @('http://127.0.0.1:8188/system_stats','http://127.0.0.1:7866/mcp')) {
 try { $resp=Invoke-WebRequest -Method Get -Uri $endpoint -TimeoutSec 3 -UseBasicParsing;Write-Host "$endpoint : HTTP $($resp.StatusCode) (MCP GET may require session POST)" }
 catch { Write-Host "$endpoint : not verified (no engines were started)" }
}
