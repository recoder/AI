. "$PSScriptRoot/../../scripts/common.ps1"

function Get-YueConfig {
    $tool = (Read-WorkspaceManifest tools).tools.yue
    if ($tool.generation -ne 'YuE2' -or $tool.backend -ne 'wan2gp' -or $tool.runtime -ne 'native' -or $tool.revision -notmatch '^[a-f0-9]{40}$') {
        throw 'YuE requires the native Wan2GP YuE2 backend and an exact source commit revision.'
    }
    $workspace = Get-WorkspaceConfig
    $paths = @{}
    foreach ($field in @('path', 'model_path')) {
        if ([string]::IsNullOrWhiteSpace($tool[$field]) -or [IO.Path]::IsPathRooted($tool[$field])) {
            throw "YuE '$field' must be a nonempty workspace-relative path."
        }
        $resolved = [IO.Path]::GetFullPath($tool[$field], $workspace.Root)
        if (-not $resolved.StartsWith($workspace.Root.TrimEnd('\', '/') + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw "YuE '$field' escapes the workspace root."
        }
        $paths[$field] = $resolved
    }
    return [pscustomobject]@{ Declaration = $tool; Application = $paths.path;
        Models = $paths.model_path; Workspace = $workspace }
}

function Get-YueState {
    param($Config = (Get-YueConfig))
    $source = Get-YueSourceState $Config
    $python = Join-Path $Config.Application '.venv/Scripts/python.exe'
    $runtime = Test-Path -LiteralPath $python -PathType Leaf
    $declaration = (Read-WorkspaceManifest models).models.yue
    if ($declaration.path -ne $Config.Declaration.model_path) { throw 'YuE tool/model destination declarations must agree.' }
    $missing = @($declaration.files | Where-Object {
        $path = [IO.Path]::GetFullPath($_.name, $Config.Models)
        if (-not $path.StartsWith($Config.Models.TrimEnd('\', '/') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Model artifact escapes its destination.' }
        -not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -ne $_.size
    })
    $runner = Test-Path -LiteralPath (Join-Path $Config.Workspace.Paths.bin 'yue.yaml') -PathType Leaf
    return [pscustomobject]@{ Source = $source; Runtime = $runtime; Python = $python;
        Models = ($missing.Count -eq 0); MissingModels = $missing; Runner = $runner;
        Ready = ($source.Ready -and $runtime -and $missing.Count -eq 0 -and $runner) }
}

function Invoke-YueGit {
    param([string[]]$Arguments)
    $git = Get-Command git -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $result = Invoke-WorkspaceCommand -FilePath $git.Source -Arguments $Arguments -TimeoutSeconds 300
    if ($result.TimedOut -or $result.ExitCode -ne 0) {
        throw "YuE Git operation failed (exit $($result.ExitCode), timeout $($result.TimedOut)): $($result.ErrorOutput). Retry just source yue after resolving the error."
    }
    return $result.Output.Trim()
}

function Get-YueSourceState {
    param($Config = (Get-YueConfig))
    if (-not (Test-Path -LiteralPath $Config.Application)) { return [pscustomobject]@{ Ready = $false; Detail = 'repository missing' } }
    if (-not (Test-Path -LiteralPath (Join-Path $Config.Application '.git'))) { return [pscustomobject]@{ Ready = $false; Detail = 'application path is not a managed Git repository' } }
    try {
        $remote = Invoke-YueGit @('-C', $Config.Application, 'remote', 'get-url', 'origin')
        if ($remote -ne $Config.Declaration.repo) { throw "wrong remote '$remote'" }
        $head = Invoke-YueGit @('-C', $Config.Application, 'rev-parse', 'HEAD')
        if ($head -ne $Config.Declaration.revision) { throw "revision mismatch: $head" }
        $changes = Invoke-YueGit @('-C', $Config.Application, 'status', '--porcelain', '--untracked-files=no')
        if ($changes) { throw 'tracked source files have local changes; preserve them before reconciliation' }
        if (-not (Test-Path -LiteralPath (Join-Path $Config.Application $Config.Declaration.entrypoint) -PathType Leaf)) { throw 'inference entrypoint missing' }
        return [pscustomobject]@{ Ready = $true; Detail = "pinned Wan2GP source $head" }
    } catch { return [pscustomobject]@{ Ready = $false; Detail = $_.Exception.Message } }
}
