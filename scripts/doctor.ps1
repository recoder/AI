#requires -Version 7.4
[CmdletBinding()]
param([switch]$HelpersOnly)
. "$PSScriptRoot/common.ps1"
Update-ProcessPath
$workspace = Get-WorkspaceConfig
$failures = 0
Write-Host 'Helper tools'
foreach ($package in @(Get-PackageConfig)) {
    $state = Get-PackageState $package
    if ($state.Usable) { Write-Host "  OK $($state.Name): $($state.Detail)" }
    else { $failures++; Write-Host "  FAIL $($state.Name): $($state.Detail). Repair: just packages" }
}
Write-Host 'Workspace directories'
foreach ($entry in $workspace.Paths.GetEnumerator()) {
    if (Test-Path -LiteralPath $entry.Value -PathType Container) { Write-Host "  OK $($entry.Key)" }
    else { $failures++; Write-Host "  FAIL $($entry.Key): missing directory. Repair: just directories" }
}
if (-not $HelpersOnly -and (Test-Path -LiteralPath (Join-Path $script:RepositoryRoot 'config/tools.yaml'))) {
    . "$PSScriptRoot/../tools/yue/common.ps1"
    try { & "$PSScriptRoot/../tools/yue/validate.ps1" }
    catch { $failures++; Write-Host "  FAIL YuE: $($_.Exception.Message)" }
}
if ($failures) { throw "Doctor found $failures problem(s). See repair commands above." }
