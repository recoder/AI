#requires -Version 7.4
# Focused bootstrap checks without installers or external test dependencies.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/../scripts/common.ps1"
function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "Assertion failed: $Message" }
}
$originalRoot = $env:AI_WORKSPACE_ROOT
$testRoot = Join-Path $script:RepositoryRoot "cache/bootstrap-tests/$([guid]::NewGuid().ToString('N'))"
try {
    $env:AI_WORKSPACE_ROOT = $testRoot
    $config = Get-WorkspaceConfig
    Assert-True ($config.Root -eq $testRoot) 'environment override determines workspace root'
    Assert-True ($config.Paths.bin -eq (Join-Path $testRoot 'bin')) 'bin derives from workspace root'

    & "$PSScriptRoot/../scripts/directories.ps1" -WhatIf
    Assert-True (-not (Test-Path -LiteralPath $testRoot)) 'dry-run creates no directories'
    & "$PSScriptRoot/../scripts/directories.ps1"
    $sentinel = Join-Path $config.Paths.work 'preserve.txt'
    Set-Content -LiteralPath $sentinel -Value 'user data'
    & "$PSScriptRoot/../scripts/directories.ps1"
    Assert-True ((Get-Content -LiteralPath $sentinel) -eq 'user data') 'reruns preserve user data'
    Assert-True (@($config.Paths.Values | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Container) }).Count -eq 0) 'all configured directories exist'

    $missing = Get-PackageState @{ name = 'missing'; command = 'ai-workspace-nonexistent-test-command'; arguments = @('--version') }
    Assert-True (-not $missing.Usable) 'missing executable is not usable'
    $failed = Get-PackageState @{ name = 'failed'; command = 'pwsh'; arguments = @('-NoProfile', '-Command', 'exit 7') }
    Assert-True (-not $failed.Usable) 'nonzero probe is not usable'
    $wrongVersion = Get-PackageState @{ name = 'version'; command = 'pwsh'; arguments = @('--version'); version = '0.0.0' }
    Assert-True (-not $wrongVersion.Usable) 'version mismatch is not usable'

    # Inject malformed configuration without modifying the real manifests.
    function Read-WorkspaceManifest {
        param($Name)
        return @{ workspace = @{ root = '..'; directories = @{ outside = '../outside' } } }
    }
    $rejected = $false
    try { Get-WorkspaceConfig | Out-Null } catch { $rejected = $_.Exception.Message -like '*escapes*' }
    Assert-True $rejected 'directory traversal is rejected'
    Write-Host "Bootstrap tests passed. Isolated fixture retained at $testRoot"
} finally { $env:AI_WORKSPACE_ROOT = $originalRoot }
