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

    $interpreter = (Get-Command pwsh).Source
    $hung = Get-PackageState @{ name = 'hung'; command = 'pwsh';
        arguments = @('-NoProfile', '-Command', 'Start-Sleep -Seconds 10'); probe_timeout_seconds = 1 }
    Assert-True (-not $hung.Usable -and $hung.Detail -like '*timed out*') 'hung probes time out'
    $streams = Invoke-WorkspaceCommand -FilePath $interpreter -Arguments @('-NoProfile', '-Command',
        '[Console]::Out.Write("stdout"); [Console]::Error.Write("stderr"); exit 9')
    Assert-True ($streams.ExitCode -eq 9 -and $streams.Output -eq 'stdout' -and $streams.ErrorOutput -eq 'stderr') 'both streams and exit code are retained'
    $echoScript = Join-Path $testRoot 'echo arguments.ps1'
    Set-Content -LiteralPath $echoScript -Value 'ConvertTo-Json -InputObject @($args) -Compress'
    $literalArguments = @('a path with spaces', '"quoted"', '$(not executed)', 'semi;colon')
    $echo = Invoke-WorkspaceCommand -FilePath $interpreter -Arguments (@('-NoProfile', '-File', $echoScript) + $literalArguments)
    $roundTrip = @(ConvertFrom-Json $echo.Output)
    Assert-True ($echo.ExitCode -eq 0 -and $roundTrip.Count -eq $literalArguments.Count) 'argument count is preserved'
    for ($i = 0; $i -lt $literalArguments.Count; $i++) {
        Assert-True ($roundTrip[$i] -ceq $literalArguments[$i]) "argument $i remains literal"
    }
    $originalInvoker = (Get-Item Function:Invoke-WorkspaceCommand).ScriptBlock
    try {
        function Invoke-WorkspaceCommand { throw 'simulated process launch error' }
        $launchFailure = Get-PackageState @{ name = 'launch'; command = 'pwsh'; arguments = @('--version') }
        Assert-True (-not $launchFailure.Usable -and $launchFailure.Detail -like '*simulated*') 'launch failures return unusable state instead of aborting diagnostics'
    } finally { Set-Item Function:Invoke-WorkspaceCommand $originalInvoker }
    Assert-True ((Get-InstallerFailureMessage -2147024864) -like '*0x80070020*regression*') 'WinGet sharing failure includes its hex code and recovery guidance'
    $pathBefore = $env:PATH
    try {
        Update-ProcessPath
        $pathOnce = $env:PATH
        Update-ProcessPath
        Assert-True ($env:PATH -eq $pathOnce) 'PATH refresh is idempotent'
    } finally { $env:PATH = $pathBefore }

    # Inject malformed configuration without modifying the real manifests.
    function Read-WorkspaceManifest {
        param($Name)
        return @{ workspace = @{ root = '..'; directories = @{ outside = '../outside' } } }
    }
    $rejected = $false
    try { Get-WorkspaceConfig | Out-Null } catch { $rejected = $_.Exception.Message -like '*escapes*' }
    Assert-True $rejected 'directory traversal is rejected'
    function Read-WorkspaceManifest {
        param($Name)
        return @{ packages = @(@{ name = 'bad'; id = 'test'; command = 'pwsh'; arguments = @('--version'); scope = 'invalid' }) }
    }
    $rejected = $false
    try { Get-PackageConfig | Out-Null } catch { $rejected = $_.Exception.Message -like '*invalid scope*' }
    Assert-True $rejected 'invalid package scope is rejected before installation'
    Write-Host "Bootstrap tests passed. Isolated fixture retained at $testRoot"
} finally { $env:AI_WORKSPACE_ROOT = $originalRoot }
