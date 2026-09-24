# Shared managed application source and environment operations.
. "$PSScriptRoot/common.ps1"
. "$PSScriptRoot/repositories.ps1" -DefinitionsOnly

function Get-ApplicationConfig {
    param([Parameter(Mandatory)][string]$Tool)
    $manifest = (Read-WorkspaceManifest tools).tools
    if ($Tool -notmatch '^[a-z0-9][a-z0-9-]*$' -or -not $manifest.Contains($Tool)) { throw "Unknown tool '$Tool'." }
    $toolConfig = $manifest[$Tool]
    if ($toolConfig.revision -notmatch '^[a-f0-9]{40}$') { throw "Managed tool '$Tool' must pin an exact commit." }
    $workspace = Get-WorkspaceConfig
    $paths = @{}
    foreach ($field in @('path','model_path')) {
        if ([string]::IsNullOrWhiteSpace($toolConfig[$field]) -or [IO.Path]::IsPathRooted($toolConfig[$field])) { throw "Tool '$Tool' $field must be workspace-relative." }
        $path = [IO.Path]::GetFullPath($toolConfig[$field],$workspace.Root)
        if (-not $path.StartsWith($workspace.Root.TrimEnd('\','/')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw "Tool '$Tool' path escapes workspace." }
        $paths[$field] = $path
    }
    return [pscustomobject]@{ Name=$Tool; Declaration=$toolConfig; Application=$paths.path; Models=$paths.model_path; Workspace=$workspace }
}

function Initialize-ApplicationSource {
    param($Config)
    $state = Get-RepositoryState $Config.Application $Config.Declaration.repo $Config.Declaration.revision
    if ($state.Ready -and -not $state.Dirty -and (Test-Path -LiteralPath (Join-Path $Config.Application $Config.Declaration.entrypoint))) { Write-Host "OK source $($Config.Name): pinned revision"; return }
    if (-not $state.Missing) {
        # Only a clone that never completed checkout may be resumed.
        if (Test-Path -LiteralPath (Join-Path $Config.Application '.git/index')) { throw "Tool source $($Config.Name): $($state.Detail); resolve explicitly, preserving changes." }
        $remote = Invoke-WorkspaceGit @('-C',$Config.Application,'remote','get-url','origin')
        if ($remote -ne $Config.Declaration.repo -or (Invoke-WorkspaceGit @('-C',$Config.Application,'ls-files','--others','--exclude-standard'))) { throw 'Partial tool checkout conflicts with declared source; preserve/resolve explicitly.' }
    } else {
        New-Item -ItemType Directory -Path (Split-Path $Config.Application) -Force | Out-Null
        Invoke-WorkspaceGit @('clone','--filter=blob:none','--no-checkout',$Config.Declaration.repo,$Config.Application) | Write-Host
    }
    Invoke-WorkspaceGit @('-C',$Config.Application,'fetch','origin',$Config.Declaration.revision) | Write-Host
    Invoke-WorkspaceGit @('-C',$Config.Application,'checkout','--detach',$Config.Declaration.revision) | Write-Host
    $state = Get-RepositoryState $Config.Application $Config.Declaration.repo $Config.Declaration.revision
    if (-not $state.Ready -or $state.Dirty) { throw "Tool source validation failed: $($state.Detail)" }
}

function Initialize-ApplicationEnvironment {
    param($Config, [string]$Project)
    $saved = $env:UV_PROJECT_ENVIRONMENT
    try {
        $env:UV_PROJECT_ENVIRONMENT = Join-Path $Config.Application '.venv'
        & uv sync --frozen --project $Project --python $Config.Declaration.python
        if ($LASTEXITCODE -ne 0) { throw "Environment sync failed. Retry just install $($Config.Name)." }
    } finally { $env:UV_PROJECT_ENVIRONMENT = $saved }
}
