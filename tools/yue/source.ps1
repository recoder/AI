#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
$config = Get-YueConfig
Update-ProcessPath
New-Item -ItemType Directory -Path $config.Workspace.Paths.logs -Force | Out-Null
$log = Join-Path $config.Workspace.Paths.logs "yue-source-$([guid]::NewGuid().ToString('N')).log"
Start-Transcript -LiteralPath $log | Out-Null
try {
    $state = Get-YueSourceState $config
    if ($state.Ready) { Write-Host "OK YuE: $($state.Detail)"; return }
    if (-not (Test-Path -LiteralPath $config.Application)) {
        New-Item -ItemType Directory -Path (Split-Path $config.Application -Parent) -Force | Out-Null
        Invoke-YueGit @('clone', '--no-checkout', '--filter=blob:none', '--single-branch', '--branch',
            $config.Declaration.branch, $config.Declaration.repo, $config.Application) | Write-Host
    }
    if (-not (Test-Path -LiteralPath (Join-Path $config.Application '.git'))) { throw "Refusing to modify '$($config.Application)': $($state.Detail)" }
    $remote = Invoke-YueGit @('-C', $config.Application, 'remote', 'get-url', 'origin')
    if ($remote -ne $config.Declaration.repo) { throw 'YuE remote mismatch. Preserve this checkout and resolve config/path explicitly.' }
    # A no-checkout clone is resumable. Never switch an existing checked-out revision automatically.
    $entrypointExists = Test-Path -LiteralPath (Join-Path $config.Application $config.Declaration.entrypoint)
    if ($entrypointExists -or (Test-Path -LiteralPath (Join-Path $config.Application 'README.md')) -or
        (Test-Path -LiteralPath (Join-Path $config.Application '.git/index'))) {
        throw "Refusing to switch or repair an existing checkout automatically: $($state.Detail). Preserve local files and resolve the revision/path explicitly."
    }
    $untracked = Invoke-YueGit @('-C', $config.Application, 'ls-files', '--others', '--exclude-standard')
    if ($untracked) { throw 'YuE partial clone has untracked files; preserve them before retrying.' }
    Invoke-YueGit @('-C', $config.Application, 'fetch', 'origin', $config.Declaration.revision) | Write-Host
    Invoke-YueGit @('-C', $config.Application, 'checkout', '--detach', $config.Declaration.revision) | Write-Host
    $state = Get-YueSourceState $config
    if (-not $state.Ready) { throw $state.Detail }
    Write-Host "OK YuE source prepared: $($config.Application)"
    Write-Host 'Next: just install yue, then just models yue and just validate yue'
} finally { Stop-Transcript | Out-Null; Write-Host "Log: $log" }
