#requires -Version 7.4
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/../tools/yue/common.ps1"
$originalRoot = $env:AI_WORKSPACE_ROOT
$fixture = Join-Path $script:RepositoryRoot "cache/yue-tests/$([guid]::NewGuid().ToString('N'))"
try {
    $env:AI_WORKSPACE_ROOT = $fixture
    $config = Get-YueConfig
    if ($config.Application -ne (Join-Path $fixture 'apps/wan2gp')) { throw 'YuE source path ignores workspace override.' }
    if ((Get-YueSourceState $config).Ready) { throw 'Missing source must not appear ready.' }
    New-Item -ItemType Directory -Path $config.Application -Force | Out-Null
    $sentinel = Join-Path $config.Application 'user-content.txt'
    Set-Content -LiteralPath $sentinel -Value 'preserve me'
    Invoke-YueGit @('init', $config.Application) | Out-Null
    Invoke-YueGit @('-C', $config.Application, 'remote', 'add', 'origin', 'https://example.invalid/wrong.git') | Out-Null
    $state = Get-YueSourceState $config
    if ($state.Ready -or $state.Detail -notlike '*wrong remote*') { throw 'Wrong source remote was not detected.' }
    $rejected = $false
    try { & "$PSScriptRoot/../tools/yue/source.ps1" }
    catch { $rejected = $_.Exception.Message -like '*remote mismatch*' }
    if (-not $rejected) { throw 'Source reconciliation must refuse a wrong remote without fetching.' }
    if ((Get-Content -LiteralPath $sentinel) -ne 'preserve me') { throw 'Source reconciliation changed user content.' }
    Write-Host "YuE source safety tests passed. Fixture retained at $fixture"
} finally { $env:AI_WORKSPACE_ROOT = $originalRoot }
