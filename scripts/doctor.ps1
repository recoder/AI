#requires -Version 7.4
[CmdletBinding()]
param([switch]$HelpersOnly, [string]$Profile)
. "$PSScriptRoot/profiles.ps1"
. "$PSScriptRoot/application-common.ps1"
. "$PSScriptRoot/restart.ps1"
Update-ProcessPath
$workspace = Get-WorkspaceConfig
$selected = Get-WorkspaceProfile $Profile
$failures = 0
Write-Host "Profile: $($selected.Name)"
Write-Host 'Helper tools'
foreach ($package in @(Get-PackageConfig | Where-Object { $_.name -in $selected.packages })) {
    $state = Get-PackageState $package
    if ($state.Usable) { Write-Host "  OK $($state.Name): $($state.Detail)" }
    else { $failures++; Write-Host "  FAIL $($state.Name): $($state.Detail). Repair: just packages" }
}
Write-Host 'Workspace directories'
foreach ($entry in $workspace.Paths.GetEnumerator()) {
    if (Test-Path -LiteralPath $entry.Value -PathType Container) { Write-Host "  OK $($entry.Key)" }
    else { $failures++; Write-Host "  FAIL $($entry.Key): missing directory. Repair: just directories" }
}
if (-not $HelpersOnly) {
    if ('tool-service' -notin $selected.tools) {
        $serviceDeclaration = (Read-WorkspaceManifest tools).tools['tool-service']
        $servicePython = Join-Path (Join-Path $workspace.Root $serviceDeclaration.path) '.venv/Scripts/python.exe'
        if (Test-Path -LiteralPath $servicePython -PathType Leaf) {
            try { & "$PSScriptRoot/tool-service.ps1" -Operation validate }
            catch { $failures++; Write-Host '  FAIL tool service: see diagnostics above. Repair: just validate tool-service' }
        } else { Write-Host '  INFO optional tool service not installed. Install: just install tool-service' }
    }
    Write-Host 'Shared caches'
    $environment = (Read-WorkspaceManifest workspace).workspace.environment
    foreach ($entry in $environment.GetEnumerator()) {
        $scope = (Read-WorkspaceManifest workspace).workspace.environment_scope
        $actual = [Environment]::GetEnvironmentVariable($entry.Key, $(if ($scope -eq 'user') {'User'} else {'Process'}))
        if ($actual -eq $workspace.Paths[$entry.Value]) { Write-Host "  OK $($entry.Key)" }
        else { $failures++; Write-Host "  FAIL $($entry.Key): differs from declared cache path. Repair: just bootstrap core" }
    }
    foreach ($tool in $selected.tools) {
        try {
            & pwsh -NoProfile -File "$PSScriptRoot/tools.ps1" -Operation validate -Tool $tool
            if ($LASTEXITCODE -ne 0) { throw 'component validation failed; see output above' }
        } catch { $failures++; Write-Host "  FAIL ${tool}: $($_.Exception.Message). Repair: just install $tool / just models $tool" }
    }
    foreach ($repo in @(Get-UserRepositoryConfig | Where-Object { $_.Name -in $selected.repos })) {
        $state = Get-RepositoryState $repo.Path $repo.Remote $repo.Revision
        if ($state.Ready) { Write-Host "  OK repository $($repo.Name): $($state.Detail)" }
        else { $failures++; Write-Host "  FAIL repository $($repo.Name): $($state.Detail). Repair: just repos" }
    }
    $drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($workspace.Root))
    if ($drive.AvailableFreeSpace -lt 5GB) { Write-Host '  WARN disk free space below 5 GiB; allow space before installing more models.' }
    else { Write-Host "  OK disk: $([math]::Round($drive.AvailableFreeSpace/1GB)) GiB free" }
    Write-Host $(if($env:HF_TOKEN){'  INFO HF_TOKEN available (value hidden)'}else{'  INFO HF_TOKEN absent; public models do not require it'})
}
$restart = @(Get-WorkspaceRestartReasons)
if ($restart) { Write-Host "WARN restart pending: $($restart -join ', ')" }
if ($failures) { throw "Doctor found $failures problem(s). See repair commands above." }
