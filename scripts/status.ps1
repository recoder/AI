#requires -Version 7.4
[CmdletBinding()]
param([string]$Profile)
. "$PSScriptRoot/profiles.ps1"
. "$PSScriptRoot/application-common.ps1"
$workspace = Get-WorkspaceConfig
$selected = Get-WorkspaceProfile $Profile
Update-ProcessPath
$packages = @(Get-PackageConfig | Where-Object { $_.name -in $selected.packages } | ForEach-Object { Get-PackageState $_ })
$present = @($workspace.Paths.Values | Where-Object { Test-Path -LiteralPath $_ -PathType Container }).Count
Write-Host "Workspace: $($workspace.Root)"
Write-Host "Profile: $($selected.Name)"
Write-Host "Helper packages: $(@($packages | Where-Object Usable).Count)/$($packages.Count)"
Write-Host "Directories: $present/$($workspace.Paths.Count)"
& "$PSScriptRoot/tool-service.ps1" -Operation status
foreach ($tool in $selected.tools) {
    $stateScript = Join-Path $script:RepositoryRoot "tools/$tool/state.ps1"
    if (-not (Test-Path -LiteralPath $stateScript)) { Write-Host "PENDING ${tool}: state adapter missing"; continue }
    $state = & $stateScript
    Write-Host "${tool}: ready=$($state.Ready), runtime=$($state.Runtime), models=$($state.Models), runner=$($state.Runner)"
}
foreach ($repo in @(Get-UserRepositoryConfig | Where-Object { $_.Name -in $selected.repos })) {
    $state = Get-RepositoryState $repo.Path $repo.Remote $repo.Revision
    Write-Host "Repository $($repo.Name): $($state.Detail)"
}
