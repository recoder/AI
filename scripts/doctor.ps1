#requires -Version 7.4
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
Write-Host 'Applications/GPU/models: checks pending; this report covers the bootstrap foundation only.'
if ($failures) { throw "Doctor found $failures problem(s). See repair commands above." }
