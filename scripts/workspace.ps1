#requires -Version 7.4
[CmdletBinding()]
param([switch]$WhatIf)
. "$PSScriptRoot/common.ps1"
$workspace = Get-WorkspaceConfig
if (-not $workspace.Paths.logs) { throw 'Missing logs directory declaration in config/workspace.yaml. Add workspace.directories.logs before running bootstrap.' }
if ($WhatIf) {
    & "$PSScriptRoot/directories.ps1" -WhatIf
    & "$PSScriptRoot/packages.ps1" -WhatIf
    return
}
New-Item -ItemType Directory -Path $workspace.Paths.logs -Force | Out-Null
$log = Join-Path $workspace.Paths.logs "bootstrap-$(Get-Date -Format yyyyMMdd-HHmmss)-$([guid]::NewGuid().ToString('N')).log"
Start-Transcript -LiteralPath $log | Out-Null
try {
    & "$PSScriptRoot/directories.ps1"
    & "$PSScriptRoot/packages.ps1"
    Write-Host "`nBootstrap foundation complete. Applications and models remain planned."
    Write-Host 'Next: just doctor'
} catch {
    Write-Host "`nBootstrap failed: $($_.Exception.Message)"
    Write-Host 'Retry safely with: just bootstrap'
    throw
} finally {
    Stop-Transcript | Out-Null
    Write-Host "Log: $log"
}
