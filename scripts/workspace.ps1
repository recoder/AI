#requires -Version 7.4
[CmdletBinding()]
param([switch]$WhatIf, [string]$Profile)
. "$PSScriptRoot/profiles.ps1"
. "$PSScriptRoot/restart.ps1"
$workspace = Get-WorkspaceConfig
$selected = Get-WorkspaceProfile $Profile
if ($WhatIf) {
    Write-Host "Profile: $($selected.Name)"
    & "$PSScriptRoot/directories.ps1" -WhatIf
    & "$PSScriptRoot/packages.ps1" -Names $selected.packages -WhatIf
    foreach ($kind in @('tools','repos','models')) { foreach ($item in $selected.$kind) { Write-Host "PLAN reconcile $kind $item" } }
    Write-Host 'PLAN apply declared shared caches and validate selected components'
    return
}
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Full workspace reconciliation must run in a normal shell. Use bootstrap.ps1 -MachineOnly for elevated machine prerequisites.' }
New-Item -ItemType Directory -Path $workspace.Paths.logs -Force | Out-Null
$log = Join-Path $workspace.Paths.logs "bootstrap-$(Get-Date -Format yyyyMMdd-HHmmss)-$([guid]::NewGuid().ToString('N')).log"
Start-Transcript -LiteralPath $log | Out-Null
$results = [Collections.Generic.List[object]]::new()
function Invoke-ReconciliationStep {
    param([string]$Name, [scriptblock]$Action, [string]$Repair)
    Write-Host "`nReconciling $Name"
    try {
        & $Action | Out-Host
        $results.Add([pscustomobject]@{Name=$Name; Success=$true; Detail='ready'; Repair=$Repair})
        return $true
    } catch {
        $results.Add([pscustomobject]@{Name=$Name; Success=$false; Detail=$_.Exception.Message; Repair=$Repair})
        Write-Host "FAIL ${Name}: $($_.Exception.Message)"
        return $false
    }
}
function Invoke-ToolComponent([string]$Operation,[string]$Tool) {
    & pwsh -NoProfile -File "$PSScriptRoot/tools.ps1" -Operation $Operation -Tool $Tool
    if ($LASTEXITCODE -ne 0) { throw "Tool $Tool $Operation failed (exit $LASTEXITCODE); inspect its component log." }
}
try {
    Write-Host "AI Workspace Bootstrap — profile $($selected.Name)"
    $directoryReady = Invoke-ReconciliationStep 'directories' { & "$PSScriptRoot/directories.ps1" } 'just directories'
    $beforeRestart = @(Get-WorkspaceRestartReasons)
    $packagesReady = Invoke-ReconciliationStep 'prerequisites' {
        & "$PSScriptRoot/packages.ps1" -Names $selected.packages
        $newRestart = @(Get-WorkspaceRestartReasons | Where-Object { $_ -notin $beforeRestart })
        if ($newRestart) { throw "New reboot requirement: $($newRestart -join ', '). Restart Windows, then retry bootstrap with the same profile." }
    } 'bootstrap.ps1 -MachineOnly (administrator), then retry bootstrap normally'
    if ($directoryReady -and $packagesReady) {
        $cacheReady = Invoke-ReconciliationStep 'shared cache configuration' {
            $scope = (Read-WorkspaceManifest workspace).workspace.environment_scope
            if ($scope -notin @('user','process')) { throw 'workspace.environment_scope must be user or process.' }
            Set-WorkspaceCacheEnvironment -Persist:($scope -eq 'user')
        } 'check config/workspace.yaml and rerun bootstrap'
        if ($cacheReady) {
            $failedTools = @()
            foreach ($tool in $selected.tools) {
                if (-not (Invoke-ReconciliationStep "tool $tool" { Invoke-ToolComponent install $tool } "just install $tool")) { $failedTools += $tool }
            }
            if ($selected.repos.Count) { $null = Invoke-ReconciliationStep 'user repositories' { & "$PSScriptRoot/repositories.ps1" -Names $selected.repos } 'just repos' }
            $failedModels = @()
            foreach ($group in $selected.models) {
                if ($group -in $failedTools) { Write-Host "SKIP models ${group}: repair its tool first"; $failedModels += $group; continue }
                if (-not (Invoke-ReconciliationStep "models $group" { & "$PSScriptRoot/models.ps1" -Group $group } "just models $group")) { $failedModels += $group }
            }
            foreach ($tool in $selected.tools) {
                if ($tool -in $failedTools -or $tool -in $failedModels) { Write-Host "SKIP validation ${tool}: repair previous failure first"; continue }
                $null = Invoke-ReconciliationStep "validation $tool" { Invoke-ToolComponent validate $tool } "just validate $tool"
            }
        } else { Write-Host 'SKIP tools/repositories/models: repair shared cache configuration first.' }
    } else { Write-Host 'SKIP tools/repositories/models: repair prerequisites/directories first.' }
    Write-Host "`nAI Workspace Bootstrap Summary — $($selected.Name)"
    foreach ($result in $results) {
        if ($result.Success) { Write-Host "OK $($result.Name)" }
        else { Write-Host "FAIL $($result.Name): $($result.Detail)"; Write-Host "  Repair: $($result.Repair)" }
    }
    $restart = @(Get-WorkspaceRestartReasons)
    if ($restart) { Write-Host "WARN restart pending: $($restart -join ', ')" }
    $failures = @($results | Where-Object { -not $_.Success })
    if ($failures.Count) { throw "Bootstrap has $($failures.Count) failed component(s). Partial work is preserved; retry the same profile after repair. Log: $log" }
    Write-Host "Next: just doctor $($selected.Name)"
} finally { Stop-Transcript | Out-Null; Write-Host "Log: $log" }
