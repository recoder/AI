#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
Update-ProcessPath
$workspace = Get-WorkspaceConfig
$packages = @(Get-PackageConfig | ForEach-Object { Get-PackageState $_ })
$present = @($workspace.Paths.Values | Where-Object { Test-Path -LiteralPath $_ -PathType Container }).Count
Write-Host "Workspace: $($workspace.Root)"
Write-Host "Helper packages: $(@($packages | Where-Object Usable).Count)/$($packages.Count)"
Write-Host "Directories: $present/$($workspace.Paths.Count)"
Write-Host 'Applications/models/runners: not implemented yet'
