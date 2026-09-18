#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
Update-ProcessPath
$workspace = Get-WorkspaceConfig
$packages = @(Get-PackageConfig | ForEach-Object { Get-PackageState $_ })
$present = @($workspace.Paths.Values | Where-Object { Test-Path -LiteralPath $_ -PathType Container }).Count
Write-Host "Workspace: $($workspace.Root)"
Write-Host "Helper packages: $(@($packages | Where-Object Usable).Count)/$($packages.Count)"
Write-Host "Directories: $present/$($workspace.Paths.Count)"
if (Test-Path -LiteralPath (Join-Path $script:RepositoryRoot 'config/tools.yaml')) {
    . "$PSScriptRoot/../tools/yue/common.ps1"
    $state = Get-YueState
    Write-Host "YuE source: $($state.Source.Detail)"
    Write-Host "YuE native environment: $($state.Runtime); models: $($state.Models); runner config: $($state.Runner)"
    Write-Host 'Deep checks: just validate yue'
}
